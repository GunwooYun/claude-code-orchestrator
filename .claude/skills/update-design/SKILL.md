---
name: update-design
description: Explicitly update DESIGN.md with decisions from the current conversation. Use when you want to force a design document update.
disable-model-invocation: true
---

# Update Design Document

Record/update project design and implementation decisions in `.claude/docs/DESIGN.md` based on conversation content.

> **Note**: This skill explicitly invokes the same workflow as the `design-tracker` skill.
> Use this when you want to force a design document update.

## Workflow

1. Read existing `.claude/docs/DESIGN.md`
2. Extract decisions/information from the conversation
3. Update the appropriate section
4. Add entry to Changelog with today's date

## Section Mapping

| Topic | Section |
|-------|---------|
| Goals, purpose | Overview |
| Structure, components | Architecture |
| Design patterns | Implementation Plan > Patterns |
| Library choices | Implementation Plan > Libraries |
| Decision rationale | Implementation Plan > Key Decisions |
| Future work | TODO |
| Unresolved issues | Open Questions |

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

## Language

- Document content: English (technical), Korean OK for descriptions
- User communication: Korean

If $ARGUMENTS provided, focus on recording that content.
