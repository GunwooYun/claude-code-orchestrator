"""
Checks on what enters a session before anything is asked: path-scoped rules and
skill descriptions.

A rule with `paths:` frontmatter loads only when Claude reads or edits a file
matching one of its globs; if the YAML does not parse, Claude Code ignores the
frontmatter and loads the rule every session — silently
(code.claude.com/docs/en/memory.md, "Path-specific rules"). The budget ratchet in
`test_template_consistency.py` excludes a rule as soon as `paths:` appears near
its top, without parsing anything, so a broken frontmatter would be counted as a
saving while costing every session. These tests pin ONE frontmatter shape (a YAML
list of double-quoted globs) that is valid by construction, and require the two
detectors to agree.

Skill descriptions are always in context and are cut at 1,536 characters in the
skill listing (code.claude.com/docs/en/skills.md). The phrase checks below are
DRIFT TRIPWIRES over prose, not behavioural coverage: they fail when a trigger
phrase disappears, and cannot show that the skill still fires.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
RULES = REPO / ".claude" / "rules"
SKILLS = REPO / ".claude" / "skills"

# The budget test's detector, copied verbatim so the two can be compared.
BUDGET_DETECTOR = re.compile(r"^---\n(?:.*\n)*?paths:")
# The only accepted shape: every glob double-quoted, one per line.
PINNED_SHAPE = re.compile(r'^---\npaths:\n(?:  - "[^"\n]+"\n)+---\n')
GLOB_RE = re.compile(r'^  - "([^"\n]+)"$', re.MULTILINE)

# Rules that must stay out of the always-loaded layer. Losing the frontmatter
# would put them back silently, inside the budget's slack.
EXPECTED_SCOPED = frozenset({"coding-principles.md", "test-writing.md"})

LISTING_CAP_CHARS = 1_536
TRIGGER_PHRASES = {
    "doc-write": ("PROACTIVELY", "Confluence", "문서로 정리해줘", "Do NOT", "설명해줘"),
    "ticket": ("PROACTIVELY", "ABC-123", "Do NOT", "/jira-setup"),
}


def scoped_rules() -> list[Path]:
    return [
        p
        for p in sorted(RULES.glob("*.md"))
        if BUDGET_DETECTOR.match(p.read_text(encoding="utf-8")[:400])
    ]


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    )
    return out.stdout.splitlines()


def glob_matches(glob: str, path: str) -> bool:
    # fnmatch's `*` crosses `/`, which approximates `**`; a leading `**/` also
    # matches files at the root.
    return fnmatch.fnmatch(path, glob) or fnmatch.fnmatch(
        path, glob.removeprefix("**/")
    )


def frontmatter_field(text: str, field: str) -> str:
    """Return a top-level frontmatter field, joining a `|` block scalar."""
    head = text.split("\n---\n", 1)[0]
    lines = head.splitlines()[1:]
    for i, line in enumerate(lines):
        if not line.startswith(f"{field}:"):
            continue
        value = line.split(":", 1)[1].strip()
        if value != "|":
            return value
        block = []
        for nxt in lines[i + 1 :]:
            if nxt and not nxt.startswith(" "):
                break
            block.append(nxt.strip())
        return " ".join(block).strip()
    return ""


class ScopedRuleFrontmatterTests(unittest.TestCase):
    def test_the_expected_rules_are_scoped(self) -> None:
        names = {p.name for p in scoped_rules()}
        self.assertLessEqual(
            EXPECTED_SCOPED, names, "a rule lost its paths: frontmatter"
        )

    def test_every_frontmatter_in_rules_uses_the_pinned_shape(self) -> None:
        for path in sorted(RULES.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---\n"):
                continue
            with self.subTest(rule=path.name):
                self.assertRegex(
                    text,
                    PINNED_SHAPE,
                    "rule frontmatter must be `paths:` followed by double-quoted "
                    "globs, one per line; anything else risks a YAML error, and "
                    "a YAML error loads the rule every session",
                )

    def test_the_budget_detector_and_the_pinned_shape_agree(self) -> None:
        for path in sorted(RULES.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(rule=path.name):
                self.assertEqual(
                    bool(BUDGET_DETECTOR.match(text[:400])),
                    bool(PINNED_SHAPE.match(text)),
                    "the budget test counts this rule as scoped but the shape "
                    "check does not (or the reverse)",
                )

    def test_every_scoped_rule_matches_a_tracked_file(self) -> None:
        files = tracked_files()
        for path in scoped_rules():
            globs = GLOB_RE.findall(
                path.read_text(encoding="utf-8").split("\n---\n")[0]
            )
            with self.subTest(rule=path.name):
                self.assertTrue(globs, "no globs found")
                self.assertTrue(
                    any(glob_matches(g, f) for g in globs for f in files),
                    f"{globs} match no tracked file, so the rule never loads here",
                )


class MovedGuidanceTests(unittest.TestCase):
    """Drift tripwire over prose: the guidance moved out of testing.md still exists."""

    def test_test_writing_guidance_lives_in_the_scoped_rule(self) -> None:
        rule = (RULES / "test-writing.md").read_text(encoding="utf-8")
        for phrase in (
            "목(mock)은 외부 의존성만",
            "test_{대상}_{조건}_{기대결과}",
            "## 체크리스트",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rule)

    def test_the_testing_rule_points_at_it(self) -> None:
        testing = (RULES / "testing.md").read_text(encoding="utf-8")
        self.assertIn(".claude/rules/test-writing.md", testing)


class SkillDescriptionTests(unittest.TestCase):
    def _listing_text(self, skill: str) -> str:
        text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
        parts = (
            frontmatter_field(text, "description"),
            frontmatter_field(text, "when_to_use"),
        )
        return " ".join(p for p in parts if p)

    def test_every_description_fits_the_listing_cap(self) -> None:
        for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
            listing = self._listing_text(skill_md.parent.name)
            with self.subTest(skill=skill_md.parent.name):
                self.assertTrue(listing, "no description found")
                self.assertLess(len(listing), LISTING_CAP_CHARS)

    def test_trimmed_descriptions_keep_their_triggers(self) -> None:
        for skill, phrases in TRIGGER_PHRASES.items():
            listing = self._listing_text(skill)
            for phrase in phrases:
                with self.subTest(skill=skill, phrase=phrase):
                    self.assertIn(phrase, listing)


if __name__ == "__main__":
    unittest.main()
