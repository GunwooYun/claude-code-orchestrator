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
| **입력이 큼** (파일 5개 · 500줄 이상) | **agy 프리필터 → deep-reasoning** (아래 참조) |

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
`.claude/agents/deep-reasoning.md`, which pins `model: fable`. The model is
pinned rather than inherited, so deep analysis always runs on Claude Fable no
matter which model the main session uses, and the main context stays lightweight.
Think of it as a trusted senior expert you can always consult.

**When facing difficult decisions → Consult the deep-reasoning subagent.**

## 큰 입력에는 앞단에 프리필터를 둔다

라우팅 기준은 주제가 아니라 **토큰량 × 추론 난이도**다. 전체 표는
`.claude/rules/antigravity-delegation.md` 와 `CLAUDE.md` 에 있고, 이 절은 그중
"토큰 많음 × 추론 어려움" 칸을 deep-reasoning 쪽에서 본 것이다.

deep-reasoning 은 자기 컨텍스트에서 파일을 직접 읽는다. 그것이 메인 컨텍스트를
지키는 방식이지만, **입력이 크면 가장 비싼 모델이 가장 토큰 많이 쓰는 일(넓게
읽기)을 하게 된다.**

```
작은 입력  ──────────────────────> deep-reasoning (직접 읽는다)

큰 입력   ──> agy: file:line 나열 ──> deep-reasoning (그 지점만 판정)
```

**기준**: 입력이 **파일 5개 또는 500줄 이상**이면 프리필터를 검토한다 — 이 숫자는
`CLAUDE.md` 「큰 변경의 기준」에서 정의되고, 여기서는 인용한다. 그 아래에서는
왕복 비용이 절약분보다 크므로 그냥 직접 준다.

프리필터를 둘 때:

- **agy 는 위치와 사실만 반환한다 — 판정은 아니다.** agy 가 요약해 버리면
  deep-reasoning 은 코드가 아니라 요약을 추론한다.
- **"걸러진 입력을 받았다"고 프롬프트에 명시한다.** 그리고 부족하면 직접 읽으라고
  말한다. 전수라고 착각하면 없는 것을 없다고 결론낸다.
- **agy 를 쓸 수 없으면 프리필터를 생략한다.** 기존 동작이므로 결과는 같고 토큰만
  늘어난다.

상세: `.claude/rules/antigravity-delegation.md` 의 "라우팅은 주제가 아니라 비용으로
한다" → B. 2단계 퍼널.

**판정은 절대 넘기지 않는다.** 설계가 맞는지, 이 코드가 안전한지, A 와 B 중
무엇인지는 deep-reasoning 의 일이다. agy 는 읽는 범위를 좁히는 데만 쓴다.

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
