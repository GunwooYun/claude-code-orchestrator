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
| Full writing style lives in `.claude/docs/`, with a short pointer rule | `.claude/rules/*.md` loads every session; 466 lines of document style would tax sessions that write no documents | Put the whole style in `.claude/rules/` | 2026-09-25 |

## TODO

<!-- Features to implement -->

Direction: the template must serve any stack, so it should not *know* stacks — it
should know what to ask. Three layers: invariant orchestration principles, a
per-project contract the project declares, and stack knowledge consulted only at
setup time.

- [ ] **Project profile (the contract).** Define the schema and write it once per
      project. Slots: lint / format / typecheck / test commands per tier, where
      each runs (local | container | target), expected duration, source globs,
      doc and ticket destinations, model matrix, response language. The
      verification manifest folds into this rather than living separately.
- [ ] **Hooks read the profile instead of hard-coding tools.** `lint-on-save.py`
      currently names `ruff` and `ty` directly, so a different stack needs the
      hook edited. That is the real blocker to general use.
- [ ] **`/initproject` detects the stack, consults stack knowledge, confirms with
      the user, writes the profile.** Knowledge files under
      `.claude/skills/initproject/references/stacks/` — start with
      `python-django.md` (carries the measured ty/mypy finding), `yocto.md`
      (BitBake: no Python type checker; `bitbake -p`, `oelint-adv`, shellcheck),
      `python-lib.md`.
- [ ] **Verification plan in `/feature`.** Name the tests and their commands
      before code exists; pair each implementation task with a `verify:<tier>`
      task. Highest leverage of the verification work and needs no tooling.
- [ ] **Commit gate.** PreToolUse can deny (`permissionDecision: "deny"`) and can
      be scoped with a handler `if: "Bash(git *)"` — both confirmed. Requires a
      fresh receipt whose fingerprint matches the working tree; fail-open on any
      exception.
- [ ] `checkpoint.py` hardening: the section regex ends only at `^## ` so an
      intervening H1 is destroyed; a malformed timestamp raises an uncaught
      `ValueError`; `--since` is unvalidated and parsed as UTC while grouping is
      local; context files are rewritten non-atomically.
- [ ] `post-implementation-review.py` keys its state on a single hard-coded
      `/tmp` path shared by every project and session, so it self-disables
      permanently once fired. Key it per project and session.
- [ ] agy-unavailable fallback: four skills assume `agy` is installed and no path
      degrades without it.

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
| 2026-09-25 | Pinned deep-reasoning to Fable; renamed the two entry skills; added the writing-style rule; repaired the quality gate (`uv run`, `lint-on-save`, `post-test-analysis`) and added hook contract tests; recorded the stack-agnostic direction |
| | Initial |
