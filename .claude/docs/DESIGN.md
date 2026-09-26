# Project Design Document

> This document tracks design decisions made during conversations.
> Updated automatically by the `design-tracker` skill.

## Overview

<!-- Project purpose and goals -->

## Architecture

<!-- System structure, components, data flow -->

```
[Component diagram or description here]
```

## Implementation Plan

### Patterns & Approaches

<!-- Design patterns, architectural approaches -->

| Pattern | Purpose | Notes |
|---------|---------|-------|
| | | |

### Libraries & Roles

<!-- Libraries and their responsibilities -->

| Library | Role | Version | Notes |
|---------|------|---------|-------|
| | | | |

### Key Decisions

<!-- Important decisions and their rationale -->

| Decision | Rationale | Alternatives Considered | Date |
|----------|-----------|------------------------|------|
| deep-reasoning pins `model: fable` instead of `inherit` | With `inherit`, an Opus main session made the subagent Opus too, so the most expensive model did the token-heavy work (reading files) that the orchestrator/worker split exists to avoid | Keep `inherit` and correct only the docs | 2026-09-25 |
| `/init` renamed `/initproject`, `/startproject` renamed `/feature` | `/init` collided with Claude Code's built-in `/init` (which generates a fresh CLAUDE.md), so which one fired was unpredictable; `/startproject` read as once-per-project while it runs once per unit of work | Keep the names and document the relationship only | 2026-09-25 |
| This repository is not a package (`[tool.uv] package = false`) | A hatchling build-system for a non-existent `src/` made every `uv run` fail, which took down `poe lint`/`test`/`all` with it | Add `tool.hatch.build.targets.wheel` and keep the build backend | 2026-09-25 |
| This repository type-checks with `ty`; the checker is chosen per project by `/initproject` | Pure-Python repo with no Django, and the rules and lint hook already assumed `ty`. Measured: on Django models `ty` reports 3 false positives on 3 correct lines because it has no plugin for the field descriptors, while `mypy` + `django-stubs` is clean — so the choice cannot be a template-wide default | Template-wide mypy; template-wide ty | 2026-09-25 |
| `poe lint` no longer auto-fixes; the gate is read-only and `poe fix` mutates | A gate that rewrites files can never fail on a lint or format issue, so `poe all` gave false assurance | Leave `--fix` in the gate | 2026-09-25 |
| The lens review's product is the CONFLICTS, not the findings list | Concatenating three reports is the easy version and loses the most valuable signal: where two lenses recommend opposite things is the real design decision. The aggregate step is forbidden from resolving a conflict silently — it presents both sides and what each choice gives up | Merge the reports and pick the best recommendation | 2026-09-26 |
| A lens that finds nothing must say so, and is told not to invent | A lens under pressure to look useful produces noise that buries real findings. "Found nothing" and "did not look" are also reported separately, because they are different facts | Expect every lens to return findings | 2026-09-26 |
| Lenses must declare what they do NOT cover | Non-orthogonal lenses report the same thing three times: triple cost, single value. The exclusion goes into each lens prompt verbatim, not just into the skill's table | Define lenses only by what they look at | 2026-09-26 |
| The pre-filter runs once and every lens gets the same list | Per-lens pre-filtering triples the cost AND gives each lens a different view, which makes the aggregate's comparison impossible — so the conflict detection, the whole point, stops working | Pre-filter inside each lens | 2026-09-26 |
| `/lens-review` does not replace the separate-session review | The lenses run in isolated contexts, but the orchestrator writes their prompts, so its framing survives. Isolation is not neutrality. It runs BEFORE the separate session to clear the obvious, so the neutral review spends itself on the hard parts | Treat multi-lens as sufficient review | 2026-09-26 |
| Named `lens-review`, not `review` or `code-review` | Both collide with built-in commands, which is the mistake `/init` already made in this repository once | `/review` | 2026-09-26 |
| Routing is by cost (token volume × reasoning difficulty), not by topic | The rules classified by subject — "research goes to agy" — which left the two token-heavy cells of the matrix empty, so log triage, repo-wide impact analysis, file pre-filtering and boilerplate all flowed to Claude. That is the structural cause of the token imbalance the user reported | Keep topic-based routing and ask for more agy calls | 2026-09-26 |
| The agy pre-filter returns `file:line` and facts, never verdicts | If agy summarises, deep-reasoning reasons about the summary instead of the code, and the funnel becomes a quality regression rather than a saving. The pre-filter narrows what is read; it does not decide anything | Let agy summarise its findings | 2026-09-26 |
| The always-loaded rules carry DECISIONS; syntax lives with the process that runs it | `.claude/rules/antigravity-delegation.md` was 425 lines / 21,890 bytes — 38% of the always-loaded layer — and most of it was command syntax, prompt templates and reference prose already present in `.claude/agents/general-purpose.md` and the antigravity skill. Verbatim overlap was only ~6%, so the copies were independently worded and could contradict each other with no test noticing. The rule now holds routing, the agy fallback ladder, the tier table and "judgement is never delegated"; 12,754 bytes, and the layer went from 57,378 to 48,236 | Move the syntax into a new `references/` file (a fourth home); shrink by deleting the fallback ladder | 2026-09-26 |
| Whether `.claude/rules/*.md` reaches a SUBAGENT is treated as unknown | The Claude Code docs state that `CLAUDE.md` loads into subagents and say nothing about `.claude/rules/`; skills do not auto-invoke there either and must be named in `skills:` frontmatter. A subagent in this session reported seeing the rule files in its own context, but that is an observation of one runtime, not a guarantee across versions, and this is a template that runs elsewhere. So anything an executor MUST have is duplicated into `.claude/agents/general-purpose.md` on purpose, and a test asserts it is still there | Rely on the observation and delete the executor's copy; rely on the docs and duplicate everything | 2026-09-26 |
| The shrink-vs-keep conflict between two review lenses was FALSE | One lens wanted the rule smaller, the other wanted the fallback ladder kept always-loaded. The ladder is 1,545 characters, 9% of the file; the bulk was reference material neither lens was defending. Both were satisfied by the same cut, so it was recorded as a measurement error rather than resolved as a trade-off. What the ladder must stay for is narrower than first stated: `agy-probe` does print an install/login remedy, but it cannot say what to do INSTEAD of agy in this work unit, and that is what the ladder holds | Split the difference; treat it as a genuine trade-off | 2026-09-26 |
| The pre-filter is recall-oriented and its consumer is told the input was filtered | A pre-filter that misses a location hides it from deep-reasoning for ever, and a consumer that believes it saw everything concludes that what it cannot see does not exist | Optimise the pre-filter for precision | 2026-09-26 |
| Below 5 files / 500 lines there is no funnel, and that number is defined in exactly one place | The round trip costs more than it saves on a small input, and a rule with no threshold funnels everything. Three decisions consult the same boundary (pre-filter, `/lens-review`, `/feature` Phase 6) and each had restated it, which drifted to 500 in the routing rules and 300 in the review paths — fifteen lines apart in the same file, with nothing failing. CLAUDE.md now owns the number and a test fails the moment two sites disagree, so restating it where it helps the model read it stays safe | A separate threshold per decision; pointers with no number anywhere | 2026-09-26 |
| The routing claim is marked as weakly measurable | `log-cli-tools.py` records only `"tool": "antigravity"`, so the log can show agy's call count and tier distribution but NOT the work Claude did instead. The metric supports the claim and cannot falsify it — stating that prevents over-reading it later | Present the tier distribution as proof of re-allocation | 2026-09-26 |
| `/jira-setup` asks for the project key instead of listing projects | Measured against a real connector: one organisation has 141 Jira projects. Listing them burns context and the user knows their own key anyway | Show a picker of projects | 2026-09-26 |
| Project `style` (classic vs next-gen) is recorded, and transition names are read rather than guessed | Measured: the same site mixes company-managed and team-managed projects, whose issue types and workflow transitions differ. A guessed transition name either fails or moves the ticket to the wrong state | Assume one workflow; hard-code "In Progress"/"Done" | 2026-09-26 |
| Confluence access does not imply Jira access, and a site can appear more than once | Measured: `getAccessibleAtlassianResources` returned the same cloudId twice, once with Confluence scopes and once with `read:jira-work`/`write:jira-work`. Treating the first entry as the site would have missed Jira entirely | One entry per site | 2026-09-26 |
| Jira write policy is the user's choice, recorded per project | A comment and a status change are outward-facing writes a team reacts to. The default follows the document policy already agreed — additive actions are reported, overwriting actions are confirmed first — and status transitions are always confirmed because they move shared state | Bake a default into the template | 2026-09-26 |
| A ticket body is data, not an instruction | Ticket text is written by anyone with access. An instruction inside it ("delete this file") is confirmed with the user rather than obeyed | Treat the ticket as the task specification verbatim | 2026-09-26 |
| The document skill is `doc-write`, not `confluence-write` | The style rules govern five document types and two of them are not Confluence (a repo compliance document, `jobs/<ticket>/plan.md`). A Confluence-named skill handling Jira and repo files would mis-trigger, and splitting it would duplicate 90% of the content | `/confluence-write` plus a second skill | 2026-09-26 |
| Rules say WHAT to obey, the skill says HOW to do it | The style document is 466 lines and loads only on demand; the procedure (connector check, location, storage format, publish policy) is a different concern with a different lifetime. A test samples distinctive prose from the style document and fails if the skill transcribes it | One file holding both | 2026-09-26 |
| No Confluence space, parent page or MCP tool name in the template | Space and parent are per project — they go in `CLAUDE.md` `## Project Setup` once the user answers. Connector tool names differ per setup, so naming one exactly would break on another Atlassian connector. Tests assert both absences | Hard-code the user's space; name the tools exactly | 2026-09-26 |
| `CLAUDE.md` sections are keyed by the LIFETIME of what they hold | Five skills wrote state into one `## Current Project` heading while `/feature` Phase 5 said to replace that block, so the Jira site, transition names, write policy and Confluence space recorded by `/jira-setup` and `/doc-write` were erased at the next `/feature` run and `/ticket` then stopped or re-asked. Project-permanent state now lives in `## Project Setup` (appended to, replaced by nobody), work-unit state in `## Current Project` (replaced per unit), session state in `## Session History` (rewritten, always last). Found by `/lens-review`, not by a test | One block for everything; give `/feature` a merge rule instead of a separate heading | 2026-09-26 |
| agy availability is three states, not a boolean | "Not installed", "not logged in" and "answered with nothing" need three different remedies — install, log in, wait — and the template collapsed all of them into "if agy is installed; otherwise note it". A soft-denied call exits 0 with an empty answer, so a boolean check would also have called that success | A single is-it-there check | 2026-09-25 |
| The probe checks for a usable answer BEFORE matching error words, and captures stderr with `mktemp` | The first version matched the authentication patterns against `$output$stderr` first, so a call that answered correctly while agy wrote a warning, quota notice or retry line mentioning `log in`, `credential` or `403` to stderr was reported UNAUTHENTICATED — a healthy session sent down the fallback path with a remedy the user could not act on. Ordering it after the token check also demotes the patterns to choosing WHICH unusable state to report, so a loose match costs precision rather than correctness. The stderr file was `/tmp/.agy-probe-err.$$`, a guessable path whose redirection follows a planted symlink; a test plants one over a range of PIDs and asserts the victim file is untouched | Match the error words first; keep the PID-based temp path | 2026-09-26 |
| The probe lives in the antigravity skill, not `.claude/scripts/` | That directory is the project's verification contract; a probe is not a tier and would read as a fifth entrypoint. A test asserts it is not there | Put it beside the verify-* scripts | 2026-09-25 |
| Degrading without agy must be declared in the artefact's first line | A research document written with Grep and WebSearch has different breadth from a Gemini sweep. A later reader who cannot tell which they are holding will over-trust it, and `/feature` Phase 3 will review a plan whose evidence base it cannot judge | Degrade silently; skip research entirely | 2026-09-25 |
| Every hook has a trigger case AND a silence case, and the pair is required structurally | The contract tests assert tolerance (exit 0, valid-or-empty stdout, survives junk) and empty stdout is a legal answer, so a hook that reads its payload and returns satisfies all of them — measured: a no-op `main()` in any of the eight hooks left all 13 contract tests green. That is the exact shape of this template's most expensive defect (`lint-on-save.py` read an env var Claude Code never sets). A trigger case alone passes for a hook that fires on everything and a silence case alone for one that never fires, so both are required, and `CoverageTests` fails when a hook on disk has neither | More contract properties; a coverage percentage | 2026-09-26 |
| Which files count as implementation is decided by EXCLUSION, not by a list of languages | The hook listed seven extensions, so work in any other language was invisible — the same hard-coding the template is being cured of elsewhere. Missing a language costs a hook that never fires; counting one extra file type costs one early suggestion, so the asymmetry favours excluding documents, config, data, assets and lockfiles and counting the rest | Extend the inclusion list; read the extensions from a config file | 2026-09-25 |
| Per-session state removes the need for a SessionStart reset hook | The suggestion must fire once per session, which the original implemented as a flag in shared state and therefore never reset. Keying the file by session id makes a new session start empty by construction, with no second hook to keep in sync | Add a SessionStart hook that clears the flag | 2026-09-25 |
| A log entry with an unusable timestamp is skipped and counted, not grouped | It has no place in a chronological history. `local_date` fell back to the timestamp's first ten characters, so a corrupt line became a heading. Skipping silently would hide data loss, so the count is printed | Group them under an "unknown date" bucket | 2026-09-25 |
| The history section is located by a line scan that skips fenced code blocks, not by a regex | The checkpointing skill documents the section it writes inside a ```markdown fence. The regex matched that line, so the section started inside the example and everything up to the next heading — the fence's closing backticks included — was replaced, leaving the rest of the document inside an unterminated code block. The mirror case matters too: a `## ...` line inside a fence must not end the section. The scan also matches a header on the last line with no trailing newline, which the regex required and therefore appended a second section below on every run | Keep the regex and add a fence-stripping pre-pass; document the limitation | 2026-09-26 |
| Each context file declares the heading its history lives under | `CLAUDE.md` uses `## Session History` and `AGENTS.md` uses `## Consultation History`. Assuming one header made the script append a second, parallel section to AGENTS.md on every run | Rename AGENTS.md's section to match | 2026-09-25 |
| Output on exit 0 is informational and is passed through, not discarded | The first version dropped all output when the script succeeded. Tools that warn but succeed are common (eslint warnings, clippy, deprecation notices); swallowing that output makes the model report "clean". The contract had also stated the rule three different ways in three files | Keep "silent on pass" strictly, and have scripts never print on success | 2026-09-25 |
| Every tier accepts optional trailing arguments | With a no-argument-only contract a monorepo could not express scope: `verify-task` would have to check everything (breaking the 5-minute budget) or guess from `git diff`. Callers still pass none | Arguments only on verify-save | 2026-09-25 |
| The caller resolves `verify-<tier>` or `verify-<tier>.{py,sh,ps1,cmd,bat}` | Requiring an extensionless executable with a shebang excluded Windows checkouts outright, where neither the execute bit nor the shebang exists. A file with a known extension runs through its interpreter | Unix-only, stated as a limitation | 2026-09-25 |
| Shared helpers allowed as `_*` or `lib/` in `.claude/scripts/` | The contract demanded all complexity live inside the scripts while a test forbade any file that was not an entrypoint — so four scripts needing the same container wrapper had to duplicate it | Four self-contained scripts, duplication accepted | 2026-09-25 |
| This repo configures only the `save` and `task` tiers | Its whole suite runs in ~3 seconds, so `unit` and `full` have no honest content. The doc-consistency checks that were in `verify-full` take ~1s and are deterministic, so by this project's own rule (duration decides the tier) they belong in the gate — they moved to `tests/test_template_consistency.py` and now run after every task instead of only when someone invokes the slowest tier | Keep verify-full as the home for template self-checks | 2026-09-25 |
| Reverted `pytest-cov` and the coverage run | `--cov=.claude` measured only the three modules imported in-process (41%), while six hooks run as subprocesses and were not measured at all. It reported the wrong number confidently and doubled the tier's runtime | Keep it and add subprocess coverage | 2026-09-25 |
| Script names match tier names exactly (`verify-save`/`task`/`unit`/`full`) | The reviewer proposed `lint-file`/`check`/`test-unit`/`test-full`, which would have left the scripts and the tier vocabulary in `rules/testing.md`, `CLAUDE.md`, `/feature` and `/plan` using different words for the same thing — the drift this project keeps having to repair. A test now asserts every tier name appears in `rules/testing.md` | The reviewer's names | 2026-09-25 |
| `verify-full` in THIS repo checks the template's self-consistency, not a longer test run | A template repository's slowest meaningful check is whether it still describes itself truthfully. It found 3 real defects on its first run (two dangling references from a research doc, and a regex bug of its own that truncated `.jsonl` to `.json`) | A longer test run; no full tier at all | 2026-09-25 |
| Tests do not execute `verify-task`/`unit`/`full` | Those run this test suite (they are the gate), so calling them from a test recurses without end. That `verify-task` passes is already proven by `poe all` being green when the tests run; what is left is shell-syntax and no-chaining checks | An env-var guard breaking the recursion at depth 1, at the cost of running the suite twice per gate | 2026-09-25 |
| The per-project contract is the **filesystem** (four scripts), not a profile schema | An adversarial review falsified the premise. Measured: exactly ONE hook runs stack tools, and the real generality bug was `/initproject` Step 5 omitting `tdd`/`simplify` (6 hardcoded `uv run pytest` lines surviving setup). A profile would also have been a 4th copy of the test command — after `pyproject.toml`, `rules/testing.md` and `CLAUDE.md` — creating exactly the drift Step 3 exists to prevent. `runs_in: container` alone would force the hook to become a path-mapping execution adapter | A `project-profile.toml` schema; reading existing files (`pyproject.toml` is Python-only, Yocto has neither) | 2026-09-25 |
| Verification plan comes FIRST, before any tooling | It is prose, it was already the highest-leverage step, and applying it to a real Yocto and a real Django repo is what reveals which commands need names. Designing a schema before observing its consumers was the core mistake | Schema first, then hooks, then the plan | 2026-09-25 |
| Verification tiers are defined by DURATION, not by the words unit/e2e | "e2e" means an HTTP request to a compose stack in one project and a QEMU `testimage` run in another; the word cannot drive a decision, the budget can | Model unit/integration/e2e as first-class | 2026-09-25 |
| A save-tier gate is READ-ONLY, and a test hands it a file the tier actually processes | `verify-save` ran `ruff format` and `ruff check --fix`, so the hook rewrote every file the model had just written: an unused import deleted, exit 0, no output — the silence the contract defines as "nothing to report". `/initproject` Step 5 already said "never put an auto-fixing command in a gate" and this repository's own gate did. No test caught it because `SaveTierContractTests` used only paths the tier IGNORES and said so in its docstring. Found by the separate-session review | Keep `--fix` and document the hazard; report the change instead of removing it | 2026-09-26 |
| The review worktree is checked out at the WORK branch, never at `main` | `/feature` Phase 6 Option A said to check out `main` and then run `git diff main...HEAD`, which inside that worktree compares main with itself and prints nothing — the review session sees "no changes" and stops, silently. README described the same procedure differently (`git diff <base>..main`), so the two files disagreed about where the work lives. Introduced by the restructure that carried CLAUDE.md's worktree command into the skill. The cloud case (no interactive `claude`) is now written down too: push the branch and start a fresh session against it, since the isolation that matters is context, not files | Leave the recipe local-only; keep two wordings | 2026-09-26 |
| `/feature`'s document order IS its execution order, and a test compares the two | The workflow diagram promised an "Implementation Loop" step that had no section anywhere in the file — the one step where code is written was the only step with no instructions, and its rules were parked in Phase 4 (Task Creation) for want of a home. `## User Confirmation`, the gate before any code, sat AFTER the post-implementation review section. Both are structural and no substring test could see them, so `tests/test_feature_workflow.py` parses the diagram and the headings and asserts both directions: every diagram step has a section in order, and every `## Phase` section is in the diagram (the direction that would have caught the stray `## User Confirmation`) | Reorder and rely on review; write a phrase test | 2026-09-26 |
| The confirmation gate is numbered `Phase 4b`, and phases are never renumbered | "Phase N" is a public name: eight files point into `/feature` by phase number (CLAUDE.md, two rules, `/ticket`, `/plan`, `.claude/scripts/README.md`, DESIGN.md) and none of it was tested, so a renumbering would have drifted silently. An unnumbered step between 4 and 5 also reads as an aside a model may skip, while `4 → 4b → 5` reads as a sequence — the file already used that convention for Phase 2b. A test resolves every inbound phase reference | Renumber into 1..8; leave the gate unnumbered | 2026-09-26 |
| The verification plan is persisted into `## Current Project`, not only into the conversation | Phase 6 Option A asks a NEW session to compare the plan's scenario IDs against the tests, and the plan existed only in the finished conversation — the template had a step whose input it never saved. The `## Current Project` block now carries a compact scenario table, keeping the IDs and the negative-test column, which are what the comparison is made of | Leave it in the plan document; drop the comparison | 2026-09-26 |
| The verification plan lives in `/feature` output, not in any project-level config | Lifetimes differ: project commands are stable, per-feature scenarios change every ticket. Folding them would churn project config per ticket | Fold the verification manifest into the profile | 2026-09-25 |
| Full writing style lives in `.claude/docs/`, with a short pointer rule | `.claude/rules/*.md` loads every session; 466 lines of document style would tax sessions that write no documents | Put the whole style in `.claude/rules/` | 2026-09-25 |

## TODO

Direction: the template must serve any stack, so it should not *know* stacks — it
should know what to ask, and the per-project contract should be the filesystem
(scripts with exit codes) rather than a schema. Revised after an adversarial
review falsified the original profile design; see Key Decisions.

- [x] **Verification plan in `/feature`.** Phase 2b writes scenarios, commands,
      tiers and a negative-test column before code exists; Phase 3 reviews
      verification adequacy; Phase 4 pairs every implementation task with a
      `verify:` task; Phase 6 judges tests against the plan's scenario IDs.
      `rules/testing.md` rewritten stack-agnostic; `CLAUDE.md` carries the
      principle; `/plan` steps must cite tier + command + failure condition.
- [x] **Four scripts as the contract.** `.claude/scripts/verify-{save,task,unit,full}`
      plus `README.md` holding the contract. Named after the tiers in
      `rules/testing.md` so the two cannot drift. Exit code is the interface;
      execution location, path translation and tool discovery live inside the
      script, where a person can run it by hand.
- [x] **`lint-on-save.py` delegates to `verify-save` and names no tool.** A test
      asserts it mentions no toolchain. `Bash(.claude/scripts/*)` allowed;
      `.claude/scripts/verify-` added to `TEST_BUILD_COMMANDS`.
- [x] **`/initproject` Step 5 writes the scripts.** The procedure is
      stack-agnostic by construction: four questions per tier (what command can
      fail / where does it run / how long / how does it go red), no recipe to
      match against, and a tier with no honest answer gets no script.
- [x] **`initproject/references/known-pitfalls.md`** — measured facts with dates
      only, no per-stack recipes.
- [x] `checkpoint.py` hardening — seven defects, each with a regression test
      written first (`tests/test_checkpoint_hardening.py`, scenario IDs C1-C7):
      the section regex ended only at `^## ` so an intervening H1 was destroyed;
      one malformed timestamp aborted the whole run; `--since` was unvalidated
      and compared in UTC while grouping is local; context files were rewritten
      non-atomically with no backup; `HEAD~10` was hard-coded; `AGENTS.md` uses
      `## Consultation History` so a second parallel section was appended; and
      entries from any tool other than agy were discarded. Two further bugs were
      found by running the fixed script for real: an unparseable timestamp still
      produced a garbage `### broken-tim` heading when `--since` was absent, and
      the atomic-write tests passed while its caller was reverted to a plain
      write, so a test now asserts the backup exists.

      **Correction (2026-09-26):** the `HEAD~10` entry above was recorded as
      closed while it was not. Only `get_file_changes` had been switched to
      `resolve_commit_range`; `get_file_stats` kept
      `git diff --numstat HEAD~10 HEAD` and therefore returned nothing on any
      repository with fewer than eleven commits — the same silent
      "no changes detected" the fix was for. Found by `/lens-review`, reproduced
      on a two-commit repository, and fixed by walking the same range with the
      same walker (`git log --numstat`, which also covers the root commit where
      `git diff` has no parent). `tests/test_checkpoint_hardening.py`
      `FileStatsRangeTests` now asserts that every file listed as changed has
      line counts, so the two call sites cannot drift apart again.
- [x] `checkpointing/SKILL.md` brought back in line with `checkpoint.py`: it
      showed `**agy조사:**` and `✓` while the script writes `**agy:**` and
      `[OK]`/`[FAILED]` (labels moved to English per `rules/language.md`), and it
      said both context files use `## Session History` while `AGENTS.md` uses
      `## Consultation History`. `DocumentedFormatTests` asserts the document
      against *generated* output rather than against a copy of the format, so the
      two cannot drift apart in either direction.

- [x] `post-implementation-review.py` — state is now per project and per session
      under `.claude/logs/implementation-state/`, with stale files pruned after
      7 days and symlinks refused. Which files count is exclusion-based rather
      than a list of seven extensions, and comment stripping covers the common
      syntaxes instead of only `#`. 16 regression tests
      (`tests/test_post_implementation_review.py`, scenario IDs R1-R6).
- [x] agy-unavailable fallback. Two layers, because they answer different
      questions: `/initproject` Step 3b probes at setup time, while a person is
      present, and asks for installation or login as the state requires; the
      runtime path in `/feature` Phase 1 cannot wait for anybody and degrades to
      Claude's own tools instead. `agy-probe` distinguishes MISSING /
      UNAUTHENTICATED / DEGRADED because the remedies differ. The fallback ladder
      lives once in `.claude/rules/antigravity-delegation.md`; the other files
      point at it rather than copying it. 16 tests.

Dropped after review:
- ~~Hooks read a project profile~~ — one hook runs stack tools; a project-owned
  script covers it with no loader code in every hook.
- ~~Per-stack recipe files (Layer 3)~~ — see `known-pitfalls.md` above.
- ~~Commit gate with freshness receipts~~ — a receipt cannot stay fresh across a
  two-hour image build, and the fail-open policy that keeps it safe also makes
  it trivially bypassed. `.git/hooks/pre-commit` running `check` is the same
  guard in one line and works outside Claude too (measured: repo git hooks do
  run under the Bash tool; `--no-verify` bypasses them).
- ~~Stop hook that blocks "done" without a test run~~ — a `command` hook cannot
  force continuation, so it would be the only non-Python hook here, and the
  8-block cap makes it unreliable.

- [x] Separate-session neutral review performed (the procedure this file's
      Phase 6 Option A prescribes), on commit `45c4afa`. A fresh session with no
      context from the implementing one reviewed `main...HEAD` and pushed its
      report to the branch `claude/review-45c4afa`. It found 13 defects and
      three mutations that left all 312 tests green. **Twelve of its claims were
      re-reproduced here before anything was accepted; all twelve reproduced
      exactly**, including byte-identical md5 sums on the verify-save case.

      Fixed in this session: F1 (review worktree / empty diff, in `/feature`,
      README and CLAUDE.md), F2 (`verify-save` made read-only, contract amended,
      non-mutation test added), F3 (`poe` → `uv run poe` where the always-loaded
      files point), F4 (`dev-environment.md` realigned with `pyproject.toml`:
      py311, no `src/`, real task list), and the four verification gaps — the
      symlink refusal, the soft-deny success flag, the line-count trigger, and a
      vacuous tier test of my own that passed with every `verify-*` stripped out
      of the skill.

      Deferred with the reviewer's agreement (follow-up, not merge-blocking):
      F5 `checkpoint.py` drops renames (`R` status is neither A/M/D, and this
      branch contains three); F6 its commit walker is unbounded while the file
      walkers use `HEAD~10`, so one summary mixes two ranges; F8 the executor
      agent file is told to follow the fallback ladder without carrying it;
      F9 DESIGN.md asserts no MCP tool names are in the template while two
      appear in `/doc-write`; F10 the byte figure in the budget docstring is
      367 bytes stale; F11 README's `python3 -m unittest` runs 0 tests and
      reports OK; F12 the new `Bash(.claude/scripts/*)` allowance pre-approves
      scripts the model itself writes; F13 the design-review hook fires on any
      write over 500 characters.

      What the review did NOT cover, in its own words: it never ran `/feature`,
      `/initproject`, `/lens-review`, `/doc-write`, `/jira-setup` or `/ticket`;
      agy, Jira and Windows are all unverified; and six test modules were read
      but not mutation-checked.

- [x] `/feature` restructured into execution order with the missing
      implementation-loop section written, and the duplication around it closed:
      the tier table (whose rows were byte-identical to `rules/testing.md` 원칙 4,
      with a second copy of the Yocto/Django illustration) became a pointer; the
      loop rules moved out of Phase 4 rather than being copied; the background
      unit-tier run got the Task-prompt template it never had, carrying the
      script contract explicitly because a general-purpose subagent is not
      guaranteed to load the rules; and three stale restatements of the sequence
      (`README.md` twice, `CLAUDE.md` 진행 순서) plus a pointer in
      `.claude/scripts/README.md` to a section that did not exist were corrected.
      `references/task-patterns.md`, referenced by nothing and teaching "Testing"
      as a final category against Phase 4's mandatory pairing, was fixed and
      wired in.

- [x] Always-loaded context split by WHO needs it, with three tests added before
      the cut so they would go red on the likely mistakes: tier/slug equality
      across the five copies (also fails if the table leaves the rule),
      section-anchor resolution, and a byte ratchet plus a negative check that
      `--dangerously-skip-permissions` never returns to a rule file. All
      confirmed by mutation. The ratchet's docstring states what it is not: bytes
      are not tokens, the layer mixes Korean prose with English command blocks,
      and the subagent multiplier is unknown.

- [x] Hooks are fed real triggering payloads (`tests/test_hook_effects.py`,
      33 tests). Each of the eight hooks now has a payload it must react to and
      one it must ignore, with the effect asserted where it is observable:
      `additionalContext` in stdout JSON, text on stderr, a JSONL line, a state
      file. Side effects are redirected, not mocked — `CLAUDE_PROJECT_DIR` points
      at a temporary project, and `log-cli-tools.py` is copied into a temporary
      tree because its log path is relative to its own `__file__`.

      Verified by mutation rather than by counting: all 8 no-op mutations pass
      the contract tests and fail these; 5 always-fire mutations, plus
      `is_source_file -> True`, the removed agy-binary check and the removed
      `os.path.isfile` check, all fail these. Three silence cases exist because
      that second run exposed them — the originals returned early (a skip list,
      an explicit success flag, a command with no bare `-p`) and the always-fire
      mutants survived. The suite looked complete at 29 tests and was not.

      Still open: nothing here proves Claude Code sends this payload shape, that
      the `settings.json` matchers route to these files, or that the emitted
      context changes what the model does. Only a real session shows that.

- [x] Phrase tests declare what they are. `/lens-review` measured that roughly
      90 of this suite's assertions are substring matches against markdown and
      that 14 template mutations leave the suite green — appending a sentence
      that reverses an asserted rule stays green, while a meaning-preserving
      reword goes red. Each markdown-asserting module now says in its docstring
      that it is a drift tripwire and not behavioural coverage, and
      `PhraseTestHonestyTests` requires that of any module added later. The limit
      itself is not fixed by this — feeding hooks and skills real triggering
      input is a separate piece of work.

## Open Questions

<!-- Unresolved issues, things to investigate -->

- [ ] "Tests were run" is enforceable; "the tests are meaningful" is not. The
      closest available checks are `/feature` Phase 6 comparing tests against the
      verification plan's scenario IDs, and `/lens-review`'s verification-adequacy
      lens. Both are judgement, not enforcement. **Standing limitation**, not a
      task — do not expect this one to close.
- [ ] Nothing here has been exercised on a real project yet. Every verification in
      this session ran against the template itself, which has no `src/`, a
      3-second test suite and only two verification tiers. The first real
      `/initproject` on a Django or Yocto repository is where the assumptions get
      tested. Record what breaks.
- [ ] `/lens-review`, `/doc-write`, `/jira-setup`, `/ticket` and `agy-probe`'s
      READY path have never actually run. Their tests assert their instructions,
      not their behaviour in use.

Closed, so that a later session does not reopen them:

- ~~Profile schema granularity~~ — the profile was rejected; the contract is four
  scripts and an exit code. See Key Decisions.
- ~~Whether to add a Stop hook that blocks "done" without a test run~~ — dropped.
  A `command` hook cannot force continuation, and the commit gate plus
  `.git/hooks/pre-commit` cover the same ground more simply.

## Changelog

| Date | Changes |
|------|---------|
| 2026-09-26 | `/lens-review`: orthogonal lenses in parallel, one shared pre-filter, aggregation that surfaces inter-lens conflicts rather than resolving them, conditional adversarial verification; 30 tests |
| 2026-09-26 | Cost-based routing: token volume × reasoning difficulty replaces topic-only routing; two-stage funnel (agy narrows, Claude judges) wired into /feature Phase 3 and Phase 6, with a size threshold and a locations-not-verdicts contract; 17 tests |
| 2026-09-26 | Jira integration: `/jira-setup` (manual, once per project — connection state, project context, write policy) and `/ticket` (auto-invoked, ticket to implementation to comment/transition); 29 tests, design grounded in measurements against a real connector |
| 2026-09-26 | `/doc-write` skill: auto-invoked document writing under the user's style rules, with the trigger boundary in its description, an asymmetric publish policy, and no project- or connector-specific values; 16 tests |
| 2026-09-25 | agy fallback: `agy-probe` reports READY/MISSING/UNAUTHENTICATED/DEGRADED; `/initproject` Step 3b asks for install or login at setup time; `/feature` Phase 1 degrades to Claude's own tools and records that it did |
| 2026-09-25 | post-implementation-review.py: per-project/per-session state with pruning and symlink refusal, exclusion-based source detection, multi-language comment stripping; 16 regression tests written first |
| 2026-09-25 | checkpoint.py hardened against data loss (section boundary, atomic writes with backup, timestamp and --since handling, git range, per-file history heading, all tools kept); 17 regression tests written before the fixes |
| 2026-09-25 | Contract review: pass-through of success output, optional scope arguments, interpreter resolution for Windows, shared helpers, tiers reduced to the two this repo honestly has, template self-checks moved into the gate, coverage theatre reverted |
| 2026-09-25 | Verification contract as four executables (`.claude/scripts/verify-*`); `lint-on-save` delegates and names no tool; `/initproject` Step 5 writes them; `known-pitfalls.md` for measured facts |
| 2026-09-25 | Verification-first: `/feature` Phase 2b verification plan, paired verify tasks, adequacy review; stack-agnostic `rules/testing.md`; duration-based tiers |
| 2026-09-25 | Pinned deep-reasoning to Fable; renamed the two entry skills; added the writing-style rule; repaired the quality gate (`uv run`, `lint-on-save`, `post-test-analysis`) and added hook contract tests; recorded the stack-agnostic direction |
| | Initial |
