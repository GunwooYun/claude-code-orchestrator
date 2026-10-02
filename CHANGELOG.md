# Changelog

`.claude/ORCHESTRATOR_VERSION` in an adopting project says which entry below it
came from. Check it with `/orchestrator-version` (add `--check-latest` to compare
with the newest release). Releases are tags `vX.Y.Z` on `main`; `develop` holds
work that has not been released. From 1.0.0 the template is used across real
projects, and changes are driven by reports from that use (field reports, or
"what I tried, what happened, how I worked around it").

Upgrading an adopted copy: do not copy the template over it — follow README
「자주 밟는 함정」 (compare each file with the template's history, merge what the
project changed, back up a gitignored `.claude/` first).

## [Unreleased]

Merged to `develop`, not yet released. A release renames this heading.

### Added
- `/initproject` asks whether the orchestrator may push, merge PRs, tag and
  delete merged branches on its own (Step 2 question 5, applied in Step 2b):
  the permission goes to `.claude/settings.local.json`, the instruction to
  `## Project Setup`. Force-push and history rewrites stay denied either way.
- `/isolated-review`: an optional, committed `.claude/isolated-review.json`
  (`{"cap_exclude": [globs]}`) leaves docs and evidence files out of the
  3,000-line cap — not out of the review. A branch that changes the list is
  INCOMPLETE.
- `/feature` Phase 6 and `CLAUDE.md`: a review round ends when it has no
  Medium-or-higher finding; low and nit go with the next change.

### Fixed
From the first field report (Immich, 2026-10-02), where three real runs ended
INVALID, INCOMPLETE, INCOMPLETE for reasons that were not the reviewer's:
- `/isolated-review` no longer counts a dotfile under `.claude/` (a hook's
  state) as a tree change, and INVALID now names the files that changed.
- A file the branch adds counts as read when its whole content reached the
  reviewer through the diff — inline, or through Reads of the diff file that
  cover its lines. Doc-heavy branches were always INCOMPLETE.

## [1.0.0] - 2026-10-02

The template is put into use across projects. No code change from 0.1.1; this
release changes how the template evolves: from here, by reports from real use
rather than by rounds of review.

### Known limits (stated, not hidden)
- `/isolated-review` has not yet run on live work in progress. It was replayed
  on six past units of work in a real project (Immich fork) and compared with
  the person-opened reviews of the same changes: it found 10 of 25 of their
  findings and missed both Medium ones, which needed running code (mutation
  runs, library probes) — a read-only reviewer cannot. It found 10 real issues
  of its own, no false ones; its severities run high. It complements an A2
  review and does not replace it. Details: `docs/isolated-review.md`.

## [0.1.1] - 2026-10-01

Small fixes after 0.1.0 (#12, #13, #14). No change to how a project adopts or
runs the template.

### Changed
- `/isolated-review` field reports ask whether a hidden value kept the person
  from judging a finding. Redaction stays broad (decided 2026-10-01) and is
  narrowed only on that evidence (#14).

### Fixed
- `bash-write-check` no longer reports files git rewrote when git runs next to
  read-only commands (`cd x && git rebase …`, `… | tail`); a writing command
  or a redirection in the same line is still checked. `cut`, `tr` and `jq`
  count as read-only too; `sort` and `uniq` do not (both can write a file)
  (#12, #13).
- `/isolated-review`: a second report in the same second is written as
  `<name>-2.md` instead of overwriting the first; `field-report` reads its
  date (#12).

## [0.1.0] - 2026-09-30

First versioned release. Everything merged up to PR #10. Copies taken before
this release have no `.claude/ORCHESTRATOR_VERSION`.

### Added
- `/initproject` (per project) and `/feature` (per unit of work), replacing
  `/init` and `/startproject` (#1).
- The verification contract: `.claude/scripts/verify-{save,task,unit,full}`,
  exit code as the interface; verification planned before code in `/feature`
  (#1).
- Cost-based routing (token volume × reasoning difficulty), agy fallbacks,
  `/lens-review`, `/doc-write`, `/jira-setup`, `/ticket` (#1).
- `bash-write-check` hook: runs the save gate on files written through Bash
  (#5).
- `/orchestrator-version` and this changelog (#9).
- `/isolated-review`: `/feature` Phase 6's default review, run by a separate
  read-only `claude -p` session (Read/Grep/Glob only, isolation probed before
  every run, secrets redacted, report kept out of git), and `field-report` to
  summarise its runs without code or review text (#10). Tested with the real CLI
  on a seeded test repository only, not yet on a real work branch.

### Changed
- `.claude/docs/DESIGN.md` ships as an empty skeleton; the template's own
  design record moved to `docs/DESIGN.md` (#2).
- `/initproject` and `/feature` hardened from their first real runs: headless
  runs documented as unsupported, H1 retitled, tagline replaced, task list in
  the todo tool or a tracked checklist (#2, #6, #8).
- Default permissions: docker, kill, network and wrapper commands no longer
  auto-run; an `ask` list and more `deny` rules (#4).
- Commits and PRs carry no attribution footer (`attribution` setting).

### Fixed
- The save gate's results never reached the model (stderr with exit 0); they
  now arrive as `additionalContext` (#5).
- `bash-write-check` skips package stores such as `.pnpm-store`; `>/dev/null`
  is not a write (#7).
