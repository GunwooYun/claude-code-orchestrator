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
- [ ] **Four scripts as the contract.** `.claude/scripts/{lint-file,check,test-unit,test-full}`,
      shipped calling this repo's own `uv run ruff/ty/pytest`. Exit code is the
      schema. Container path mapping, env and sudo live inside the script, where
      the project owner can run it by hand.
- [ ] **`lint-on-save.py` calls `lint-file` if present, else prints one line.**
      Roughly 20 lines shorter than today. Add `Bash(.claude/scripts/*)` to
      settings.json allow, and `.claude/scripts/` to `TEST_BUILD_COMMANDS` in
      `post-test-analysis.py`.
- [ ] **`/initproject` writes the four scripts per stack.** Yocto: `lint-file` =
      `oelint-adv` on `.bb`/`.bbappend`, `check` = `bitbake -p`, `test-full` =
      image + `testimage`. Docker: wrap each in `docker compose exec -T`.
- [ ] **One `initproject/references/known-pitfalls.md`** — measured facts with a
      date and how they were measured (first entry: `ty` reports 3 false
      positives on 3 correct Django model lines, no field-descriptor plugin;
      mypy + django-stubs clean, 2026-09-25). NOT per-stack recipe files: those
      duplicate the model's own knowledge and rot, and a stale recipe the model
      trusts over its own knowledge is worse than no recipe. Unknown stack → one
      agy T3 query at setup.
- [ ] `checkpoint.py` hardening: the section regex ends only at `^## ` so an
      intervening H1 is destroyed; a malformed timestamp raises an uncaught
      `ValueError`; `--since` is unvalidated and parsed as UTC while grouping is
      local; context files are rewritten non-atomically.
- [ ] `post-implementation-review.py` keys its state on a single hard-coded
      `/tmp` path shared by every project and session, so it self-disables
      permanently once fired. Key it per project and session.
- [ ] agy-unavailable fallback: four skills assume `agy` is installed and no path
      degrades without it.

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
| 2026-09-25 | Verification-first: `/feature` Phase 2b verification plan, paired verify tasks, adequacy review; stack-agnostic `rules/testing.md`; duration-based tiers |
| 2026-09-25 | Pinned deep-reasoning to Fable; renamed the two entry skills; added the writing-style rule; repaired the quality gate (`uv run`, `lint-on-save`, `post-test-analysis`) and added hook contract tests; recorded the stack-agnostic direction |
| | Initial |
