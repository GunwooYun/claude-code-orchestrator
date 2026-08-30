# Antigravity CLI (agy) Use Cases

## Use Case Categories

### 1. Pre-Implementation Research

Before implementing a new feature, use agy to research best practices.

```bash
# General research
agy -p "Research best practices for implementing OAuth2 in Python.
Include:
- Recommended libraries (compare authlib vs python-oauth2 vs others)
- Security considerations
- Common pitfalls to avoid
- Example implementations"

# Framework-specific research
agy -p "Research FastAPI authentication patterns in 2025.
Focus on:
- JWT vs session-based auth
- Dependency injection patterns
- Testing strategies"
```

### 2. Repository-Wide Understanding

Leverage the 1M token context window for comprehensive codebase analysis.

```bash
# Full repository analysis
agy -p "Analyze this entire codebase and provide:
1. Architecture diagram (describe in text)
2. Module dependency graph
3. Key abstractions and their purposes
4. Suggested areas for improvement"

# Specific aspect analysis
agy -p "Trace the data flow for user authentication:
- Entry points (API endpoints)
- Middleware processing
- Database interactions
- Response formatting"
```

### 3. Multimodal Data Analysis

#### Video Analysis

```bash
# Tutorial video analysis
agy -p "Read the file at ./tutorial.mp4. Analyze this tutorial video:
- Summarize the main concepts taught
- List step-by-step instructions
- Note any important warnings or tips
- Identify timestamps for key sections"

# Code review video
agy -p "Read the file at ./code-review.mp4. Extract code patterns and best practices demonstrated in this video"
```

#### Audio Analysis

```bash
# Meeting recording
agy -p "Read the file at ./meeting.mp3. Transcribe and summarize this technical discussion:
- Key decisions made
- Action items
- Open questions
- Technical terms mentioned"

# Podcast/talk analysis
agy -p "Read the file at ./conference-talk.mp3. Extract technical insights from this talk about {topic}"
```

#### PDF Analysis

```bash
# API documentation
agy -p "Read the file at ./api-spec.pdf. Extract from this API documentation:
- All available endpoints
- Request/response schemas
- Authentication requirements
- Rate limiting rules"

# Technical specification
agy -p "Read the file at ./spec.pdf. Summarize this technical specification:
- Core requirements
- Constraints
- Interface definitions
- Edge cases to handle"

# Research paper
agy -p "Read the file at ./paper.pdf. Analyze this paper and explain:
- Problem being solved
- Proposed approach
- Key algorithms
- How to apply this in practice"
```

### 4. Documentation & Web Research

```bash
# Latest documentation
agy -p "Find and summarize the latest React 19 features and migration guide from official docs"

# Compare libraries
agy -p "Compare these Python HTTP clients in 2025:
- httpx vs aiohttp vs requests
- Performance benchmarks
- Feature comparison
- Community activity"

# Troubleshooting
agy -p "Research common causes and solutions for: {error message}
Search Stack Overflow, GitHub Issues, and official docs"
```

### 5. Code Migration Analysis

```bash
# Framework migration
agy -p "Analyze our codebase for Django to FastAPI migration:
- Identify all Django-specific patterns used
- Map to FastAPI equivalents
- Estimate migration complexity per module
- Suggest migration order"

# Version upgrade
agy -p "Research breaking changes from Python 3.11 to 3.13.
Cross-reference with our codebase to identify:
- Deprecated features we use
- New features we could adopt
- Required changes"
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
  --output-format json
```

### Piping to Files

```bash
agy -p "Generate comprehensive documentation for src/auth/" > docs/auth-module.md
```

## Quota

agy draws on the Google account's Antigravity quota. When it is exhausted the CLI
prints `Individual quota reached ... Resets in Xh` and exits with an error — wait for
the reset (or upgrade the plan). Plan accordingly for large research tasks.
