# Antigravity Delegation Rule

**Antigravity CLI (`agy`) is your research specialist with massive context and multimodal capabilities (Gemini models).**

## Context Management (CRITICAL)

**컨텍스트 소비를 의식해서 agy를 사용한다.**
agy는 출력이 커지기 쉬우므로, **서브 에이전트 경유를 권장**한다.

| 상황 | 권장 방법 |
|------|-----------|
| 짧은 질문 · 짧은 답변 | 직접 호출 OK |
| 코드베이스 분석 | 서브 에이전트 경유 (출력 큼) |
| 라이브러리 조사 | 서브 에이전트 경유 (출력 큼) |
| 멀티모달 처리 | 서브 에이전트 경유 |

```
┌──────────────────────────────────────────────────────────┐
│  Main Claude Code                                        │
│  → 짧은 질문이면 직접 호출하면 됨                             │
│  → 출력이 클 것으로 예상되면 서브 에이전트 경유          │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Subagent (general-purpose)                         │ │
│  │  → Calls Antigravity CLI (agy)                      │ │
│  │  → Saves full output to .claude/docs/research/      │ │
│  │  → Returns key findings only                        │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

## About Antigravity CLI

Antigravity CLI (`agy`) is the successor of Gemini CLI and excels at:
- **Massive context (Gemini models)** — Analyze entire codebases at once
- **Google Search grounding** — Access latest information
- **Multimodal processing** — PDF, image, video analysis

Think of agy as your research assistant who can quickly gather and synthesize information.

**When you need research → Delegate to subagent → Subagent consults agy.**

## Antigravity vs deep-reasoning: Choose the Right Tool

| Task | deep-reasoning | Antigravity (agy) |
|------|----------------|-------------------|
| Design decisions | ✓ | |
| Debugging | ✓ | |
| Code implementation | ✓ | |
| Trade-off analysis | ✓ | |
| Large codebase understanding | | ✓ |
| Pre-implementation research | | ✓ |
| Latest docs/library research | | ✓ |
| PDF/image/video analysis | | ✓ |

## When to Consult agy

ALWAYS consult agy BEFORE:

1. **Pre-implementation research** - Best practices, library comparison
2. **Large codebase analysis** - Repository-wide understanding
3. **Documentation search** - Latest official docs, breaking changes
4. **Multimodal tasks** - PDF, image, video content extraction

### Trigger Phrases (User Input)

Consult agy when user says:

| Korean | English |
|----------|---------|
| "조사해 줘", "리서치해 줘", "조사해" | "Research" "Investigate" "Look up" |
| "이 PDF/영상/이미지를 봐줘"  | "Analyze this PDF/video/image" |
| "코드베이스 전체를 이해해 줘" | "Understand the entire codebase" |
| "최신 문서를 확인해 줘" | "Check the latest documentation" |
| "~에 대한 정보를 모아줘" | "Gather information about X" |

## When NOT to Consult

Skip agy for:

- Design decisions (use deep-reasoning subagent instead)
- Code implementation (main Claude or general-purpose subagent)
- Debugging (use deep-reasoning subagent instead)
- Simple file operations (do directly)
- Running tests/linting (do directly)

## How to Consult (via Subagent)

**IMPORTANT: Use subagent to preserve main context.**

### Recommended: Subagent Pattern

Use Task tool with `subagent_type: "general-purpose"`:

```
Task tool parameters:
- subagent_type: "general-purpose"
- run_in_background: true (for parallel work)
- prompt: |
    Research: {topic}

    1. Call Antigravity CLI:
       agy -p "{research question}"

    2. Save full output to: .claude/docs/research/{topic}.md

    3. Return CONCISE summary (5-7 bullet points):
       - Key findings
       - Recommended approach
       - Important caveats
```

### Subagent Patterns by Task Type

**Research Pattern:**
```
prompt: |
  Research best practices for {topic}.

  agy -p "Research: {topic}. Include recommended approaches,
  common pitfalls, and library recommendations."

  Save to .claude/docs/research/{topic}.md
  Return 5-7 key bullet points.
```

**Codebase Analysis Pattern** (reads repo files → needs the headless flags):
```
prompt: |
  Analyze codebase for {purpose}.

  Run from the repository root (CWD is the workspace):
  agy -p "Analyze architecture, key modules, data flow,
  and entry points of this repository.
  Do not create or modify any files; return everything in your response." \
    --dangerously-skip-permissions --sandbox --print-timeout 10m

  Save to .claude/docs/research/codebase-analysis.md
  Return architecture summary and key insights.
```

**Multimodal Pattern** (reads a file → needs the headless flags):
```
prompt: |
  Extract information from {file}.

  agy -p "Read the file at {absolute_path} and {extraction prompt}.
  Do not create or modify any files; return everything in your response." \
    --dangerously-skip-permissions --sandbox

  (stdin file redirection is NOT supported — pass the absolute path
   in the prompt; agy reads the file with its own tools. Verified for
   images and PDF; video/audio untested.)

  Save to .claude/docs/research/{output}.md
  Return key extracted information.
```

### Step 2: Continue Your Work

While subagent is processing, you can:
- Work on other files
- Run tests
- Spawn the deep-reasoning subagent for design/debugging consultation

### Step 3: Receive Summary

Subagent returns concise summary. Full output available in `.claude/docs/research/` if needed.

## Antigravity CLI Commands Reference

For use within subagents:

```bash
# Research (simple)
agy -p "{question}"

# Codebase analysis (reads repo files → headless flags required; CWD is the workspace)
agy -p "{question} Do not create or modify any files." \
  --dangerously-skip-permissions --sandbox --print-timeout 10m [--add-dir {path}]

# Multimodal (path-in-prompt; no stdin redirection; headless flags required)
agy -p "Read the file at {absolute_path} and {question} Do not create or modify any files." \
  --dangerously-skip-permissions --sandbox

# Scripted/CI calls (recommended for automation)
agy -p "{question}" --output-format json --print-timeout 10m
```

### Headless Caveats (IMPORTANT)

- **soft-deny trap**: In print mode, a tool that cannot get permission is
  silently skipped and the run still exits 0. If research comes back empty,
  check stderr for soft-deny notices or use `--output-format json` and gate
  on `.status == "SUCCESS"`.
- **File reads are denied in headless mode by default** (verified 2026-08-30:
  `read_file` on a workspace image was auto-denied → empty response, status
  SUCCESS). This template therefore appends
  `--dangerously-skip-permissions --sandbox` to every pattern that must read
  files (codebase analysis, multimodal). `--sandbox` restricts terminal
  commands during that call; file reads still work (verified for a workspace
  PNG, an out-of-workspace PNG, and a PDF). Pure web research prompts do not
  need the flags.
- **What the flags expose**: `write_file`, `read_url`, and MCP tools are also
  auto-approved for that call, and `Bash(agy:*)` in `settings.json` lets
  subagents run such calls without a Claude-side prompt. The real guard is the
  prompt: every flagged template must say *"Do not create or modify any files;
  return everything in your response"* (also enforced by `.agents/rules/AGENTS.md`),
  and the calls run only inside git-tracked repos.
- Whole-repo analysis can exceed the 5m default — flagged patterns include
  `--print-timeout 10m`. Files outside the workspace can also be exposed
  explicitly with `--add-dir <dir>`.
- Optional hardening (per machine, not part of the template): allow reads
  globally with `{"permissions": {"allow": ["read_file(*)"]}}` in
  `~/.gemini/antigravity-cli/settings.json` and drop the flags.
- **Default timeout is 5m** — set `--print-timeout` explicitly for long tasks.
- Model can be pinned with `--model {slug}` (list: `agy models`,
  e.g. `gemini-3.1-pro-high`); unknown slugs fail loudly.
- Do NOT redirect stderr to /dev/null in subagent calls — it carries the
  soft-deny diagnostics.

**Language protocol:**
1. Ask agy in **English**
2. Subagent receives response in **English**
3. Subagent summarizes and saves full output
4. Main receives summary, reports to user in **Korean**

## Why Subagent Pattern?

- **Context preservation**: Main orchestrator stays lightweight
- **Full capture**: Subagent can save entire agy output to file
- **Concise handoff**: Main only receives key findings
- **Parallel work**: Background subagents enable concurrent research

**Use agy (via subagent) for research, the deep-reasoning subagent for reasoning, Claude for orchestration.**
