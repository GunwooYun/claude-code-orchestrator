"""
tools/hook-check: right after an upgrade, every registered hook must run.

The incident behind it: a hook crashed on the system python (`datetime.UTC`
on 3.10) and failed silently 1,933 times, because nothing ran the hooks until
a transcript was read. These tests plant that failure and a registration that
points at a deleted file, and check the tool names both.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
TOOL = REPO / "tools" / "hook-check"

CRASHING_HOOK = (
    "import sys\nsys.stdin.read()\nraise RuntimeError('boom from planted hook')\n"
)


def settings_with(*commands: tuple[str, str, str]) -> str:
    """(event, matcher, command) triples -> a settings.json text."""
    hooks: dict[str, list[dict]] = {}
    for event, matcher, command in commands:
        hooks.setdefault(event, []).append(
            {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}
        )
    return json.dumps({"hooks": hooks})


class HookCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name)
        (self.project / ".claude" / "hooks").mkdir(parents=True)

    def write(self, rel: str, text: str) -> None:
        (self.project / rel).write_text(text, encoding="utf-8")

    def run_tool(self, root: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TOOL), str(root or self.project)],
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_this_repository_s_registered_hooks_all_run(self) -> None:
        settings = json.loads((REPO / ".claude/settings.json").read_text("utf-8"))
        registered = sum(
            len(group["hooks"])
            for groups in settings["hooks"].values()
            for group in groups
        )
        self.assertGreater(registered, 0)
        result = self.run_tool(REPO)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        ok_lines = [x for x in result.stdout.splitlines() if x.startswith("ok   ")]
        self.assertEqual(registered, len(ok_lines), result.stdout)

    def test_a_hook_that_raises_is_named_and_fails_the_run(self) -> None:
        self.write(".claude/hooks/crash.py", CRASHING_HOOK)
        self.write(
            ".claude/settings.json",
            settings_with(
                (
                    "PostToolUse",
                    "Edit|Write",
                    'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/crash.py"',
                )
            ),
        )
        result = self.run_tool()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"FAIL PostToolUse\[Edit\|Write\] .*crash\.py")
        self.assertIn("boom from planted hook", result.stdout)

    def test_a_non_ascii_failure_prints_on_a_narrow_code_page(self) -> None:
        # Korean Windows: cp949 pipes, and tracebacks carry the user's name.
        self.write(
            ".claude/hooks/crash.py",
            # Raw UTF-8 bytes: the hook's own encoding settings must not matter.
            "import sys\nsys.stdin.read()\n"
            "sys.stderr.buffer.write('Traceback (most recent call last):\\n"
            "RuntimeError: 경로 윤건우\\n'.encode('utf-8'))\nsys.exit(1)\n",
        )
        self.write(
            ".claude/settings.json",
            settings_with(
                (
                    "PostToolUse",
                    "Edit|Write",
                    'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/crash.py"',
                )
            ),
        )
        result = subprocess.run(
            [sys.executable, str(TOOL), str(self.project)],
            capture_output=True,
            timeout=120,
            env={**os.environ, "PYTHONIOENCODING": "ascii"},
        )
        self.assertEqual(1, result.returncode, result.stderr.decode("utf-8", "replace"))
        self.assertIn("경로 윤건우", result.stdout.decode("utf-8"))

    def test_a_hook_that_swallows_its_own_error_still_fails_the_run(self) -> None:
        # The template's hooks catch every exception, print this line and exit 0.
        self.write(
            ".claude/hooks/swallow.py",
            "import sys\n"
            "print('[swallow] hook error (ignored): boom', file=sys.stderr)\n",
        )
        self.write(
            ".claude/settings.json",
            settings_with(
                (
                    "PostToolUse",
                    "Edit|Write",
                    'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/swallow.py"',
                )
            ),
        )
        result = self.run_tool()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"FAIL .*swallow\.py.*hook error \(ignored\)")

    def test_a_registration_to_a_missing_file_is_reported_as_missing(self) -> None:
        self.write(
            ".claude/settings.json",
            settings_with(
                (
                    "PreToolUse",
                    "Bash",
                    'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/deleted.py"',
                )
            ),
        )
        result = self.run_tool()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"FAIL .*deleted\.py.*missing")

    def test_stdout_that_is_not_json_fails(self) -> None:
        self.write(".claude/hooks/chatty.py", "import sys\nprint('hello')\n")
        self.write(
            ".claude/settings.json",
            settings_with(
                (
                    "UserPromptSubmit",
                    "",
                    'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/chatty.py"',
                )
            ),
        )
        result = self.run_tool()
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("not JSON", result.stdout)

    def test_no_settings_json_is_a_usage_error(self) -> None:
        result = self.run_tool()
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertTrue(result.stderr.startswith("hook-check: "), result.stderr)

    def test_unreadable_settings_json_is_a_usage_error(self) -> None:
        self.write(".claude/settings.json", "{ not json")
        result = self.run_tool()
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertIn("hook-check: ", result.stderr)

    def test_the_project_is_not_written(self) -> None:
        self.write(
            ".claude/settings.json",
            settings_with(
                (
                    "PostToolUse",
                    "Bash",
                    'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/crash.py"',
                )
            ),
        )
        before = sorted(p.relative_to(self.project) for p in self.project.rglob("*"))
        self.run_tool()
        after = sorted(p.relative_to(self.project) for p in self.project.rglob("*"))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
