# claude-code-orchestrator

![Claude Code Orchestrator](./summary.png)

Multi-Agent AI Development Environment

```
Claude Code (Orchestrator) ─┬─ deep-reasoning Subagent (Claude Fable, 심층 추론)
                            ├─ Antigravity CLI / agy (Research, Gemini 모델)
                            └─ Subagents (Parallel Tasks)
```

## Quick Start

기존 프로젝트의 루트로 실행:

```bash
git clone --depth 1 https://github.com/GunwooYun/claude-code-orchestrator.git .starter && cp -r .starter/.claude .starter/.agents .starter/CLAUDE.md . && rm -rf .starter && claude
```

## Prerequisites

### Claude Code

```bash
# 네이티브 인스톨러 (npm 불필요)
curl -fsSL https://claude.ai/install.sh | bash
claude   # 최초 실행 시 로그인
```

### Antigravity CLI (agy)

Gemini CLI의 후속 도구. npm 불필요.

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
agy          # 최초 실행 시 Google 로그인 (인증은 ~/.gemini/ 에 전역 저장)
agy models   # 사용 가능한 모델 슬러그 확인
```

> 참고: 헤드리스(`agy -p`) 호출에서 파일 읽기는 기본 거부(soft-deny: 조용히 건너뛰고 exit 0)되기 때문에,
> 이 템플릿은 파일을 읽어야 하는 패턴(코드베이스 분석·멀티모달)에 `--dangerously-skip-permissions --sandbox`를
> 붙여 **추가 설정 없이** 동작하도록 되어 있다. 이 플래그는 해당 호출 동안 agy의 파일 쓰기·MCP 도구도 자동 승인하므로,
> 템플릿의 모든 해당 프롬프트는 "파일을 만들거나 수정하지 말고 응답으로만 반환"을 명시하고 `.agents/rules/AGENTS.md`도
> agy를 읽기 전용으로 묶는다. 더 엄격하게 쓰고 싶다면 (선택) `~/.gemini/antigravity-cli/settings.json`에
> `{ "permissions": { "allow": ["read_file(*)"] } }`를 넣고 플래그를 빼면 된다.
>
> 이미 루트에 `AGENTS.md`(Codex/Cursor 등 용)가 있는 프로젝트에서는 agy가 그 파일과 `.agents/rules/AGENTS.md`를 함께 로드한다.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│           Claude Code (Orchestrator)                        │
│           → 컨텍스트 절약이 최우선                         │
│           → 사용자 대화/조정/실행 담당                   │
│                      ↓                                      │
│  ┌───────────────────────────┐  ┌────────────────────────┐  │
│  │  deep-reasoning Subagent  │  │  Subagent              │  │
│  │  (Claude Fable)           │  │  (general-purpose)     │  │
│  │  → 독립된 컨텍스트         │  │  → 독립된 컨텍스트      │  │
│  │  → 설계/추론/디버깅        │  │  → agy 호출 가능       │  │
│  │  → 읽기 전용, 권고만 반환   │  │  → 결과 요약 후 반환    │  │
│  └───────────────────────────┘  │                        │  │
│                                 │   ┌──────────────┐     │  │
│                                 │   │  agy         │     │  │
│                                 │   │  리서치       │     │  │
│                                 │   │  멀티모달     │     │  │
│                                 │   └──────────────┘     │  │
│                                 └────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 컨텍스트 관리 (핵심)

메인 오케스트레이터(Claude)의 컨텍스트를 아끼기 위해 **출력이 큰 작업은 반드시 서브에이전트를 경유**한다.

| 상황 | 권장 방식 |
|------|----------|
| 출력이 클 것으로 예상 | 서브에이전트 경유 |
| 짧은 질문·짧은 답변 | 직접 호출 가능 |
| 설계/디버깅 상담 | deep-reasoning 서브에이전트 |
| agy 리서치 | general-purpose 서브에이전트 경유 |
| 상세 분석 필요 | 서브에이전트 → 파일 저장 |

## 디렉터리 구조(Directory Structure)

```
.
├── CLAUDE.md # 메인 시스템 문서
├── README.md
├── pyproject.toml # Python 프로젝트 설정
├── uv.lock # 의존성 잠금 파일
├── tests/ # 훅 단위 테스트 (python3 -m unittest)
│
├── .claude/
│   ├── agents/
│   │   ├── deep-reasoning.md    # 심층 추론 서브에이전트 (Claude Fable)
│   │   └── general-purpose.md   # 범용 서브에이전트 (agy 호출)
│   │
│   ├── scripts/                 # 검증 계약 (프로젝트가 소유, /initproject가 작성)
│   │   ├── README.md            # 계약 전문 — 네 이름과 종료 코드
│   │   └── verify-{save,task,unit,full}
│   │
│   ├── skills/                  # 재사용 가능한 워크플로우
│   │   ├── initproject/         # 첫 세션 설정 (프로젝트당 1회)
│   │   ├── doc-write/           # 문서 작성 (자동 발동)
│   │   ├── jira-setup/          # Jira 연결 (프로젝트당 1회)
│   │   ├── ticket/              # 티켓에서 작업 시작 (자동 발동)
│   │   ├── lens-review/         # 다관점 병렬 리뷰 (자동 발동)
│   │   ├── feature/             # 작업 단위 킥오프 (티켓마다)
│   │   ├── plan/                # 구현 계획
│   │   ├── tdd/                 # 테스트 주도 개발
│   │   ├── checkpointing/       # 세션 영속화
│   │   ├── deep-reasoning/      # 심층 추론 서브에이전트 연동
│   │   ├── antigravity-system/  # Antigravity CLI (agy) 연동
│   │   └── ...
│   │
│   ├── hooks/                   # 자동화 훅
│   │   ├── agent-router.py      # 에이전트 라우팅
│   │   ├── lint-on-save.py      # 저장 시 verify-save 호출 (도구 이름 모름)
│   │   └── ...
│   │
│   ├── rules/                   # 개발 규칙
│   │   ├── coding-principles.md
│   │   ├── testing.md
│   │   └── ...
│   │
│   ├── docs/
│   │   ├── DESIGN.md            # 설계 결정 기록
│   │   ├── research/            # agy 조사 결과
│   │   └── libraries/           # 라이브러리 제약
│   │
│   └── logs/
│       └── cli-tools.jsonl      # agy 입출력 로그
│
└── .agents/                     # Antigravity CLI (agy) 워크스페이스 설정
    ├── rules/AGENTS.md          # agy용 프로젝트 컨텍스트
    └── skills/context-loader/   # agy 워크스페이스 스킬
```

## Skills

**먼저 읽을 것 — `/initproject`와 `/feature`의 관계.** 둘 다 쓰며, 순서가 있다.
`/initproject`는 템플릿을 복사한 직후 **프로젝트당 한 번** 실행해서 **템플릿 자체를**
이 프로젝트에 맞게 고친다. `/feature`는 **작업 단위마다 반복** 실행해서 **제품 코드를**
만든다. 즉 `/initproject` 1회 → 이후 티켓마다 `/feature`. 설계 판단이 없는 작업
(버그 수정, 문구 변경, 설정값 조정)은 `/feature` 없이 바로 처리한다.

### `/feature` — 작업 단위 킥오프 (티켓마다 반복)

멀티에이전트 협업으로 **작업 단위 하나**를 킥오프한다. 티켓 하나당 한 번 실행하고,
같은 기능의 후속 수정 티켓에도 다시 실행한다.

```
/feature 사용자 인증 기능
```

**워크플로우:**
1. **agy** → 리포지토리 분석·사전 조사
2. **Claude** → 요구사항 정리·계획 수립
2b. **Claude** → **검증 계획 (코드보다 먼저, 생략 불가)** — 시나리오 / 명령 / 티어 /
    실패해야 할 때 실패하는지
3. **deep-reasoning** → 계획 리뷰·리스크 분석 + **검증 충분성** (어떤 동작이
   시나리오로 덮이지 않았는지)
4. **Claude** → 실행 태스크 목록 생성 — **구현 태스크마다 `verify:` 태스크를 짝**
5. 구현 루프: 태스크 → `verify:task` → 다음 태스크, 마지막에 `verify:unit`
6. **별도 세션 리뷰** → 계획의 시나리오 ID 와 실제 테스트를 대조

검증 티어는 **소요 시간**으로 정한다 — `save`(초) / `task`(≤5분) /
`unit`(10~60분) / `full`(무제한, CI 전용). `unit`/`e2e` 같은 말은 스택마다 뜻이
달라 판단 기준이 못 된다. 자세한 원칙은 `.claude/rules/testing.md`.

### `/plan` — 구현 계획 수립

요구사항을 실제 구현 단계로 분해한다.

```
/plan API 엔드포인트 추가
```

**출력:**
- 구현 단계(파일, 변경 내용, 검증 방법)
- 의존성 및 위험
- 검증 기준

### `/tdd` — 테스트 주도 개발

Red → Green → Refactor 사이클을 강제한다.

```
/tdd 사용자 등록 기능
```

**워크플로우:**
1. 테스트 케이스 설계
2. 실패한 테스트 작성(Red)
3. 최소한의 구현(Green)
4. 리팩토링(Refactor)

### `/checkpointing` — 세션 저장

대화·결정·코드 흐름을 재사용 가능하게 보존한다.

```bash
/checkpointing                    # 기본: agy 상담 로그를 CLAUDE.md / .agents/rules/AGENTS.md 의 Session History 에 기록
/checkpointing --full             # 전체 : git 이력 및 파일 변경 포함 → .claude/checkpoints/
/checkpointing --full --analyze   # 분석 : 재사용 가능한 기술 패턴(스킬 후보) 발견
```

> 주의: 기본 모드는 `CLAUDE.md`와 `.agents/rules/AGENTS.md`를 **직접 수정**한다(Session History 섹션 덮어쓰기). 리뷰 전용 세션에서는 실행하지 않는다.

### `/deep-reasoning` — 심층 추론 서브에이전트 연동

설계 판단, 디버깅, 트레이드오프 분석 전용. Claude Fable이 격리된 컨텍스트에서 분석하고 간결한 권고만 반환한다.
같은 이름이 두 곳에 있다: `/deep-reasoning` **스킬**은 "언제·어떻게 상담할지"의 가이드이고, `deep-reasoning` **에이전트**(`.claude/agents/`)가 `Task(subagent_type="deep-reasoning")`의 실제 대상이다.
읽기 전용은 Edit/Write 도구를 제거하고 Bash 사용을 지시로 제한한 것이며, 커널 수준 샌드박스는 아니다.

**트리거 예시:**
- "어떻게 설계해야 하는가?" "어떻게 구현할까?"
- "왜 안 돌아가지?" "오류가 나온다"
- "어느 쪽이 좋다?" "비교해"

### `/antigravity-system` — Antigravity CLI (agy) 연동

리서치, 대규모 분석, 멀티모달 처리 전용. Gemini 모델의 대규모 컨텍스트와 Google 검색 그라운딩을 활용한다.

**트리거 예:**
- "조사해" "리서치해"
- "이 PDF/동영상 보기"
- "코드베이스 전체 이해"

### `/simplify` — 코드 리팩토링

코드를 간결화·가독성 향상시킵니다.

### `/design-tracker` — 설계 결정 추적

아키텍처 및 구현 결정을 `.claude/docs/DESIGN.md`에 자동으로 기록합니다. `/update-design`은 같은 파일을 수동으로 강제 갱신한다.

### `/doc-write` — 문서 작성 (자동 발동, 타이핑 불필요)

Confluence 페이지, Jira 티켓 본문, 저장소 준거 문서, 구현 계획서를 **사용자가 정의한
스타일 규칙으로** 쓴다. `description` 에 발동 경계가 박혀 있어 **이름을 칠 필요가
없다** — "문서로 정리해줘" 같은 요청에 스스로 발동한다.

```
발동함     Confluence 링크 + 작성 요청 / "보고서 써줘" / 티켓 본문 / 저장소 준거 문서
발동 안 함  "설명해줘", "분석해줘", "요약해줘" → 채팅 답변 / 코드 주석 / 커밋 메시지
애매하면    채팅으로 답하고 "문서로 만들까요?" 한 줄
```

역할 분리: **규칙은 `.claude/docs/writing-style.md`(무엇을 지키는가), 절차는 이
스킬(어떻게 하는가).** 스킬은 규칙을 복사하지 않고 가리킨다 — 테스트가 전사를
금지한다.

발행 정책은 비대칭이다. **새 페이지는 발행하고 링크와 함께 보고**하지만,
**기존 페이지는 반드시 먼저 확인받는다**(다른 사람이 읽고 있을 수 있다).
스페이스·부모 페이지가 정해지지 않았으면 **묻고**, 답을 `CLAUDE.md` 의
`## Current Project` 에 기록해서 다음부터 묻지 않는다 — 템플릿에 박지 않는다.

### `/jira-setup`, `/ticket` — Jira 연동

`/jira-setup` 은 **프로젝트당 한 번** 실행해서 연결 상태를 판별하고 사이트·프로젝트
키·프로젝트 style·전이 이름·쓰기 정책을 `CLAUDE.md` 의 `## Current Project` 에
기록한다. 수동 전용이다 — 기록을 실수로 덮으면 안 된다.

`/ticket` 은 **자동 발동**한다. `ABC-123` 이나 Jira 링크를 주면서 작업을 요청하면
티켓을 읽고 → 작업 크기를 판정해 `/feature` 또는 직접 작업으로 보내고 → 구현 후
코멘트와 상태 전이로 닫는다.

실제 커넥터로 측정해서 설계가 바뀐 지점들:

| 측정 | 설계 결과 |
|---|---|
| 한 조직에 프로젝트 **141개** | 목록을 나열하지 않고 **키를 묻는다** |
| `classic`(company-managed)과 `next-gen`(team-managed) 혼재 | style 을 기록하고 **전이 이름을 조회한다 — 추측하지 않는다** |
| 같은 사이트가 스코프 그룹별로 **중복 등장** (Confluence 용 / Jira 용) | 사이트를 유일하다고 가정하지 않고, **Confluence 접근이 Jira 접근을 뜻하지 않음**을 구분 |

쓰기 정책은 문서 정책과 같은 논리다 — **덧붙이는 것은 보고, 덮는 것은 먼저 확인.**
코멘트는 초안을 보여주고 승인 후, **상태 전이와 설명 수정은 항상 확인**한다(공유
상태이고 남이 쓴 것일 수 있다). 자격증명은 기록하지 않는다 — 인증은 커넥터가 관리하고
**로그인은 대신 할 수 없다**.

### `/lens-review` — 다관점 병렬 리뷰 (자동 발동)

같은 변경을 **직교하는 관점 3개로 병렬 검토**하고 취합한다. 기본 렌즈는
`correctness`(주장한 동작을 하는가) / `design`(구조가 유지되는가) /
`robustness`(적대적 입력·실패 모드). 변경 성격에 따라 하나를 교체한다 — 테스트가
빈약하면 `design` → 검증 충분성, 순수 리팩터링이면 `correctness` → 동작 보존.

**가장 큰 가치는 발견 목록이 아니라 관점 간 충돌이다.** correctness 가 "여기 가드를
추가하라"고 하는데 design 이 "이 함수는 존재하지 않아야 한다"고 하면, 그것이 진짜
설계 결정 지점이다. 취합 단계는 **충돌을 임의로 판정하지 않고** 양쪽 근거와
무엇을 잃는지를 나란히 제시한다.

```
큰 변경 ──> agy 프리필터 (한 번, 모든 렌즈에 같은 목록)
              ├─> correctness  ─┐
              ├─> design       ─┼─> 취합: 중복 제거 → 충돌 노출 → 심각도 정렬
              └─> robustness   ─┘
```

비용은 렌즈 수에 선형이라 **3개를 권한다** — 4개 이상에서는 새 발견보다 중복이
빠르게 늘어난다. **작은 변경에는 쓰지 않는다**: deep-reasoning 한 번이 더 싸고
결과도 같다. 발견의 적대적 재검증은 조건부다(자동 수정에 쓸 때, 또는 렌즈가 신뢰도를
낮게 표시했을 때).

**별도 세션 리뷰를 대체하지 않는다.** 렌즈는 격리된 컨텍스트에서 돌지만
**프롬프트를 이 세션이 쓰므로 프레이밍 편향이 남는다.** 최종 리뷰는 여전히
`git worktree` 로 격리한 새 세션이 담당한다 — 이 스킬은 그 전에 명백한 것들을
걷어내 최종 리뷰가 어려운 것에 집중하게 한다.

### `/research-lib`, `/update-lib-docs` — 라이브러리 제약 문서

`/research-lib <lib>`는 라이브러리 조사 결과를 `.claude/docs/libraries/<lib>.md`에 저장하고, `/update-lib-docs`는 기존 문서를 최신화한다. deep-reasoning 코드 리뷰와 agy 리서치가 이 문서를 제약 조건으로 참조한다.

### `/initproject` — 첫 세션 설정 (프로젝트당 1회)

템플릿을 복사한 직후 실행한다. 스택을 감지하고 → 커밋 정책·린트 훅 처리·프로젝트 개요를 한 번에 물은 뒤 → `CLAUDE.md` 기술 스택/`## Current Project`를 채우고 → `.claude/scripts/`의 검증 스크립트 4개를 이 프로젝트의 실제 명령으로 작성하고(계약), 템플릿 자신의 도구가 드러난 산문(`rules/dev-environment.md` 등)을 맞추고 → `.agents/rules/AGENTS.md`에 프로젝트 단락, `docs/DESIGN.md`에 아키텍처 시드를 쓰고 → 스모크 테스트 후 보고한다. 설치·커밋 정책 변경은 반드시 먼저 묻는다.

## 검증 계약 — 어떤 스택에도 붙는 방법

오케스트레이터는 프로젝트의 언어·도구·실행 위치를 **알지 못한다.** 대신
`.claude/scripts/` 의 네 실행 파일을 호출하고 종료 코드를 읽는다.

```
verify-save <path>   초        파일 저장 시 (훅)
verify-task          ≤5분      태스크마다 (게이트)
verify-unit          10~60분   작업 단위당 한 번
verify-full          무제한    CI 또는 사람만
```

네 티어를 다 가질 필요는 없다. **이 저장소는 `save` 와 `task` 만 가진다** — 전체
테스트가 3초에 끝나므로 더 느린 티어가 정직하게 존재하지 않는다. 있는 척하는
스크립트(항상 0을 반환하는 것)는 검사하지 않은 성공을 보고하므로 없는 것보다
나쁘다. 템플릿 자신이 이 규칙을 지킨다.

`0` 은 통과(출력 없음), `0 이외` 는 실패(이유 출력). **파일이 없으면 그 티어가
설정되지 않았다는 뜻**이고, 호출자는 그 사실을 그대로 알린다 — 통과로 치지 않는다.

언어·컨테이너·원격 장비·경로 변환·환경 준비는 **전부 스크립트 안에** 있다.
그래서 사람이 손으로 재현할 수 있다.

```bash
.claude/scripts/verify-save path/to/file   # 저장 시점과 똑같이
.claude/scripts/verify-task; echo $?       # 게이트를 그대로
```

`/initproject` 가 프로젝트당 한 번 작성한다. 스택별 레시피는 없다 — 티어마다
네 가지만 묻는다: **실패할 수 있는 명령은 무엇인가 / 어디서 도는가 / 얼마나
걸리는가 / 어떻게 빨간불이 나는가.** 정직하게 답할 수 없는 티어는 스크립트를
만들지 않는다.

이 저장소의 `verify-*` 는 **이 저장소 자신의 구현**(Python + uv)이며 다른
프로젝트의 참고 답안이 아니다. `tests/test_verify_scripts.py` 는 언어를 가정하지
않고 계약만 검사하므로 그대로 복사해 쓸 수 있다.

→ 계약 전문: `.claude/scripts/README.md`

## 실전 활용 가이드 — 120% 뽑아내기

이 템플릿의 가치는 "세 에이전트를 의도적으로 분리해서 쓰는 습관"에서 나온다. 아래는 실제 적용·운영하면서 검증한 사용법이다.

### 1. 적용 절차 (프로젝트당 1회)

복사 자체는 세 경로면 끝이다. 시간이 드는 건 그 뒤의 **프로젝트 맞춤화**이고, 이건 대부분 첫 세션의 오케스트레이터에게 시킬 수 있다.

**Step A — 복사 (1분)**

```bash
cd <your-project>
git clone --depth 1 https://github.com/GunwooYun/claude-code-orchestrator.git .starter \
  && cp -r .starter/.claude .starter/.agents .starter/CLAUDE.md . && rm -rf .starter
```

> 이미 쓰고 있던 다른 프로젝트의 사본에서 복사할 때는 런타임 파일을 빼고 가져온다:
> `rsync -a --exclude logs/ --exclude checkpoints/ --exclude __pycache__/ --exclude settings.local.json <src>/.claude/ ./.claude/`
> (`settings.local.json`은 머신·세션별 권한 기록이라 옮기면 안 된다.)

**Step B — 커밋할지 정한다 (회사·공유 저장소라면 먼저)**

| 선택 | 방법 | 언제 |
|---|---|---|
| 로컬 전용 | `printf '%s\n' .claude/ .agents/ CLAUDE.md >> .git/info/exclude` | 팀 합의 전, 개인 실험. `.gitignore`와 문법이 같지만 커밋되지 않는 개인 무시 목록 |
| 저장소에 커밋 | 브랜치에서 커밋 + `.gitignore`에 `.claude/logs/`, `.claude/checkpoints/`, `.claude/settings.local.json` 추가 | 팀 전체가 같은 훅·규칙을 쓰기로 한 경우 |

**Step C — 스택이 템플릿 기본값(Python + uv/ruff/ty/pytest)과 다르면 맞춘다**

| 파일 | 왜 | 예: Django(pip)+Vue+Docker 프로젝트에서 한 일 |
|---|---|---|
| `CLAUDE.md` 기술 스택 섹션 | 세션이 매번 읽는 유일한 스택 정보 | 백엔드/프론트/실행 방식/품질 도구/커밋 규칙으로 교체 |
| `.claude/rules/dev-environment.md` | 규칙이 uv 명령을 강요함 | pip·Docker·black/isort/flake8·pytest-django 기준으로 재작성, 보안 민감 디렉토리 명시 |
| `.claude/scripts/verify-*` | 없으면 해당 티어가 설정되지 않은 것 | `/initproject` Step 5가 작성. 훅과 스킬은 이 이름만 알고 내용은 모른다 |
| `.claude/rules/testing.md` | `uv run pytest` 표기 | 실제 테스트 명령으로 |
| `.claude/settings.json` `permissions.allow` | 프로젝트 도구 명령 자동 허용 | `Bash(isort:*)`, `Bash(flake8:*)`, `Bash(docker compose:*)` 추가 |

스택이 템플릿과 같은 Python/uv 프로젝트면 이 단계는 통째로 건너뛴다.

**Step D — 프로젝트 컨텍스트 채우기**

1. **`.agents/rules/AGENTS.md`** 상단에 프로젝트 설명 한 단락 — agy가 리서치할 때 읽는 유일한 프로젝트 컨텍스트다. 보안 민감 프로젝트면 "키·비밀값은 출력 금지"도 여기에.
2. **`.claude/docs/DESIGN.md`** — 아키텍처 5줄, 주요 라이브러리 표, 미결 질문. deep-reasoning이 리뷰 전에 항상 읽는다.

**실제로는 이렇게 한다 — C·D는 `/initproject`가 수행한다.** 오케스트레이터는 첫 세션에서 스스로 맞춤화를 시작하지 않는다(그런 지시가 CLAUDE.md에 없고, README는 복사되지 않는다). 그래서 사람이 할 일은 세 가지뿐이다:

```bash
# A. 복사  → B. 커밋 여부(로컬 전용이면 .git/info/exclude) → 첫 세션
claude
> /initproject
```

`/initproject`는 스택을 감지하고, 커밋 정책·린트 훅 처리·프로젝트 개요를 한 번에 묻고, 스택이 템플릿 기본값과 다르면 Step C의 파일들을 고치고, Step D의 `AGENTS.md`·`DESIGN.md`를 채운 뒤 스모크 테스트와 보고로 끝난다. 스택이 uv/ruff 그대로면 "맞출 게 없음"이라고 보고한다. 남은 판단은 `DESIGN.md` TODO에 기록되어 이후 세션이 이어받는다.

**Step E — 스모크 테스트**: `/deep-reasoning`·`/antigravity-system` 스킬이 목록에 뜨는지, `agy -p "Reply with OK" --model gemini-3.7-flash-low`가 동작하는지, 파일 하나 편집 후 린트 훅 출력과 `git diff`(포매터가 과하게 손대지 않는지)를 확인한다.

남는 판단(테스트 실행 방식, 기존 린트 지적 처리 등)은 `DESIGN.md`의 TODO에 적어 두고 실제 작업하면서 오케스트레이터와 함께 정하면 된다 — `design-tracker`가 결정을 기록한다.

### 2. 질문 유형별 라우팅 — 누구에게 시킬 것인가

| 하고 싶은 것 | 시키는 대상 | 말하는 법 |
|---|---|---|
| 구조·패턴·트레이드오프 판단, 원인 불명 버그, 계획/코드 리뷰 | **deep-reasoning** | "이 설계 검토해 줘", "왜 안 돼?", "A vs B" |
| 라이브러리 조사, 최신 문서, 레포 전체 파악, PDF/이미지 분석 | **agy** (general-purpose 경유) | "조사해 줘", "이 PDF 요약", "코드베이스 전체 구조" |
| 실제 구현, 파일 수정, 테스트 실행, 커밋 | **메인 Claude** / general-purpose | 평소대로 |
| 한두 문장 답이면 되는 질문 | **메인 Claude 직접** | 서브에이전트 띄우지 말 것 |

트리거 단어가 들어가면 `agent-router.py`가 자동으로 제안하지만, 확실할 때는 **명시적으로** 지정하는 편이 빠르다: "deep-reasoning에게 이 diff 리뷰시켜 줘", "agy로 httpx vs aiohttp 조사해서 research에 저장해 줘".

### 3. 기능 하나의 표준 사이클

```
/feature <기능>       agy 사전조사 → 요구사항 → deep-reasoning 계획 리뷰 → 태스크 목록 → CLAUDE.md 갱신
      ↓
/plan <세부 항목>        단계·파일·검증 기준 분해
      ↓
/tdd <단위>              Red → Green → Refactor (테스트 먼저)
      ↓
구현 → 훅이 리뷰 제안    파일 3개/100줄 넘으면 post-implementation-review 가 deep-reasoning 리뷰를 권함
      ↓
/simplify                리팩토링 패스
      ↓
별도 세션 리뷰            아래 §5 참고 (worktree)
      ↓
/checkpointing --full --analyze   세션 기록 + 반복 패턴을 스킬 후보로 추출
```

`/feature`가 CLAUDE.md에 추가하는 `## Current Project` 블록은 다음 세션의 출발점이다. 기능이 끝나면 지우거나 요약해 둔다.

### 4. 컨텍스트를 지키는 규칙

- **출력이 10줄을 넘을 것 같으면 서브에이전트.** 메인 컨텍스트는 실질 70~100k 토큰이고, 한 번 오염되면 세션 내내 비용을 낸다.
- **리서치는 파일로**: agy 결과는 `.claude/docs/research/<topic>.md`에 저장시키고 메인에는 요약 5~7줄만 받는다. 다음 세션의 deep-reasoning이 그 파일을 읽는다.
- **라이브러리 제약은 `docs/libraries/`에**: 한 번 조사한 라이브러리의 버전·금기 사항을 적어 두면 코드 리뷰 템플릿이 자동으로 참조한다.
- **세션이 길어지면 `/checkpointing --full`** 후 새 세션. `/clear`보다 낫다.
- 플랜 모드(Shift+Tab)로 설계 단계를 분리하면 deep-reasoning 상담 결과가 플랜 파일에 남아 세션이 끊겨도 이어진다.

### 5. 리뷰는 다른 세션에서 — 오염 없이

구현한 세션은 자기 코드에 편향된다. 리뷰는 **git worktree**로 격리한 새 세션에서 받는다:

```bash
git worktree add --detach ../<project>-review main   # main이 체크아웃된 상태라 --detach 필요
cd ../<project>-review && claude
# → "git diff <base>..main 을 리뷰하고 결과를 .claude/docs/review-report.md 에만 작성해. 다른 파일은 수정하지 마."
```

- 리뷰 세션에서는 `/checkpointing`을 실행하지 않는다(CLAUDE.md·AGENTS.md를 덮어쓴다).
- 리포트를 원래 세션에서 읽고 항목별로 반영 → 리포트 삭제 → `git worktree remove ../<project>-review`.
- 리뷰어에게 "deep-reasoning 서브에이전트 두 개로 코드/문서를 나눠 보라"고 하면 격리된 컨텍스트에서 깊게 본다.

### 6. agy를 제대로 쓰는 법

- **웹 리서치는 플래그 없이** `agy -p "..."`. **저장소 파일을 읽어야 하면** 템플릿 패턴대로 `--dangerously-skip-permissions --sandbox`(+ 긴 분석은 `--print-timeout 10m`). 그 프롬프트에는 반드시 "파일을 만들거나 수정하지 말 것"이 들어가야 한다.
- **빈 응답은 실패다.** 헤드리스 agy는 권한 없는 도구를 조용히 건너뛰고 exit 0을 낸다(soft-deny). `--output-format json`으로 `.status`와 `response`를 함께 보고, stderr를 버리지 않는다. `log-cli-tools.py`도 이 경우 `success: false`로 기록한다.
- **모델은 규칙에 따라 오케스트레이터가 선택**(자동 판별이 아니라 표를 따르는 판단): 템플릿 호출은 `--model`을 항상 명시한다 — T1 한 줄 사실 확인 `gemini-3.7-flash-low`, T2 웹 페이지 하나·작은 파일 하나 요약 `gemini-3.7-flash-high`(스크립트가 소비하는 추출은 `gemini-3.1-pro-low`), T3 비교·종합·마이그레이션 가이드 `gemini-3.1-pro-high`, T4 레포 전체·모듈 설명·멀티모달 `gemini-3.1-pro-high` + `--print-timeout 10m`. 헤드리스 플래그는 등급이 아니라 **입력이 파일/디렉토리/레포를 언급하는지**로 결정한다. 애매하면 상위 등급, T4는 하향 금지, 빈 답은 먼저 soft-deny(stderr `auto-denied`)인지 확인한 뒤에만 Pro로 1회 재실행. 전역 기본값(`agy` TUI의 `/model`)은 `--model`이 없는 호출에만 적용된다. 정책 전문: `.claude/rules/antigravity-delegation.md`.
- **쿼터**: "Individual quota reached … Resets in Xh"가 뜨면 리셋까지 기다린다. 큰 리서치는 하나의 잘 짜인 프롬프트로 몰아서 보낸다.
- **멀티모달**: 이미지·PDF는 검증됨. 절대경로를 프롬프트에 넣는다(stdin 리다이렉트 불가). 영상·음성은 미검증.
- 상세: `.claude/docs/research/antigravity-cli.md`, `.claude/rules/antigravity-delegation.md`.

### 7. 프로젝트 맞춤화 포인트

| 파일 | 손볼 이유 |
|---|---|
| `CLAUDE.md` 기술 스택 / `rules/dev-environment.md` | 프로젝트 스택에 맞추기 (기본값은 uv/ruff/ty) |
| `scripts/verify-*` | 이 프로젝트의 실제 검증 명령으로 작성 (훅은 손대지 않는다) |
| `hooks/agent-router.py` 트리거 목록 | 팀이 자주 쓰는 표현 추가, 과잉 매칭 단어("문서" 등) 조정 |
| `agents/deep-reasoning.md` `model:` | 세션 모델과 다른 리뷰 모델을 쓰고 싶을 때만 |
| `settings.json` `permissions.allow` | 프로젝트 도구 명령(`docker`, `npm` 등) 추가 |
| `.agents/rules/AGENTS.md` | agy에게 줄 프로젝트 설명·금기 사항 |

### 8. 자주 밟는 함정

- **적용이 끝난 프로젝트에 템플릿을 다시 복사하면 맞춤화가 전부 원본으로 덮어써진다.** 복사는 프로젝트당 **한 번**이다. 이후 템플릿 개선을 가져오려면 파일 단위로 골라 복사한다 — 템플릿 소유(그대로 덮어써도 되는 것): `.claude/agents/`, `.claude/skills/`, `.claude/hooks/`(전부 — 훅은 더 이상 스택을 모른다), `rules/deep-reasoning-delegation.md`, `rules/antigravity-delegation.md`, `rules/coding-principles.md`, `rules/security.md`, `rules/language.md`. **프로젝트 소유(덮어쓰지 말 것)**: `CLAUDE.md`, `rules/dev-environment.md`, `rules/testing.md`, `scripts/verify-*`, `settings.json`, `.agents/rules/AGENTS.md`, `docs/DESIGN.md`, `docs/research/`.

- 훅 파일명 변경 후 `settings.json` 미동기화 → PreToolUse 오류로 편집 전면 차단. 같은 커밋에서 함께 바꾼다.
- `/checkpointing` 기본 모드가 `CLAUDE.md`·`AGENTS.md`를 덮어쓴다. 실행 전 커밋해 둔다.
- deep-reasoning의 "읽기 전용"은 도구 제거 + 지시이지 커널 샌드박스가 아니다. 커밋 전 `git status`를 습관화한다.
- 서브에이전트는 서브에이전트를 못 띄운다. general-purpose 안에서 설계 판단이 필요해지면 메인으로 돌아와 deep-reasoning을 부른다(훅 문구도 그렇게 안내한다).
- agy 로그(`.claude/logs/`)와 체크포인트(`.claude/checkpoints/`)는 gitignore 대상이다 — 남기고 싶은 결론은 `docs/`로 옮긴다.

## 개발 (Development)

### 기술 스택(Tech Stack)

| 도구 | 용도 |
|--------|------|
| **uv** | 패키지 관리 (pip 미사용) |
| **ruff** | 린트·포맷 |
| **mypy** | 타입 검사 (`pyproject.toml` 기준) |
| **pytest** | 테스트 (`tests/`) |
| **poethepoet** | 태스크 러너 |

> 이 저장소는 순수 Python 이라 `ty` 로 통일되어 있다(`pyproject.toml`, `poe typecheck`, `verify-save`). **타입체커는 템플릿이 정하지 않는다** — `/initproject` 가 스택을 보고 고른다. 측정된 주의사항은 `.claude/skills/initproject/references/known-pitfalls.md` 에 있다(요약: 디스크립터로 속성 타입을 바꾸는 프레임워크에서는 `ty` 가 정상 코드를 오탐하므로 플러그인을 지원하는 체커를 쓴다).

### Commands

```bash
# 의존성
uv add <package>           # 패키지 추가
uv add --dev <package>     # 개발 종속성 추가
uv sync                    # 종속성 동기화

# 품질 점검
poe lint                   # ruff check --fix (포맷은 poe format)
poe format                 # ruff format
poe typecheck              # mypy src/  ← src/ 디렉토리가 있어야 동작 (이 템플릿 저장소에는 없음)
poe test                   # pytest (tests/)
poe all                    # lint → format → typecheck → test

# 직접 실행
uv run pytest -v
uv run ruff check .
```

## Hooks

자동화 훅은 적절한 시점에서 에이전트 연동을 제안합니다.

| 후크 | 트리거 | 동작 |
|--------|----------|------|
| `agent-router.py` | 사용자 입력 | deep-reasoning / agy 라우팅 제안 |
| `lint-on-save.py` | 파일 저장 | 자동 lint 실행 |
| `suggest-deep-reasoning-before-write.py` | 파일 쓰기 전 | 심층 추론 리뷰 제안 |
| `suggest-deep-reasoning-after-plan.py` | Plan 태스크 후 | 계획 리뷰 제안 |
| `suggest-antigravity-research.py` | 웹 검색/페치 전 | agy 리서치 제안 |
| `post-test-analysis.py` | 테스트 실패 | 디버깅 분석 제안 |
| `post-implementation-review.py` | 파일 3개 이상 / 100줄 이상 수정 후 | 코드 리뷰 제안 |
| `log-cli-tools.py` | agy 실행 | I/O 로깅 (`.claude/logs/cli-tools.jsonl`) |

훅은 전부 **제안만** 한다(차단하지 않음). 훅 파일명을 바꾸면 `.claude/settings.json`의 등록 경로를 **같은 커밋에서** 함께 바꿔야 한다 — 어긋나면 PreToolUse 훅 오류로 모든 Edit이 막힌다.

## Language Rules

- **코드 및 추론**: 영어
- **사용자 응답**: 한국어
- **기술문서**: 영어
- **README**: 한국어 허용

## License
[MIT](LICENSE)

원본: [gaebalai/claude-code-orchestrator](https://github.com/gaebalai/claude-code-orchestrator) (MDRULES Dev. by JAEWOO, KIM.) — 이 포크는 Codex CLI 역할을 Claude의 deep-reasoning 서브에이전트로 대체하고, Gemini CLI를 후속 도구인 Antigravity CLI(agy)로 마이그레이션한 버전입니다.
