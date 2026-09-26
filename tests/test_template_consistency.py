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

Some of these read real state (settings.json against the hooks on disk, script
permissions) and hold on their own. The ones that assert on prose — the
reference check and the threshold scan — are DRIFT TRIPWIRES, not behavioural
coverage: a substring match fails when a phrase disappears and passes for any
text that still contains it, so it cannot tell whether what the prose promises
is true. `LargeChangeThresholdTests` guards the scan itself for that reason, and
`PhraseTestHonestyTests` requires every markdown-asserting module to say the
same thing in its own docstring.

These are specific to THIS repository (a Claude Code template). A project
adopting the template does not need them; `tests/test_verify_scripts.py` is the
part meant to be copied.
"""

from __future__ import annotations

import ast
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
        self.assertIn("큰 변경의 기준", body, "there is no single definition site")
        for consumer in ("프리필터", "/lens-review", "/feature"):
            self.assertIn(consumer, body, f"the definition does not name {consumer}")

    def test_the_definition_covers_the_size_independent_case(self) -> None:
        """A one-line change to an auth check is large regardless of the count."""
        body = " ".join((REPO / "CLAUDE.md").read_text(encoding="utf-8").split())
        self.assertIn("보안 경계", body)


class AlwaysLoadedBudgetTests(unittest.TestCase):
    """
    A ratchet on the always-loaded layer, and a check that syntax stays out of it.

    `CLAUDE.md` and every `.claude/rules/*.md` without `paths:` frontmatter enter
    every session before anything is asked. Two dated measurements, both
    historical facts rather than claims about the present: **57,378 bytes before
    the routing-rule split** (21,890 of it the agy rule, a file largely about
    saving tokens, which made it the largest fixed cost here), and **48,236
    immediately after it, on 2026-09-26**.

    The docstring deliberately does not state a current total. An earlier version
    did, and it went stale by 367 bytes within two commits while the test stayed
    green — the separate-session review measured it. The live number is whatever
    the assertion below computes; the only figure that must be maintained is the
    cap.

    What this test is, precisely: a RATCHET, not a proof. It cannot show that the
    layer is the right size or that anything in it earns its place; it only
    forces a deliberate decision when the number grows past the cap, instead of
    letting it drift a paragraph at a time. The cap carries ~10% slack so an
    ordinary edit does not fail the suite.

    Two honest limits: bytes are not tokens, and this layer mixes Korean prose
    (dense per byte in UTF-8, three bytes a character) with English command
    blocks, so the byte figure over- or under-states cost depending on which
    grew. And whether `.claude/rules/*.md` reaches a SUBAGENT is not documented
    — the Claude Code docs guarantee only `CLAUDE.md` — so the real multiplier on
    this number is unknown. That is why the executor's command syntax lives in
    `.claude/agents/general-purpose.md` rather than here.
    """

    # A ratchet, not a measurement: raise it deliberately, with a reason.
    BUDGET_BYTES = 53_000

    def _always_loaded(self) -> list[Path]:
        files = [REPO / "CLAUDE.md"]
        for path in sorted((REPO / ".claude" / "rules").glob("*.md")):
            head = path.read_text(encoding="utf-8")[:400]
            if re.match(r"^---\n(?:.*\n)*?paths:", head):
                continue  # conditionally loaded, not part of the fixed cost
            files.append(path)
        return files

    def test_the_layer_stays_within_budget(self) -> None:
        sizes = {p.name: len(p.read_bytes()) for p in self._always_loaded()}
        total = sum(sizes.values())
        self.assertLessEqual(
            total,
            self.BUDGET_BYTES,
            f"the always-loaded layer is {total} bytes, over the {self.BUDGET_BYTES} "
            f"ratchet. Largest: {sorted(sizes.items(), key=lambda kv: -kv[1])[:3]}. "
            "Move reference material to a skill or an agent file, or raise the "
            "cap deliberately and say why.",
        )

    def test_the_scan_finds_the_layer(self) -> None:
        """Guards the ratchet: an empty file list would pass any budget."""
        files = self._always_loaded()
        self.assertGreaterEqual(len(files), 8, f"only found {files}")
        self.assertIn("CLAUDE.md", [p.name for p in files])

    def test_no_rule_file_carries_command_syntax(self) -> None:
        """
        A negative check on a STRUCTURED token, which is why it bites: the flag
        string is exact, so pasting a command back into the always-loaded layer
        fails here rather than being noticed in review. The flags belong with the
        process that runs them — `.claude/agents/general-purpose.md` — and with
        the skill that composes prompts.
        """
        offenders = [
            str(p.relative_to(REPO))
            for p in sorted((REPO / ".claude" / "rules").glob("*.md"))
            if "--dangerously-skip-permissions" in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(
            [],
            offenders,
            f"command syntax is back in the always-loaded rules: {offenders}",
        )

    def test_the_executor_still_has_the_syntax_it_needs(self) -> None:
        """
        The other half of the move. Deleting the flags from the rule is only safe
        because the subagent that runs the commands carries them itself —
        subagents are not documented to load `.claude/rules/`, and skills do not
        auto-invoke inside them.
        """
        executor = (REPO / ".claude" / "agents" / "general-purpose.md").read_text(
            encoding="utf-8"
        )
        for token in ("--dangerously-skip-permissions", "--sandbox", "agy -p"):
            self.assertIn(token, executor, f"the executor lost {token}")
        self.assertIn(
            "Do not create or modify any files",
            executor,
            "the read-only sentence that guards the flags is gone",
        )

    def test_the_executor_carries_the_fallback_ladder_itself(self) -> None:
        """
        The other thing an executor cannot look up.

        The agent file used to say "follow the fallback section in the rule" and
        "do not duplicate this", which is the opposite of what the split
        concluded: a subagent is not documented to receive `.claude/rules/` at
        all, and skills do not auto-invoke there. So the states and the
        alternative paths live in the agent file too, on purpose.
        """
        executor = (REPO / ".claude" / "agents" / "general-purpose.md").read_text(
            encoding="utf-8"
        )
        for state in ("MISSING", "UNAUTHENTICATED", "DEGRADED"):
            self.assertIn(
                state, executor, f"the executor cannot recognise the {state} state"
            )
        for alternative in ("WebSearch", "Grep"):
            self.assertIn(
                alternative,
                executor,
                f"the executor is not told it can fall back to {alternative}",
            )
        self.assertIn(
            "대체 불가",
            executor,
            "the executor is not told that video and audio have no substitute",
        )


class ModelTierConsistencyTests(unittest.TestCase):
    """
    Every copy of the tier table must name the same slug for the same tier.

    The slugs are restated in the routing rule, the antigravity skill, the
    general-purpose agent definition, a skill reference, CLAUDE.md, README and a
    hook. A tier paired with the wrong slug is a silent cost or quality bug: a T4
    repo analysis on a flash model gives a worse answer for less money and
    nothing errors. This is the same class of drift as the 500/300 threshold, and
    the same shape of test catches it — equality between independent copies of a
    STRUCTURED token, not a phrase lookup, so it survives rewording and fails on
    a real disagreement.

    The routing rule is the canonical table, so this test also fails if that
    table is removed from the always-loaded rules. That is deliberate: the
    orchestrator pins the slug when it writes a Task prompt, before any skill has
    necessarily loaded, and an unpinned call falls back to the user's global
    default — the most expensive tier.
    """

    TIER = re.compile(r"\bT([1-4])\b")
    SLUG = re.compile(r"gemini-[0-9a-z.\-]*-(?:low|high)")
    CANONICAL = REPO / ".claude" / "rules" / "antigravity-delegation.md"

    def _files(self) -> list[Path]:
        found = [
            p
            for p in REPO.rglob("*.md")
            if not any(
                part in (".git", "research", "node_modules", "checkpoints")
                for part in p.parts
            )
        ]
        found += sorted((REPO / ".claude" / "hooks").glob("*.py"))
        return sorted(set(found))

    def _pairings(self, path: Path) -> dict[str, set[str]]:
        """Tier -> slugs, taken from lines that name exactly one tier."""
        pairs: dict[str, set[str]] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            tiers = set(self.TIER.findall(line))
            slugs = set(self.SLUG.findall(line))
            if len(tiers) == 1 and slugs:
                pairs.setdefault(tiers.pop(), set()).update(slugs)
        return pairs

    def test_the_canonical_table_is_in_the_always_loaded_rule(self) -> None:
        canonical = self._pairings(self.CANONICAL)
        self.assertEqual(
            {"1", "2", "3", "4"},
            set(canonical),
            "the tier table is no longer complete in the always-loaded rule, so "
            "the orchestrator cannot pin a slug before a skill loads",
        )
        for tier, slugs in canonical.items():
            self.assertTrue(slugs, f"T{tier} names no slug")

    def test_no_copy_contradicts_the_canonical_table(self) -> None:
        canonical = self._pairings(self.CANONICAL)
        problems = []
        for path in self._files():
            if path == self.CANONICAL:
                continue
            for tier, slugs in self._pairings(path).items():
                extra = slugs - canonical.get(tier, set())
                if extra:
                    problems.append(
                        f"{path.relative_to(REPO)} maps T{tier} to "
                        f"{sorted(extra)}, which the rule does not"
                    )
        self.assertEqual([], problems, "; ".join(problems))

    def test_at_least_three_files_restate_the_table(self) -> None:
        """Guards the extractor: with none found, the test above is vacuous."""
        restating = [
            p for p in self._files() if p != self.CANONICAL and self._pairings(p)
        ]
        self.assertGreaterEqual(
            len(restating), 3, f"only {len(restating)} files paired a tier with a slug"
        )

    def test_every_slug_used_anywhere_is_a_known_slug(self) -> None:
        """Catches an invented or mistyped slug, which fails loudly at call time."""
        known = set().union(*self._pairings(self.CANONICAL).values())
        unknown = {}
        for path in self._files():
            used = set(self.SLUG.findall(path.read_text(encoding="utf-8")))
            if used - known:
                unknown[str(path.relative_to(REPO))] = sorted(used - known)
        self.assertEqual({}, unknown, f"unknown model slugs: {unknown}")


class SectionPointerTests(unittest.TestCase):
    """
    A pointer that names a SECTION of another file must still find it.

    `test_instructions_do_not_reference_missing_input_files` checks that the
    file exists. It does not check the section, and the section is what the
    reader needs: `.claude/agents/general-purpose.md` sends the subagent to
    "agy 가 없을 때" in the routing rule, `/feature` to "라우팅은 주제가 아니라
    비용으로 한다", `/initproject` to "Model Policy", and five files to CLAUDE.md's
    「큰 변경」의 기준. Renaming or moving any of those leaves a pointer into
    nothing, and the model follows it to a file where the section is absent —
    which reads as "this rule does not exist" rather than as an error.

    This is not a substring match on prose: it resolves each pointer against the
    target file's actual headings, so it fails on a rename in either file.
    """

    # <file>.md followed by → / -> / " 의 " and a quoted section, or by 「section」.
    POINTER = re.compile(
        r"`?(?P<file>(?:\.claude/|\.agents/|)[\w./-]+\.md)`?"
        r"(?:"
        r'[^"「\n]{0,4}?(?:→|->|\s의\s)\s*(?:「(?P<k1>[^」]{3,60})」|"(?P<q1>[^"]{3,60})")'
        r"|"
        r"[ ]{0,2}(?:의[ ]?)?「(?P<k2>[^」]{3,60})」"
        r")"
    )

    def _pointers(self) -> list[tuple[Path, str, str]]:
        found = []
        for path in sorted(REPO.rglob("*.md")):
            if any(
                part in (".git", "research", "node_modules", "checkpoints")
                for part in path.parts
            ):
                continue
            flat = " ".join(path.read_text(encoding="utf-8").split())
            for match in self.POINTER.finditer(flat):
                section = (
                    match.group("k1") or match.group("q1") or match.group("k2") or ""
                )
                found.append((path, match.group("file"), section))
        return found

    def _resolve(self, ref: str) -> Path | None:
        for candidate in (REPO / ref, REPO / ".claude" / ref):
            if candidate.is_file():
                return candidate
        return None

    def test_the_scan_finds_the_pointers_it_is_meant_to(self) -> None:
        """Guards the scanner: one that matches nothing would pass vacuously."""
        pointers = self._pointers()
        self.assertGreaterEqual(
            len(pointers), 12, f"the scan found only {len(pointers)} pointers"
        )
        targets = {ref for _, ref, _ in pointers}
        self.assertTrue(
            any("antigravity-delegation" in t for t in targets),
            "the most-pointed-at rule is not among the matches",
        )

    def test_every_section_pointer_resolves_to_a_heading(self) -> None:
        unresolved = []
        for source, ref, section in self._pointers():
            target = self._resolve(ref)
            if target is None:
                continue  # file existence is another test's job
            headings = [
                re.sub(r"^#+\s*", "", line).strip()
                for line in target.read_text(encoding="utf-8").splitlines()
                if line.startswith("#")
            ]
            if not any(section in heading for heading in headings):
                unresolved.append(f"{source.relative_to(REPO)} -> {ref} :: {section!r}")
        self.assertEqual(
            [], unresolved, "section pointers into nothing: " + "; ".join(unresolved)
        )


class PhraseTestHonestyTests(unittest.TestCase):
    """
    A phrase test that claims more than it proves is worse than no test.

    /lens-review measured that roughly 90 of this suite's assertions are
    substring matches against markdown, and that 14 separate mutations of the
    template leave the suite green. That is a real limit of the approach, not a
    bug to fix by adding more phrases — so every module that asserts on markdown
    has to say so where the next reader will see it.
    """

    def _markdown_asserting_modules(self) -> list[Path]:
        modules = []
        for path in sorted((REPO / "tests").glob("test_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                if any(
                    isinstance(sub, ast.Constant)
                    and isinstance(sub.value, str)
                    and sub.value.endswith(".md")
                    for sub in ast.walk(node)
                ):
                    modules.append(path)
                    break
        return modules

    def test_the_scan_finds_the_modules_it_is_meant_to(self) -> None:
        """Guards the guard: a selector that matches nothing passes vacuously."""
        found = {p.name for p in self._markdown_asserting_modules()}
        self.assertIn("test_routing_rules.py", found)
        self.assertGreaterEqual(len(found), 5, f"the selector found only {found}")

    def test_each_one_states_that_it_is_a_tripwire(self) -> None:
        for path in self._markdown_asserting_modules():
            with self.subTest(module=path.name):
                doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
                self.assertIsNotNone(doc, "no module docstring at all")
                assert doc is not None
                lowered = doc.lower()
                self.assertIn(
                    "drift tripwire",
                    lowered,
                    "a module of substring assertions on prose must say so",
                )
                self.assertIn(
                    "behavioural",
                    lowered,
                    "it must also say what it is NOT — behavioural coverage",
                )


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
