"""
Drift tripwires for the routing rules — not behavioural coverage.

Each assertion is a substring match against prose: it catches a rule that was
deleted or renamed, nothing more. A green run means the pinned wording is still
there, not that a session behaves as written.

Reduced on 2026-10-03 (direction review): the rules files were cut to their
decisions, and this file now pins only the four rules whose loss would turn the
orchestrator's delegation from a saving into a quality regression.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
CLAUDE_MD = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
AGY = (REPO / ".claude/rules/antigravity-delegation.md").read_text(encoding="utf-8")
DEEP = (REPO / ".claude/rules/deep-reasoning-delegation.md").read_text(encoding="utf-8")


class RoutingRuleTests(unittest.TestCase):
    def test_judgement_is_never_delegated_to_agy(self) -> None:
        self.assertIn("판정은 넘기지 않는다", CLAUDE_MD)
        self.assertIn("never for judgement", AGY)
        self.assertIn("Judgement is never delegated to agy", DEEP)

    def test_the_prefilter_returns_locations_and_facts_only(self) -> None:
        self.assertIn("`file:line` 과 사실만", CLAUDE_MD)
        self.assertIn("**locations and facts only**", AGY)

    def test_degrading_without_agy_is_never_silent(self) -> None:
        self.assertIn("Never degrade silently", AGY)

    def test_the_large_change_threshold_is_cited_not_redefined(self) -> None:
        self.assertIn("**파일 5개 또는 500줄.**", CLAUDE_MD)
        for name, text in (("antigravity", AGY), ("deep-reasoning", DEEP)):
            with self.subTest(rule=name):
                self.assertIn("5+ files or 500+ lines", text)
                self.assertIn("「큰 변경의 기준」", text)


if __name__ == "__main__":
    unittest.main()
