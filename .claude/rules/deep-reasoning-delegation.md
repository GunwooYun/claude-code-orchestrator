# Deep-Reasoning Delegation Rule

The `deep-reasoning` subagent (`.claude/agents/deep-reasoning.md`, pinned to
`model: fable`) is the orchestrator's senior architect and debugger. It reads
code in its own isolated context, never edits, and returns a concise
recommendation — so the main context stays light.

## When to consult — BEFORE

1. **Design decisions** — how to structure code, which pattern to use
2. **Debugging** — the cause is not obvious, or the first fix failed
3. **Implementation planning** — multi-step work, several possible approaches
4. **Trade-offs** — choosing between options

User phrases that mean this: "어떻게 설계/구현하지?", "왜 안 돌아가지?", "에러가 나요",
"어느 쪽이 좋아?", "비교해 줘", "~를 만들고 싶다", "분석해 줘", "깊게 생각해".

## When NOT to

Typo fixes and small edits, explicit instructions, standard operations (commit,
running tests), tasks with one obvious solution, reading or searching files.
Trivial questions: the main orchestrator answers directly.

**Quick check:** "Am I about to make a non-trivial decision?" YES → consult first.

## Large inputs

Input of **5+ files or 500+ lines** (defined in `CLAUDE.md` 「큰 변경의 기준」): put an
agy pre-filter in front — agy returns `file:line` and facts, deep-reasoning
judges. Tell deep-reasoning the input was filtered and that it may read more.
Below that size, give it the files directly. If agy is unavailable, skip the
filter. Details: `.claude/rules/antigravity-delegation.md` → 2단계 퍼널.

**Judgement is never delegated to agy.** Whether a design is right, whether code
is safe, A vs B — that is deep-reasoning's job.

## How to consult

From the MAIN orchestrator (subagents cannot spawn subagents):

```
Task tool parameters:
- subagent_type: "deep-reasoning"
- run_in_background: true   # optional, for parallel work
- prompt: |
    {Design question / bug / trade-off}

    Relevant files: {paths}

    Return CONCISE summary:
    - Key recommendation
    - Main rationale (2-3 points)
    - Any concerns or risks
```

Prompt in **English**; the subagent answers in English; the main session reports
to the user in **Korean**.
