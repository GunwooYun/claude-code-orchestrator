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

**Antigravity CLI (`agy`, Gemini models) is your research specialist with massive context.**

> **상세규칙**: `.claude/rules/antigravity-delegation.md`

## Context Management (CRITICAL)

**서브에이전트 경유 권장한다**. agy 출력은 커지기 쉽기 때문에.

| 상황 | 방법 |
|------|------|
| 코드베이스 분석 | 서브에이전트 경유 (권장) |
| 라이브러리 조사 | 서브에이전트 경유 (권장) |
| 멀티모달 | 서브에이전트 경유 (권장) |
| 짧은 질문 (1-2 문 답변) | 직접 호출 OK |

## Antigravity vs deep-reasoning

| Task | Antigravity (agy) | deep-reasoning |
|------|-------------------|----------------|
|**리포지토리 전체 이해**|✓| |
|**라이브러리 조사**|✓| |
|**멀티모달(PDF/이미지/동영상)**|✓| |
|**최신 문서 검색**|✓| |
|**디자인 판단**| |✓|
|**디버그** | |✓|
|**코드 구현** | | (main Claude / general-purpose) |

## When to Consult (MUST)

| Situation | Trigger Examples |
|-----------|------------------|
| **Research** | "검색" "리서치" / "Research" "Investigate" |
| **Library docs** | "라이브러리" "문서" / "Library" "Docs" |
| **Codebase analysis** | "코드베이스 전체" / "Entire codebase" |
| **Multimodal** | "PDF" "이미지" "동영상" / "PDF" "Image" "Video" |

## When NOT to Consult

- Design decisions (use deep-reasoning subagent)
- Debugging (use deep-reasoning subagent)
- Code implementation (main Claude or general-purpose subagent)
- Simple file operations (do directly)

## How to Consult

### Recommended: Subagent Pattern

**Use Task tool with `subagent_type='general-purpose'` to preserve main context.**

```
Task tool parameters:
- subagent_type: "general-purpose"
- run_in_background: true (optional, for parallel work)
- prompt: |
    Research: {topic}

    agy -p "{research question}" --model gemini-3.1-pro-high   # T3; use flash tiers for lookups

    Save full output to: .claude/docs/research/{topic}.md
    Return CONCISE summary (5-7 bullet points).
```

### Direct Call (Short Questions Only)

For quick questions expecting brief answers:

```bash
agy -p "Brief question" --model gemini-3.7-flash-low
```

### Model Tiers (pin `--model` per call)

| Tier | Task | `--model` |
|------|------|-----------|
| T1 | One-fact lookup, version check | `gemini-3.7-flash-low` |
| T2 | Summarize/extract from one source | `gemini-3.7-flash-high` |
| T3 | Comparison, best practices, research report | `gemini-3.1-pro-high` |
| T4 | Whole-repo analysis, PDF/image/video | `gemini-3.1-pro-high` + `--print-timeout 10m` |

Unsure → higher tier. Never downgrade T4. Empty/shallow T1–T2 answer → re-run once at T3.
Full policy: `.claude/rules/antigravity-delegation.md` → "Model Policy".

### CLI Options Reference

```bash
# T1 / T2 / T3 (web research, no file reads)
agy -p "{question}" --model gemini-3.7-flash-low        # quick fact
agy -p "{summarize X}" --model gemini-3.7-flash-high    # single-source summary
agy -p "{compare A vs B}" --model gemini-3.1-pro-high   # research report

# T4 codebase analysis (reads repo files → headless flags required; run from repo root)
agy -p "{question} Do not create or modify any files." \
  --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox --print-timeout 10m

# T4 multimodal (path-in-prompt; stdin redirection NOT supported; headless flags required)
agy -p "Read the file at {absolute_path} and {prompt}. Do not create or modify any files." \
  --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox

# JSON output (any tier; gate on .status == "SUCCESS")
agy -p "{question}" --model {slug} --output-format json --print-timeout 10m
```

**Headless caveats**: permission-denied tools are silently skipped with exit 0
(soft-deny) — if results look empty, check stderr or the JSON `.status` field.
File reads are denied by default in headless mode, so every pattern that reads
files carries `--dangerously-skip-permissions --sandbox` (auto-approves agy's
tools incl. write_file; terminal sandboxed). Those prompts MUST include
"Do not create or modify any files; return everything in your response".
Web research prompts need no flags. Default print timeout is 5m (repo analysis
adds `--print-timeout 10m`). Pin models with `--model {slug}` (`agy models`).

### Workflow (Subagent)

1. **Spawn subagent** with agy research prompt
2. **Continue your work** → Subagent runs in parallel
3. **Receive summary** → Subagent returns key findings
4. **Full output saved** → `.claude/docs/research/{topic}.md`

## Language Protocol

1. Ask agy in **English**
2. Receive response in **English**
3. Synthesize and apply findings
4. Report to user in **Korean**

## Output Location

Save agy research results to:
```
.claude/docs/research/{topic}.md
```

This allows Claude (and the deep-reasoning subagent) to reference the research later.

## Task Templates

### Pre-Implementation Research

```bash
agy -p "Research best practices for {feature} in Python 2026.
Include:
- Common patterns and anti-patterns
- Library recommendations (with comparison)
- Performance considerations
- Security concerns
- Code examples" --model gemini-3.1-pro-high
```

### Repository Analysis

```bash
agy -p "Analyze this repository:
1. Architecture overview
2. Key modules and responsibilities
3. Data flow between components
4. Entry points and extension points
5. Existing patterns to follow
Do not create or modify any files; return everything in your response." \
  --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox --print-timeout 10m
```

### Library Research

See: `references/lib-research-task.md`

### Multimodal Analysis

Verified headless: images (PNG) and PDF. Video/audio untested via `-p`.
Add "Do not create or modify any files." to each prompt.

```bash
# Video
agy -p "Read the file at /path/to/tutorial.mp4 and analyze: main concepts, key points, timestamps" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox

# PDF
agy -p "Read the file at /path/to/api-docs.pdf and extract: API specs, examples, constraints" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox

# Image
agy -p "Read the file at /path/to/diagram.png and describe the architecture it shows" --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox
```

## Integration with deep-reasoning

| Workflow | Steps |
|----------|-------|
| **New feature** | agy research → deep-reasoning design review |
| **Library choice** | agy comparison → deep-reasoning decision |
| **Bug investigation** | agy codebase search → deep-reasoning debug |

## Why Antigravity?

- **Massive context (Gemini models)**: Entire repositories at once
- **Google Search**: Latest information and docs
- **Multimodal**: PDF/image/video understanding
- **Fast exploration**: Quick overview before deep work
- **Shared context**: Results saved for Claude and its subagents
