# Changelog

`.claude/ORCHESTRATOR_VERSION` in an adopting project says which entry below it
came from (`cat .claude/ORCHESTRATOR_VERSION`). Releases are tags `vX.Y.Z` on `main`; `develop` holds
work that has not been released. From 1.0.0 the template is used across real
projects, and changes are driven by evidence from that use (`usage-report`
counts, or "what I tried, what happened, how I worked around it").

Upgrading an adopted copy: do not copy the template over it — run
`/orchestrator-upgrade` (from 5.1.0), or paste the prompt in README
「업그레이드 절차」 into a copy that predates it. Both follow `tools/UPGRADE.md`
from a fresh clone of the latest release.

## [Unreleased]

### Added
- `tools/upgrade-plan` marks never-shipped skills, agents and rules
  `[loaded]`, and `tools/UPGRADE.md` asks once whether each is the project's
  own or a leftover (showing its description and how often it ran). The first
  real upgrade (3.0.1 → 5.1.0) kept two skills from the template's pre-fork
  original — `startproject`, `review` — unused for weeks yet loaded every
  session, because never-shipped files counted as the project's own.

### Changed
- README §11: the first real project upgrade (Linux, 3.0.1 → 5.1.0) and what
  it showed.
- README 「업그레이드 절차」: copies from before 5.1.0 start the upgrade with one
  line — read the skill file from `main` and follow it — instead of a
  four-line prompt; what the session asks, in the order a 5.0.0 → 5.1.0
  rehearsal against the real release showed, and what to do when a
  permission prompt is refused.

## [5.1.0] - 2026-10-16

Upgrading becomes a skill, and the template works on Windows. The upgrade no
longer means reading README §9 and waiting a day: `/orchestrator-upgrade`
follows the procedure shipped with the release it installs, asks only where the
choice is yours, and checks the hooks right away (`tools/hook-check`). On
Windows the save check never ran before (every save: `WinError 193`); it now
runs, also under a Korean user folder. Verified by rehearsals on macOS and on
Windows 11 (Git Bash), not yet by a real project's upgrade.

**Upgrade:**
1. Delete `.claude/hooks/__pycache__/` if it exists. The old hooks wrote it and
   the new ones do not; where `.gitignore` lacks it, the leftover keeps
   `/isolated-review` refusing the working tree as dirty.

### Added
- Skill `/orchestrator-upgrade`: clones the latest release into a temporary
  directory and follows that clone's `tools/UPGRADE.md`, asking only at
  decision points (GitHub unreachable → retry / a clone path / stop; dirty tree
  or unfinished unit; the version; the plan; each MERGE; edits to project-owned
  files; a failed check; commit; deleting the temporary clone). The skill only
  bootstraps, so an old copy of it still runs the new procedure. Projects from
  before this release paste one prompt instead (README 「업그레이드 절차」).
- `tools/UPGRADE.md` — the one upgrade procedure (repository-only, never
  copied). After applying, it re-runs `upgrade-plan --from <old>`: only MERGE
  and KEEP may remain (no REPLACE / ADD / DELETE, except project-owned files
  the user kept). A `[project-owned]` file the project edited is never copied
  or merged, even as MERGE (`CLAUDE.md`); only CHANGELOG hand steps change it.
  One it never edited (REPLACE) is offered. The commit stages only the files
  the upgrade changed. Local-only template files (`.git/info/exclude`) roll
  back from the backup.
- `tools/hook-check <project>` — runs every hook registered in the project's
  `settings.json` with a payload it reacts to and fails naming the hook that
  crashed, swallowed its own error (`hook error (ignored)`), or whose file is
  missing. It replaces "use it for a day, then read
  `usage-report`" as the post-upgrade hook check; the `usage-report`
  comparison after a few days stays optional.

### Fixed
- The save check never ran on Windows: the hooks exec'd the extensionless
  `#!/bin/sh` `verify-save`, which Windows cannot do, and reported
  `could not run … [WinError 193]` on every save. On Windows an extensionless
  script now runs by its shebang — sh scripts through Git Bash's `sh` (or
  `CLAUDE_CODE_GIT_BASH_PATH`) with `/` paths, Python ones through Python —
  and without `sh` the message names Git Bash. `tools/hook-check` now fails a
  hook whose save check never ran (`could not run` / `timed out after`); it
  reported these hooks ok before. Projects without `verify-save` were not
  affected.
- The save-check hooks under a non-ASCII path on Korean Windows (found under
  `C:\Users\<name>윤건우`): they read Claude Code's UTF-8 payload through the
  cp949 text stream, so the path came out garbled and `lint-on-save` went
  silent; and the check's UTF-8 output was decoded as cp949, so the report
  read "None". They now read the payload as bytes and decode the check's
  output as UTF-8 (`hook-check` too).
- The save-check hooks no longer write `.claude/hooks/__pycache__/`: in a
  project whose `.gitignore` lacks it, that untracked file made
  `/isolated-review` refuse the working tree as dirty (seen on the Windows
  check; not Windows-specific).
- `tools/upgrade-plan` on Windows (found by the Windows rehearsal):
  a CRLF checkout (Git for Windows' default `core.autocrlf=true`) no longer
  makes every unedited file look edited — CRLF counts as LF, as with
  `git hash-object`; and output is UTF-8, so a non-ASCII project path (a
  Korean user name) no longer crashes it on the cp949 code page. `hook-check`
  writes UTF-8 too.

### Changed
- README 「업그레이드 절차」 is an overview: when, how to start (the skill or the
  paste-in prompt), what Claude asks, the immediate check, the optional
  comparison after a few days (3–5 tasks — the 5.0.0 list said "a day"), and
  the manual fallback (follow `tools/UPGRADE.md`). The step-by-step shell
  blocks are gone; the procedure is in one place. After an upgrade, start a
  new Claude session: the running one loaded the old instructions.
- `docs/windows-upgrade-check.md` and `docs/windows-check.md`: Windows checks
  a person or a tester Claude session runs (Git Bash), with pass/fail per
  scenario.
- README §12: feature PRs into `develop` are squash-merged, `develop` → `main`
  is a merge commit, and how to recover when a release PR was squashed.

## [5.0.0] - 2026-10-14

The second direction review (`docs/direction-review-2026-10-13.md`), judged on
counts from a real work project for the first time: what real use did not need
is removed (breaking), `usage-report` makes that evidence re-runnable, and the
Jira/Confluence skills are fixed where real use broke them. README is rewritten
for a first-time reader (terms, Jira/Confluence map, a 5.0.0 upgrade list,
`usage-report` step by step).

**Upgrade — do this in one step**, or every Bash call reports a missing hook:
1. Delete `.claude/hooks/log-cli-tools.py`,
   `.claude/skills/isolated-review/field-report`,
   `.claude/docs/templates/field-report.md`,
   `.claude/skills/feature/references/` and
   `.claude/skills/orchestrator-version/` (all still in tag `v4.3.1`).
   `python3 <template clone>/tools/upgrade-plan <project>` lists them as DELETE.
2. In your `.claude/settings.json`, remove the PostToolUse `Bash` entry
   `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/log-cli-tools.py"`.
3. Project-owned files, by hand: drop the `.claude/logs/cli-tools.jsonl` row
   from `CLAUDE.md`'s 문서구조 table and the "Your past calls are logged…"
   sentence from `.agents/rules/AGENTS.md`.
4. Optional: delete `.claude/logs/cli-tools.jsonl` and
   `.claude/logs/isolated-review/refusals.jsonl`; nothing reads them.
5. A copy upgraded in place from before 2.0.0 may still carry hooks removed
   then. `tools/upgrade-plan` lists such files under PROJECT-ONLY
   "last shipped in X" but does not flag their `settings.json` entries: check
   those by hand, and delete file and registration together (a registered
   leftover keeps running). Then run `.claude/bin/usage-report --since <today>`
   after a day of work: every hook's `errors` column should be 0.
6. `.claude/docs/writing-style.md` is now project-owned. If your copy is the
   template's, take the new file (it no longer carries another team's
   Confluence links and examples); if you edited it, keep yours.
7. If `/jira-setup` ran before and `CLAUDE.md` no longer has `### Jira` (a
   second `/initproject` could erase it), run `/jira-setup` again.

### Removed (breaking)
- Skill `/orchestrator-version`. Its upgrade classifier (`--plan`) moves to
  the repository-only `tools/upgrade-plan`: it was always run from a template
  clone, never from the project's copy, so it no longer ships. Showing the
  installed version and `--check-latest` are gone (`cat
  .claude/ORCHESTRATOR_VERSION`; the plan lists the CHANGELOG entries in
  between). 0 uses in both real adopters; its description cost every session.
- Hook `log-cli-tools`. On a real adopter whose system `python3` is 3.10 it
  failed on every Bash call for two weeks (1,933 non-blocking errors,
  `ImportError: datetime.UTC`) and nothing showed it; nothing read its log.
  Gone with it: the call-shape rules it imposed on the general-purpose
  executor. agy calls are now counted from transcripts by `usage-report`.
- `/isolated-review`'s `field-report` and its template: never run in a real
  adopter; its one report was closed unsent. `run-review` no longer writes
  `refusals.jsonl`; a REFUSED reason is still redacted before it is printed.
- `/feature`'s `references/` (task patterns, review procedures, research
  fallback): opened 0 times in two real projects' transcripts. What still
  matters is in `SKILL.md` and `CLAUDE.md`.
- Unreferenced `summary.jpg`; pointers to `.claude/docs/libraries/` (removed
  in 4.2.0).

### Added
- `.claude/bin/usage-report`: counts how a project used the template, from
  what is already recorded — Claude Code's session transcripts. Per template
  skill (0 included), subagent type, hook file (runs, output, **errors**);
  denied tool calls; verify-tier runs and failures; how far `/feature`
  sessions get; main vs subagent tokens; agy calls and probe states. Counts
  only: no text, paths, or names that are not the template's. No new hook.
  Transcripts are deleted after `cleanupPeriodDays` (default 30), so run it
  periodically with `--since` and keep the reports. On another machine,
  without copying anything there:
  `ssh <host> 'cd <project> && python3 - --since <date>' < .claude/bin/usage-report`.
  It also splits Atlassian MCP calls (read / write) between sessions that ran
  `/ticket`, `/jira-setup` or `/doc-write` and the rest.

### Changed
- The gate type-checks shipped Python at 3.10 (`ty` python-version, ruff
  target `py310`): hooks run on the adopter's system `python3`, and ruff's
  py311 target is what suggested the `datetime.UTC` import.
- `/isolated-review`: the 3,000-line-cap refusal names `cap_exclude`. The cap
  was hit in two real projects (4,104 and 4,311 lines); the option was used
  in neither.
- README: `/doc-write`, `/jira-setup`, `/ticket` are in real use (the "never
  run" row predated counting that project); "leaving usage evidence" replaces
  the field-report section (sections renumbered).
- Shorter shipped prose where it did not instruct: the general-purpose
  diagram, AGENTS.md's position tree, isolated-review SKILL.md's lock details
  (the do-not-loosen rule, Fable pin and A2 fallback stay), known-pitfalls'
  hook-writing facts. `docs/` design history trimmed (git keeps it).
- The template's own tests: prose checks with no incident behind them removed;
  the Python-floor test now runs at 3.10 instead of being skipped.

### Fixed
- `## Project Setup` kept by every writer: on the work project `### Jira`
  (from `/jira-setup`) was gone after a second `/initproject` recreated the
  section, so `/ticket` had no write policy. `/initproject`, `/jira-setup` and
  `/doc-write` now edit only their own part and create the section if absent.
- `.claude/docs/writing-style.md` shipped one team's Confluence links, its
  reference report and sentences from its own domain. Removed; the patterns
  stay as general rules. It is project-owned from now on (`tools/upgrade-plan` marks it).
- `/ticket`, `/jira-setup`, `/doc-write` shortened where they restated the
  style guide, each other or their own steps.
- "1 skill call vs ~150 MCP calls" (README, design docs) mixed two periods:
  136 of 153 calls predate the skills; after installation all 17 ran in sessions that ran them.

## [4.3.1] - 2026-10-13

README only. 4.3.0 was released with the README behind it. Upgrading from
4.3.0: only `.claude/ORCHESTRATOR_VERSION` changes in an adopted copy.

### Changed
- README, brought up to 4.3.0: `/initproject` Step 3 names the `STALE` probe
  state and Step 3c (`/agy-models`). The review verdicts say Claude Code's
  runtime files and `.claude/` dotfiles do not make INVALID. The upgrade
  procedure says to keep your Model policy table rows and to re-probe after.
- README §13 (developing this repository): a release updates README to its
  own changes in the release-prep PR, and the develop → main PR is merged
  with a merge commit — a squash (4.2.0, #52) made the next release conflict.

## [4.3.0] - 2026-10-13

**Upgrade soon if you use agy:** on agy 1.3.3 every tier slug this template
named is rejected, so every agy call failed and the probe told you to wait.
Also: an upgrade-plan tool, a per-tier agy model choice, and a fix for
isolated reviews ending INVALID on Claude Code's own runtime files. Nothing is
removed. Upgrading: run `check --plan` (Added), then `.claude/bin/agy-probe` —
`READY`, or `STALE` → `/agy-models`.

### Added
- **`check --plan <project>`: the upgrade classification as a tool, read-only.**
  Run the template clone's script (`.claude/skills/orchestrator-version/check`)
  against an adopted copy: every file under `.claude/`, `.agents/` and
  `CLAUDE.md` is classed REPLACE / MERGE / KEEP / DELETE / DELETE-MODIFIED /
  ADD / ABSENT / PROJECT-ONLY by the README hash rule, project-owned files are
  marked, and PROJECT-ONLY files are grouped by the last release that shipped
  them. It also lists scripts that lost their exec bit, `settings.json` hook
  registrations left without a file, and the CHANGELOG entries to read. It
  changes nothing. Why: a real 3.1.0 copy still carried 18 files earlier
  upgrades should have deleted (hooks, and skills colliding with built-ins), and
  the README procedure had no tool; the plan lists exactly those 18.
- **`/agy-models`: choose the agy model of each tier** (user-invoked; also
  `/initproject` Step 3c). Shows the table and the Gemini slugs agy offers,
  asks for T1–T4, writes the table, re-probes to `READY`. `STALE` points to
  it, so it is run again whenever agy renames its models — without re-running
  all of `/initproject`. Why: agy quota differs per person — with quota to
  spare, high on every tier is a reasonable choice.

### Fixed
- **`/isolated-review`: Claude Code's runtime files no longer make a review
  INVALID.** `.claude/scheduled_tasks.lock` (written by any Claude session in the
  project, the reviewer included) appeared mid-run and a real review ended
  INVALID with the reviewed commit unchanged. The snapshot and the clean-tree
  check now skip the paths Claude Code lists in its `# claude-code-runtime`
  block of `.git/info/exclude`; edits to any other file under `.claude/` are
  still caught, gitignored or not. Hit INVALID naming one of those paths in an
  adopted copy: upgrade `run-review`.
- **agy model slugs: every tier failed on agy 1.3.3.** It offers only the 3.8
  Flash slugs; the 3.7 Flash and 3.1 Pro slugs the Model policy table named
  are rejected (exit 1). T1 is now 3.8 Flash low, T2–T4 3.8 Flash high (agy
  replaced 3.1 Pro High with 3.8 Flash High). The table in
  `.claude/rules/antigravity-delegation.md` is now the only place a slug is
  written; the agent file, `/feature` and `CLAUDE.md` name the tier, and
  `AGENTS.md` uses a generic `{slug}`. Upgrading: take those files as they
  are, and keep your own table rows if you changed them.
- **`agy-probe` reports `STALE`** (exit 1) when agy no longer offers a slug
  the table names, or a tier row has none — checked with `agy models` before
  its own call. It used to report DEGRADED, "wait", for a fault that waiting
  never fixes. It reads its own slug from the table.

## [4.2.0] - 2026-10-12

Maintenance from deferred items. Two shipped files that nothing used are gone
(see Removed — delete them when upgrading); everything else changes only this
repository's own gate and tests, which adopting projects do not copy.

### Changed
- **This repository's gate runs its tests in parallel: ~90 s → ~25 s.**
  `poe test` is now `pytest -n auto` (new dev extra `pytest-xdist`); most of the
  suite waits on subprocesses, not CPU. Same results as a serial run (335 passed,
  1 skipped). Maintainers: `uv sync --all-extras` after pulling. Adopting projects
  are unaffected — `pyproject.toml` is not copied, and their gate is their own.
- `tests/test_agy_probe.py`: the temp-file leak test now watches its own `TMPDIR`.
  It globbed `/tmp` for the capture file's old name, so it could not fail on a
  real leak.
- This repository's tests no longer depend on local state: the model-tier
  consistency test read untracked files and failed on a fresh clone (it now reads
  `git ls-files`), and the hook contract tests no longer write a mark into the
  real `.claude/logs/bash-marks/`.
- README 「업그레이드 절차」 now classifies four template-owned files it left out:
  `docs/writing-style.md`, `docs/templates/field-report.md`, `scripts/README.md`
  and `ORCHESTRATOR_VERSION`.

### Removed
- `.claude/docs/libraries/_TEMPLATE.md`. No instruction pointed at it: the
  general-purpose agent's library prompt defines its own layout. Upgrading: delete
  it unless the project filled it in; `.claude/docs/libraries/` itself stays the
  place for library notes and is created when the first one is saved.
- `.agents/skills/context-loader/`. agy's own conversation store shows it never
  activated: 0 of 61 conversations on the maintainer's machine, 21 of them in an
  adopting project that has it. `.agents/rules/AGENTS.md` stays — it is the
  context agy reads. Upgrading: delete `.agents/skills/context-loader/`. Restore
  from tag `v4.1.0` if a project relies on it.

## [4.1.0] - 2026-10-08

The second tuning pass: a quarter less text enters every session. Rules that
apply only to some files now load when such a file is opened — checked by hand
in a live session (`docs/DESIGN.md` Open Questions). Nothing is removed; one
upgrade step is by hand, for the project-owned `testing.md`.

### Changed
- **Less text in every session: always-loaded rules 30,361 → 22,864 bytes.**
  `rules/coding-principles.md` now loads only when a Python file is read or edited
  (`paths:` frontmatter; `/initproject` rewrites the globs for other stacks), and
  carries the Python security examples. `rules/security.md` keeps a short
  language-agnostic kernel. `rules/testing.md` keeps principles 1–5 and the tier
  table; test naming, cases, mocking and the checklist moved to the new
  `rules/test-writing.md`, loaded for files under `tests/`. `rules/writing-style.md`
  keeps the honesty rules and its pointers. The `doc-write` and `ticket`
  descriptions are shorter; their triggers are unchanged.
- Upgrading: `coding-principles.md`, `security.md` and `writing-style.md` are
  template-owned and can be replaced. `testing.md` is project-owned — **by hand**,
  move its "테스트 작성" and "체크리스트" sections into a new
  `rules/test-writing.md` (copy the template's frontmatter and adjust the glob to
  the project's test location), or leave `testing.md` as it is.
- The gate cannot show that the scoped rules load when they should; a hand check
  in a live session did (an `InstructionsLoaded` hook — `/context` and `--debug`
  do not show rules loaded on demand). Still unverified: that the shorter
  descriptions trigger as before. What to watch: `docs/DESIGN.md` Open Questions.

## [4.0.0] - 2026-10-08

The first tuning pass measured from real use. Three skills that recorded use
never invoked are gone — deep-reasoning and agy are called exactly as before,
through the rules and the agent files. Breaking because three slash commands
disappear; an adopted copy upgrades by README §9 (now covering added files).

### Removed (breaking)
- **`/deep-reasoning`, `/antigravity-system` and `/checkpointing` skills.** Recorded
  use (9 sessions, 3 projects) shows no invocation of any of them (Skill tool
  calls and slash commands; a transcript cannot show an auto-activation that
  leaves no tool call), while the deep-reasoning
  subagent ran 30 times and agy 79 times without them. Calling deep-reasoning
  and agy works as before: the rules and the agent files already carried how.
  The agy prompt templates (pre-implementation research, one library) moved to
  `.claude/agents/general-purpose.md`. `/checkpointing` is gone with its tests;
  the `log-cli-tools` hook and `.claude/logs/cli-tools.jsonl` stay. A
  `## Session History` an earlier `/checkpointing` wrote into `CLAUDE.md` (or
  `## Consultation History` in `.agents/rules/AGENTS.md`) is no longer
  rewritten; delete it by hand.

### Changed
- **`agy-probe` moved to `.claude/bin/agy-probe`.** The `settings.json` allow
  entry changes from `Bash(.claude/skills/antigravity-system/agy-probe)` to
  `Bash(.claude/bin/agy-probe)`.
- **README upgrade procedure** covers files a release adds, lists `.claude/bin/`
  as template-owned, and says to apply by hand what CHANGELOG changes inside a
  project-owned file.

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
