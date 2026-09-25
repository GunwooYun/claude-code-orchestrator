---
name: initproject
description: First-session setup after copying the orchestrator template into a project. Detects the stack, confirms the per-agent model matrix with the user, checks whether agy is installed and logged in (asking for installation or login while a person is present), writes the four verification scripts in .claude/scripts/ that form this project's contract with the orchestrator, adapts CLAUDE.md / rules / permissions where the template's own toolchain shows through, and seeds the agy context (.agents/rules/AGENTS.md) and DESIGN.md. Run once per project.
disable-model-invocation: true
---

# Initialize Project Configuration (first session)

You have just been copied into a new project together with `.claude/`, `.agents/`
and `CLAUDE.md`. Make the template fit **this** project. Work through the steps
in order; skip a step when it does not apply and say so in the final report.

## Ground rules

- `CLAUDE.md`: touch only `## 기술 스택(Tech Stack)` and `## Current Project`
  (create it if missing, place it after `## 언어 프로토콜` and **before** any
  `## Session History`). Never edit the other sections, never add a second H1.
- `.agents/rules/AGENTS.md` is Antigravity CLI's context: add a project
  paragraph, keep its read-only rules intact, never create a root `AGENTS.md`.
- Ask before installing anything or changing what gets committed.

## Step 1 — Detect the stack

Look for: `pyproject.toml` / `uv.lock` / `requirements*.txt` / `setup.py`,
`package.json` (+ scripts), `Cargo.toml`, `go.mod`, `Makefile`, `Dockerfile*`,
`docker-compose*.yml`, CI configs, existing lint/format configs
(`ruff.toml`, `.flake8`, `setup.cfg`, `.eslintrc*`, `.pre-commit-config.yaml`),
test layout, and the commit-message convention from `git log --oneline -20`.
Record: languages, package manager, formatter/linter/type-checker **with pinned
versions**, test runner and how it is invoked (locally or inside a container),
default branch, commit convention.

## Step 2 — Ask the user (one AskUserQuestion, several questions)

1. **Project overview** — what does it do, in 1–2 sentences (used for
   `AGENTS.md` and `DESIGN.md`).
2. **Repository policy** — commit `.claude/ .agents/ CLAUDE.md` to the repo, or
   keep them local-only? If local-only, append them to `.git/info/exclude`.
   If committed, make sure `.gitignore` covers `.claude/logs/`,
   `.claude/checkpoints/`, `.claude/settings.local.json`.
3. **Verification** — what command tells this project it is healthy, and how
   long does it take? Collect enough to write Step 5's scripts: the fast
   per-file check, the gate, anything slower, and where each runs (locally, in a
   container, on a device, only in CI). Ask which tools must be installed first.
   A tier the user cannot name honestly gets no script.
4. **Code language** for identifiers/comments (English default) and any extra
   conventions.

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

Procedure:

1. `grep -n '^model:' .claude/agents/*.md` and report the real values.
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

Replace the body of `## 기술 스택(Tech Stack)` with the detected stack: language
and framework versions, package manager, quality tools with versions, how the
project runs (container vs local), a `공통 명령어` block with the **real**
commands, the commit convention and default branch, then
`→ 참고: .claude/rules/dev-environment.md`. Add/refresh `## Current Project`
with the overview and conventions from Step 2.

## Step 5 — Write the verification scripts (the project contract)

This is where stack detection ends up. Everything the orchestrator will ever know
about this project's toolchain is captured here, in four executables, and nothing
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
| `verify-unit` | 10–60 min | none | What runs once per unit of work? |
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
- No destructive actions: a formatter may rewrite the file, but nothing commits,
  pushes, deploys, or creates resources.
- `verify-full` may chain `verify-unit`; `verify-save` must never chain a slower
  tier, or saving a file starts a build.
- If a tool may be absent, the script decides whether that is a failure and says
  so — do not let the caller guess.

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
| `.claude/rules/testing.md` | Principles are stack-agnostic; leave them. Only the short `## 명령` section names this template's own tools — point it at the project's. Tier commands live in `.claude/scripts/`, not here. |
| `.claude/skills/tdd/SKILL.md`, `.claude/skills/simplify/SKILL.md` | These carry `uv run pytest` in code blocks and were previously missed by this step, so they kept telling the model to run pytest after setup. Leave the placeholders (`{TEST_ONE}`, `{TEST_ALL}`, …) and make sure `CLAUDE.md` → `공통 명령어` holds the real commands; only edit the skills if a placeholder is still wrong for this stack. For a stack with no unit tests (e.g. Yocto recipes), say so in `tdd/SKILL.md` and name what replaces Red-Green-Refactor. |
| `.claude/settings.json` | `Bash(.claude/scripts/*)` is already allowed. Add `Bash(<tool>:*)` only for tools the model runs directly outside the scripts. |
| Rules that do not apply | Suggest removal (e.g. `testing.md` for a repo without tests) — do not delete without confirmation. |

Verify with `python3 -m py_compile .claude/hooks/*.py` and by piping a sample
payload (`{"tool_name":"Edit","tool_input":{"file_path":"<a scratch file>"}}`)
into the lint hook.

Then prove nothing still names the template's default toolchain:

```bash
grep -rn 'uv run\|ruff\|\bty\b\|pytest' .claude/rules .claude/skills CLAUDE.md \
  | grep -v initproject/references
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
  `DESIGN.md` TODO), and a reminder to check `git diff` after the first edit
  if a formatter was enabled.
