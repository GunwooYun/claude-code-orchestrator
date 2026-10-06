---
name: initproject
description: First-session setup after copying the orchestrator template into a project. Detects the stack, confirms the per-agent model matrix with the user, checks whether agy is installed and logged in (asking for installation or login while a person is present), writes the verification scripts in .claude/scripts/ (one per tier the project honestly has) that form this project's contract with the orchestrator, adapts CLAUDE.md / rules / permissions where the template's own toolchain shows through, and seeds the agy context (.agents/rules/AGENTS.md) and DESIGN.md. Run once per project.
disable-model-invocation: true
---

# Initialize Project Configuration (first session)

You have just been copied into a new project together with `.claude/`, `.agents/`
and `CLAUDE.md`. Make the template fit **this** project. Work through the steps
in order; skip a step when it does not apply and say so in the final report.

## Ground rules

- `CLAUDE.md`: touch only the H1 title line, `## 기술 스택(Tech Stack)` and `## Project Setup`
  (create it if missing, place it after `## 언어 프로토콜`, then
  `## Current Project`, then **before** any `## Session History`). Never edit the
  other sections. Replace the H1 in place (Step 4); never add a second one. The section lifetimes are defined in
  `CLAUDE.md` → 「`CLAUDE.md` 섹션의 수명」: `## Project Setup` holds what lasts as
  long as the project, `## Current Project` is replaced per work unit by
  `/feature`, so **do not put project-permanent state in the latter**.
- `.agents/rules/AGENTS.md` is Antigravity CLI's context: add a project
  paragraph, keep its read-only rules intact, never create a root `AGENTS.md`.
- Ask before installing anything or changing what gets committed.
- Tell the user up front that this skill writes several files under `.claude/`
  and that Claude Code asks for approval on each of them. In a non-interactive
  run those writes were refused even with `--permission-mode acceptEdits`, while
  `CLAUDE.md` and `.gitignore` went through — so a headless run stops short.
- **This skill needs a person.** Steps 2 and 3 ask questions. A headless run
  (`claude -p`) stopped at Step 2 after doing Steps 1–3 and still exited as
  `success`; an interactive run completed all eight steps (2026-09-28). Headless
  runs are not supported. If nobody can answer, stop and say so; do not guess
  the answers.

## Step 1 — Detect the stack

Look for: `pyproject.toml` / `uv.lock` / `requirements*.txt` / `setup.py`,
`package.json` (+ scripts), `Cargo.toml`, `go.mod`, `Makefile`, `Dockerfile*`,
`docker-compose*.yml`, CI configs, existing lint/format configs
(`ruff.toml`, `.flake8`, `setup.cfg`, `.eslintrc*`, `.pre-commit-config.yaml`),
test layout, and the commit-message convention from `git log --oneline -20`.
Record: languages, package manager, formatter/linter/type-checker **with pinned
versions**, test runner and how it is invoked (locally or inside a container),
default branch, commit convention.

For a formatter, record whether the project **has adopted it**, not only whether
it is installed: a config for it exists, and running its check mode over the
tracked files passes for (nearly) all of them. Write down the measured count
(e.g. "black --check: 414 of 555 files would be reformatted, no config" — not
adopted). Step 5 uses this.

## Step 2 — Ask the user (AskUserQuestion: questions 1–4 in one call, 5 in a second — it takes at most four)

1. **Project overview** — what does it do, in 1–2 sentences (used for
   `AGENTS.md` and `DESIGN.md`), and **what "done" looks like**: the few
   capabilities that, once working, mean the goal is met. Record them in
   Step 4 as `완료 지점`; `/feature` checks every unit of work against them.
   Without it work keeps going after the goal is met — a real project built
   200+ commits of extras after its two core features were done.
2. **Repository policy** — commit `.claude/ .agents/ CLAUDE.md` to the repo, or
   keep them local-only? If local-only, append them to `.git/info/exclude`.
   If committed, make sure `.gitignore` covers `.claude/logs/`,
   `.claude/checkpoints/`, `.claude/settings.local.json`, and — for
   `/isolated-review` — `.claude/docs/reviews/` and `.claude/isolated-review/`.
   Its reports and transcripts quote the code under review; a committed report
   also lets a later reviewer read the earlier verdict.
3. **Verification** — what command tells this project it is healthy, and how
   long does it take? Collect enough to write Step 5's scripts: the fast
   per-file check, the gate, anything slower, and where each runs (locally, in a
   container, on a device, only in CI). Ask which tools must be installed first.
   A tier the user cannot name honestly gets no script.
4. **Code language** for identifiers/comments (English default) and any extra
   conventions.
5. **Git and GitHub operations** — may the orchestrator push, merge PRs, tag
   releases and delete merged branches on its own, or ask each time?
   - **Delegated**: fewer interruptions; the user reviews PRs after the fact.
   - **Ask** (the template default): every push, merge and tag waits for a yes.
   Either way force-push, history rewrites, tag deletion and anything that
   touches production stay with the user. Apply the answer in Step 2b.

### Step 2b — Apply the git-operations choice

**Delegated** — the permission and the behaviour are recorded separately,
because they live in different files with different lifetimes:

- `.claude/settings.local.json` (never committed; created if missing) — add to
  `permissions.allow`: `Bash(git push origin *)` and, if `gh` is installed and
  logged in (`gh auth status`), `Bash(gh pr *)`. Merge into the existing
  list; do not replace it. Leave `.claude/settings.json` alone: it ships to
  every copy, and its `deny` rules (`git push --force`, `git push -f`) still
  win over this allow — deny is evaluated first.
- `CLAUDE.md` `## Project Setup` — add `Git operations: delegated — Claude
  pushes, merges PRs (merge commit), tags releases and deletes merged branches;
  it asks before force-push, history rewrites, tag deletion and anything that
  touches production.` Without this line the next session only has the
  permission, not the instruction to use it.

**Ask** — change no settings (the template's `ask` rules already cover `git
push`) and add `Git operations: ask — Claude asks before every push, merge and
tag.` to `## Project Setup`.

If `gh` is missing, say that merges and PRs will be manual whichever was
chosen, and record the delegated line without "merges PRs".

## Step 3 — Confirm the model matrix

Each agent's model is pinned in its definition file, not inherited. Show the
user the **current** assignment — read it from the files, never from this table —
and ask whether to keep it or change it.

| Role | Defined in | Default | Why |
|---|---|---|---|
| Main orchestrator | the user's session (`/model`) | Opus | Orchestration, user dialogue, final decisions |
| `deep-reasoning` | `.claude/agents/deep-reasoning.md` → `model:` | `fable` | Deep reasoning on a cheaper tier than the main session; pinned so an Opus main session does not silently make it Opus |
| `general-purpose` | `.claude/agents/general-purpose.md` → `model:` | `sonnet` | Thin wrapper around agy and file work — the tokens should go to agy, not to this agent |
| agy research | `--model` per call | see the Model Policy in `.claude/rules/antigravity-delegation.md` | Gemini tiers T1–T4, pinned per call |
| `/isolated-review` reviewer | `.claude/skills/isolated-review/run-review` → `MODEL` | `fable` | **Not reassignable.** Its neutrality was measured on Fable. Tell the user: without Fable access this skill always ends FAILED, and Phase 6 uses a person-opened (A2) review instead |

Procedure:

1. `grep -n '^model:' .claude/agents/*.md` and report the real values, plus
   `grep -n '^MODEL = ' .claude/skills/isolated-review/run-review` (reported,
   not offered for change).
2. Ask the user (one AskUserQuestion): keep this matrix, or reassign? Offer the
   trade-off — a cheaper `deep-reasoning` saves tokens but weakens design review;
   raising `general-purpose` above `sonnet` mostly burns tokens on wrapping agy.
3. Apply any change to the `model:` frontmatter of the agent files. Valid values
   are the tier aliases (`opus`, `fable`, `sonnet`, `haiku`) or `inherit`.
4. **If the user picks `inherit` for `deep-reasoning`, say what it means**: that
   subagent then runs on whatever the main session runs on, which defeats the
   cost split. Record the choice either way.
5. Whenever a value changes, update the comment in the agent file and any prose
   that names a model (`CLAUDE.md`, `README.md`,
   `.claude/rules/deep-reasoning-delegation.md`,
   `.claude/skills/deep-reasoning/SKILL.md`) so no document claims a model that
   is not pinned. This drift is what the step exists to prevent.

### Step 3b — agy: installed? logged in?

The template assumes agy is installed and authenticated. That assumption is worth
checking **here**, while a person is present and can act on it — during a work
session nobody can be asked to log in.

```sh
.claude/skills/antigravity-system/agy-probe
```

Branch on the first word it prints:

| State | What to do |
|---|---|
| `READY` | Report agy's model policy (the `agy research` row above) and move on. Nothing to install. |
| `MISSING` | **Ask the user to install Antigravity CLI**, then to run `agy` once and log in. Offer to wait: re-run the probe when they say they are done. Do not install it yourself — Step 2's ground rule is to ask before installing anything. |
| `UNAUTHENTICATED` | agy is already there, so this is the short path: **ask the user to run `agy` and log in**, then re-run the probe. Say explicitly that no installation is needed. |
| `DEGRADED` | Installed and authenticated but the probe came back empty. Show the probe's detail line (soft-deny, quota, or network) and ask whether to wait and retry or proceed without agy. |

If the user declines, or the state does not become `READY`:

1. Say plainly which capabilities are reduced — cite the fallback table in
   `.claude/rules/antigravity-delegation.md`, and that video and audio analysis
   become impossible rather than degraded.
2. Record the state and the date in `.claude/docs/DESIGN.md` under Open
   Questions, so a later session does not rediscover it.
3. Continue setup. A missing agy is not a reason to abandon `/initproject` —
   every other step still applies.

**Do not loop.** Ask once, re-probe once after the user says they are done, then
take the answer as final and move on.

## Step 4 — CLAUDE.md

Replace the H1 (`# Claude Code Orchestrator`) with `# <project name>`, in place.
This file is now the project's only always-loaded context and should not open by
naming the template. Replace the bold tagline under it
(`**멀티 에이전트 협업 프레임워크**`) with the one-sentence overview from Step 2.
Keep exactly one H1; the template's own sections below them stay as they are.

In `## Project Setup`, record which template release this project adopted:
`Orchestrator: v<contents of .claude/ORCHESTRATOR_VERSION>, adopted <today>`. If
that file is missing the copy predates versioning — write `unknown (pre-0.1.0
copy)`. A later upgrade starts from this line (`/orchestrator-version`).

Replace the body of `## 기술 스택(Tech Stack)` with the detected stack: language
and framework versions, package manager, quality tools with versions, how the
project runs (container vs local), a `공통 명령어` block with the **real**
commands, the commit convention and default branch, then
`→ 참고: .claude/rules/dev-environment.md`. Add/refresh `## Project Setup`
with the overview, the `완료 지점` list and the conventions from Step 2 — that section outlives every
single work unit, and `/feature` replaces `## Current Project`, not this one.
Leave `## Current Project` for `/feature` to write.

## Step 5 — Write the verification scripts (the project contract)

This is where stack detection ends up. Everything the orchestrator will ever know
about this project's toolchain is captured here, in these executables, and nothing
downstream needs to know the stack again.

Read `.claude/scripts/README.md` first — it is the contract. Then read
`references/known-pitfalls.md`: it holds **measured** findings (not general
knowledge) and may change a tool choice. If it says nothing about this stack, use
your own knowledge; if you are unsure and agy is available, one T3 query.

### The procedure is stack-agnostic

Do NOT look for a matching recipe — there is none, on purpose. Work the four
tiers in order and answer the same four questions for each:

1. **What command tells us this tier is healthy?** It must be able to FAIL.
   Never put an auto-fixing command in a gate.
2. **Where does it run?** Locally, inside a container, on a target device, in a
   cross-build environment. Whatever wrapper that needs goes INSIDE the script.
3. **How long does it take?** That decides the tier, not the command's name.
   A command that takes minutes cannot be the `save` tier.
4. **How does it go red?** If you cannot say, you do not yet know what this tier
   verifies.

| Script | Budget | Argument | Ask the user |
|---|---|---|---|
| `verify-save` | seconds | one host file path | Which file types are worth checking on save, and with what? |
| `verify-task` | ≤5 min | none | What is the fast gate after each task? |
| `verify-unit` | 5–60 min | none | What runs once per unit of work? |
| `verify-full` | unbounded | none | What only CI or a person should ever run? |

**A tier with no honest answer gets no script.** An absent script means "not
configured", which callers report plainly. A script that always exits 0 is worse
than no script: it reports success that was never checked.

### Rules for what you write

- `#!/bin/sh` unless the project prefers otherwise. Executable (`chmod +x`).
- Exit 0 = pass (print nothing), non-zero = fail (print why).
- `verify-save` exits 0 silently for a path it does not handle, for a missing
  file, and for no argument at all. Decide handled types with a `case` on the
  path inside the script — do not add a config file.
- Path translation is the script's job. `verify-save` receives a **host** path;
  if the tool runs elsewhere, convert it there.
- Gates do not modify files: no formatter, no `--fix`. A gate that silently
  rewrites what the model just wrote exits 0 with no output, and the model cannot
  tell that from "nothing to say" (this template's own `verify-save` did exactly
  that). Auto-fixing is a command a person runs on purpose. If a tier must fix
  anyway, it prints what it changed.
- **A format check goes into a gate only if the project has adopted that
  formatter** (Step 1's measurement). A format check judges appearance only —
  skipping it changes no behaviour. On a codebase that does not follow it, it
  reports every save of an untouched file as a failure. That noise trains people
  and the model to ignore the hook. Reformatting other people's code to silence
  it pollutes diffs, breaks intentional layout and causes merge conflicts. If
  the formatter is not adopted, leave the format check out and tell the user the
  measured count. Adopting a formatter is the team's decision, made as one
  separate whole-repository formatting commit, never piecemeal while working.
  Static checks that find real defects (undefined names, type errors) stay.
- No destructive actions: nothing commits, pushes, deploys, or creates resources.
- `verify-full` may chain `verify-unit`; `verify-save` must never chain a slower
  tier, or saving a file starts a build.
- If a tool may be absent, the script decides whether that is a failure and says
  so — do not let the caller guess.
- Code shared by several scripts (container entry, toolchain sourcing) goes in a
  helper whose name starts with `_` (e.g. `.claude/scripts/_lib.sh`) or under
  `lib/` — see `.claude/scripts/README.md`. A name without `_` reads as an
  entrypoint.

### Verify what you wrote

Run each script by hand and check the contract, not the output:

```bash
.claude/scripts/verify-save <a file the project checks>   # expect non-zero on bad input
.claude/scripts/verify-save README.md; echo $?            # expect 0 and NO output
.claude/scripts/verify-save; echo $?                      # expect 0
.claude/scripts/verify-task; echo $?                      # expect 0 on a clean tree
```

Then prove the gate can fail — introduce one violation, confirm `verify-task`
goes non-zero, and revert it. **A gate that has never failed is not known to be
a gate.** Record in the final report which tiers exist and which were skipped.

If the project keeps its own test suite for this, `tests/test_verify_scripts.py`
in this template checks the contract without assuming any language; copy it.

## Step 6 — Adapt the remaining prose (skip what already fits)

| File | What to do |
|---|---|
| `.claude/rules/dev-environment.md` | Rewrite for the real toolchain: layout table, package manager, how to run, formatter/linter/type-checker table with versions and exact invocations, test commands, pre-commit checklist in the project's commit convention. Add a security-posture section if the domain is sensitive. |
| `.claude/hooks/lint-on-save.py` | **Usually nothing.** It names no tool — it runs `.claude/scripts/verify-save` (Step 5) and reports what that returns. Edit it only to change hook behaviour itself, not the toolchain. Remove its registration from `settings.json` if the user chose no save-tier check. |
| `.claude/rules/language.md` | Its defaults (English identifiers and comments, Korean for the user) stay. If the codebase already follows a different convention (e.g. Korean comments, a commit-message language), add a short `Project override` paragraph that names what the code already does and where — do not rewrite the defaults. |
| `.claude/rules/testing.md` | Stack-agnostic; usually leave it. Add a short note only if the project has its own test conventions (fixture location, naming). Tier commands live in `.claude/scripts/`, not here. |
| `.claude/settings.json` | Ships with template tooling only in `allow` (`git`, `uv`, `python3`, `agy`, `.claude/scripts/*`, read-only helpers) and an `ask` list for consequential commands (`git push`, `docker`, `rm -rf`, `kill`, `sed -i`, …). Add allow rules **only** for tools the detected stack runs directly outside `.claude/scripts/*`, and narrowly (`Bash(npm run test:*)`, not `Bash(npm:*)` or `Bash(npx:*)`, which approve anything they wrap). Remove `Bash(uv:*)` if the stack does not use uv. **Never move an `ask` entry to `allow`** and never add `docker`, `curl` or `kill` to allow; if the machine runs live containers or services, say so in the report. Read-only forms (`docker ps`, `git status`) never prompt anyway. |
| Rules that do not apply | Suggest removal (e.g. `testing.md` for a repo without tests) — do not delete without confirmation. |

Verify with `python3 -m py_compile .claude/hooks/*.py` and by piping a sample
payload (`{"tool_name":"Edit","tool_input":{"file_path":"<a scratch file>"}}`)
into the lint hook.

Then prove nothing still names the template's default toolchain:

```bash
grep -rn 'uv run\|ruff\|\bty\b\|pytest\|conftest\|def test_\|unittest' .claude/rules .claude/skills CLAUDE.md \
  | grep -v initproject/
```

Every remaining hit must be either this project's real toolchain or an
explicitly-labelled template default. A hit the user's stack does not use is
the bug this step exists to prevent.

## Step 7 — Seed agy context and design doc

1. `.agents/rules/AGENTS.md`: insert `## This Project: <name>` right after the
   title — domain, main directories/apps, companion systems, and any "never
   print secrets/keys" instruction. Keep the rest of the file unchanged.
2. `.claude/docs/DESIGN.md`: fill Overview, an Architecture block (directories →
   components → data flow), the Libraries table with versions, any decision
   made in this session (e.g. lint settings) with today's date, and open
   questions you could not resolve (test invocation, CI, etc.) as TODO items.
   The file ships as an empty skeleton; keep its headings. Any entry already
   there that describes this template (it names `/initproject`, `/feature`,
   `/lens-review`, `checkpoint.py` or the hooks) is a leftover from a copy made
   before 2026-09-28: tell the user and delete it before filling — it would
   otherwise be read as this project's design.

## Step 8 — Smoke test and report

- Skills list shows `/deep-reasoning`, `/antigravity-system`, `/feature`.
- `grep -n '^model:' .claude/agents/*.md` matches the matrix agreed in Step 3,
  and no prose names a model that is not pinned.
- Each verification script written in Step 5 runs by hand and honours the
  contract (0 = pass and silent, non-zero = fail with a reason); the gate has
  been seen to fail once on an injected violation.
- `.claude/skills/antigravity-system/agy-probe` prints the state agreed in
  Step 3b. `READY` exits 0; any other state must already be recorded in
  `DESIGN.md` Open Questions with today's date.
- Report in Korean: detected stack, the final model matrix, agy's state and
  what it costs if not `READY`, which verification
  tiers exist and which were skipped and why, what was changed per file, what was
  skipped and why, what the user still has to decide (also written to
  `DESIGN.md` TODO), and the command a person runs to auto-fix (kept out of the
  gates).
