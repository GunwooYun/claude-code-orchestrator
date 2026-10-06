#!/usr/bin/env python3
"""
PostToolUse hook: Log Antigravity CLI (agy) input/output to JSONL file.

Triggers after Bash tool calls that actually invoke `agy` in print mode
(`agy -p|--print|--prompt "..."`). Quoted mentions of agy inside other
commands (grep, echo, heredocs) are ignored.
Logs are stored in .claude/logs/cli-tools.jsonl

The hook only sees the Bash tool's stdout, so it judges a call only when that
stdout can be nothing but agy's: a single-line `agy …` on its own, with at most
`2>file`, `<file` and a final `| tee …` (`direct`). Every other shape is
recorded with `success: null` — unknown — and a blank response, plus a coarse
`stdout_target` (`file:<path>`, `stderr`, `pipe:<cmd>`, `substitution`,
`complex`, `unclassified`). A soft-deny notice on stderr is a failure in any
shape. An allowlist can only err toward unknown; the two rounds that parsed
every shell shape before it kept finding new false successes.

Known limits: a mid-word `#` (`~/c#proj`) is read as a comment and a quoted
punctuation-only argument (`agy -p ";"`) as an operator; `agy -p q # don't`
is unknown (the apostrophe opens a quote in the newline check); `cd x` on one
line and `agy …` on the next is not logged; backticks and a quoted
`"$(agy …)"` are not logged.

All agents (Claude Code, subagents, agy) can read this log.
"""

import json
import re
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "cli-tools.jsonl"

PROMPT_FLAGS = {"-p", "--print", "--prompt"}
# agy flags that consume the following token as their value.
VALUE_FLAGS = {
    "--model",
    "--output-format",
    "--print-timeout",
    "--add-dir",
    "--agent",
    "--json-schema",
    "--input-format",
    "--effort",
    "--mode",
    "--project",
    "--conversation",
    "--log-file",
}
# Tokens that may legitimately precede the agy binary in the same command segment.
# Known false negatives (accepted): `bash -c 'agy …'`, `uv run agy …`,
# `timeout -k 5 60 agy …` — the binary is not the segment head there.
WRAPPER_COMMANDS = {
    "sudo",
    "nohup",
    "command",
    "exec",
    "env",
    "time",
    "do",
    "then",
    "else",
    "elif",
    "if",
    "while",
    "until",
    "{",
    "!",
}
# The wrappers a `direct` call may start with: none of them write to stdout or
# end the call early (`timeout` can leave a partial answer that looks whole).
DIRECT_PREFIX = frozenset({"env", "command", "exec", "time", "!", "sudo", "nohup"})
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# shlex's punctuation characters, and how a glued run of them splits back into
# operators and redirections (longest alternatives first).
PUNCTUATION = "();<>|&"
PUNCTUATION_SPLIT = re.compile(r"&>>|&>|>>|>&|>\||\|\||&&|\|&|;;|<<|[();<>|&]")
CONTROL_OPERATORS = frozenset({";", "&", "|", "||", "&&", "|&", ";;", "(", ")"})
PIPES = frozenset({"|", "|&"})
# A backslash-newline continues the line, unless the backslash is itself escaped.
LINE_CONTINUATION = re.compile(r"(?<!\\)((?:\\\\)*)\\\n")
# Full-line comments and blank lines before the command: nothing precedes them,
# so no quote or heredoc can be open there.
LEADING_COMMENTS = re.compile(r"\A(?:[ \t]*(?:#[^\n]*)?\n)+")
# An unquoted run of digits touching a redirection operator is its fd (`2>err`,
# not `--conversation 42 > f` and not `"2" > f`). shlex drops the spacing that
# tells them apart, so the fd is marked in the raw text first and glued back
# onto its operator (`2>`) by tokenize.
FD_PREFIX = re.compile(r"(?<![^\s;|()])(\d+)(?=>>|>\||>&|>|<)")
FD_MARK = "\x00"
FD_TOKEN = re.compile(r"^\x00(\d+)$")
# Any redirection token, fd glued on or not.
REDIRECTION_TOKEN = re.compile(r"^\d*(&>>|&>|>>|>\||>&|>|<<|<&|<>|<)$")
# The output redirections, split into fd and operator.
OUTPUT_REDIRECTION = re.compile(r"^(\d*)(&>>|&>|>>|>\||>&|>)$")
OUTPUT_REDIRECTS = frozenset({">", ">>", ">|"})
BOTH_REDIRECTS = frozenset({"&>", "&>>"})
STDOUT_FD = "1"
STDERR_FD = "2"
# Redirections a `direct` call may carry: stderr to a file, input from a file.
DIRECT_STDERR_OPS = frozenset({"2>", "2>>"})
DIRECT_INPUT_OP = "<"
# A stderr target that is really stdout (`2>/dev/stdout`, `2>/dev/fd/1`).
DEVICE_PREFIXES = ("/dev/", "/proc/")
DEV_NULL = "/dev/null"
# stdout_target values (the rest are `file:<path>`, `fd:<n>`, `pipe:<command>`).
DIRECT = "direct"
COMPLEX = "complex"
UNCLASSIFIED = "unclassified"
STDERR_TARGET = "stderr"
SUBSTITUTION = "substitution"
PIPE_PREFIX = "pipe:"
# Markers agy prints on STDERR when a tool was auto-denied in headless mode.
# Matched against stderr only — stdout may legitimately discuss these strings.
SOFT_DENY_MARKERS = ("auto-denied", "no output produced", "soft-den")


def tokenize(command: str) -> list[str]:
    """Tokenize a shell command, keeping operators and redirections as tokens.

    shlex glues adjacent punctuation into one token (`);`, `)|`, `2>&1|` gives
    `>&` then `|`), so every all-punctuation token is split into operators and
    redirections. Quoted strings stay single tokens; `#` starts a comment;
    newlines are whitespace (so a heredoc body is never a command of its own).
    An fd is glued onto its operator (`2>`, `2>&`).
    """
    joined = LINE_CONTINUATION.sub(r"\1 ", command)
    lexer = shlex.shlex(
        FD_PREFIX.sub(FD_MARK + r"\1", joined), posix=True, punctuation_chars=True
    )
    lexer.whitespace_split = True
    try:
        raw = list(lexer)
    except ValueError:
        # Unbalanced quotes (e.g. heredoc bodies) — not a plain agy call.
        return []
    tokens: list[str] = []
    pending_fd = ""
    for token in raw:
        fd = FD_TOKEN.match(token)
        if fd:
            pending_fd = fd.group(1)
            continue
        if token and all(ch in PUNCTUATION for ch in token):
            parts = PUNCTUATION_SPLIT.findall(token)
        else:
            # The marker only belongs on a bare fd; inside a word it is noise.
            parts = [token.replace(FD_MARK, "")]
        if pending_fd and parts:
            parts[0] = pending_fd + parts[0]
            pending_fd = ""
        tokens.extend(parts)
    return tokens


def segment_bounds(tokens: list[str]) -> list[tuple[int, int]]:
    """Return [start, end) index pairs of the simple commands in `tokens`."""
    bounds: list[tuple[int, int]] = []
    start = 0
    for index, token in enumerate(tokens):
        if token in CONTROL_OPERATORS:
            if index > start:
                bounds.append((start, index))
            start = index + 1
    if len(tokens) > start:
        bounds.append((start, len(tokens)))
    return bounds


def split_segments(command: str) -> list[list[str]]:
    """Tokenize a shell command and split it into simple-command segments.

    Shell control operators (; & | ( ) and their doubled forms) become segment
    boundaries; redirections stay inside their segment; quoted strings stay
    single tokens, so `grep 'agy -p "x"'` never yields a segment that starts
    with agy.
    """
    tokens = tokenize(command)
    return [tokens[start:end] for start, end in segment_bounds(tokens)]


def command_start(tokens: list[str], start: int, end: int) -> int:
    """Index of the command word in tokens[start:end], past env and wrappers."""
    index = start
    while index < end:
        head = tokens[index]
        if ENV_ASSIGNMENT.match(head) or head in WRAPPER_COMMANDS:
            index += 1
        elif head == "timeout" and end - index > 1:
            index += 2
        else:
            break
    return index


def is_agy(word: str) -> bool:
    return word == "agy" or word.endswith("/agy")


def find_agy_segment(tokens: list[str]) -> tuple[int, int, int] | None:
    """(segment start, command word, end) of the first real agy invocation."""
    for start, end in segment_bounds(tokens):
        head = command_start(tokens, start, end)
        if head < end and is_agy(tokens[head]):
            return start, head, end
    return None


def find_agy_args(command: str) -> list[str] | None:
    """Return the argv of the first real agy invocation, or None."""
    tokens = tokenize(command)
    found = find_agy_segment(tokens)
    if found is None:
        return None
    _, head, end = found
    return tokens[head:end]


def next_operator(tokens: list[str], start: int) -> int:
    """Index of the first control operator at or after `start` (or the end)."""
    for index in range(start, len(tokens)):
        if tokens[index] in CONTROL_OPERATORS:
            return index
    return len(tokens)


def inside_substitution(tokens: list[str], end: int) -> bool:
    """True when tokens[end] sits inside an open `$(`."""
    stack: list[bool] = []
    for index in range(end):
        if tokens[index] == "(":
            stack.append(index > 0 and tokens[index - 1].endswith("$"))
        elif tokens[index] == ")" and stack:
            stack.pop()
    return any(stack)


def redirect_target(tokens: list[str], start: int, end: int) -> str | None:
    """Where the redirections in tokens[start:end] send stdout; None = unchanged.

    Only labels a call that is already not `direct`, for a person reading the
    log. The last redirection touching stdout wins.
    """
    target: str | None = None
    index = start
    while index < end:
        redirection = OUTPUT_REDIRECTION.match(tokens[index])
        if not redirection:
            index += 1
            continue
        fd = redirection.group(1) or STDOUT_FD
        token = redirection.group(2)
        operand = tokens[index + 1] if index + 1 < end else ""
        if token in BOTH_REDIRECTS:
            target = f"file:{operand}"
        elif fd != STDOUT_FD:
            pass  # another fd (usually stderr) moves; stdout stays where it was
        elif token in OUTPUT_REDIRECTS:
            target = f"file:{operand}"
        elif operand == STDERR_FD:
            target = STDERR_TARGET
        elif operand.isdigit():
            target = None if operand == STDOUT_FD else f"fd:{operand}"
        else:
            target = f"file:{operand}"  # `>& file` is `&> file`
        index += 2
    return target


def has_unquoted_newline(command: str) -> bool:
    """True when the command has more than one line outside quotes.

    A separate pass, because tokenize treats newlines as whitespace (that is
    what keeps heredoc bodies from becoming commands). Comments are NOT
    stripped here: `agy -p q # note` + newline + `echo hi` must still show the
    newline. A quote this pass cannot close (`# don't`) counts as a newline —
    the call is then unknown, never wrongly direct.
    """
    text = LEADING_COMMENTS.sub("", LINE_CONTINUATION.sub(r"\1 ", command)).strip()
    lexer = shlex.shlex(text, posix=True, punctuation_chars="\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return any(token and set(token) == {"\n"} for token in lexer)
    except ValueError:
        return True


def allowed_redirections(tokens: list[str], start: int, end: int) -> bool:
    """True when agy's own redirections are only `2>file`, `2>>file`, `<file`."""
    index = start
    while index < end:
        token = tokens[index]
        if not REDIRECTION_TOKEN.match(token):
            index += 1
            continue
        operand = tokens[index + 1] if index + 1 < end else ""
        if not operand or REDIRECTION_TOKEN.match(operand):
            return False
        if token in DIRECT_STDERR_OPS:
            if operand.startswith(DEVICE_PREFIXES) and operand != DEV_NULL:
                return False  # `2>/dev/stdout` merges stderr into stdout
        elif token != DIRECT_INPUT_OP:
            return False
        index += 2
    return True


def is_direct(command: str, tokens: list[str], found: tuple[int, int, int]) -> bool:
    """True only for the one shape whose stdout can be nothing but agy's."""
    segment, head, end = found
    if segment != 0 or has_unquoted_newline(command):
        return False
    for word in tokens[segment:head]:
        if not (ENV_ASSIGNMENT.match(word) or word in DIRECT_PREFIX):
            return False
    if not allowed_redirections(tokens, head, end):
        return False
    if end == len(tokens):
        return True
    # The only follow-on allowed: `| tee [args]` as the last command, unredirected.
    tee_start = end + 1
    if tokens[end] != "|" or tee_start >= len(tokens):
        return False
    if next_operator(tokens, tee_start) != len(tokens):
        return False
    if command_name(tokens[tee_start]) != "tee":
        return False
    return not any(REDIRECTION_TOKEN.match(token) for token in tokens[tee_start:])


def command_name(word: str) -> str:
    return word.rsplit("/", 1)[-1]


def classify_stdout_target(command: str) -> str:
    """`direct` for the allowlisted shape; otherwise a coarse label."""
    tokens = tokenize(command)
    found = find_agy_segment(tokens)
    if found is None:
        return COMPLEX
    _, head, end = found
    target = redirect_target(tokens, head, end)
    if target is not None:
        return target
    if inside_substitution(tokens, head):
        return SUBSTITUTION
    if end < len(tokens) and tokens[end] in PIPES:
        consumer = end + 1
        consumer_end = next_operator(tokens, consumer)
        word = command_start(tokens, consumer, consumer_end)
        name = command_name(tokens[word]) if word < consumer_end else ""
        if name != "tee":
            return f"{PIPE_PREFIX}{name}"
    if is_direct(command, tokens, found):
        return DIRECT
    return COMPLEX


def stdout_target(command: str) -> str:
    """classify_stdout_target, failing closed to `unclassified` on a parser gap."""
    try:
        return classify_stdout_target(command)
    except Exception:  # noqa: BLE001 - a parser gap must not drop the log entry
        return UNCLASSIFIED


def extract_agy_prompt(args: list[str]) -> str | None:
    """Extract the print-mode prompt from agy argv (flag order agnostic).

    `-p/--print` is a boolean flag and the prompt is positional, so the prompt
    is the first non-flag token after the print flag that is not the value of
    a value-taking flag (e.g. `agy -p --model X "q"` → "q").
    """
    if not any(
        t in PROMPT_FLAGS or t.split("=", 1)[0] in PROMPT_FLAGS for t in args[1:]
    ):
        return None
    for token in args[1:]:
        for flag in PROMPT_FLAGS:
            if token.startswith(flag + "=") and token[len(flag) + 1 :].strip():
                return token[len(flag) + 1 :].strip()
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
            return token[len("--model=") :]
    return None


def _parse_result_payload(stdout: str) -> dict | None:
    """Parse agy's JSON envelope; for stream-json use the last non-empty line.

    Only called for `direct` calls, whose stdout is agy's alone, so nothing can
    follow the envelope.
    """
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


def soft_denied(stderr: str) -> bool:
    stderr_lower = (stderr or "").lower()
    return any(marker in stderr_lower for marker in SOFT_DENY_MARKERS)


def determine_success(stdout: str, stderr: str) -> bool:
    """Best-effort success flag for a `direct` call, reflecting soft-deny."""
    if soft_denied(stderr):
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
    target = stdout_target(command)
    if target == DIRECT:
        response = truncate_text(stdout) if stdout else ""
        success: bool | None = determine_success(stdout, stderr)
    else:
        # stdout may be anyone's: no answer, no verdict — except a soft-deny,
        # which is a failure wherever stdout went.
        response = ""
        success = False if soft_denied(stderr) else None
    return {
        # Local time with offset so checkpoint day-grouping matches the user's calendar.
        "timestamp": datetime.now(UTC).astimezone().isoformat(),
        "tool": "antigravity",
        "model": extract_model(args) or "default",
        "prompt": truncate_text(prompt),
        "response": response,
        "success": success,
        "stdout_target": target,
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
    print(
        json.dumps(
            {
                "systemMessage": "[LOG] Antigravity call logged to .claude/logs/cli-tools.jsonl"
            }
        )
    )


if __name__ == "__main__":
    main()
