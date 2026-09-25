#!/usr/bin/env python3
"""
PostToolUse hook: format and check Python files after Edit/Write.

Reads the tool payload from **stdin** (Claude Code does not set a
CLAUDE_TOOL_INPUT environment variable; an earlier version read one and was
therefore a permanent no-op). Never blocks: PostToolUse cannot undo a write
anyway, so every path exits 0.

The commands are still hard-coded to this repository's toolchain
(ruff + ty). They belong in the project profile so the hook works on any
stack; that move is the next step and is tracked in
.claude/docs/DESIGN.md.
"""

import json
import os
import shutil
import subprocess
import sys

MAX_PATH_LENGTH = 4096
COMMAND_TIMEOUT_SECONDS = 30

# Directories whose contents are generated or vendored: formatting them is noise
# at best and a diff the user did not ask for at worst.
SKIPPED_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        "migrations",
        "build",
        "dist",
        ".mypy_cache",
        ".ruff_cache",
    }
)

# Extra places a tool may live when it was installed for the user rather than
# into the project environment.
EXTRA_TOOL_DIRS = (
    os.path.expanduser("~/.local/bin"),
    os.path.expanduser("~/.cargo/bin"),
)


def read_payload() -> dict:
    """Read the hook payload from stdin. Returns {} when unusable."""
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def get_file_path(payload: dict) -> str | None:
    """Extract the edited file's path from the hook payload."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    return file_path if isinstance(file_path, str) else None


def validate_path(file_path: str) -> bool:
    """Reject empty, over-long, or traversing paths."""
    if not file_path or len(file_path) > MAX_PATH_LENGTH:
        return False
    if ".." in file_path:
        return False
    return True


def is_python_file(path: str) -> bool:
    return path.endswith(".py")


def is_generated(path: str) -> bool:
    """True when the path lies inside a generated or vendored directory."""
    parts = set(os.path.normpath(path).split(os.sep))
    return bool(parts & SKIPPED_DIR_NAMES)


def resolve_tool(name: str) -> list[str] | None:
    """
    Build the argv prefix that runs `name`.

    Prefers the project environment (`uv run <name>`) so the pinned version is
    used, falls back to the tool on PATH, then to the usual per-user install
    directories. Returns None when the tool cannot be found at all.
    """
    if shutil.which("uv") and os.path.exists("pyproject.toml"):
        return ["uv", "run", name]
    direct = shutil.which(name)
    if direct:
        return [direct]
    for directory in EXTRA_TOOL_DIRS:
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return [candidate]
    return None


def run_command(cmd: list[str], cwd: str) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {COMMAND_TIMEOUT_SECONDS}s"
    except (FileNotFoundError, PermissionError) as exc:
        return 1, "", f"Could not run {cmd[0]}: {exc}"


def check_file(file_path: str, project_dir: str) -> list[str]:
    """Format and check one file. Returns human-readable issues, if any."""
    issues: list[str] = []

    ruff = resolve_tool("ruff")
    if ruff is None:
        return ["ruff not found — skipped formatting and linting."]

    ret, stdout, stderr = run_command([*ruff, "format", file_path], project_dir)
    if ret != 0:
        issues.append(f"ruff format failed:\n{stderr or stdout}")

    ret, stdout, stderr = run_command([*ruff, "check", "--fix", file_path], project_dir)
    if ret != 0:
        output = stdout or stderr
        if output.strip():
            issues.append(f"ruff check issues:\n{output}")

    ty = resolve_tool("ty")
    if ty is None:
        return issues
    ret, stdout, stderr = run_command([*ty, "check", file_path], project_dir)
    if ret != 0:
        output = stdout or stderr
        if output.strip():
            issues.append(f"ty check issues:\n{output}")

    return issues


def main() -> None:
    payload = read_payload()
    file_path = get_file_path(payload)
    if not file_path or not validate_path(file_path):
        return
    if not is_python_file(file_path) or is_generated(file_path):
        return

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    if not os.path.isfile(file_path):
        return

    if file_path.startswith(project_dir):
        rel_path = os.path.relpath(file_path, project_dir)
    else:
        rel_path = file_path

    issues = check_file(file_path, project_dir)
    if not issues:
        print(f"[lint-on-save] OK: {rel_path}")
        return

    print(f"[lint-on-save] Issues found in {rel_path}:", file=sys.stderr)
    for issue in issues:
        print(issue, file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - a hook must never break the session
        print(f"[lint-on-save] hook error (ignored): {exc}", file=sys.stderr)
    sys.exit(0)
