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

## agy 가 없을 때 (CRITICAL)

**agy 설치·로그인은 전제이지 보장이 아니다.** 폐쇄망, 만료된 세션, 소진된 쿼터,
설치되지 않은 머신 — 어느 경우든 작업 중에 발생할 수 있다.

### 상태 판별

```sh
.claude/skills/antigravity-system/agy-probe
```

종료 코드 `0` 이면 쓸 수 있다. `0 이외` 면 첫 단어가 상태다.

| 상태 | 뜻 | 조치 |
|---|---|---|
| `READY` | 설치·인증·응답 정상 | 그대로 진행 |
| `MISSING` | PATH 에 없음 | 아래 대체 경로로 진행 + 설치를 사용자에게 알림 |
| `UNAUTHENTICATED` | 설치됐지만 세션 없음 | 대체 경로 + **로그인만 하면 된다**고 알림 |
| `DEGRADED` | 응답이 비었음 (soft-deny·쿼터·네트워크) | 대체 경로 + 무엇이 비었는지 알림 |

**작업 단위마다 한 번만 확인한다.** 호출마다 프로브를 돌리면 그 자체가 낭비다.
`/feature` Phase 1 에서 한 번 확인하고 결과를 그 작업 내내 재사용한다.

### 대체 경로 (agy 없이 같은 목적을 달성한다)

| agy 의 역할 | 대체 | 무엇을 잃는가 |
|---|---|---|
| 웹 리서치 (T1~T3) | general-purpose 서브에이전트가 `WebSearch`/`WebFetch` 로 조사 → `.claude/docs/research/` 저장 → 요약 반환 | Google 그라운딩의 넓이. Claude 토큰을 씀 |
| 레포 전체 분석 (T4) | general-purpose 서브에이전트가 `Grep`/`Glob`/`Read` 로 **표적 탐색** | 전수 조사가 아님 — 무엇을 읽었는지 명시해야 함 |
| PDF·이미지 | Claude 의 `Read` 도구가 직접 읽는다 | 거의 없음 |
| 영상·음성 | **대체 불가** | 그 작업은 할 수 없다 |
| deep-reasoning 앞단 프리필터 | 생략하고 deep-reasoning 이 직접 읽는다 | 비싼 모델이 넓게 읽음 (토큰 증가) |

### 절대 규칙

- **조용히 degrade 하지 않는다.** agy 없이 만든 리서치 문서는 **첫 줄에 그 사실과
  무엇으로 대체했는지**를 적는다. 나중에 읽는 사람이 Gemini 전수 조사로 오해하면
  그 문서를 근거로 잘못된 결정을 한다.
- **리서치를 건너뛰고 계획을 세우지 않는다.** 대체 경로도 불가능하면
  "조사하지 못했다"를 계획에 명시하고 그 불확실성을 리스크로 올린다. 없는 조사를
  있는 것처럼 두면 `/feature` Phase 3 이 검토할 근거가 사라진다.
- **대체 불가한 것(영상·음성)은 대체 불가라고 말한다.** 비슷한 것으로 갈음하지
  않는다.
- 상태를 사용자에게 **한 번** 알린다. 매 호출마다 반복하면 무시하게 된다.
- `/initproject` 는 설정 시점에 이 판별을 하고 설치·로그인을 요청한다. 실행 중에는
  사용자를 기다릴 수 없으므로 대체 경로로 진행하고 사실만 보고한다.

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

    1. Call Antigravity CLI (the orchestrator fills {slug} per the Model Policy):
       agy -p "{research question}" --model {slug}

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
  common pitfalls, and library recommendations." --model {slug}   # T3 → gemini-3.1-pro-high

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
    --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox --print-timeout 10m

  Save to .claude/docs/research/codebase-analysis.md
  Return architecture summary and key insights.
```

**Multimodal Pattern** (reads a file → needs the headless flags):
```
prompt: |
  Extract information from {file}.

  agy -p "Read the file at {absolute_path} and {extraction prompt}.
  Do not create or modify any files; return everything in your response." \
    --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox

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

## Model Policy (choose `--model` by task tier)

The global default is set by the user via `/model` in the agy TUI (currently
`gemini-3.1-pro-high`). Templates pin the model **per call** so quota is spent
where it matters. Slugs come from `agy models`; the suffix is the effort tier.

**Who decides**: the **main orchestrator** picks the tier when it writes the
Task prompt (it knows the user's intent) and puts the concrete slug into the
command; the general-purpose subagent executes it as given. Templates therefore
show `--model {slug}` — never a hard-coded slug — unless the tier is fixed by
the task shape (T4).

| Tier | Task shape | `--model` | Notes |
|------|-----------|-----------|-------|
| **T1 Quick lookup** | One fact / yes-no / version check; answer ≤ 1 paragraph; single web source | `gemini-3.7-flash-low` | Cheapest. Ask for the source URL in the prompt (do not auto-escalate when it is missing) |
| **T2 Summarize / extract** | Summarize **one web page** or **one small local file**; pull structured fields from a known input | `gemini-3.7-flash-high` | If the output is **machine-consumed** (`--json-schema`, piped into a script) use `gemini-3.1-pro-low` instead — schema enforces shape, not completeness |
| **T3 Research report** | Library comparison, best practices, multi-source synthesis, migration/breaking-change guides | `gemini-3.1-pro-high` | Save output to `.claude/docs/research/` |
| **T4 Whole-repo / multimodal** | Repository-wide analysis, "explain this module/directory", cross-module tracing, PDF/image/video | `gemini-3.1-pro-high` + `--print-timeout 10m` | Never downgrade |

**Headless flags are keyed on the INPUT, not the tier.** Whenever the prompt
names a local file, directory, module, or "this repo" — at *any* tier — the
command must carry `--dangerously-skip-permissions --sandbox` **and** the
sentence "Do not create or modify any files; return everything in your
response." Pure web prompts never need them.

Decision rules:

1. **Unsure between two tiers → pick the higher one.** A wrong downgrade means a
   re-run, which costs more than the Pro call it tried to avoid.
2. **Never downgrade T4.** Large-context accuracy is the whole point of agy.
3. **User instruction wins** ("use flash", "use pro") over this table.
4. **Empty answer → check for soft-deny first, then escalate once.** If stderr
   says `auto-denied` (or JSON `.status`/`response` shows an empty success),
   it is a *flag* problem: re-run at the **same** tier with the headless flags.
   Only if a flagged/web call is genuinely hedged or shallow, re-run **once** on
   `gemini-3.1-pro-high` with the same flags — never loop at the same tier.
5. Do **not** pass `--effort`; the slug suffix (`-low/-high`) is the only
   effort knob. Calls without `--model` fall back to the user's global default
   (currently the most expensive tier) and are logged as `"default"` — pin.

Rationale: savings come from the call *distribution* (most calls are T1/T2),
not from table granularity; more rows enlarge the overlap between descriptions
and make routing itself error-prone. Keep 4 tiers; after a few weeks,
`jq .model .claude/logs/cli-tools.jsonl` shows the real distribution — refine
only if the T3 share is high.

## Antigravity CLI Commands Reference

For use within subagents:

```bash
# T1 quick lookup (web)
agy -p "{one-fact question}. Include the source URL." --model gemini-3.7-flash-low

# T2 summarize / extract — web page
agy -p "{summarize or extract}" --model gemini-3.7-flash-high
# T2 summarize / extract — one local file (input names a file → flags + read-only sentence)
agy -p "Read the file at {absolute_path} and {summarize}. Do not create or modify any files." \
  --model gemini-3.7-flash-high --dangerously-skip-permissions --sandbox
# T2 machine-consumed extraction (schema enforces shape, not completeness → pro-low)
agy -p "{extract fields}" --model gemini-3.1-pro-low --output-format json --json-schema '{...}'

# T3 research report
agy -p "{comparison / best-practices question}" --model gemini-3.1-pro-high

# T4 codebase analysis (reads repo files → headless flags required; CWD is the workspace)
agy -p "{question} Do not create or modify any files." \
  --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox --print-timeout 10m [--add-dir {path}]

# T4 multimodal (path-in-prompt; no stdin redirection; headless flags required)
agy -p "Read the file at {absolute_path} and {question} Do not create or modify any files." \
  --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox

# Scripted/CI calls (any tier; gate on .status == "SUCCESS")
agy -p "{question}" --model {slug} --output-format json --print-timeout 10m
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
- Pin the model per call with `--model {slug}` following the Model Policy
  above (list: `agy models`); unknown slugs fail loudly.
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
