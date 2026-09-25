#!/usr/bin/env python3
"""
PostToolUse hook: run the project's save-tier check after Edit/Write.

This hook knows NOTHING about any language or tool. It reads the edited file's
path from the stdin payload and hands it to the project's `verify-save` script,
whose contract is in .claude/scripts/README.md.

Everything stack-specific — which file types are checked, which tools run, and
whether they run locally, in a container or on a target device — lives in that
script, where a person can run it by hand. `/initproject` writes it once per
project.

Advisory only: PostToolUse cannot undo a write, so every path exits 0.

History, so the same bugs are not reintroduced:
  - an early version read a `CLAUDE_TOOL_INPUT` environment variable that Claude
    Code does not set, making it a permanent no-op
  - a later one hard-coded ruff and ty, so it did nothing on a project using
    neither
  - a later one discarded the script's output whenever it exited 0, which hides
    tools that warn on success and made the model report "clean"
"""

import json
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.join(".claude", "scripts")
TIER = "save"
MAX_PATH_LENGTH = 4096

# Must stay below the hook's own timeout in .claude/settings.json, or the
# harness kills us first and the message below is never seen. The save tier is
# specified in seconds, so this is a backstop, not a budget.
TIMEOUT_SECONDS = 25

# An extensionless executable first (the portable default), then forms that need
# no execute bit or shebang — which is what Windows checkouts have.
INTERPRETERS: tuple[tuple[str, list[str]], ...] = (
    ("", []),
    (".py", [sys.executable]),
    (".sh", ["sh"]),
    (".ps1", ["pwsh", "-File"]),
    (".cmd", ["cmd", "/c"]),
    (".bat", ["cmd", "/c"]),
)


def read_payload() -> dict:
    """Read the hook payload from stdin. Returns {} when unusable."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def get_file_path(payload: dict) -> str | None:
    """Extract the edited file's path from the hook payload."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str):
        return None
    if not file_path or len(file_path) > MAX_PATH_LENGTH or ".." in file_path:
        return None
    return file_path


def resolve_script(project_dir: str) -> tuple[list[str], str] | None:
    """
    Find the project's verify-save script.

    Returns (argv prefix, relative path) or None when no tier script exists.
    An extensionless file must be executable; a file with a known extension is
    run through its interpreter, so it needs neither an execute bit nor a
    shebang.
    """
    for suffix, prefix in INTERPRETERS:
        rel = os.path.join(SCRIPTS_DIR, f"verify-{TIER}{suffix}")
        path = os.path.join(project_dir, rel)
        if not os.path.isfile(path):
            continue
        if not prefix and not os.access(path, os.X_OK):
            continue
        return [*prefix, path], rel
    return None


def notice_path(project_dir: str) -> str:
    """Where the once-per-session marker for the missing-script notice lives."""
    session = os.environ.get("CLAUDE_SESSION_ID", "session")
    safe = "".join(c for c in session if c.isalnum() or c in "-_")[:64] or "session"
    return os.path.join(project_dir, ".claude", "logs", f".no-verify-save.{safe}")


def warn_missing_once(project_dir: str) -> None:
    """
    Say "no save tier configured" once per session, not on every edit.

    A project may legitimately have no save tier (checks that need the whole
    project loaded, or that only run in CI). Repeating the notice on every save
    trains people to ignore hook output.
    """
    marker = notice_path(project_dir)
    try:
        if os.path.exists(marker):
            return
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write("reported\n")
    except OSError:
        pass  # cannot track it; better to repeat the notice than to lose it
    print(
        f"[lint-on-save] no {SCRIPTS_DIR}/verify-{TIER} in this project — "
        "the save-tier check is not configured. This is fine if checks run at a "
        "slower tier; see .claude/scripts/README.md. (reported once per session)",
        file=sys.stderr,
    )


def main() -> None:
    file_path = get_file_path(read_payload())
    if not file_path or not os.path.isfile(file_path):
        return

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    resolved = resolve_script(project_dir)
    if resolved is None:
        warn_missing_once(project_dir)
        return
    argv, rel = resolved

    try:
        result = subprocess.run(
            [*argv, file_path],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(
            f"[lint-on-save] {rel} timed out after {TIMEOUT_SECONDS}s — "
            "the save tier is meant to take seconds.",
            file=sys.stderr,
        )
        return
    except OSError as exc:
        print(f"[lint-on-save] could not run {rel}: {exc}", file=sys.stderr)
        return

    output = f"{result.stdout}{result.stderr}".strip()
    rel_path = (
        os.path.relpath(file_path, project_dir)
        if file_path.startswith(project_dir)
        else file_path
    )

    if result.returncode == 0:
        # Contract: output on success is informational (warnings, progress). It
        # is passed through rather than discarded — swallowing it is how a
        # warning becomes a false "clean".
        if output:
            print(f"[lint-on-save] {rel_path} (passed with notes):", file=sys.stderr)
            print(output, file=sys.stderr)
        return

    print(f"[lint-on-save] {rel_path}:", file=sys.stderr)
    print(output or f"{rel} exited {result.returncode} with no output", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - a hook must never break the session
        print(f"[lint-on-save] hook error (ignored): {exc}", file=sys.stderr)
    sys.exit(0)
