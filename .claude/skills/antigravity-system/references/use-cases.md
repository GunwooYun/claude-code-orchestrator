# Antigravity CLI (agy) Use Cases

## Use Case Categories

Every example pins `--model` per the Model Policy in `.claude/rules/antigravity-delegation.md`
(T1 `gemini-3.7-flash-low`, T2 `gemini-3.7-flash-high`, T3/T4 `gemini-3.1-pro-high`).

### 1. Pre-Implementation Research

Before implementing a new feature, use agy to research best practices.

```bash
# General research
agy -p "Research best practices for implementing OAuth2 in Python.
Include:
- Recommended libraries (compare authlib vs python-oauth2 vs others)
- Security considerations
- Common pitfalls to avoid
- Example implementations" --model gemini-3.1-pro-high

# Framework-specific research
agy -p "Research FastAPI authentication patterns in 2026.
Focus on:
- JWT vs session-based auth
- Dependency injection patterns
- Testing strategies" --model gemini-3.1-pro-high
```

### 2. Repository-Wide Understanding

Leverage the massive context window for comprehensive codebase analysis.
Reading repo files in headless mode requires `--dangerously-skip-permissions --sandbox`;
whole-repo analysis can exceed the 5m default, so add `--print-timeout 10m`.
These prompts must stay read-only: agy must not create or modify files.

```bash
# Full repository analysis
agy -p "Analyze this entire codebase and provide:
1. Architecture diagram (describe in text)
2. Module dependency graph
3. Key abstractions and their purposes
4. Suggested areas for improvement" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox --print-timeout 10m

# Specific aspect analysis
agy -p "Trace the data flow for user authentication:
- Entry points (API endpoints)
- Middleware processing
- Database interactions
- Response formatting" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox --print-timeout 10m
```

### 3. Multimodal Data Analysis

Verified headless: images (PNG) and PDF. Video/audio are supported by the models but
untested via `-p`. Use absolute paths; files outside the workspace also worked under the flags.

#### Video Analysis

```bash
# Tutorial video analysis
agy -p "Read the file at /path/to/tutorial.mp4. Analyze this tutorial video:
- Summarize the main concepts taught
- List step-by-step instructions
- Note any important warnings or tips
- Identify timestamps for key sections" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox

# Code review video
agy -p "Read the file at /path/to/code-review.mp4. Extract code patterns and best practices demonstrated in this video" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox
```

#### Audio Analysis

```bash
# Meeting recording
agy -p "Read the file at /path/to/meeting.mp3. Transcribe and summarize this technical discussion:
- Key decisions made
- Action items
- Open questions
- Technical terms mentioned" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox

# Podcast/talk analysis
agy -p "Read the file at /path/to/conference-talk.mp3. Extract technical insights from this talk about {topic}" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox
```

#### PDF Analysis

```bash
# API documentation
agy -p "Read the file at /path/to/api-spec.pdf. Extract from this API documentation:
- All available endpoints
- Request/response schemas
- Authentication requirements
- Rate limiting rules" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox

# Technical specification
agy -p "Read the file at /path/to/spec.pdf. Summarize this technical specification:
- Core requirements
- Constraints
- Interface definitions
- Edge cases to handle" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox

# Research paper
agy -p "Read the file at /path/to/paper.pdf. Analyze this paper and explain:
- Problem being solved
- Proposed approach
- Key algorithms
- How to apply this in practice" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox
```

### 4. Documentation & Web Research

```bash
# Latest documentation
agy -p "Find and summarize the latest React 19 features and migration guide from official docs" --model gemini-3.7-flash-high

# Compare libraries
agy -p "Compare these Python HTTP clients in 2026:
- httpx vs aiohttp vs requests
- Performance benchmarks
- Feature comparison
- Community activity" --model gemini-3.1-pro-high

# Troubleshooting
agy -p "Research common causes and solutions for: {error message}
Search Stack Overflow, GitHub Issues, and official docs" --model gemini-3.1-pro-high
```

### 5. Code Migration Analysis

```bash
# Framework migration
agy -p "Analyze our codebase for Django to FastAPI migration:
- Identify all Django-specific patterns used
- Map to FastAPI equivalents
- Estimate migration complexity per module
- Suggest migration order" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox --print-timeout 10m

# Version upgrade
agy -p "Research breaking changes from Python 3.11 to 3.13.
Cross-reference with our codebase to identify:
- Deprecated features we use
- New features we could adopt
- Required changes" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox --print-timeout 10m
```

## When NOT to Use Antigravity

| Task | Reason | Use Instead |
|------|--------|-------------|
| Design decisions | Requires deep reasoning | deep-reasoning subagent |
| Code implementation | Execution task | Claude Code directly |
| Debugging | Requires logical analysis | deep-reasoning subagent |
| Simple file edits | Overkill | Claude Code directly |
| Running tests | Execution task | Claude Code directly |

## Output Handling

### JSON Output for Structured Data

```bash
agy -p "List all API endpoints in this codebase with their HTTP methods" \
  --dangerously-skip-permissions --sandbox --output-format json
```

### Piping to Files

```bash
agy -p "Generate comprehensive documentation for src/auth/" \
  --dangerously-skip-permissions --sandbox > docs/auth-module.md
```

## Quota

agy draws on the Google account's Antigravity quota. When it is exhausted the CLI
prints `Individual quota reached ... Resets in Xh` and exits with an error — wait for
the reset (or upgrade the plan). Plan accordingly for large research tasks.
