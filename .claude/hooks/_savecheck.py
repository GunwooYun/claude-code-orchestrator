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
import shutil
import subprocess
import sys
from collections.abc import Callable

SCRIPTS_DIR = os.path.join(".claude", "scripts")
TIER = "save"

# Windows cannot exec a shebang script (WinError 193, seen on every save on a
# real Windows project): such a script runs through an interpreter named here.
SH_NAMES = frozenset({"sh", "dash", "ash", "bash", "zsh"})
GIT_BASH_ENV = "CLAUDE_CODE_GIT_BASH_PATH"
# argv[0] when a sh script needs sh and none was found: check() reports it.
NO_SH = ""

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


def shebang_runner(path: str, which: Callable[[str], str | None]) -> list[str] | None:
    """
    How Windows runs an extensionless script: by its shebang. A sh-family
    shebang runs through sh (Git Bash's, or NO_SH when there is none); a Python
    one through this interpreter; anything else is not runnable here.
    """
    try:
        with open(path, "rb") as handle:
            first = handle.readline(256)
    except OSError:
        return None
    if not first.startswith(b"#!"):
        return None
    words = first[2:].decode("utf-8", "replace").split()
    if words and os.path.basename(words[0]) == "env":
        words = words[1:]
    if not words:
        return None
    name = os.path.basename(words[0]).lower().removesuffix(".exe")
    if name in SH_NAMES:
        sh = which("sh") or which("bash") or os.environ.get(GIT_BASH_ENV)
        return [sh or NO_SH]
    if name.startswith("python"):
        return [sys.executable]
    return None


def is_sh(program: str) -> bool:
    name = os.path.basename(program).lower().removesuffix(".exe")
    return name in SH_NAMES


def resolve_script(
    project_dir: str,
    windows: bool | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> tuple[list[str], str] | None:
    """
    Find the project's verify-save script.

    Returns (argv prefix, relative path) or None when no tier script exists.
    An extensionless file must be executable — on Windows, where every file
    counts as executable and none can be exec'd by its shebang, it runs through
    the interpreter its shebang names instead. A file with a known extension is
    run through its interpreter, so it needs neither an execute bit nor a
    shebang.
    """
    windows = os.name == "nt" if windows is None else windows
    for suffix, prefix in INTERPRETERS:
        rel = os.path.join(SCRIPTS_DIR, f"verify-{TIER}{suffix}")
        path = os.path.join(project_dir, rel)
        if not os.path.isfile(path):
            continue
        if not prefix:
            if windows:
                runner = shebang_runner(path, which)
                if runner is None:
                    continue
                return [*runner, path], rel
            if not os.access(path, os.X_OK):
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
    windows: bool | None = None,
) -> str | None:
    """
    Run verify-save on one file. Returns the text Claude should see, or None
    when the check passed silently (the contract's "nothing to report").
    """
    if argv[0] == NO_SH:
        return (
            f"[{tag}] could not run {rel}: it is a sh script and no sh was found "
            f"on PATH (nor {GIT_BASH_ENV}) — on Windows the save check needs Git "
            "Bash (Git for Windows), or a verify-save.py / .ps1 next to it."
        )
    # sh on Windows: forward slashes, or the script's `*/dir/*` globs never match.
    windows = os.name == "nt" if windows is None else windows
    arg = file_path.replace("\\", "/") if windows and is_sh(argv[0]) else file_path
    try:
        result = subprocess.run(
            [*argv, arg],
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
