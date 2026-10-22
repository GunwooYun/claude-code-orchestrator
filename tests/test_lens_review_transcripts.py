"""
Tests for the transcript side of /lens-review: `collect`, which takes answers
from the session's subagent transcripts, and tools/lens-audit, which checks a
run's locks from them. Split from test_lens_review.py (file size rule).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_lens_review import FINDING, LENSES, REPO, SKILL, load, lr, make_run


class CollectTests(unittest.TestCase):
    """V-collect: answers come from the session's transcripts, matched by prompt."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"
        (self.root / ".claude/rules").mkdir(parents=True)
        self.run_dir = make_run(self.root)
        self.config = Path(self._tmp.name) / "config"
        self.agents = self.config / "projects" / "-repo" / "sess" / "subagents"
        self.agents.mkdir(parents=True)
        env = {"CLAUDE_CONFIG_DIR": str(self.config), "CLAUDE_CODE_SESSION_ID": "sess"}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.n = 0

    def agent(self, prompt: str, answer: str | None, tool_last: bool = False) -> None:
        self.n += 1
        rows: list[dict] = [{"type": "user", "message": {"content": prompt}}]
        if answer is not None:
            rows.append(
                {
                    "type": "assistant",
                    "message": {
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": answer}],
                    },
                }
            )
        if tool_last:
            rows.append(
                {
                    "type": "assistant",
                    # Text and a tool call in one message: still working.
                    "message": {
                        "content": [
                            {"type": "text", "text": "Let me read more."},
                            {"type": "tool_use", "name": "Read"},
                        ]
                    },
                }
            )
        (self.agents / f"agent-{self.n}.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows)
        )

    def test_collect_saves_lens_answers_then_verifier_answers(self) -> None:
        for lens in LENSES:
            answer = FINDING.strip() if lens == "tests" else "NO FINDINGS"
            self.agent(lr.lens_prompt(self.root, self.run_dir, lens), answer)
        saved, missing, _ = lr.collect(self.root, self.run_dir)
        self.assertEqual(5, len(saved))
        self.assertEqual(["verify-tests-1.md"], missing)
        self.assertEqual(
            FINDING.strip() + "\n", (self.run_dir / "lens-tests.md").read_text()
        )
        self.agent(lr.verify_prompt(self.run_dir, "tests:1"), "verdict: CONFIRMED")
        saved, missing, _ = lr.collect(self.root, self.run_dir)
        self.assertIn("verify-tests-1.md", saved)
        self.assertEqual([], missing)

    def test_collect_saves_lens_and_verifier_answers_in_one_call(self) -> None:
        """Both transcripts exist already: the second pass picks up the verifier."""
        (self.run_dir / "lens-tests.md").write_text(FINDING.strip() + "\n")
        verify = lr.verify_prompt(self.run_dir, "tests:1")
        (self.run_dir / "lens-tests.md").unlink()
        for lens in LENSES:
            answer = FINDING.strip() if lens == "tests" else "NO FINDINGS"
            self.agent(lr.lens_prompt(self.root, self.run_dir, lens), answer)
        self.agent(verify, "verdict: CONFIRMED")
        saved, missing, _ = lr.collect(self.root, self.run_dir)
        self.assertIn("verify-tests-1.md", saved)
        self.assertEqual(6, len(saved))
        self.assertEqual([], missing)

    def stamp(self, n: int, mtime: int) -> None:
        os.utime(self.agents / f"agent-{n}.jsonl", (mtime, mtime))

    def test_collect_retried_prompt_takes_the_newest_transcript(self) -> None:
        """The first by file name is not the newest: a failed attempt must lose."""
        prompt = lr.lens_prompt(self.root, self.run_dir, "security")
        self.agent(prompt, "API error, giving up")  # agent-1: old, sorts first
        self.agent(prompt, "NO FINDINGS")  # agent-2: the retry, newest
        self.agent(prompt, "older still")  # agent-3: sorts last, oldest
        self.stamp(1, 2000)
        self.stamp(2, 3000)
        self.stamp(3, 1000)
        saved, *_ = lr.collect(self.root, self.run_dir)
        self.assertEqual(["lens-security.md"], saved)
        self.assertEqual(
            "NO FINDINGS\n", (self.run_dir / "lens-security.md").read_text()
        )

    def test_collect_unfinished_retry_does_not_fall_back_to_the_old_answer(
        self,
    ) -> None:
        prompt = lr.lens_prompt(self.root, self.run_dir, "security")
        self.agent(prompt, "API error, giving up")
        self.agent(prompt, "partial", tool_last=True)  # the retry, still working
        self.stamp(1, 1000)
        self.stamp(2, 2000)
        saved, missing, _ = lr.collect(self.root, self.run_dir)
        self.assertEqual([], saved)
        self.assertIn("lens-security.md", missing)

    def test_collect_skips_a_changed_prompt_and_an_unfinished_agent(self) -> None:
        self.agent(
            lr.lens_prompt(self.root, self.run_dir, "security") + "\nBe brief.",
            "NO FINDINGS",
        )
        self.agent(
            lr.lens_prompt(self.root, self.run_dir, "tests"), "partial", tool_last=True
        )
        saved, missing, _ = lr.collect(self.root, self.run_dir)
        self.assertEqual([], saved)
        self.assertIn("lens-security.md", missing)
        self.assertIn("lens-tests.md", missing)

    def test_collect_takes_a_handback_and_skips_mid_run_text(self) -> None:
        """Interactive agents answer through SubagentHandback; text rows mid-run
        (no end_turn) are not answers."""
        prompt = lr.lens_prompt(self.root, self.run_dir, "security")
        rows = [
            {"type": "user", "message": {"content": prompt}},
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Reading."}]},
            },
        ]
        self.n += 1
        path = self.agents / f"agent-{self.n}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows))
        saved, *_ = lr.collect(self.root, self.run_dir)
        self.assertEqual([], saved)
        rows.append(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "SubagentHandback",
                            "input": {"message": "NO FINDINGS"},
                        }
                    ]
                },
            }
        )
        path.write_text("\n".join(json.dumps(r) for r in rows))
        saved, *_ = lr.collect(self.root, self.run_dir)
        self.assertEqual(["lens-security.md"], saved)
        self.assertEqual(
            "NO FINDINGS\n", (self.run_dir / "lens-security.md").read_text()
        )

    def unstopped(self, prompt: str, text: str) -> str:
        """An agent whose last text row was written without its stop_reason."""
        self.n += 1
        rows = [
            {"type": "user", "message": {"content": prompt}},
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": text}]},
            },
        ]
        (self.agents / f"agent-{self.n}.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows)
        )
        return str(self.n)

    def notify(self, agent: str, status: str) -> None:
        """The main session's record of an agent's end (queue-operation row)."""
        main = self.agents.parent.with_suffix(".jsonl")
        notice = (
            f"<task-notification>\n<task-id>{agent}</task-id>\n"
            f"<status>{status}</status>\n<result>…</result>\n</task-notification>"
        )
        row = {"type": "queue-operation", "operation": "enqueue", "content": notice}
        with main.open("a") as out:
            out.write(json.dumps(row) + "\n")

    def test_collect_unstopped_text_of_a_completed_agent_is_its_answer(self) -> None:
        """Seen in 4 of 6 runs of one batch: the answer row lacks stop_reason, but
        the main session was told the agent completed."""
        prompt = lr.lens_prompt(self.root, self.run_dir, "security")
        agent = self.unstopped(prompt, "NO FINDINGS")
        saved, missing, _ = lr.collect(self.root, self.run_dir)
        self.assertEqual([], saved)
        self.assertIn("lens-security.md", missing)
        self.notify(agent, "failed")
        saved, *_ = lr.collect(self.root, self.run_dir)
        self.assertEqual([], saved)
        self.notify(agent, "completed")
        saved, *_ = lr.collect(self.root, self.run_dir)
        self.assertEqual(["lens-security.md"], saved)
        self.assertEqual(
            "NO FINDINGS\n", (self.run_dir / "lens-security.md").read_text()
        )

    def test_collect_completed_agent_ending_on_a_tool_call_is_not_saved(self) -> None:
        prompt = lr.lens_prompt(self.root, self.run_dir, "tests")
        self.agent(prompt, None, tool_last=True)
        self.notify(str(self.n), "completed")
        saved, missing, _ = lr.collect(self.root, self.run_dir)
        self.assertEqual([], saved)
        self.assertIn("lens-tests.md", missing)

    def test_collect_reports_an_api_error_as_failed_not_missing(self) -> None:
        """A usage limit ends the agent with a synthetic error row: it will never
        answer, so it is named as failed with the reason."""
        prompt = lr.lens_prompt(self.root, self.run_dir, "security")
        agent = self.unstopped(prompt, "You've hit your session limit")
        path = self.agents / f"agent-{agent}.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        rows[-1].update(isApiErrorMessage=True, error="rate_limit")
        path.write_text("\n".join(json.dumps(r) for r in rows))
        self.notify(agent, "completed")
        saved, missing, failed = lr.collect(self.root, self.run_dir)
        self.assertEqual([], saved)
        self.assertNotIn("lens-security.md", missing)
        self.assertEqual(["lens-security.md (rate_limit)"], failed)
        self.assertFalse((self.run_dir / "lens-security.md").exists())
        self.agent(prompt, "NO FINDINGS")  # the retry, newest
        self.stamp(int(agent), 1000)
        saved, missing, failed = lr.collect(self.root, self.run_dir)
        self.assertEqual(["lens-security.md"], saved)
        self.assertEqual([], failed)

    def test_collect_ignores_other_sessions(self) -> None:
        other = self.config / "projects" / "-repo" / "other" / "subagents"
        other.mkdir(parents=True)
        prompt = lr.lens_prompt(self.root, self.run_dir, "security")
        rows = [
            {"type": "user", "message": {"content": prompt}},
            {
                "type": "assistant",
                "message": {
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": "NO FINDINGS"}],
                },
            },
        ]
        (other / "agent-x.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
        saved, *_ = lr.collect(self.root, self.run_dir)
        self.assertEqual([], saved)


audit = load(REPO / "tools" / "lens-audit", "lens_audit")


class AuditTests(unittest.TestCase):
    """V-audit: a recorded-shape transcript passes; each broken lock is caught."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / ".claude/rules").mkdir(parents=True)
        (self.root / ".claude/rules/testing.md").write_text("r")
        shutil.copytree(SKILL, self.root / ".claude/skills/lens-review")
        self.run_dir = make_run(self.root)
        self.answers = {lens: "NO FINDINGS" for lens in LENSES}
        self.answers["correctness"] = FINDING.strip()
        for lens, text in self.answers.items():
            (self.run_dir / f"lens-{lens}.md").write_text(text)
        (self.run_dir / "verify-correctness-1.md").write_text(
            "verdict: CONFIRMED\nimpact: low"
        )
        report_text, _ = lr.build_report(self.root, self.run_dir)
        self.report = lr.write_report_file(self.root, "feat", report_text)
        self.summary = (
            report_text.split("## Summary", 1)[1].split("\n## ", 1)[0].strip()
        )
        self.findings = (
            report_text.split("## Findings", 1)[1].split("\n## ", 1)[0].strip()
        )
        self.transcript = self.root / "session.jsonl"
        self.agents = self.root / "session" / "subagents"
        self.agents.mkdir(parents=True)

    def calls(self) -> list[tuple[str, str]]:
        """(prompt, saved answer text) for every call the procedure makes."""
        out = [
            (lr.lens_prompt(self.root, self.run_dir, lens), self.answers[lens])
            for lens in LENSES
        ]
        out.append(
            (
                lr.verify_prompt(self.run_dir, "correctness:1"),
                "verdict: CONFIRMED\nimpact: low",
            )
        )
        return out

    def record(
        self,
        prompt_edit: str = "",
        effort: str = "medium",
        extra_tool: str | None = None,
        shown: str | None = None,
        model: str = "claude-opus-5-5",
        drop: int | None = None,
        repeat: int | None = None,
        finish: bool = True,
    ) -> None:
        """drop: leave call i out; repeat: send call i twice; finish: the
        agents hand back (False: an agent that never answered)."""
        rows = []
        for i, (prompt, answer) in enumerate(self.calls()):
            if i == drop:
                continue
            if i == len(LENSES):  # the verifier call
                prompt += prompt_edit
            tool_id = f"toolu_{i}"
            call = {
                "type": "assistant",
                "message": {
                    "model": "claude-sonnet-5-5",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": tool_id,
                            "name": "Agent",
                            "input": {
                                "subagent_type": "lens-reviewer",
                                "prompt": prompt,
                            },
                        }
                    ],
                },
            }
            rows.append(call)
            if i == repeat:
                again = json.loads(json.dumps(call))
                again["message"]["content"][0]["id"] = f"{tool_id}_again"
                rows.append(again)
            agent_rows = []
            if extra_tool and i == 0:
                agent_rows.append(
                    {
                        "type": "assistant",
                        "effort": effort,
                        "message": {
                            "model": "claude-opus-5-5",
                            "content": [
                                {"type": "tool_use", "name": extra_tool, "input": {}}
                            ],
                        },
                    }
                )
            # An interactive session's background agent hands back.
            ending = {
                "type": "tool_use",
                "name": "SubagentHandback",
                "input": {"message": answer},
            }
            if not finish:  # still working: a text row with no end_turn
                ending = {"type": "text", "text": "Reading."}
            agent_rows.append(
                {
                    "type": "assistant",
                    "effort": effort,
                    "message": {"model": model, "content": [ending]},
                }
            )
            (self.agents / f"agent-{i}.jsonl").write_text(
                "\n".join(json.dumps(r) for r in agent_rows)
            )
            (self.agents / f"agent-{i}.meta.json").write_text(
                json.dumps({"agentType": "lens-reviewer", "toolUseId": tool_id})
            )
        rows.append(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": self.summary if shown is None else shown,
                        }
                    ]
                },
            }
        )
        self.transcript.write_text("\n".join(json.dumps(r) for r in rows))

    def problems(self) -> list[str]:
        return audit.audit(self.root, self.transcript, self.run_dir)

    def test_audit_passes_a_clean_run(self) -> None:
        self.record()
        self.assertEqual([], self.problems())

    def test_audit_catches_a_saved_answer_changed_by_one_char(self) -> None:
        self.record()
        (self.run_dir / "lens-correctness.md").write_text(
            FINDING.strip().replace("last", "Last")
        )
        self.assertTrue(
            any(p.startswith("2:") for p in self.problems()), self.problems()
        )

    def test_audit_catches_a_line_added_to_a_verifier_prompt(self) -> None:
        self.record(prompt_edit="\nWeigh real occurrence.")
        self.assertTrue(any(p.startswith("1:") for p in self.problems()))

    def test_audit_catches_effort_and_tools(self) -> None:
        self.record(effort="high", extra_tool="Bash")
        found = self.problems()
        self.assertTrue(any(p.startswith("3:") for p in found), found)
        self.assertTrue(any(p.startswith("4:") for p in found), found)

    def test_audit_catches_a_summarised_report(self) -> None:
        self.record(shown="One finding in correctness; looks minor.")
        self.assertTrue(any(p.startswith("5:") for p in self.problems()))

    def test_audit_requires_the_summary_not_the_findings(self) -> None:
        """Check 5 is about ## Summary: showing only the findings fails it."""
        self.record(shown=self.findings)
        self.assertTrue(any(p.startswith("5:") for p in self.problems()))

    def test_audit_catches_a_non_opus_model(self) -> None:
        self.record(model="claude-sonnet-5-5")
        found = self.problems()
        self.assertTrue(any(p.startswith("3:") for p in found), found)

    def test_audit_catches_a_missing_or_repeated_call(self) -> None:
        self.record(drop=1)
        found = self.problems()
        self.assertIn("1: prompt for lens-security.md sent 0 times", found)
        self.record(repeat=1)
        found = self.problems()
        self.assertIn("1: prompt for lens-security.md sent 2 times", found)

    def test_audit_catches_an_agent_that_never_answered(self) -> None:
        """No final message and no saved file must not compare equal (None == None)."""
        self.record(finish=False)
        (self.run_dir / "lens-security.md").unlink()
        found = self.problems()
        self.assertTrue(any(p.startswith("2: lens-security.md") for p in found), found)
