"""
Checks that this template still describes itself truthfully.

These began life inside `.claude/scripts/verify-full`, which was the wrong place:
they take about a second and are fully deterministic, so by this project's own
rule — duration decides the tier (`.claude/rules/testing.md`) — they belong in
the task gate, where they run after every task instead of only when a person
remembers to invoke the slowest tier.

They exist because this repository's most common defect class is drift: a hook
renamed without updating what points at it, a skill directory whose frontmatter
disagrees, a document promising a file that was never written.

These are specific to THIS repository (a Claude Code template). A project
adopting the template does not need them; `tests/test_verify_scripts.py` is the
part meant to be copied.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
HOOKS = REPO / ".claude" / "hooks"
SKILLS = REPO / ".claude" / "skills"
SETTINGS = REPO / ".claude" / "settings.json"

# Locations whose contents are INPUTS the model is told to read. Outputs are
# excluded on purpose: .claude/docs/, .claude/logs/ and .claude/checkpoints/ hold
# what a skill creates, often with a date or placeholder in the name.
INPUT_DIRS = ("rules", "skills", "agents", "hooks", "scripts")

# Files that name other files. .claude/docs/research/ is excluded: research
# output describes what a tool COULD do and names paths never meant to exist.
SOURCES = (
    REPO / "CLAUDE.md",
    REPO / "README.md",
    REPO / ".claude" / "rules",
    REPO / ".claude" / "skills",
    REPO / ".claude" / "agents",
    REPO / ".claude" / "scripts" / "README.md",
    REPO / ".claude" / "docs" / "DESIGN.md",
)

# Optional by design, so absence is not a defect. Kept as an explicit short list
# rather than a pattern, so it stays reviewable instead of becoming a dumping
# ground.
OPTIONAL_PATHS = frozenset({".claude/settings.local.json"})

# \b after the extension matters: without it ".jsonl" matches as ".json" and
# every log reference looks dangling.
REFERENCE_RE = re.compile(
    r"\.claude/(?:"
    + "|".join(INPUT_DIRS)
    + r")/[A-Za-z0-9_./-]+\.(?:md|py|json|toml)\b"
)


def read_text_files(paths) -> dict[Path, str]:
    """Every file under the given paths, as {path: text}."""
    out: dict[Path, str] = {}
    for source in paths:
        if source.is_file():
            out[source] = source.read_text(encoding="utf-8", errors="replace")
        elif source.is_dir():
            for child in sorted(source.rglob("*")):
                if child.is_file() and child.suffix in {".md", ".py"}:
                    out[child] = child.read_text(encoding="utf-8", errors="replace")
    return out


class HookRegistrationTests(unittest.TestCase):
    def test_every_hook_on_disk_is_registered(self) -> None:
        registered = SETTINGS.read_text(encoding="utf-8")
        for hook in sorted(HOOKS.glob("*.py")):
            self.assertIn(
                hook.name,
                registered,
                f"{hook.name} exists but nothing in settings.json runs it",
            )

    def test_every_registered_hook_exists(self) -> None:
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        on_disk = {p.name for p in HOOKS.glob("*.py")}
        for handlers in settings.get("hooks", {}).values():
            for group in handlers:
                for handler in group.get("hooks", []):
                    command = handler.get("command", "")
                    if ".claude/hooks/" not in command:
                        continue
                    name = command.split(".claude/hooks/")[1].split()[0].strip("\"'")
                    self.assertIn(
                        name,
                        on_disk,
                        f"settings.json runs {name}, which is not on disk",
                    )

    def test_hook_timeouts_leave_room_for_the_hook_to_report(self) -> None:
        """
        A hook that self-limits above its registered timeout is killed by the
        harness first, so its own timeout message is unreachable.
        """
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        registered: dict[str, int] = {}
        for handlers in settings.get("hooks", {}).values():
            for group in handlers:
                for handler in group.get("hooks", []):
                    command = handler.get("command", "")
                    if ".claude/hooks/" not in command:
                        continue
                    name = command.split(".claude/hooks/")[1].split()[0].strip("\"'")
                    if "timeout" in handler:
                        registered[name] = handler["timeout"]

        for name, limit in registered.items():
            source = (HOOKS / name).read_text(encoding="utf-8")
            for match in re.finditer(r"TIMEOUT_SECONDS\s*=\s*(\d+)", source):
                with self.subTest(hook=name):
                    self.assertLess(
                        int(match.group(1)),
                        limit,
                        f"{name} waits {match.group(1)}s but settings.json kills it "
                        f"at {limit}s",
                    )


class SkillNamingTests(unittest.TestCase):
    def test_directory_name_matches_frontmatter_name(self) -> None:
        for skill in sorted(SKILLS.glob("*/SKILL.md")):
            declared = None
            for line in skill.read_text(encoding="utf-8").splitlines():
                if line.startswith("name:"):
                    declared = line.split(":", 1)[1].strip()
                    break
            with self.subTest(skill=skill.parent.name):
                self.assertEqual(
                    skill.parent.name,
                    declared,
                    "a skill is invoked by its frontmatter name; a mismatch means "
                    "the directory is not what the user types",
                )


class ReferenceTests(unittest.TestCase):
    def test_instructions_do_not_reference_missing_input_files(self) -> None:
        dangling: list[str] = []
        for path, text in read_text_files(SOURCES).items():
            for ref in sorted(set(REFERENCE_RE.findall(text))):
                if ref in OPTIONAL_PATHS or (REPO / ref).exists():
                    continue
                dangling.append(f"{path.relative_to(REPO)} -> {ref}")
        self.assertEqual([], dangling, "instructions point at files that do not exist")


class LargeChangeThresholdTests(unittest.TestCase):
    """
    One boundary, one number.

    Three decisions consult "is this change large?": whether to put an agy
    pre-filter in front of deep-reasoning, whether /lens-review is worth three
    subagents, and which review route /feature Phase 6 takes. Each site restated
    the number, and they drifted: 500 lines in the routing rules, 300 in
    /lens-review and in /feature Phase 6 — the two appeared fifteen lines apart
    in the same file. Nothing failed, which is why it survived.

    The definition lives in CLAUDE.md. A site may restate the number where that
    helps the model read it (a skill description is matched without its body
    loaded), and this test makes restating it safe by failing the moment two
    sites disagree.
    """

    # "파일 5개", "5+ files", "5 files" — the file half of the same threshold.
    FILE_TOKENS = ("파일 5개", "5+ files", "5 files")
    LINE_COUNT = re.compile(r"(\d{2,4})\s*\+?\s*(?:줄|changed lines|lines)")
    LOOKAHEAD = 80

    def _threshold_mentions(self) -> dict[str, set[str]]:
        found: dict[str, set[str]] = {}
        for path in sorted(REPO.rglob("*.md")):
            if any(
                part in (".git", "research", "node_modules", "checkpoints")
                for part in path.parts
            ):
                continue
            flat = " ".join(path.read_text(encoding="utf-8").split())
            numbers: set[str] = set()
            for token in self.FILE_TOKENS:
                start = 0
                while True:
                    at = flat.find(token, start)
                    if at == -1:
                        break
                    window = flat[at : at + len(token) + self.LOOKAHEAD]
                    numbers.update(self.LINE_COUNT.findall(window))
                    start = at + 1
            if numbers:
                found[str(path.relative_to(REPO))] = numbers
        return found

    def test_the_threshold_is_stated_somewhere(self) -> None:
        """Guards the test itself: a regex that matches nothing proves nothing."""
        mentions = self._threshold_mentions()
        self.assertGreaterEqual(
            len(mentions), 4, f"the scan found almost nothing: {mentions}"
        )

    def test_every_site_uses_the_same_line_count(self) -> None:
        mentions = self._threshold_mentions()
        distinct = set().union(*mentions.values())
        self.assertEqual(
            1,
            len(distinct),
            "the large-change threshold disagrees between files: "
            + "; ".join(f"{f} -> {sorted(n)}" for f, n in sorted(mentions.items())),
        )

    def test_claude_md_defines_it_and_lists_who_uses_it(self) -> None:
        body = " ".join((REPO / "CLAUDE.md").read_text(encoding="utf-8").split())
        self.assertIn("「큰 변경」의 기준", body, "there is no single definition site")
        for consumer in ("프리필터", "/lens-review", "/feature"):
            self.assertIn(consumer, body, f"the definition does not name {consumer}")

    def test_the_definition_covers_the_size_independent_case(self) -> None:
        """A one-line change to an auth check is large regardless of the count."""
        body = " ".join((REPO / "CLAUDE.md").read_text(encoding="utf-8").split())
        self.assertIn("보안 경계", body)


class ScriptContractTests(unittest.TestCase):
    """The template's own scripts must satisfy the contract they document."""

    def test_only_entrypoints_and_helpers_live_in_scripts(self) -> None:
        scripts = REPO / ".claude" / "scripts"
        for entry in sorted(scripts.iterdir()):
            if entry.is_dir():
                self.assertEqual(
                    "lib",
                    entry.name,
                    "only a lib/ subdirectory is allowed beside the entrypoints",
                )
                continue
            name = entry.name
            allowed = (
                name == "README.md"
                or name.startswith("verify-")
                or name.startswith("_")
            )
            self.assertTrue(
                allowed,
                f"{name} is neither an entrypoint (verify-*), a helper (_*), "
                "nor the contract README — it will be mistaken for an entrypoint",
            )

    def test_save_tier_does_not_chain_a_slower_tier(self) -> None:
        save = REPO / ".claude" / "scripts" / "verify-save"
        if not save.is_file():
            self.skipTest("no save tier configured")
        text = save.read_text(encoding="utf-8")
        for slower in ("verify-task", "verify-unit", "verify-full"):
            self.assertNotIn(
                slower,
                text,
                f"verify-save invokes {slower}: saving a file must not start a build",
            )


if __name__ == "__main__":
    unittest.main()
