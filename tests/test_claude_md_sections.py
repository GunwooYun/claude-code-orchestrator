"""
Lifetime discipline for the `CLAUDE.md` sections the skills write into.

These are drift tripwires, not behavioural coverage: they assert that prose in
one file still says what prose in another file assumes. They cannot prove a
skill behaves correctly — only a session can — but they do catch the failure
that motivated them, which was real and silent:

    /initproject seeds `## Current Project` (overview, conventions)
    /jira-setup  stores `### Jira` there   (site, transitions, write policy)
    /doc-write   stores the Confluence location there
    /feature     Phase 5 says "replace an existing `## Current Project` block"
    → the first three are erased by the fourth, and /ticket then stops or re-asks

Three sections with three different lifetimes had been collapsed into one
heading, and one of the writers had replace semantics. The repair is that the
lifetime decides the heading:

  C1  the three sections, their lifetimes and their order are defined in
      CLAUDE.md, which is the one file always in context
  C2  project-permanent state goes to `## Project Setup`, and each writer of it
      names the work-unit section it must not use — that a skill does not
      *replace* the block is NOT mechanically checkable here, because a warning
      against replacing it contains the same words as an instruction to do so
  C3  the reader of that state looks for it under the same heading
  C4  `/feature` replaces only the work-unit section, and is told so explicitly
  C5  the order is Setup → Current → Session History, because /checkpointing
      rewrites the last one and anything after it is lost
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
CLAUDE_MD = REPO / "CLAUDE.md"
SKILLS = REPO / ".claude" / "skills"

SETUP_SECTION = "## Project Setup"
WORK_SECTION = "## Current Project"
HISTORY_SECTION = "## Session History"

INITPROJECT = SKILLS / "initproject" / "SKILL.md"
FEATURE = SKILLS / "feature" / "SKILL.md"
JIRA_SETUP = SKILLS / "jira-setup" / "SKILL.md"
DOC_WRITE = SKILLS / "doc-write" / "SKILL.md"
TICKET = SKILLS / "ticket" / "SKILL.md"

# Skills that store state whose lifetime is the whole project.
PERMANENT_WRITERS = (INITPROJECT, JIRA_SETUP, DOC_WRITE)


def flat(path: Path) -> str:
    """Whitespace-collapsed text, so markdown rewrapping cannot fail a test."""
    return " ".join(path.read_text(encoding="utf-8").split())


class ContractTests(unittest.TestCase):
    """C1 — the lifetimes are stated where every session reads them."""

    def test_claude_md_names_all_three_sections(self) -> None:
        body = flat(CLAUDE_MD)
        for section in (SETUP_SECTION, WORK_SECTION, HISTORY_SECTION):
            self.assertIn(section, body, f"CLAUDE.md does not define {section}")

    def test_claude_md_states_each_lifetime(self) -> None:
        body = flat(CLAUDE_MD)
        for lifetime in ("프로젝트 영구", "작업 단위", "세션"):
            self.assertIn(lifetime, body, f"no lifetime named {lifetime!r}")

    def test_claude_md_states_which_section_is_replaced(self) -> None:
        body = flat(CLAUDE_MD)
        self.assertIn("교체한다", body)
        self.assertIn("덧붙인다", body)


class PermanentStateTests(unittest.TestCase):
    """C2 — several writers, no replacer."""

    def test_permanent_writers_target_the_setup_section(self) -> None:
        for path in PERMANENT_WRITERS:
            with self.subTest(skill=path.parent.name):
                self.assertIn(
                    SETUP_SECTION,
                    flat(path),
                    "project-permanent state is stored under a heading that "
                    "/feature replaces",
                )

    def test_the_write_instruction_itself_names_the_setup_section(self) -> None:
        """
        Mentioning the heading somewhere is not enough: the skills also warn
        about the section they must NOT use, so a file can name both while
        instructing the wrong one. This anchors on the instruction site.
        """
        anchor = f"이 스킬 파일이 아니라 `CLAUDE.md` 의 `{SETUP_SECTION}`"
        for path in (JIRA_SETUP, DOC_WRITE):
            with self.subTest(skill=path.parent.name):
                self.assertIn(
                    anchor,
                    flat(path),
                    "the sentence that says where to write still points at "
                    "another section",
                )

    def test_permanent_writers_name_the_hazard_they_must_avoid(self) -> None:
        """
        Whether a skill *replaces* the block cannot be checked by proximity —
        every warning about replacing it also mentions both the verb and the
        heading, and a negation reads the same to a substring match. What is
        checkable is that each writer of permanent state names the section it
        must not use, and says its update is additive.
        """
        for path in (JIRA_SETUP, DOC_WRITE):
            with self.subTest(skill=path.parent.name):
                body = flat(path)
                self.assertIn(
                    WORK_SECTION,
                    body,
                    "the skill does not name the section whose contents are "
                    "replaced per work unit, so a future edit may drift back to it",
                )
                self.assertIn("/feature", body)

    def test_more_than_one_skill_writes_the_setup_section(self) -> None:
        """
        If only one skill ever wrote it, a separate heading would be pointless —
        the whole reason it exists is that its writers have different moments.
        """
        writers = [p for p in PERMANENT_WRITERS if SETUP_SECTION in flat(p)]
        self.assertGreater(len(writers), 1)


class ReaderTests(unittest.TestCase):
    """C3 — a reader looking under the old heading finds nothing."""

    def test_ticket_reads_the_setup_section(self) -> None:
        self.assertIn(SETUP_SECTION, flat(TICKET))

    def test_ticket_does_not_look_under_the_work_unit_section(self) -> None:
        body = flat(TICKET)
        jira_mentions = [
            body[max(0, i - 80) : i + 80]
            for i in range(len(body))
            if body.startswith(WORK_SECTION, i)
        ]
        for window in jira_mentions:
            self.assertNotIn(
                "Jira",
                window,
                "/ticket still expects the Jira config under the section "
                "/feature replaces",
            )


class FeatureScopeTests(unittest.TestCase):
    """C4 — the replace rule has to name its limit."""

    def test_feature_replaces_only_the_work_unit_section(self) -> None:
        body = flat(FEATURE)
        self.assertIn(WORK_SECTION, body)
        self.assertIn("Replace an existing", body)

    def test_feature_is_told_not_to_touch_the_setup_section(self) -> None:
        self.assertIn(
            f"`{SETUP_SECTION}` 블록은 건드리지 않는다",
            flat(FEATURE),
            "nothing stops Phase 5 from replacing the permanent config",
        )


class OrderingTests(unittest.TestCase):
    """C5 — /checkpointing rewrites the last section; order is load-bearing."""

    def test_claude_md_states_the_order(self) -> None:
        body = flat(CLAUDE_MD)
        setup = body.index(SETUP_SECTION)
        history = body.index(HISTORY_SECTION)
        self.assertLess(setup, history, "the documented order is Setup → History")

    def test_initproject_places_the_setup_section_before_session_history(self) -> None:
        body = flat(INITPROJECT)
        self.assertIn(SETUP_SECTION, body)
        self.assertIn("Session History", body)

    def test_writers_are_warned_about_the_session_history_boundary(self) -> None:
        for path in (FEATURE, JIRA_SETUP, DOC_WRITE):
            with self.subTest(skill=path.parent.name):
                self.assertIn(
                    "Session History",
                    flat(path),
                    "a writer that does not know the boundary can write past it, "
                    "where /checkpointing will delete its work",
                )


if __name__ == "__main__":
    unittest.main()
