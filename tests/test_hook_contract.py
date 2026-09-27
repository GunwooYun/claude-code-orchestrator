"""
Contract tests every hook in .claude/hooks/ must satisfy.

The contract exists because `lint-on-save.py` was a permanent no-op: it read a
`CLAUDE_TOOL_INPUT` environment variable that Claude Code never sets, so it
produced nothing and exited 0 — indistinguishable from "nothing to report".
These tests feed each hook the real payload shape and assert the three
properties the harness relies on:

  1. exit 0 always (a non-zero PostToolUse/PreToolUse exit disrupts the session)
  2. stdout is empty or a single valid JSON object
  3. when stdout carries JSON, `hookSpecificOutput.hookEventName` is present

Plus a regression test per hook for the specific bug that motivated it.

**These tests cannot detect a dead hook.** Empty stdout is a legal answer here —
it is what a hook with nothing to report prints — so a hook that reads its
payload and returns immediately satisfies every assertion in this file.
Measured: inserting `sys.exit(0)` after `json.load(sys.stdin)` in any of the
eight hooks leaves all 13 of these tests green. `tests/test_hook_effects.py`
covers that: it asserts an observable effect on a payload that should trigger
each hook, and silence on one that should not. Add a case there, not here, when
a hook gains behaviour.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).parent.parent / ".claude" / "hooks"
SETTINGS = Path(__file__).parent.parent / ".claude" / "settings.json"

# A payload per hook event, shaped the way Claude Code sends it.
PAYLOADS: dict[str, dict] = {
    "UserPromptSubmit": {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "test-session",
        "prompt": "Refactor the retry logic and explain the tradeoffs",
    },
    "PreToolUse-Edit": {
        "hook_event_name": "PreToolUse",
        "session_id": "test-session",
        "tool_name": "Edit",
        "tool_input": {"file_path": "/tmp/example.py", "new_string": "x = 1\n"},
    },
    "PreToolUse-WebSearch": {
        "hook_event_name": "PreToolUse",
        "session_id": "test-session",
        "tool_name": "WebSearch",
        "tool_input": {"query": "httpx vs aiohttp benchmarks"},
    },
    "PostToolUse-Bash": {
        "hook_event_name": "PostToolUse",
        "session_id": "test-session",
        "tool_name": "Bash",
        "tool_input": {"command": "uv run pytest -q"},
        "tool_response": {"stdout": "41 passed in 0.05s\n", "stderr": ""},
    },
    "PostToolUse-Edit": {
        "hook_event_name": "PostToolUse",
        "session_id": "test-session",
        "tool_name": "Edit",
        "tool_input": {"file_path": "/tmp/example.py"},
        "tool_response": {"filePath": "/tmp/example.py"},
    },
    "PostToolUse-Task": {
        "hook_event_name": "PostToolUse",
        "session_id": "test-session",
        "tool_name": "Task",
        "tool_input": {"subagent_type": "general-purpose", "prompt": "Plan the work"},
        "tool_response": {"content": "done"},
    },
}

# Which payloads each hook must tolerate. Every hook must survive every payload
# it can plausibly receive, plus the degenerate inputs below.
HOOK_PAYLOADS: dict[str, tuple[str, ...]] = {
    "agent-router.py": ("UserPromptSubmit",),
    "suggest-deep-reasoning-before-write.py": ("PreToolUse-Edit",),
    "suggest-antigravity-research.py": ("PreToolUse-WebSearch",),
    "suggest-deep-reasoning-after-plan.py": ("PostToolUse-Task",),
    "post-test-analysis.py": ("PostToolUse-Bash",),
    "log-cli-tools.py": ("PostToolUse-Bash",),
    "lint-on-save.py": ("PostToolUse-Edit",),
    "post-implementation-review.py": ("PostToolUse-Edit",),
}

DEGENERATE_INPUTS = ("", "not json at all", "[]", "null", "{}")


def hook_files() -> list[Path]:
    return sorted(p for p in HOOKS_DIR.glob("*.py") if not p.name.startswith("_"))


def run_hook(path: Path, payload: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(HOOKS_DIR.parent.parent),
    )


class HookInventoryTests(unittest.TestCase):
    def test_every_hook_on_disk_is_registered_in_settings(self) -> None:
        registered = SETTINGS.read_text(encoding="utf-8")
        for path in hook_files():
            self.assertIn(
                path.name,
                registered,
                f"{path.name} exists but is not registered in .claude/settings.json",
            )

    def test_every_hook_referenced_by_settings_exists(self) -> None:
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        names = {p.name for p in hook_files()}
        referenced = set()
        for handlers in settings.get("hooks", {}).values():
            for group in handlers:
                for handler in group.get("hooks", []):
                    command = handler.get("command", "")
                    for name in names | {"MISSING"}:
                        if name != "MISSING" and name in command:
                            referenced.add(name)
                    if ".claude/hooks/" in command:
                        stem = (
                            command.split(".claude/hooks/")[1].split()[0].strip("\"'")
                        )
                        self.assertIn(
                            stem,
                            names,
                            f"settings.json registers {stem}, which is not on disk",
                        )
        self.assertTrue(referenced, "no hooks matched settings.json commands")

    def test_every_hook_reads_stdin(self) -> None:
        """A hook that never reads stdin cannot see its payload (the lint-on-save bug)."""
        for path in hook_files():
            source = path.read_text(encoding="utf-8")
            self.assertIn(
                "sys.stdin",
                source,
                f"{path.name} does not read sys.stdin, so it can never see its payload",
            )

    def test_no_hook_reads_a_claude_tool_input_env_var(self) -> None:
        """
        No such variable is set; reading one is how lint-on-save silently died.

        Matches `os.environ` specifically rather than the substring "environ",
        which also occurs inside the word "environment" — so a docstring
        explaining the bug does not trip the test.
        """
        for path in hook_files():
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if "CLAUDE_TOOL_INPUT" in line and "os.environ" in line:
                    self.fail(
                        f"{path.name}:{lineno} reads CLAUDE_TOOL_INPUT from the "
                        "environment, which Claude Code does not set"
                    )


class HookContractTests(unittest.TestCase):
    def assert_contract(self, path: Path, payload: str) -> None:
        result = run_hook(path, payload)
        self.assertEqual(
            0,
            result.returncode,
            f"{path.name} exited {result.returncode}\nstderr: {result.stderr}",
        )
        stdout = result.stdout.strip()
        if not stdout:
            return
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"{path.name} printed non-JSON to stdout: {exc}\n{stdout[:400]}")
        self.assertIsInstance(
            parsed, dict, f"{path.name} printed JSON that is not an object"
        )
        if "hookSpecificOutput" in parsed:
            self.assertIn(
                "hookEventName",
                parsed["hookSpecificOutput"],
                f"{path.name} omitted hookEventName",
            )

    def test_hooks_honour_contract_on_their_payloads(self) -> None:
        for path in hook_files():
            for key in HOOK_PAYLOADS.get(path.name, ()):
                with self.subTest(hook=path.name, payload=key):
                    self.assert_contract(path, json.dumps(PAYLOADS[key]))

    def test_hooks_honour_contract_on_every_payload_shape(self) -> None:
        """A hook may be registered for more events later; none may crash."""
        for path in hook_files():
            for key, payload in PAYLOADS.items():
                with self.subTest(hook=path.name, payload=key):
                    self.assert_contract(path, json.dumps(payload))

    def test_hooks_survive_degenerate_input(self) -> None:
        for path in hook_files():
            for payload in DEGENERATE_INPUTS:
                with self.subTest(hook=path.name, payload=payload or "<empty>"):
                    self.assert_contract(path, payload)


class PostTestAnalysisRegressionTests(unittest.TestCase):
    """The false-positive bugs: overlapping patterns and green-run detection."""

    def setUp(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "post_test_analysis", HOOKS_DIR / "post-test-analysis.py"
        )
        assert spec and spec.loader
        self.hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.hook)

    def test_single_error_line_does_not_trip_the_threshold(self) -> None:
        suggested, _ = self.hook.has_complex_failure("error: unexpected token\n")
        self.assertFalse(suggested, "one error line must not count as several failures")

    def test_green_pytest_verbose_run_is_not_a_failure(self) -> None:
        output = (
            "tests/test_a.py::test_error_message_is_clear PASSED\n"
            "tests/test_a.py::test_error_code_mapping PASSED\n"
            "tests/test_a.py::test_raises_value_error PASSED\n"
            "============================== 3 passed in 0.05s ===============================\n"
        )
        suggested, reason = self.hook.has_complex_failure(output)
        self.assertFalse(suggested, f"green run flagged as failure: {reason}")

    def test_module_not_found_does_not_suppress_a_real_failure(self) -> None:
        output = (
            "ModuleNotFoundError: No module named 'foo'\n"
            "Traceback (most recent call last):\n"
            "  File 'a.py', line 2, in <module>\n"
            "AssertionError: expected 3, got 4\n"
            "2 failed, 1 passed\n"
        )
        suggested, _ = self.hook.has_complex_failure(output)
        self.assertTrue(
            suggested, "a traceback must not be suppressed by a simple error"
        )

    def test_bare_module_not_found_is_left_alone(self) -> None:
        suggested, _ = self.hook.has_complex_failure(
            "ModuleNotFoundError: No module named 'foo'\n"
        )
        self.assertFalse(suggested, "a mechanical fix needs no deep reasoning")

    def test_real_multi_failure_run_is_flagged(self) -> None:
        output = (
            "=================================== FAILURES ===================================\n"
            "FAILED tests/test_a.py::test_one - AssertionError\n"
            "FAILED tests/test_b.py::test_two - ValueError\n"
            "2 failed, 39 passed in 1.20s\n"
        )
        suggested, _ = self.hook.has_complex_failure(output)
        self.assertTrue(suggested)

    def test_explicit_success_flag_wins_over_scary_words(self) -> None:
        suggested, _ = self.hook.has_complex_failure(
            "error: something\nTraceback (most recent call last):\n", flagged=False
        )
        self.assertFalse(suggested, "an explicit success flag must be honoured")


if __name__ == "__main__":
    unittest.main()
