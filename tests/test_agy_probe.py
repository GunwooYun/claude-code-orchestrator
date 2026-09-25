"""
Tests for the agy availability probe.

The probe exists because seven files in this template tell the model to call
`agy` and, before this change, none of them said what to do when the call cannot
work. "Not installed", "not logged in" and "answered with nothing" need three
different remedies, so they have to be distinguishable.

Honesty about what is verified here: this container has no agy, so only the
MISSING state is measured against the real tool. The other three are driven
through a stub `agy` placed on PATH, which exercises the probe's logic but not
the real CLI's wording. The authentication patterns are matched loosely for that
reason, and a real agy that words the error differently would fall through to
DEGRADED — still "unusable", still a remedy, just a less specific one.
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
PROBE = REPO / ".claude" / "skills" / "antigravity-system" / "agy-probe"


def run_probe(path_prefix: str | None = None, *args: str):
    env = dict(os.environ)
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}{os.pathsep}{env['PATH']}"
    else:
        # A PATH with no agy on it, and no shell builtins missing.
        env["PATH"] = "/usr/bin:/bin"
    return subprocess.run(
        [str(PROBE), *args],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        cwd=str(REPO),
    )


def stub_agy(directory: Path, body: str) -> None:
    """Put a fake `agy` on PATH so the probe's branches can be exercised."""
    script = directory / "agy"
    script.write_text(body, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)


def state(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""


class ProbeShapeTests(unittest.TestCase):
    def test_probe_is_executable_with_a_shebang(self) -> None:
        self.assertTrue(PROBE.is_file())
        self.assertTrue(os.access(PROBE, os.X_OK))
        self.assertTrue(PROBE.read_text(encoding="utf-8").startswith("#!"))

    def test_probe_does_not_live_in_the_verification_contract_dir(self) -> None:
        """
        .claude/scripts/ is the project's verification contract. A probe is not a
        tier, and putting it there would make it look like a fifth entrypoint.
        """
        self.assertFalse((REPO / ".claude" / "scripts" / "agy-probe").exists())


class MissingTests(unittest.TestCase):
    """The only state measured against reality here: this container has no agy."""

    def test_reports_missing_and_fails(self) -> None:
        result = run_probe()
        self.assertEqual("MISSING", state(result))
        self.assertNotEqual(0, result.returncode)

    def test_says_what_to_do(self) -> None:
        self.assertIn("Install", run_probe().stdout)


class StubbedStateTests(unittest.TestCase):
    """The remaining states, driven through a stub agy."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin = Path(self.tmp.name)

    def test_ready_when_the_expected_token_comes_back(self) -> None:
        stub_agy(self.bin, '#!/bin/sh\necho "PROBE_OK"\n')
        result = run_probe(str(self.bin))
        self.assertEqual("READY", state(result))
        self.assertEqual(0, result.returncode)

    def test_unauthenticated_is_distinguished_from_missing(self) -> None:
        stub_agy(self.bin, '#!/bin/sh\necho "Error: please log in first" >&2\nexit 1\n')
        result = run_probe(str(self.bin))
        self.assertEqual("UNAUTHENTICATED", state(result))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("log in", result.stdout.lower())

    def test_unauthenticated_detected_on_stdout_too(self) -> None:
        stub_agy(self.bin, '#!/bin/sh\necho "401 Unauthenticated"\nexit 0\n')
        self.assertEqual("UNAUTHENTICATED", state(run_probe(str(self.bin))))

    def test_soft_deny_is_degraded_not_ready(self) -> None:
        """
        The documented trap: a denied tool call is skipped and the run still
        exits 0 with an empty answer. Treating that as success is how research
        silently comes back empty.
        """
        stub_agy(self.bin, "#!/bin/sh\nexit 0\n")
        result = run_probe(str(self.bin))
        self.assertEqual("DEGRADED", state(result))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("soft-deny", result.stdout)

    def test_a_hedged_answer_is_degraded(self) -> None:
        stub_agy(self.bin, '#!/bin/sh\necho "I cannot help with that."\n')
        self.assertEqual("DEGRADED", state(run_probe(str(self.bin))))

    def test_a_crash_is_degraded_and_reports_the_exit_code(self) -> None:
        stub_agy(self.bin, '#!/bin/sh\necho "segfault" >&2\nexit 139\n')
        result = run_probe(str(self.bin))
        self.assertEqual("DEGRADED", state(result))
        self.assertIn("139", result.stdout)

    def test_quiet_suppresses_output_but_keeps_the_exit_code(self) -> None:
        stub_agy(self.bin, '#!/bin/sh\necho "PROBE_OK"\n')
        ready = run_probe(str(self.bin), "--quiet")
        self.assertEqual("", ready.stdout.strip())
        self.assertEqual(0, ready.returncode)

        stub_agy(self.bin, "#!/bin/sh\nexit 0\n")
        degraded = run_probe(str(self.bin), "--quiet")
        self.assertEqual("", degraded.stdout.strip())
        self.assertNotEqual(0, degraded.returncode)

    def test_no_temp_file_is_left_behind(self) -> None:
        stub_agy(self.bin, '#!/bin/sh\necho "PROBE_OK"\necho "noise" >&2\n')
        run_probe(str(self.bin))
        leftovers = list(Path("/tmp").glob(".agy-probe-err.*"))
        self.assertEqual([], leftovers, "the probe leaked its stderr temp file")


class DegradationRuleTests(unittest.TestCase):
    """
    The probe is only useful if the rules say what to do with each state.

    These assert the guidance exists where the model will actually read it —
    .claude/rules/ is loaded into every session, the skills are not.
    """

    def test_the_delegation_rule_defines_the_fallback(self) -> None:
        rule = (REPO / ".claude" / "rules" / "antigravity-delegation.md").read_text(
            encoding="utf-8"
        )
        for token in ("agy-probe", "MISSING", "UNAUTHENTICATED", "DEGRADED"):
            self.assertIn(token, rule, f"the rule does not mention {token}")

    def test_the_rule_forbids_silent_degradation(self) -> None:
        rule = (REPO / ".claude" / "rules" / "antigravity-delegation.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "조용히",
            rule,
            "the rule must state that degrading silently is not allowed — a "
            "research document produced without agy has different breadth and "
            "must say so",
        )

    def test_initproject_branches_on_the_probe(self) -> None:
        skill = (REPO / ".claude" / "skills" / "initproject" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("agy-probe", skill)
        for token in ("MISSING", "UNAUTHENTICATED"):
            self.assertIn(token, skill, f"/initproject does not handle {token}")

    def test_feature_phase_1_degrades_instead_of_failing(self) -> None:
        skill = (REPO / ".claude" / "skills" / "feature" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("agy-probe", skill, "Phase 1 still assumes agy works")


if __name__ == "__main__":
    unittest.main()
