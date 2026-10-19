# Upgrade procedure

The procedure for bringing a project's copy of the template up to a release. It lives
in the template repository and is never copied into projects, so whoever follows it —
the `/orchestrator-upgrade` skill, the paste-in prompt in README §9, or a person by
hand — always reads the version that matches the release being installed.

**Inputs**

| Name | Meaning |
|---|---|
| `CLONE` | A full clone of the template (with tags), checked out at the target tag `vNEW` |
| `PROJECT` | The project root (where Claude was started) |
| `CLONE_KIND` | `temporary` — made for this run in a `mktemp -d` directory (`CLONE_PARENT`); `user-supplied` — the user's own clone |

**Rules for whoever follows this**

- Talk to the user in their language. Check before you ask; ask only when a check fails
  or the decision is the user's. Every **Ask** below is a stop until the user answers.
- Change nothing outside `PROJECT`, `CLONE_PARENT`, `~/usage-reports/` and the backup file.
- If something fails mid-way, stop, report what was done, and offer step 9 (roll back).
  Do not improvise a fix to a template file.
- On Windows run everything in Git Bash (Claude Code's Bash tool). PowerShell cannot run
  the template's hooks or `sh` scripts.
- `CLONE`, `PROJECT`, `CLONE_PARENT`, `PY`, `OLD`, `NEW` are placeholders. Shell variables do
  not survive between Claude Code's Bash calls: keep the literal values and write them into
  every command.

## 0. Python

The template's tools need Python 3.10 or newer. Find the launcher once and use it as `PY`:

```bash
for c in python3 python "py -3"; do $c -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null && { echo "$c"; break; }; done
```

None found → tell the user Python 3.10+ is needed and stop.

## 1. Preflight

- `git -C "$PROJECT" status --porcelain` is not empty → **Ask:** stop so they can commit
  or stash first (recommended) / continue anyway (the upgrade will be mixed with their
  changes).
- `CLAUDE.md` or `CLAUDE.local.md` has a `## Current Project` whose `- Status:` is not
  `완료` → **Ask:** finish that unit first (recommended) / continue. The upgrade does not
  touch that block, but an upgrade between units can be reverted on its own.
- `PROJECT` is not a git repository → say the backup in step 3 is the only way back.
- `git -C "$PROJECT" ls-files --error-unmatch .claude/ORCHESTRATOR_VERSION` fails → the
  template files are local-only (ignored, e.g. via `.git/info/exclude`): git cannot commit
  or undo them, so step 7 is skipped and the backup in step 3 is the way back. Say so.

## 2. Versions and what changes

- `OLD` = `PROJECT/.claude/ORCHESTRATOR_VERSION`. Missing → **Ask** which release the
  copy was taken from, and pass `--from OLD` to every `upgrade-plan` call below.
- `NEW` = the tag `CLONE` is on. `OLD == NEW` → say so and go to step 8.
- Read `git -C "$CLONE" show vNEW:CHANGELOG.md` from the top down to `## [OLD]`. Summarise
  for the user in a few lines: what changed, and every hand step (the numbered list under
  an entry's bold **Upgrade** line).
- **Ask:** upgrade `OLD → NEW`?

## 3. Branch, baseline, backup

```bash
cd "$PROJECT"
git switch -c upgrade-orchestrator            # exists → Ask for another name
mkdir -p ~/usage-reports
$PY "$CLONE/.claude/bin/usage-report" > ~/usage-reports/"$(basename "$PWD")-$(date +%F)-before.md"
tar czf ~/backup-"$(basename "$PWD")-$(date +%F)".tgz .claude $( [ -d .agents ] && echo .agents ) CLAUDE.md
```

A failing `usage-report` is noted and does not stop the upgrade. A failing backup stops it.

## 4. Plan and approval

```bash
$PY "$CLONE/tools/upgrade-plan" "$PROJECT"
```

Exit 2 → show its stderr and stop. Otherwise show the user, grouped:

- **MERGE** — files the project (or `/initproject`) changed and upstream changed too.
  Name each one and what the project's edit was.
- **DELETE**, **DELETE-MODIFIED**, **HOOKS** — what will be removed, and the
  `settings.json` registrations that must go in the same step.
- **ABSENT**, **PROJECT-ONLY "last shipped in X"** — shipped files the project lacks;
  leftovers an earlier upgrade should have removed.
- **PROJECT-ONLY "never shipped" marked `[loaded]`** — skills, agents or rules this
  template never shipped but every session loads: the project's own, or leftovers of an
  older template (a real project kept `startproject` and `review` from the pre-fork
  original). For each, show its `description:` line and, if the project has transcripts,
  how often it ran: `grep -rlE 'command-name>/<name><|"skill": ?"<name>"'
  ~/.claude/projects/*<project dir name>*/*.jsonl | wc -l`.
- **`[project-owned]`** — never overwritten; only the CHANGELOG hand steps touch them.
- REPLACE / ADD — counts, and the list on request.

**Ask:** apply this? The user may exclude files. Record the exclusions and the approved
MERGE set; step 6 checks against them.

## 5. Apply

Work from `CLONE` (it is on `vNEW`). Paths are relative to the project root.

**`[project-owned]` paths** (the plan marks them in every class):

- MERGE, KEEP, DELETE-MODIFIED — the project edited it: never copy or rewrite it. It can
  show as MERGE (`CLAUDE.md` usually does). Show the upstream change
  (`git -C "$CLONE" diff vOLD vNEW -- <path>`) for information; only the CHANGELOG hand
  steps below change it.
- REPLACE, ADD, DELETE — the project never edited it (an untouched skeleton such as
  `docs/DESIGN.md`): **Ask** once for the list — take upstream (the new version, or the
  deletion, as the table below does) / keep the project's. A CHANGELOG hand step that names one of them wins.

The table is for every path not kept by these rules.

| Class | Action |
|---|---|
| REPLACE, ADD | `cp "$CLONE/<path>" "<path>"` (create the directory first) |
| DELETE | `rm "<path>"`; remove directories left empty |
| DELETE-MODIFIED | **Ask** per file: delete / keep |
| ABSENT | **Ask** once for the list: add back / leave out |
| PROJECT-ONLY "last shipped in X" | **Ask** once for the list: delete / keep |
| PROJECT-ONLY "never shipped" `[loaded]` | **Ask** once for the list: keep (the project's own) / delete (a leftover; the backup still has it) |
| MERGE | One file at a time: show the project's edit (`git -C "$CLONE" show vOLD:<path>` vs the project file) and the upstream change (`vOLD` vs `vNEW`); write the `vNEW` file with the project's edit re-applied; show the result diff; **Ask** to confirm |
| EXEC BIT | `chmod +x` each listed path |
| HOOKS | Remove each listed registration from `.claude/settings.json` (it is project-owned: show the edit, **Ask**) |
| ADD of a script | Its note says where to allow it in `settings.json` permissions — show the edit, **Ask** |

Then the CHANGELOG hand steps for every version after `OLD`, in order. Each one that
edits a project-owned file (`CLAUDE.md`, `settings.json`, `.agents/rules/AGENTS.md`, …):
show the edit, **Ask**, apply. A step that says to re-run a skill (for example
`/jira-setup`) is listed for the user in step 8, not run here.

Delete a hook file and its `settings.json` registration in the same step: a
registration without its file fails on every tool call.

## 6. Check

All four, then report the results together.

1. **Nothing left behind.**

   ```bash
   $PY "$CLONE/tools/upgrade-plan" "$PROJECT" --from OLD
   ```

   Expected: applied files are only counted (`NOOP: N files already match NEW`), the
   approved MERGE files and the `[project-owned]` ones stay listed as MERGE (they differ
   from both versions), `[project-owned]` files the user chose to keep stay in their class,
   KEEP lists
   the project's own edits (including the hand steps just applied), and the files the user
   excluded or chose to keep stay as they were. Any other REPLACE / ADD / DELETE /
   DELETE-MODIFIED / ABSENT line, or a HOOKS or EXEC BIT section, is a step that was
   missed — go back to step 5 for it. The `--from` override note is expected.

2. **Every hook runs.**

   ```bash
   $PY "$CLONE/tools/hook-check" "$PROJECT"
   ```

   Exit 0 → done. Exit 1 → show the `FAIL` lines; **Ask:** diagnose and fix / roll back
   (step 9). Exit 2 → `settings.json` is missing or not valid JSON: fix that first.

3. **The project's gate.** `.claude/scripts/verify-task` if it exists — report the exit
   code. A failure that also fails on the commit before the upgrade is not the upgrade's;
   say so instead of fixing it.

4. **agy.** `.claude/bin/agy-probe` — report the first word. `STALE` → suggest `/agy-models`.

Then `cat .claude/ORCHESTRATOR_VERSION` (must say `NEW`) and `git status`.

## 7. Commit

**Ask:** commit now? If yes:

Stage only what step 5 changed — not whole directories, which may hold untracked
runtime files (`.claude/logs/`, `__pycache__/`):

```bash
git add -- <each path written or added in step 5>
git add -u -- .claude CLAUDE.md $( [ -d .agents ] && echo .agents )   # deletions and edits
git commit -m "chore: upgrade claude-code-orchestrator template to vNEW"
git ls-files --error-unmatch -- <each ADD path taken in step 5>        # must exit 0
```

The last line fails on an added file that was left out of the commit: stage it and amend.

Local-only template files (step 1) skip this; the backup is their way back.

## 8. Clean up and hand over

- `CLONE_KIND` = `temporary` → **Ask** to delete it. Before deleting, check that
  `$CLONE_PARENT/claude-code-orchestrator` holds `.git` and `.claude/ORCHESTRATOR_VERSION`;
  then `rm -rf "$CLONE_PARENT"`. Anything else → leave it and print the path.
- `CLONE_KIND` = `user-supplied` → never delete it.
- Tell the user:
  - the upgrade is finished — nothing needs to wait;
  - hand steps left for them (skills to re-run, e.g. `/jira-setup`);
  - optional, after a few days of normal work (3–5 tasks): run
    `.claude/bin/usage-report --since <today>` and compare it with the `before` report in
    `~/usage-reports/` — delegation counts, `/feature` phases, gate runs, hook errors. If
    something got worse, roll back (step 9).
  - the branch `upgrade-orchestrator` goes to a PR or a merge as usual;
  - **start a new Claude session before working on**: this session loaded the old
    `CLAUDE.md`, rules and skills when it started (hooks are picked up live). Work in
    progress continues from `## Current Project`.

## 9. Roll back

Only on the user's word.

- Committed: `git revert <upgrade commit>`.
- Not committed, template files tracked by git: `git switch -` back to the previous branch
  after `git stash -u` (the stash keeps the attempt for inspection), or discard the branch.
- Local-only template files, or no git: `rm -rf .claude .agents CLAUDE.md` then
  `tar xzf ~/backup-<project>-<date>.tgz`.
