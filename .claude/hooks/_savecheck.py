"""
Shared by the hooks that run the project's save-tier check: lint-on-save.py
(files written with Edit/Write) and bash-write-check.py (files written through
Bash). Not a hook itself — the leading underscore keeps it out of the hook
registry and the hook tests.

Everything stack-specific lives in `.claude/scripts/verify-save`, whose contract
is in .claude/scripts/README.md. This module only finds that script, runs it on
one path, and hands the result to Claude.
"""

import json
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.join(".claude", "scripts")
TIER = "save"

# Must stay below the hook's own timeout in .claude/settings.json, or the
# harness kills us first and the message is never seen. The save tier is
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


def report(event: str, message: str) -> None:
    """
    Hand a message to Claude. Plain stderr with exit 0 is never shown to it
    (code.claude.com/docs/en/hooks), which is how lint-on-save went unseen.
    """
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": message,
                }
            }
        )
    )


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


def check(
    argv: list[str],
    rel: str,
    file_path: str,
    project_dir: str,
    tag: str,
    timeout: float = TIMEOUT_SECONDS,
) -> str | None:
    """
    Run verify-save on one file. Returns the text Claude should see, or None
    when the check passed silently (the contract's "nothing to report").
    """
    try:
        result = subprocess.run(
            [*argv, file_path],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return (
            f"[{tag}] {rel} timed out after {timeout:.0f}s — "
            "the save tier is meant to take seconds."
        )
    except OSError as exc:
        return f"[{tag}] could not run {rel}: {exc}"

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
            return f"[{tag}] {rel_path} (passed with notes):\n{output}"
        return None

    return f"[{tag}] {rel_path}:\n" + (
        output or f"{rel} exited {result.returncode} with no output"
    )
