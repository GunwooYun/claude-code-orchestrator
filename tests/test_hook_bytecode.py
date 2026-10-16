"""
The save-check hooks leave no bytecode in the project.

Seen on a Windows check (2026-10-15): after a hook ran, the untracked
`.claude/hooks/__pycache__/_savecheck.cpython-313.pyc` made /isolated-review
refuse the working tree as dirty in a project whose .gitignore lacks it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
HOOKS = ("lint-on-save.py", "bash-write-check.py")


class HookBytecodeTests(unittest.TestCase):
    def test_running_a_hook_writes_no_pycache(self) -> None:
        for hook in HOOKS:
            with self.subTest(hook=hook), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                hooks = root / ".claude" / "hooks"
                hooks.mkdir(parents=True)
                for name in (hook, "_savecheck.py"):
                    shutil.copy2(REPO / ".claude/hooks" / name, hooks)
                target = root / "a.py"
                target.write_text("x = 1\n", encoding="utf-8")
                payload = {
                    "session_id": "bytecode",
                    "tool_name": "Edit",
                    "tool_input": {"file_path": str(target)},
                }
                env = {
                    k: v
                    for k, v in os.environ.items()
                    if k != "PYTHONDONTWRITEBYTECODE"
                }
                subprocess.run(
                    [sys.executable, str(hooks / hook)],
                    input=json.dumps(payload),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(root),
                    env={**env, "CLAUDE_PROJECT_DIR": str(root)},
                )
                self.assertFalse((hooks / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
