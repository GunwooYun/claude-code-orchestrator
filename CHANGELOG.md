# Changelog

`.claude/ORCHESTRATOR_VERSION` in an adopting project says which entry below it
came from. Check it with `/orchestrator-version` (add `--check-latest` to compare
with the newest release). Releases are tags `vX.Y.Z` on `main`; `develop` holds
work that has not been released. Versions stay `0.x` while features are still
being validated in real use.

Upgrading an adopted copy: do not copy the template over it — follow README
「자주 밟는 함정」 (compare each file with the template's history, merge what the
project changed, back up a gitignored `.claude/` first).

## [Unreleased]

Merged to `develop`, not yet released. A release renames this heading.

### Fixed
- `bash-write-check` no longer reports files git rewrote when git runs next to
  read-only commands (`cd x && git rebase …`, `… | tail`); a writing command
  or a redirection in the same line is still checked.
- `/isolated-review`: a second report in the same second is written as
  `<name>-2.md` instead of overwriting the first; `field-report` reads its
  date.

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
