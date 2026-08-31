# Library Research Task for Antigravity (agy)

When delegating library research to agy, use this prompt template.

## Prompt Template

```
Research the library "{library_name}" comprehensively.

Use Google Search to find:
- Official documentation
- GitHub README, Issues, Discussions
- PyPI / npm pages
- Latest blog posts, tutorials (2026)

---

Provide documentation in this structure:

## Basic Information
- Library name, current version, license
- Official documentation URL
- Installation method (pip, npm, etc.)
- Python/Node version requirements

## Core Features
- Main features and primary use cases
- Basic usage with code examples
- Key APIs and their purposes

## Important Constraints & Notes
- Known limitations
- Conflicts with other libraries
- Performance characteristics
- Breaking changes in recent versions
- Async/sync requirements
- Thread-safety considerations

## Common Patterns
- Recommended initialization patterns
- Error handling patterns
- Configuration best practices
- Testing approaches

## Troubleshooting
- Common errors and solutions
- Debugging methods
- Where to find help (Discord, GitHub Issues, etc.)

---

Output in markdown format suitable for saving to .claude/docs/libraries/{library_name}.md
Output documentation content in English.
```

## Example Invocation

```bash
# Basic library research
agy -p "Research the library 'httpx' comprehensively.

Use Google Search to find:
- Official documentation
- GitHub README, Issues, Discussions
- PyPI pages
- Latest blog posts, tutorials (2026)

[Template structure as above...]
" --model gemini-3.1-pro-high

# Research with specific focus
agy -p "Research 'pydantic' v2 with focus on:
- Migration from v1 to v2
- Performance improvements
- New validation patterns
- Breaking changes

[Template structure as above...]
" --model gemini-3.1-pro-high
```

## Workflow

1. **Run agy research** (background)
   ```bash
   agy -p "Research: {library}" --model gemini-3.1-pro-high
   ```

2. **Save output to docs**
   - Claude saves agy's output to `.claude/docs/libraries/{library}.md`

3. **Update existing docs**
   - If documentation already exists, compare and update

## Output Location

All library documentation should be saved to:
```
.claude/docs/libraries/{library-name}.md
```

## When to Use

- Introducing a new library to the project
- Checking library specifications before implementation
- Updating outdated library documentation
- Investigating library conflicts or issues
- When user says "이 라이브러리에 대해 조사해 줘", "research this library"

## Integration with deep-reasoning

After agy researches a library:
1. Documentation is saved to `.claude/docs/libraries/`
2. The deep-reasoning subagent can reference this when reviewing code or refactoring
3. Ensures library constraints are respected across all agents
