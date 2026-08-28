# Deep-Reasoning Delegation Rule

**The `deep-reasoning` subagent is your highly capable supporter (Claude Fable, isolated context).**

## Context Management (CRITICAL)

**컨텍스트 소비를 의식해서 deep-reasoning 서브에이전트를 사용하세요.**
분석에 필요한 파일 읽기·코드 추적은 전부 서브에이전트의 독립 컨텍스트에서 소비되고,
메인에는 **간결한 결론만** 돌아옵니다.

| 상황 | 권장 방법 |
|------|-----------|
| 짧은 질문 · 짧은 답변 | 메인이 직접 답변 |
| 상세한 설계 상담 | deep-reasoning 서브에이전트 |
| 디버깅 분석 | deep-reasoning 서브에이전트 |
| 여러 개의 질문이 있는 경우 | deep-reasoning 서브에이전트 |

```
┌──────────────────────────────────────────────────────────┐
│  Main Claude Code (Orchestrator)                         │
│  → 사소한 질문이면 직접 답변하면 됨                          │
│  → 깊은 분석이 필요하면 deep-reasoning 서브에이전트 호출        │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Subagent (deep-reasoning)                          │ │
│  │  → Isolated context (reads code/diffs itself)       │ │
│  │  → Read-only: analyzes and recommends, never edits  │ │
│  │  → Returns concise recommendation only              │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

## About deep-reasoning

The `deep-reasoning` subagent is a senior architect/debugger persona defined in
`.claude/agents/deep-reasoning.md`. It inherits the session model (Claude Fable),
so deep analysis quality is preserved while the main context stays lightweight.
Think of it as a trusted senior expert you can always consult.

**When facing difficult decisions → Consult the deep-reasoning subagent.**

## When to Consult

ALWAYS consult deep-reasoning BEFORE:

1. **Design decisions** - How to structure code, which pattern to use
2. **Debugging** - If cause isn't obvious or first fix failed
3. **Implementation planning** - Multi-step tasks, multiple approaches
4. **Trade-off evaluation** - Choosing between options

### Trigger Phrases (User Input)

Consult deep-reasoning when user says:

| Korean | English |
|----------|---------|
| "어떻게 설계해야 할까?", "어떻게 구현하지?" | "How should I design/implement?" |
| "왜 안 돌아가지?", "원인은?", "에러가 나요" | "Why doesn't this work?" "Error" |
| "어느 쪽이 좋아?", "비교해 줘", "트레이드오프는?" | "Which is better?" "Compare" |
| "~를 만들고 싶다", "~를 구현해 줘" | "Build X" "Implement X" |
| "생각해 줘", "분석해 줘", "깊게 생각해" | "Think" "Analyze" "Think deeper" |

## When NOT to Consult

Skip deep-reasoning for simple, straightforward tasks:

- Simple file edits (typo fixes, small changes)
- Following explicit user instructions
- Standard operations (git commit, running tests)
- Tasks with clear, single solutions
- Reading/searching files

## Quick Check

Ask yourself: "Am I about to make a non-trivial decision?"

- YES → Consult deep-reasoning first
- NO → Proceed with execution

## How to Consult

Use Task tool with `subagent_type: "deep-reasoning"` (called from the MAIN
orchestrator — subagents cannot spawn other subagents):

```
Task tool parameters:
- subagent_type: "deep-reasoning"
- run_in_background: true (optional, for parallel work)
- prompt: |
    {Design question / bug / trade-off}

    Relevant files: {paths}

    Return CONCISE summary:
    - Key recommendation
    - Main rationale (2-3 points)
    - Any concerns or risks
```

### Trivial Questions

No subagent needed — the main orchestrator answers directly.
Subagent overhead is only justified when analysis requires reading
multiple files or long reasoning chains.

**Language protocol:**
1. Prompt the subagent in **English**
2. Subagent returns analysis in **English**
3. Main reports to user in **Korean**

## Why Subagent Pattern?

- **Context preservation**: Main orchestrator stays lightweight
- **Full analysis**: Subagent reads code/diffs in its own context
- **Concise handoff**: Main only receives actionable summary
- **Parallel work**: Background subagents enable concurrent tasks

**Don't hesitate to delegate. deep-reasoning subagent = efficient collaboration.**
