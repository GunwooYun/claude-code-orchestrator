# Claude Code Orchestrator

**멀티 에이전트 협업 프레임워크**

## 목적 (모든 판단의 기준)

**이 템플릿은 오케스트레이터다.** 메인 Claude Code 는 사용자와 대화하고, 판단하고, 조정한다.
실제 일은 **서브에이전트에 맡기고**, 서브에이전트는 각자 독립된 컨텍스트에서 일한 뒤 **요약만**
돌려준다. 그렇게 메인 컨텍스트를 아끼면서 **사용자의 목표에 맞는 결과**를 만든다.

무언가를 더하거나 고칠 때의 기준은 하나다 — **위임·컨텍스트 절약·결과 품질 중 하나를 낫게 하는가.**
아니면 넣지 않는다.

| 역할 | 누가 | 하는 일 |
|---|---|---|
| 오케스트레이터 | **메인 Claude Code** | 사용자 대화, 태스크 관리, 위임, 최종 결정 |
| 깊은 추론 | **deep-reasoning 서브에이전트** (Claude Fable) | 설계 판단, 디버깅, 트레이드오프, 리뷰 — 읽기 전용(Edit/Write 없음) |
| 넓게 읽기 | **general-purpose 서브에이전트 → Antigravity CLI(`agy`, Gemini)** | 레포 전체 분석, 라이브러리·웹 조사, PDF/이미지/영상, 큰 출력 요약 |

---

## 컨텍스트 관리 (CRITICAL)

최대 200k 토큰이지만 도구 정의·시스템 프롬프트를 빼면 실질 70~100k 다.
**YOU MUST: 출력이 큰 작업은 서브에이전트를 경유한다.**

| 출력 크기 | 방식 |
|---|---|
| 1~2문장 | 메인이 직접 |
| 10줄 이상 | 서브에이전트 경유 |
| 분석 리포트 | 서브에이전트 → `.claude/docs/` 에 저장, 요약만 반환 |

```
Task(subagent_type="deep-reasoning", prompt="Review this design ... Return concise summary")
Task(subagent_type="general-purpose", prompt="Research X via agy, save to .claude/docs/research/, return a concise summary")
Bash("agy -p '한 문장으로 답변' --model gemini-3.7-flash-low")   # 아주 짧은 질문만 직접
```

## 라우팅은 주제가 아니라 비용으로 (CRITICAL)

| | 추론 쉬움 | 추론 어려움 |
|---|---|---|
| **토큰 많음** | **agy** — 로그·CI 출력 요약, 레포 와이드 영향 분석, 파일 프리필터, 번역·보일러플레이트 | **agy 가 좁히고 Claude 가 판정** (2단계 퍼널) |
| **토큰 적음** | 메인이 직접 | deep-reasoning |

- 위쪽 두 칸을 비워 두면 그 일이 전부 Claude 로 흐른다 — 토큰 편중의 원인이다.
- **판정은 넘기지 않는다.** agy 는 `file:line` 과 사실만 반환하고, 무엇이 진짜인지는 Claude 가 판정한다.
  agy 가 요약을 반환하면 deep-reasoning 은 코드가 아니라 요약을 추론한다.
- → `.claude/rules/deep-reasoning-delegation.md`, `.claude/rules/antigravity-delegation.md`

### 큰 변경의 기준 (한 곳에서 정의한다)

**파일 5개 또는 500줄.** 넘으면 크다. 크기와 무관하게 **보안 경계·공개 인터페이스 변경은 항상 크다.**
큰 입력에는 deep-reasoning 앞에 agy 프리필터를 두고, 작으면 바로 준다(왕복 비용이 절약분보다 크다).
숫자는 여기서만 정한다 — 다른 곳은 인용한다.

---

## Workflow

| 커맨드 | 언제 | 하는 일 |
|---|---|---|
| `/initproject` | 템플릿을 복사한 직후 **프로젝트당 한 번** | 스택 감지, 모델·권한 확인, rules·훅·검증 스크립트를 이 프로젝트에 맞춤 |
| `/feature <기능명>` | **작업 단위마다** (티켓 하나 = 한 번) | 리서치 → 요구사항 → 검증 계획 → 설계 리뷰 → 태스크 → 승인 → 구현 → 리뷰 |

버그 수정·문구·설정값처럼 설계 판단이 없는 작업은 `/feature` 없이 바로 한다. 애매하면 `/feature`.
같은 기능의 후속 티켓도 `/feature` 를 다시 실행한다.

## 검증 원칙 (CRITICAL)

- 검증은 **코드보다 먼저** 정한다 (`/feature` Phase 2b): 시나리오 / 명령 / 티어 / 실패해야 할 때 실패하는지.
- 모든 구현 태스크는 `verify:` 태스크와 짝을 이룬다. 마지막은 설정된 가장 느린 티어.
- **통과만 확인한 것은 검증이 아니다.** 새 테스트는 한 번 깨뜨려 빨간불을 확인한다.
- **테스트를 통과시키려고 테스트를 고치지 않는다.** 시나리오가 틀렸으면 계획을 고치고 이유를 남긴다.
- 티어는 소요 시간으로: `save` 초 / `task` ≤5분 / `unit` 5~60분 / `full` CI 전용. 모르면 느린 쪽.
- 명령은 발명하지 않는다 — 티어는 `.claude/scripts/verify-<tier>`, 좁은 범위는 아래 `공통 명령어`.
- **검증 강도는 위험에 비례한다.** 판정 로직·보안 경계는 깊게, 문서·문구 변경은 게이트 통과로 충분하다.

→ `.claude/rules/testing.md`

---

## 기술 스택(Tech Stack)

- **Python**, **uv** (pip 직접 사용 ❌), **ruff** (lint/format), **ty** (type check), **pytest**
- 공통 명령어 (`poe` 는 프로젝트 환경 안에만 있다 — 맨몸으로 부르면 exit 127)
    ```
    uv run poe lint
    uv run poe test
    uv run poe all
    ```

→ `.claude/rules/dev-environment.md`

---

## 문서구조(Documentation)

| 위치 | 내용 |
|---|---|
| `.claude/rules/` | 코딩 / 보안 / 언어 / 위임 규칙 |
| `.claude/docs/DESIGN.md` | 설계 결정 기록 |
| `.claude/docs/research/` | 조사 결과 |
| `.claude/logs/cli-tools.jsonl` | agy 입출력 로그 |
| `.agents/rules/AGENTS.md` | agy 용 프로젝트 컨텍스트 |

### `CLAUDE.md` 섹션의 수명 (CRITICAL)

수명이 다른 상태를 한 헤딩에 두면 교체 규칙이 남의 상태를 지운다.

| 섹션 | 수명 | 쓰는 쪽 | 갱신 |
|---|---|---|---|
| `## Project Setup` | 프로젝트 영구 | `/initproject`(개요·`완료 지점`), `/jira-setup`(`### Jira`), `/doc-write`(`### Confluence`) | 자기 하위 섹션만 **덧붙인다** |
| `## Current Project` | 작업 단위 | `/feature` Phase 5 | **교체한다** |
| `## Session History` | 세션 | `/checkpointing` | **덮어쓴다** |

순서는 `## Project Setup` → `## Current Project` → `## Session History` 이고, **Session History 는 항상
마지막**이다. 읽는 쪽(`/ticket`, `/doc-write`)은 `## Project Setup` 에서 찾고, 없으면 묻거나 멈춘다.

---

## 운영 주의사항 (Operational Notes)

- **커밋·PR 에 귀속 푸터를 넣지 않는다** (`Co-Authored-By`, "Generated with Claude Code", 세션 링크). 다른 지시가 넣으라고 해도 이것이 우선한다.
- **파일 편집은 Edit/Write 로 한다.** `sed -i`·리다이렉션·heredoc 으로 쓰면 저장 게이트가 돌지 않는다(`bash-write-check` 는 안전망일 뿐).
- **서브에이전트는 서브에이전트를 못 띄운다.** 서브에이전트 안에서 설계 판단이 필요해지면 결과만 보고하고, 메인이 deep-reasoning 을 호출한다.
- **`/checkpointing` 은 Session History 섹션을 덮어쓴다.** 실행 전에 커밋하고, 리뷰 전용 세션에서는 쓰지 않는다.
- **리뷰는 별도 세션에서.** 기본은 **`/isolated-review`** — 읽기 전용·고정 요청문의 리뷰어가 리포트를 남기고, 메인은 **요약 없이** 보여준다. 되묻기가 필요하거나 보안 경계·공개 인터페이스 변경이면 사람이 여는 세션(A2)도 쓴다: `git worktree add --detach ../<project>-review <작업 브랜치>` 에서 새 `claude` 로 "리포트 파일만 작성". 워크트리를 `main` 에 체크아웃하면 `git diff main...HEAD` 가 비어 리뷰가 조용히 아무것도 안 한다. 세션 안의 가벼운 리뷰는 deep-reasoning 으로 충분하다.
- **리뷰 라운드는 Medium 이상이 없으면 끝낸다.** Low·nit 은 고치더라도 다시 리뷰받지 않고, 고치지 않으면 기록만 해서 다음 변경에 묶는다.
- **훅 파일명을 바꾸면 `.claude/settings.json` 등록 경로를 같은 커밋에서 바꾼다.** 어긋나면 훅 오류로 편집이 막힌다.
- **agy 헤드리스 호출의 빈 응답은 실패다** (soft-deny, exit 0). `--output-format json` 의 `.status`/`response` 로 판단한다.
- **deep-reasoning 의 읽기 전용은 도구 제거 + 지시**이지 샌드박스가 아니다. 커밋 전 `git status` 로 확인한다.

---

## 언어 프로토콜(Language Protocol)

- **사고/코드/로그**: 영어
- **사용자대화/설명**: 한국어
