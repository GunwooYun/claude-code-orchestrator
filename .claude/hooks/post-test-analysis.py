#!/usr/bin/env python3
"""
PostToolUse hook: suggest deep-reasoning analysis after a test/build failure.

Advisory only — PostToolUse cannot block, so every path exits 0.

Three bugs in the previous version made this hook fire on passing runs:
  1. FAILURE_PATTERNS listed `ERROR`, `Error:`, `error:` and `failed`/`FAILED`
     and matched them case-insensitively, so ONE `error:` line counted three
     times and tripped the `>= 3` threshold on its own.
  2. `pytest -v` prints every test name, so a green run whose test names
     contain "error" also tripped the threshold.
  3. Any output mentioning `ModuleNotFoundError` suppressed the hook entirely,
     hiding genuine multi-failure runs.

The fix: decide whether the command FAILED first (explicit signal from the
payload, then a counted summary line), and only then judge complexity by
counting *distinct kinds* of failure marker rather than raw occurrences.
"""

import json
import re
import sys

# Commands whose output is worth reading at all.
TEST_BUILD_COMMANDS = (
    "pytest",
    "npm test",
    "npm run test",
    "npm run build",
    "ruff check",
    "ty check",
    "mypy",
    "tsc",
    "cargo test",
    "go test",
    "make test",
    "make build",
    "bitbake",
    "oelint-adv",
    # The project's own verification scripts (.claude/scripts/README.md).
    # Listed last because this prefix matches whatever the project put inside.
    ".claude/scripts/verify-",
)

# Counted summaries. These are the most reliable signal a runner gives us.
FAILURE_COUNT_RE = re.compile(
    r"\b(\d+)\s+(?:failed|failures?|errors?)\b", re.IGNORECASE
)
PASSED_COUNT_RE = re.compile(r"\b(\d+)\s+passed\b", re.IGNORECASE)
DIAGNOSTIC_COUNT_RE = re.compile(
    r"\bFound\s+(\d+)\s+(?:error|diagnostic)s?\b", re.IGNORECASE
)

# Unambiguous "this run is fine" statements.
SUCCESS_MARKERS = (
    re.compile(r"\btest result:\s*ok\b"),
    re.compile(r"\bAll checks passed\b"),
    re.compile(r"\bSuccess: no issues found\b"),
    re.compile(r"\bno issues found\b", re.IGNORECASE),
)

# Distinct KINDS of failure marker. The dict key is what gets counted, so a
# marker appearing fifty times still counts once.
STRONG_FAILURE_MARKERS = {
    "traceback": re.compile(r"Traceback \(most recent call last\)"),
    "pytest-failed": re.compile(r"^FAILED\s", re.MULTILINE),
    "pytest-failures-section": re.compile(r"=+\s*FAILURES\s*=+"),
    "assertion": re.compile(r"\bAssertionError\b"),
    "compiler-error": re.compile(r"^error(\[[^\]]+\])?:", re.MULTILINE),
    "go-fail": re.compile(r"^---\s+FAIL:", re.MULTILINE),
    "panic": re.compile(r"^panic:", re.MULTILINE),
    "exception": re.compile(r"^\s*\w*(?:Error|Exception):", re.MULTILINE),
    "bitbake-error": re.compile(r"^ERROR:", re.MULTILINE),
}

# Failures with an obvious mechanical fix. They suppress the suggestion only
# when nothing else in the output suggests a deeper problem.
SIMPLE_FAILURE_MARKERS = (
    "ModuleNotFoundError",
    "command not found",
    "No such file or directory",
    "ENOENT",
)

MIN_DISTINCT_MARKERS = 2
MIN_FAILURE_COUNT = 2


def is_test_or_build_command(command: str) -> bool:
    """Check whether the command runs tests, a build, or a checker."""
    command_lower = command.lower()
    return any(cmd in command_lower for cmd in TEST_BUILD_COMMANDS)


def sum_matches(pattern: re.Pattern[str], output: str) -> int:
    """Total of every number the pattern captures."""
    return sum(int(value) for value in pattern.findall(output))


def explicit_failure(response: object) -> bool | None:
    """
    Read a failure flag straight from the tool response when one is present.

    Returns True/False when the payload says so, None when it does not.
    """
    if not isinstance(response, dict):
        return None
    for key in ("is_error", "isError", "error"):
        value = response.get(key)
        if isinstance(value, bool):
            return value
    for key in ("exit_code", "exitCode", "returncode", "status"):
        value = response.get(key)
        if isinstance(value, int):
            return value != 0
    return None


def looks_failed(output: str, flagged: bool | None) -> bool:
    """Decide whether the command actually failed."""
    if flagged is not None:
        return flagged

    failures = sum_matches(FAILURE_COUNT_RE, output)
    diagnostics = sum_matches(DIAGNOSTIC_COUNT_RE, output)
    if failures or diagnostics:
        return True

    # A counted pass with no counted failure is green, whatever words the test
    # names happen to contain.
    if sum_matches(PASSED_COUNT_RE, output):
        return False
    if any(marker.search(output) for marker in SUCCESS_MARKERS):
        return False

    # No summary at all: fall back to the markers themselves.
    return bool(distinct_marker_kinds(output))


def distinct_marker_kinds(output: str) -> list[str]:
    """Names of the failure-marker kinds present, each counted at most once."""
    return [
        name
        for name, pattern in STRONG_FAILURE_MARKERS.items()
        if pattern.search(output)
    ]


def has_complex_failure(output: str, flagged: bool | None = None) -> tuple[bool, str]:
    """Return (should_suggest, reason) for this command output."""
    if not looks_failed(output, flagged):
        return False, ""

    kinds = distinct_marker_kinds(output)
    failure_count = sum_matches(FAILURE_COUNT_RE, output) or sum_matches(
        DIAGNOSTIC_COUNT_RE, output
    )

    # Only mechanically-fixable markers and nothing else: not worth a subagent.
    if not kinds and any(simple in output for simple in SIMPLE_FAILURE_MARKERS):
        return False, ""

    if "traceback" in kinds:
        return True, "Test failure with traceback"
    if len(kinds) >= MIN_DISTINCT_MARKERS:
        return (
            True,
            f"Failure with {len(kinds)} distinct error kinds ({', '.join(sorted(kinds))})",
        )
    if failure_count >= MIN_FAILURE_COUNT:
        return True, f"{failure_count} failures reported"
    return False, ""


def main() -> None:
    data = json.load(sys.stdin)
    if data.get("tool_name") != "Bash":
        return

    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not is_test_or_build_command(command):
        return

    response = data.get("tool_response", data.get("tool_output", ""))
    if isinstance(response, dict):
        output = f"{response.get('stdout', '')}\n{response.get('stderr', '')}"
    else:
        output = str(response or "")

    should_suggest, reason = has_complex_failure(output, explicit_failure(response))
    if not should_suggest:
        return

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        f"[Debug Suggestion] {reason}. "
                        "Consider consulting the deep-reasoning subagent for debugging "
                        "analysis. **Recommended**: Use Task tool with "
                        "subagent_type='deep-reasoning' with full error context to "
                        "preserve main context. If you are a subagent, report the "
                        "failure back to the orchestrator instead."
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
