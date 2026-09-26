"""
Regression tests for the defects that made checkpoint.py able to destroy data.

Written before the fixes, per `.claude/rules/testing.md` principle 1 — each test
here failed against the original implementation, which is what makes it a
verification rather than a description of current behaviour.

Scenario IDs match the hardening notes in `.claude/docs/DESIGN.md`:

  C1  the section regex ended only at `^## `, so an intervening H1 or thematic
      break was swallowed and destroyed on rewrite
  C2  a malformed timestamp in one log line raised an uncaught ValueError and
      aborted the whole checkpoint
  C3  `--since` was neither validated nor reported; a typo produced a traceback
  C4  `--since` was forced to UTC while grouping is by local date, so an entry
      belonging to the requested local day was dropped
  C5  context files were rewritten read-then-write, with no temp file and no
      backup, so a crash mid-write truncated CLAUDE.md
  C6  `HEAD~10` was hard-coded, so a repository with fewer than 11 commits
      silently reported "no changes"
  C7  entries from any tool other than agy were silently discarded
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).parent.parent
SCRIPT = REPO / ".claude" / "skills" / "checkpointing" / "checkpoint.py"

spec = importlib.util.spec_from_file_location("checkpoint", SCRIPT)
assert spec and spec.loader
checkpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checkpoint)


class SectionBoundaryTests(unittest.TestCase):
    """C1 — the section must not swallow content it does not own."""

    HISTORY = "## Session History\n\n### 2026-09-25\n\n- entry\n"

    def test_an_h1_after_the_section_survives(self) -> None:
        doc = (
            "# Top\n\n## Session History\n\nold entry\n\n"
            "# Another Top Level\n\nbody that must survive\n"
        )
        result = checkpoint.replace_session_history(doc, self.HISTORY)
        self.assertIn("# Another Top Level", result)
        self.assertIn("body that must survive", result)
        self.assertNotIn("old entry", result)

    def test_a_thematic_break_after_the_section_survives(self) -> None:
        doc = "## Session History\n\nold\n\n---\n\n## Later\n\nkeep me\n"
        result = checkpoint.replace_session_history(doc, self.HISTORY)
        self.assertIn("## Later", result)
        self.assertIn("keep me", result)

    def test_a_following_h2_still_survives(self) -> None:
        doc = "## Session History\n\nold\n\n## Current Project\n\nkeep me\n"
        result = checkpoint.replace_session_history(doc, self.HISTORY)
        self.assertIn("## Current Project", result)
        self.assertIn("keep me", result)

    def test_an_inline_mention_is_not_a_section_start(self) -> None:
        doc = (
            "# Doc\n\n## Ops\n\n- `## Session History` is overwritten\n\n## End\n\nx\n"
        )
        result = checkpoint.replace_session_history(doc, self.HISTORY)
        self.assertIn("is overwritten", result)
        self.assertIn("## End", result)

    def test_a_header_inside_a_code_fence_is_not_a_section_start(self) -> None:
        """
        The skill's own documentation shows the section it writes inside a
        ```markdown fence. Matching that line started the section there, and
        everything up to the next heading -- including the fence's closing
        backticks -- was replaced, leaving the rest of the document inside an
        unterminated code block.
        """
        doc = (
            "# Doc\n\n## How it works\n\n"
            "```markdown\n## Session History\n\n### 2026-01-01\n\n- example\n```\n\n"
            "## Session History\n\nold entry\n\n## Real Section\n\nkeep me\n"
        )
        result = checkpoint.replace_session_history(doc, self.HISTORY)
        self.assertIn("- example", result, "the fenced example was destroyed")
        self.assertEqual(2, result.count("```"), "the fence is no longer balanced")
        self.assertIn("## Real Section", result)
        self.assertIn("keep me", result)
        self.assertNotIn("old entry", result)

    def test_a_tilde_fence_is_honoured_too(self) -> None:
        doc = (
            "# Doc\n\n~~~\n## Session History\n\n- example\n~~~\n\n## End\n\nkeep me\n"
        )
        result = checkpoint.replace_session_history(doc, self.HISTORY)
        self.assertIn("- example", result)
        self.assertIn("keep me", result)

    def test_a_heading_inside_a_fence_does_not_end_the_section(self) -> None:
        """The mirror image: a fenced `## ...` must not truncate the replacement."""
        doc = (
            "## Session History\n\nold\n\n```\n## Not A Heading\n```\n\n"
            "## Real\n\nkeep me\n"
        )
        result = checkpoint.replace_session_history(doc, self.HISTORY)
        self.assertNotIn("## Not A Heading", result, "fenced text survived as content")
        self.assertIn("## Real", result)
        self.assertIn("keep me", result)

    def test_a_header_on_the_last_line_without_a_newline_is_matched(self) -> None:
        """
        The pattern required a newline after the header, so a file ending exactly
        at the heading did not match and a second section was appended.
        """
        doc = "# Doc\n\n## Session History"
        result = checkpoint.replace_session_history(doc, self.HISTORY)
        self.assertEqual(
            1,
            result.count("## Session History"),
            "a second history section was appended below the first",
        )

    def test_a_file_with_no_trailing_newline_is_still_replaced_in_place(self) -> None:
        doc = "# Doc\n\n## Session History\n\nold entry"
        result = checkpoint.replace_session_history(doc, self.HISTORY)
        self.assertEqual(1, result.count("## Session History"))
        self.assertNotIn("old entry", result)

    def test_applying_twice_is_stable(self) -> None:
        doc = "# Top\n\n## Session History\n\nold\n\n# H1\n\nbody\n"
        once = checkpoint.replace_session_history(doc, self.HISTORY)
        twice = checkpoint.replace_session_history(once, self.HISTORY)
        self.assertEqual(once, twice)


class LogParsingTests(unittest.TestCase):
    """C2, C4, C7 — one bad line must not abort the run."""

    def write_log(self, lines: list[str]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        log = Path(tmp.name) / "cli-tools.jsonl"
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return log

    def entry(self, timestamp: str, tool: str = "antigravity") -> str:
        return json.dumps(
            {"timestamp": timestamp, "tool": tool, "prompt": "p", "success": True}
        )

    def test_a_malformed_timestamp_is_skipped_not_fatal(self) -> None:
        log = self.write_log(
            [
                self.entry("not-a-date"),
                self.entry("2026-09-25T10:00:00+00:00"),
            ]
        )
        entries = checkpoint.parse_logs(since="2026-09-01", log_file=log)
        self.assertEqual(1, len(entries), "the good entry must survive the bad one")

    def test_a_missing_timestamp_is_skipped_not_fatal(self) -> None:
        log = self.write_log(
            [
                json.dumps({"tool": "antigravity"}),
                self.entry("2026-09-25T10:00:00+00:00"),
            ]
        )
        self.assertEqual(
            1, len(checkpoint.parse_logs(since="2026-09-01", log_file=log))
        )

    def test_a_bad_timestamp_is_skipped_even_without_since(self) -> None:
        """
        Found by running the script for real: without --since no timestamp check
        ran, the entry reached local_date, and its first ten characters became a
        heading — "### broken-tim" in the history.
        """
        log = self.write_log(
            [self.entry("broken-timestamp"), self.entry("2026-09-25T10:00:00+00:00")]
        )
        entries = checkpoint.parse_logs(log_file=log)
        self.assertEqual(1, len(entries))
        dates = set(checkpoint.summarize_entries(entries))
        for date in dates:
            self.assertRegex(
                date, r"^\d{4}-\d{2}-\d{2}$", f"{date!r} is not a date heading"
            )

    def test_since_is_interpreted_in_local_time(self) -> None:
        """
        C4 — grouping is by local date, so the filter must be too, or an entry
        that belongs to the requested local day is dropped.
        """
        local_now = datetime.now().astimezone()
        target_day = local_now.date().isoformat()
        # Start of the local day, expressed in a deliberately different offset.
        start_of_local_day = datetime(
            local_now.year,
            local_now.month,
            local_now.day,
            1,
            0,
            tzinfo=local_now.tzinfo,
        )
        shifted = start_of_local_day.astimezone(timezone(timedelta(hours=-11)))
        log = self.write_log([self.entry(shifted.isoformat())])
        entries = checkpoint.parse_logs(since=target_day, log_file=log)
        self.assertEqual(
            1,
            len(entries),
            "an entry on the requested local day was filtered out by a UTC comparison",
        )

    def test_entries_from_other_tools_are_kept(self) -> None:
        """C7 — the summary pre-seeded only agy and dropped everything else."""
        log = self.write_log(
            [
                self.entry("2026-09-25T10:00:00+00:00", tool="antigravity"),
                self.entry("2026-09-25T11:00:00+00:00", tool="claude"),
            ]
        )
        entries = checkpoint.parse_logs(log_file=log)
        summary = checkpoint.summarize_entries(entries)
        tools = {tool for by_tool in summary.values() for tool in by_tool}
        self.assertIn("claude", tools, "a non-agy tool's entries vanished")


class SinceValidationTests(unittest.TestCase):
    """C3 — a bad --since must produce a message, not a traceback."""

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(REPO),
        )

    def test_a_malformed_since_is_rejected_cleanly(self) -> None:
        result = self.run_script("--since", "24/09/2026")
        self.assertNotEqual(0, result.returncode)
        combined = result.stdout + result.stderr
        self.assertNotIn("Traceback", combined, "argument errors must not crash")
        self.assertIn("since", combined.lower())


class AtomicWriteTests(unittest.TestCase):
    """C5 — a rewrite must not be able to leave a truncated file."""

    def test_write_is_atomic_and_keeps_a_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "CLAUDE.md"
            original = "# Doc\n\n## Session History\n\nold\n"
            target.write_text(original, encoding="utf-8")

            checkpoint.write_text_atomic(target, "# Doc\n\nnew\n")

            self.assertEqual("# Doc\n\nnew\n", target.read_text(encoding="utf-8"))
            backup = target.with_suffix(target.suffix + ".bak")
            self.assertTrue(backup.is_file(), "no backup was kept")
            self.assertEqual(original, backup.read_text(encoding="utf-8"))

    def test_no_temp_file_is_left_behind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "CLAUDE.md"
            target.write_text("x\n", encoding="utf-8")
            checkpoint.write_text_atomic(target, "y\n")
            leftovers = [
                p.name
                for p in Path(tmp).iterdir()
                if p.name not in {"CLAUDE.md", "CLAUDE.md.bak"}
            ]
            self.assertEqual([], leftovers)

    def test_update_context_file_goes_through_the_atomic_path(self) -> None:
        """
        Testing the helper in isolation did not catch reverting its caller: the
        two tests above still passed when update_context_file went back to a
        plain write_text. The backup is the observable proof it was used.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "CLAUDE.md"
            original = "# Doc\n\n## Session History\n\nold\n\n## Keep\n\nkeep me\n"
            target.write_text(original, encoding="utf-8")

            wrote = checkpoint.update_context_file(
                target, "## Session History\n\n### 2026-09-25\n\n- new\n"
            )

            self.assertTrue(wrote)
            backup = target.with_suffix(target.suffix + ".bak")
            self.assertTrue(
                backup.is_file(),
                "update_context_file did not use write_text_atomic — a crash "
                "mid-write would truncate the file",
            )
            self.assertEqual(original, backup.read_text(encoding="utf-8"))
            updated = target.read_text(encoding="utf-8")
            self.assertIn("- new", updated)
            self.assertIn("keep me", updated)
            self.assertNotIn("old", updated)

    def test_an_unchanged_file_is_not_rewritten(self) -> None:
        """No backup churn when there is nothing to change."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "CLAUDE.md"
            history = "## Session History\n\n### 2026-09-25\n\n- same\n"
            target.write_text(f"# Doc\n\n{history}", encoding="utf-8")
            checkpoint.update_context_file(target, history)
            self.assertFalse(
                target.with_suffix(target.suffix + ".bak").exists(),
                "an identical rewrite should not touch the file at all",
            )


class GitRangeTests(unittest.TestCase):
    """C6 — a young repository must not silently report 'no changes'."""

    def test_range_falls_back_on_a_repository_with_few_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", "."], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
            (repo / "a.txt").write_text("1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "one"], cwd=repo, check=True)

            spec_ = f"{checkpoint.DEFAULT_HISTORY_DEPTH}"
            self.assertTrue(
                spec_.isdigit(), "depth must be a number, not a hard-coded ref"
            )

            rev_range = checkpoint.resolve_commit_range(cwd=repo)
            self.assertIsNotNone(
                rev_range, "a single-commit repository produced no usable range"
            )
            result = subprocess.run(
                ["git", "log", "--oneline", *rev_range],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("one", result.stdout)


class FileStatsRangeTests(unittest.TestCase):
    """
    C6 again, in the function the first repair missed.

    `get_file_changes` was switched to `resolve_commit_range`; `get_file_stats`
    was not, and kept `git diff --numstat HEAD~10 HEAD`. On a repository with
    fewer than eleven commits that command fails, `run_git_command` returns
    None, and the checkpoint reports no line counts at all — the same
    "no changes detected" that C6 was supposed to close. DESIGN.md recorded the
    defect as closed while this call site still carried it.
    """

    def _young_repo(self, commits: int) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)
        subprocess.run(["git", "init", "-q", "."], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
        for n in range(commits):
            (repo / f"f{n}.txt").write_text(f"line {n}\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", f"c{n}"], cwd=repo, check=True)
        return repo

    def _stats_in(self, repo: Path) -> dict:
        original = checkpoint.PROJECT_ROOT
        checkpoint.PROJECT_ROOT = repo
        try:
            return checkpoint.get_file_stats()
        finally:
            checkpoint.PROJECT_ROOT = original

    def test_line_counts_are_reported_on_a_two_commit_repository(self) -> None:
        stats = self._stats_in(self._young_repo(2))
        self.assertNotEqual(
            {},
            stats,
            "get_file_stats still hard-codes a ref deeper than the history",
        )
        self.assertIn("f1.txt", stats)

    def test_line_counts_are_reported_on_a_single_commit_repository(self) -> None:
        stats = self._stats_in(self._young_repo(1))
        self.assertIn("f0.txt", stats, "the root commit's own changes are invisible")

    def test_the_two_walkers_agree_on_which_files_changed(self) -> None:
        """
        A checkpoint lists a file from one function and its line counts from the
        other. If they cover different ranges, a file appears with no numbers.
        """
        repo = self._young_repo(3)
        original = checkpoint.PROJECT_ROOT
        checkpoint.PROJECT_ROOT = repo
        try:
            changes = checkpoint.get_file_changes()
            stats = checkpoint.get_file_stats()
        finally:
            checkpoint.PROJECT_ROOT = original
        listed = set(changes["created"]) | set(changes["modified"])
        self.assertTrue(listed, "no files listed at all")
        self.assertEqual(
            set(),
            listed - set(stats),
            "a file is listed as changed but has no line counts",
        )


class DocumentedFormatTests(unittest.TestCase):
    """
    The skill's documentation must show what the script actually writes.

    It showed `**agy조사:**` and `✓` in the Session History block while the
    script writes `**agy:**` and `[OK]` / `[FAILED]` (labels were moved to
    English per .claude/rules/language.md), and it said both context files get
    `## Session History` while AGENTS.md gets `## Consultation History`. A reader
    following the document looks for a section that is not there, and an editor
    "fixing" the script to match the document reintroduces the bug.

    Asserted against generated output rather than against a copy of the format,
    so the document cannot drift from the code in either direction.
    """

    SKILL = REPO / ".claude" / "skills" / "checkpointing" / "SKILL.md"

    def rendered(self) -> str:
        by_date = {
            "2026-01-26": {
                "antigravity": [
                    {"prompt": "MCP vs CLI comparison", "success": True},
                    {"prompt": "a call that failed", "success": False},
                ]
            }
        }
        return checkpoint.generate_session_history(by_date)

    def test_the_tool_label_matches(self) -> None:
        self.assertIn("**agy:**", self.rendered())
        self.assertIn("**agy:**", self.SKILL.read_text(encoding="utf-8"))

    def test_the_status_markers_match(self) -> None:
        rendered = self.rendered()
        self.assertIn("- [OK] ", rendered)
        self.assertIn("- [FAILED] ", rendered)
        doc = self.SKILL.read_text(encoding="utf-8")
        self.assertIn("[OK]", doc)
        self.assertIn("[FAILED]", doc, "the failure marker is undocumented")

    def test_the_stale_korean_label_is_gone(self) -> None:
        self.assertNotIn("agy조사:", self.SKILL.read_text(encoding="utf-8"))

    def test_both_context_headings_are_documented(self) -> None:
        doc = self.SKILL.read_text(encoding="utf-8")
        for target in checkpoint.CONTEXT_FILES.values():
            header = target["header"]
            assert isinstance(header, str)
            self.assertIn(header, doc, f"the document does not mention {header}")

    def test_the_document_says_which_file_gets_which_heading(self) -> None:
        doc = " ".join(self.SKILL.read_text(encoding="utf-8").split())
        self.assertIn("AGENTS.md", doc)

        def offsets(needle: str) -> list[int]:
            found, start = [], 0
            while (at := doc.find(needle, start)) != -1:
                found.append(at)
                start = at + 1
            return found

        # Any mention of the heading near any mention of the file will do; the
        # first of each are far apart because the ASCII diagram splits the
        # heading across box-drawing characters.
        pairs = [
            abs(a - b)
            for a in offsets("## Consultation History")
            for b in offsets("AGENTS.md")
        ]
        self.assertTrue(pairs, "one of the two is not mentioned at all")
        self.assertLess(
            min(pairs),
            200,
            "the second heading is mentioned but not tied to the file it belongs to",
        )


class ContextTargetTests(unittest.TestCase):
    """The AGENTS.md file ends with a differently-named history section."""

    def test_agents_file_header_is_configurable_per_target(self) -> None:
        agents = REPO / ".agents" / "rules" / "AGENTS.md"
        if not agents.is_file():
            self.skipTest("no AGENTS.md in this checkout")
        text = agents.read_text(encoding="utf-8")
        header = checkpoint.CONTEXT_FILES["antigravity"]["header"]
        self.assertIn(
            header,
            text,
            "checkpoint.py would append a second, parallel history section instead "
            "of updating the one that is already there",
        )


if __name__ == "__main__":
    unittest.main()
