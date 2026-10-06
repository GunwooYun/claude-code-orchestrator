---
name: antigravity-system
description: |
  PROACTIVELY consult Antigravity CLI (agy) for research, large codebase
  comprehension, and multimodal data processing. Powered by Gemini models:
  massive context windows, Google Search grounding, PDF/image/video analysis,
  and repository-wide understanding. Use for pre-implementation research,
  documentation analysis, and multimodal tasks.
  Explicit triggers: "research", "investigate", "analyze PDF/image/video", "understand codebase".
metadata:
  short-description: Claude Code ↔ Antigravity CLI collaboration (research & multimodal)
---

# Antigravity System — Research & Multimodal Specialist

This skill is **how to call** agy. **What to send, which tier, and what to do
when agy is unavailable** is decided by the always-loaded rule and not repeated
here — two copies of a criterion drift apart:

- Routing, the two-stage funnel, no delegated judgement, model tiers (T1–T4):
  `.claude/rules/antigravity-delegation.md` → "What goes to agy — by cost, not topic", "Model policy"
- When agy is unavailable: check `.claude/skills/antigravity-system/agy-probe`, then
  the same file → "When agy is unavailable". Never skip research; say on the
  output's first line what replaced agy.
- Exact command lines, headless flags, soft-deny handling: `.claude/agents/general-purpose.md`
  (the subagent that runs agy carries them itself)

## How to Consult

**Through a general-purpose subagent**, so the output never enters the main context:

```
Task tool parameters:
- subagent_type: "general-purpose"
- run_in_background: true (optional, for parallel work)
- prompt: |
    Research: {topic}

    agy -p "{research question}" --model {slug}   # the orchestrator fills the slug per tier

    Save full output to: .claude/docs/research/{topic}.md
    Return CONCISE summary (5-7 bullet points).
```

Directly only for a one-line answer: `agy -p "Brief question" --model gemini-3.7-flash-low`.

Never redirect agy's stdout (`> file`, `$(...)`, `; echo $?`): the log hook reads
stdout as agy's answer and records a redirected call as `[UNKNOWN]`. For a copy
on disk use `| tee <file>` (details: `.claude/agents/general-purpose.md`).

Ask agy in **English**; report to the user in **Korean**. Full answers go to
`.claude/docs/research/{topic}.md` so deep-reasoning can read them later.

## Prompt Templates

### Pre-Implementation Research (T3, web — no headless flags)

```
Research best practices for {feature} in {language} {year}.
Include: common patterns and anti-patterns, library recommendations with a
comparison, performance and security considerations, code examples.
```

### Repository Analysis (T4 — reads files, so headless flags + the no-modify sentence)

```
Analyze this repository:
1. Architecture overview  2. Key modules  3. Data flow
4. Entry points and extension points  5. Existing patterns to follow
Answer with file:line for every claim.
Do not create or modify any files; return everything in your response.
```

### Library Research

See: `references/lib-research-task.md`

### Multimodal (T4)

Verified headless: PNG and PDF; video/audio untested through `-p`. Name the
absolute path in the prompt (stdin is not supported) and add the no-modify sentence:
`Read the file at {absolute_path} and {what to extract}. Do not create or modify any files.`
