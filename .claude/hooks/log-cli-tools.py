#!/usr/bin/env python3
"""
PostToolUse hook: Log Antigravity CLI (agy) input/output to JSONL file.

Triggers after Bash tool calls that actually invoke `agy` in print mode
(`agy -p|--print|--prompt "..."`). Quoted mentions of agy inside other
commands (grep, echo, heredocs) are ignored.
Logs are stored in .claude/logs/cli-tools.jsonl

All agents (Claude Code, subagents, agy) can read this log.
"""

import json
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "cli-tools.jsonl"

PROMPT_FLAGS = {"-p", "--print", "--prompt"}
# Tokens that may legitimately precede the agy binary in the same command segment.
WRAPPER_COMMANDS = {"sudo", "nohup", "command", "exec", "env", "time"}
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Markers agy prints on stderr when a tool was auto-denied in headless mode.
SOFT_DENY_MARKERS = ("auto-denied", "no output produced", "soft-den")


def split_segments(command: str) -> list[list[str]]:
    """Tokenize a shell command and split it into simple-command segments.

    Shell control operators (; & | ( ) ) become segment boundaries; quoted
    strings stay single tokens, so `grep 'agy -p "x"'` never yields a
    segment that starts with agy.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        # Unbalanced quotes (e.g. heredoc bodies) — not a plain agy call.
        return []

    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token and all(ch in ";&|()" for ch in token):
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def find_agy_args(command: str) -> list[str] | None:
    """Return the argv of the first real agy invocation, or None."""
    for segment in split_segments(command):
        tokens = list(segment)
        # Skip env assignments and wrappers such as `timeout 60`.
        while tokens:
            head = tokens[0]
            if ENV_ASSIGNMENT.match(head) or head in WRAPPER_COMMANDS:
                tokens.pop(0)
            elif head == "timeout" and len(tokens) > 1:
                tokens = tokens[2:]
            else:
                break
        if not tokens:
            continue
        if tokens[0] == "agy" or tokens[0].endswith("/agy"):
            return tokens
    return None


def extract_agy_prompt(args: list[str]) -> str | None:
    """Extract the print-mode prompt from agy argv (flag order agnostic)."""
    for i, token in enumerate(args):
        if token in PROMPT_FLAGS and i + 1 < len(args):
            return args[i + 1].strip() or None
        for flag in PROMPT_FLAGS:
            if token.startswith(flag + "="):
                return token[len(flag) + 1:].strip() or None
    return None


def extract_model(args: list[str]) -> str | None:
    """Extract --model value from agy argv (supports --model X and --model=X)."""
    for i, token in enumerate(args):
        if token == "--model" and i + 1 < len(args):
            return args[i + 1]
        if token.startswith("--model="):
            return token[len("--model="):]
    return None


def determine_success(stdout: str, stderr: str) -> bool:
    """Best-effort success flag that reflects agy's headless soft-deny."""
    combined = f"{stdout}\n{stderr}".lower()
    if any(marker in combined for marker in SOFT_DENY_MARKERS):
        return False
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return bool(stdout.strip())
    if isinstance(payload, dict) and "status" in payload:
        return payload.get("status") == "SUCCESS" and bool(payload.get("response"))
    return bool(stdout.strip())


def truncate_text(text: str, max_length: int = 2000) -> str:
    """Truncate text if too long."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + f"... [truncated, {len(text)} total chars]"


def log_entry(entry: dict) -> None:
    """Append entry to JSONL log file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def build_entry(command: str, tool_response: dict) -> dict | None:
    """Build a log entry for an agy command, or None if it is not one."""
    args = find_agy_args(command)
    if args is None:
        return None
    prompt = extract_agy_prompt(args)
    if not prompt:
        return None

    stdout = tool_response.get("stdout", "") or tool_response.get("content", "") or ""
    stderr = tool_response.get("stderr", "") or ""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": "antigravity",
        "model": extract_model(args) or "default",
        "prompt": truncate_text(prompt),
        "response": truncate_text(stdout) if stdout else "",
        "success": determine_success(stdout, stderr),
    }


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    if hook_input.get("tool_name", "") != "Bash":
        return

    command = hook_input.get("tool_input", {}).get("command", "")
    tool_response = hook_input.get("tool_response", {}) or {}
    if not isinstance(tool_response, dict):
        tool_response = {"stdout": str(tool_response)}

    entry = build_entry(command, tool_response)
    if entry is None:
        return

    log_entry(entry)
    print(json.dumps({"systemMessage": "[LOG] Antigravity call logged to .claude/logs/cli-tools.jsonl"}))


if __name__ == "__main__":
    main()
