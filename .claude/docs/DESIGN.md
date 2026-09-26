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
| The document skill is `doc-write`, not `confluence-write` | The style rules govern five document types and two of them are not Confluence (a repo compliance document, `jobs/<ticket>/plan.md`). A Confluence-named skill handling Jira and repo files would mis-trigger, and splitting it would duplicate 90% of the content | `/confluence-write` plus a second skill | 2026-09-26 |
| Rules say WHAT to obey, the skill says HOW to do it | The style document is 466 lines and loads only on demand; the procedure (connector check, location, storage format, publish policy) is a different concern with a different lifetime. A test samples distinctive prose from the style document and fails if the skill transcribes it | One file holding both | 2026-09-26 |
| No Confluence space, parent page or MCP tool name in the template | Space and parent are per project — they go in `CLAUDE.md` `## Current Project` once the user answers. Connector tool names differ per setup, so naming one exactly would break on another Atlassian connector. Tests assert both absences | Hard-code the user's space; name the tools exactly | 2026-09-26 |
| agy availability is three states, not a boolean | "Not installed", "not logged in" and "answered with nothing" need three different remedies — install, log in, wait — and the template collapsed all of them into "if agy is installed; otherwise note it". A soft-denied call exits 0 with an empty answer, so a boolean check would also have called that success | A single is-it-there check | 2026-09-25 |
| The probe lives in the antigravity skill, not `.claude/scripts/` | That directory is the project's verification contract; a probe is not a tier and would read as a fifth entrypoint. A test asserts it is not there | Put it beside the verify-* scripts | 2026-09-25 |
| Degrading without agy must be declared in the artefact's first line | A research document written with Grep and WebSearch has different breadth from a Gemini sweep. A later reader who cannot tell which they are holding will over-trust it, and `/feature` Phase 3 will review a plan whose evidence base it cannot judge | Degrade silently; skip research entirely | 2026-09-25 |
| Which files count as implementation is decided by EXCLUSION, not by a list of languages | The hook listed seven extensions, so work in any other language was invisible — the same hard-coding the template is being cured of elsewhere. Missing a language costs a hook that never fires; counting one extra file type costs one early suggestion, so the asymmetry favours excluding documents, config, data, assets and lockfiles and counting the rest | Extend the inclusion list; read the extensions from a config file | 2026-09-25 |
| Per-session state removes the need for a SessionStart reset hook | The suggestion must fire once per session, which the original implemented as a flag in shared state and therefore never reset. Keying the file by session id makes a new session start empty by construction, with no second hook to keep in sync | Add a SessionStart hook that clears the flag | 2026-09-25 |
| A log entry with an unusable timestamp is skipped and counted, not grouped | It has no place in a chronological history. `local_date` fell back to the timestamp's first ten characters, so a corrupt line became a heading. Skipping silently would hide data loss, so the count is printed | Group them under an "unknown date" bucket | 2026-09-25 |
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

## Open Questions

<!-- Unresolved issues, things to investigate -->

- [ ] Profile schema granularity: too few slots and stack details leak back into
      hook code; too many and `/initproject` becomes a twenty-question form.
      To be reviewed adversarially before the schema is fixed.
- [ ] A Stop hook cannot force continuation from a `command` hook — that needs a
      `prompt` or `agent` hook returning `{"ok": false, "reason": ...}`, which
      would be the only non-Python hook here. Worth the inconsistency, or drop
      the "no done without a test run" check and rely on the commit gate?
- [ ] "Tests were run" is enforceable; "the tests are meaningful" is not. The
      closest available check is comparing receipts against the verification
      plan's scenario IDs during review.

## Changelog

| Date | Changes |
|------|---------|
| 2026-09-26 | `/doc-write` skill: auto-invoked document writing under the user's style rules, with the trigger boundary in its description, an asymmetric publish policy, and no project- or connector-specific values; 16 tests |
| 2026-09-25 | agy fallback: `agy-probe` reports READY/MISSING/UNAUTHENTICATED/DEGRADED; `/initproject` Step 3b asks for install or login at setup time; `/feature` Phase 1 degrades to Claude's own tools and records that it did |
| 2026-09-25 | post-implementation-review.py: per-project/per-session state with pruning and symlink refusal, exclusion-based source detection, multi-language comment stripping; 16 regression tests written first |
| 2026-09-25 | checkpoint.py hardened against data loss (section boundary, atomic writes with backup, timestamp and --since handling, git range, per-file history heading, all tools kept); 17 regression tests written before the fixes |
| 2026-09-25 | Contract review: pass-through of success output, optional scope arguments, interpreter resolution for Windows, shared helpers, tiers reduced to the two this repo honestly has, template self-checks moved into the gate, coverage theatre reverted |
| 2026-09-25 | Verification contract as four executables (`.claude/scripts/verify-*`); `lint-on-save` delegates and names no tool; `/initproject` Step 5 writes them; `known-pitfalls.md` for measured facts |
| 2026-09-25 | Verification-first: `/feature` Phase 2b verification plan, paired verify tasks, adequacy review; stack-agnostic `rules/testing.md`; duration-based tiers |
| 2026-09-25 | Pinned deep-reasoning to Fable; renamed the two entry skills; added the writing-style rule; repaired the quality gate (`uv run`, `lint-on-save`, `post-test-analysis`) and added hook contract tests; recorded the stack-agnostic direction |
| | Initial |
