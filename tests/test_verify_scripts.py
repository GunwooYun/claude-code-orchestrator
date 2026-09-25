"""
Tests for the verification-script contract (.claude/scripts/README.md).

The contract is deliberately tiny — four names, one optional argument, an exit
code — because it has to be reimplementable in any language on any stack. These
tests pin the parts a caller relies on, so a project that rewrites the scripts
can run this file to check its own implementations.

Nothing here assumes Python, ruff, ty or pytest inside the scripts. The one
exception is marked: this repository dogfoods its own contract, so `verify-task`
is expected to pass on this tree.
"""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
SCRIPTS = REPO / ".claude" / "scripts"
TIERS = ("save", "task", "unit", "full")
HOOK = REPO / ".claude" / "hooks" / "lint-on-save.py"


def script(tier: str) -> Path:
    return SCRIPTS / f"verify-{tier}"


def run(args: list[str], cwd: Path | None = None, env: dict | None = None):
    return subprocess.run(
        args,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        timeout=600,
        env={**os.environ, **(env or {})},
    )


class ContractShapeTests(unittest.TestCase):
    """Properties every implementation must have, whatever it runs inside."""

    def test_contract_is_documented(self) -> None:
        readme = SCRIPTS / "README.md"
        self.assertTrue(readme.is_file(), "the contract must be written down")
        text = readme.read_text(encoding="utf-8")
        for tier in TIERS:
            self.assertIn(f"verify-{tier}", text, f"README omits verify-{tier}")

    def test_present_scripts_are_executable_with_a_shebang(self) -> None:
        for tier in TIERS:
            path = script(tier)
            if not path.is_file():
                continue  # absence means "this tier is unconfigured" — allowed
            with self.subTest(tier=tier):
                self.assertTrue(
                    os.access(path, os.X_OK), f"{path.name} is not executable"
                )
                first = path.read_text(encoding="utf-8").splitlines()[0]
                self.assertTrue(first.startswith("#!"), f"{path.name} has no shebang")

    def test_tier_names_match_the_documented_tiers(self) -> None:
        """Script names and .claude/rules/testing.md tiers must not drift apart."""
        rules = (REPO / ".claude" / "rules" / "testing.md").read_text(encoding="utf-8")
        for tier in TIERS:
            self.assertIn(
                f"`{tier}`", rules, f"testing.md does not define the {tier} tier"
            )

    def test_no_unknown_scripts_in_the_directory(self) -> None:
        """A fifth entrypoint nobody calls is a trap; keep the surface honest."""
        allowed = {f"verify-{t}" for t in TIERS} | {"README.md"}
        found = {p.name for p in SCRIPTS.iterdir() if p.is_file()}
        self.assertEqual(
            set(),
            found - allowed,
            "unexpected files in .claude/scripts/ — either call them or remove them",
        )


class VerifySaveContractTests(unittest.TestCase):
    """verify-save is the only script with an argument, so it has more rules."""

    def setUp(self) -> None:
        if not script("save").is_file():
            self.skipTest("verify-save not configured")

    def test_no_argument_exits_zero(self) -> None:
        self.assertEqual(0, run([str(script("save"))]).returncode)

    def test_missing_file_exits_zero(self) -> None:
        result = run([str(script("save")), str(REPO / "does" / "not" / "exist.py")])
        self.assertEqual(0, result.returncode)

    def test_directory_argument_exits_zero(self) -> None:
        self.assertEqual(0, run([str(script("save")), str(SCRIPTS)]).returncode)

    def test_unhandled_file_type_is_silent_and_successful(self) -> None:
        result = run([str(script("save")), str(SCRIPTS / "README.md")])
        self.assertEqual(0, result.returncode)
        self.assertEqual(
            "",
            (result.stdout + result.stderr).strip(),
            "a file the script does not handle must produce no output",
        )

    def test_clean_input_is_silent(self) -> None:
        """The caller stays quiet on success, so success must print nothing."""
        result = run([str(script("save")), str(HOOK)])
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("", (result.stdout + result.stderr).strip())

    def test_bad_input_fails_and_explains(self) -> None:
        """Written stack-agnostically: a file this project checks, made invalid."""
        import tempfile

        handled = self._a_handled_extension()
        if handled is None:
            self.skipTest("cannot infer a file type this project checks")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / f"probe{handled}"
            target.write_text("def broken(  :\n", encoding="utf-8")
            result = run([str(script("save")), str(target)])
            self.assertNotEqual(0, result.returncode, "invalid input must fail")
            self.assertTrue(
                (result.stdout + result.stderr).strip(),
                "a failure must explain itself",
            )

    def _a_handled_extension(self) -> str | None:
        """Extensions named in the script's own case statement."""
        text = script("save").read_text(encoding="utf-8")
        for token in ("*.py", "*.js", "*.ts", "*.go", "*.rs", "*.sh", "*.bb"):
            if token in text:
                return token[1:]
        return None


class HookIntegrationTests(unittest.TestCase):
    """The hook must delegate, and must not pretend an absent script passed."""

    def payload(self, path: str) -> str:
        return json.dumps({"tool_name": "Edit", "tool_input": {"file_path": path}})

    def run_hook(self, path: str, project_dir: Path):
        return subprocess.run(
            ["python3", str(HOOK)],
            input=self.payload(path),
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(project_dir),
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
        )

    def test_hook_contains_no_stack_specific_tool_names(self) -> None:
        """The whole point of the indirection: the hook knows no toolchain."""
        source = HOOK.read_text(encoding="utf-8")
        body = "\n".join(
            line for line in source.splitlines() if not line.strip().startswith("#")
        )
        # Strip the module docstring, which names tools while explaining history.
        if body.count('"""') >= 2:
            first = body.index('"""')
            second = body.index('"""', first + 3)
            body = body[:first] + body[second + 3 :]
        for tool in ("ruff", "mypy", " ty ", "pytest", "npm", "cargo", "bitbake"):
            self.assertNotIn(
                tool,
                body,
                f"lint-on-save.py names {tool!r}; stack knowledge belongs in the script",
            )

    def test_hook_is_silent_on_a_clean_file(self) -> None:
        result = self.run_hook(str(HOOK), REPO)
        self.assertEqual(0, result.returncode)
        self.assertEqual("", (result.stdout + result.stderr).strip())

    def test_hook_reports_when_the_script_is_absent(self) -> None:
        """Absent must not look like passed."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            target = project / "probe.py"
            target.write_text("x = 1\n", encoding="utf-8")
            result = self.run_hook(str(target), project)
            self.assertEqual(0, result.returncode, "the hook must never block")
            self.assertIn("verify-save", result.stdout + result.stderr)


class ScriptHealthTests(unittest.TestCase):
    """
    Cheap checks on the scripts this suite must NOT execute.

    verify-task, verify-unit and verify-full all run this test suite (they are
    this repository's gate), so calling them from inside a test would recurse
    without end. That `verify-task` passes is already proven by the fact that
    `poe all` — which IS verify-task — is green when this file runs.

    What is left to check is that they have not rotted: valid shell, and no
    accidental recursion through a tier that a hook is allowed to call.
    """

    def test_scripts_are_valid_shell(self) -> None:
        for tier in TIERS:
            path = script(tier)
            if not path.is_file():
                continue
            first = path.read_text(encoding="utf-8").splitlines()[0]
            if "sh" not in first:
                continue  # some other language; not ours to syntax-check
            with self.subTest(tier=tier):
                result = run(["sh", "-n", str(path)])
                self.assertEqual(
                    0, result.returncode, f"{path.name}: {result.stderr.strip()}"
                )

    def test_save_tier_does_not_reach_a_slower_tier(self) -> None:
        """
        The save tier runs on every keystroke-to-disk and is the one tier a hook
        invokes, so it must not chain into a gate or a build.
        """
        if not script("save").is_file():
            self.skipTest("verify-save not configured")
        text = script("save").read_text(encoding="utf-8")
        for slower in ("verify-task", "verify-unit", "verify-full"):
            self.assertNotIn(
                slower,
                text,
                f"verify-save invokes {slower}: the save tier must stay in seconds",
            )

    def test_only_the_full_tier_chains_other_tiers(self) -> None:
        if script("task").is_file():
            self.assertNotIn(
                "verify-unit",
                script("task").read_text(encoding="utf-8"),
                "verify-task must not run the unit tier; it is the <=5min gate",
            )


if __name__ == "__main__":
    unittest.main()
