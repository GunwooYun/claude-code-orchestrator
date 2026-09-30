"""
Round-4 separate-session review of /isolated-review: the findings that survived
three earlier rounds — paths and headings handled as strings, a parent that dies
mid-run, what field-report lets out, and the Python floor. Numbers (#1, #4, ...)
are that review's finding numbers; X1–X3 are its conflicts, decided by the user
on 2026-09-30.

Uses the fake `claude` and the sandbox from test_isolated_review.py.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import ModuleType

from test_isolated_review import (
    EXIT_COMPLETE,
    EXIT_FAILED,
    EXIT_INCOMPLETE,
    EXIT_INVALID,
    EXIT_REFUSED,
    REPO,
    SCRIPT_REL,
    SKILL,
    IsolatedReviewCase,
    Sandbox,
    load_script,
)

RR = load_script()
FIELD_REPORT = SKILL / "field-report"
WAIT_S = 30


def load_field_report() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("field_report", str(FIELD_REPORT))
    spec = importlib.util.spec_from_loader("field_report", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def header(stdout: str) -> str:
    return stdout.split("\n---\n", 1)[0]


class PathHandlingTests(IsolatedReviewCase):
    def test_1_a_non_ascii_file_name_can_reach_complete(self) -> None:
        # git quotes such names ("src/\355\225\234...") unless told not to; the
        # quoted form then never matched what the reviewer wrote or read.
        box = self.sandbox(changed={"src/한국어.py": "x = 1\n"})
        result = box.run()
        self.assertEqual(EXIT_COMPLETE, result.returncode, result.stdout)
        self.assertIn("src/한국어.py", box.stdin())

    def test_4b_a_path_that_is_a_suffix_of_another_is_not_listed_by_it(self) -> None:
        # `a.py` is a substring of `src/data.py`: a substring check called it
        # listed and the run COMPLETE.
        box = self.sandbox(changed={"a.py": "a = 1\n", "src/data.py": "d = 1\n"})
        result = box.run(scenario="coverage_last_only")
        self.assertEqual(EXIT_FAILED, result.returncode, result.stdout)
        self.assertIn("coverage: a.py not listed", result.stdout)

    def test_4a_a_heading_quoted_inside_findings_is_not_the_coverage_section(
        self,
    ) -> None:
        result = self.sandbox().run(scenario="quoted_heading")
        self.assertEqual(EXIT_COMPLETE, result.returncode, result.stdout)

    def test_4c_a_required_heading_mentioned_only_inline_is_missing(self) -> None:
        result = self.sandbox().run(scenario="tests_heading_inline")
        self.assertEqual(EXIT_FAILED, result.returncode, result.stdout)
        self.assertIn("missing section: ## Tests", result.stdout)

    def test_18a_a_deleted_file_needs_no_read(self) -> None:
        box = self.sandbox(changed={"src/work.py": "w = 1\n"}, deleted=["tracked.txt"])
        result = box.run(
            scenario="coverage_no_read", files=["tracked.txt", "src/work.py"]
        )
        self.assertEqual(EXIT_COMPLETE, result.returncode, result.stdout)

    def test_18b_a_grep_on_a_file_counts_as_touching_it(self) -> None:
        result = self.sandbox().run(scenario="grep_only")
        self.assertEqual(EXIT_COMPLETE, result.returncode, result.stdout)

    def test_12_a_read_through_an_unnormalised_path_still_counts(self) -> None:
        result = self.sandbox().run(scenario="read_dot_path")
        self.assertEqual(EXIT_COMPLETE, result.returncode, result.stdout)

    def test_19_a_pure_rename_changes_no_lines(self) -> None:
        # --numstat without -M counted a rename as every line deleted and
        # added, while the file list (with -M) saw one renamed file.
        big = "x\n" * (RR.INLINE_MAX_LINES + 100)
        box = self.sandbox(
            base_files={"src/big.txt": big}, renamed={"src/big.txt": "src/moved.txt"}
        )
        # Git's default already detects renames; a config that turns it off is
        # what made the two commands disagree.
        subprocess.run(
            ["git", "config", "diff.renames", "false"], cwd=box.root, check=True
        )
        result = box.run(files=["src/moved.txt"])
        self.assertIn("1 files, 0 lines, diff inline", result.stdout)


class BoundaryTests(IsolatedReviewCase):
    def lines(self, n: int) -> Sandbox:
        return self.sandbox(changed={"src/big.txt": "x\n" * n})

    def test_18c_exactly_the_inline_limit_is_inline(self) -> None:
        result = self.lines(RR.INLINE_MAX_LINES).run()
        self.assertIn("diff inline", result.stdout)

    def test_18c_one_over_the_inline_limit_goes_to_a_file(self) -> None:
        result = self.lines(RR.INLINE_MAX_LINES + 1).run()
        self.assertIn("diff file", result.stdout)

    def test_18c_exactly_the_cap_is_reviewed(self) -> None:
        result = self.lines(RR.HARD_CAP_LINES).run()
        self.assertNotEqual(EXIT_REFUSED, result.returncode, result.stderr)

    def test_18c_one_over_the_cap_is_refused(self) -> None:
        result = self.lines(RR.HARD_CAP_LINES + 1).run()
        self.assertEqual(EXIT_REFUSED, result.returncode)


class ProbeTests(IsolatedReviewCase):
    def test_13_the_same_canary_denied_twice_does_not_pass_the_probe(self) -> None:
        box = self.sandbox()
        result = box.run(scenario="probe_same_twice")
        self.assertEqual(EXIT_FAILED, result.returncode, result.stdout)
        self.assertFalse((box.log / "main.argv.json").exists(), "reviewer ran anyway")

    def test_19_the_probe_cost_is_in_the_header(self) -> None:
        result = self.sandbox().run()
        self.assertIn("probe cost: $0.004", header(result.stdout))

    def test_19_the_probe_directory_is_removed(self) -> None:
        box = self.sandbox()
        box.run()
        self.assertFalse((box.root / RR.WORK_REL).exists())


class InterruptTests(IsolatedReviewCase):
    """#2: a run-review that is stopped must not leave the reviewer running."""

    def start(self, box: Sandbox) -> subprocess.Popen[str]:
        env = dict(os.environ)
        env["PATH"] = f"{box.bin}{os.pathsep}{env['PATH']}"
        env.update(
            FAKE_LOG=str(box.log), FAKE_SCENARIO="sleep", FAKE_FILES="src/work.py"
        )
        return subprocess.Popen(
            [sys.executable, str(box.root / SCRIPT_REL), "--base", "main"],
            cwd=box.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

    def wait_for(self, path: Path) -> None:
        deadline = time.monotonic() + WAIT_S
        while not path.exists():
            self.assertLess(time.monotonic(), deadline, f"{path} never appeared")
            time.sleep(0.1)

    def alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def test_2_a_signal_stops_the_reviewer_and_still_leaves_a_report(self) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            with self.subTest(signal=sig.name):
                box = self.sandbox()
                proc = self.start(box)
                self.wait_for(box.log / "main.child.pid")
                reviewer = int((box.log / "main.pid").read_text())
                child = int((box.log / "main.child.pid").read_text())
                proc.send_signal(sig)
                out, _ = proc.communicate(timeout=WAIT_S)
                self.assertEqual(EXIT_FAILED, proc.returncode, out)
                self.assertIn("interrupted", out)
                self.assertFalse(self.alive(reviewer), "the reviewer kept running")
                # Round-5 review F5: only the process group reaches this one.
                self.assertTrue(self.gone(child), "the reviewer's child kept running")
                self.assertEqual(1, len(box.reports()))

    def gone(self, pid: int) -> bool:
        """An orphan is reaped by init shortly after it dies; allow for that."""
        deadline = time.monotonic() + 5
        while self.alive(pid):
            if time.monotonic() > deadline:
                os.kill(pid, signal.SIGKILL)  # do not leak it past the test
                return False
            time.sleep(0.1)
        return True


class CleanupAndRefusalTests(IsolatedReviewCase):
    def test_8_a_clean_up_failure_keeps_the_report(self) -> None:
        box = self.sandbox(changed={"src/big.txt": "x\n" * (RR.INLINE_MAX_LINES + 1)})
        result = box.run(scenario="lock_work")
        self.assertEqual(EXIT_COMPLETE, result.returncode, result.stdout)
        self.assertIn("could not remove", result.stdout)
        self.assertEqual(1, len(box.reports()))

    def test_9_outside_a_git_repository_is_a_refusal_not_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(REPO / SCRIPT_REL), "--base", "main"],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=60,
            )
        self.assertEqual(EXIT_REFUSED, result.returncode, result.stderr)
        self.assertIn("REFUSED", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_7_a_secret_in_a_refusal_reason_is_not_recorded(self) -> None:
        box = self.sandbox()
        token = "ghp_" + "a" * 36
        box.run(base=f"https://x:{token}@example.com/r")
        log = box.root / RR.LOG_REL / "refusals.jsonl"
        self.assertTrue(log.exists())
        self.assertNotIn(token, log.read_text(encoding="utf-8"))


class DenyChangeTests(IsolatedReviewCase):
    """X1: the change under review must not silently set what the reviewer sees."""

    def settings(self, *extra: str) -> str:
        deny = ["Read(./private/**)", *extra, "Bash(rm:*)"]
        return json.dumps({"permissions": {"deny": deny}})

    def test_x1_a_branch_that_adds_a_read_deny_is_not_complete(self) -> None:
        box = self.sandbox(
            changed={
                "src/work.py": "w = 1\n",
                ".claude/settings.json": self.settings("Read(./tests/**)"),
            }
        )
        result = box.run()
        self.assertEqual(EXIT_INCOMPLETE, result.returncode, result.stdout)
        self.assertIn("Read(./tests/**)", header(result.stdout))

    def test_x1_a_branch_that_removes_a_read_deny_is_not_complete(self) -> None:
        box = self.sandbox(
            changed={"src/work.py": "w = 1\n", ".claude/settings.json": "{}"}
        )
        result = box.run()
        self.assertEqual(EXIT_INCOMPLETE, result.returncode, result.stdout)
        self.assertIn("Read(./private/**)", header(result.stdout))

    def test_x1_a_change_to_other_settings_is_complete(self) -> None:
        box = self.sandbox(
            changed={
                "src/work.py": "w = 1\n",
                ".claude/settings.json": self.settings("Bash(curl:*)"),
            }
        )
        result = box.run()
        self.assertEqual(EXIT_COMPLETE, result.returncode, result.stdout)

    def test_x1_the_header_records_the_forwarded_denies(self) -> None:
        result = self.sandbox().run()
        self.assertIn("Read(./private/**)", header(result.stdout))


class PythonFloorTests(IsolatedReviewCase):
    """
    #5: adopting projects run these scripts with whatever python3 they have.
    The formatter (target py311) turned `with a, b:` into the parenthesised
    form, which is a SyntaxError before 3.10 — the round-3 fix was undone by
    `ruff format` and nobody saw it.
    """

    FLOOR = "3.8"

    def old_python(self) -> str:
        found = subprocess.run(
            ["uv", "python", "find", "--no-project", self.FLOOR],
            capture_output=True,
            text=True,
        )
        path = found.stdout.strip()
        if found.returncode != 0 or not path:
            self.skipTest(f"no Python {self.FLOOR} (uv python install {self.FLOOR})")
        return path

    def test_5_run_review_and_field_report_run_on_the_floor(self) -> None:
        python = self.old_python()
        box = self.sandbox(changed={"src/a.py": "a = 1\n", "src/b.py": "b = 2\n"})
        result = box.run(scenario="coverage_no_read", python=python)
        self.assertEqual(EXIT_INCOMPLETE, result.returncode, result.stderr)
        report = subprocess.run(
            [python, str(box.root / ".claude/skills/isolated-review/field-report")],
            cwd=box.root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(0, report.returncode, report.stderr)
        self.assertIn("INCOMPLETE", report.stdout)

    def test_5_no_construct_the_floor_cannot_parse(self) -> None:
        # A tripwire for machines without the old interpreter: the two forms
        # that have already slipped in.
        for name in ("run-review", "field-report"):
            source = (SKILL / name).read_text(encoding="utf-8")
            with self.subTest(script=name):
                self.assertIsNone(re.search(r"^\s*with \(\s*$", source, re.M))
                self.assertNotIn(".removeprefix(", source)
                self.assertNotIn(".removesuffix(", source)


class FieldReportPrivacyTests(IsolatedReviewCase):
    """#6: without --include-paths, only known reason shapes leave the machine."""

    SECRETS = (
        "Makefile",
        "LICENSE",
        "pw12345",
        "example.com",
        "123456789012",
        "acme",
        "feature/secret-project",
    )

    def write_run(self, box: Sandbox, reasons: list[str], model: str) -> None:
        reports = box.root / RR.REPORT_REL
        reports.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Isolated review — FAILED",
            "",
            "- verdict: **FAILED** (never an approval)",
            *[f"- reason: {r}" for r in reasons],
            "- base: origin/main  merge-base: abc  HEAD: def  branch: feature/secret-project",
            "- changed: 2 files, 10 lines, diff inline",
            f"- model: {model}  cost: $1.00  time: 10s",
            "- transcript: .claude/logs/isolated-review/run1/",
        ]
        (reports / "feature-secret-project-20260930-120000.md").write_text(
            "\n".join(lines) + "\n\n---\n\n## Findings\nNone.\n", encoding="utf-8"
        )
        log = box.root / RR.LOG_REL / "run1"
        log.mkdir(parents=True, exist_ok=True)
        init = {
            "type": "system",
            "subtype": "init",
            "tools": ["Glob", "Grep", "Read", "mcp__acme_jira__search"],
            "slash_commands": [],
        }
        (log / "review.jsonl").write_text(json.dumps(init) + "\n", encoding="utf-8")
        refusals = [
            "HEAD is the merge-base with feature/secret-project: nothing to review",
            "the working tree must be clean (commit first): ['Makefile', 'LICENSE']",
            "git merge-base HEAD origin/acme failed: fatal: Not a valid object name",
            "claude is not on PATH",
            "an unknown shape mentioning acme",
        ]
        with (box.root / RR.LOG_REL / "refusals.jsonl").open("w") as handle:
            for reason in refusals:
                handle.write(json.dumps({"time": "t", "reason": reason}) + "\n")

    def field_report(self, box: Sandbox, *args: str) -> str:
        out = subprocess.run(
            [
                sys.executable,
                str(box.root / SKILL.relative_to(REPO) / "field-report"),
                *args,
            ],
            cwd=box.root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(0, out.returncode, out.stderr)
        return out.stdout

    def reasons(self) -> list[str]:
        return [
            "coverage: Makefile not listed",
            "coverage: LICENSE listed but never read",
            "run ended as error_during_execution: ['fetch https://u:pw12345@example.com/x']",
            "pinned model 'fable' did not run (modelUsage: ['arn:aws:bedrock:us-east-1:123456789012:m'])",
            "isolation: tools granted were ['Glob', 'Grep', 'Read', 'mcp__acme_jira__search'], expected ['Glob', 'Grep', 'Read']",
            "cli stderr: acme proxy said no",
            "something nobody anticipated about acme",
            "missing section: ## Tests",
            "timed out after 45 min — partial stream kept, not a verdict",
        ]

    def test_6_nothing_project_specific_leaves_without_include_paths(self) -> None:
        box = self.sandbox()
        self.write_run(box, self.reasons(), "arn:aws:bedrock:us-east-1:123456789012:m")
        text = self.field_report(box)
        for secret in self.SECRETS:
            with self.subTest(secret=secret):
                self.assertNotIn(secret, text)

    def test_6_known_safe_reasons_are_kept_whole(self) -> None:
        box = self.sandbox()
        self.write_run(box, self.reasons(), "claude-fable-5-1")
        text = self.field_report(box)
        for kept in (
            "missing section: ## Tests",
            "timed out after 45 min",
            "coverage: <path> not listed",
            "claude is not on PATH",
            "claude-fable-5-1",
            "Glob, Grep, Read",
            "tools granted were [Glob, Grep, Read, <mcp tool>]",
        ):
            with self.subTest(kept=kept):
                self.assertIn(kept, text)

    def test_6_include_paths_shows_them(self) -> None:
        box = self.sandbox()
        self.write_run(box, self.reasons(), "claude-fable-5-1")
        text = self.field_report(box, "--include-paths")
        self.assertIn("Makefile", text)
        self.assertIn("mcp__acme_jira__search", text)


class ReasonShapeDriftTests(IsolatedReviewCase):
    """
    field-report lets a reason out only in a shape it knows. A reason run-review
    starts to write without a matching shape is hidden — safe, but the field
    report loses it silently. This ties the two together: every reason these
    scenarios make must come through as more than <hidden>.
    """

    SCENARIOS = (
        "coverage_no_read",
        "coverage_missing",
        "init_bash",
        "init_slash",
        "probe_leak",
        "probe_same_twice",
        "empty_result",
        "not_completed",
        "budget",
        "missing_section",
        "wrong_model",
        "no_result",
        "startup_error",
        "startup_error_main",
        "bad_model_usage",
    )

    def test_16_every_reason_run_review_writes_has_a_known_shape(self) -> None:
        box = self.sandbox(changed={"src/a.py": "a = 1\n", "src/b.py": "b = 2\n"})
        # From stdout, not the report files: runs within one second share a
        # report name. modify_tree runs last; it leaves the tree dirty, so the
        # run after it is a refusal.
        reasons: list[str] = []
        for scenario in (*self.SCENARIOS, "modify_tree", "ok"):
            out = box.run(scenario=scenario).stdout
            reasons += [
                line[len("- reason: ") :]
                for line in out.splitlines()
                if line.startswith("- reason: ")
            ]
        log = box.root / RR.LOG_REL / "refusals.jsonl"
        reasons += [json.loads(x)["reason"] for x in log.read_text().splitlines()]
        self.assertGreater(len(reasons), len(self.SCENARIOS))
        field_report = load_field_report()
        for reason in reasons:
            with self.subTest(reason=reason):
                self.assertNotEqual(
                    field_report.HIDDEN, field_report.hide_reason(reason, False)
                )


class DocumentedNumbersTests(unittest.TestCase):
    """#11: the numbers the orchestrator quotes to the user are the script's."""

    def test_11_skill_md_states_the_scripts_ceilings_and_exit_codes(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        # Every occurrence, not one: SKILL.md quotes each ceiling more than
        # once, and a single stale copy is the one the user is asked about.
        budgets = re.findall(r"\$(\d+(?:\.\d+)?)", skill)
        minutes = re.findall(r"(\d+) ?(?:분|min)", skill)
        self.assertGreaterEqual(len(budgets), 2)
        self.assertGreaterEqual(len(minutes), 3)
        for found in budgets:
            self.assertEqual(RR.MAX_BUDGET_USD, float(found))
        for found in minutes:
            self.assertEqual(RR.MAX_TIMEOUT_MIN, float(found))
        self.assertIn(f"at most {RR.HARD_CAP_LINES}", skill)
        for verdict, code in RR.EXIT.items():
            with self.subTest(verdict=verdict):
                self.assertIn(f"| {code} | {verdict} |", skill)

    def test_x3_feature_tells_the_orchestrator_to_pass_the_base(self) -> None:
        feature = (REPO / ".claude/skills/feature/SKILL.md").read_text(encoding="utf-8")
        a1 = feature.split("**A1 — `/isolated-review`", 1)[1].split("**A2", 1)[0]
        self.assertIn("--base", a1)


class RoundFiveTests(IsolatedReviewCase):
    """Round-5 separate-session review, 2026-09-30. F-numbers are its findings."""

    def deny_rules(self, box: Sandbox) -> list[str]:
        argv = box.argv()
        return json.loads(argv[argv.index("--settings") + 1])["permissions"]["deny"]

    def test_f1_the_implementers_other_notes_are_denied(self) -> None:
        # /checkpointing writes the session's history to .agents/rules/AGENTS.md
        # too; nested CLAUDE.md files are context files like the root one.
        box = self.sandbox()
        box.run()
        deny = self.deny_rules(box)
        for rule in ("Read(./.agents/**)", "Read(./**/CLAUDE.md)"):
            with self.subTest(rule=rule):
                self.assertIn(rule, deny)

    def test_f2_kebab_case_names_quoted_as_evidence_are_kept(self) -> None:
        for text in (
            "the `--disk-cache-directory-path` flag is never validated",
            "class `task-runner-configuration-panel` is unused",
            "the mask-sensitive-fields-in-logs option",
            "`desk-notification-service-handler` has no resource limits",
            "the risk-assessment-matrix-v2 spreadsheet",
        ):
            with self.subTest(text=text):
                self.assertEqual((text, 0), RR.redact(text))
        key = "sk-" + "a1" * 12
        self.assertEqual(("key [REDACTED]", 1), RR.redact(f"key {key}"))

    def findings(self, body: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "feat-20260930-120000.md"
            report.write_text(
                "# Isolated review — COMPLETE\n\n---\n\n## Findings\n"
                + body
                + "\n\n## Tests\n- x — high\n",
                encoding="utf-8",
            )
            return load_field_report().parse_report(report)["confidences"]

    def test_f3_field_report_counts_findings_in_every_common_form(self) -> None:
        cases = {
            "- `a.py:1` — breaks — high\n- `b.py:2` — breaks — low": ["high", "low"],
            "1. `a.py:1` — breaks — high\n2. `b.py:2` — breaks — low": ["high", "low"],
            "- `a.py:1` — breaks — confidence: high\n- `b.py:2` — breaks (medium)": [
                "high",
                "medium",
            ],
            "- `a.py:1` — bad input\n  produces wrong output — high": ["high"],
            "- **`a.py:1`** — breaks — **high**": ["high"],
            "* `a.py:1` — slow path is low priority — medium": ["medium"],
            "None found.": [],
        }
        for body, expected in cases.items():
            with self.subTest(body=body):
                self.assertEqual(expected, self.findings(body))

    def test_f3_the_prompt_fixes_the_finding_line_format(self) -> None:
        prompt = " ".join((SKILL / "prompt.md").read_text(encoding="utf-8").split())
        self.assertIn("one line starting with `- `", prompt)
        self.assertIn("ending in `— high`, `— medium` or `— low`", prompt)

    def test_f4_an_ignored_file_under_claude_changed_mid_run_is_invalid(self) -> None:
        # Invisible to `git status`: only the content hash of .claude/ sees it.
        result = self.sandbox().run(scenario="modify_ignored_claude_file")
        self.assertEqual(EXIT_INVALID, result.returncode, result.stdout)

    def test_f6_a_probe_granted_bash_stops_the_review(self) -> None:
        box = self.sandbox()
        result = box.run(scenario="probe_bash")
        self.assertEqual(EXIT_FAILED, result.returncode, result.stdout)
        self.assertIn("probe isolation", result.stdout)
        self.assertFalse((box.log / "main.argv.json").exists(), "reviewer ran anyway")

    def test_f6_the_last_coverage_heading_is_the_section(self) -> None:
        result = self.sandbox().run(scenario="two_coverage")
        self.assertEqual(EXIT_COMPLETE, result.returncode, result.stdout)

    def test_f6_a_heading_with_trailing_words_is_not_the_heading(self) -> None:
        result = self.sandbox().run(scenario="heading_trailing")
        self.assertEqual(EXIT_FAILED, result.returncode, result.stdout)
        self.assertIn("missing section: ## Tests", result.stdout)

    def test_f6_a_detached_head_report_is_named_detached(self) -> None:
        box = self.sandbox()
        subprocess.run(["git", "checkout", "-q", "--detach"], cwd=box.root, check=True)
        box.run()
        [report] = box.reports()
        self.assertTrue(report.name.startswith("detached-"), report.name)

    def test_f6_the_plan_stops_at_the_next_subheading(self) -> None:
        box = self.sandbox(
            claude_md="# P\n\n## Current Project: x\n\n### Verification plan\n"
            "| V1 | adds work |\n\n### Decisions\n- trust me\n"
        )
        box.run()
        self.assertIn("V1", box.stdin())
        self.assertNotIn("trust me", box.stdin())

    def test_f7_a_colour_config_does_not_reach_the_reviewer(self) -> None:
        box = self.sandbox()
        subprocess.run(
            ["git", "config", "color.ui", "always"], cwd=box.root, check=True
        )
        box.run()
        self.assertNotIn("\x1b[", box.stdin())

    def test_f9_a_temp_dir_inside_the_repository_is_refused(self) -> None:
        # The "outside" canary would sit inside the working directory, be
        # readable, and fail every run with a misleading probe reason.
        box = self.sandbox()
        inside = box.root / "tmp-inside"
        inside.mkdir()
        result = box.run(extra_env={"TMPDIR": str(inside)})
        self.assertEqual(EXIT_REFUSED, result.returncode, result.stderr)
        self.assertIn("TMPDIR", result.stderr)

    def test_f11_skill_md_says_grep_counts_as_reading(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        row = next(x for x in skill.splitlines() if x.startswith("| 0 | COMPLETE |"))
        self.assertIn("Grep", row)

    def test_f12_field_report_judges_the_probe_like_run_review(self) -> None:
        box = self.sandbox()
        box.run(scenario="probe_same_twice")
        out = subprocess.run(
            [sys.executable, str(FIELD_REPORT)],
            cwd=box.root,
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout
        row = next(line for line in out.splitlines() if line.startswith("| 1 |"))
        self.assertNotEqual("passed", row.split("|")[12].strip(), row)


if __name__ == "__main__":
    unittest.main()
