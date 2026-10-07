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

### Removed
- **`/deep-reasoning`, `/antigravity-system` and `/checkpointing` skills.** Recorded
  use (9 sessions, 3 projects) invoked none of them, while the deep-reasoning
  subagent ran 30 times and agy 79 times without them. Calling deep-reasoning
  and agy works as before: the rules and the agent files already carried how.
  The agy prompt templates (pre-implementation research, one library) moved to
  `.claude/agents/general-purpose.md`. `/checkpointing` is gone with its tests;
  the `log-cli-tools` hook and `.claude/logs/cli-tools.jsonl` stay.

### Changed
- **`agy-probe` moved to `.claude/bin/agy-probe`.** Update the `settings.json`
  allow entry when upgrading a copy.

### Upgrading
- Delete `.claude/skills/deep-reasoning/`, `.claude/skills/antigravity-system/`
  and `.claude/skills/checkpointing/` from the copy. A `## Session History`
  section an earlier `/checkpointing` wrote into `CLAUDE.md` (or
  `## Consultation History` in `.agents/rules/AGENTS.md`) is no longer
  rewritten; delete it by hand if it is there.

## [3.1.0] - 2026-10-07

The first change driven by a handoff report from an adopting project. The agy
log no longer records false successes. The rules now cover how review findings
are weighed, how files are edited, and what a format check may demand.

### Fixed
- **`log-cli-tools` no longer logs a false success.** It read the Bash tool's
  stdout as agy's answer, so a call redirected to a file, captured with
  `$(...)` or followed by `|| echo` / `; echo EXIT_CODE=$?` was logged with the
  echo as its response and marked a success (an adopting project: 10 of 28
  calls). Only a single-line `agy …` on its own is judged now (`<file` and a
  final `| tee` allowed; no `2>file`, inline comment, backslash, `$'`, `$(`
  or `${`); every other shape is `success: null` with a blank response and a
  `stdout_target` saying why. A differential test checks every judged shape
  against real bash (#31).
- `/checkpointing` renders that unknown outcome as `[UNKNOWN]` instead of
  `[FAILED]` (#31).
- **A long agy call is no longer logged `[FAILED]` after it succeeds.** Past
  the Bash tool's 2-minute default the call was moved to the background: it
  finished, but the log hook had already recorded the empty stdout as a
  failure and never fired again (measured). The agy templates now tell callers
  to pass the Bash tool `timeout: 600000`, and keep `--print-timeout` at 9m,
  under that 10-minute foreground maximum. A consistency test keeps every
  template's limit below it.
- **`/isolated-review` usability.** `--base develop` now means `origin/develop`
  when that exists. It refused in a clone with only the remote branch, and a
  stale local branch would widen the range; pass `refs/heads/<name>` for a
  local one. A dirty-tree refusal now says to commit the files or list
  local-only ones in `.gitignore` / `.git/info/exclude`. After the verbatim
  report, the session adds a complete translation into the user's language,
  since the user judges each finding.
- **Tests are type-checked, and clean.** Four test files carried 16
  pre-existing `ty` errors (a module loaded from a path: `spec` possibly
  `None`, attributes unknown; a `Path | None` attribute). They were not bugs,
  but the save check printed them again on every edit of those files. Fixed at
  the source, and `tests/` joined the gate's type check so new ones are caught.

### Changed
- The agent and skill docs ask for one agy call per Bash command, alone, and
  `| tee <file>` when a copy on disk is needed (#31).
- **Review findings are filtered by real occurrence.** A finding whose input
  does not occur in real use — a usage nobody has, a condition that cannot
  arise, an input built only in theory — is recorded, not fixed, whatever its
  severity, and never starts another implement → review → fix round. Goals
  are not set as open-ended absolutes, and an agreed stop condition is not
  reopened by a theoretical finding. Defined in `CLAUDE.md` 운영 주의사항;
  `/feature` and `/isolated-review` point to it (#32).
- **`/initproject` puts a format check in a gate only if the project has
  adopted that formatter** — a config exists and (nearly) all tracked files
  already pass. Otherwise it leaves the check out and reports the measured
  count. A format check judges appearance only; on an unformatted codebase it
  fails every save of untouched code, and reformatting other people's code
  pollutes diffs. Static checks (undefined names, type errors) stay. Measured
  case recorded in `references/known-pitfalls.md` (414 of 555 files) (#34).
- **"Edit with Edit/Write" now states its priority and exceptions.** It wins
  over other instructions that allow sed/heredoc edits (auto mode says so),
  because a Bash edit skips the save check (a whole session's hooks never ran
  in an adopting project). Bash stays the tool for files in a container, on a
  remote device or needing privileges, binary files, tool output and bulk
  replacement — written for the shell where it runs, then re-read and checked.
- **deep-reasoning marks every factual claim** `[verified: …]` /
  `[inference]` / `[unverified]`, and the orchestrator re-checks the
  unverified ones and those a decision rests on — a count reported without its
  method was off by one, and a "judged by reading" finding was wider in scope.
- **`/feature` marks the Current Project block `Status: 완료 (date)`** when the
  unit ends, so a session opened before the next `/feature` does not read a
  finished unit as current.
- **Bash output with known lines is filtered before it is delegated**
  (`tail`, `grep`), with the full output kept in a file and the exit code as
  the verdict; output that needs understanding still goes to a subagent.
- **README** updated for 3.1.0:
  - Separate Linux / macOS and Windows (PowerShell) commands for the template
    copy, backup, local-only exclude and smoke test. The Windows commands are
    marked unverified.
  - Directory changes are written as instructions, not as `cd` inside code blocks.
  - Upgrade checks compare git content hashes. `diff` reports a file as changed
    when only its execute bit differs.
  - The hook, review, verification and pitfall sections describe this release's
    behaviour.

## [3.0.1] - 2026-10-05

Documentation only — nothing that ships into a project changed.

### Changed
- README rewritten for 3.0.0 as a step-by-step adoption guide (copy, commit
  policy, `/initproject` step by step with its five questions, smoke test,
  first `/feature`, review, merge), with six diagrams, the upgrade procedure
  and what is verified (#28).

## [3.0.0] - 2026-10-05

The optimization pass (#25) and the first change driven by the second field
report: work is checked against the project's goal.

### Added
- **Goal check.** `/initproject` asks what "done" looks like and records it as
  `완료 지점` in `## Project Setup`; `/feature` Phase 2 first says which of
  those items the work serves (or that none does, and asks whether to go on),
  and resolves an ambiguous feature name against existing features before
  researching it. From the Immich field report (2026-10-04): 200+ commits of
  extras after the two core features were done, and "구글 로그인" built as the
  wrong feature — the same "no definition of done" this repository had.

### Removed (breaking)
- Hooks `suggest-deep-reasoning-before-write` and `post-test-analysis` — the
  same unmeasured-nudge class as the four removed in 2.0.0. Remove their
  `settings.json` registrations in the same step.
- `/checkpointing --full` and `--analyze` (never run; skill mining contradicts
  "new skills only from field reports"). Session-history mode stays.
- Orphan shipped files: two obsolete research notes, the writing-style template
  and two unreferenced skill references; three uncalled functions.

### Changed
- `/feature` SKILL.md keeps what every run needs; the A2 review procedure, the
  Option B prompt and the no-agy research prompt moved to `references/`
  (loaded on demand): 25 KB → 21 KB per use.
- `/deep-reasoning` and `/antigravity-system` SKILL.md no longer restate the
  always-loaded rules or the executor's command lines.
- `rules/testing.md` and `rules/dev-environment.md` drop examples the model
  already knows. Always-loaded context 31.9 KB → 28.7 KB; ratchet 31 KB.
- Tests that only matched prose (CLAUDE.md sections, doc-write, Jira, several
  consistency classes) were removed; structural checks that caught real breaks
  stay.

## [2.0.0] - 2026-10-03

The direction review (`docs/direction-review-2026-10-03.md`). The template is an
**orchestrator**: the main session talks, decides and delegates; subagents work
in their own contexts and return summaries. This release cuts what does not
serve that and stops building: from here, changes come only from field reports.

### Removed (breaking)
- Skills `/plan`, `/tdd`, `/simplify`, `/design-tracker`, `/update-design`,
  `/research-lib`, `/update-lib-docs`, `/lens-review` — never run in real work.
- Hooks `agent-router`, `suggest-antigravity-research`,
  `suggest-deep-reasoning-after-plan`, `post-implementation-review` — nudges
  whose effect was never measured. Their `settings.json` registrations are gone
  too; **an adopting project must remove its own registrations of these hooks
  in the same step**, or every edit fails on a missing hook file.
- Everything removed is still in tag `v1.1.0`.

### Changed
- `CLAUDE.md` opens with the purpose and the one test for any change ("does it
  improve delegation, context saving or result quality?"); template history
  and test-file references are out. The rules files keep only their decisions.
  Always-loaded context: 51 KB → about 32 KB (cap lowered to 35 KB).
- README: purpose section; the "what is verified" table states current facts
  (agy is in real use; four skills never run).
- Phrase tests on the rewritten rules are reduced to the four rules that matter.

## [1.1.0] - 2026-10-02

The first changes driven by a field report (Immich, #20), plus the git-operations
choice in `/initproject` (#19).

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
