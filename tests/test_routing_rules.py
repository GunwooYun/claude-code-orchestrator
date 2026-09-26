"""
Invariants for the cost-based routing rules.

These are DRIFT TRIPWIRES, not behavioural coverage. Every assertion below is
a substring match against prose. It fails when a pinned phrase disappears and
passes for any text that still contains it, so it catches a rename, a deletion
and a rewrite that drops a rule — and nothing else. Measured on this
repository: appending a sentence that REVERSES the asserted rule leaves the
suite green, while a meaning-preserving reword of the same rule turns it red.
A green run therefore means "the wording these tests pin is still present". It
does not mean a skill or rule behaves as documented; only running it in a
session shows that.

The template used to route by TOPIC only — "research goes to agy" — which left
token-heavy work that nobody calls research flowing to Claude. These pin the
properties that make the cost axis safe, because each one, if lost, turns the
funnel from a saving into a quality regression:

  A1  the cost axis exists in the always-loaded rules, and in CLAUDE.md, which
      is the only file guaranteed to be in context
  A2  the pre-filter returns locations and facts, never verdicts — an agy summary
      would make deep-reasoning reason about the summary instead of the code
  A3  the pre-filter is recall-oriented, and the consumer is told its input was
      filtered, or it concludes that what it cannot see does not exist
  A4  small inputs skip the funnel, or the round trip costs more than it saves
  A5  judgement never moves to agy; only the reading does
  A6  the honest limit of the measurement is stated, since the log records only
      agy calls and cannot show the work Claude did instead
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
AGY_RULE = REPO / ".claude" / "rules" / "antigravity-delegation.md"
DR_RULE = REPO / ".claude" / "rules" / "deep-reasoning-delegation.md"
CLAUDE_MD = REPO / "CLAUDE.md"


def flat(path: Path) -> str:
    """Whitespace-collapsed text, so markdown rewrapping cannot fail a test."""
    return " ".join(path.read_text(encoding="utf-8").split())


ROUTING_FILES = (AGY_RULE, DR_RULE, CLAUDE_MD)


class CostAxisTests(unittest.TestCase):
    """A1 — the axis must be where the model will read it."""

    def test_the_axis_is_named_in_every_routing_file(self) -> None:
        for path in ROUTING_FILES:
            with self.subTest(file=path.name):
                self.assertIn("토큰량 × 추론 난이도", flat(path))

    def test_claude_md_carries_the_matrix(self) -> None:
        """CLAUDE.md is the one file always in context."""
        body = flat(CLAUDE_MD)
        for cell in ("추론 쉬움", "추론 어려움", "토큰 많음", "토큰 적음"):
            self.assertIn(cell, body, f"CLAUDE.md omits {cell}")

    def test_the_empty_cells_are_explained(self) -> None:
        """The reason the axis exists at all."""
        self.assertIn("위쪽 두 칸", flat(AGY_RULE))
        self.assertIn("토큰 편중의 구조적 원인", flat(AGY_RULE))

    def test_token_heavy_reasoning_light_work_is_enumerated(self) -> None:
        body = flat(AGY_RULE)
        for case in ("스택트레이스", "영향 분석", "프리필터", "보일러플레이트"):
            self.assertIn(case, body, f"the agy rule does not list {case}")


class PrefilterContractTests(unittest.TestCase):
    """A2, A3, A4 — the rules that keep a funnel from degrading quality."""

    def test_the_prefilter_returns_locations_not_verdicts(self) -> None:
        for path in (AGY_RULE, DR_RULE, CLAUDE_MD):
            with self.subTest(file=path.name):
                body = flat(path)
                self.assertIn("file:line", body)
                self.assertIn("판정", body)

    def test_summarising_instead_of_pointing_is_named_as_the_hazard(self) -> None:
        """
        The failure this rule exists to prevent: reasoning about a summary.
        """
        for path in (AGY_RULE, DR_RULE, CLAUDE_MD):
            with self.subTest(file=path.name):
                self.assertIn("코드가 아니라 요약을 추론", flat(path))

    def test_the_prefilter_is_recall_oriented(self) -> None:
        body = flat(AGY_RULE)
        self.assertIn("재현율", body)
        self.assertIn("확실하지 않으면 포함하라", body)

    def test_the_consumer_is_told_its_input_was_filtered(self) -> None:
        for path in (AGY_RULE, DR_RULE):
            with self.subTest(file=path.name):
                self.assertIn("걸러진 입력", flat(path))

    def test_a_threshold_keeps_small_inputs_out_of_the_funnel(self) -> None:
        for path in (AGY_RULE, DR_RULE):
            with self.subTest(file=path.name):
                body = flat(path)
                self.assertIn(
                    "500줄", body, "no size threshold, so every input funnels"
                )
                self.assertIn("파일 5개", body)

    def test_the_funnel_degrades_when_agy_is_unavailable(self) -> None:
        for path in (AGY_RULE, DR_RULE):
            with self.subTest(file=path.name):
                self.assertIn("프리필터", flat(path))
        self.assertIn("퍼널을 생략하고", flat(AGY_RULE))


class JudgementStaysWithClaudeTests(unittest.TestCase):
    """A5 — the point is to stop the expensive model reading widely, not to
    move decisions to the cheap one."""

    def test_judgement_is_explicitly_not_delegated(self) -> None:
        self.assertIn("판정은 절대 넘기지 않는다", flat(DR_RULE))
        self.assertIn("판단은 넘기지 않는다", flat(AGY_RULE))

    def test_the_separation_is_stated_as_the_safeguard(self) -> None:
        body = flat(AGY_RULE)
        self.assertIn(
            "agy 는 넓게 읽고 후보를 뽑는다. Claude 는 무엇이 진짜인지 판정한다",
            body,
        )

    def test_design_and_safety_questions_stay_with_deep_reasoning(self) -> None:
        body = flat(AGY_RULE)
        self.assertIn("이 코드가 안전한가", body)
        self.assertIn("이 설계가 맞나", body)


class MeasurementHonestyTests(unittest.TestCase):
    """A6 — a metric whose limit is unstated will be over-read."""

    def test_the_measurable_and_unmeasurable_are_separated(self) -> None:
        body = flat(AGY_RULE)
        self.assertIn("측정된다", body)
        self.assertIn("측정되지 않는다", body)

    def test_the_log_only_records_agy_calls(self) -> None:
        body = flat(AGY_RULE)
        self.assertIn('"tool": "antigravity"', body)
        self.assertIn("Claude 가 한 일은 로그에 없다", body)

    def test_the_claim_is_marked_as_weak_evidence(self) -> None:
        self.assertIn("약한 증거", flat(AGY_RULE))

    def test_the_log_claim_matches_the_hook(self) -> None:
        """
        The rule says the hook records only agy. If that ever changes, the rule's
        honesty caveat becomes wrong in the other direction.
        """
        hook = (REPO / ".claude" / "hooks" / "log-cli-tools.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"tool": "antigravity"', hook)


if __name__ == "__main__":
    unittest.main()
