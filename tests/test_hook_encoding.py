"""
The save-check hooks on a non-UTF-8 locale with a non-ASCII project path.

Found on Windows (2026-10-16) under C:\\Users\\YunGunwoo윤건우: the hooks read
Claude Code's UTF-8 payload through the cp949 text stream, so the path came out
garbled and lint-on-save returned silently; and the save check's UTF-8 output
was decoded with cp949, so the report to Claude read "None". Reproduced here
by forcing the same encodings: PYTHONIOENCODING=cp949 for stdin and an EUC-KR
locale for subprocess decoding.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
HOOKS = REPO / ".claude" / "hooks"
KOREAN_ENV = {"PYTHONIOENCODING": "cp949", "LC_ALL": "ko_KR.eucKR", "PYTHONUTF8": "0"}


class HookEncodingTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name) / "윤건우" / "proj"
        hooks = self.project / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        for name in ("lint-on-save.py", "bash-write-check.py", "_savecheck.py"):
            shutil.copy2(HOOKS / name, hooks)
        script = self.project / ".claude" / "scripts" / "verify-save"
        script.parent.mkdir(parents=True)
        script.write_text('#!/bin/sh\necho "SAVE-RAN $1"\nexit 1\n', encoding="utf-8")
        script.chmod(0o755)

    def hook(self, name: str, payload: dict) -> str:
        done = subprocess.run(
            [sys.executable, str(self.project / ".claude/hooks" / name)],
            input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            capture_output=True,
            timeout=60,
            cwd=str(self.project),
            env={**os.environ, **KOREAN_ENV, "CLAUDE_PROJECT_DIR": str(self.project)},
        )
        self.assertEqual(0, done.returncode, done.stderr.decode("utf-8", "replace"))
        out = done.stdout.decode("utf-8").strip()
        if not out:
            return ""
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]

    def test_lint_on_save_reports_the_check_for_a_korean_path(self) -> None:
        target = self.project / "t.py"
        target.write_text("x = 1\n", encoding="utf-8")
        context = self.hook(
            "lint-on-save.py",
            {
                "session_id": "enc",
                "tool_name": "Edit",
                "tool_input": {"file_path": str(target)},
            },
        )
        self.assertIn(f"SAVE-RAN {target}", context)
        self.assertNotIn("None", context)

    def test_bash_write_check_reports_the_check_for_a_korean_path(self) -> None:
        base = {
            "session_id": "enc",
            "cwd": str(self.project),
            "tool_use_id": "toolu_enc",
            "tool_name": "Bash",
            "tool_input": {"command": "printf 'y = 2\\n' > u.py"},
        }
        self.hook("bash-write-check.py", {**base, "hook_event_name": "PreToolUse"})
        time.sleep(0.05)
        (self.project / "u.py").write_text("y = 2\n", encoding="utf-8")
        context = self.hook(
            "bash-write-check.py",
            {**base, "hook_event_name": "PostToolUse", "tool_response": {"stdout": ""}},
        )
        self.assertIn("SAVE-RAN", context)
        self.assertIn("u.py", context)
        self.assertNotIn("None", context)


if __name__ == "__main__":
    unittest.main()
