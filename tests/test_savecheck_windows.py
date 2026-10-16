"""
How the save check runs verify-save on Windows (.claude/hooks/_savecheck.py).

Found on a real Windows project (2026-10-15): every save reported
"could not run .claude\\scripts\\verify-save: [WinError 193]" — Windows cannot
exec a shebang script — so the save check never ran there. Windows is not
available here, so the platform and the PATH lookup are injected (they are the
external dependency); the argv the module builds is then really run by /bin/sh.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
MODULE = REPO / ".claude" / "hooks" / "_savecheck.py"

spec = importlib.util.spec_from_file_location("_savecheck", MODULE)
assert spec is not None and spec.loader is not None
savecheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(savecheck)


def which_sh(name: str) -> str | None:
    return "/bin/sh" if name == "sh" else None


def which_nothing(name: str) -> str | None:
    return None


class WindowsSaveCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.scripts = self.root / ".claude" / "scripts"
        self.scripts.mkdir(parents=True)
        self.marker = self.root / "marker.txt"
        os.environ.pop(savecheck.GIT_BASH_ENV, None)

    def script(self, body: str, name: str = "verify-save", mode: int = 0o644) -> Path:
        """A Windows checkout: no execute bit."""
        path = self.scripts / name
        path.write_bytes(body.encode("utf-8"))
        path.chmod(mode)
        return path

    def recording_sh(self) -> Path:
        return self.script(f'#!/bin/sh\nprintf "%s" "$1" > "{self.marker}"\nexit 0\n')

    def test_a_sh_script_runs_through_sh_with_forward_slashes(self) -> None:
        path = self.recording_sh()
        resolved = savecheck.resolve_script(str(self.root), True, which_sh)
        self.assertEqual(
            (["/bin/sh", str(path)], ".claude/scripts/verify-save"), resolved
        )
        assert resolved is not None
        message = savecheck.check(
            resolved[0],
            resolved[1],
            "C:\\proj\\migrations\\m.py",
            str(self.root),
            "lint-on-save",
            windows=True,
        )
        self.assertIsNone(message)
        self.assertEqual("C:/proj/migrations/m.py", self.marker.read_text("utf-8"))

    def test_no_sh_on_path_names_git_bash_and_runs_nothing(self) -> None:
        self.recording_sh()
        resolved = savecheck.resolve_script(str(self.root), True, which_nothing)
        assert resolved is not None
        message = savecheck.check(
            resolved[0],
            resolved[1],
            "C:\\proj\\a.py",
            str(self.root),
            "lint-on-save",
            windows=True,
        )
        assert message is not None
        self.assertIn("could not run", message)
        self.assertIn("Git Bash", message)
        self.assertFalse(self.marker.exists(), "the script must not be exec'd directly")

    def test_git_bash_path_env_wins_over_a_bash_on_path(self) -> None:
        # A bare `bash` on a Windows PATH can be WSL's launcher (review, 2026-10-15).
        path = self.recording_sh()
        os.environ[savecheck.GIT_BASH_ENV] = "/bin/sh"
        self.addCleanup(os.environ.pop, savecheck.GIT_BASH_ENV, None)

        def which_wsl_bash(name: str) -> str | None:
            return "C:/Windows/System32/bash.exe" if name == "bash" else None

        resolved = savecheck.resolve_script(str(self.root), True, which_wsl_bash)
        self.assertEqual(["/bin/sh", str(path)], resolved and resolved[0])

    def test_shebangs_map_to_their_runner(self) -> None:
        cases = {
            b"#!/bin/sh\n": ["/bin/sh"],
            b"#!/bin/sh\r\n": ["/bin/sh"],
            b"#!/usr/bin/env bash\n": ["/bin/sh"],
            b"#!/usr/bin/env python3\n": [sys.executable],
            b"#!/usr/bin/perl\n": None,
            b"echo no shebang\n": None,
        }
        for first, expected in cases.items():
            with self.subTest(first=first):
                path = self.scripts / "probe"
                path.write_bytes(first + b"exit 0\n")
                self.assertEqual(
                    expected, savecheck.shebang_runner(str(path), which_sh)
                )

    def test_an_unrunnable_shebang_falls_through_to_an_extension_form(self) -> None:
        self.script("#!/usr/bin/perl\nexit 0\n")
        py = self.script("import sys\n", name="verify-save.py")
        resolved = savecheck.resolve_script(str(self.root), True, which_sh)
        self.assertEqual([sys.executable, str(py)], resolved and resolved[0])

    def test_posix_still_needs_the_execute_bit_and_keeps_the_path(self) -> None:
        self.recording_sh()
        self.assertIsNone(savecheck.resolve_script(str(self.root), False, which_sh))
        path = self.recording_sh()
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        resolved = savecheck.resolve_script(str(self.root), False, which_sh)
        self.assertEqual([str(path)], resolved and resolved[0])
        assert resolved is not None
        savecheck.check(
            resolved[0], resolved[1], "dir\\name.py", str(self.root), "t", windows=False
        )
        self.assertEqual("dir\\name.py", self.marker.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
