"""
Invariants for the doc-write skill.

A skill is prose, so what can be checked mechanically is narrow — but these are
exactly the properties that broke elsewhere in this template, so they are worth
pinning:

  D1  the skill must not copy the style rules; it must point at them (duplicated
      guidance in two files is the drift this repo keeps repairing)
  D2  the trigger boundary must be in the description, because that is the only
      thing the model reads when deciding whether to invoke a skill at all
  D3  it must not hard-code a Confluence space, parent page or MCP tool name —
      those are per-project or per-connector and belong nowhere in a template
  D4  the publish policy must distinguish a new page from an existing one
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
SKILL = REPO / ".claude" / "skills" / "doc-write" / "SKILL.md"
STYLE_FULL = REPO / ".claude" / "docs" / "writing-style.md"
STYLE_RULE = REPO / ".claude" / "rules" / "writing-style.md"


def skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def frontmatter(text: str) -> str:
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, "the skill has no frontmatter"
    return match.group(1)


class ExistenceTests(unittest.TestCase):
    def test_the_skill_exists_and_is_named_after_its_directory(self) -> None:
        self.assertTrue(SKILL.is_file())
        self.assertIn("name: doc-write", frontmatter(skill_text()))

    def test_it_is_model_invocable(self) -> None:
        """
        The user asked not to have to type it. A skill is auto-invocable unless
        disable-model-invocation is set, so that flag must be absent.
        """
        self.assertNotIn("disable-model-invocation", frontmatter(skill_text()))


class PointerTests(unittest.TestCase):
    """D1 — procedure here, rules there."""

    def test_it_points_at_the_full_style_document(self) -> None:
        self.assertIn(".claude/docs/writing-style.md", skill_text())

    def test_it_does_not_copy_the_style_rules(self) -> None:
        """
        Sampled from distinctive lines of the style document rather than by
        length, so paraphrase is allowed but transcription is not.
        """
        style = STYLE_FULL.read_text(encoding="utf-8")
        long_lines = [
            line.strip()
            for line in style.splitlines()
            if len(line.strip()) > 45
            and not line.strip().startswith(("#", "|", ">", "-"))
        ]
        self.assertTrue(long_lines, "the style document has no sampleable prose")
        copied = [line for line in long_lines if line in skill_text()]
        self.assertEqual(
            [],
            copied[:3],
            "the skill transcribes the style document instead of pointing at it",
        )

    def test_it_says_not_to_duplicate_the_rules(self) -> None:
        self.assertIn("복사하지 않는다", skill_text())


class TriggerBoundaryTests(unittest.TestCase):
    """D2 — the description is the only lever for auto-invocation."""

    def test_the_description_names_what_triggers_it(self) -> None:
        description = frontmatter(skill_text())
        for phrase in ("Confluence", "문서로 정리해줘", "보고서 써줘"):
            self.assertIn(phrase, description, f"description omits {phrase!r}")

    def test_the_description_names_what_must_not_trigger_it(self) -> None:
        description = frontmatter(skill_text())
        for phrase in ("설명해줘", "분석해줘", "요약해줘"):
            self.assertIn(
                phrase,
                description,
                f"description does not exclude {phrase!r}, so a chat answer would "
                "become a document",
            )

    def test_code_comments_are_excluded(self) -> None:
        description = frontmatter(skill_text())
        self.assertTrue(
            "docstring" in description or "commit message" in description,
            "the description must exclude code comments and commit messages",
        )

    def test_the_ambiguous_case_defaults_to_chat(self) -> None:
        text = skill_text()
        self.assertIn("애매하면 채팅으로", text)


class NoProjectSpecificsTests(unittest.TestCase):
    """D3 — a template must not carry one project's Confluence layout."""

    def test_no_hard_coded_space_key_or_parent_page(self) -> None:
        text = skill_text()
        # A space key in prose would look like `스페이스 DEV` or `space=DEV`.
        self.assertNotRegex(
            text,
            r"스페이스\s+[A-Z]{2,}\b",
            "a concrete space key is hard-coded; it belongs in CLAUDE.md per project",
        )
        self.assertIn("묻는다", text, "the skill must ask when the location is unset")

    def test_it_records_the_answer_in_the_project_file_not_in_itself(self) -> None:
        """
        Under `## Project Setup`, not `## Current Project`: the latter is
        replaced per work unit by /feature, which would silently delete the
        recorded space key. See tests/test_claude_md_sections.py.
        """
        self.assertIn("Project Setup", skill_text())

    def test_no_hard_coded_mcp_tool_names(self) -> None:
        """
        Connector tool names differ per setup, so naming one exactly would break
        on a different Atlassian connector.
        """
        self.assertNotIn("mcp__", skill_text())
        self.assertIn("커넥터 설정에 따라 다르므로", skill_text())


class PublishPolicyTests(unittest.TestCase):
    """D4 — the asymmetry between a new page and someone else's page."""

    def test_new_and_existing_pages_are_treated_differently(self) -> None:
        text = skill_text()
        self.assertIn("새 페이지", text)
        self.assertIn("기존 페이지", text)
        self.assertIn("먼저 확인받는다", text)

    def test_it_cannot_promise_to_log_the_user_in(self) -> None:
        text = skill_text()
        self.assertIn(
            "로그인은 대신 할 수 없다",
            text,
            "OAuth happens in the client; the skill must not imply otherwise",
        )

    def test_a_draft_is_not_discarded_when_the_connector_is_missing(self) -> None:
        self.assertIn("버리지 않고", skill_text())


class StyleRuleWiringTests(unittest.TestCase):
    """The always-loaded rule should lead here, or the skill may never fire."""

    def test_the_always_loaded_rule_mentions_the_skill(self) -> None:
        self.assertIn("doc-write", STYLE_RULE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
