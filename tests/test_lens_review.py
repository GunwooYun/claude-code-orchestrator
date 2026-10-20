"""
Tests for .claude/skills/lens-review/lens-review and the lens-reviewer agent.

The script is the part of /lens-review that must not depend on how the main
session reads or retypes text: the scope, the prompts, the report. Scenario IDs
are those of the plan (docs/lens-review.md, "Verification").
"""

from __future__ import annotations

import ast
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

REPO = Path(__file__).parent.parent
SKILL = REPO / ".claude" / "skills" / "lens-review"
SCRIPT = SKILL / "lens-review"
AGENT = REPO / ".claude" / "agents" / "lens-reviewer.md"
RUN_REVIEW = REPO / ".claude" / "skills" / "isolated-review" / "run-review"
LENSES = ("correctness", "security", "integration", "tests", "simplicity")
FIXTURES = Path(__file__).parent / "fixtures" / "lens-review"


def load(path: Path, name: str) -> ModuleType:
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


lr = load(SCRIPT, "lens_review")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def run_script(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


class Repo:
    """origin (bare) + a clone: `main` pushed, `feat` three commits ahead."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        top = Path(self._tmp.name)
        self.origin = top / "origin.git"
        self.root = top / "repo"
        git(top, "init", "-q", "--bare", "-b", "main", str(self.origin))
        git(top, "clone", "-q", str(self.origin), str(self.root))
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "t")
        git(self.root, "checkout", "-q", "-b", "main")
        (self.root / ".gitignore").write_text(".claude/logs/\n.claude/docs/reviews/\n")
        (self.root / ".claude" / "rules").mkdir(parents=True)
        (self.root / ".claude" / "rules" / "security.md").write_text("# rule\n")
        self.write("base.py", "x = 1\n")
        self.write("old_name.py", "def f():\n    return 1\n")
        self.write("gone.py", "y = 2\n")
        self.commit("base")
        git(self.root, "push", "-q", "-u", "origin", "main")
        git(self.root, "checkout", "-q", "-b", "feat")

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message: str) -> str:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", message)
        return git(self.root, "rev-parse", "HEAD").strip()

    def three_commits(self) -> None:
        self.write("a.py", "a = 1\n")
        self.commit("one")
        self.write("b.py", "b = 1\n")
        self.commit("two")
        self.write("c.py", "c = 1\n")
        self.commit("three")

    def scope(self, *args: str) -> tuple[subprocess.CompletedProcess[str], dict | None]:
        done = run_script(self.root, "scope", *args)
        match = re.search(r"^run: (\S+)", done.stdout, re.MULTILINE)
        data = None
        if match:
            data = json.loads((self.root / match.group(1) / "scope.json").read_text())
        return done, data

    def close(self) -> None:
        self._tmp.cleanup()


class ScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()
        self.addCleanup(self.repo.close)

    def paths(self, data: dict) -> set[str]:
        return {f["path"] for f in data["files"]}

    def test_scope_committed_covers_the_whole_branch_not_one_commit(self) -> None:
        """V1"""
        self.repo.three_commits()
        done, data = self.repo.scope("--base", "main")
        self.assertEqual(0, done.returncode, done.stderr)
        assert data is not None
        self.assertEqual("committed", data["mode"])
        self.assertEqual({"a.py", "b.py", "c.py"}, self.paths(data))
        diff = (self.repo.root / data["diff"]).read_text()
        for name in ("a.py", "b.py", "c.py"):
            self.assertIn(f"+++ b/{name}", diff)

    def test_scope_dirty_tree_becomes_worktree_mode_with_untracked(self) -> None:
        """V2"""
        self.repo.three_commits()
        self.repo.write("a.py", "a = 2\n")
        self.repo.write("new_untracked.py", "z = 1\n")
        done, data = self.repo.scope("--base", "main")
        self.assertEqual(0, done.returncode, done.stderr)
        assert data is not None
        self.assertEqual("worktree", data["mode"])
        self.assertEqual(["new_untracked.py"], data["untracked"])
        self.assertIn("new_untracked.py", self.paths(data))
        diff = (self.repo.root / data["diff"]).read_text()
        self.assertIn("+a = 2", diff)
        self.assertIn("+z = 1", diff)
        self.assertIn("untracked", done.stdout)

    def test_scope_bare_base_means_origin_copy(self) -> None:
        """V3: a stale local main must not widen the range."""
        git(self.repo.root, "branch", "-f", "main", "HEAD")  # local main == feat start
        self.repo.write("a.py", "a = 1\n")
        self.repo.commit("one")
        git(self.repo.root, "push", "-q", "origin", "feat:main")  # origin/main moves
        git(self.repo.root, "fetch", "-q")
        self.repo.write("b.py", "b = 1\n")
        self.repo.commit("two")
        done, data = self.repo.scope("--base", "main")
        self.assertEqual(0, done.returncode, done.stderr)
        assert data is not None
        self.assertEqual("origin/main", data["base"])
        self.assertEqual({"b.py"}, self.paths(data))

    def test_scope_unknown_base_is_refused(self) -> None:
        """V3"""
        self.repo.three_commits()
        done, data = self.repo.scope("--base", "no-such-branch")
        self.assertEqual(2, done.returncode)
        self.assertIsNone(data)
        self.assertIn("refused", done.stderr)

    def test_scope_without_change_is_refused_and_writes_nothing(self) -> None:
        """V4"""
        done, data = self.repo.scope("--base", "main")
        self.assertEqual(2, done.returncode)
        self.assertIn("no change", done.stderr)
        self.assertFalse((self.repo.root / ".claude" / "logs").exists())

    def test_scope_ignores_its_own_and_review_output(self) -> None:
        """V4: a leftover run dir or report is not a change to review."""
        (self.repo.root / ".claude/docs/reviews").mkdir(parents=True)
        (self.repo.root / ".claude/docs/reviews/x.md").write_text("r\n")
        (self.repo.root / ".claude/logs/lens-review/old").mkdir(parents=True)
        done, _ = self.repo.scope("--base", "main", "--mode", "worktree")
        self.assertEqual(2, done.returncode, done.stdout)

    def test_scope_edge_cases_rename_delete_binary(self) -> None:
        """V-edge"""
        git(self.repo.root, "mv", "old_name.py", "new_name.py")
        git(self.repo.root, "rm", "-q", "gone.py")
        (self.repo.root / "blob.bin").write_bytes(b"\0\1\2" * 100)
        self.repo.commit("edges")
        done, data = self.repo.scope("--base", "main")
        self.assertEqual(0, done.returncode, done.stderr)
        assert data is not None
        status = {f["path"]: f["status"] for f in data["files"]}
        self.assertEqual("R", status["new_name.py"])
        self.assertEqual("D", status["gone.py"])
        self.assertEqual("A", status["blob.bin"])
        self.assertNotIn("old_name.py", status)

    def test_scope_base_as_sha_and_full_ref_and_detached(self) -> None:
        """V-edge"""
        start = git(self.repo.root, "rev-parse", "origin/main").strip()
        self.repo.three_commits()
        for base in (start, "refs/heads/main"):
            done, data = self.repo.scope("--base", base)
            self.assertEqual(0, done.returncode, (base, done.stderr))
            assert data is not None
            self.assertEqual({"a.py", "b.py", "c.py"}, self.paths(data))
        git(self.repo.root, "checkout", "-q", "--detach")
        done, data = self.repo.scope("--base", "main")
        self.assertEqual(0, done.returncode, done.stderr)
        assert data is not None
        self.assertEqual("detached", data["branch"])

    def test_scope_untracked_only_is_a_change(self) -> None:
        """V-edge"""
        self.repo.write("only_new.py", "n = 1\n")
        done, data = self.repo.scope("--base", "main")
        self.assertEqual(0, done.returncode, done.stderr)
        assert data is not None
        self.assertEqual("worktree", data["mode"])
        self.assertEqual({"only_new.py"}, self.paths(data))

    def test_scope_over_cap_writes_scope_then_refuses(self) -> None:
        """V-edge"""
        self.repo.write("big.py", "".join(f"v{i} = {i}\n" for i in range(3100)))
        self.repo.commit("big")
        done, data = self.repo.scope("--base", "main")
        self.assertEqual(2, done.returncode)
        self.assertIn("cap", done.stderr)
        runs = list((self.repo.root / ".claude/logs/lens-review").iterdir())
        self.assertEqual(1, len(runs))
        saved = json.loads((runs[0] / "scope.json").read_text())
        self.assertTrue(saved["over_cap"])
        self.assertIsNone(data)

    def test_scope_paths_narrow_the_change(self) -> None:
        """V-edge"""
        self.repo.three_commits()
        done, data = self.repo.scope("--base", "main", "--paths", "a.py")
        self.assertEqual(0, done.returncode, done.stderr)
        assert data is not None
        self.assertEqual({"a.py"}, self.paths(data))


class SharedGitHelperTests(unittest.TestCase):
    """The copied helper keeps run-review's behaviour (drift guard)."""

    def function_source(self, path: Path, name: str) -> str:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                node.body = [
                    n
                    for n in node.body
                    if not (
                        isinstance(n, ast.Expr)
                        and isinstance(n.value, ast.Constant)
                        and isinstance(n.value.value, str)
                    )
                ]
                return ast.dump(node)
        raise AssertionError(f"{name} not found in {path}")

    def test_resolve_base_matches_run_review(self) -> None:
        self.assertEqual(
            self.function_source(RUN_REVIEW, "resolve_base"),
            self.function_source(SCRIPT, "resolve_base"),
        )


def make_run(tmp: Path, files: list[str] | None = None) -> Path:
    run = tmp / ".claude/logs/lens-review/r1"
    run.mkdir(parents=True)
    scope = {
        "base_arg": "main",
        "base": "origin/main",
        "merge_base": "a" * 40,
        "head": "b" * 40,
        "branch": "feat",
        "mode": "committed",
        "paths": [],
        "files": [{"status": "M", "path": p, "lines": 3} for p in (files or ["x.py"])],
        "untracked": [],
        "lines": 3,
        "over_cap": False,
        "diff": ".claude/logs/lens-review/r1/diff.patch",
        "run": ".claude/logs/lens-review/r1",
    }
    (run / "scope.json").write_text(json.dumps(scope))
    return run


FINDING = """### F1
severity: major
location: x.py:3
claim: The loop skips the last item.
failure: For [1, 2], only 1 is processed.
evidence: `for i in range(len(items) - 1)`
confidence: high
"""


class PromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / ".claude/rules").mkdir(parents=True)
        (self.root / ".claude/rules/testing.md").write_text("r")
        self.run_dir = make_run(self.root, ["x.py", "y.py"])

    def template(self, name: str) -> str:
        return (SKILL / "prompts" / name).read_text(encoding="utf-8")

    def test_lens_prompt_is_the_template_with_only_scope_filled(self) -> None:
        """V6"""
        text = lr.lens_prompt(self.root, self.run_dir, "tests")
        body = (SKILL / "prompts/lenses/tests.md").read_text().strip()
        # Rebuild by hand: every token replaced, nothing else added.
        expected = self.template("lens.md")
        for token, value in {
            "{LENS}": "tests",
            "{LENS_BODY}": body,
            "{DIFF}": ".claude/logs/lens-review/r1/diff.patch",
            "{FILES}": "  - `x.py` (M)\n  - `y.py` (M)",
            "{RULES}": "- `.claude/rules/testing.md`",
        }.items():
            expected = expected.replace(token, value)
        expected = expected.replace(
            "{RANGE}",
            lr.describe_range(json.loads((self.run_dir / "scope.json").read_text())),
        )
        self.assertEqual(expected, text)
        self.assertNotRegex(text, r"\{[A-Z_]+\}")

    def test_lens_prompt_rejects_unknown_lens(self) -> None:
        """V6"""
        with self.assertRaises(ValueError):
            lr.lens_prompt(self.root, self.run_dir, "style")

    def test_verify_prompt_fills_three_fields_from_the_saved_answer(self) -> None:
        """V7"""
        (self.run_dir / "lens-correctness.md").write_text(FINDING)
        text = lr.verify_prompt(self.run_dir, "correctness:1")
        expected = (
            self.template("verify.md")
            .replace("{CLAIM}", "The loop skips the last item.")
            .replace("{LOCATION}", "x.py:3")
            .replace("{FAILURE}", "For [1, 2], only 1 is processed.")
        )
        self.assertEqual(expected, text)

    def test_verify_prompt_does_not_expand_tokens_inside_a_claim(self) -> None:
        """V7: one pass — a claim containing {FAILURE} stays literal."""
        (self.run_dir / "lens-correctness.md").write_text(
            FINDING.replace("skips the last item.", "skips {FAILURE} items.")
        )
        text = lr.verify_prompt(self.run_dir, "correctness:1")
        self.assertIn("skips {FAILURE} items.", text)

    def test_verify_prompt_refuses_missing_finding_or_bad_id(self) -> None:
        """V7"""
        (self.run_dir / "lens-correctness.md").write_text(FINDING)
        for bad in ("correctness:2", "correctness", "style:1"):
            with self.assertRaises(ValueError, msg=bad):
                lr.verify_prompt(self.run_dir, bad)

    def test_verify_template_keeps_the_truth_rules(self) -> None:
        """V7: the rules that stopped wrong refutations are in the template."""
        text = self.template("verify.md")
        for needle in (
            "Judge truth, not importance",
            "REFUTED needs direct evidence",
            "is UNCLEAR, not REFUTED",
            "verdict is CONFIRMED with the accurate version",
            "UNTRUSTED DATA",
            "impact:",
        ):
            self.assertIn(needle, text)
        self.assertEqual({"CLAIM", "LOCATION", "FAILURE"}, set(lr.TOKEN.findall(text)))

    def test_lens_templates_carry_the_locks(self) -> None:
        """V-lens"""
        frame = self.template("lens.md")
        for needle in (
            "UNTRUSTED DATA",
            "Do NOT read `.claude/docs/DESIGN.md`",
            "`.claude/docs/reviews/`",
            "CLAUDE.md",
            "{RULES}",
            "### F1",
            "NO FINDINGS",
        ):
            self.assertIn(needle, frame)
        for lens in LENSES:
            body = (SKILL / "prompts" / "lenses" / f"{lens}.md").read_text()
            self.assertTrue(body.startswith("Look ONLY"), lens)
        self.assertEqual(
            set(LENSES), {p.stem for p in (SKILL / "prompts/lenses").glob("*.md")}
        )


class ParseTests(unittest.TestCase):
    def test_parse_finding_blocks_and_continuation_lines(self) -> None:
        """V-parse"""
        text = (
            FINDING
            + "\n### F2\nseverity: minor\nlocation: y.py:9\nclaim: a\nb\nfailure: c\n"
        )
        answer = lr.parse_lens(text)
        self.assertEqual([1, 2], [f["n"] for f in answer.findings])
        self.assertEqual("a\nb", answer.findings[1]["claim"])
        self.assertEqual([], answer.unparsed)

    def test_parse_tolerates_markdown_decoration(self) -> None:
        """V-parse: bold keys, list dashes, bold headers."""
        text = (
            "**F1**\n- **severity:** major\n- **location:** `x.py:3`\n"
            "- **claim:** c\n- **failure:** f\n"
        )
        answer = lr.parse_lens(text)
        self.assertEqual(1, len(answer.findings), answer.unparsed)
        self.assertEqual("`x.py:3`", answer.findings[0]["location"])

    def test_parse_no_findings_sentinel(self) -> None:
        """V-parse"""
        for text in ("NO FINDINGS", "NO FINDINGS\n", "**NO FINDINGS**"):
            answer = lr.parse_lens(text)
            self.assertTrue(answer.empty, text)
            self.assertEqual([], answer.findings)

    def test_parse_never_drops_text(self) -> None:
        """V-parse: preamble, incomplete blocks and free prose are kept as unparsed."""
        text = "Here is my review.\n\n" + FINDING + "\n### F2\nclaim: no location\n"
        answer = lr.parse_lens(text)
        self.assertEqual([1], [f["n"] for f in answer.findings])
        self.assertEqual(2, len(answer.unparsed))
        self.assertIn("Here is my review.", answer.unparsed[0])
        self.assertIn("no location", answer.unparsed[1])
        prose = lr.parse_lens("The code looks fine but x.py:3 skips an item.")
        self.assertEqual([], prose.findings)
        self.assertEqual(1, len(prose.unparsed))

    def test_parse_recorded_answers(self) -> None:
        """V-parse: real lens answers recorded in rehearsals parse completely."""
        cases = sorted(FIXTURES.glob("*.md")) if FIXTURES.exists() else []
        for path in cases:
            expected = int(path.stem.rsplit("-", 1)[-1])  # name ends in -<count>
            answer = lr.parse_lens(path.read_text(encoding="utf-8"))
            self.assertEqual(expected, len(answer.findings), path.name)
            self.assertEqual([], answer.unparsed, path.name)

    def test_parse_verdict_variants(self) -> None:
        """V8b"""
        self.assertEqual(
            "CONFIRMED", lr.parse_verdict("verdict: CONFIRMED\n")["verdict"]
        )
        self.assertEqual(
            "REFUTED", lr.parse_verdict("**verdict:** **REFUTED**\n")["verdict"]
        )
        self.assertEqual(
            "UNVERIFIED", lr.parse_verdict("I think it is fine.")["verdict"]
        )
        self.assertEqual("UNVERIFIED", lr.parse_verdict(None)["verdict"])
        self.assertEqual("UNVERIFIED", lr.parse_verdict("verdict: MAYBE\n")["verdict"])


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.run_dir = make_run(self.root)
        for lens in LENSES:
            (self.run_dir / f"lens-{lens}.md").write_text("NO FINDINGS\n")

    def lens(self, name: str, text: str) -> None:
        (self.run_dir / f"lens-{name}.md").write_text(text)

    def verdict(self, name: str, n: int, text: str) -> None:
        (self.run_dir / f"verify-{name}-{n}.md").write_text(text)

    def sections(self, text: str) -> dict[str, str]:
        parts = re.split(r"^## ", text, flags=re.MULTILINE)
        return {p.split("\n", 1)[0]: p for p in parts[1:]}

    def test_report_moves_refuted_out_of_findings(self) -> None:
        """V8"""
        self.lens(
            "correctness",
            FINDING + FINDING.replace("F1", "F2").replace("x.py:3", "x.py:9"),
        )
        self.verdict("correctness", 1, "verdict: CONFIRMED\nimpact: low\n")
        self.verdict("correctness", 2, "verdict: REFUTED\nevidence: x.py:8 guards it\n")
        text, complete = lr.build_report(self.run_dir)
        self.assertTrue(complete)
        parts = self.sections(text)
        self.assertIn("`x.py:3`", parts["Findings"])
        self.assertNotIn("x.py:9", parts["Findings"])
        self.assertIn("x.py:9", parts["Refuted"])
        self.assertIn("x.py:8 guards it", parts["Refuted"])
        self.assertIn("CONFIRMED 1, REFUTED 1, UNCLEAR 0, UNVERIFIED 0", text)

    def test_report_orders_by_verdict_then_impact_and_labels_unclear(self) -> None:
        """V8"""
        blocks = "".join(
            FINDING.replace("F1", f"F{n}").replace("x.py:3", f"x.py:{n}")
            for n in (1, 2, 3)
        )
        self.lens("tests", blocks)
        self.verdict("tests", 1, "verdict: CONFIRMED\nimpact: none\n")
        self.verdict("tests", 2, "verdict: UNCLEAR\nimpact: low\n")
        self.verdict(
            "tests", 3, "verdict: CONFIRMED\nimpact: hit in normal use — users\n"
        )
        text, _ = lr.build_report(self.run_dir)
        findings = self.sections(text)["Findings"]
        order = [m.group(1) for m in re.finditer(r"`x\.py:(\d)`", findings)]
        self.assertEqual(["3", "1", "2"], order)
        self.assertIn("— UNCLEAR", findings)
        self.assertIn("impact: hit in normal use — users", findings)

    def test_report_groups_same_location_across_lenses(self) -> None:
        """V8"""
        self.lens("correctness", FINDING)
        self.lens("tests", FINDING)
        self.verdict("correctness", 1, "verdict: CONFIRMED\n")
        self.verdict("tests", 1, "verdict: CONFIRMED\n")
        text, _ = lr.build_report(self.run_dir)
        self.assertEqual(2, text.count("also reported by another lens"))

    def test_report_without_verdict_is_written_and_incomplete(self) -> None:
        """V8b"""
        self.lens("security", FINDING)
        text, complete = lr.build_report(self.run_dir)
        self.assertFalse(complete)
        self.assertIn("— UNVERIFIED", self.sections(text)["Findings"])
        self.assertIn("security F1: no verdict", self.sections(text)["Incomplete"])

    def test_report_with_missing_or_unparsed_answer_is_incomplete(self) -> None:
        """V8b"""
        (self.run_dir / "lens-simplicity.md").unlink()
        self.lens("integration", "Looks fine to me.")
        text, complete = lr.build_report(self.run_dir)
        self.assertFalse(complete)
        parts = self.sections(text)
        self.assertIn("Looks fine to me.", parts["Unparsed"])
        self.assertIn("simplicity: no answer saved", parts["Incomplete"])

    def test_report_cli_writes_a_new_file_and_exits_3_when_incomplete(self) -> None:
        """V5 + V8b through the command line."""
        git(self.root, "init", "-q")
        self.lens("security", FINDING)
        first = run_script(self.root, "report", "--run", ".claude/logs/lens-review/r1")
        second = run_script(self.root, "report", "--run", ".claude/logs/lens-review/r1")
        self.assertEqual(3, first.returncode, first.stderr)
        self.assertNotEqual(first.stdout.strip(), second.stdout.strip())
        for done in (first, second):
            path = self.root / done.stdout.strip()
            self.assertTrue(path.name.startswith("lens-feat-"), path)
            self.assertEqual(
                ".claude/docs/reviews", path.parent.relative_to(self.root).as_posix()
            )


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
                    "message": {"content": [{"type": "text", "text": answer}]},
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
        saved, missing = lr.collect(self.root, self.run_dir)
        self.assertEqual(5, len(saved))
        self.assertEqual(["verify-tests-1.md"], missing)
        self.assertEqual(
            FINDING.strip() + "\n", (self.run_dir / "lens-tests.md").read_text()
        )
        self.agent(lr.verify_prompt(self.run_dir, "tests:1"), "verdict: CONFIRMED")
        saved, missing = lr.collect(self.root, self.run_dir)
        self.assertIn("verify-tests-1.md", saved)
        self.assertEqual([], missing)

    def test_collect_skips_a_changed_prompt_and_an_unfinished_agent(self) -> None:
        self.agent(
            lr.lens_prompt(self.root, self.run_dir, "security") + "\nBe brief.",
            "NO FINDINGS",
        )
        self.agent(
            lr.lens_prompt(self.root, self.run_dir, "tests"), "partial", tool_last=True
        )
        saved, missing = lr.collect(self.root, self.run_dir)
        self.assertEqual([], saved)
        self.assertIn("lens-security.md", missing)
        self.assertIn("lens-tests.md", missing)

    def test_collect_ignores_other_sessions(self) -> None:
        other = self.config / "projects" / "-repo" / "other" / "subagents"
        other.mkdir(parents=True)
        prompt = lr.lens_prompt(self.root, self.run_dir, "security")
        rows = [
            {"type": "user", "message": {"content": prompt}},
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "NO FINDINGS"}]},
            },
        ]
        (other / "agent-x.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
        saved, _ = lr.collect(self.root, self.run_dir)
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
        report_text, _ = lr.build_report(self.run_dir)
        self.report = lr.write_report_file(self.root, "feat", report_text)
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
    ) -> None:
        rows = []
        for i, (prompt, answer) in enumerate(self.calls()):
            if i == len(LENSES):  # the verifier call
                prompt += prompt_edit
            tool_id = f"toolu_{i}"
            rows.append(
                {
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
            )
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
            agent_rows.append(
                {
                    "type": "assistant",
                    "effort": effort,
                    "message": {
                        "model": "claude-opus-5-5",
                        "content": [{"type": "text", "text": answer}],
                    },
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
                            "text": self.findings if shown is None else shown,
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


class AgentTests(unittest.TestCase):
    def frontmatter(self) -> dict[str, str]:
        text = AGENT.read_text(encoding="utf-8")
        head = text.split("---", 2)[1]
        return {
            m.group(1): m.group(2).strip()
            for m in re.finditer(r"^(\w+):\s*(.*)$", head, re.MULTILINE)
        }

    def test_agent_is_locked_to_reading_with_opus_medium(self) -> None:
        """V9"""
        fm = self.frontmatter()
        self.assertEqual("lens-reviewer", fm["name"])
        self.assertEqual(
            {"Read", "Grep", "Glob"}, {t.strip() for t in fm["tools"].split(",")}
        )
        self.assertEqual("opus", fm["model"])
        self.assertEqual("medium", fm["effort"])
        self.assertEqual("true", fm["omitClaudeMd"])
        self.assertNotIn("DESIGN.md", AGENT.read_text(encoding="utf-8"))


class SkillWiringTests(unittest.TestCase):
    def test_skill_names_files_that_exist_and_is_user_invoked(self) -> None:
        """V10"""
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("disable-model-invocation: true", text)
        self.assertIn("python3 .claude/skills/lens-review/lens-review", text)
        self.assertIn("subagent_type", text)
        self.assertIn("lens-reviewer", text)
        for lens in LENSES:
            self.assertIn(lens, text)

    def test_script_is_in_the_quality_gate(self) -> None:
        """V10"""
        text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
        for task in ("lint", "format-check", "typecheck"):
            line = re.search(rf"^{task} = .*$", text, re.MULTILINE)
            assert line is not None, task
            self.assertIn(".claude/skills/lens-review/lens-review", line.group(0), task)

    def test_feature_phase_6_offers_the_lens_review(self) -> None:
        """V10"""
        text = (REPO / ".claude/skills/feature/SKILL.md").read_text(encoding="utf-8")
        phase6 = text.split("## Phase 6", 1)[1]
        self.assertIn("/lens-review", phase6)


if __name__ == "__main__":
    unittest.main()
