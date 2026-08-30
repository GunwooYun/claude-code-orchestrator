---
name: deep-reasoning
description: |
  PROACTIVELY consult the deep-reasoning subagent (Claude Fable in an isolated
  context), your highly capable supporter with exceptional reasoning abilities.
  A trusted expert you should ALWAYS consult BEFORE making decisions on: design
  choices, implementation approaches, debugging strategies, refactoring plans,
  or any non-trivial problem. When uncertain, consult it. Don't hesitate.
  Explicit triggers: "think deeper", "analyze", "second opinion", "깊게 생각해",
  "분석해".
metadata:
  short-description: Claude Code ↔ deep-reasoning subagent collaboration
---

# Deep Reasoning — Design & Debugging Partner

**The `deep-reasoning` subagent (Claude Fable, isolated context) is your highly capable supporter for deep reasoning tasks.**

> **상세규칙**: `.claude/rules/deep-reasoning-delegation.md`

## Context Management (CRITICAL)

**서브에이전트로 실행된다**. 분석에 필요한 파일 읽기·긴 추론은 전부 서브에이전트의
독립 컨텍스트에서 소비되고, 메인에는 간결한 결론만 돌아온다.

| 상황 | 방법 |
|------|------|
| 자세한 설계 상담 | deep-reasoning 서브에이전트 |
| 디버그 분석 | deep-reasoning 서브에이전트 |
| 짧은 질문 (1-2 문 답변) | 메인이 직접 답변 |

## When to Consult (MUST)

| Situation | Trigger Examples |
|-----------|------------------|
| **Design decisions** | "어떻게 설계하지?" "아키텍처" / "How to design?" |
| **Debugging** | "왜 안 돌아가지?" "오류" / "Debug" "Error" |
| **Trade-off analysis** | "어느 쪽이 좋은가?" "비교해" / "Compare" "Which?" |
| **Complex implementation** | "구현 방법" "어떻게 만드는가?" / "How to implement?" |
| **Refactoring** | "리팩터링" "간단하게" / "Refactor" "Simplify" |
| **Code review** | "리뷰해 줘" "확인해 줘" / "Review" "Check" |

## When NOT to Consult

- Simple file edits, typo fixes
- Following explicit user instructions
- git commit, running tests, linting
- Tasks with obvious single solutions

## How to Consult

**Use Task tool with `subagent_type: "deep-reasoning"` from the MAIN
orchestrator** (subagents cannot spawn other subagents).

```
Task tool parameters:
- subagent_type: "deep-reasoning"
- run_in_background: true (optional, for parallel work)
- prompt: |
    {Design question / bug / trade-off}

    Relevant files: {paths — the subagent reads them itself}

    Return CONCISE summary (key recommendation + rationale + risks).
```

### Workflow

1. **Spawn subagent** with the consultation prompt
2. **Continue your work** → Subagent runs in parallel
3. **Receive summary** → Subagent returns concise insights

### Access Modes

| Mode | Use Case |
|------|----------|
| deep-reasoning subagent (read-only) | Analysis, review, debugging advice |
| Main Claude / general-purpose subagent | Implementation, refactoring, fixes |

## Language Protocol

1. Prompt the subagent in **English**
2. Receive analysis in **English**
3. Execute based on the recommendation (main or general-purpose applies changes)
4. Report to user in **Korean**

## Task Templates

### Design Review

```
Task(subagent_type="deep-reasoning", prompt="""
Review this design approach for: {feature}

Context:
{relevant code or architecture, or file paths to read}

Evaluate:
1. Is this approach sound?
2. Alternative approaches?
3. Potential issues?
4. Recommendations?
""")
```

### Debug Analysis

```
Task(subagent_type="deep-reasoning", prompt="""
Debug this issue:

Error: {error message}
Code: {relevant code or file paths}
Context: {what was happening}

Analyze root cause and suggest fixes.
""")
```

### Code Review

See: `references/code-review-task.md`

### Refactoring

See: `references/refactoring-task.md`

## Integration with Antigravity (agy)

| Task | Use |
|------|-----|
| Need research first | agy → then deep-reasoning |
| Design decision | deep-reasoning directly |
| Library comparison | agy research → deep-reasoning decision |

## Why deep-reasoning?

- **Deep reasoning**: Claude Fable-level analysis in an isolated context
- **Code expertise**: Implementation strategies and patterns
- **Zero extra setup**: No external CLI or account required
- **Parallel work**: Background execution keeps you productive
