#!/usr/bin/env python3
"""
PostToolUse hook: suggest a deep-reasoning review after substantial implementation.

Counts source files touched and lines written in THIS session, in THIS project,
and suggests a review once a threshold is crossed. Advisory only: PostToolUse
cannot block, so every path exits 0.

Three defects shaped this rewrite:

  1. State lived at one hard-coded `/tmp/claude-code-implementation-state.json`
     shared by every project and every session. Once `review_suggested` was set
     the hook was mute for ever, and counters accumulated across unrelated
     repositories. State is now per project and per session, which also removes
     the need for a SessionStart hook to reset anything.
  2. That path is world-writable and predictable, so anyone on the machine could
     pre-create it as a symlink and have the hook write through it. State now
     lives under the project's own .claude/logs/, and the write refuses to
     follow a symlink.
  3. Which files counted was a hard-coded list of seven extensions, so an
     implementation in any other language was invisible. The test is now
     exclusion-based: anything that is not documentation, config, data or a
     lockfile counts — so Kotlin, SQL, a BitBake recipe or a shell script all do.
"""

import json
import os
import sys
import time
from pathlib import Path

MAX_PATH_LENGTH = 4096
MAX_CONTENT_LENGTH = 1_000_000

# Thresholds for suggesting a review.
MIN_FILES_FOR_REVIEW = 3
MIN_LINES_FOR_REVIEW = 100

# Per-session state files are cheap, but they must not pile up for ever.
STATE_RETENTION_DAYS = 7
STATE_DIR_PARTS = (".claude", "logs", "implementation-state")

# Extensions that are NOT an implementation. Everything else counts, so a
# language nobody thought to list is still seen. Kept as an exclusion list for
# exactly that reason — the previous inclusion list had seven entries and missed
# every other language.
NON_SOURCE_SUFFIXES = frozenset(
    {
        # documentation and prose
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".adoc",
        ".tex",
        ".pdf",
        # data and config
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".env",
        ".csv",
        ".tsv",
        ".xml",
        ".properties",
        ".editorconfig",
        # assets
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
        ".mp4",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        # build output and archives
        ".lock",
        ".log",
        ".bak",
        ".tmp",
        ".zip",
        ".tar",
        ".gz",
        ".whl",
        ".pyc",
    }
)

# Exact filenames that are config or generated even though their suffix is not.
NON_SOURCE_NAMES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "uv.lock",
        "poetry.lock",
        "Cargo.lock",
        "go.sum",
        "Gemfile.lock",
        "LICENSE",
        "NOTICE",
        "CODEOWNERS",
        ".gitignore",
        ".gitattributes",
    }
)

# Directories whose contents are generated, vendored, or not ours.
NON_SOURCE_DIRS = frozenset(
    {".git", ".venv", "node_modules", "__pycache__", "dist", "build", "vendor"}
)

# Line prefixes that start a comment in some widely used language. Used only to
# avoid counting comment-only lines as implementation; a false negative here
# costs nothing.
COMMENT_PREFIXES = ("#", "//", "--", ";", "/*", "*", "<!--")


def validate_input(file_path: str, content: str) -> bool:
    """Reject inputs that are missing, over-long, or traversing."""
    if not file_path or len(file_path) > MAX_PATH_LENGTH:
        return False
    if len(content) > MAX_CONTENT_LENGTH:
        return False
    if ".." in file_path:
        return False
    return True


def is_source_file(file_path: str) -> bool:
    """
    True when editing this path plausibly counts as implementation.

    Exclusion-based on purpose: an unfamiliar extension counts as source, because
    the cost of missing a language is a hook that never fires, while the cost of
    counting one extra file type is one early suggestion.
    """
    path = Path(file_path)
    if set(path.parts) & NON_SOURCE_DIRS:
        return False
    if path.name in NON_SOURCE_NAMES:
        return False
    if path.suffix.lower() in NON_SOURCE_SUFFIXES:
        return False
    # No extension at all: a script or a binary. Scripts are source, but there is
    # no way to tell from the path, so leave these out rather than guess.
    return bool(path.suffix)


def count_lines(content: str) -> int:
    """Count lines that are neither blank nor comment-only, in any language."""
    total = 0
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(COMMENT_PREFIXES):
            continue
        total += 1
    return total


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))


def state_dir(root: Path | None = None) -> Path:
    """Where per-session state lives: inside the project, already gitignored."""
    return (root or project_root()).joinpath(*STATE_DIR_PARTS)


def state_filename(session_id: str) -> str:
    """A filename derived from the session id, safe on any filesystem."""
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:80]
    return f"{safe or 'unknown'}.json"


def session_id_from(payload: dict) -> str:
    """Prefer the payload's session id; fall back to the environment."""
    for value in (payload.get("session_id"), os.environ.get("CLAUDE_SESSION_ID")):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


def empty_state() -> dict:
    return {"files_changed": [], "total_lines": 0, "review_suggested": False}


def load_state(path: Path) -> dict:
    """Read this session's state, falling back to an empty one."""
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError, ValueError):
        return empty_state()
    if not isinstance(state, dict):
        return empty_state()
    merged = empty_state()
    merged.update({k: v for k, v in state.items() if k in merged})
    if not isinstance(merged["files_changed"], list):
        merged["files_changed"] = []
    if not isinstance(merged["total_lines"], int):
        merged["total_lines"] = 0
    return merged


def save_state(path: Path, state: dict) -> None:
    """
    Write this session's state, refusing to follow a symlink.

    Failures are ignored: the hook is advisory, and losing a counter is better
    than disrupting the session. The symlink check is what the old predictable
    /tmp path made necessary.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            return
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
    except OSError:
        return


def prune_stale_state(directory: Path, keep: str) -> None:
    """Delete session state older than the retention window."""
    cutoff = time.time() - STATE_RETENTION_DAYS * 86400
    try:
        entries = list(directory.iterdir())
    except OSError:
        return
    for entry in entries:
        if entry.name == keep or entry.suffix != ".json":
            continue
        try:
            if entry.stat().st_mtime < cutoff:
                entry.unlink()
        except OSError:
            continue


def should_suggest_review(state: dict) -> tuple[bool, str]:
    """Decide whether this session has accumulated enough to warrant a review."""
    if state.get("review_suggested"):
        return False, ""

    files_count = len(state.get("files_changed", []))
    total_lines = state.get("total_lines", 0)

    if files_count >= MIN_FILES_FOR_REVIEW:
        return True, f"{files_count} source files touched"
    if total_lines >= MIN_LINES_FOR_REVIEW:
        return True, f"{total_lines}+ lines written"
    return False, ""


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    if not isinstance(payload, dict):
        return
    if payload.get("tool_name") not in ("Write", "Edit"):
        return

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    file_path = tool_input.get("file_path") or ""
    content = tool_input.get("content") or tool_input.get("new_string") or ""
    if not isinstance(file_path, str) or not isinstance(content, str):
        return
    if not validate_input(file_path, content) or not is_source_file(file_path):
        return

    root = project_root()
    directory = state_dir(root)
    filename = state_filename(session_id_from(payload))
    path = directory / filename

    state = load_state(path)
    if file_path not in state["files_changed"]:
        state["files_changed"].append(file_path)
    state["total_lines"] += count_lines(content)

    should_review, reason = should_suggest_review(state)
    if should_review:
        state["review_suggested"] = True

    save_state(path, state)
    prune_stale_state(directory, keep=filename)

    if not should_review:
        return

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        f"[Code Review Suggestion] {reason} in this session. "
                        "Consider having the deep-reasoning subagent review the "
                        "implementation. **Recommended**: Use Task tool with "
                        "subagent_type='deep-reasoning' with git diff to preserve "
                        "main context. If you are a subagent, report back to the "
                        "orchestrator instead."
                    ),
                }
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - a hook must never break the session
        print(f"Hook error (ignored): {exc}", file=sys.stderr)
    sys.exit(0)
