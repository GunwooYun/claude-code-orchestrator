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
│   ├── skills/                  # 재사용 가능한 워크플로우
│   │   ├── startproject/        # 프로젝트 시작
│   │   ├── plan/                # 구현 계획
│   │   ├── tdd/                 # 테스트 주도 개발
│   │   ├── checkpointing/       # 세션 영속화
│   │   ├── deep-reasoning/      # 심층 추론 서브에이전트 연동
│   │   ├── antigravity-system/  # Antigravity CLI (agy) 연동
│   │   └── ...
│   │
│   ├── hooks/                   # 자동화 훅
│   │   ├── agent-router.py      # 에이전트 라우팅
│   │   ├── lint-on-save.py      # 저장 시 자동 린트
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

### `/startproject` — 프로젝트 시작

멀티에이전트 협업으로 프로젝트를 킥오프한다.

```
/startproject 사용자 인증 기능
```

**워크플로우:**
1. **agy** → 리포지토리 분석·사전 조사
2. **Claude** → 요구사항 정리·계획 수립
3. **deep-reasoning** → 계획 리뷰·리스크 분석
4. **Claude** → 실행 태스크 목록 생성

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

### `/research-lib`, `/update-lib-docs` — 라이브러리 제약 문서

`/research-lib <lib>`는 라이브러리 조사 결과를 `.claude/docs/libraries/<lib>.md`에 저장하고, `/update-lib-docs`는 기존 문서를 최신화한다. deep-reasoning 코드 리뷰와 agy 리서치가 이 문서를 제약 조건으로 참조한다.

### `/init` — 프로젝트 스택 감지

프로젝트 구조를 분석해 `CLAUDE.md`의 기술 스택 섹션과 `## Current Project` 블록을 채우고, 불필요한 규칙 파일을 제안한다. 템플릿 적용 직후 1회 실행 후 결과를 검토한다. (agy 컨텍스트인 `.agents/rules/AGENTS.md`는 건드리지 않는다.)

## 실전 활용 가이드 — 120% 뽑아내기

이 템플릿의 가치는 "세 에이전트를 의도적으로 분리해서 쓰는 습관"에서 나온다. 아래는 실제 적용·운영하면서 검증한 사용법이다.

### 1. 적용 절차 (프로젝트당 1회)

```bash
cd <your-project>
git clone --depth 1 https://github.com/GunwooYun/claude-code-orchestrator.git .starter \
  && cp -r .starter/.claude .starter/.agents .starter/CLAUDE.md . && rm -rf .starter
claude        # 폴더 신뢰 → 첫 세션
```

첫 세션에서 할 일 (순서대로):

1. **`/init`** — 프로젝트 스택을 감지시켜 `CLAUDE.md`의 기술 스택 섹션과 `## Current Project` 블록을 채우고, 결과를 직접 검토한다. 불필요한 규칙 파일도 이때 제안받는다.
2. **`.claude/rules/dev-environment.md`와 `hooks/lint-on-save.py`를 실제 프로젝트에 맞춘다.** 템플릿 기본값은 Python + uv/ruff/ty/pytest다. Django(pip)나 프론트엔드 프로젝트라면 이 둘을 고치지 않는 한 규칙과 린트 훅(`uv run ruff`/`ty`)은 헛돌거나 조용히 건너뛴다.
3. **`.agents/rules/AGENTS.md`**에 프로젝트 한 줄 설명을 추가한다 — agy가 리서치할 때 읽는 유일한 프로젝트 컨텍스트다.
4. **`.claude/docs/DESIGN.md`**를 열어 현재 아키텍처를 5줄이라도 적는다. deep-reasoning이 리뷰 전에 항상 이 파일을 읽는다.
5. 스모크 테스트: `/deep-reasoning`·`/antigravity-system` 스킬이 목록에 뜨는지, `agy -p "Reply with OK"`가 동작하는지.

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
/startproject <기능>   agy 사전조사 → 요구사항 → deep-reasoning 계획 리뷰 → 태스크 목록 → CLAUDE.md 갱신
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

`/startproject`가 CLAUDE.md에 추가하는 `## Current Project` 블록은 다음 세션의 출발점이다. 기능이 끝나면 지우거나 요약해 둔다.

### 4. 컨텍스트를 지키는 규칙

- **출력이 10줄을 넘을 것 같으면 서브에이전트.** 메인 컨텍스트는 실질 70~100k 토큰이고, 한 번 오염되면 세션 내내 비용을 낸다.
- **리서치는 파일로**: agy 결과는 `.claude/docs/research/<topic>.md`에 저장시키고 메인에는 요약 5~7줄만 받는다. 다음 세션의 deep-reasoning이 그 파일을 읽는다.
- **라이브러리 제약은 `docs/libraries/`에**: 한 번 조사한 라이브러리의 버전·금기 사항을 적어 두면 코드 리뷰 템플릿이 자동으로 참조한다.
- **세션이 길어지면 `/checkpointing --full`** 후 새 세션. `/clear`보다 낫다.
- 플랜 모드(Shift+Tab)로 설계 단계를 분리하면 deep-reasoning 상담 결과가 플랜 파일에 남아 세션이 끊겨도 이어진다.

### 5. 리뷰는 다른 세션에서 — 오염 없이

구현한 세션은 자기 코드에 편향된다. 리뷰는 **git worktree**로 격리한 새 세션에서 받는다:

```bash
git worktree add ../<project>-review main
cd ../<project>-review && claude
# → "git diff <base>..main 을 리뷰하고 결과를 .claude/docs/review-report.md 에만 작성해. 다른 파일은 수정하지 마."
```

- 리뷰 세션에서는 `/checkpointing`을 실행하지 않는다(CLAUDE.md·AGENTS.md를 덮어쓴다).
- 리포트를 원래 세션에서 읽고 항목별로 반영 → 리포트 삭제 → `git worktree remove ../<project>-review`.
- 리뷰어에게 "deep-reasoning 서브에이전트 두 개로 코드/문서를 나눠 보라"고 하면 격리된 컨텍스트에서 깊게 본다.

### 6. agy를 제대로 쓰는 법

- **웹 리서치는 플래그 없이** `agy -p "..."`. **저장소 파일을 읽어야 하면** 템플릿 패턴대로 `--dangerously-skip-permissions --sandbox`(+ 긴 분석은 `--print-timeout 10m`). 그 프롬프트에는 반드시 "파일을 만들거나 수정하지 말 것"이 들어가야 한다.
- **빈 응답은 실패다.** 헤드리스 agy는 권한 없는 도구를 조용히 건너뛰고 exit 0을 낸다(soft-deny). `--output-format json`으로 `.status`와 `response`를 함께 보고, stderr를 버리지 않는다. `log-cli-tools.py`도 이 경우 `success: false`로 기록한다.
- **모델은 작업 등급으로 자동 선택**: 템플릿 호출은 `--model`을 항상 명시한다 — T1 한 줄 사실 확인 `gemini-3.7-flash-low`, T2 단일 문서 요약·추출 `gemini-3.7-flash-high`, T3 비교·종합 리서치 `gemini-3.1-pro-high`, T4 레포 전체·멀티모달 `gemini-3.1-pro-high` + `--print-timeout 10m`. 애매하면 상위 등급, T4는 하향 금지, 얕은 답이면 T3로 1회 재실행. 전역 기본값(`agy` TUI의 `/model`)은 `--model`이 없는 호출에만 적용된다. 정책 전문: `.claude/rules/antigravity-delegation.md`.
- **쿼터**: "Individual quota reached … Resets in Xh"가 뜨면 리셋까지 기다린다. 큰 리서치는 하나의 잘 짜인 프롬프트로 몰아서 보낸다.
- **멀티모달**: 이미지·PDF는 검증됨. 절대경로를 프롬프트에 넣는다(stdin 리다이렉트 불가). 영상·음성은 미검증.
- 상세: `.claude/docs/research/antigravity-cli.md`, `.claude/rules/antigravity-delegation.md`.

### 7. 프로젝트 맞춤화 포인트

| 파일 | 손볼 이유 |
|---|---|
| `CLAUDE.md` 기술 스택 / `rules/dev-environment.md` | 프로젝트 스택에 맞추기 (기본값은 uv/ruff/ty) |
| `hooks/lint-on-save.py` | 실제 린터·타입체커 명령으로 교체 |
| `hooks/agent-router.py` 트리거 목록 | 팀이 자주 쓰는 표현 추가, 과잉 매칭 단어("문서" 등) 조정 |
| `agents/deep-reasoning.md` `model:` | 세션 모델과 다른 리뷰 모델을 쓰고 싶을 때만 |
| `settings.json` `permissions.allow` | 프로젝트 도구 명령(`docker`, `npm` 등) 추가 |
| `.agents/rules/AGENTS.md` | agy에게 줄 프로젝트 설명·금기 사항 |

### 8. 자주 밟는 함정

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

> 알려진 불일치: `pyproject.toml`/`poe typecheck`는 **mypy**를 쓰지만 `CLAUDE.md`, `.claude/rules/dev-environment.md`, `lint-on-save.py` 훅은 **ty**(`uv run ty check`)를 전제한다(upstream부터 존재). 적용하는 프로젝트에서 둘 중 하나로 통일할 것 — ty를 쓰려면 `uv add --dev ty` 후 `typecheck = "ty check src/"`로, mypy를 유지하려면 규칙 문서와 훅의 `ty` 호출을 `mypy`로 바꾼다.

### Commands

```bash
# 의존성
uv add <package>           # 패키지 추가
uv add --dev <package>     # 개발 종속성 추가
uv sync                    # 종속성 동기화

# 품질 점검
poe lint                   # ruff check + format
poe typecheck              # mypy
poe test                   # pytest
poe all                    # 전체 검사 실행

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
