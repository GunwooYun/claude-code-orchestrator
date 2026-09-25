#!/usr/bin/env python3
"""
PostToolUse hook: run the project's save-tier check after Edit/Write.

This hook knows NOTHING about any language or tool. It reads the edited file's
path from the stdin payload and hands it to `.claude/scripts/verify-save`, whose
contract is documented in .claude/scripts/README.md: exit 0 means nothing to
report, non-zero means issues, and output is only produced on failure.

Everything stack-specific — which file types are checked, which tools run, and
whether they run locally, in a container or on a target device — lives in that
script, where a person can run it by hand and debug it. `/initproject` writes it
once per project.

Advisory only: PostToolUse cannot undo a write, so every path exits 0.

History: an earlier version read a `CLAUDE_TOOL_INPUT` environment variable that
Claude Code does not set, making it a permanent no-op; a later one hard-coded
ruff and ty, so it did nothing useful on a project that uses neither.
"""

import json
import os
import subprocess
import sys

SCRIPT = os.path.join(".claude", "scripts", "verify-save")
MAX_PATH_LENGTH = 4096
TIMEOUT_SECONDS = 120


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


def main() -> None:
    file_path = get_file_path(read_payload())
    if not file_path or not os.path.isfile(file_path):
        return

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    script = os.path.join(project_dir, SCRIPT)
    if not (os.path.isfile(script) and os.access(script, os.X_OK)):
        # Not configured for this project. Say it once, with the path, rather
        # than staying silent and looking like a passing check.
        print(
            f"[lint-on-save] no executable {SCRIPT} — save-tier check skipped. "
            "See .claude/scripts/README.md.",
            file=sys.stderr,
        )
        return

    try:
        result = subprocess.run(
            [script, file_path],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(
            f"[lint-on-save] {SCRIPT} timed out after {TIMEOUT_SECONDS}s — "
            "the save tier is meant to take seconds.",
            file=sys.stderr,
        )
        return
    except OSError as exc:
        print(f"[lint-on-save] could not run {SCRIPT}: {exc}", file=sys.stderr)
        return

    output = f"{result.stdout}{result.stderr}".strip()
    if result.returncode == 0:
        # Contract: a passing run prints nothing, so neither do we.
        return

    rel_path = (
        os.path.relpath(file_path, project_dir)
        if file_path.startswith(project_dir)
        else file_path
    )
    print(f"[lint-on-save] {rel_path}:", file=sys.stderr)
    print(
        output or f"{SCRIPT} exited {result.returncode} with no output", file=sys.stderr
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - a hook must never break the session
        print(f"[lint-on-save] hook error (ignored): {exc}", file=sys.stderr)
    sys.exit(0)
