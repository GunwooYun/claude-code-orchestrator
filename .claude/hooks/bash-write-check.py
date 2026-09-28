#!/usr/bin/env python3
"""
PreToolUse + PostToolUse hook on Bash: run the save-tier check on files a Bash
command wrote.

lint-on-save.py only sees Edit/Write. A file written with `sed -i`, a
redirection or a python heredoc skipped verify-save entirely — observed twice on
real runs in an adopting project, once on the gate scripts themselves.

  Pre   record the time, keyed by the tool call's `tool_use_id`
  Post  find files under the project modified since then, run verify-save on
        them (at most MAX_CHECKED), and tell Claude what failed

Detection is by mtime, not git: the observed files (.claude/, CLAUDE.md) were
gitignored. Known blind spots, by design: tools that preserve old mtimes
(`cp -p`, `touch -d`), coarse-mtime filesystems, and trees too large to walk
within WALK_SECONDS — the last is reported once per session, not hidden.

A safety net, not the path: CLAUDE.md tells the model to edit with Edit/Write.
Advisory only: every path exits 0, and nothing is said when nothing was written.
"""

import json
import os
import re
import sys
import time

from _savecheck import check, report, resolve_script

MARKS_DIR = os.path.join(".claude", "logs", "bash-marks")
STALE_SECONDS = 3600
WALK_SECONDS = 3.0
WALK_MAX_ENTRIES = 50_000
MAX_CHECKED = 5
# The whole Post run, walk included. Below the registered hook timeout in
# .claude/settings.json, so the harness never kills the hook before it reports.
TIMEOUT_SECONDS = 25

# Directories whose contents are generated, vendored or the hooks' own state.
PRUNED_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".cache",
        "dist",
        "build",
        "target",
        "out",
        "coverage",
        "htmlcov",
    }
)
PRUNED_PATHS = (
    os.path.join(".claude", "logs"),
    os.path.join(".claude", "checkpoints"),
)

# Only for the nudge line; detection does not depend on it.
WRITE_PATTERN = re.compile(
    r"\bsed\s+(-\w*\s+)*-i|(^|[^0-9&<>])>>?\s*[\w./~-]|\btee\b|write_text|"
    r"open\([^)]*['\"][wa]\+?['\"]"
)
GATE_SCRIPT = re.compile(r"^\.claude[/\\]scripts[/\\]verify-")


def read_payload() -> dict:
    """Read the hook payload from stdin. Returns {} when unusable."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def mark_path(project_dir: str, tool_use_id: str) -> str:
    safe = "".join(c for c in tool_use_id if c.isalnum() or c in "-_")[:80]
    return os.path.join(project_dir, MARKS_DIR, safe)


def sweep_stale(marks: str) -> None:
    """Drop marks whose Post never came (a crash, a killed command)."""
    cutoff = time.time() - STALE_SECONDS
    for name in os.listdir(marks):
        path = os.path.join(marks, name)
        if os.path.getmtime(path) < cutoff:
            os.remove(path)


def on_pre(project_dir: str, tool_use_id: str) -> None:
    path = mark_path(project_dir, tool_use_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sweep_stale(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("")


def take_mark(project_dir: str, tool_use_id: str) -> int | None:
    """
    The mark's own mtime, not a time.time_ns() written into it: file mtimes come
    from the kernel's coarse clock (a tick of a few ms), so a file written just
    after a precise timestamp can carry an EARLIER mtime and be missed — found
    by this hook's tests. Comparing mtime with mtime uses one clock.
    """
    path = mark_path(project_dir, tool_use_id)
    try:
        started = os.stat(path).st_mtime_ns
        os.remove(path)
    except OSError:
        return None
    return started


def only_git(command: str) -> bool:
    """checkout/pull/stash rewrite files that are not the model's edits."""
    segments = [s.strip() for s in re.split(r"&&|\|\||;|\|", command) if s.strip()]
    return bool(segments) and all(s.split()[0] == "git" for s in segments)


def modified_since(project_dir: str, started_ns: int) -> tuple[list[str], bool]:
    """
    Files under project_dir modified after started_ns, as project-relative
    paths. The bool is False when the walk ran out of budget.
    """
    found: list[str] = []
    deadline = time.monotonic() + WALK_SECONDS
    entries = 0
    for root, dirs, files in os.walk(project_dir, followlinks=False):
        rel_root = os.path.relpath(root, project_dir)
        dirs[:] = [
            d
            for d in dirs
            if d not in PRUNED_NAMES
            and os.path.normpath(os.path.join(rel_root, d)) not in PRUNED_PATHS
        ]
        for name in files:
            entries += 1
            path = os.path.join(root, name)
            try:
                stat = os.lstat(path)
            except OSError:
                continue
            if stat.st_mtime_ns >= started_ns and os.path.isfile(path):
                found.append(os.path.relpath(path, project_dir))
        if entries > WALK_MAX_ENTRIES or time.monotonic() > deadline:
            return found, False
    return sorted(found), True


def warn_too_large_once(project_dir: str, session: str) -> str | None:
    safe = "".join(c for c in session if c.isalnum() or c in "-_")[:64] or "session"
    marker = os.path.join(project_dir, MARKS_DIR, f".too-large.{safe}")
    if os.path.exists(marker):
        return None
    try:
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write("reported\n")
    except OSError:
        pass
    return (
        "[bash-write] this tree is too large to scan after each Bash call, so "
        "files written through Bash are not save-checked here. Edit with "
        "Edit/Write. (reported once per session)"
    )


def on_post(project_dir: str, payload: dict, tool_use_id: str) -> None:
    budget_end = time.monotonic() + TIMEOUT_SECONDS
    started = take_mark(project_dir, tool_use_id)
    if started is None:
        return
    tool_input = payload.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(command, str) or only_git(command):
        return

    files, complete = modified_since(project_dir, started)
    if not complete:
        notice = warn_too_large_once(project_dir, str(payload.get("session_id", "")))
        if notice:
            report("PostToolUse", notice)
        return
    if not files:
        return

    lines: list[str] = []
    resolved = resolve_script(project_dir)
    if resolved is not None:
        argv, rel = resolved
        for index, path in enumerate(files[:MAX_CHECKED]):
            remaining = budget_end - time.monotonic()
            if remaining < 1:
                lines.append(
                    f"[bash-write] out of time after {index} file(s); run {rel} "
                    "on the rest."
                )
                break
            message = check(
                argv,
                rel,
                os.path.join(project_dir, path),
                project_dir,
                "bash-write",
                timeout=remaining,
            )
            if message:
                lines.append(message)
        if len(files) > MAX_CHECKED:
            lines.append(
                f"[bash-write] checked {MAX_CHECKED} of {len(files)} files written "
                f"by this command; run {rel} on the rest."
            )

    if any(GATE_SCRIPT.match(path) for path in files):
        lines.append(
            "[bash-write] a gate script was rewritten via Bash — smoke-test it on a "
            "known-bad file before trusting it (README Step E)."
        )
    if WRITE_PATTERN.search(command):
        lines.append(
            "[bash-write] this command wrote files through Bash; use Edit/Write — "
            "the save check runs at edit time there."
        )
    if lines:
        report("PostToolUse", "\n".join(lines))


def main() -> None:
    payload = read_payload()
    tool_use_id = payload.get("tool_use_id")
    if not isinstance(tool_use_id, str) or not tool_use_id:
        return
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    event = payload.get("hook_event_name")
    if event == "PreToolUse":
        on_pre(project_dir, tool_use_id)
    elif event == "PostToolUse":
        on_post(project_dir, payload, tool_use_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - a hook must never break the session
        print(f"[bash-write] hook error (ignored): {exc}", file=sys.stderr)
    sys.exit(0)
