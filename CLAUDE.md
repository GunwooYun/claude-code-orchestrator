# Claude Code Orchestrator

**멀티 에이전트 협업 프레임워크**

**Claude Code**가 **deep-reasoning 서브에이전트(Claude Fable, 심층 추론)**와 **Antigravity CLI(`agy`, Gemini 모델 기반 대규모 리서치)**를 오케스트레이션하여 각 에이전트의 강점을 극대화하고 **개발 속도와 품질을 동시에 끌어올리는 구조**다.

---

## 왜 이 구조가 필요한가?

| 에이전트 | 강점 | 사용 목적 |
|-------|----------|---------|
| **Claude Code (메인)** | 오케스트레이션, 사용자 대화 | 전체 통합, 태스크 관리, 의사결정|
| **deep-reasoning 서브에이전트 (Claude Fable)** | 깊은 추론, 설계 판단, 디버깅 | 설계 검토, 에러 분석, 트레이드오프 평가 (격리된 컨텍스트, 읽기 전용 — Edit/Write 도구 없음, Bash는 지시로 제한) |
| **Antigravity CLI (`agy`, Gemini 모델)** | 대규모 컨텍스트, 멀티모달, 웹 검색 | 대규모 코드 분석, 라이브러리 조사, PDF/이미지/영상 분석 |

**IMPORTANT**: 각 에이전트는 단독으로도 강력하지만, **의도적으로 역할을 분리했을 때 성능이 폭발**한다.

---

## 컨텍스트 관리 (CRITICAL)

Claude Code의 최대 컨텍스트는 **200k 토큰**이지만,
툴 정의 / 시스템 프롬프트 등을 제외하면 **실질적으로 70~100k 수준**이다.

**YOU MUST** 👉 그래서 **출력이 큰 작업은 반드시 서브 에이전트 경유**가 원칙이다.

### 출력 크기 기준

| 출력 크기  | 사용 방식           | 이유                     |
| ------ | --------------- | ---------------------- |
| 1~2문장  | 메인이 직접 처리        | 오버헤드 없음                |
| 10줄 이상 | **서브 에이전트 경유**  | 메인 컨텍스트 보호             |
| 분석 리포트 | 서브 에이전트 → 파일 저장 | `.claude/docs/`에 영구 보존 |

### 예시
```
# MUST: 설계 검토는 deep-reasoning 서브에이전트 (분석은 격리 컨텍스트에서, 요약만 반환)
Task(subagent_type="deep-reasoning", prompt="Review this design ... Return concise summary")

# MUST: 대규모 리서치는 general-purpose 서브에이전트 경유로 agy 호출 (출력 큼)
Task(subagent_type="general-purpose", prompt="Research X via agy, save to .claude/docs/research/, return a concise summary")

# OK: 짧은 agy 질문은 직접 호출 (아주 짧은 출력)
Bash("agy -p '한 문장으로 답변' --model gemini-3.7-flash-low")
```

---

## 빠른 사용 가이드(Quick Reference)

### deep-reasoning 서브에이전트를 써야 할 때

- 설계 판단
    - "어떤 패턴이 맞을까?"
    - "이 구조, 확장 가능할까?"
- 디버깅
    - "왜 이 에러가 나는지?"
- 비교/선택
    - "A vs B, 뭐가 나은지?"
- ➡ 깊은 사고가 필요하면 deep-reasoning (메인에서 `Task(subagent_type="deep-reasoning")` 호출)

→ 참고: `.claude/rules/deep-reasoning-delegation.md`

### Antigravity CLI(agy)를 써야 할 때

- 리서치
    - "이거 조사해줘"
    - "요즘 트렌드 뭐임?"
- 대규모 분석
    - "이 레포 전체 구조 설명해줘"
- 멀티모달
    - "이 PDF 요약"
    - "이 강의 영상 핵심만 정리"
- ➡ 많이 읽고, 넓게 볼 땐 agy

### 라우팅은 주제가 아니라 비용으로 (CRITICAL)

"리서치면 agy" 라는 주제 기준만으로는 부족하다. **토큰량 × 추론 난이도**로 정한다.

| | 추론 쉬움 | 추론 어려움 |
|---|---|---|
| **토큰 많음** | **agy** — 로그·CI 출력 요약, 레포 와이드 영향 분석, 파일 프리필터, 번역·보일러플레이트 | **agy 가 좁히고 Claude 가 판정** (2단계 퍼널) |
| **토큰 적음** | 메인이 직접 | deep-reasoning |

**위쪽 두 칸을 비워두면 그 일이 전부 Claude 로 흐른다** — 토큰 편중의 구조적 원인이다.

**큰 입력**(아래 기준)에서 deep-reasoning 앞에 agy 프리필터를 둔다. 단
**agy 는 `file:line` 과 사실만 반환하고 판정은 하지 않는다** — 요약을 반환하면
deep-reasoning 이 코드가 아니라 요약을 추론한다.

**판정은 넘기지 않는다.** agy 는 넓게 읽고 후보를 뽑고, Claude 가 무엇이 진짜인지
판정한다.

→ 참고: `.claude/rules/antigravity-delegation.md`

### 큰 변경의 기준 (한 곳에서 정의한다)

**파일 5개 또는 500줄.** 이것을 넘으면 크다. 크기와 무관하게 **보안 경계·공개
인터페이스 변경은 항상 크다.**

| 쓰는 곳 | 기준을 넘으면 | 넘지 않으면 |
|---|---|---|
| agy 프리필터 (2단계 퍼널) | agy 가 `file:line` 으로 좁히고 deep-reasoning 이 판정 | 프리필터 없이 deep-reasoning 에 바로 준다 — 왕복 비용이 절약분보다 크다 |
| `/lens-review` | 직교하는 렌즈 3개를 병렬로 | deep-reasoning 한 번 — 3배 비용에 얻는 것이 그만큼 늘지 않는다 |
| `/feature` Phase 6 | 위와 같다 | 위와 같다 |

**숫자는 여기서만 정한다.** 다른 파일이 숫자를 다시 적을 수는 있지만(스킬
description 은 본문 없이 읽힌다), 어긋나는 순간
`tests/test_template_consistency.py` 가 실패한다 — 실제로 프리필터 500 / 리뷰 300
으로 어긋나 있었고, 같은 `/feature` 안에서 15줄 거리였다.

---

## Workflow

### 두 커맨드의 관계 (순서가 있다)

| 커맨드 | 실행 시점 | 대상 | 하는 일 |
|---|---|---|---|
| `/initproject` | 템플릿을 복사한 직후 **프로젝트당 한 번** | **템플릿 자체** | 스택 감지, 모델 매트릭스 확인, rules·훅·권한을 이 프로젝트에 맞게 개조 |
| `/feature` | **작업 단위마다 반복** (티켓 하나 = 한 번) | **제품 코드** | 리서치 → 요구사항 → 설계 리뷰 → 태스크 → 구현 → 리뷰 |

`/initproject` 1회 → 그 다음부터 작업마다 `/feature`. 같은 기능을 수정하는
후속 티켓도 `/feature`를 다시 실행한다(입력이 달라 리서치·설계 리뷰의 방향이
"기존 구현을 어디까지 건드리나"로 바뀐다).

버그 수정·문구 변경·설정값 조정처럼 설계 판단이 없는 작업은 `/feature`를 쓰지
않고 바로 처리한다. 애매하면 `/feature`를 쓴다 — 설계 리뷰 단계에서 걸러진다.

```
/feature <기능명>
```

### 진행 순서

1. Antigravity CLI (agy)
    - 리포지토리 전체 분석 (서브 에이전트)
2. Claude 
    - 요구사항 정리
    - 개발 계획 수립
3. deep-reasoning 서브에이전트
    - 설계 리뷰 및 리스크 검토
4. Claude 
    - 실행 가능한 태스크 리스트 생성 (구현 태스크마다 `verify:` 태스크를 짝)
5. 사용자 승인
    - 코드를 쓰기 전 마지막 게이트. 계획이 바뀌면 4로 되돌아간다
6. Claude 
    - 승인된 계획과 검증 계획을 `## Current Project` 에 남긴다
7. 구현 루프
    - 태스크 → `verify:task` → 다음 태스크, 마지막에 설정된 가장 느린 티어
8. (권장)
    - **구현 완료 후 별도 세션에서 리뷰**

→ 관련 커맨드: `/initproject`(프로젝트당 1회), `/feature`(작업 단위마다), `/plan`, `/tdd` skills

---

## 검증 원칙 (CRITICAL)

**구현보다 검증이 중요하다.** 그래서 검증은 코드보다 먼저 정해진다.

- `/feature` Phase 2b 에서 **코드가 존재하기 전에** 검증 계획을 쓴다 —
  시나리오 / 명령 / 티어 / **실패해야 할 때 실패하는지**.
- 모든 구현 태스크는 `verify:` 태스크와 짝을 이룬다. 마지막은 이 프로젝트에
  설정된 가장 느린 티어 — 없는 티어를 todo 에 적지 않는다.
- **통과만 확인한 것은 검증이 아니다.** 성공 로그는 검증이 아니고, 새 테스트는
  한 번 깨뜨려 봐서 빨간불이 나는 것을 확인한다.
- **테스트를 통과시키려고 테스트를 고치지 않는다.** 시나리오가 틀렸으면 계획을
  고치고 무엇을 왜 바꿨는지 남긴다.
- 티어는 **소요 시간으로** 정한다 (`save` 초 / `task` ≤5분 / `unit` 10~60분 /
  `full` 무제한·CI 전용). 모르면 느린 쪽.
- 검증 명령은 발명하지 않는다 — 티어 단위는 `.claude/scripts/verify-<tier>`
  (계약: `.claude/scripts/README.md`), 더 좁은 범위는 아래 `공통 명령어`.

→ 참고: `.claude/rules/testing.md`

---

## 기술 스택(Tech Stack)

- **Python** 
- **uv** 
    - pip 직접 사용 ❌
    - 속도 + 재현성 우선
- **ruff** 
    - lint/format 통합
- **ty** 
    - type check
- **pytest**
    - 테스트 표준
- 공통 명령어
    ```
    poe lint
    poe test
    poe all
    ```

→ 참고: `.claude/rules/dev-environment.md`

---

## 문서구조(Documentation)

| 위치                             | 내용                    |
| ------------------------------ | --------------------- |
| `.claude/rules/`               | 코딩 / 보안 / 언어 규칙       |
| `.claude/docs/DESIGN.md`       | 설계 결정 기록              |
| `.claude/docs/research/`       | agy 조사 결과             |
| `.claude/logs/cli-tools.jsonl` | agy 입출력 로그            |
| `.agents/rules/AGENTS.md`      | agy용 프로젝트 컨텍스트     |

### `CLAUDE.md` 섹션의 수명 (CRITICAL)

스킬들이 `CLAUDE.md` 에 상태를 기록한다. **수명이 다른 상태를 한 헤딩에 두면
교체 규칙이 남의 상태를 지운다.** 그래서 수명이 헤딩을 결정한다.

| 섹션 | 수명 | 쓰는 쪽 | 갱신 방식 |
|---|---|---|---|
| `## Project Setup` | **프로젝트 영구** | `/initproject`(개요·규약), `/jira-setup`(`### Jira`), `/doc-write`(`### Confluence`) | **덧붙인다** — 자기 하위 섹션만 갱신하고 블록 전체를 교체하지 않는다 |
| `## Current Project` | **작업 단위** (티켓/기능 하나) | `/feature` Phase 5 | **교체한다** — 다음 작업이 이전 작업의 블록을 대체한다 |
| `## Session History` | **세션** | `/checkpointing` | **덮어쓴다** — 매번 재생성된다 |

**순서는 `## Project Setup` → `## Current Project` → `## Session History` 이고,
Session History 는 항상 마지막이다.** `/checkpointing` 이 그 섹션을 다음 헤딩까지
재생성하므로, 뒤에 놓인 것은 소실된다.

읽는 쪽(`/ticket` 의 Jira 설정, `/doc-write` 의 스페이스)은 `## Project Setup`
에서 찾는다. 거기에 없으면 **묻거나 멈춘다** — 추측하지 않는다.

---

## 운영 주의사항 (Operational Notes)

- **서브에이전트는 서브에이전트를 못 띄운다.** general-purpose 안에서 설계 판단이 필요해지면 결과만 보고하고, 메인이 `Task(subagent_type="deep-reasoning")`를 호출한다.
- **`/checkpointing`(기본 모드)은 `CLAUDE.md`와 `.agents/rules/AGENTS.md`의 Session History 섹션을 덮어쓴다.** 실행 전에 커밋해 두고, 리뷰 전용 세션에서는 실행하지 않는다. `## Project Setup` 과 `## Current Project` 블록은 Session History 섹션 **앞**에 둔다 (위 「`CLAUDE.md` 섹션의 수명」).
- **리뷰는 별도 세션에서.** 구현한 세션은 자기 코드에 편향되므로 `git worktree add --detach ../<project>-review main`으로 격리한 새 `claude` 세션에서 "리포트 파일만 작성, 다른 파일 수정 금지"로 리뷰를 받고, 원 세션에서 반영한다. 세션 안에서의 가벼운 리뷰는 deep-reasoning 서브에이전트로 충분하다.
- **훅 파일명을 바꾸면 `.claude/settings.json` 등록 경로를 같은 커밋에서 함께 바꾼다.** 어긋나면 PreToolUse 훅 오류로 모든 Edit이 막힌다.
- **agy 헤드리스 호출의 빈 응답은 실패다** (soft-deny, exit 0). stderr를 버리지 말고 `--output-format json`의 `.status`/`response`로 판단한다. 파일을 읽는 호출은 템플릿 패턴의 플래그와 "파일 수정 금지" 문구를 그대로 쓴다.
- **deep-reasoning의 읽기 전용은 도구 제거 + 지시**이지 커널 샌드박스가 아니다. 커밋 전 `git status`로 의도치 않은 변경을 확인한다.

---

## 언어 프로토콜(Language Protocol)

- **사고/코드/로그**: 영어
- **사용자대화/설명**: 한국어
