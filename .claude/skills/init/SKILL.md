---
name: init
description: Analyze project structure and update CLAUDE.md (Claude Code context) with the detected tech stack and commands. Do NOT touch .agents/rules/AGENTS.md (agy context).
disable-model-invocation: true
---

# Initialize Project Configuration

Analyze this project and update **only the project-specific sections** of `CLAUDE.md`
(the Claude Code context file). `.agents/rules/AGENTS.md` is Antigravity CLI's context
and is NOT the target of this skill; a root-level `AGENTS.md` must not be created.

## Important

- Only update the `## 기술 스택(Tech Stack)` section and the `## Current Project` block (create it if missing)
- Do **NOT** modify any other section: agent table, `## 컨텍스트 관리`, `## 빠른 사용 가이드`, `## Workflow`, `## 문서구조`, `## 운영 주의사항 (Operational Notes)`, `## 언어 프로토콜`, or an existing `## Session History`
- Insert `## Current Project` **before** `## Session History` if that section exists (`/checkpointing` rewrites the Session History section; content placed inside it is lost)
- Do not add a second H1 or a separate language section — CLAUDE.md already has `## 언어 프로토콜`

## Steps

### 1. Project Analysis

Find these files to identify the tech stack:

- `package.json` → Node.js/TypeScript project
- `pyproject.toml` / `setup.py` / `requirements.txt` → Python project
- `Cargo.toml` → Rust project
- `go.mod` → Go project
- `Makefile` / `Dockerfile` → Build/deploy config
- `.github/workflows/` → CI/CD config

Also detect:

- npm scripts / poe tasks / make targets → Common commands
- Major libraries/frameworks

### 2. Ask User

Use AskUserQuestion tool to ask:

1. **Project overview**: What does this project do? (1-2 sentences)
2. **Code language**: English or Korean for comments/variable names?
3. **Additional rules**: Any other coding conventions to follow?

### 3. Partial Update of CLAUDE.md

Use Edit tool to replace the body of `## 기술 스택(Tech Stack)` and to add/refresh a `## Current Project` block (placed after `## 언어 프로토콜` and before any `## Session History`), using this format:

```markdown
## 기술 스택(Tech Stack)

- **Language**: {Detected language}
- **Package Manager**: {Detected tools}
- **Dev Tools**: {Detected tools}
- **Main Libraries**: {Detected libraries}
- 공통 명령어
    ```
    {detected commands}
    ```

→ 참고: `.claude/rules/dev-environment.md`

## Current Project

### Overview
{User's answer, 1-2 sentences}

### Conventions
- Code language: {English or Korean, from the user's answer}
- {Additional rules from the user}
```

### 4. Update Common Commands

The `공통 명령어` block inside the Tech Stack section holds the detected commands:

```markdown
## Common Commands

```bash
# Detected commands (example)
{npm run dev / poe test / make build etc.}
```
```

### 5. Check Unnecessary Rules

Check rules in `.claude/rules/` and suggest removing unnecessary ones:

- Non-Python project → `dev-environment.md` (uv/ruff/ty) may not be needed; also adjust `hooks/lint-on-save.py`
- No-test project → `testing.md` may not be needed
- Also point out the mypy-vs-ty mismatch between `pyproject.toml` and the rules if the project keeps Python tooling

### 6. Report Completion

Report to user (in Korean):

- Detected tech stack
- Updated sections
- Recommended rules to remove (if any)
