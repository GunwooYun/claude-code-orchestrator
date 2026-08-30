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
- Do **NOT** modify the orchestration sections (agent table, context management, quick reference, workflow, language protocol)

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

Use Edit tool to replace the `## 기술 스택(Tech Stack)` section and to add/refresh a `## Current Project` block at the end, using this format:

```markdown
# Project Overview

{User's answer}

## Language Settings

- **Thinking/Reasoning**: English
- **Code**: {Based on analysis - English or Korean}
- **User Communication**: Korean

## Tech Stack

- **Language**: {Detected language}
- **Package Manager**: {Detected tools}
- **Dev Tools**: {Detected tools}
- **Main Libraries**: {Detected libraries}
```

### 4. Update Common Commands

Inside the Tech Stack section, replace the `공통 명령어` block with the detected commands:

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
