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

    def test_quick_start_clones_the_release_branch(self) -> None:
        # Drift tripwire over prose. The default branch is `develop` (work in
        # progress); a bare `git clone` would hand adopters unreleased changes.
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        clones = [
            line
            for line in readme.splitlines()
            if "git clone" in line and "claude-code-orchestrator" in line
        ]
        self.assertTrue(clones, "the scan no longer finds the Quick Start clone")
        for line in clones:
            with self.subTest(line=line.strip()[:60]):
                self.assertIn("--branch main", line)

    def test_initproject_records_the_adopted_version(self) -> None:
        # Drift tripwire over prose.
        skill = (REPO / ".claude/skills/initproject/SKILL.md").read_text(
            encoding="utf-8"
        )
        step4 = skill.split("## Step 4", 1)[1].split("\n## ", 1)[0]
        self.assertIn("ORCHESTRATOR_VERSION", step4)


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


if __name__ == "__main__":
    unittest.main()
