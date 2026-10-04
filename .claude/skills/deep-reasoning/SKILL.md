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

When to consult, when not, large inputs and the basic prompt shape:
`.claude/rules/deep-reasoning-delegation.md` (always loaded — not repeated here).
The subagent is read-only; the main session or a general-purpose subagent applies
its recommendation. Prompt in English, report to the user in Korean.

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

## With agy

Research first (library comparison, unfamiliar code base) → agy through a
general-purpose subagent, then deep-reasoning decides. A design decision on
known code → deep-reasoning directly.
