"""
Tests for the rating step of /lens-review (`prompt rate`, ordering in the
report) and the lens-verifier agent. Split from test_lens_review.py (file size
rule).
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from test_lens_review import FINDING, LENSES, REPO, SKILL, lr, make_run

VERIFIER = REPO / ".claude" / "agents" / "lens-verifier.md"


def finding(n: int, line: int, claim: str) -> str:
    return (
        FINDING.replace("F1", f"F{n}")
        .replace("x.py:3", f"x.py:{line}")
        .replace("The loop skips the last item.", claim)
    )


class RatingTests(unittest.TestCase):
    """V-rate: the rater orders kept findings; it never drops one."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.run_dir = make_run(self.root)
        for lens in LENSES:
            (self.run_dir / f"lens-{lens}.md").write_text("NO FINDINGS\n")
        # Three kept findings and one refuted, in two lenses.
        (self.run_dir / "lens-tests.md").write_text(
            finding(1, 1, "Claim one.") + finding(2, 2, "Claim two.")
        )
        (self.run_dir / "lens-correctness.md").write_text(
            finding(1, 3, "Claim three.") + finding(2, 4, "Claim refuted.")
        )
        for name, text in (
            ("tests-1", "verdict: CONFIRMED\nimpact: low\n"),
            ("tests-2", "verdict: CONFIRMED\nimpact: none\n"),
            ("correctness-1", "verdict: CONFIRMED\nimpact: low\ncorrection: line 5\n"),
            ("correctness-2", "verdict: REFUTED\nevidence: x.py:9\n"),
        ):
            (self.run_dir / f"verify-{name}.md").write_text(text)

    def ids(self) -> dict[str, str]:
        """claim text -> R id, as the rater sees them."""
        kept = lr.rate_order(self.run_dir) or []
        return {f["claim"]: f"R{i}" for i, (_, f) in enumerate(kept, 1)}

    def rate(self, lines: dict[str, str]) -> None:
        ids = self.ids()
        (self.run_dir / "rate.md").write_text(
            "".join(f"{ids[claim]}: {value}\n" for claim, value in lines.items())
        )

    def summary(self) -> list[str]:
        text, _ = lr.build_report(self.root, self.run_dir)
        part = text.split("## Summary", 1)[1].split("\n## ", 1)[0]
        return [line for line in part.splitlines() if line.startswith("- ")]

    def test_rate_prompt_holds_every_kept_finding_and_no_refuted_one(self) -> None:
        prompt = lr.rate_prompt(self.run_dir)
        for claim in ("Claim one.", "Claim two.", "Claim three."):
            self.assertEqual(1, prompt.count(claim), claim)
        self.assertNotIn("Claim refuted.", prompt)
        self.assertIn("correction: line 5", prompt)
        self.assertEqual(["R1", "R2", "R3"], re.findall(r"^### (R\d+)$", prompt, re.M))
        self.assertNotIn("{FINDINGS}", prompt)

    def test_rate_prompt_is_the_same_every_time_it_is_built(self) -> None:
        """collect matches the rater's answer by prompt, so it must not vary."""
        self.assertEqual(lr.rate_prompt(self.run_dir), lr.rate_prompt(self.run_dir))

    def test_rate_prompt_waits_for_every_verdict(self) -> None:
        (self.run_dir / "verify-tests-2.md").unlink()
        self.assertIsNone(lr.rate_order(self.run_dir))
        with self.assertRaises(ValueError):
            lr.rate_prompt(self.run_dir)

    def test_report_orders_production_and_worst_consequence_first(self) -> None:
        self.rate(
            {
                "Claim one.": "production=no consequence=cosmetic reach=always",
                "Claim two.": "production=yes consequence=data-loss reach=rare",
                "Claim three.": "production=yes consequence=diagnosability reach=common",
            }
        )
        lines = self.summary()
        self.assertEqual(4, len(lines))  # three kept + one refuted: nothing dropped
        self.assertIn("production · data-loss · rare · tests F2", lines[0])
        self.assertIn("production · diagnosability · common · correctness F1", lines[1])
        self.assertIn("not production · cosmetic · always · tests F1", lines[2])
        self.assertTrue(lines[3].startswith("- REFUTED · correctness F2"))

    def test_report_shows_the_rating_on_each_finding(self) -> None:
        self.rate(
            {c: "production=yes consequence=outage reach=common" for c in self.ids()}
        )
        text, complete = lr.build_report(self.root, self.run_dir)
        self.assertTrue(complete)
        self.assertEqual(3, text.count("- rating: production · outage · common"))
        self.assertIn("- rated: production 3, not production 0, unrated 0", text)

    def test_report_without_rating_is_incomplete_and_keeps_every_finding(self) -> None:
        text, complete = lr.build_report(self.root, self.run_dir)
        self.assertFalse(complete)
        self.assertIn("no rating saved (rate.md)", text)
        self.assertEqual(4, len(self.summary()))

    def test_report_with_a_partial_rating_is_incomplete(self) -> None:
        self.rate({"Claim one.": "production=yes consequence=outage reach=common"})
        text, complete = lr.build_report(self.root, self.run_dir)
        self.assertFalse(complete)
        self.assertIn("rate.md rates 1 of 3 kept findings", text)

    def test_agent_for_routes_lens_prompts_to_the_reviewer_only(self) -> None:
        self.assertEqual("lens-reviewer", lr.agent_for("lens-tests.md"))
        self.assertEqual("lens-verifier", lr.agent_for("verify-tests-1.md"))
        self.assertEqual("lens-verifier", lr.agent_for("rate.md"))


class VerifierAgentTests(unittest.TestCase):
    def test_verifier_is_locked_to_reading_with_sonnet_medium(self) -> None:
        """V9 for the verifier agent."""
        text = VERIFIER.read_text(encoding="utf-8")
        head = text.split("---", 2)[1]
        fm = {
            m.group(1): m.group(2).strip()
            for m in re.finditer(r"^(\w+):\s*(.*)$", head, re.MULTILINE)
        }
        self.assertEqual("lens-verifier", fm["name"])
        self.assertEqual(
            {"Read", "Grep", "Glob"}, {t.strip() for t in fm["tools"].split(",")}
        )
        self.assertEqual("sonnet", fm["model"])
        self.assertEqual("medium", fm["effort"])
        self.assertEqual("true", fm["omitClaudeMd"])

    def test_skill_sends_verify_and_rate_prompts_to_the_verifier(self) -> None:
        """V10: SKILL.md names the agent that lens-audit expects for each prompt."""
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        verify = text.split("prompt verify", 1)[1].split("prompt rate", 1)[0]
        rate = text.split("prompt rate", 1)[1].split("**Report.**", 1)[0]
        self.assertIn('subagent_type="lens-verifier"', verify)
        self.assertIn('subagent_type="lens-verifier"', rate)
        lens = text.split("prompt lens", 1)[1].split("prompt verify", 1)[0]
        self.assertIn('subagent_type="lens-reviewer"', lens)


if __name__ == "__main__":
    unittest.main()
