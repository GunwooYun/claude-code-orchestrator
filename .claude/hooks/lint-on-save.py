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
  - every version up to 2026-09-28 reported on stderr with exit 0. The hooks
    reference says that stderr "goes to the debug log only ... and Claude never
    sees it", so no save-tier result ever reached the model. Reports now go out
    as JSON `additionalContext`, the channel Claude receives.
"""

import json
import os
import sys

from _savecheck import SCRIPTS_DIR, TIER, check, report, resolve_script

MAX_PATH_LENGTH = 4096
EVENT = "PostToolUse"


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
    report(
        EVENT,
        f"[lint-on-save] no {SCRIPTS_DIR}/verify-{TIER} in this project — "
        "the save-tier check is not configured. This is fine if checks run at a "
        "slower tier; see .claude/scripts/README.md. (reported once per session)",
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

    message = check(argv, rel, file_path, project_dir, "lint-on-save")
    if message:
        report(EVENT, message)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - a hook must never break the session
        print(f"[lint-on-save] hook error (ignored): {exc}", file=sys.stderr)
    sys.exit(0)
