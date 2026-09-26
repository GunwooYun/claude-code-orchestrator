---
name: feature
description: |
  Kick off ONE unit of work (a ticket, a feature, a structural change) with
  multi-agent collaboration: agy research -> requirements -> a verification plan
  written BEFORE any code -> deep-reasoning design and verification review ->
  paired implementation/verify tasks -> implementation loop -> review. Run it
  again for every new unit of work, including follow-up tickets on a feature it
  already built. Skip it for changes with no design decision (bug fixes,
  wording, config values).
metadata:
  short-description: Per-work-unit kickoff with multi-agent collaboration
---

# Feature Kickoff

**멀티 에이전트 협업으로 작업 단위 하나를 시작한다.**
작업(티켓) 하나당 한 번 실행하며, 같은 기능의 후속 수정 티켓에도 다시 실행한다.

## Overview

이 스킬은 Claude(오케스트레이션 + deep-reasoning 서브에이전트)와 Antigravity CLI(agy)를 협조시켜 작업 개시부터 구현 후 리뷰까지를 커버한다.

프로젝트 전체 설정은 이 스킬이 아니라 `/initproject`가 프로젝트당 한 번 수행한다.

## Workflow

```
Phase 1: Research (agy via Subagent)
    ↓
Phase 2: Requirements & Planning (Claude)
    ↓
Phase 2b: VERIFICATION PLAN (Claude)          ← 코드보다 먼저. 생략 불가
    ↓
Phase 3: Design + Verification Review (deep-reasoning Subagent)
    ↓
Phase 4: Task Creation (Claude)               ← 구현 태스크마다 verify 태스크 짝
    ↓
Phase 4b: User Confirmation (Claude ↔ 사용자)  ← 코드를 쓰기 전 마지막 게이트
    ↓
Phase 5: CLAUDE.md Update (Claude)            ← 승인된 계획을 세션 밖으로 남긴다
    ↓
Implementation Loop:  태스크 → verify:task → 다음 태스크
                      마지막에 설정된 가장 느린 티어
    ↓
Phase 6: Multi-Session Review (New Session + deep-reasoning)
```

**검증이 구현보다 먼저 정해진다.** Phase 2b 를 건너뛰면 Phase 4 의 태스크 짝을
만들 수 없고, Phase 6 이 대조할 기준이 없어진다.

**이 문서의 순서가 실행 순서다.** 위 도식의 단계마다 같은 이름의 섹션이 아래에 같은
순서로 있고, `tests/test_feature_workflow.py` 가 그 일치를 검사한다 — 예전에는
구현 루프에 섹션이 아예 없었고(코드를 쓰는 단계가 유일하게 지시 없는 단계였다),
사용자 승인이 구현 후 리뷰보다 뒤에 있었다.

---

## Phase 1: Antigravity Research (Background)

**Task tool에서 하위 에이전트를 시작하고 agy로 리포지토리 분석한다.**

**먼저 agy 를 쓸 수 있는지 한 번 확인한다** — 작업 단위당 한 번이면 충분하고,
결과를 이 작업 내내 재사용한다.

```sh
.claude/skills/antigravity-system/agy-probe
```

종료 코드 0(`READY`)이면 아래 A, 그 외면 B 로 간다. 상태와 그 의미는
`.claude/rules/antigravity-delegation.md` 의 "agy 가 없을 때"를 따른다.

### A. agy 가 READY 일 때

```
Task tool parameters:
- subagent_type: "general-purpose"
- run_in_background: true
- prompt: |
    Research for: {feature}

    1. Call Antigravity CLI (from the repository root):
       agy -p "Analyze this repository for: {feature}

       Provide:
       1. Repository structure and architecture
       2. Relevant existing code and patterns
       3. Library recommendations
       4. Technical considerations
       Do not create or modify any files; return everything in your response.
       " --model gemini-3.1-pro-high --dangerously-skip-permissions --sandbox --print-timeout 10m

    2. Save full output to: .claude/docs/research/{feature}.md

    3. Return CONCISE summary (5-7 bullet points)
```

### B. agy 를 쓸 수 없을 때 (MISSING / UNAUTHENTICATED / DEGRADED)

**리서치를 건너뛰지 않는다.** 같은 목적을 Claude 자신의 도구로 달성하되, 더
좁아진다는 사실을 문서와 사용자에게 남긴다.

```
Task tool parameters:
- subagent_type: "general-purpose"
- run_in_background: true
- prompt: |
    Research for: {feature}. agy is unavailable ({state}), so use your own tools.

    1. Repository: use Grep/Glob/Read to find the code this feature touches.
       This is TARGETED, not exhaustive — record which paths you actually read.

    2. External: use WebSearch/WebFetch only for what the repository cannot
       answer (library choice, breaking changes). Cite URLs.

    3. Save to .claude/docs/research/{feature}.md, and make the FIRST LINE:
       > 조사 도구: Claude (WebSearch/Grep) — agy 사용 불가 ({state}, {date}).
       > 레포 전수 조사가 아니며, 읽은 경로는 아래 "조사 범위"에 적혀 있다.

    4. Add a "조사 범위" section listing the paths read and the queries run.

    5. Return CONCISE summary (5-7 bullets) AND a "못 본 것" list — what a
       repository-wide sweep would have covered and this did not.
```

그리고 **사용자에게 한 번 알린다**: 어떤 상태인지, 무엇으로 대체했는지, 무엇이
불가능해졌는지(영상·음성 분석은 대체 불가). 매번 반복하지 않는다.

Phase 3 의 deep-reasoning 프롬프트에 **"리서치가 좁다"는 사실을 함께 넘긴다** —
설계 리뷰가 근거의 폭을 감안해서 판단해야 한다.

---

## Phase 2: Requirements Gathering (Claude)

**사용자에게 질문하여 요구 사항을 명확히 한다.**

**티켓에서 시작한 작업이면 `/ticket` 이 이미 일부를 채워 왔다.** 채워진 항목은 다시
묻지 않고 값을 보여주며 "이대로 맞습니까"만 확인한다. 티켓이 답하지 못한 것만 묻는다
— 특히 **성공기준은 티켓에 비어 있는 경우가 많고, Phase 2b 가 그것을 입력으로
받으므로 반드시 채운다.**

Ask in Korean:

1. **목적**: 무엇을 달성하고 싶습니까?
2. **스코프**: 포함하거나 제외하는 것은?
3. **기술적 요건**: 특정 라이브러리, 제약은?
4. **성공기준**: 완료의 판단기준은? — **어떻게 검증하면 그것이 충족됐다고
   말할 수 있습니까?** 이 답이 아래 검증 계획의 입력이 된다.

**Draft implementation plan based on agy research + user answers.**

### Phase 2b: 검증 계획 (MANDATORY — 코드보다 먼저 쓴다)

**이 프로젝트에서 검증은 구현보다 중요하다.** 그래서 "테스트를 할까?"를
"정해둔 것을 돌려라"로 바꿔 놓는다. 구현 계획과 같은 문서에, 코드가 존재하기
전에 아래를 쓴다.

명령은 발명하지 않는다. **티어 단위 명령은 `.claude/scripts/verify-<tier>` 다** —
이것이 프로젝트와의 계약이고, 그 안에 무엇이 들어 있는지는 이 스킬이 알 필요가
없다(`.claude/scripts/README.md`). 스크립트보다 좁은 범위로 돌려야 하면
`CLAUDE.md` 의 `공통 명령어` 를 본다.

해당 티어의 스크립트가 없으면 **그 티어는 이 프로젝트에 설정되지 않았다는
뜻이다.** 없는 것을 있는 척하지 말고, 사용자에게 무엇으로 검증할지 묻거나
`/initproject` 로 설정하라고 알린다.

```markdown
## 검증 계획

### 시나리오
| ID | 무엇을 검증하는가 | 어떻게 (명령) | 티어 | 실패해야 할 때 실패하는가 |
|----|------------------|---------------|------|---------------------------|
| V1 | {행동 하나} | `.claude/scripts/verify-task` | task | {음성 시험 방법} |
| V2 | ... | `.claude/scripts/verify-unit` | unit | ... |

### 이 작업에서 검증하지 않는 것
- {범위 밖인 것과 그 이유}

### 검증할 수 없는 것
- {수단이 없는 것, 왜 없는지, 사람이 무엇을 하면 되는지}
```

**규칙:**

- **시나리오는 행동 단위로 쓴다.** "models.py 를 테스트한다"가 아니라
  "만료된 토큰으로 요청하면 401 이 반환된다".
- **음성 시험 칸을 비우지 않는다.** 통과만 확인한 테스트는 검증이 아니다
  (`.claude/rules/writing-style.md` 의 정직성 규칙과 같은 원칙). 어떻게 하면
  이 테스트가 실패하는지 적지 못하면 그 시나리오는 아직 설계되지 않았다.
- **검증할 수 없는 것을 빈칸으로 두지 않는다.** 적어서 남긴다.
- **티어**는 `.claude/rules/testing.md` 의 "원칙 4" 가 정의한다 — 예산, 언제 도는가,
  누가 돌리는가. 여기 옮겨 적지 않는다(표를 두 벌 두면 갈라진다). **모르면 느린
  쪽으로 적는다.**

---

## Phase 3: Design Review (deep-reasoning Subagent, Background)

**Task tool에서 deep-reasoning 서브에이전트를 시작하고 계획을 검토한다.**

**입력이 크면 앞단에 agy 프리필터를 둔다** — 파일 5개 또는 500줄 이상이면 검토한다.
deep-reasoning 이 넓게 읽는 일을 하지 않게 하는 것이 목적이다. 단 **agy 는 `file:line`
과 사실만 반환하고 판정은 하지 않으며**, deep-reasoning 에게 "걸러진 입력을 받았다,
부족하면 직접 읽어라"를 프롬프트에 명시한다. 그 아래 크기에서는 왕복 비용이 절약분보다
크므로 바로 준다. 기준과 절대 규칙:
`.claude/rules/antigravity-delegation.md` → "라우팅은 주제가 아니라 비용으로 한다".

```
Task tool parameters:
- subagent_type: "deep-reasoning"
- run_in_background: true
- prompt: |
    Review this implementation plan for: {feature}

    Draft plan: {plan from Phase 2}

    Verification plan: {verification plan from Phase 2b}

    Analyze:
    1. Approach assessment
    2. Risk analysis
    3. Implementation order
    4. Improvements
    5. Verification adequacy — this matters most here:
       - Which behaviours in the plan NO scenario covers
       - Scenarios in the wrong tier (too slow for a per-task gate, or too
         shallow for what they claim to prove)
       - Scenarios whose "fails when it should" column is empty or wrong —
         a test that cannot fail proves nothing
       - Which tasks should be tagged risk:high (run the unit tier after them)

    Return CONCISE summary:
    - Top 3-5 recommendations
    - Key risks
    - Suggested order
    - Untested behaviours and the scenarios to add
```

리뷰가 "커버되지 않은 동작"을 지적하면 **Phase 4 로 넘어가기 전에 검증 계획을
고친다.** 지적을 태스크로 미루지 않는다 — 그러면 코드가 먼저 생기고 계획이
사후 정당화가 된다.

---

## Phase 4: Task Creation (Claude)

**서브에이전트 요약을 통합하고 작업 목록을 작성한다.**

**모든 구현 태스크는 검증 태스크와 짝을 이룬다.** 실행 루프가 실제로 보는 것은
todo 목록이므로, 여기에 없으면 검증은 일어나지 않는다.

태스크를 얼마나 크게 쪼갤지, 의존 순서를 어떻게 잡을지는
`references/task-patterns.md` 를 본다.

```python
# 구현 태스크
{
    "content": "Implement {specific feature}",
    "activeForm": "Implementing {specific feature}",
    "status": "pending"
}
# 그 즉시 뒤따르는 검증 태스크 — 시나리오 ID 와 명령을 그대로 적는다
{
    "content": "verify:task V1,V2 — .claude/scripts/verify-task",
    "activeForm": "Verifying V1,V2",
    "status": "pending"
}
```

**규칙:**

- 짝 없는 구현 태스크를 만들지 않는다. 검증할 게 없다고 판단되면 그 이유를
  검증 계획의 "검증하지 않는 것"에 적는다.
- **마지막 태스크는 이 프로젝트에 설정된 가장 느린 티어다** — 보통
  `verify:unit` 이지만, `.claude/scripts/verify-unit` 이 없으면 그 티어는 이
  프로젝트에 존재하지 않으므로 `verify:task` 가 마지막이 된다. 없는 티어를 todo 에
  적지 않는다. 느린 티어는 general-purpose 서브에이전트에 백그라운드로 넘기고
  10줄 이내 요약만 받는다 — 그동안 메인은 다른 todo 를 진행한다.
- `verify:full` 은 todo 에 넣지 않는다. CI 또는 사람의 몫이다. 대신
  "무엇을 CI 에서 돌려야 하는지"를 완료 보고에 남긴다.
- 루프가 도는 방식(실패했을 때, `risk:high`, 느린 티어 위임, 완료 보고)은
  아래 "Implementation Loop" 가 담는다 — 태스크를 **만드는** 일과 태스크를
  **도는** 일은 다른 단계다.

---

## Phase 4b: User Confirmation

Present final plan to user (in Korean):

```markdown
## 프로젝트 계획 : {feature}

### 조사 결과 (agy)
{Key findings - 3-5 bullet points}

### 설계 정책 (deep-reasoning 검토)
{Approach with refinements}

### 검증 계획
{시나리오 표 — ID / 무엇을 / 명령 / 티어 / 음성 시험}
{검증하지 않는 것}
{검증할 수 없는 것 — 있으면 반드시 노출한다}

### 작업 목록 ({N}개)
{Task list — 구현 태스크와 verify 태스크가 짝지어진 상태로}

### 위험과 주의사항
{From deep-reasoning analysis}

### 다음 단계
1. 이 계획으로 진행하시겠습니까?
2. 구현 완료 후 다른 세션에서 검토를 수행한다.

---
이 계획으로 진행하시겠습니까?
```

**승인 없이 코드를 쓰지 않는다.** 사용자가 계획을 바꾸면 **Phase 4 로 돌아가** 태스크
목록을 고치고 다시 제시한다. 설계 자체가 바뀌면 Phase 3 으로 돌아간다. 승인 전에
`CLAUDE.md` 를 쓰지 않는다 — 승인되지 않은 계획을 남기면 두 번 쓰게 된다.

---
## Phase 5: CLAUDE.md Update (IMPORTANT)

**프로젝트 관련 정보를 CLAUDE.md에 추가한다.**

Add to CLAUDE.md — **before** any existing `## Session History` section (that section is
rewritten by `/checkpointing`; anything placed after it is lost). Replace an existing
`## Current Project` block instead of appending a second one:

```markdown
---

## Current Project: {feature}

### Context
- Goal: {1-2 sentences}
- Key files: {list}
- Dependencies: {list}

### Decisions
- {Decision 1}: {rationale}
- {Decision 2}: {rationale}

### Notes
- {Important constraints or considerations}

### Verification plan
| ID | 무엇을 검증하는가 | 명령 | 티어 | 실패해야 할 때 실패하는가 |
|----|------------------|------|------|---------------------------|
| V1 | {행동} | {명령} | {티어} | {음성 시험} |
- 검증하지 않는 것: {...}
- 검증할 수 없는 것: {...}
```

**검증 계획을 여기 남기는 것이 Phase 6 의 전제다.** Option A 는 새 세션에서
"계획의 시나리오 ID 와 실제 테스트를 대조"하는데, 그 계획이 대화 안에만 있으면 새
세션은 읽을 곳이 없다. 표는 압축해도 되지만 **시나리오 ID 와 음성 시험 칸은
남긴다** — 그 두 칸이 대조의 근거다.

**This ensures context persists across sessions.**

**`## Project Setup` 블록은 건드리지 않는다.** 그 섹션은 `/initproject`·
`/jira-setup`·`/doc-write` 가 쓰는 **프로젝트 영구** 상태(스택 개요·규약, Jira
사이트·전이 이름·쓰기 정책, Confluence 스페이스)이고, 여기서 교체하는 것은
**작업 단위** 상태인 `## Current Project` 하나다. 두 섹션의 수명은 `CLAUDE.md` 의
「`CLAUDE.md` 섹션의 수명」에 정의돼 있다 — 섞으면 `/ticket` 이 정책을 못 찾는다.

---

## Implementation Loop (구현 루프)

**태스크 → `verify:task` → 다음 태스크.** Phase 4 가 만든 짝을 순서대로 돈다. 코드가
쓰이는 단계는 여기뿐이다.

### 검증이 실패했을 때

- **다음 구현 태스크로 넘어가지 않는다.** 실패한 검증은 정보다.
- 원인이 명확하지 않으면 `.claude/rules/deep-reasoning-delegation.md` 에 따라
  deep-reasoning 에 넘긴다.
- **테스트를 통과시키기 위해 테스트를 고치지 않는다.** 시나리오가 틀렸다고
  판단되면 검증 계획을 고치고, 무엇을 왜 바꿨는지 남긴다 — 조용히 고치지 않는다.
- 계획을 고쳤으면 `CLAUDE.md` 의 `### Verification plan` 도 같이 고친다. 두 벌이
  갈라지면 Phase 6 이 대조할 기준을 잃는다.

### `risk:high` 태스크 뒤

Phase 3 이 위험하다고 표시한 태스크가 끝나면, 그 자리에서 **느린 티어를 한 번 더
돈다**(`verify:unit` 이 설정돼 있으면 그것). 작업 끝까지 미루면 원인 범위가 그만큼
넓어진다.

### 느린 티어는 배경으로 넘긴다

마지막(또는 `risk:high` 뒤) 티어는 general-purpose 서브에이전트에 넘긴다. **그
서브에이전트는 이 스킬도 규칙 파일도 받는다고 보장되지 않으므로, 필요한 것은 Task
프롬프트에 직접 쓴다.**

```
Task tool parameters:
- subagent_type: "general-purpose"
- run_in_background: true
- prompt: |
    Run the project's verification tier and report.

    1. Run: .claude/scripts/verify-unit      (substitute the tier being run)
    2. The EXIT CODE is the verdict: 0 = pass, non-zero = fail.
       Output on exit 0 is informational (warnings, progress) — do NOT
       discard it and do NOT report "clean" when there is output.
    3. Do NOT modify any file. Do NOT fix a failing test. You are reporting,
       not repairing.
    4. Return AT MOST 10 lines: the exit code, which scenario IDs failed
       ({scenario IDs from the verification plan}), and the first real error.
       If it timed out or could not run, say that instead of guessing.
```

배경에서 도는 동안 메인은 **코드가 아닌 todo** 만 진행한다(완료 보고 준비 등).
다음 작업 단위를 시작하지 않는다 — 아직 이 단위의 판정이 나오지 않았다.

### 루프 중에 오는 리뷰 제안

`post-implementation-review.py` 훅이 파일 3개·100줄을 넘기면 "deep-reasoning 리뷰를
고려하라"를 끼워 넣는다. **그것은 Phase 6 Option B 이고, 루프 중에 시작하지
않는다.** 지금 돌고 있는 짝을 끝내고, Phase 6 에서 처리한다.

### 구현 중에 결정이 바뀌면

`CLAUDE.md` 의 `### Decisions` 를 **그때 바로** 고친다. 끝에 몰아서 쓰면 무엇을 왜
바꿨는지 잃는다.

### 루프의 끝 — 완료 보고

마지막 티어의 결과가 오면 보고한다. `/ticket` Step 5 가 이것을 그대로 쓴다.

- **무엇을 돌렸는가**: 티어와 명령, 그리고 결과(통과/실패)
- **시나리오별 결과**: 계획의 ID 마다 대응하는 테스트와 그 결과
- **검증하지 못한 것**: 계획의 "검증할 수 없는 것" 과 루프 중에 새로 생긴 것
- **CI 가 돌려야 하는 것**: `verify:full` 은 todo 에 넣지 않았으므로 여기 남긴다
- **성공 로그는 검증이 아니다.** 통과만 확인한 것을 "검증했다"고 쓰지 않는다.

---
## Phase 6: Multi-Session Review (Post-Implementation)

**구현 완료 후 다른 세션에서 리뷰를 실시한다.**

### Option A: New Claude Session

**워크트리는 작업 브랜치에 체크아웃한다.** `main` 에 체크아웃하면 그 안에서
`HEAD == main` 이므로 `git diff main...HEAD` 가 **아무것도 출력하지 않고**, 리뷰
세션은 "변경 없음"을 보고 조용히 끝난다.

1. `git worktree add --detach ../<project>-review <작업 브랜치>` 로 격리하고 그 안에서
   새 `claude` 세션을 띄운다 (`CLAUDE.md` 운영 주의사항과 같은 방식).
2. `git diff main...HEAD` 로 변경 전체를 본다 — **1번을 작업 브랜치로 했을 때만
   내용이 나온다.** 확인: `git rev-parse --short HEAD main` 의 두 값이 달라야 한다.
3. **"리포트 파일만 작성, 다른 파일 수정 금지"** 로 리뷰를 받고, 원 세션에서 반영한다.
4. `CLAUDE.md` `### Verification plan` 의 시나리오 ID 와 실제 테스트를 대조하게 한다.

**컨테이너·클라우드 세션이라 대화형 `claude` 를 띄울 수 없으면**, 작업 브랜치를 push
하고 그 브랜치를 상대로 **새 세션**을 만든다(새 클론 = 격리, 컨텍스트 공유 없음).
리포트는 별도 리뷰 브랜치로 받고 작업 브랜치에는 push 하지 않는다. 워크트리는 로컬
방식이고, 격리의 본질은 파일이 아니라 **컨텍스트**다.

### Option B: deep-reasoning Review (via Subagent)

변경이 크면(파일 5개 또는 500줄 이상, 또는 보안 경계·공개 인터페이스 —
기준: `CLAUDE.md` 「큰 변경의 기준」) Option B 대신
**`/lens-review`** 를 쓴다 — 직교하는 관점 3개를 병렬로 돌리고, **관점 간 충돌**을
드러낸다. 작은 변경에는 아래 단일 호출이 더 싸고 결과도 같다.

어느 쪽도 **Option A(별도 세션)를 대체하지 않는다.** 둘 다 이 세션이 프롬프트를
쓰므로 편향이 남는다.

```
Task tool parameters:
- subagent_type: "deep-reasoning"
- prompt: |
    Review the implementation for: {feature}

    Run `git diff main...HEAD` to see all changes.
    (If the diff is large — 5+ files or 500+ lines — the orchestrator may have
    run an agy pre-filter first and listed the locations to look at. That list
    is FILTERED, not exhaustive: read anything else you need directly.)

    Verification plan agreed before implementation:
    {verification plan from Phase 2b, scenario IDs included}

    Check:
    1. Code quality and patterns
    2. Potential bugs
    3. Missing edge cases
    4. Security concerns
    5. Verification adequacy — judge the tests, not just their presence:
       - Every scenario ID in the plan: is there a test for it, and does that
         test actually assert what the scenario claims?
       - Does any test pass for the wrong reason (asserts on output that would
         also appear on failure, mocks the thing under test, no negative case)?
       - Behaviour in the diff that no scenario covers
       - Scenarios quietly dropped or weakened during implementation

    Return findings and recommendations.
```

**여기서 "테스트가 있다"와 "테스트가 검증한다"를 구분한다.** 전자는 기계가 볼 수
있고, 후자는 사람이나 리뷰어만 판단할 수 있다. 이 프로젝트에서 자동으로 강제할
수 없는 유일한 항목이므로, 이 단계를 생략하면 검증 체계에 구멍이 남는다.

### Why Multi-Session Review?

- **Fresh perspective**: New session has no bias from implementation
- **Neutral judgement on its own tests**: the session that wrote a test is the
  worst judge of whether it proves anything
- **Different context**: Can focus purely on review, not implementation details
- **Isolated context**: Deep analysis without context pollution

---

## Output Files

| File | Purpose |
|------|---------|
| `.claude/docs/research/{feature}.md` | agy research output (또는 대체 경로로 만든 조사 기록) |
| `CLAUDE.md` → `## Current Project` | 승인된 계획 + `### Verification plan` (Phase 6 이 대조하는 근거) |
| Task list (internal) | 구현/verify 짝의 진행 상황 |
| 완료 보고 (대화) | 무엇을 돌렸는지·시나리오별 결과·CI 몫 — `/ticket` Step 5 가 그대로 쓴다 |

---

## Tips

- **All deep-reasoning/agy work through subagents** to preserve main context
- **Update CLAUDE.md** to persist context across sessions
- **Use multi-session review** for better quality assurance
- **Ctrl+T**: Toggle task list visibility
