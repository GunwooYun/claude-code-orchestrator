---
name: context-loader
description: Load project context from .claude/ directory at the start of every task. This ensures Antigravity CLI (agy) has the same coding rules, design decisions, and library constraints as Claude Code.
---

# Context Loader Skill for Antigravity (agy)

## Purpose

Load shared project context from `.claude/` directory to ensure Antigravity CLI (agy) operates with the same knowledge as Claude Code.

## When to Activate

At the beginning of research or analysis tasks that touch this project's code
or design. Note: in headless (`agy -p`) calls, file reads only succeed when the
caller passed the permission flags; if reads are denied, skip this skill and
answer from the prompt alone. Prefer `DESIGN.md` and `docs/libraries/` over
loading every rule file.

## Workflow

### Step 1: Load Coding Rules

Read relevant files from `.claude/rules/`:

```
.claude/rules/
├── coding-principles.md   # Simplicity, single responsibility, early return
├── dev-environment.md     # uv, ruff, ty, pytest requirements
├── language.md            # Think in English, respond in Korean
├── security.md            # Secrets, validation, SQLi/XSS prevention
└── testing.md             # TDD, AAA pattern, 80% coverage
```

### Step 2: Load Design Documentation

Read `.claude/docs/DESIGN.md` for:
- Architecture decisions
- Implementation patterns
- Library choices and constraints

### Step 3: Check Library Documentation

If the task involves specific libraries, read relevant files from:
```
.claude/docs/libraries/
```

### Step 4: Execute Research Task

With the loaded context, execute the requested research/analysis following:
- Project coding principles
- Existing design decisions
- Library constraints

## Key Rules to Remember

1. **Simplicity first** - Recommend readable solutions over complex
2. **Type hints required** - Suggest typed code
3. **Use uv** - Reference uv for package management
4. **Security** - Highlight security considerations

## Language Protocol

- **Thinking/Reasoning**: English
- **Code examples**: English (variables, functions, comments)
- **Output**: Structured markdown, suitable for documentation

## Output Guidelines

When providing research results:
- Structure with clear headings
- Include code examples when relevant
- Cite sources from web search
- Note constraints relevant to this project
- Return everything in the response — do not create or modify files
  (Claude Code persists findings to `.claude/docs/research/`)
