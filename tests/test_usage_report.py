"""
Tests for `.claude/bin/usage-report` — counts of how the template was used,
read from what Claude Code and the template already record.

The transcripts here are synthetic, shaped after records measured in real
transcripts (2026-10-13): `<command-name>` tags in user text, `tool_use` /
`tool_result` blocks, `hook_success` attachments that carry the hook command,
`hook_additional_context` attachments that carry only the event, and
`message.usage` repeated on every record of one API response. Claude Code does
not document this format, so a renamed field in another version shows up as
zeros, not as an error — these tests cannot catch that.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
SCRIPT = REPO / ".claude" / "bin" / "usage-report"
SENTINEL = "SENTINEL-do-not-leak"
SESSION = "11111111-aaaa-bbbb-cccc-000000000001"


def ts(day: str = "2026-10-10") -> str:
    return f"{day}T09:00:00.000Z"


def user_text(text: str, day: str = "2026-10-10") -> dict:
    return {
        "type": "user",
        "timestamp": ts(day),
        "cwd": f"/{SENTINEL}/project",
        "message": {"role": "user", "content": text},
    }


def tool_use(
    tool_id: str, name: str, tool_input: dict, msg_id: str = "", day: str = "2026-10-10"
) -> dict:
    return {
        "type": "assistant",
        "timestamp": ts(day),
        "message": {
            "id": msg_id or f"msg-{tool_id}",
            "content": [
                {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}
            ],
            "usage": usage(),
        },
    }


def tool_result(
    tool_id: str, text: str, is_error: bool = False, day: str = "2026-10-10"
) -> dict:
    return {
        "type": "user",
        "timestamp": ts(day),
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": text,
                    "is_error": is_error,
                }
            ],
        },
        "toolUseResult": {"stdout": text, "stderr": ""},
    }


def usage(
    inp: int = 10, cache_new: int = 20, cache_read: int = 30, out: int = 5
) -> dict:
    return {
        "input_tokens": inp,
        "cache_creation_input_tokens": cache_new,
        "cache_read_input_tokens": cache_read,
        "output_tokens": out,
    }


def hook_success(
    hook_file: str, exit_code: int = 0, stdout: str = "", day: str = "2026-10-10"
) -> dict:
    return {
        "type": "attachment",
        "timestamp": ts(day),
        "attachment": {
            "type": "hook_success",
            "hookName": "PostToolUse:Bash",
            "hookEvent": "PostToolUse",
            "command": f'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/{hook_file}',
            "exitCode": exit_code,
            "stdout": stdout,
            "stderr": "",
            "content": stdout,
        },
    }


def hook_error(hook_file: str, stderr: str = "ImportError: x") -> dict:
    """Shape measured on a real adopter (2026-10-13): the error record carries the command."""
    return {
        "type": "attachment",
        "timestamp": ts(),
        "attachment": {
            "type": "hook_non_blocking_error",
            "hookName": "PostToolUse:Bash",
            "hookEvent": "PostToolUse",
            "command": f'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/{hook_file}"',
            "exitCode": 1,
            "stdout": "",
            "stderr": stderr,
            "durationMs": 40,
        },
    }


def hook_message(kind: str, event: str, content: str = SENTINEL) -> dict:
    return {
        "type": "attachment",
        "timestamp": ts(),
        "attachment": {
            "type": kind,
            "hookName": f"{event}:Bash",
            "hookEvent": event,
            "content": content,
        },
    }


class UsageReportCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = self.root / "project"
        self.transcripts = self.root / "transcripts"
        self.transcripts.mkdir()
        (self.project / ".claude" / "logs").mkdir(parents=True)

    def write_session(
        self, records: list[dict], session: str = SESSION, agent: str = ""
    ) -> None:
        if agent:
            path = self.transcripts / session / "subagents" / f"agent-{agent}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path = self.transcripts / f"{session}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")

    def run_report(self, *args: str, tz: str = "") -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "TZ": tz} if tz else None
        return subprocess.run(
            [
                str(SCRIPT),
                "--project",
                str(self.project),
                "--transcripts",
                str(self.transcripts),
                *args,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

    def report(self, *args: str, tz: str = "") -> dict:
        result = self.run_report("--json", *args, tz=tz)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


class SkillCounts(UsageReportCase):
    def test_never_invoked_template_skill_is_listed_with_zero(self) -> None:
        """U1 — 0 is the removal signal, so it must be printed, not omitted."""
        self.write_session([user_text("<command-name>/feature</command-name>")])
        skills = self.report()["skills"]
        self.assertEqual(skills["ticket"], {"typed": 0, "model": 0, "last": None})
        self.assertEqual(skills["feature"]["typed"], 1)

    def test_typed_and_model_invocations_are_counted_apart(self) -> None:
        """U2"""
        self.write_session(
            [
                user_text("<command-name>/feature</command-name>", day="2026-10-09"),
                user_text("<command-name>feature</command-name>", day="2026-10-11"),
                tool_use("t1", "Skill", {"skill": "isolated-review"}),
            ]
        )
        skills = self.report()["skills"]
        self.assertEqual(
            skills["feature"], {"typed": 2, "model": 0, "last": "2026-10-11"}
        )
        self.assertEqual(skills["isolated-review"]["model"], 1)

    def test_names_outside_the_template_are_only_summed(self) -> None:
        """U2 — a work project's own command and skill names never leave."""
        self.write_session(
            [
                user_text(f"<command-name>/{SENTINEL}</command-name>"),
                tool_use("t1", "Skill", {"skill": SENTINEL}),
            ]
        )
        data = self.report()
        self.assertEqual(data["other_commands"], {"typed": 1, "model": 1})
        self.assertNotIn(SENTINEL, json.dumps(data))

    def test_template_lists_match_the_template(self) -> None:
        """The name lists are constants; they must follow the template's files."""
        data = self.report()
        skills = sorted(
            p.name
            for p in (REPO / ".claude" / "skills").iterdir()
            if (p / "SKILL.md").exists()
        )
        hooks = sorted(
            p.name
            for p in (REPO / ".claude" / "hooks").glob("*.py")
            if not p.name.startswith("_")
        )
        agents = sorted(p.stem for p in (REPO / ".claude" / "agents").glob("*.md"))
        self.assertEqual(sorted(data["skills"]), skills)
        self.assertEqual(sorted(data["hooks"]), hooks)
        for agent in agents:
            self.assertIn(agent, data["subagents"])


class Subagents(UsageReportCase):
    def test_subagent_types_counted_and_unknown_summed(self) -> None:
        self.write_session(
            [
                tool_use("a1", "Agent", {"subagent_type": "deep-reasoning"}),
                tool_use("a2", "Task", {"subagent_type": "general-purpose"}),
                tool_use("a3", "Agent", {"subagent_type": SENTINEL}),
            ]
        )
        data = self.report()
        self.assertEqual(data["subagents"]["deep-reasoning"], 1)
        self.assertEqual(data["subagents"]["general-purpose"], 1)
        self.assertEqual(data["other_subagents"], 1)
        self.assertNotIn(SENTINEL, json.dumps(data))


class NothingLeaks(UsageReportCase):
    def test_sentinel_never_reaches_either_output(self) -> None:
        """U3 — text, inputs, outputs, hook output and errors, cwd: counts only."""
        self.write_session(
            [
                user_text(f"please {SENTINEL}"),
                tool_use("b1", "Bash", {"command": f"agy -p '{SENTINEL}'"}),
                tool_result("b1", SENTINEL),
                tool_use("b2", "Bash", {"command": f"echo {SENTINEL}"}),
                tool_result("b2", f"Exit code 1\n{SENTINEL}", is_error=True),
                hook_success("lint-on-save.py", 2, stdout=SENTINEL),
                hook_message("hook_additional_context", "PostToolUse"),
                hook_message(f"hook_{SENTINEL}", "PostToolUse"),
                hook_error("lint-on-save.py", stderr=SENTINEL),
                tool_use("p1", "Bash", {"command": ".claude/bin/agy-probe"}),
                tool_result("p1", f"{SENTINEL} state"),
            ]
        )
        self.write_session([user_text(SENTINEL)], agent="x1")
        for args in (("--json",), ()):
            result = self.run_report(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(SENTINEL, result.stdout)
            self.assertNotIn(SENTINEL, result.stderr)


class Tokens(UsageReportCase):
    def test_one_response_split_over_records_counts_once(self) -> None:
        """U4"""
        self.write_session(
            [
                tool_use("c1", "Read", {}, msg_id="m1"),
                tool_use("c2", "Read", {}, msg_id="m1"),
                tool_use("c3", "Read", {}, msg_id="m2"),
            ]
        )
        self.write_session([tool_use("c4", "Read", {}, msg_id="m9")], agent="x1")
        tokens = self.report()["tokens"]
        self.assertEqual(
            tokens["main"],
            {"input": 20, "cache_creation": 40, "cache_read": 60, "output": 10},
        )
        self.assertEqual(tokens["subagent"]["output"], 5)

    def test_streamed_response_counts_its_final_record(self) -> None:
        # Measured (2026-10-14): subagent records of one response carry a
        # growing output_tokens; the first record undercounted 4.6x-24x.
        records = [tool_use(f"s{n}", "Read", {}, msg_id="m1") for n in range(3)]
        for record, out in zip(records, (1, 7, 12), strict=True):
            record["message"]["usage"] = usage(out=out)
        self.write_session([user_text("hi")])
        self.write_session(records, agent="x1")
        self.assertEqual(self.report()["tokens"]["subagent"]["output"], 12)


class Hooks(UsageReportCase):
    def test_runs_nonzero_and_output_per_hook_file(self) -> None:
        """U5"""
        self.write_session(
            [
                hook_success("lint-on-save.py"),
                hook_success("lint-on-save.py", 2, stdout="ruff: E501"),
                hook_success("bash-write-check.py", 0, stdout="note"),
                hook_success("my-own-hook.py", 1),
                hook_message("hook_additional_context", "PostToolUse"),
                hook_message("hook_system_message", "PostToolUse"),
                hook_message("hook_blocking_error", "PreToolUse"),
            ]
        )
        data = self.report()
        self.assertEqual(
            data["hooks"]["lint-on-save.py"],
            {"runs": 2, "nonzero": 1, "with_output": 1, "errors": 0},
        )
        self.assertEqual(data["hooks"]["bash-write-check.py"]["with_output"], 1)
        self.assertEqual(
            data["other_hooks"],
            {"runs": 1, "nonzero": 1, "with_output": 0, "errors": 0},
        )
        self.assertEqual(
            data["hook_messages"],
            {
                "PostToolUse:hook_additional_context": 1,
                "PostToolUse:hook_system_message": 1,
                "PreToolUse:hook_blocking_error": 1,
            },
        )

    def test_errors_are_charged_to_the_hook_that_failed(self) -> None:
        """R1 — a hook failing on every call (1,933 times in a real project) must show."""
        self.write_session(
            [
                hook_success("bash-write-check.py"),
                hook_error("bash-write-check.py"),
                hook_error("bash-write-check.py"),
                hook_error(f"{SENTINEL}.py", stderr=SENTINEL),
            ]
        )
        data = self.report()
        self.assertEqual(data["hooks"]["bash-write-check.py"]["errors"], 2)
        self.assertEqual(data["hooks"]["bash-write-check.py"]["runs"], 1)
        self.assertEqual(data["other_hooks"]["errors"], 1)
        self.assertEqual(data["hook_messages"], {})
        self.assertNotIn(SENTINEL, json.dumps(data))
        self.assertIn(
            "| bash-write-check.py | 1 | 0 | 0 | 2 |", self.run_report().stdout
        )


class Denied(UsageReportCase):
    def test_denied_calls_counted_per_tool(self) -> None:
        """U6"""
        self.write_session(
            [
                tool_use("d1", "Bash", {"command": "rm -rf x"}),
                tool_result(
                    "d1", "Permission for this action was denied by the user", True
                ),
                tool_use("d2", "Write", {}),
                tool_result(
                    "d2", "The user doesn't want to proceed with this tool use.", True
                ),
                tool_use("d3", f"mcp__{SENTINEL}__send", {}),
                tool_result("d3", "Permission for this action was denied", True),
                tool_use("d4", "Bash", {"command": "false"}),
                tool_result("d4", "Exit code 1", True),
            ]
        )
        data = self.report()
        self.assertEqual(data["denied"], {"Bash": 1, "Write": 1, "mcp": 1})


class Gate(UsageReportCase):
    def test_verify_runs_and_failures_per_tier(self) -> None:
        """U7"""
        self.write_session(
            [
                tool_use("g1", "Bash", {"command": ".claude/scripts/verify-task"}),
                tool_result("g1", "ok"),
                tool_use(
                    "g2", "Bash", {"command": ".claude/scripts/verify-task tests/x.py"}
                ),
                tool_result("g2", "Exit code 1\nFAILED", True),
            ]
        )
        self.write_session(
            [
                tool_use("g3", "Bash", {"command": "./.claude/scripts/verify-unit"}),
                tool_result("g3", "ok"),
            ],
            agent="x1",
        )
        self.assertEqual(
            self.report()["gate"],
            {"task": {"runs": 2, "failed": 1}, "unit": {"runs": 1, "failed": 0}},
        )

    def test_only_commands_in_command_position_are_runs(self) -> None:
        # Measured (2026-10-14): about a quarter of the mentions in real
        # transcripts were reads or arguments, not runs.
        commands = {
            "cat .claude/scripts/verify-task": False,
            "git diff -- .claude/scripts/verify-task": False,
            'git commit -m "run .claude/scripts/verify-task"': False,
            "cd /r && .claude/scripts/verify-task": True,
            "for i in 1; do .claude/scripts/verify-task; done": True,
            '"$CLAUDE_PROJECT_DIR"/.claude/scripts/verify-task': True,
            "/usr/bin/time .claude/scripts/verify-task": True,
        }
        self.write_session(
            [
                tool_use(f"v{n}", "Bash", {"command": command})
                for n, command in enumerate(commands)
            ]
        )
        runs = sum(commands.values())
        self.assertEqual(self.report()["gate"], {"task": {"runs": runs, "failed": 0}})


class FeatureProgress(UsageReportCase):
    def test_how_far_feature_sessions_get(self) -> None:
        self.write_session(
            [
                user_text("<command-name>/feature</command-name>"),
                tool_use("f1", "Agent", {"subagent_type": "deep-reasoning"}),
                tool_use("f2", "Skill", {"skill": "isolated-review"}),
            ]
        )
        self.write_session(
            [tool_use("f3", "Bash", {"command": ".claude/scripts/verify-unit"})],
            agent="x1",
        )
        self.write_session(
            [user_text("<command-name>/feature</command-name>")],
            session="22222222-aaaa-bbbb-cccc-000000000002",
        )
        self.write_session(
            [tool_use("f4", "Agent", {"subagent_type": "deep-reasoning"})],
            session="33333333-aaaa-bbbb-cccc-000000000003",
        )
        self.assertEqual(
            self.report()["feature_sessions"],
            {"sessions": 2, "design_review": 1, "verify_run": 1, "isolated_review": 1},
        )


class Agy(UsageReportCase):
    def test_agy_calls_probe_states_and_log(self) -> None:
        """U8"""
        self.write_session(
            [
                tool_use("y1", "Bash", {"command": "agy -p 'x' --model m"}),
                tool_result("y1", "answer"),
                tool_use("y2", "Bash", {"command": "cd /r && agy -p 'x'"}),
                tool_result("y2", "Exit code 1\nerror", True),
                tool_use("y3", "Bash", {"command": ".claude/bin/agy-probe"}),
                tool_result("y3", "READY"),
                tool_use("y4", "Bash", {"command": "cd /r; .claude/bin/agy-probe"}),
                tool_result("y4", "Exit code 1\nSTALE T1 gemini-x", True),
                # Named as an argument, not run (measured in a real project).
                # A newline separates commands; one call can run several kinds.
                tool_use("y7", "Bash", {"command": "cd /r\nagy -p 'x'"}),
                tool_result("y7", "answer"),
                tool_use(
                    "y8",
                    "Bash",
                    {"command": ".claude/scripts/verify-task; .claude/bin/agy-probe"},
                ),
                # Was expected as "unknown": that is the common real shape
                # (2026-10-14: 30 of 41 probe runs), so the state is read
                # from any line, not only the first word.
                tool_result("y8", "== gate ==\nREADY"),
                tool_use("y9", "Bash", {"command": ".claude/bin/agy-probe"}),
                tool_result("y9", "Exit code 1\nTraceback: boom", True),
                tool_use("y5", "Bash", {"command": "grep -n agy-probe a.md"}),
                tool_result("y5", "a.md:1: agy-probe"),
                tool_use("y6", "Bash", {"command": "echo agy is down | tee x"}),
                tool_result("y6", "agy is down"),
            ]
        )
        data = self.report()
        self.assertEqual(
            data["agy"],
            {
                "calls": 3,
                "failed": 1,
                "probe_runs": 4,
                "probe_states": {"READY": 2, "STALE": 1, "unknown": 1},
            },
        )
        self.assertEqual(data["gate"], {"task": {"runs": 1, "failed": 0}})


class Since(UsageReportCase):
    def test_since_drops_older_records(self) -> None:
        """U9"""
        self.write_session(
            [
                user_text("<command-name>/feature</command-name>", day="2026-09-01"),
                user_text("<command-name>/feature</command-name>", day="2026-10-12"),
            ]
        )
        data = self.report("--since", "2026-10-01")
        self.assertEqual(data["skills"]["feature"]["typed"], 1)
        self.assertEqual(data["coverage"]["first"], "2026-10-12")

    def test_since_is_a_local_date(self) -> None:
        # Transcript stamps are UTC; --since and the run-log names are local.
        record = user_text("<command-name>/feature</command-name>")
        record["timestamp"] = "2026-10-12T20:00:00.000Z"  # 05:00 on the 13th in Seoul
        self.write_session([record])
        data = self.report("--since", "2026-10-13", tz="Asia/Seoul")
        self.assertEqual(data["skills"]["feature"]["typed"], 1)
        self.assertEqual(data["coverage"]["first"], "2026-10-13")

    def test_bad_since_is_refused(self) -> None:
        result = self.run_report("--since", "yesterday")
        self.assertEqual(result.returncode, 2)


class Coverage(UsageReportCase):
    def test_sessions_and_dates(self) -> None:
        self.write_session([user_text("hi", day="2026-10-02")])
        self.write_session([user_text("hi", day="2026-10-05")], agent="x1")
        self.write_session(
            [user_text("hi", day="2026-10-08")],
            session="22222222-aaaa-bbbb-cccc-000000000002",
        )
        coverage = self.report()["coverage"]
        self.assertEqual(coverage["main_sessions"], 2)
        self.assertEqual(coverage["subagent_transcripts"], 1)
        self.assertEqual(
            (coverage["first"], coverage["last"]), ("2026-10-02", "2026-10-08")
        )

    def test_missing_transcript_dir_exits_2(self) -> None:
        """U10"""
        result = subprocess.run(
            [str(SCRIPT), "--transcripts", str(self.root / "nope")],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("no transcripts", result.stderr)

    def test_markdown_is_the_default(self) -> None:
        self.write_session([user_text("<command-name>/feature</command-name>")])
        result = self.run_report()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("# Usage report"))
        self.assertIn("| feature | 1 | 0 |", result.stdout)

    def test_the_script_is_executable(self) -> None:
        self.assertTrue(SCRIPT.stat().st_mode & 0o111)


if __name__ == "__main__":
    unittest.main()
