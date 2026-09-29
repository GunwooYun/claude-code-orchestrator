"""
End-to-end effect tests: every hook must DO something on a payload that should
trigger it, and nothing on one that should not.

These exist because the contract tests in `test_hook_contract.py` could not
detect a dead hook. They assert tolerance — exit 0, valid-or-empty stdout,
survives junk — and empty stdout is a legal contract answer, so a hook that
reads its payload and returns immediately satisfies every one of them.
Measured: inserting `sys.exit(0)` after `json.load(sys.stdin)` in
`agent-router.py` left all 221 tests green. The template's most expensive defect
so far (`lint-on-save.py` read an environment variable Claude Code never sets
and was a permanent no-op) is exactly that shape.

So each hook here gets a pair:

  TRIGGER  a payload the hook is supposed to react to, and an assertion on the
           observable effect — a marker in stdout JSON, text on stderr, or a
           file on disk
  SILENT   a payload it must ignore, asserted to produce no effect

The pair matters. A trigger case alone is satisfied by a hook that fires on
everything; a silence case alone is satisfied by a hook that never fires.

`test_every_hook_has_both` makes the coverage structural: a hook added to
`.claude/hooks/` with no entry here fails, instead of being silently untested.

Side effects are redirected rather than mocked, so the real file is exercised:
hooks honouring `CLAUDE_PROJECT_DIR` get a temporary project, and
`log-cli-tools.py`, whose log path is relative to its own `__file__`, is copied
into a temporary tree.

Measured, 2026-09-26 (reproduce by editing a hook and running both modules):

    mutation                                   test_hook_contract  this module
    no-op main(), each of the 8 hooks          8/8 pass            8/8 fail
    gate fires always (5 hooks with a gate)    not run             5/5 fail
    is_source_file -> True                     not run             fail
    agy binary check removed                   not run             fail
    os.path.isfile check removed               not run             fail

Three of the silence cases exist BECAUSE of that second run: the first versions
returned early (a skip list, an explicit success flag, a command with no bare
`-p`), so the always-fire mutants passed. Each of those now has a companion case
that reaches the final gate. That is the whole argument for mutating rather than
counting tests — the suite looked complete at 29 and was not.

What this still does not cover: the harness itself. These tests call the hooks
the way settings.json says Claude Code will, but nothing here proves Claude Code
sends that shape, that the matchers route to these files, or that the emitted
additionalContext changes what the model does. Only a real session shows that.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
HOOKS = REPO / ".claude" / "hooks"


def hook_files() -> list[Path]:
    return sorted(p for p in HOOKS.glob("*.py") if not p.name.startswith("_"))


def run(
    hook: Path, payload: dict | str, env: dict[str, str] | None = None, cwd: Path = REPO
) -> subprocess.CompletedProcess[str]:
    body = payload if isinstance(payload, str) else json.dumps(payload)
    environment = dict(os.environ)
    environment.pop("CLAUDE_PROJECT_DIR", None)
    environment.pop("CLAUDE_SESSION_ID", None)
    if env:
        environment.update(env)
    return subprocess.run(
        [sys.executable, str(hook)],
        input=body,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(cwd),
        env=environment,
    )


def context(result: subprocess.CompletedProcess[str]) -> str:
    """The additionalContext a hook emitted, or "" when it stayed silent."""
    out = result.stdout.strip()
    if not out:
        return ""
    parsed = json.loads(out)
    specific = parsed.get("hookSpecificOutput", {})
    return specific.get("additionalContext", "") or parsed.get("systemMessage", "")


# Hooks whose effect is asserted below. Keyed by filename so the structural test
# can compare it against what is on disk.
COVERED = {
    "agent-router.py",
    "suggest-deep-reasoning-before-write.py",
    "suggest-antigravity-research.py",
    "suggest-deep-reasoning-after-plan.py",
    "post-test-analysis.py",
    "log-cli-tools.py",
    "lint-on-save.py",
    "post-implementation-review.py",
    "bash-write-check.py",
}


class CoverageTests(unittest.TestCase):
    def test_every_hook_has_both(self) -> None:
        on_disk = {p.name for p in hook_files()}
        missing = on_disk - COVERED
        self.assertEqual(
            set(),
            missing,
            f"{sorted(missing)} has no trigger/silence pair, so a no-op version "
            "of it would pass the suite",
        )
        stale = COVERED - on_disk
        self.assertEqual(set(), stale, f"{sorted(stale)} is listed but not on disk")


class AgentRouterTests(unittest.TestCase):
    HOOK = HOOKS / "agent-router.py"

    def prompt(self, text: str) -> str:
        return context(
            run(self.HOOK, {"hook_event_name": "UserPromptSubmit", "prompt": text})
        )

    def test_a_debugging_prompt_routes_to_deep_reasoning(self) -> None:
        emitted = self.prompt("Why does the retry logic fail? Please debug it")
        self.assertIn("[Agent Routing]", emitted)
        self.assertIn("deep-reasoning", emitted)

    def test_a_research_prompt_routes_to_antigravity(self) -> None:
        emitted = self.prompt("Please research the newest library options for parsing")
        self.assertIn("[Agent Routing]", emitted)
        self.assertIn("agy", emitted)

    def test_a_plain_edit_request_is_not_routed(self) -> None:
        self.assertEqual(
            "", self.prompt("Please rename the variable foo to bar in that one file")
        )

    def test_a_very_short_prompt_is_not_routed(self) -> None:
        self.assertEqual("", self.prompt("ok"))


class SuggestBeforeWriteTests(unittest.TestCase):
    HOOK = HOOKS / "suggest-deep-reasoning-before-write.py"

    def edit(self, file_path: str, new_string: str = "x = 1\n", **extra: str) -> str:
        return context(
            run(
                self.HOOK,
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Edit",
                    "tool_input": {"file_path": file_path, "new_string": new_string},
                    **extra,
                },
            )
        )

    def test_a_design_path_suggests_a_review(self) -> None:
        emitted = self.edit("/tmp/project/core/schema.py")
        self.assertIn("[Design Review Reminder]", emitted)

    def edit_in_session(self, file_path: str, session: str) -> str:
        project = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, project, True)
        self.project = getattr(self, "project", project)
        return context(
            run(
                self.HOOK,
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": session,
                    "tool_name": "Edit",
                    "tool_input": {"file_path": file_path, "new_string": "x = 1\n"},
                },
                env={"CLAUDE_PROJECT_DIR": self.project},
            )
        )

    def test_the_same_file_is_reminded_once_per_session(self) -> None:
        """
        The first real /feature run got this reminder 9 times in the main session
        after its design review had already run; this repo's own session got it
        on every edit of the same test file. Once per file per session is enough
        for the model to have seen it.
        """
        first = self.edit_in_session("/tmp/project/core/schema.py", "s1")
        second = self.edit_in_session("/tmp/project/core/schema.py", "s1")
        self.assertIn("[Design Review Reminder]", first)
        self.assertEqual("", second, "reminded twice for the same file")

    def test_another_file_or_session_is_still_reminded(self) -> None:
        self.edit_in_session("/tmp/project/core/schema.py", "s1")
        other_file = self.edit_in_session("/tmp/project/core/models.py", "s1")
        other_session = self.edit_in_session("/tmp/project/core/schema.py", "s2")
        self.assertIn("[Design Review Reminder]", other_file)
        self.assertIn("[Design Review Reminder]", other_session)

    def test_a_large_edit_is_not_called_a_new_file(self) -> None:
        emitted = self.edit("/tmp/project/app/handler.py", "y = 2\n" * 120)
        self.assertIn("[Design Review Reminder]", emitted)
        self.assertNotIn("Creating new file", emitted)

    def test_inside_a_subagent_the_same_edit_stays_silent(self) -> None:
        """
        A subagent cannot spawn deep-reasoning, so the reminder is noise there:
        the first interactive /initproject run got it 8 times inside one
        general-purpose subagent. `agent_id` is present only when the hook fires
        inside a subagent (code.claude.com/docs/en/hooks, common input fields).
        """
        emitted = self.edit(
            "/tmp/project/core/schema.py",
            agent_id="a1b2c3",
            agent_type="general-purpose",
        )
        self.assertEqual("", emitted)

    def test_a_main_session_run_with_agent_still_suggests(self) -> None:
        # `--agent` sets agent_type without agent_id; that is still the main
        # thread, which can spawn deep-reasoning.
        emitted = self.edit("/tmp/project/core/schema.py", agent_type="reviewer")
        self.assertIn("[Design Review Reminder]", emitted)

    def test_a_readme_edit_stays_silent(self) -> None:
        self.assertEqual("", self.edit("/tmp/project/README.md"))

    def test_a_trivial_edit_to_a_plain_file_stays_silent(self) -> None:
        self.assertEqual("", self.edit("/tmp/project/utils.py", "count += 1\n"))

    def test_a_long_prose_file_does_not_trigger_a_design_review(self) -> None:
        """
        Behaviour deliberately CHANGED, recorded rather than adjusted silently.

        The size trigger used to fire on any write over 500 characters of any
        kind. The separate-session review observed it firing on its own markdown
        report — prose with no design content — and pointed at this repo's own
        rule in lint-on-save.py: repeating a notice on every save trains people
        to ignore hook output. Documents, data and config now do not trigger the
        size rule; a path that looks like design still does, whatever it holds.
        """
        self.assertEqual(
            "",
            self.edit("/tmp/project/notes/report.md", "prose. " * 400),
            "a long markdown file asked for a design review",
        )

    def test_a_long_new_source_file_still_triggers(self) -> None:
        """The narrowing must not silence the case the hook exists for."""
        emitted = self.edit(
            "/tmp/project/service.py", "def handler():\n    pass\n" * 60
        )
        self.assertIn("[Design Review Reminder]", emitted)

    def test_a_design_path_triggers_even_for_a_document(self) -> None:
        """DESIGN.md is prose, and is exactly what this hook wants seen."""
        emitted = self.edit("/tmp/project/docs/DESIGN.md", "x\n")
        self.assertIn("[Design Review Reminder]", emitted)


class SuggestAntigravityTests(unittest.TestCase):
    HOOK = HOOKS / "suggest-antigravity-research.py"

    def search(self, query: str) -> str:
        return context(
            run(
                self.HOOK,
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "WebSearch",
                    "tool_input": {"query": query},
                },
            )
        )

    def test_a_comparison_query_suggests_agy(self) -> None:
        emitted = self.search("best practice for retry back-off in async clients")
        self.assertIn("[Antigravity Research Suggestion]", emitted)

    def test_a_version_lookup_stays_silent(self) -> None:
        """Exercises the early skip list."""
        self.assertEqual("", self.search("httpx version"))

    def test_an_ordinary_short_query_stays_silent(self) -> None:
        """
        Exercises the fall-through, which the skip-list case does not reach.
        Found by mutation: making the final `return False` fire always left the
        suite green while only the early-exit path was covered.
        """
        self.assertEqual("", self.search("set the timeout"))


class SuggestAfterPlanTests(unittest.TestCase):
    HOOK = HOOKS / "suggest-deep-reasoning-after-plan.py"

    def task(self, tool_input: dict, tool_name: str = "Task") -> str:
        return context(
            run(
                self.HOOK,
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "tool_response": {"content": "done"},
                },
            )
        )

    def test_a_finished_plan_task_suggests_a_review(self) -> None:
        emitted = self.task({"subagent_type": "Plan", "prompt": "lay out the steps"})
        self.assertIn("[Plan Review Suggestion]", emitted)

    def test_an_unrelated_subagent_run_stays_silent(self) -> None:
        self.assertEqual(
            "",
            self.task(
                {"subagent_type": "general-purpose", "prompt": "count the log lines"}
            ),
        )

    def test_another_tool_stays_silent(self) -> None:
        self.assertEqual("", self.task({"subagent_type": "Plan"}, tool_name="Bash"))


class PostTestAnalysisTests(unittest.TestCase):
    HOOK = HOOKS / "post-test-analysis.py"

    def bash(self, command: str, stdout: str) -> str:
        return context(
            run(
                self.HOOK,
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Bash",
                    "tool_input": {"command": command},
                    "tool_response": {"stdout": stdout, "stderr": ""},
                },
            )
        )

    def test_a_multi_failure_test_run_suggests_debugging(self) -> None:
        emitted = self.bash(
            "uv run pytest -q",
            "FAILED tests/test_a.py::test_one - AssertionError\n"
            "FAILED tests/test_b.py::test_two - ValueError\n"
            "2 failed, 39 passed in 1.20s\n",
        )
        self.assertIn("[Debug Suggestion]", emitted)

    def test_a_green_run_stays_silent(self) -> None:
        """Exercises the explicit-success path."""
        self.assertEqual("", self.bash("uv run pytest -q", "248 passed in 4.10s\n"))

    def test_a_single_small_failure_is_left_alone(self) -> None:
        """
        Exercises the last gate: the output DOES look failed, but one failure of
        one kind is a mechanical fix and does not need a subagent. Found by
        mutation — without it, a hook that flagged every failed run passed,
        because the other silence cases return earlier.
        """
        self.assertEqual(
            "",
            self.bash(
                "uv run pytest -q",
                "FAILED tests/test_a.py::test_one\n1 failed, 247 passed\n",
            ),
        )

    def test_a_run_with_no_failure_signal_stays_silent(self) -> None:
        """
        Exercises the fall-through: a test command whose output says neither
        pass nor fail. Found by mutation, same as above — without it, a hook
        that flagged every test run passed.
        """
        self.assertEqual("", self.bash("uv run pytest -q", "collected 0 items\n"))

    def test_a_command_that_is_not_a_test_run_stays_silent(self) -> None:
        self.assertEqual("", self.bash("git status", "FAILED FAILED 2 failed\n"))


class LogCliToolsTests(unittest.TestCase):
    """
    Run a COPY of the hook so its log path, which is relative to its own
    `__file__`, lands in a temporary tree instead of this repository's log.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "hooks").mkdir()
        self.hook = self.root / "hooks" / "log-cli-tools.py"
        shutil.copy2(HOOKS / "log-cli-tools.py", self.hook)
        self.log = self.root / "logs" / "cli-tools.jsonl"

    def bash(self, command: str) -> subprocess.CompletedProcess[str]:
        return run(
            self.hook,
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": command},
                "tool_response": {"stdout": "answer\n", "stderr": ""},
            },
            cwd=self.root,
        )

    def test_an_agy_call_is_written_to_the_log(self) -> None:
        result = self.bash('agy -p "one fact" --model gemini-3.7-flash-low')
        self.assertTrue(self.log.is_file(), "nothing was logged")
        entry = json.loads(self.log.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual("antigravity", entry["tool"])
        self.assertEqual("gemini-3.7-flash-low", entry["model"])
        self.assertIn("cli-tools.jsonl", context(result))

    def test_another_binary_with_a_p_flag_is_not_logged(self) -> None:
        """
        `-p` means "prompt" only for agy. Found by mutation: with the quoted
        mention as the only silence case, treating every command as an agy call
        still passed, because that command had no bare `-p` token either. This
        one does, so it exercises the check on the binary itself.
        """
        result = self.bash("mkdir -p .claude/docs/research")
        self.assertFalse(self.log.exists(), "mkdir was logged as an agy call")
        self.assertEqual("", context(result))

    def test_a_command_that_only_mentions_agy_is_not_logged(self) -> None:
        result = self.bash("grep -rn 'agy -p' .claude/rules")
        self.assertFalse(
            self.log.exists(), "a quoted mention was logged as a real call"
        )
        self.assertEqual("", context(result))


class LintOnSaveTests(unittest.TestCase):
    """
    The full chain: stdin payload -> file path -> the project's verify-save
    script -> its output relayed to CLAUDE. A stub script stands in for the
    project's real one, which is what the contract in .claude/scripts/README.md
    promises is possible.

    Corrected 2026-09-28, recorded rather than changed silently: these tests
    used to assert on stderr, and the hook wrote there with exit 0. The hooks
    reference (code.claude.com/docs/en/hooks) says stderr from a hook that exits
    0 "goes to the debug log only ... and Claude never sees it". So every
    assertion passed while the model saw nothing — observed in this repo's own
    session, where Edit-written test files failed `ruff format --check` three
    times and the failure surfaced only at verify-task. The assertions now read
    `additionalContext`, the channel Claude actually receives.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name)
        (self.project / ".claude" / "scripts").mkdir(parents=True)
        self.edited = self.project / "example.py"
        self.edited.write_text("x = 1\n", encoding="utf-8")

    def write_verify_save(self, body: str) -> None:
        script = self.project / ".claude" / "scripts" / "verify-save"
        script.write_text(body, encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)

    def edit(self, file_path: str | None = None) -> subprocess.CompletedProcess[str]:
        return run(
            HOOKS / "lint-on-save.py",
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": file_path or str(self.edited)},
            },
            env={
                "CLAUDE_PROJECT_DIR": str(self.project),
                "CLAUDE_SESSION_ID": "effects-test",
            },
            cwd=self.project,
        )

    def test_a_failing_check_reaches_claude_with_its_output(self) -> None:
        self.write_verify_save('#!/bin/sh\necho "BOOM: bad indent"\nexit 1\n')
        result = self.edit()
        seen = context(result)
        self.assertIn("[lint-on-save]", seen)
        self.assertIn("BOOM: bad indent", seen)
        self.assertEqual(0, result.returncode, "a PostToolUse hook must exit 0")

    def test_the_edited_path_is_passed_to_the_script(self) -> None:
        self.write_verify_save('#!/bin/sh\necho "got:$1"\nexit 1\n')
        self.assertIn(f"got:{self.edited}", context(self.edit()))

    def test_output_on_success_is_relayed_not_swallowed(self) -> None:
        self.write_verify_save('#!/bin/sh\necho "warning: deprecated call"\nexit 0\n')
        seen = context(self.edit())
        self.assertIn("passed with notes", seen)
        self.assertIn("warning: deprecated call", seen)

    def test_a_silent_pass_says_nothing(self) -> None:
        self.write_verify_save("#!/bin/sh\nexit 0\n")
        result = self.edit()
        self.assertEqual("", result.stdout.strip())
        self.assertEqual("", result.stderr.strip())

    def test_a_missing_tier_is_reported_once_per_session(self) -> None:
        first = self.edit()
        self.assertIn("not configured", context(first))
        second = self.edit()
        self.assertEqual(
            "", second.stdout.strip(), "the notice repeated on the next save"
        )

    def test_a_path_that_does_not_exist_is_ignored(self) -> None:
        self.write_verify_save('#!/bin/sh\necho "should not run"\nexit 1\n')
        result = self.edit(file_path=str(self.project / "gone.py"))
        self.assertEqual("", result.stdout.strip())


class BashWriteCheckTests(unittest.TestCase):
    """
    Files written through Bash (`sed -i`, redirection, a python heredoc) skip the
    Edit/Write hooks, so verify-save never saw them. Observed twice on real runs
    in an adopting project, including the gate scripts themselves. The hook marks
    the time before a Bash call and, after it, runs verify-save on files modified
    since — mtime, not git, because the observed files were gitignored.
    """

    HOOK = HOOKS / "bash-write-check.py"

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name)
        scripts = self.project / ".claude" / "scripts"
        scripts.mkdir(parents=True)
        self.gate = scripts / "verify-save"
        self.gate.write_text('#!/bin/sh\necho "FAIL:$1"\nexit 1\n', encoding="utf-8")
        self.gate.chmod(self.gate.stat().st_mode | stat.S_IEXEC)
        self.source = self.project / "a.py"
        self.source.write_text("x = 1\n", encoding="utf-8")
        old = time.time() - 60
        for path in (self.gate, self.source):
            os.utime(path, (old, old))

    def call(self, event: str, command: str, tool_use_id: str = "toolu_1") -> str:
        result = run(
            self.HOOK,
            {
                "hook_event_name": event,
                "session_id": "effects-test",
                "tool_use_id": tool_use_id,
                "tool_name": "Bash",
                "tool_input": {"command": command},
            },
            env={"CLAUDE_PROJECT_DIR": str(self.project)},
            cwd=self.project,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return context(result)

    def touch(self, rel: str) -> None:
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("changed\n", encoding="utf-8")

    def test_a_file_written_by_sed_is_checked_and_nudged(self) -> None:
        self.assertEqual("", self.call("PreToolUse", "sed -i s/1/2/ a.py"))
        self.touch("a.py")
        seen = self.call("PostToolUse", "sed -i s/1/2/ a.py")
        self.assertIn("[bash-write] a.py", seen)
        self.assertIn("FAIL:", seen)
        self.assertIn("Edit/Write", seen)

    def test_a_heredoc_write_is_still_checked(self) -> None:
        command = "python3 - <<'EOF'\nopen('a.py','w').write('y')\nEOF"
        self.call("PreToolUse", command)
        self.touch("a.py")
        self.assertIn("[bash-write] a.py", self.call("PostToolUse", command))

    def test_rewriting_the_gate_script_asks_for_a_smoke_test(self) -> None:
        self.call("PreToolUse", "cat > .claude/scripts/verify-save <<'EOF'")
        self.touch(".claude/scripts/verify-save")
        self.gate.chmod(self.gate.stat().st_mode | stat.S_IEXEC)
        self.assertIn("smoke-test", self.call("PostToolUse", "cat > x"))

    def test_the_number_of_files_checked_is_capped(self) -> None:
        self.call("PreToolUse", "sed -i s/a/b/ *.py")
        for index in range(8):
            self.touch(f"m{index}.py")
        self.assertIn("checked 5 of 8", self.call("PostToolUse", "sed -i s/a/b/ *.py"))

    def test_nothing_written_says_nothing(self) -> None:
        self.call("PreToolUse", "ls")
        self.assertEqual("", self.call("PostToolUse", "ls"))

    def test_a_file_changed_before_the_command_is_not_reported(self) -> None:
        self.touch("a.py")
        time.sleep(0.05)  # past the kernel's coarse mtime tick
        self.call("PreToolUse", "sed -i s/1/2/ b.py")
        self.assertEqual("", self.call("PostToolUse", "sed -i s/1/2/ b.py"))

    def test_build_output_and_logs_are_not_scanned(self) -> None:
        self.call("PreToolUse", "npm run build > build/log.txt")
        self.touch("build/out.py")
        self.touch("node_modules/pkg/index.py")
        self.touch(".claude/logs/cli-tools.jsonl")
        self.assertEqual("", self.call("PostToolUse", "npm run build > build/log.txt"))

    def test_package_stores_and_framework_caches_are_not_scanned(self) -> None:
        """
        A real adopting repo (a pnpm monorepo) held 68,466 of its 73,737 files in
        `.pnpm-store`, so every walk hit the 50k-entry budget and the hook went
        inert for the session. Stores and caches are never the model's edits.
        """
        self.call("PreToolUse", "pnpm install > install.log")
        for store in (
            ".pnpm-store",
            ".yarn",
            ".gradle",
            ".dart_tool",
            "Pods",
            ".svelte-kit",
            ".next",
            ".turbo",
        ):
            self.touch(f"{store}/pkg/index.py")
        self.assertEqual("", self.call("PostToolUse", "pnpm install > install.log"))

    def test_discarding_output_to_dev_null_is_not_a_write(self) -> None:
        # Seen in this repo's own session: `ruff format x.py >/dev/null` drew the
        # "use Edit/Write" nudge although nothing was redirected into a file.
        self.gate.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        old = time.time() - 60
        os.utime(self.gate, (old, old))
        command = "uv run ruff format a.py >/dev/null 2>&1"
        self.call("PreToolUse", command)
        self.touch("a.py")
        self.assertEqual("", self.call("PostToolUse", command))

    def test_a_post_without_its_pre_says_nothing(self) -> None:
        self.touch("a.py")
        self.assertEqual(
            "", self.call("PostToolUse", "sed -i s/1/2/ a.py", "toolu_unknown")
        )

    def test_git_commands_are_not_reported(self) -> None:
        self.call("PreToolUse", "git checkout -- a.py")
        self.touch("a.py")
        self.assertEqual("", self.call("PostToolUse", "git checkout -- a.py"))

    def test_a_passing_file_from_a_non_editing_command_stays_silent(self) -> None:
        self.gate.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        old = time.time() - 60
        os.utime(self.gate, (old, old))
        self.call("PreToolUse", "npm test")
        self.touch("a.py")
        self.assertEqual("", self.call("PostToolUse", "npm test"))


class PostImplementationReviewTests(unittest.TestCase):
    HOOK = HOOKS / "post-implementation-review.py"

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name)

    def edit(self, name: str, lines: int = 5, session: str = "s1") -> str:
        return context(
            run(
                self.HOOK,
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session,
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": f"src/{name}",
                        "new_string": "line\n" * lines,
                    },
                },
                env={"CLAUDE_PROJECT_DIR": str(self.project)},
                cwd=self.project,
            )
        )

    def state_files(self) -> list[Path]:
        directory = self.project / ".claude" / "logs" / "implementation-state"
        return sorted(directory.glob("*.json")) if directory.exists() else []

    def test_the_first_edit_records_state_but_stays_silent(self) -> None:
        self.assertEqual("", self.edit("one.py"))
        self.assertEqual(1, len(self.state_files()), "no state was written")

    def test_the_third_source_file_triggers_the_suggestion(self) -> None:
        self.edit("one.py")
        self.edit("two.py")
        emitted = self.edit("three.py")
        self.assertIn("[Code Review Suggestion]", emitted)
        self.assertIn("3 source files", emitted)

    def test_it_suggests_only_once_per_session(self) -> None:
        self.edit("one.py")
        self.edit("two.py")
        self.edit("three.py")
        self.assertEqual("", self.edit("four.py"), "it suggested twice")

    def test_a_different_session_starts_from_zero(self) -> None:
        self.edit("one.py", session="s1")
        self.edit("two.py", session="s1")
        self.assertEqual("", self.edit("one.py", session="s2"))

    def test_documents_do_not_count_as_implementation(self) -> None:
        self.edit("a.md")
        self.edit("b.md")
        self.assertEqual("", self.edit("c.md"))


if __name__ == "__main__":
    unittest.main()
