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
# agy flags that consume the following token as their value.
VALUE_FLAGS = {
    "--model", "--output-format", "--print-timeout", "--add-dir", "--agent",
    "--json-schema", "--input-format", "--effort", "--mode", "--project",
    "--conversation", "--log-file",
}
# Tokens that may legitimately precede the agy binary in the same command segment.
# Known false negatives (accepted): `bash -c 'agy …'`, `uv run agy …`,
# `timeout -k 5 60 agy …` — the binary is not the segment head there.
WRAPPER_COMMANDS = {"sudo", "nohup", "command", "exec", "env", "time", "do", "then", "else"}
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Markers agy prints on STDERR when a tool was auto-denied in headless mode.
# Matched against stderr only — stdout may legitimately discuss these strings.
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
    """Extract the print-mode prompt from agy argv (flag order agnostic).

    `-p/--print` is a boolean flag and the prompt is positional, so the prompt
    is the first non-flag token after the print flag that is not the value of
    a value-taking flag (e.g. `agy -p --model X "q"` → "q").
    """
    if not any(t in PROMPT_FLAGS or t.split("=", 1)[0] in PROMPT_FLAGS for t in args[1:]):
        return None
    for token in args[1:]:
        for flag in PROMPT_FLAGS:
            if token.startswith(flag + "=") and token[len(flag) + 1:].strip():
                return token[len(flag) + 1:].strip()
    skip_next = False
    for token in args[1:]:
        if skip_next:
            skip_next = False
            continue
        if token in PROMPT_FLAGS:
            continue
        if token in VALUE_FLAGS:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        return token.strip() or None
    return None


def extract_model(args: list[str]) -> str | None:
    """Extract --model value from agy argv (supports --model X and --model=X)."""
    for i, token in enumerate(args):
        if token == "--model" and i + 1 < len(args):
            return args[i + 1]
        if token.startswith("--model="):
            return token[len("--model="):]
    return None


def _parse_result_payload(stdout: str) -> dict | None:
    """Parse agy's JSON envelope; for stream-json use the last non-empty line."""
    candidates = [stdout.strip()]
    lines = [ln for ln in stdout.strip().splitlines() if ln.strip()]
    if lines:
        candidates.append(lines[-1])
    for text in candidates:
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict) and "status" in payload:
            return payload
    return None


def determine_success(stdout: str, stderr: str) -> bool:
    """Best-effort success flag that reflects agy's headless soft-deny."""
    stderr_lower = (stderr or "").lower()
    if any(marker in stderr_lower for marker in SOFT_DENY_MARKERS):
        return False
    payload = _parse_result_payload(stdout or "")
    if payload is not None:
        return payload.get("status") == "SUCCESS" and bool(payload.get("response"))
    return bool((stdout or "").strip())


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
        # Local time with offset so checkpoint day-grouping matches the user's calendar.
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "tool": "antigravity",
        "model": extract_model(args) or "default",
        "prompt": truncate_text(prompt),
        "response": truncate_text(stdout) if stdout else "",
        "success": determine_success(stdout, stderr),
    }


def process_hook_input(hook_input: object) -> dict | None:
    """Validate a PostToolUse payload and build a log entry (None = ignore)."""
    if not isinstance(hook_input, dict):
        return None
    if hook_input.get("tool_name", "") != "Bash":
        return None
    tool_input = hook_input.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command", "")
    if not isinstance(command, str) or not command:
        return None
    tool_response = hook_input.get("tool_response") or {}
    if not isinstance(tool_response, dict):
        tool_response = {"stdout": str(tool_response)}
    return build_entry(command, tool_response)


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    try:
        entry = process_hook_input(hook_input)
        if entry is None:
            return
        log_entry(entry)
    except Exception as exc:  # never break the calling tool because of logging
        print(f"log-cli-tools hook error: {exc}", file=sys.stderr)
        return
    print(json.dumps({"systemMessage": "[LOG] Antigravity call logged to .claude/logs/cli-tools.jsonl"}))


if __name__ == "__main__":
    main()
