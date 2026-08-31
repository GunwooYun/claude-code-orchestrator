---
name: init
description: First-session setup after copying the orchestrator template into a project. Detects the stack, adapts CLAUDE.md / rules / lint hook / permissions when the stack differs from the template default (Python + uv/ruff/ty/pytest), and seeds the agy context (.agents/rules/AGENTS.md) and DESIGN.md. Run once per project.
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
3. **Lint hook** (only if the stack is not uv/ruff) — install the project's own
   formatter/linter locally at the pinned versions (e.g.
   `pipx install black==<ver>`), disable `lint-on-save.py` in `settings.json`,
   or keep it as report-only.
4. **Code language** for identifiers/comments (English default) and any extra
   conventions.

## Step 3 — CLAUDE.md

Replace the body of `## 기술 스택(Tech Stack)` with the detected stack: language
and framework versions, package manager, quality tools with versions, how the
project runs (container vs local), a `공통 명령어` block with the **real**
commands, the commit convention and default branch, then
`→ 참고: .claude/rules/dev-environment.md`. Add/refresh `## Current Project`
with the overview and conventions from Step 2.

## Step 4 — Adapt rules and hooks (skip entirely if the stack is Python + uv/ruff/ty/pytest)

| File | What to do |
|---|---|
| `.claude/rules/dev-environment.md` | Rewrite for the real toolchain: layout table, package manager, how to run, formatter/linter/type-checker table with versions and exact invocations, test commands, pre-commit checklist in the project's commit convention. Add a security-posture section if the domain is sensitive. |
| `.claude/hooks/lint-on-save.py` | Replace the `uv run ruff` / `ty` calls with the project's tools (format → import sort → check-only linter; frontend linter only when `node_modules` exists). Read the file path from **stdin JSON** (`tool_input.file_path`). Resolve tools via `shutil.which` with a `~/.local/bin` fallback. Skip generated dirs (`migrations/`, `node_modules/`). Never block. Or remove its registration from `settings.json` if the user chose to disable it. |
| `.claude/rules/testing.md` | Replace `uv run pytest` with the real test command (e.g. `docker compose … exec backend pytest`, `npm test`). |
| `.claude/settings.json` | Add `Bash(<tool>:*)` allow entries for the project's tools (`isort`, `flake8`, `docker compose`, `cargo`, `go`, …). |
| Rules that do not apply | Suggest removal (e.g. `testing.md` for a repo without tests) — do not delete without confirmation. |

Verify with `python3 -m py_compile .claude/hooks/*.py` and by piping a sample
payload (`{"tool_name":"Edit","tool_input":{"file_path":"<a scratch file>"}}`)
into the lint hook.

## Step 5 — Seed agy context and design doc

1. `.agents/rules/AGENTS.md`: insert `## This Project: <name>` right after the
   title — domain, main directories/apps, companion systems, and any "never
   print secrets/keys" instruction. Keep the rest of the file unchanged.
2. `.claude/docs/DESIGN.md`: fill Overview, an Architecture block (directories →
   components → data flow), the Libraries table with versions, any decision
   made in this session (e.g. lint settings) with today's date, and open
   questions you could not resolve (test invocation, CI, etc.) as TODO items.

## Step 6 — Smoke test and report

- Skills list shows `/deep-reasoning`, `/antigravity-system`, `/startproject`.
- `agy -p "Reply with exactly: OK" --model gemini-3.7-flash-low` returns OK
  (if agy is installed; otherwise note it).
- Report in Korean: detected stack, what was changed per file, what was
  skipped and why, what the user still has to decide (also written to
  `DESIGN.md` TODO), and a reminder to check `git diff` after the first edit
  if a formatter was enabled.
