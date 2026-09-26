"""
Regression tests for post-implementation-review.py.

Written before the fixes, per `.claude/rules/testing.md` principle 1. Scenario
IDs match the notes in `.claude/docs/DESIGN.md`:

  R1  state lived at one hard-coded /tmp path shared by every project, so
      counters accumulated across unrelated repositories
  R2  the same path was shared by every session, so once the suggestion fired
      the hook was mute forever — no SessionStart hook existed to clear it
  R3  a world-writable, predictable /tmp path can be pre-created as a symlink
      pointing anywhere the user can write
  R4  the source-file test was a hard-coded list of seven extensions, so an
      implementation in any other language was invisible
  R5  comment stripping assumed `#`, so `//`-commented languages counted
      comments as code
  R6  state files must not accumulate without bound
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
HOOK = REPO / ".claude" / "hooks" / "post-implementation-review.py"

spec = importlib.util.spec_from_file_location("post_implementation_review", HOOK)
assert spec and spec.loader
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def payload(file_path: str, content: str, session: str = "s1") -> str:
    return json.dumps(
        {
            "hook_event_name": "PostToolUse",
            "session_id": session,
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content},
        }
    )


def run_hook(body: str, project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=body,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(project),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
    )


def make_project(tmp: str) -> Path:
    project = Path(tmp)
    (project / ".claude" / "logs").mkdir(parents=True)
    return project


def write_source(project: Path, name: str, lines: int = 60) -> tuple[str, str]:
    body = "\n".join(f"value_{i} = {i}" for i in range(lines))
    path = project / name
    path.write_text(body, encoding="utf-8")
    return str(path), body


def suggestions(result: subprocess.CompletedProcess[str]) -> bool:
    return "Code Review Suggestion" in result.stdout


class StateLocationTests(unittest.TestCase):
    """R1, R3 — state belongs to the project, not to a shared /tmp path."""

    def test_no_hard_coded_tmp_path_in_the_source(self) -> None:
        """
        Parsed with ast rather than grepped, so the docstring explaining why the
        old path was wrong does not trip the test — the same false positive a
        substring check produced twice before.
        """
        import ast

        tree = ast.parse(HOOK.read_text(encoding="utf-8"))
        docstrings = {
            ast.get_docstring(node, clean=False)
            for node in ast.walk(tree)
            if isinstance(
                node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )
        }
        offenders = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value not in docstrings
            and node.value.startswith(("/tmp", "/var/tmp"))
        ]
        self.assertEqual(
            [],
            offenders,
            "a predictable shared temp path is both cross-project state and a "
            "symlink target anyone on the machine can pre-create",
        )

    def test_state_is_written_inside_the_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(tmp)
            path, content = write_source(project, "a.py")
            run_hook(payload(path, content), project)
            written = list((project / ".claude" / "logs").rglob("*"))
            self.assertTrue(
                [p for p in written if p.is_file()],
                "the hook kept no state under the project",
            )

    def test_two_projects_do_not_share_counters(self) -> None:
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            first, second = make_project(one), make_project(two)
            # Two files in the first project: below the 3-file threshold.
            for name in ("a.py", "b.py"):
                path, content = write_source(first, name, lines=5)
                run_hook(payload(path, content), first)
            # A single file in the second must not inherit the first's count.
            path, content = write_source(second, "c.py", lines=5)
            result = run_hook(payload(path, content), second)
            self.assertFalse(
                suggestions(result),
                "the second project inherited the first project's file count",
            )


class SessionScopeTests(unittest.TestCase):
    """R2 — a new session starts fresh; within one session it fires once."""

    def test_the_suggestion_fires_once_within_a_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(tmp)
            fired = 0
            for name in ("a.py", "b.py", "c.py", "d.py", "e.py"):
                path, content = write_source(project, name, lines=5)
                if suggestions(run_hook(payload(path, content, "s1"), project)):
                    fired += 1
            self.assertEqual(1, fired, "the suggestion should not repeat in a session")

    def test_a_new_session_can_suggest_again(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(tmp)
            for name in ("a.py", "b.py", "c.py"):
                path, content = write_source(project, name, lines=5)
                run_hook(payload(path, content, "s1"), project)

            fired = False
            for name in ("d.py", "e.py", "f.py"):
                path, content = write_source(project, name, lines=5)
                if suggestions(run_hook(payload(path, content, "s2"), project)):
                    fired = True
            self.assertTrue(
                fired,
                "a fresh session inherited the previous session's 'already suggested' "
                "flag and was mute — the original bug made this permanent",
            )


class SourceDetectionTests(unittest.TestCase):
    """R4 — which files count must not be a list of seven languages."""

    def test_an_unlisted_language_counts_as_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(tmp)
            fired = False
            for name in ("a.kt", "b.bb", "c.sql"):
                path, content = write_source(project, name, lines=5)
                if suggestions(run_hook(payload(path, content, "s1"), project)):
                    fired = True
            self.assertTrue(
                fired,
                "files in languages the hook was not taught about were invisible",
            )

    def test_documents_and_config_do_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(tmp)
            fired = False
            for name in ("README.md", "data.json", "uv.lock", "notes.txt"):
                path, content = write_source(project, name, lines=5)
                if suggestions(run_hook(payload(path, content, "s1"), project)):
                    fired = True
            self.assertFalse(
                fired, "editing documents or config is not an implementation"
            )

    def test_is_source_file_is_exclusion_based(self) -> None:
        self.assertTrue(hook.is_source_file("app/main.kt"))
        self.assertTrue(hook.is_source_file("recipes/foo_1.0.bb"))
        self.assertFalse(hook.is_source_file("docs/README.md"))
        self.assertFalse(hook.is_source_file("uv.lock"))
        self.assertFalse(hook.is_source_file("package-lock.json"))


class LineCountingTests(unittest.TestCase):
    """R5 — comment stripping must not assume one comment syntax."""

    def test_slash_comments_are_not_counted_as_code(self) -> None:
        content = "// a comment\n// another\nint x = 1;\n"
        self.assertEqual(1, hook.count_lines(content))

    def test_hash_comments_are_not_counted_as_code(self) -> None:
        self.assertEqual(1, hook.count_lines("# note\nx = 1\n"))

    def test_blank_lines_are_not_counted(self) -> None:
        self.assertEqual(2, hook.count_lines("x = 1\n\n\ny = 2\n"))


class HousekeepingTests(unittest.TestCase):
    """R6 — per-session files must not accumulate for ever."""

    def test_stale_state_files_are_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(tmp)
            state_dir = hook.state_dir(project)
            state_dir.mkdir(parents=True, exist_ok=True)
            stale = state_dir / hook.state_filename("ancient")
            stale.write_text("{}", encoding="utf-8")
            old = time.time() - (hook.STATE_RETENTION_DAYS + 2) * 86400
            os.utime(stale, (old, old))

            path, content = write_source(project, "a.py", lines=5)
            run_hook(payload(path, content, "fresh"), project)

            self.assertFalse(stale.exists(), "stale session state was never cleaned up")

    def test_current_state_survives_housekeeping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(tmp)
            path, content = write_source(project, "a.py", lines=5)
            run_hook(payload(path, content, "keep"), project)
            expected = hook.state_dir(project) / hook.state_filename("keep")
            self.assertTrue(expected.is_file(), "this session's own state was removed")


class SymlinkRefusalTests(unittest.TestCase):
    """
    R3, actually exercised.

    The hook refuses to write through a symlink, and both its own docstring and
    DESIGN.md record that as a closed defect with regression tests attached.
    Measured by an independent review: deleting the check
    (`if path.is_symlink(): return` -> `if False: return`) left all 312 tests
    green. The claim was true of the code and false of the tests.
    """

    def test_state_is_not_written_through_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            victim = root / "victim.json"
            victim.write_text("untouched\n", encoding="utf-8")
            directory = hook.state_dir(root)
            directory.mkdir(parents=True, exist_ok=True)
            planted = directory / hook.state_filename("s1")
            planted.symlink_to(victim)

            hook.save_state(planted, {"files_changed": ["a.py"], "total_lines": 10})

            self.assertEqual(
                "untouched\n",
                victim.read_text(encoding="utf-8"),
                "the hook wrote through a planted symlink",
            )

    def test_a_regular_path_is_still_written(self) -> None:
        """The refusal must not be achieved by never writing at all."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            hook.save_state(path, {"files_changed": ["a.py"], "total_lines": 10})
            self.assertTrue(path.is_file(), "no state was written")
            self.assertEqual(["a.py"], json.loads(path.read_text())["files_changed"])


class LineThresholdTests(unittest.TestCase):
    """
    The second trigger. The file-count threshold had tests; the line threshold
    had none, so raising MIN_LINES_FOR_REVIEW to 100000 left the suite green.
    """

    # Deliberate literals, not `hook.MIN_LINES_FOR_REVIEW`. Deriving the input
    # from the constant makes the test adapt to any retuning — measured: with
    # `total_lines: hook.MIN_LINES_FOR_REVIEW`, raising the constant to 100000
    # kept the suite green, which is the tautology this class exists to avoid.
    # These two numbers bracket the shipped value (100) and are a ratchet: a
    # deliberate retuning outside the bracket must fail here and be argued for.
    CLEARLY_LARGE = 200
    CLEARLY_SMALL = 20

    def test_the_line_threshold_fires_on_one_big_file(self) -> None:
        should, reason = hook.should_suggest_review(
            {
                "files_changed": ["only.py"],
                "total_lines": self.CLEARLY_LARGE,
                "review_suggested": False,
            }
        )
        self.assertTrue(
            should,
            f"{self.CLEARLY_LARGE} lines in a single file did not trigger a "
            "review suggestion, so only the file-count trigger works",
        )
        self.assertIn("lines", reason)

    def test_a_small_single_file_stays_quiet(self) -> None:
        should, _ = hook.should_suggest_review(
            {
                "files_changed": ["only.py"],
                "total_lines": self.CLEARLY_SMALL,
                "review_suggested": False,
            }
        )
        self.assertFalse(
            should,
            f"{self.CLEARLY_SMALL} lines triggered a review — the threshold is "
            "ignored, so the hook fires on every edit",
        )


class RobustnessTests(unittest.TestCase):
    """The hook is advisory: nothing it meets may break the session."""

    def test_an_unwritable_state_directory_does_not_fail_the_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(tmp)
            path, content = write_source(project, "a.py", lines=5)
            logs = project / ".claude" / "logs"
            logs.chmod(0o500)
            try:
                result = run_hook(payload(path, content), project)
                self.assertEqual(0, result.returncode)
            finally:
                logs.chmod(0o700)

    def test_degenerate_payloads_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(tmp)
            for body in ("", "not json", "[]", "{}", '{"tool_name":"Bash"}'):
                with self.subTest(payload=body or "<empty>"):
                    self.assertEqual(0, run_hook(body, project).returncode)

    def test_a_missing_session_id_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(tmp)
            path, content = write_source(project, "a.py", lines=5)
            body = json.dumps(
                {
                    "tool_name": "Write",
                    "tool_input": {"file_path": path, "content": content},
                }
            )
            self.assertEqual(0, run_hook(body, project).returncode)


if __name__ == "__main__":
    unittest.main()
