"""
Versioning: which orchestrator a project adopted must be visible in the project.

Adopting projects copy `.claude/` (README Quick Start), so the version has to
live inside it: `.claude/ORCHESTRATOR_VERSION`. `CHANGELOG.md` stays at the
repository root and is read over the network only when asked
(`/orchestrator-version --check-latest`) — company networks may block GitHub.

Most checks here are behavioural (the check script against a local stand-in for
the upstream repository). The README and /initproject checks are each a
drift tripwire over prose, not behavioural coverage.
"""

from __future__ import annotations

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

REPO = Path(__file__).parent.parent
VERSION_FILE = REPO / ".claude" / "ORCHESTRATOR_VERSION"
CHANGELOG = REPO / "CHANGELOG.md"
CHECK = REPO / ".claude" / "skills" / "orchestrator-version" / "check"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

FIXTURE_CHANGELOG = """# Changelog

## [0.2.0] - 2026-10-10

### Added
- NEW-IN-0.2.0 isolated review.

## [0.1.0] - 2026-09-30

### Added
- OLD-IN-0.1.0 first release.
"""


def changelog_versions(text: str) -> list[str]:
    return re.findall(r"^## \[(\d+\.\d+\.\d+)\]", text, re.MULTILINE)


class VersionRecordTests(unittest.TestCase):
    def test_the_version_file_ships_inside_claude_and_is_semver(self) -> None:
        self.assertTrue(
            VERSION_FILE.is_file(), "adopters copy .claude/, so it must live there"
        )
        self.assertRegex(VERSION_FILE.read_text(encoding="utf-8").strip(), SEMVER)

    def test_the_changelog_top_entry_is_the_shipped_version(self) -> None:
        versions = changelog_versions(CHANGELOG.read_text(encoding="utf-8"))
        self.assertTrue(versions, "no `## [x.y.z]` entry in CHANGELOG.md")
        self.assertEqual(VERSION_FILE.read_text(encoding="utf-8").strip(), versions[0])

    def test_changelog_entries_are_newest_first_and_unique(self) -> None:
        versions = changelog_versions(CHANGELOG.read_text(encoding="utf-8"))
        keys = [tuple(int(p) for p in v.split(".")) for v in versions]
        self.assertEqual(sorted(keys, reverse=True), keys)
        self.assertEqual(len(set(keys)), len(keys))

    def test_unreleased_is_at_most_one_section_above_every_release(self) -> None:
        # A release renames it; one left below a version entry would be read as
        # part of that release by /orchestrator-version.
        text = CHANGELOG.read_text(encoding="utf-8")
        unreleased = [m.start() for m in re.finditer(r"^## \[Unreleased\]", text, re.M)]
        self.assertLessEqual(len(unreleased), 1)
        first_release = re.search(r"^## \[\d+\.\d+\.\d+\]", text, re.M)
        if unreleased and first_release:
            self.assertLess(unreleased[0], first_release.start())


class CheckScriptTests(unittest.TestCase):
    """The check script against a local stand-in for the upstream repository."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        # An adopting project's copy: only .claude/ travels.
        self.project = self.tmp / "project"
        (self.project / ".claude/skills").mkdir(parents=True)
        shutil.copytree(
            CHECK.parent, self.project / ".claude/skills/orchestrator-version"
        )
        (self.project / ".claude/ORCHESTRATOR_VERSION").write_text(
            "0.1.0\n", encoding="utf-8"
        )
        # Upstream: a bare repo with release tags, and its changelog.
        self.upstream = self.tmp / "upstream.git"
        work = self.tmp / "work"
        for args in (
            ["init", "-q", "--bare", str(self.upstream)],
            ["init", "-q", str(work)],
        ):
            subprocess.run(["git", *args], check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(work),
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                "x",
                "-c",
                "user.email=t@e",
                "-c",
                "user.name=t",
            ],
            capture_output=True,
        )
        self.git_work = work
        self.changelog = self.tmp / "CHANGELOG.md"
        self.changelog.write_text(FIXTURE_CHANGELOG, encoding="utf-8")

    def tag_upstream(self, *tags: str) -> None:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@e",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@e",
        }
        subprocess.run(
            [
                "git",
                "-C",
                str(self.git_work),
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                "release",
            ],
            check=True,
            env=env,
        )
        for tag in tags:
            subprocess.run(["git", "-C", str(self.git_work), "tag", tag], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.git_work),
                "push",
                "-q",
                str(self.upstream),
                "--tags",
            ],
            check=True,
            capture_output=True,
        )

    def check(
        self, *args: str, upstream: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["ORCHESTRATOR_UPSTREAM"] = upstream or str(self.upstream)
        env["ORCHESTRATOR_CHANGELOG_URL"] = self.changelog.as_uri()
        return subprocess.run(
            [
                sys.executable,
                str(self.project / ".claude/skills/orchestrator-version/check"),
                *args,
            ],
            cwd=self.project,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

    def test_offline_shows_the_installed_version_and_touches_no_network(self) -> None:
        result = self.check(upstream="/nonexistent/should-not-be-contacted")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("installed: 0.1.0", result.stdout)
        self.assertIn("--check-latest", result.stdout)
        self.assertNotIn("unavailable", result.stdout)

    def test_a_copy_without_the_file_is_called_pre_versioning(self) -> None:
        (self.project / ".claude/ORCHESTRATOR_VERSION").unlink()
        result = self.check()
        self.assertEqual(0, result.returncode)
        self.assertIn("installed: unknown", result.stdout)
        self.assertIn("before v0.1.0", result.stdout)

    def test_newer_release_is_reported_with_only_the_newer_changes(self) -> None:
        self.tag_upstream("v0.1.0", "v0.2.0", "not-a-version")
        result = self.check("--check-latest")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("latest: 0.2.0", result.stdout)
        self.assertIn("NEW-IN-0.2.0", result.stdout)
        self.assertNotIn("OLD-IN-0.1.0", result.stdout)

    def test_up_to_date_is_said_plainly(self) -> None:
        self.tag_upstream("v0.1.0")
        result = self.check("--check-latest")
        self.assertIn("latest: 0.1.0", result.stdout)
        self.assertIn("up to date", result.stdout)

    def test_an_unreachable_upstream_is_reported_not_raised(self) -> None:
        result = self.check("--check-latest", upstream="/nonexistent/upstream.git")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("latest: unavailable", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_versions_compare_numerically_not_as_text(self) -> None:
        self.tag_upstream("v0.9.0", "v0.10.0")
        result = self.check("--check-latest")
        self.assertIn("latest: 0.10.0", result.stdout)


GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@e",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@e",
}


class PlanFixture(unittest.TestCase):
    """
    A stand-in template clone with release tags, and a project copy beside it.

    The check script is copied INTO the template and that copy runs: --plan
    takes the template to be the repository holding the script, so running the
    real script would read this repository's real tags.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.tpl = self.tmp / "tpl"
        self.project = self.tmp / "project"
        self.git("init", "-q", str(self.tpl))
        skill = ".claude/skills/orchestrator-version"
        no_cache = shutil.ignore_patterns("__pycache__")
        shutil.copytree(CHECK.parent, self.tpl / skill, ignore=no_cache)
        # The project carries the same skill copy, as a real one would.
        shutil.copytree(CHECK.parent, self.project / skill, ignore=no_cache)

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], check=True, capture_output=True, text=True, env=GIT_ENV
        ).stdout

    def release(
        self, version: str, files: dict[str, str | None], executable: tuple = ()
    ) -> None:
        """Write (or delete, on None) template files, then commit and tag.
        Paths in `executable` are committed as 100755."""
        files = {".claude/ORCHESTRATOR_VERSION": f"{version}\n", **files}
        for rel, text in files.items():
            path = self.tpl / rel
            if text is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            path.chmod(0o755 if rel in executable else 0o644)
        self.git("-C", str(self.tpl), "add", "-A")
        self.git("-C", str(self.tpl), "commit", "-q", "-m", version)
        self.git("-C", str(self.tpl), "tag", f"v{version}")

    def put(self, rel: str, text: str) -> Path:
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def plan(
        self, *args: str, script: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        script = script or self.tpl / ".claude/skills/orchestrator-version/check"
        return subprocess.run(
            [sys.executable, str(script), "--plan", str(self.project), *args],
            capture_output=True,
            text=True,
            timeout=60,
        )


class PlanPreconditionTests(PlanFixture):
    """V6, V6b: a plan that cannot be right is refused with the fix, exit 2."""

    def setUp(self) -> None:
        super().setUp()
        self.release("1.0.0", {})
        self.release("2.0.0", {})

    def test_the_newest_tag_is_chosen_numerically(self) -> None:
        self.release("10.0.0", {})
        self.release("9.0.0", {})
        self.put(".claude/ORCHESTRATOR_VERSION", "1.0.0\n")
        result = self.plan()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("1.0.0 -> 10.0.0", result.stdout)

    def test_the_old_version_comes_from_the_project_not_the_script(self) -> None:
        self.put(".claude/ORCHESTRATOR_VERSION", "1.0.0\n")
        result = self.plan()
        self.assertIn("1.0.0 -> 2.0.0", result.stdout)
        self.assertIn("the project's .claude/ORCHESTRATOR_VERSION", result.stdout)

    def test_no_version_file_and_no_from_asks_for_from(self) -> None:
        result = self.plan()
        self.assertEqual(2, result.returncode)
        self.assertIn("--from", result.stderr)
        self.assertEqual("", result.stdout)

    def test_from_overrides_the_file_and_says_so(self) -> None:
        self.put(".claude/ORCHESTRATOR_VERSION", "2.0.0\n")
        result = self.plan("--from", "1.0.0")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("1.0.0 -> 2.0.0", result.stdout)
        self.assertIn("overrides the project's file, which says 2.0.0", result.stdout)

    def test_a_missing_tag_names_fetch_tags(self) -> None:
        result = self.plan("--from", "1.5.0")
        self.assertEqual(2, result.returncode)
        self.assertIn("no tag v1.5.0", result.stderr)
        self.assertIn("fetch --tags", result.stderr)

    def test_a_project_newer_than_the_target_is_refused(self) -> None:
        result = self.plan("--from", "2.0.0", "--to", "1.0.0")
        self.assertEqual(2, result.returncode)

    def test_a_repo_that_is_not_the_template_is_refused(self) -> None:
        # A project copy inside a product repo with its own release tags.
        other = self.tmp / "product"
        self.git("init", "-q", str(other))
        shutil.copytree(CHECK.parent, other / ".claude/skills/orchestrator-version")
        self.git("-C", str(other), "add", "-A")
        self.git("-C", str(other), "commit", "-q", "-m", "x")
        self.git("-C", str(other), "tag", "v2.0.0")
        script = other / ".claude/skills/orchestrator-version/check"
        result = self.plan("--from", "2.0.0", script=script)
        self.assertEqual(2, result.returncode)
        self.assertIn("not a claude-code-orchestrator clone", result.stderr)

    def test_a_script_outside_any_repo_is_refused(self) -> None:
        copy = self.tmp / "loose/.claude/skills/orchestrator-version"
        shutil.copytree(CHECK.parent, copy)
        result = self.plan("--from", "1.0.0", script=copy / "check")
        self.assertEqual(2, result.returncode)
        self.assertIn("not a git repository", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_plan_and_check_latest_do_not_combine(self) -> None:
        result = self.plan("--check-latest")
        self.assertEqual(2, result.returncode)
        self.assertIn("not allowed with", result.stderr)


CLASS_HEADER = re.compile(r"^([A-Z-]+) \((\d+)\) — ")


def parse_plan(stdout: str) -> dict[str, dict[str, str]]:
    """class -> {path: group}; group is the PROJECT-ONLY sub-heading, else ""."""
    classes: dict[str, dict[str, str]] = {}
    current, group = "", ""
    for line in stdout.splitlines():
        if m := CLASS_HEADER.match(line):
            current, group = m[1], ""
            classes[current] = {}
        elif not line.startswith("  "):
            current = ""
        elif current and line.endswith(":"):
            group = line.strip().rsplit(" (", 1)[0]
        elif current:
            classes[current][line.strip().split("  ")[0]] = group
    return classes


def tree_state(root: Path) -> list[tuple[str, bytes, int]]:
    return sorted(
        (p.relative_to(root).as_posix(), p.read_bytes(), p.stat().st_mode)
        for p in root.rglob("*")
        if p.is_file()
    )


class PlanClassificationTests(PlanFixture):
    """V1, V2, V3, V7, VH: each file lands in its class, nothing is written."""

    def setUp(self) -> None:
        super().setUp()
        self.release(
            "0.9.0",
            {".claude/legacy.md": "l", ".claude/ancient.md": "an"},
        )
        self.release("0.10.0", {".claude/ancient.md": None})
        old = {
            "replace.md": "r1",
            "noop.md": "n",
            "merge.md": "m1",
            "keep.md": "k",
            "delete.md": "d",
            "delete-mod.md": "dm",
            "absent.md": "a",
        }
        self.release(
            "1.0.0",
            {
                ".claude/legacy.md": None,
                **{f".claude/{k}": v for k, v in old.items()},
                ".agents/rules/AGENTS.md": "ag1",
                "CLAUDE.md": "c1",
            },
        )
        self.release(
            "2.0.0",
            {
                ".claude/replace.md": "r2",
                ".claude/merge.md": "m2",
                ".claude/delete.md": None,
                ".claude/delete-mod.md": None,
                ".claude/add.md": "new",
                ".agents/rules/AGENTS.md": "ag2",
            },
        )
        # The project: a 1.0.0 copy, partly edited, plus leftovers.
        self.put(".claude/ORCHESTRATOR_VERSION", "1.0.0\n")
        for rel, text in old.items():
            if rel != "absent.md":
                self.put(f".claude/{rel}", text)
        self.put(".claude/merge.md", "m1 edited")
        self.put(".claude/keep.md", "k edited")
        self.put(".claude/delete-mod.md", "dm edited")
        self.put(".agents/rules/AGENTS.md", "ag1")
        self.put("CLAUDE.md", "c1 edited")
        self.put(".claude/legacy.md", "l")
        self.put(".claude/ancient.md", "an")
        self.put(".claude/mine.md", "project's own")

    def test_every_file_lands_in_exactly_its_class(self) -> None:
        result = self.plan()
        self.assertEqual(0, result.returncode, result.stderr)
        got = {name: set(paths) for name, paths in parse_plan(result.stdout).items()}
        self.assertEqual(
            {
                "REPLACE": {
                    ".claude/replace.md",
                    ".claude/ORCHESTRATOR_VERSION",
                    ".agents/rules/AGENTS.md",
                },
                "MERGE": {".claude/merge.md"},
                "KEEP": {".claude/keep.md", "CLAUDE.md"},
                "DELETE": {".claude/delete.md"},
                "DELETE-MODIFIED": {".claude/delete-mod.md"},
                "ADD": {".claude/add.md"},
                "ABSENT": {".claude/absent.md"},
                "PROJECT-ONLY": {
                    ".claude/legacy.md",
                    ".claude/ancient.md",
                    ".claude/mine.md",
                },
            },
            got,
        )
        # noop.md and the two skill files match 2.0.0.
        self.assertIn("NOOP: 3 files already match 2.0.0", result.stdout)

    def test_project_only_names_the_newest_release_that_shipped_it(self) -> None:
        only = parse_plan(self.plan().stdout)["PROJECT-ONLY"]
        self.assertEqual("last shipped in 0.10.0", only[".claude/legacy.md"])
        self.assertEqual("last shipped in 0.9.0", only[".claude/ancient.md"])
        self.assertEqual("never shipped", only[".claude/mine.md"])

    def test_project_owned_files_are_marked(self) -> None:
        stdout = self.plan().stdout
        self.assertIn("  CLAUDE.md  [project-owned]", stdout)
        self.assertIn("  .claude/keep.md\n", stdout)
        self.assertIn("[project-owned] = do not overwrite", stdout)

    def test_the_style_guide_is_project_owned(self) -> None:
        # It is a team's house style (it shipped one team's Confluence links
        # until 5.0.0): an upgrade must not overwrite a project's version.
        loader = importlib.machinery.SourceFileLoader("check", str(CHECK))
        spec = importlib.util.spec_from_loader("check", loader)
        assert spec is not None
        check = importlib.util.module_from_spec(spec)
        loader.exec_module(check)
        self.assertTrue(check.project_owned(".claude/docs/writing-style.md"))
        self.assertFalse(check.project_owned(".claude/rules/writing-style.md"))

    def test_runtime_state_is_not_part_of_the_plan(self) -> None:
        runtime = (
            ".claude/logs/bash-marks/toolu_x",
            ".claude/docs/reviews/r.md",
            ".claude/isolated-review/canary",
            ".claude/skills/x/__pycache__/y.cpython-312.pyc",
            ".claude/hooks/__pycache__/h.cpython-312.pyc",
            ".claude/hooks/.blocked-reviews",
            ".claude/settings.local.json",
        )
        for rel in runtime:
            self.put(rel, "state")
        # The same dotfile name outside the hooks directory is a real file.
        self.put(".claude/notes/.blocked-reviews", "a note")
        stdout = self.plan().stdout
        for rel in runtime:
            self.assertNotIn(rel, stdout)
        self.assertIn(".claude/notes/.blocked-reviews", stdout)

    def test_raw_bytes_hash_like_git(self) -> None:
        # CRLF and non-UTF-8 bytes: an unmodified copy must still be NOOP.
        raw = b"line\r\nmore\xff\xfe\n"
        (self.tpl / ".claude/raw.bin").write_bytes(raw)
        self.git("-C", str(self.tpl), "add", "-A")
        self.git("-C", str(self.tpl), "commit", "-q", "-m", "raw")
        self.git("-C", str(self.tpl), "tag", "-f", "v2.0.0")
        (self.project / ".claude/raw.bin").write_bytes(raw)
        stdout = self.plan().stdout
        self.assertNotIn("raw.bin", stdout)
        self.assertIn("NOOP: 4 files", stdout)

    def test_the_plan_writes_nothing(self) -> None:
        project_before = tree_state(self.project)
        status = ["-C", str(self.tpl), "status", "--porcelain", "--ignored"]
        tpl_before = self.git(*status)
        self.assertEqual(0, self.plan().returncode)
        self.assertEqual(project_before, tree_state(self.project))
        self.assertEqual(tpl_before, self.git(*status))


SHEBANG = "#!/usr/bin/env python3\n"
FIXTURE_TEMPLATE_CHANGELOG = """# Changelog

## [2.0.0] - 2026-10-12
## [1.5.0] - 2026-10-11
## [1.0.0] - 2026-10-10
"""


def hook_settings(*names: str) -> str:
    command = 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/{}"'
    groups = [
        {"hooks": [{"type": "command", "command": command.format(n)}]} for n in names
    ]
    return json.dumps({"hooks": {"PostToolUse": groups}})


@unittest.skipIf(os.name == "nt", "no exec bit on Windows")
class PlanExtrasTests(PlanFixture):
    """V4, V4b, V4c, V5 and the CHANGELOG pointer."""

    def setUp(self) -> None:
        super().setUp()
        self.release(
            "1.0.0",
            {
                "CHANGELOG.md": FIXTURE_TEMPLATE_CHANGELOG,
                ".claude/hooks/kept.py": SHEBANG,
                ".claude/hooks/gone.py": SHEBANG,
                ".claude/bin/tool": SHEBANG,
                ".claude/rules/doc.md": "a document tracked as 100755",
                ".claude/rules/plain.md": "plain",
            },
            executable=(
                ".claude/hooks/kept.py",
                ".claude/hooks/gone.py",
                ".claude/bin/tool",
                ".claude/rules/doc.md",
            ),
        )
        self.release(
            "2.0.0",
            {
                ".claude/hooks/gone.py": None,
                ".claude/bin/new-tool": SHEBANG,
                ".claude/rules/new-doc.md": "another 100755 document",
            },
            executable=(".claude/bin/new-tool", ".claude/rules/new-doc.md"),
        )
        self.put(".claude/ORCHESTRATOR_VERSION", "1.0.0\n")
        for rel, mode in (
            (".claude/hooks/kept.py", 0o644),  # lost its exec bit: report
            (".claude/hooks/gone.py", 0o755),
            (".claude/bin/tool", 0o755),
            (".claude/rules/doc.md", 0o644),  # 100755 upstream, no shebang
            (".claude/rules/plain.md", 0o755),  # executable here only
        ):
            shipped = self.git("-C", str(self.tpl), "show", f"v1.0.0:{rel}")
            self.put(rel, shipped).chmod(mode)
        self.put(
            ".claude/settings.json", hook_settings("kept.py", "gone.py", "lost.py")
        )

    def section(self, stdout: str, name: str) -> str:
        if f"\n{name} (" not in stdout:
            return ""
        return stdout.split(f"\n{name} (", 1)[1].split("\n\n", 1)[0]

    def test_a_script_that_lost_its_exec_bit_is_reported(self) -> None:
        result = self.plan()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            ["  .claude/hooks/kept.py"],
            self.section(result.stdout, "EXEC BIT").splitlines()[1:],
        )

    def test_add_notes_settings_permissions_only_for_scripts(self) -> None:
        add = self.section(self.plan().stdout, "ADD")
        self.assertIn(".claude/bin/new-tool  (script: allow it in settings.json", add)
        self.assertIn("  .claude/rules/new-doc.md\n", add + "\n")
        self.assertNotIn("new-doc.md  (script", add)

    def test_hook_registrations_without_a_file_after_the_plan_are_reported(
        self,
    ) -> None:
        hooks = self.section(self.plan().stdout, "HOOKS")
        self.assertIn(".claude/hooks/gone.py — deleted by this plan", hooks)
        self.assertIn(".claude/hooks/lost.py — registered, but missing", hooks)
        self.assertNotIn("kept.py", hooks)

    def test_a_hook_registered_twice_is_counted_once(self) -> None:
        # The shipped settings.json registers bash-write-check.py twice.
        settings = hook_settings("gone.py", "gone.py", "lost.py")
        self.put(".claude/settings.json", settings)
        hooks = self.section(self.plan().stdout, "HOOKS")
        self.assertTrue(hooks.startswith("2) — "), hooks)
        self.assertEqual(2, len(hooks.splitlines()[1:]))

    def test_no_hooks_section_when_every_registration_stays_valid(self) -> None:
        self.put(".claude/settings.json", hook_settings("kept.py"))
        self.assertNotIn("\nHOOKS", self.plan().stdout)

    def test_the_changelog_entries_between_the_versions_are_named(self) -> None:
        stdout = self.plan().stdout
        self.assertIn(
            "CHANGELOG — read the entries 2.0.0, 1.5.0 for hand steps", stdout
        )


if __name__ == "__main__":
    unittest.main()
