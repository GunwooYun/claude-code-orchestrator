#!/usr/bin/env python3
"""
PostToolUse hook: Log Antigravity CLI (agy) input/output to JSONL file.

Triggers after Bash tool calls that actually invoke `agy` in print mode
(`agy -p|--print|--prompt "..."`). Quoted mentions of agy inside other
commands (grep, echo, heredocs) are ignored.
Logs are stored in .claude/logs/cli-tools.jsonl

The hook only sees the Bash tool's stdout. Each entry records where agy's
stdout went (`stdout_target`); when it did not reach the Bash tool unaltered
(`> file`, `| jq`, `$(...)`), or another command in the call may have written
beside it (`mixed`: `agy … || echo FETCH FAILED`), `success` is null — unknown
— unless a JSON envelope or a soft-deny notice says how the call ended. A
parser gap is `unclassified`, also unknown. Not supported: `case … esac`,
backticks, and a quoted `"$(agy …)"` (not logged at all).

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
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# shlex's punctuation characters (newline included: it separates commands), and
# how a glued run of them splits back into operators and redirections (longest
# alternatives first).
PUNCTUATION = "();<>|&\n"
PUNCTUATION_SPLIT = re.compile(r"&>>|&>|>>|>&|>\||\|\||&&|\|&|;;|<<|[();<>|&\n]")
CONTROL_OPERATORS = frozenset({";", "&", "|", "||", "&&", "|&", ";;", "(", ")", "\n"})
PIPES = frozenset({"|", "|&"})
LINE_CONTINUATION = re.compile(r"\\\n")
# An unquoted run of digits touching a redirection operator is its fd (`2>err`,
# not `--conversation 42 > f` and not `"2" > f`). shlex drops the spacing that
# tells them apart, so the fd is marked in the raw text first and glued back
# onto its operator (`2>`) by tokenize.
FD_PREFIX = re.compile(r"(?<![^\s;|()])(\d+)(?=>>|>\||>&|>|<)")
FD_MARK = "\x00"
FD_TOKEN = re.compile(r"^\x00(\d+)$")
# A redirection token: optional fd glued on, then the operator.
REDIRECTION = re.compile(r"^(\d*)(&>>|&>|>>|>\||>&|>)$")
# Redirections that send the stream on their left (stdout unless an fd prefix
# says otherwise) somewhere other than the Bash tool's stdout.
OUTPUT_REDIRECTS = frozenset({">", ">>", ">|"})
BOTH_REDIRECTS = frozenset({"&>", "&>>"})
STDOUT_FD = "1"
STDERR_FD = "2"
# Compound commands, recognised at command-start position only. Openers count
# toward depth so a later construct is skipped whole; a closer at depth 0
# closes the construct around agy, and its redirections apply to agy. `for`,
# `while` and `until` open with `do`; `then`/`else`/`elif` neither open nor
# close. `case … esac` is not supported: its `pat)` patterns read as groups.
KEYWORD_OPENERS = frozenset({"if", "do", "{"})
KEYWORD_CLOSERS = frozenset({"fi", "done", "}"})
# Commands that write nothing to stdout in their usual use, so a neighbour that
# runs one does not make agy's stdout `mixed`. Wrong inclusions are unsafe (a
# writer counted as silent); omissions are safe (a silent command reads as
# `mixed`, i.e. unknown). Structural words appear because they head segments.
SILENT_COMMANDS = frozenset(
    {
        "cd", "export", "unset", "set", "true", "false", ":", "mkdir", "rm",
        "cp", "mv", "touch", "sleep", "exit", "return", "shift", "trap",
        "umask", "break", "continue", "[", "test", "for", "select", "case",
        "in", "function", "done", "fi", "esac", "}",
    }
)  # fmt: skip
# stdout_target values (the rest are `file:<path>`, `fd:<n>`, `pipe:<command>`).
DIRECT = "direct"
MIXED = "mixed"
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
    redirections. Quoted strings stay single tokens. An unquoted newline is a
    command separator; a backslash-newline is a continuation; `#` is not
    treated as a comment (shlex would swallow the next line with it), so a
    comment only adds words to its own command. An fd is glued onto its
    operator (`2>`, `1>&`). Known limit: a quoted string made only of
    punctuation (`agy -p ";"`) is read as an operator.
    """
    marked = FD_PREFIX.sub(FD_MARK + r"\1", LINE_CONTINUATION.sub(" ", command))
    lexer = shlex.shlex(marked, posix=True, punctuation_chars=PUNCTUATION)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
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


def find_agy_segment(tokens: list[str]) -> tuple[int, int] | None:
    """[command word, end) of the first real agy invocation, or None."""
    for start, end in segment_bounds(tokens):
        head = command_start(tokens, start, end)
        if head < end and is_agy(tokens[head]):
            return head, end
    return None


def find_agy_args(command: str) -> list[str] | None:
    """Return the argv of the first real agy invocation, or None."""
    tokens = tokenize(command)
    found = find_agy_segment(tokens)
    if found is None:
        return None
    start, end = found
    return tokens[start:end]


def next_operator(tokens: list[str], start: int) -> int:
    """Index of the first control operator at or after `start` (or the end)."""
    for index in range(start, len(tokens)):
        if tokens[index] in CONTROL_OPERATORS:
            return index
    return len(tokens)


def at_command_start(tokens: list[str], index: int) -> bool:
    return index == 0 or tokens[index - 1] in CONTROL_OPERATORS


def compound_close(tokens: list[str], start: int) -> int:
    """Index of the `)` or keyword closer ending the construct `start` is in.

    Any closer reached at depth 0 closes a construct that contains `start`,
    because constructs opened after `start` raise the depth first. Returns
    the end of the tokens when nothing encloses `start`.
    """
    depth = 0
    for index in range(start, len(tokens)):
        token = tokens[index]
        keyword = at_command_start(tokens, index)
        if token == "(" or (keyword and token in KEYWORD_OPENERS):
            depth += 1
        elif token == ")" or (keyword and token in KEYWORD_CLOSERS):
            if depth == 0:
                return index
            depth -= 1
    return len(tokens)


def open_groups(tokens: list[str], end: int) -> list[bool]:
    """Groups open at tokens[end], innermost last: True for `$(`, False for `(`."""
    stack: list[bool] = []
    for index in range(end):
        if tokens[index] == "(":
            stack.append(index > 0 and tokens[index - 1].endswith("$"))
        elif tokens[index] == ")" and stack:
            stack.pop()
    return stack


def redirect_target(tokens: list[str], start: int, end: int) -> str | None:
    """Where the redirections in tokens[start:end] send stdout; None = unchanged.

    Redirections apply left to right, so the last one touching stdout wins
    (`2>&1 >/dev/null` discards stdout). tokenize glues an fd onto its
    operator (`2>`), so a separate digit token is always an argument.
    """
    target: str | None = None
    index = start
    while index < end:
        redirection = REDIRECTION.match(tokens[index])
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


def command_name(word: str) -> str:
    return word.rsplit("/", 1)[-1]


def follow_stdout(tokens: list[str], start: int, end: int) -> tuple[str, set[int]]:
    """Walk agy's stdout from its segment tokens[start:end] to where it ends up.

    Returns the target and the start indices of the pipe consumers walked
    through. Every consumer is followed (its own redirections, the construct
    around it), so `| jq > a.txt` is a file and `$(agy | jq)` a substitution;
    the first non-tee consumer only names the result when the walk ends at the
    Bash tool's stdout.
    """
    groups = open_groups(tokens, start)
    consumer = ""
    visited: set[int] = set()
    while True:
        target = redirect_target(tokens, start, end)
        if target is not None:
            return target, visited
        position = end
        piped = False
        while position < len(tokens):
            operator = tokens[position]
            if operator in PIPES:
                # Hop to the consumer: its redirections and what follows it decide.
                start = position + 1
                end = next_operator(tokens, start)
                visited.add(start)
                head = command_start(tokens, start, end)
                if head < end:
                    name = command_name(tokens[head])
                    if name != "tee" and not consumer:
                        consumer = name
                    start = head
                piped = True
                break
            if operator == ")" or operator in KEYWORD_CLOSERS:
                if operator == ")":
                    if not groups:
                        break  # unbalanced: nothing more is known
                    if groups.pop():
                        return SUBSTITUTION, visited
                # A closed construct: its redirections apply to everything inside.
                after = next_operator(tokens, position + 1)
                target = redirect_target(tokens, position + 1, after)
                if target is not None:
                    return target, visited
                position = after
                continue
            if operator == "(":
                break
            # `;` `&&` `||` `&` newline: this command's stdout is its construct's.
            position = compound_close(tokens, position + 1)
        if not piped:
            break
    return (f"{PIPE_PREFIX}{consumer}" if consumer else DIRECT), visited


def has_other_writer(tokens: list[str], agy_start: int, skipped: set[int]) -> bool:
    """True when another command in the call may write to the same stdout.

    Over-approximates on purpose: a writer inside `$(...)` or a redirected
    group still counts, which only turns `direct` into `mixed` (unknown).
    """
    bounds = segment_bounds(tokens)
    for start, end in bounds:
        if start <= agy_start < end or start in skipped:
            continue
        if end < len(tokens) and tokens[end] in PIPES:
            continue  # a producer feeding a pipe, e.g. `cat f | agy`
        if redirect_target(tokens, start, end) is not None:
            continue
        head = command_start(tokens, start, end)
        if head >= end or command_name(tokens[head]) in SILENT_COMMANDS:
            continue
        return True
    return False


def classify_stdout_target(command: str) -> str:
    """Where the first agy invocation's stdout goes.

    `direct` means it reaches the Bash tool's stdout unaltered and nothing
    else writes there, the only case where that stdout can be read as agy's
    answer. Otherwise: `file:<path>`, `stderr`, `fd:<n>`, `pipe:<command>`,
    `substitution`, or `mixed` (agy's stdout arrives, but another command may
    write beside it — `agy || echo FETCH FAILED`).
    """
    tokens = tokenize(command)
    found = find_agy_segment(tokens)
    if found is None:
        return DIRECT
    start, end = found
    target, visited = follow_stdout(tokens, start, end)
    if target == DIRECT and has_other_writer(tokens, start, visited):
        return MIXED
    return target


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
    """Parse agy's JSON envelope from stdout.

    Tries the whole stdout, then every non-empty line from the last one up: the
    last envelope is the stream-json result, and lines after it (`; echo
    EXIT_CODE=$?`) are not agy's. Trying only the last line judged an ERROR
    envelope by the echo that followed it. An envelope carries both `status`
    and `response`; a `{"status": "ok"}` line inside a plain answer is not one.
    """
    lines = [ln for ln in stdout.strip().splitlines() if ln.strip()]
    candidates = [stdout.strip(), *reversed(lines)]
    for text in candidates:
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict) and "status" in payload and "response" in payload:
            return payload
    return None


def determine_success(
    stdout: str, stderr: str, stdout_is_agys: bool = True
) -> bool | None:
    """Best-effort success flag that reflects agy's headless soft-deny.

    None means unknown: agy's stdout went elsewhere (stdout_is_agys False) and
    neither a soft-deny notice nor a JSON envelope says how the call ended.
    """
    stderr_lower = (stderr or "").lower()
    if any(marker in stderr_lower for marker in SOFT_DENY_MARKERS):
        return False
    payload = _parse_result_payload(stdout or "")
    if payload is not None:
        return payload.get("status") == "SUCCESS" and bool(payload.get("response"))
    if not stdout_is_agys:
        return None
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
    # Kept when agy's output is in stdout, alone (direct), beside other output
    # (mixed, unclassified) or transformed (`| jq -r .response`); a file,
    # stderr or `$(...)` target leaves stdout to whatever ran next. Only
    # `direct` lets non-empty stdout count as success.
    keep_response = target in (DIRECT, MIXED, UNCLASSIFIED) or target.startswith(
        PIPE_PREFIX
    )
    return {
        # Local time with offset so checkpoint day-grouping matches the user's calendar.
        "timestamp": datetime.now(UTC).astimezone().isoformat(),
        "tool": "antigravity",
        "model": extract_model(args) or "default",
        "prompt": truncate_text(prompt),
        "response": truncate_text(stdout) if stdout and keep_response else "",
        "success": determine_success(stdout, stderr, target == DIRECT),
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
