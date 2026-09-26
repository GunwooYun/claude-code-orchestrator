"""
Structural checks on the /feature skill, the prose that actually executes.

Mostly not a phrase-presence module: the checks below compare two structures
inside or across files and fail when they disagree, so they survive rewording
and catch the defect they were written for. The exception is
`TierVocabularyTests`, whose two assertions ARE substring matches on prose; like
every such assertion in this repo those are DRIFT TRIPWIRES, not behavioural
coverage — they fail when a pinned phrase disappears and pass for any text that
still contains it.

  W1  every step in the workflow diagram has a section of its own, and the
      sections appear in the diagram's order. The diagram is the sequence of
      record; a reader following the file top to bottom must walk the same path
  W2  "Phase N" is a public name: eight other files point at /feature by phase
      number, so a renumbering must break the suite rather than the pointers
  W3  the verification tier vocabulary matches the project's contract, since the
      scripts, the rules and this skill all name the same four tiers

Measured before this module existed: the diagram promised an "Implementation
Loop" step that had no section anywhere in the file — the one step where code is
written was the only step with no instructions — and `## User Confirmation`,
where the plan is approved before any code, sat AFTER the post-implementation
review section. Both are structural, and neither was detectable by a substring
test.

What these cannot show: that following the file produces good work. Only running
/feature on a real ticket shows that.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
FEATURE = REPO / ".claude" / "skills" / "feature" / "SKILL.md"

# Steps a diagram line may name. A step is a unit of work with its own section.
STEP = re.compile(r"^(Phase \d+b?|Implementation Loop|User Confirmation)", re.M)


def text() -> str:
    return FEATURE.read_text(encoding="utf-8")


def diagram_steps() -> list[str]:
    """The step sequence from the first fenced block under `## Workflow`."""
    match = re.search(r"^## Workflow\s*\n+```(?:\w*)\n(.*?)^```", text(), re.S | re.M)
    assert match, "the skill has no workflow diagram under `## Workflow`"
    seen: list[str] = []
    for step in STEP.findall(match.group(1)):
        if step not in seen:
            seen.append(step)
    return seen


def headings() -> list[tuple[int, str]]:
    return [
        (number, line.strip())
        for number, line in enumerate(text().splitlines(), start=1)
        if line.startswith("#")
    ]


def first_heading_line(step: str) -> int | None:
    for number, heading in headings():
        if step in heading:
            return number
    return None


class WorkflowStructureTests(unittest.TestCase):
    """W1 — the diagram and the sections are the same sequence."""

    def test_the_diagram_names_several_steps(self) -> None:
        """Guards the parser: no steps found would make the rest vacuous."""
        steps = diagram_steps()
        self.assertGreaterEqual(len(steps), 6, f"only parsed {steps}")

    def test_every_diagram_step_has_a_section(self) -> None:
        missing = [step for step in diagram_steps() if first_heading_line(step) is None]
        self.assertEqual(
            [],
            missing,
            f"the diagram promises {missing} but the file has no section for it — "
            "a step with no instructions is a step that does not happen",
        )

    def test_the_sections_follow_the_diagram_order(self) -> None:
        lines = [
            (step, first_heading_line(step))
            for step in diagram_steps()
            if first_heading_line(step) is not None
        ]
        out_of_order = [
            f"{lines[i][0]} (line {lines[i][1]}) comes after "
            f"{lines[i + 1][0]} (line {lines[i + 1][1]})"
            for i in range(len(lines) - 1)
            if lines[i][1] > lines[i + 1][1]
        ]
        self.assertEqual(
            [],
            out_of_order,
            "the file's order contradicts its own diagram: " + "; ".join(out_of_order),
        )

    def test_every_phase_section_appears_in_the_diagram(self) -> None:
        """
        The other direction. A section the diagram does not mention is invisible
        to the order check above — which is exactly how `## User Confirmation`
        drifted to sit after the post-implementation review without failing
        anything.
        """
        steps = set(diagram_steps())
        undeclared = [
            heading
            for _, heading in headings()
            if heading.startswith("## ")
            and (match := re.match(r"## (Phase \d+b?)", heading))
            and match.group(1) not in steps
        ]
        self.assertEqual(
            [],
            undeclared,
            f"sections the workflow diagram does not mention: {undeclared}",
        )

    def test_the_approval_step_precedes_implementation(self) -> None:
        """
        The one ordering fact worth pinning independently of the diagram: nothing
        is written before the user approves the plan.
        """
        approval = first_heading_line("User Confirmation")
        implementation = first_heading_line("Implementation Loop")
        self.assertIsNotNone(approval, "there is no user-approval section")
        self.assertIsNotNone(implementation, "there is no implementation section")
        assert approval is not None and implementation is not None
        self.assertLess(
            approval,
            implementation,
            "the file asks for approval after implementation has begun",
        )


class PhaseReferenceTests(unittest.TestCase):
    """W2 — the phase numbers are a public interface."""

    REF = re.compile(
        r"`?/feature`?[^\n]{0,40}?Phase\s+(\d+b?)|Phase\s+(\d+b?)[^\n]{0,30}?`?/feature`?"
    )

    def _inbound(self) -> set[tuple[str, str]]:
        found: set[tuple[str, str]] = set()
        for path in sorted(REPO.rglob("*.md")):
            if path == FEATURE or any(
                part in (".git", "node_modules", "checkpoints") for part in path.parts
            ):
                continue
            flat = " ".join(path.read_text(encoding="utf-8").split())
            for match in self.REF.finditer(flat):
                phase = match.group(1) or match.group(2)
                found.add((str(path.relative_to(REPO)), phase))
        return found

    def test_several_files_point_at_phases(self) -> None:
        """Guards the scan, and records that renumbering is not a local edit."""
        inbound = self._inbound()
        self.assertGreaterEqual(len(inbound), 10, f"only found {sorted(inbound)}")
        self.assertGreaterEqual(
            len({source for source, _ in inbound}), 5, "expected several source files"
        )

    def test_every_referenced_phase_exists(self) -> None:
        available = [h for _, h in headings() if "Phase" in h]
        dangling = [
            f"{source} -> Phase {phase}"
            for source, phase in sorted(self._inbound())
            if not any(re.search(rf"Phase {re.escape(phase)}\b", h) for h in available)
        ]
        self.assertEqual(
            [], dangling, "pointers at phases that do not exist: " + "; ".join(dangling)
        )


class TierVocabularyTests(unittest.TestCase):
    """W3 — one vocabulary for the verification tiers."""

    TIERS = ("save", "task", "unit", "full")

    def test_the_skill_uses_the_contract_tier_names(self) -> None:
        body = text()
        for tier in self.TIERS:
            self.assertIn(
                f"verify-{tier}" if tier != "save" else "verify-save",
                body
                + (REPO / ".claude" / "scripts" / "README.md").read_text(
                    encoding="utf-8"
                ),
                f"the {tier} tier has no entrypoint name anywhere",
            )

    def test_the_tier_table_is_owned_by_the_testing_rule(self) -> None:
        """
        The budgets and who-runs-what belong in one place. The skill may name the
        tiers and point; restating the table is how the two drifted before.
        """
        rule = (REPO / ".claude" / "rules" / "testing.md").read_text(encoding="utf-8")
        for tier in self.TIERS:
            self.assertIn(f"`{tier}`", rule, f"the rule does not define {tier}")
        self.assertIn(
            "testing.md",
            text(),
            "the skill must point at the rule that owns the tier definitions",
        )


if __name__ == "__main__":
    unittest.main()
