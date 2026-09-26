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

## 라우팅은 주제가 아니라 비용으로 한다 (CRITICAL)

아래 "When to Consult agy" 는 **주제**로 분류한다 — "리서치면 agy". 그것만으로는
부족하다. 실제로 비용을 결정하는 축은 **토큰량 × 추론 난이도** 두 개다.

```
                 추론 쉬움                    추론 어려움
            ┌──────────────────────┬──────────────────────────────┐
토큰 많음    │  agy                 │  agy 가 좁히고 Claude 가 판정 │
            │  (아래 A)             │  (2단계 퍼널 — 아래 B)        │
            ├──────────────────────┼──────────────────────────────┤
토큰 적음    │  메인이 직접          │  deep-reasoning              │
            └──────────────────────┴──────────────────────────────┘
```

**위쪽 두 칸이 비어 있으면 그 일이 전부 Claude 로 흐른다.** 주제 기준만 쓰면
"리서치"라는 이름이 붙지 않은 토큰 과다 작업이 다 메인이나 deep-reasoning 으로
간다. 그것이 토큰 편중의 구조적 원인이다.

### A. 토큰 많음 + 추론 쉬움 → agy

주제가 "리서치"가 아니어도 agy 로 보낸다.

| 작업 | 왜 agy 인가 |
|---|---|
| 거대한 로그·스택트레이스·CI 출력 1차 요약 | 수천 줄을 읽는 일이고 판단은 없다. "실패 지점과 각 원인 후보"만 뽑아오면 된다 |
| 레포 와이드 영향 분석 | "이 함수 쓰는 곳 전부와 각 사용처의 형태". grep→Read 반복이 Claude 컨텍스트를 태운다 |
| 파일 프리필터 | 800줄에서 관련 60줄만. 읽는 일이고 고르는 기준은 명확하다 |
| 번역·포맷 변환·보일러플레이트 | 토큰은 많고 판단은 없다 |
| 세션 로그 요약 | `/checkpointing` 이 하는 집계도 여기 해당한다 |

### B. 토큰 많음 + 추론 어려움 → 2단계 퍼널 (가장 큰 레버)

**agy 가 좁히고, Claude 가 판정한다.** 지금은 deep-reasoning 이 자기 컨텍스트에서
파일을 직접 다 읽는다 — 가장 비싼 모델이 가장 토큰 많이 쓰는 일(넓게 읽기)을 한다.

```
큰 입력 ──> agy: 검토할 지점을 file:line 으로 나열 ──> deep-reasoning: 그 지점만 판정
```

적용 대상: 큰 diff 리뷰, 대규모 리팩터링 계획, 넓은 코드베이스에서의 원인 추적.

#### 퍼널의 절대 규칙

- **agy 는 위치와 사실만 반환한다. 판정은 반환하지 않는다.**
  `file:line + 무엇이 있는지` 는 OK. `이게 버그다 / 이 설계가 맞다` 는 금지.
  agy 가 요약하면 deep-reasoning 은 **코드가 아니라 요약을 추론한다** — 그러면
  퍼널이 품질을 깎는 장치가 된다.
- **재현율(recall) 우선으로 프롬프트한다.** "확실하지 않으면 포함하라"를 명시한다.
  프리필터가 중요한 곳을 빠뜨리면 deep-reasoning 은 그것을 영원히 못 본다.
- **deep-reasoning 에게 "걸러진 입력을 받았다"고 알린다.** 그리고 더 필요하면
  직접 읽으라고 말한다. 전수라고 착각하면 없는 것을 없다고 결론낸다.
- **작은 입력에는 퍼널을 쓰지 않는다.** 왕복 비용이 절약분보다 크다. 기준:
  입력이 **파일 5개 또는 500줄 미만이면 퍼널 없이** deep-reasoning 에 바로 준다.
- **agy 를 쓸 수 없으면 퍼널을 생략하고 deep-reasoning 이 직접 읽는다.** 이것이
  기존 동작이므로 degrade 는 매끄럽다. 다만 토큰이 늘어난다는 사실은 알린다
  (위 "agy 가 없을 때" 참조).

### 여전히 agy 로 보내지 않는 것

비용 축이 생겼어도 **판단은 넘기지 않는다.**

- "이 코드가 안전한가", "이 설계가 맞나", "A vs B 중 무엇인가" → deep-reasoning
- 구현 결정, 트레이드오프 판정 → deep-reasoning
- 사용자와의 대화, 최종 결정 → 메인

**agy 는 넓게 읽고 후보를 뽑는다. Claude 는 무엇이 진짜인지 판정한다.** 이 분리가
이 구조의 안전장치다. 넓게 읽는 일을 비싼 모델이 하지 않게 하는 것이 목적이고,
판정을 싼 모델에 넘기는 것이 목적이 아니다.

### 측정할 수 있는 것과 없는 것

`.claude/logs/cli-tools.jsonl` 로 확인한다.

```sh
jq -r '.model' .claude/logs/cli-tools.jsonl | sort | uniq -c | sort -rn
jq -r '[.timestamp[:10], .model] | @tsv' .claude/logs/cli-tools.jsonl | sort | uniq -c
```

- **측정된다**: agy 호출 수, 티어 분포(T1/T2 가 다수여야 한다), 날짜별 추이.
  재배치가 실제로 일어났다면 **호출 수가 늘고 T1/T2 비중이 높아야** 한다.
- **측정되지 않는다**: `log-cli-tools.py` 는 `"tool": "antigravity"` 만 기록한다.
  **agy 로 갔어야 하는데 Claude 가 한 일은 로그에 없다.** 그래서 이 지표는
  "재배치가 일어났다"의 약한 증거일 뿐이고, 반증은 못 한다. 그 사실을 알고 본다.

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
