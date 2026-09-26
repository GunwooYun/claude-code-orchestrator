"""
Invariants for the lens-review skill.

These are DRIFT TRIPWIRES, not behavioural coverage. Every assertion below is
a substring match against prose. It fails when a pinned phrase disappears and
passes for any text that still contains it, so it catches a rename, a deletion
and a rewrite that drops a rule — and nothing else. Measured on this
repository: appending a sentence that REVERSES the asserted rule leaves the
suite green, while a meaning-preserving reword of the same rule turns it red.
A green run therefore means "the wording these tests pin is still present". It
does not mean a skill or rule behaves as documented; only running it in a
session shows that.

Parallel fan-out is easy to build and easy to build badly: the common version
concatenates three reports and calls it a review. These pin the properties that
make it worth three times the cost, because each one, if lost, turns the fan-out
into expensive noise:

  L1  lenses must be orthogonal, and each must be told what it does NOT cover —
      otherwise the same finding arrives three times
  L2  a lens that finds nothing must say so; a lens under pressure to look useful
      invents findings, and noise buries the real ones
  L3  conflicts between lenses are the point, and must not be silently resolved
      by the aggregator — a disagreement is the real design decision
  L4  the pre-filter runs once and feeds every lens the same list, or the cost
      triples and the reports become incomparable
  L5  it does not replace the separate-session review, because the orchestrator
      wrote the lens prompts and its framing survives
  L6  cost is linear in lenses, so the count is bounded and a small change is
      routed to a single call instead
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
SKILL = REPO / ".claude" / "skills" / "lens-review" / "SKILL.md"
CLAUDE_MD = REPO / "CLAUDE.md"


def flat(path: Path) -> str:
    """Whitespace-collapsed text, so markdown rewrapping cannot fail a test."""
    return " ".join(path.read_text(encoding="utf-8").split())


def frontmatter(path: Path) -> str:
    match = re.match(r"---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
    assert match, "no frontmatter"
    return " ".join(match.group(1).split())


class NamingTests(unittest.TestCase):
    def test_the_name_does_not_collide_with_built_in_review_commands(self) -> None:
        """
        A skill named `review` or `code-review` would be ambiguous against the
        built-ins, which is the mistake `/init` already made here once.
        """
        self.assertEqual("lens-review", SKILL.parent.name)
        self.assertIn("name: lens-review", frontmatter(SKILL))

    def test_it_is_auto_invocable(self) -> None:
        self.assertNotIn("disable-model-invocation", frontmatter(SKILL))


class TriggerTests(unittest.TestCase):
    """L6 — three subagents is expensive, so the trigger carries a threshold."""

    def test_the_description_requires_a_substantial_change(self) -> None:
        description = frontmatter(SKILL)
        self.assertIn("substantial", description)
        self.assertIn("5+ files", description)

    def test_a_small_change_is_routed_to_a_single_call(self) -> None:
        description = frontmatter(SKILL)
        self.assertIn("one deep-reasoning call is cheaper", description)

    def test_a_question_about_code_does_not_trigger_it(self) -> None:
        self.assertIn(
            "Do NOT use it to answer a question about code", frontmatter(SKILL)
        )


class OrthogonalityTests(unittest.TestCase):
    """L1 — overlapping lenses cost 3x for 1x."""

    def test_three_default_lenses_are_defined(self) -> None:
        body = flat(SKILL)
        for lens in ("correctness", "design", "robustness"):
            self.assertIn(lens, body, f"default lens {lens} missing")

    def test_each_lens_declares_what_it_does_not_cover(self) -> None:
        body = flat(SKILL)
        self.assertIn("무엇을 보지 않는가", body)

    def test_the_exclusion_goes_into_the_lens_prompt(self) -> None:
        """Compared case-insensitively on BOTH sides — lowering only the body
        while the needle held an uppercase NOT could never match."""
        body = flat(SKILL).lower()
        self.assertIn("what this lens explicitly does not cover".lower(), body)

    def test_non_orthogonality_is_named_as_a_failure_mode(self) -> None:
        self.assertIn("렌즈가 직교하지 않는다", flat(SKILL))


class EmptyResultTests(unittest.TestCase):
    """L2 — nothing found is a result, not a failure."""

    def test_the_prompt_permits_finding_nothing(self) -> None:
        body = flat(SKILL)
        self.assertIn("Finding nothing is a result", body)

    def test_the_prompt_forbids_inventing_findings(self) -> None:
        self.assertIn("Do NOT invent a finding to look useful", flat(SKILL))

    def test_the_output_format_has_a_nothing_found_section(self) -> None:
        self.assertIn("발견 없음", flat(SKILL))

    def test_found_nothing_is_distinguished_from_not_looked(self) -> None:
        body = flat(SKILL)
        self.assertIn("보지 않은 것", body)
        self.assertIn('"발견 없음"과 "보지 않음"은 다르다', body)


class ConflictTests(unittest.TestCase):
    """L3 — the disagreement is the product."""

    def test_conflicts_are_stated_as_the_main_value(self) -> None:
        body = flat(SKILL)
        self.assertIn("충돌이 핵심 산출물이다", body)

    def test_the_aggregator_must_not_resolve_conflicts_silently(self) -> None:
        self.assertIn("충돌을 임의로 판정하지 않는다", flat(SKILL))

    def test_a_worked_conflict_example_is_given(self) -> None:
        """An abstract instruction to 'surface conflicts' is not actionable."""
        body = flat(SKILL)
        self.assertIn("가드를 추가하라", body)
        self.assertIn("존재하지 않아야 한다", body)

    def test_conflicts_come_first_in_the_output(self) -> None:
        body = SKILL.read_text(encoding="utf-8")
        conflict = body.index("### 충돌")
        findings = body.index("### 발견 (심각도 순)")
        self.assertLess(conflict, findings, "conflicts must lead the report")


class PrefilterTests(unittest.TestCase):
    """L4 — once, shared, and declared as non-exhaustive."""

    def test_the_prefilter_runs_once_for_all_lenses(self) -> None:
        body = flat(SKILL)
        self.assertIn("렌즈마다 프리필터를 돌리지 않는다", body)

    def test_the_reason_is_comparability_not_only_cost(self) -> None:
        self.assertIn("취합 단계에서 비교가 불가능", flat(SKILL))

    def test_lenses_are_told_the_list_is_not_exhaustive(self) -> None:
        self.assertIn("NOT exhaustive", flat(SKILL))

    def test_it_defers_to_the_routing_rule_rather_than_restating_it(self) -> None:
        self.assertIn("antigravity-delegation.md", flat(SKILL))

    def test_it_degrades_without_agy(self) -> None:
        self.assertIn("agy 를 쓸 수 없으면 프리필터를 생략", flat(SKILL))


class SeparateSessionTests(unittest.TestCase):
    """L5 — isolated context is not neutrality when you wrote the prompt."""

    def test_it_does_not_claim_to_replace_the_separate_session(self) -> None:
        body = flat(SKILL)
        self.assertIn("별도 세션 리뷰를 대체하지 않는다", body)

    def test_the_residual_bias_is_named(self) -> None:
        self.assertIn("프롬프트를 내가 쓴다", flat(SKILL))

    def test_the_description_excludes_final_review_of_own_work(self) -> None:
        self.assertIn("do NOT use it as the final review", frontmatter(SKILL))

    def test_it_matches_the_existing_operational_rule(self) -> None:
        """CLAUDE.md already says the implementing session is biased."""
        self.assertIn("git worktree add --detach", flat(CLAUDE_MD))
        self.assertIn("git worktree add --detach", flat(SKILL))


class CostTests(unittest.TestCase):
    """L6 — cost is linear in lenses."""

    def test_the_lens_count_is_bounded_with_a_reason(self) -> None:
        body = flat(SKILL)
        self.assertIn("3개를 넘기지 않는 것을 권한다", body)
        self.assertIn("비용은 렌즈 수에 선형", body)

    def test_verification_is_conditional_not_default(self) -> None:
        body = flat(SKILL)
        self.assertIn("검증은 조건부로", body)
        self.assertIn("항상 하지 않는다", body)

    def test_lenses_run_in_parallel_in_one_message(self) -> None:
        self.assertIn("한 메시지에서 동시에 spawn", flat(SKILL))

    def test_the_main_aggregates_because_subagents_cannot_fan_out(self) -> None:
        self.assertIn("서브에이전트는 서브에이전트를 못 띄운다", flat(SKILL))


if __name__ == "__main__":
    unittest.main()
