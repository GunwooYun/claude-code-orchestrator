"""
End-to-end effect tests: every hook must DO something on a payload that should
trigger it, and nothing on one that should not.

These exist because the contract tests in `test_hook_contract.py` could not
detect a dead hook. They assert tolerance — exit 0, valid-or-empty stdout,
survives junk — and empty stdout is a legal contract answer, so a hook that
reads its payload and returns immediately satisfies every one of them.
Measured: inserting `sys.exit(0)` after `json.load(sys.stdin)` in
a hook (the since-removed `agent-router.py`) left all 221 tests green. The template's most expensive defect
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
    "log-cli-tools.py",
    "lint-on-save.py",
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

    def test_a_redirected_call_is_logged_as_unknown(self) -> None:
        """
        V20: the unknown outcome must survive the JSONL round trip — `null`, not
        a dropped key or `false` — because checkpoint.py renders it from there.
        """
        self.bash('agy -p "q" > out.log; echo EXIT_CODE=$?')
        entry = json.loads(self.log.read_text(encoding="utf-8").splitlines()[-1])
        self.assertIn("success", entry)
        self.assertIsNone(entry["success"])
        self.assertEqual("file:out.log", entry["stdout_target"])
        self.assertEqual("", entry["response"])

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

    def test_git_among_read_only_commands_is_not_reported(self) -> None:
        # Seen in this repo's own sessions: git rewriting files inside a
        # compound command drew "checked 5 of 17 files written by this command".
        for command in (
            "cd /tmp/x && git fetch -q && git checkout -q --detach origin/b && git status --short",
            "git add README.md && GIT_EDITOR=true git rebase --continue 2>&1 | tail -3",
            "git rebase origin/develop 2>&1 | tail -3; git diff --name-only --diff-filter=U",
            # Seen after the fix above: `| cut` was not on the list.
            "git switch -q develop && git merge -q --ff-only origin/develop && git branch -vv | cut -c1-80",
            "git log --format=%s | tr a-z A-Z",
            "git log -1 --format=%s | jq -R .",
        ):
            with self.subTest(command=command):
                self.call("PreToolUse", command)
                self.touch("a.py")
                self.assertEqual("", self.call("PostToolUse", command))

    def test_a_writing_command_next_to_git_is_still_checked(self) -> None:
        for command in (
            "git checkout -- a.py && cp b.py a.py",
            "cd . && echo y > a.py && git add a.py",
            "git stash && sed -i s/1/2/ a.py",
            # Not on the list on purpose: both can write a file themselves.
            "git log --format=%s | sort -o a.py",
            "git log --format=%s | uniq - a.py",
        ):
            with self.subTest(command=command):
                self.call("PreToolUse", command)
                self.touch("a.py")
                self.assertIn("[bash-write] a.py", self.call("PostToolUse", command))

    def test_a_passing_file_from_a_non_editing_command_stays_silent(self) -> None:
        self.gate.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        old = time.time() - 60
        os.utime(self.gate, (old, old))
        self.call("PreToolUse", "npm test")
        self.touch("a.py")
        self.assertEqual("", self.call("PostToolUse", "npm test"))


if __name__ == "__main__":
    unittest.main()
