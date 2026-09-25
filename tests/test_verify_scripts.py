"""
Tests for the verification-script contract (.claude/scripts/README.md).

**This file is meant to be copied into any project that adopts the contract.**
So it assumes nothing about language or toolchain:

  - it never runs the project's real scripts against the project's real files
  - it never invokes a tier that could be slow (task/unit/full may take minutes
    to hours, and in this template they run the test suite, which would recurse)
  - it never mutates the working tree
  - it drives the caller (the hook) against STUB scripts it creates itself, so
    the assertions are about the contract rather than about any tool

What it cannot check is whether a project's real implementation is correct. That
belongs in a project-specific test, or in running the scripts by hand as
/initproject Step 5 instructs.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
SCRIPTS = REPO / ".claude" / "scripts"
HOOK = REPO / ".claude" / "hooks" / "lint-on-save.py"
TIERS = ("save", "task", "unit", "full")

# The caller resolves an extensionless executable first, then these forms, which
# need neither an execute bit nor a shebang (Windows checkouts have neither).
SUFFIXES = ("", ".py", ".sh", ".ps1", ".cmd", ".bat")


def entrypoints() -> dict[str, Path]:
    """Tier -> script path, for whichever tiers this project configured."""
    found: dict[str, Path] = {}
    for tier in TIERS:
        for suffix in SUFFIXES:
            candidate = SCRIPTS / f"verify-{tier}{suffix}"
            if candidate.is_file():
                found[tier] = candidate
                break
    return found


class ContractDocumentationTests(unittest.TestCase):
    def test_the_contract_is_written_down(self) -> None:
        readme = SCRIPTS / "README.md"
        self.assertTrue(readme.is_file(), "the contract must be written down")
        text = readme.read_text(encoding="utf-8")
        for tier in TIERS:
            self.assertIn(f"verify-{tier}", text, f"README omits verify-{tier}")

    def test_tier_names_agree_with_the_testing_rules(self) -> None:
        """
        Script names and tier names must not drift apart. Skipped when the
        project does not keep this template's rules file.
        """
        rules = REPO / ".claude" / "rules" / "testing.md"
        if not rules.is_file():
            self.skipTest("no .claude/rules/testing.md in this project")
        text = rules.read_text(encoding="utf-8")
        for tier in TIERS:
            self.assertIn(
                f"`{tier}`", text, f"testing.md does not define the {tier} tier"
            )


class DirectoryShapeTests(unittest.TestCase):
    def test_at_least_one_tier_is_configured(self) -> None:
        self.assertTrue(
            entrypoints(),
            "no verify-* script exists; nothing can verify anything in this project",
        )

    def test_extensionless_entrypoints_are_executable_with_a_shebang(self) -> None:
        for tier, path in entrypoints().items():
            if path.suffix:
                continue  # run through an interpreter; needs neither
            with self.subTest(tier=tier):
                self.assertTrue(
                    os.access(path, os.X_OK), f"{path.name} is not executable"
                )
                first = path.read_text(encoding="utf-8").splitlines()[0]
                self.assertTrue(first.startswith("#!"), f"{path.name} has no shebang")

    def test_only_entrypoints_and_helpers_live_here(self) -> None:
        """A stray file here is read as a fifth entrypoint that nobody calls."""
        for entry in sorted(SCRIPTS.iterdir()):
            if entry.is_dir():
                self.assertEqual("lib", entry.name)
                continue
            name = entry.name
            self.assertTrue(
                name == "README.md" or name.startswith(("verify-", "_")),
                f"{name}: entrypoints are verify-*, shared helpers start with _",
            )


class StubProject:
    """A throwaway project with a scripted verify-save, for driving the caller."""

    def __init__(self, tmp: str, body: str) -> None:
        self.root = Path(tmp)
        scripts = self.root / ".claude" / "scripts"
        scripts.mkdir(parents=True)
        self.marker = self.root / "marker.txt"
        self.script = scripts / "verify-save"
        self.script.write_text(body.format(marker=self.marker), encoding="utf-8")
        self.script.chmod(self.script.stat().st_mode | stat.S_IEXEC)
        self.target = self.root / "probe.txt"
        self.target.write_text("content\n", encoding="utf-8")

    def run_hook(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(
                {"tool_name": "Edit", "tool_input": {"file_path": str(self.target)}}
            ),
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(self.root),
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)},
        )


class CallerContractTests(unittest.TestCase):
    """
    How the caller must treat each contract outcome.

    Driven with stubs, so these hold for any project's real implementation.
    """

    def stub(self, body: str) -> StubProject:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return StubProject(tmp.name, body)

    def test_the_script_receives_the_edited_path(self) -> None:
        project = self.stub('#!/bin/sh\nprintf "%s" "$1" > "{marker}"\nexit 0\n')
        result = project.run_hook()
        self.assertEqual(0, result.returncode)
        self.assertTrue(
            project.marker.is_file(),
            "the script was never invoked — the caller is a no-op",
        )
        self.assertEqual(
            str(project.target), project.marker.read_text(encoding="utf-8")
        )

    def test_silent_success_is_reported_silently(self) -> None:
        project = self.stub("#!/bin/sh\nexit 0\n")
        result = project.run_hook()
        self.assertEqual("", (result.stdout + result.stderr).strip())

    def test_output_on_success_is_passed_through(self) -> None:
        """
        Tools that warn but succeed are common. Discarding their output is how a
        warning becomes a false "clean".
        """
        project = self.stub('#!/bin/sh\necho "deprecated API in use"\nexit 0\n')
        result = project.run_hook()
        self.assertEqual(0, result.returncode)
        self.assertIn("deprecated API in use", result.stdout + result.stderr)

    def test_failure_output_is_surfaced(self) -> None:
        project = self.stub('#!/bin/sh\necho "the reason" >&2\nexit 1\n')
        result = project.run_hook()
        self.assertEqual(0, result.returncode, "the caller must never block")
        self.assertIn("the reason", result.stdout + result.stderr)

    def test_silent_failure_is_still_visible(self) -> None:
        project = self.stub("#!/bin/sh\nexit 3\n")
        result = project.run_hook()
        combined = result.stdout + result.stderr
        self.assertIn("probe.txt", combined)
        self.assertIn("3", combined)

    def test_a_missing_file_does_not_reach_the_script(self) -> None:
        project = self.stub('#!/bin/sh\nprintf "%s" "$1" > "{marker}"\nexit 0\n')
        project.target.unlink()
        result = project.run_hook()
        self.assertEqual(0, result.returncode)
        self.assertFalse(project.marker.is_file())

    def test_an_absent_script_is_reported_not_treated_as_a_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude" / "scripts").mkdir(parents=True)
            target = root / "probe.txt"
            target.write_text("x\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps(
                    {"tool_name": "Edit", "tool_input": {"file_path": str(target)}}
                ),
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(root),
                env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)},
            )
            self.assertEqual(0, result.returncode)
            self.assertIn("verify-save", result.stdout + result.stderr)

    def test_a_script_needing_an_interpreter_is_still_found(self) -> None:
        """
        A Windows checkout has no execute bit and no shebang, so the caller must
        resolve verify-save.py and run it through an interpreter.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / ".claude" / "scripts"
            scripts.mkdir(parents=True)
            marker = root / "marker.txt"
            script = scripts / "verify-save.py"
            script.write_text(
                "import sys, pathlib\n"
                f"pathlib.Path({str(marker)!r}).write_text(sys.argv[1])\n",
                encoding="utf-8",
            )
            script.chmod(0o644)  # deliberately not executable
            target = root / "probe.txt"
            target.write_text("x\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps(
                    {"tool_name": "Edit", "tool_input": {"file_path": str(target)}}
                ),
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(root),
                env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)},
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(
                marker.is_file(),
                "a non-executable verify-save.py was not resolved — Windows is excluded",
            )


class SaveTierContractTests(unittest.TestCase):
    """
    The project's real verify-save, on inputs that need no toolchain.

    Only paths it must ignore are used, so nothing runs and nothing is mutated.
    """

    def setUp(self) -> None:
        self.script = entrypoints().get("save")
        if self.script is None:
            self.skipTest("no save tier configured")

    def run_save(self, *args: str) -> subprocess.CompletedProcess[str]:
        argv = [str(self.script), *args]
        if self.script.suffix == ".py":
            argv = [sys.executable, *argv]
        return subprocess.run(
            argv, cwd=str(REPO), capture_output=True, text=True, timeout=300
        )

    def test_no_argument_exits_zero(self) -> None:
        self.assertEqual(0, self.run_save().returncode)

    def test_missing_file_exits_zero(self) -> None:
        self.assertEqual(0, self.run_save(str(REPO / "no" / "such.file")).returncode)

    def test_directory_argument_exits_zero(self) -> None:
        self.assertEqual(0, self.run_save(str(SCRIPTS)).returncode)

    def test_an_unhandled_path_is_silent_and_successful(self) -> None:
        """
        The contract's one mandatory silence: a path the script does not handle
        produces no output, so the caller says nothing.

        A file with no extension at all is used rather than guessing which
        extensions this project handles.
        """
        with tempfile.TemporaryDirectory() as tmp:
            odd = Path(tmp) / "unlikely-to-be-checked"
            odd.write_text("not source code\n", encoding="utf-8")
            result = self.run_save(str(odd))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(
                "",
                (result.stdout + result.stderr).strip(),
                "an unhandled path must produce no output",
            )


class SlowTierTests(unittest.TestCase):
    """
    Cheap checks on tiers this suite must NOT execute.

    verify-task and slower may take minutes to hours, and in a project whose gate
    runs the test suite, calling one from a test recurses without end.
    """

    def test_slow_tier_scripts_are_valid_shell(self) -> None:
        for tier, path in entrypoints().items():
            if tier == "save" or path.suffix not in ("", ".sh"):
                continue
            first = path.read_text(encoding="utf-8").splitlines()[0]
            if "sh" not in first:
                continue
            with self.subTest(tier=tier):
                result = subprocess.run(
                    ["sh", "-n", str(path)], capture_output=True, text=True, timeout=60
                )
                self.assertEqual(0, result.returncode, result.stderr.strip())

    def test_the_gate_does_not_chain_a_slower_tier(self) -> None:
        task = entrypoints().get("task")
        if task is None:
            self.skipTest("no task tier configured")
        text = task.read_text(encoding="utf-8")
        for slower in ("verify-unit", "verify-full"):
            self.assertNotIn(
                slower, text, f"verify-task runs {slower}; it is the <=5min gate"
            )


if __name__ == "__main__":
    unittest.main()
