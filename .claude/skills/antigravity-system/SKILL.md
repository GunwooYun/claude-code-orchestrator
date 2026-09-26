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

> **agy 를 쓸 수 없을 때**: `.claude/skills/antigravity-system/agy-probe` 로 상태를
> 확인하고 `.claude/rules/antigravity-delegation.md` 의 "agy 가 없을 때" 절을
> 따른다. 리서치를 건너뛰지 말고 대체 경로로 진행하되 **무엇으로 대체했는지를
> 산출물 첫 줄에 남긴다.** 이 문구를 복제하지 않는다 — 규칙이 단일 출처다.

## 무엇을 agy 로 보내는가 — 여기서 정하지 않는다

이 스킬은 **어떻게 부르는가**를 담는다. **무엇을 보낼지**는 항상 로드되는 규칙이
정하고, 여기 복제하지 않는다 — 두 곳에 같은 기준이 있으면 갈라진다.

- 라우팅(토큰량 × 추론 난이도), 2단계 퍼널, 판정 위임 금지:
  `.claude/rules/antigravity-delegation.md` → "라우팅은 주제가 아니라 비용으로 한다"
- agy 를 쓸 수 없을 때의 대체 경로: 같은 파일 → "agy 가 없을 때"
- 에이전트별 강점 요약과 트리거 문구: `CLAUDE.md` 의 빠른 사용 가이드
- 출력이 클 때 서브에이전트를 경유하는 기준: `CLAUDE.md` 의 출력 크기 기준

## How to Consult

### Recommended: Subagent Pattern

**Use Task tool with `subagent_type='general-purpose'` to preserve main context.**

```
Task tool parameters:
- subagent_type: "general-purpose"
- run_in_background: true (optional, for parallel work)
- prompt: |
    Research: {topic}

    agy -p "{research question}" --model {slug}   # orchestrator fills the slug per Model Tiers

    Save full output to: .claude/docs/research/{topic}.md
    Return CONCISE summary (5-7 bullet points).
```

### Direct Call (Short Questions Only)

For quick questions expecting brief answers:

```bash
agy -p "Brief question" --model gemini-3.7-flash-low
```

### Model Tiers (pin `--model` per call)

The **main orchestrator** picks the tier when writing the Task prompt; the subagent runs the command as given.

| Tier | Task | `--model` |
|------|------|-----------|
| T1 | One-fact lookup, version check (web) | `gemini-3.7-flash-low` |
| T2 | Summarize/extract one web page or one small local file | `gemini-3.7-flash-high` (machine-consumed extraction → `gemini-3.1-pro-low`) |
| T3 | Comparison, best practices, migration guides, research report | `gemini-3.1-pro-high` |
| T4 | Whole-repo analysis, "explain this module", PDF/image/video | `gemini-3.1-pro-high` + `--print-timeout 10m` |

Headless flags follow the **input**, not the tier: any prompt naming a file/dir/module/repo
carries `--dangerously-skip-permissions --sandbox` + "Do not create or modify any files".
Unsure → higher tier. Never downgrade T4. Empty answer → check stderr for `auto-denied`
first (flag problem, same tier with flags); only a genuinely shallow answer → re-run once
on `gemini-3.1-pro-high`. Never pass `--effort`.
Full policy: `.claude/rules/antigravity-delegation.md` → "Model Policy".

### CLI Options Reference

```bash
# Web prompts (no file reads → no flags)
agy -p "{question}. Include the source URL." --model gemini-3.7-flash-low   # T1 quick fact
agy -p "{summarize this page}" --model gemini-3.7-flash-high                # T2 web summary
agy -p "{compare A vs B}" --model gemini-3.1-pro-high                       # T3 research report

# T2 one local file (input names a file → flags + read-only sentence)
agy -p "Read the file at {absolute_path} and {summarize}. Do not create or modify any files." \
  --model gemini-3.7-flash-high --dangerously-skip-permissions --sandbox

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
agy -p "Read the file at /path/to/tutorial.mp4 and analyze: main concepts, key points, timestamps. Do not create or modify any files." --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox

# PDF
agy -p "Read the file at /path/to/api-docs.pdf and extract: API specs, examples, constraints. Do not create or modify any files." --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox

# Image
agy -p "Read the file at /path/to/diagram.png and describe the architecture it shows. Do not create or modify any files." --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox
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
