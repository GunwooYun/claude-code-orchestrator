"""
Fixes from the first field report (Immich fork, 2026-10-02). Three real runs
gave INVALID, INCOMPLETE, INCOMPLETE, and none of the three was the reviewer's
fault:

  A  a project hook's dotfile under .claude/ changed mid-run → INVALID, with no
     word on which file changed
  B  a file ADDED by the branch is wholly in the diff, but counted as "never
     read" unless opened by path → doc-heavy branches were always INCOMPLETE
  D  the 3,000-line cap counted docs and evidence files (4,104 lines, 1,243 of
     them code) → the range had to be split by hand

Uses the fake `claude` and the sandbox from test_isolated_review.py.
"""

from __future__ import annotations

import json

from test_isolated_review import (
    EXIT_COMPLETE,
    EXIT_INCOMPLETE,
    EXIT_INVALID,
    EXIT_REFUSED,
    IsolatedReviewCase,
    load_script,
)
from test_isolated_review_hardening import load_field_report

RR = load_script()
CONFIG = ".claude/isolated-review.json"


def header(stdout: str) -> str:
    return stdout.split("\n---\n", 1)[0]


class SnapshotTests(IsolatedReviewCase):
    def test_a_a_hooks_state_dotfile_written_mid_run_is_not_a_tree_change(
        self,
    ) -> None:
        box = self.sandbox()
        # As in the real project: the hook's state file is not tracked.
        with (box.root / ".git/info/exclude").open("a") as handle:
            handle.write(".claude/hooks/.blocked-reviews\n")
        result = box.run(scenario="touch_hook_state")
        self.assertEqual(EXIT_COMPLETE, result.returncode, result.stdout)

    def test_a_invalid_names_the_file_that_changed(self) -> None:
        result = self.sandbox().run(scenario="modify_ignored_claude_file")
        self.assertEqual(EXIT_INVALID, result.returncode, result.stdout)
        self.assertIn(".claude/settings.local.json", header(result.stdout))


class AddedFileTests(IsolatedReviewCase):
    def test_b_an_added_file_delivered_inline_counts_as_read(self) -> None:
        box = self.sandbox(changed={"docs/new.md": "new\n", "src/work.py": "w = 1\n"})
        result = box.run(
            scenario="coverage_no_read", files=["docs/new.md", "src/work.py"]
        )
        self.assertEqual(EXIT_COMPLETE, result.returncode, result.stdout)

    def test_b_a_modified_file_still_needs_a_read(self) -> None:
        box = self.sandbox(
            base_files={"src/old.py": "o = 0\n"},
            changed={"src/old.py": "o = 1\n", "src/work.py": "w = 1\n"},
        )
        result = box.run(
            scenario="coverage_no_read", files=["src/old.py", "src/work.py"]
        )
        self.assertEqual(EXIT_INCOMPLETE, result.returncode, result.stdout)
        self.assertIn("coverage: src/old.py listed but never read", result.stdout)

    def big(self) -> dict[str, str]:
        return {"docs/big.md": "x\n" * (RR.INLINE_MAX_LINES + 50)}

    def test_b_an_added_file_in_a_diff_file_read_in_full_counts_as_read(self) -> None:
        box = self.sandbox(changed=self.big())
        result = box.run(scenario="diff_only_full")
        self.assertIn("diff file", result.stdout)
        self.assertEqual(EXIT_COMPLETE, result.returncode, result.stdout)

    def test_b_a_diff_file_read_only_in_part_does_not_count(self) -> None:
        box = self.sandbox(changed=self.big())
        result = box.run(scenario="diff_only_partial")
        self.assertEqual(EXIT_INCOMPLETE, result.returncode, result.stdout)


class CapExclusionTests(IsolatedReviewCase):
    def config(self, *patterns: str) -> str:
        return json.dumps({"cap_exclude": list(patterns)})

    def over_cap(self) -> dict[str, str]:
        return {
            "dev-docs/evidence.md": "x\n" * (RR.HARD_CAP_LINES + 100),
            "src/work.py": "w = 1\n",
        }

    def test_d_excluded_paths_do_not_count_toward_the_cap(self) -> None:
        box = self.sandbox(
            base_files={CONFIG: self.config("dev-docs/**")}, changed=self.over_cap()
        )
        result = box.run()
        self.assertNotEqual(EXIT_REFUSED, result.returncode, result.stderr)
        self.assertIn("dev-docs/**", header(result.stdout))

    def test_d_without_the_config_the_same_range_is_refused(self) -> None:
        result = self.sandbox(changed=self.over_cap()).run()
        self.assertEqual(EXIT_REFUSED, result.returncode)

    def test_d_excluded_files_are_still_reviewed(self) -> None:
        # The cap is about size, not scope: a file the config excludes must
        # still be listed in Coverage like any other.
        box = self.sandbox(
            base_files={CONFIG: self.config("dev-docs/**")}, changed=self.over_cap()
        )
        result = box.run(
            scenario="coverage_missing", files=["dev-docs/evidence.md", "src/work.py"]
        )
        self.assertIn("coverage: dev-docs/evidence.md not listed", result.stdout)

    def test_d_a_branch_that_changes_the_exclusions_is_not_complete(self) -> None:
        # The change under review must not decide how much of itself counts.
        box = self.sandbox(
            base_files={CONFIG: self.config()},
            changed={CONFIG: self.config("src/**"), "src/work.py": "w = 1\n"},
        )
        result = box.run()
        self.assertEqual(EXIT_INCOMPLETE, result.returncode, result.stdout)
        self.assertIn("cap_exclude", header(result.stdout))

    def test_d_an_unreadable_config_is_refused_not_ignored(self) -> None:
        box = self.sandbox(base_files={CONFIG: "{not json"})
        result = box.run()
        self.assertEqual(EXIT_REFUSED, result.returncode)
        self.assertIn("isolated-review.json", result.stderr)


class DriftTests(IsolatedReviewCase):
    def test_new_reasons_have_a_field_report_shape(self) -> None:
        box = self.sandbox(
            base_files={CONFIG: json.dumps({"cap_exclude": []})},
            changed={
                CONFIG: json.dumps({"cap_exclude": ["x/**"]}),
                "src/work.py": "w\n",
            },
        )
        reasons = [
            line[len("- reason: ") :]
            for line in box.run().stdout.splitlines()
            if line.startswith("- reason: ")
        ]
        box2 = self.sandbox()
        reasons += [
            line[len("- reason: ") :]
            for line in box2.run(
                scenario="modify_ignored_claude_file"
            ).stdout.splitlines()
            if line.startswith("- reason: ")
        ]
        self.assertGreaterEqual(len(reasons), 2)
        field_report = load_field_report()
        for reason in reasons:
            with self.subTest(reason=reason):
                self.assertNotEqual(
                    field_report.HIDDEN, field_report.hide_reason(reason, False)
                )
