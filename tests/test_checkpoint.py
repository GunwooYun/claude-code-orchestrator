"""Tests for .claude/skills/checkpointing/checkpoint.py (Session History replacement)."""

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".claude" / "skills" / "checkpointing" / "checkpoint.py"
spec = importlib.util.spec_from_file_location("checkpoint", SCRIPT)
checkpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checkpoint)

HISTORY = "## Session History\n\n### 2026-08-31\n\n**agy조사:**\n- ✓ test...\n"


class ReplaceSessionHistoryTests(unittest.TestCase):
    def test_inline_mention_is_not_treated_as_section(self):
        doc = (
            "# Doc\n\n## Ops\n\n- `/checkpointing` overwrites the `## Session History` "
            "section, commit first.\n- another note\n\n## Language\n\n- English\n"
        )
        out = checkpoint.replace_session_history(doc, HISTORY)
        self.assertIn("- another note", out)
        self.assertIn("## Language", out)
        self.assertTrue(out.rstrip().endswith("- ✓ test..."))
        self.assertEqual(out.count("## Session History"), 2)  # inline mention + real section

    def test_existing_section_is_replaced_not_duplicated(self):
        doc = "# Doc\n\n## Session History\n\n### 2026-08-01\n\n- old\n"
        out = checkpoint.replace_session_history(doc, HISTORY)
        self.assertNotIn("- old", out)
        self.assertEqual(out.count("## Session History"), 1)

    def test_content_after_section_survives(self):
        doc = (
            "# Doc\n\n## Session History\n\n### 2026-08-01\n\n- old\n\n"
            "## Current Project: X\n\n- goal\n"
        )
        out = checkpoint.replace_session_history(doc, HISTORY)
        self.assertIn("## Current Project: X", out)
        self.assertIn("- goal", out)
        self.assertNotIn("- old", out)

    def test_appends_when_missing(self):
        out = checkpoint.replace_session_history("# Doc\n\nbody\n", HISTORY)
        self.assertTrue(out.startswith("# Doc\n\nbody\n\n## Session History"))


class LocalDateTests(unittest.TestCase):
    def test_offset_timestamp_keeps_local_calendar_day(self):
        # 2026-08-31 01:00 KST is 2026-08-30 16:00 UTC; grouping must follow the offset given.
        self.assertEqual(checkpoint.local_date("2026-08-31T01:00:00+09:00")[:7], "2026-08")

    def test_invalid_timestamp_falls_back(self):
        self.assertEqual(checkpoint.local_date("garbage"), "garbage")
        self.assertEqual(checkpoint.local_date(""), "unknown")


if __name__ == "__main__":
    unittest.main()
