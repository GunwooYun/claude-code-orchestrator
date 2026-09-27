---
name: plan
description: Create a detailed implementation plan for a feature or task. Use when user wants to plan before coding.
disable-model-invocation: true
---

# Create Implementation Plan

Create an implementation plan for $ARGUMENTS.

## Planning Process

### 1. Requirements Analysis

First clarify:

- **Purpose**: What to achieve
- **Scope**: What to include, what to exclude
- **Constraints**: Technical, time, dependencies

### 2. Current State Investigation

Investigate the codebase:

```
- Related existing code
- Files affected
- Libraries/patterns to use
- Existing tests
```

### 3. Break Down Implementation Steps

Break into small steps:

1. Each step is independently **verifiable by a command that can fail**
2. Consider dependency order
3. High-risk steps first — tag them `risk:high` so the `unit` tier runs after them

### 4. Output Format

```markdown
## Implementation Plan: {Title}

### Purpose
{1-2 sentences}

### Scope
- New files: {list}
- Modified files: {list}
- Dependencies: {list}

### Implementation Steps

#### Step 1: {Title}
- [ ] {Specific task}
- [ ] {Specific task}
**Verification**: `{tier}` — `{the project's real command}` — proves `{scenario ID}`
**Fails when**: {how this command goes red if the step is wrong}

#### Step 2: {Title}
...

### Risks & Considerations
- {Potential issues and mitigations}

### Verification

| Step | 티어 | 명령 | 시나리오 ID | 실패 조건 |
|------|------|------|-------------|-----------|
| 1 | task | {프로젝트의 실제 명령} | V1 | {어떻게 빨간불이 나는가} |

명령은 발명하지 않는다 — 티어 단위는 `.claude/scripts/verify-<tier>`, 더 좁은
범위는 `CLAUDE.md` 의 `공통 명령어`. 티어 정의와 원칙은
`.claude/rules/testing.md` 를 따른다. `/feature` Phase 2b 로 시작한
작업이면 그 검증 계획의 시나리오 ID 를 그대로 쓴다.

**"실패 조건"을 채우지 못하는 단계는 아직 계획되지 않은 단계다.**

### Open Questions
- {Items to clarify before implementation}
```

## Notes

- Plans should be at actionable granularity
- Include verification method for each step
- Ask questions at planning stage for unclear points
- Don't over-detail (adjust during implementation)
