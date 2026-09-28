---
name: design-tracker
description: PROACTIVELY track and document project design decisions without being asked. Activate automatically when detecting architecture discussions, implementation decisions, pattern choices, library selections, or any technical decisions. Also use when user explicitly says "記録して", "設計どうなってる", "record this". Do NOT wait for user to ask - record important decisions immediately.
---

# Design Tracker Skill

## Purpose

This skill manages the project's design documentation (`.claude/docs/DESIGN.md`). It automatically tracks:
- Architecture decisions
- Implementation plans
- Library choices and their rationale
- TODO items and open questions

## When to Activate

- User discusses architecture or design patterns
- User makes implementation decisions (e.g., "let's use ReAct pattern")
- User says "record this", "add to design", "document this"
- User asks "what's our current design?" or "what have we decided?"
- Important technical decisions are made during conversation

## Workflow

### Recording Decisions

1. Read existing `.claude/docs/DESIGN.md`
2. Extract the decision/information from conversation
3. Update the appropriate section
4. Add entry to Changelog with today's date

### Sections to Update

| Conversation Topic | Target Section |
|-------------------|----------------|
| Overall goals, purpose | Overview |
| System structure, components | Architecture |
| Patterns (ReAct, etc.) | Implementation Plan > Patterns |
| Library choices | Implementation Plan > Libraries |
| Why we chose X over Y | Implementation Plan > Key Decisions |
| Things to implement later | TODO |
| Unresolved questions | Open Questions |

## Record Format

Write rows into the tables the file already has (`.claude/docs/DESIGN.md` ships
with them). Do not add headings of your own — the skeleton's headings are what
every other skill reads.

Key Decisions — one row per decision:

```markdown
| Decision | Rationale | Alternatives Considered | Date |
|----------|-----------|------------------------|------|
| {What was decided} | {Why this option; what made it necessary} | {What was rejected, and why} | {YYYY-MM-DD} |
```

Changelog — one row per update:

```markdown
| Date | Changes |
|------|---------|
| {YYYY-MM-DD} | {Brief description of what was recorded} |
```

If the file still has an empty placeholder row (`| | | | |`), replace it with
the first real row.

## Output Format

When recording, confirm in Korean:
- What was recorded
- Which section was updated
- Brief summary of the change

## Language Rules

- **Thinking/Reasoning**: English
- **Code examples**: English
- **Document content**: English (technical terms) + Korean (descriptions OK)
- **User communication**: Korean
