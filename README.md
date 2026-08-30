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

헤드리스(`agy -p`) 호출에서 파일 읽기는 기본 거부되므로(soft-deny: 조용히 건너뛰고 exit 0),
코드베이스 분석·멀티모달을 쓰려면 `~/.gemini/antigravity-cli/settings.json`에 1회 허용 규칙을 추가한다:

```json
{ "permissions": { "allow": ["read_file(*)"] } }
```

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
/checkpointing              # 기본: 기록 로그
/checkpointing --full       # 전체 : git 이력 및 파일 변경 포함
/checkpointing --analyze    # 분석 : 재사용 가능한 기술 패턴 발견
```

### `/deep-reasoning` — 심층 추론 서브에이전트 연동

설계 판단, 디버깅, 트레이드오프 분석 전용. Claude Fable이 격리된 컨텍스트에서 분석하고 간결한 권고만 반환한다.

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

아키텍처 및 구현 결정을 자동으로 기록합니다.

## 개발 (Development)

### 기술 스택(Tech Stack)

| 도구 | 용도 |
|--------|------|
| **uv** | 패키지 관리 (pip 미사용) |
| **ruff** | 린트·포맷 |
| **mypy** | 타입 검사 |
| **pytest** | 테스트 |
| **poethepoet** | 태스크 러너 |

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
| `log-cli-tools.py` | agy 실행 | I/O 로깅 |

## Language Rules

- **코드 및 추론**: 영어
- **사용자 응답**: 한국어
- **기술문서**: 영어
- **README**: 한국어 허용

## License
[MIT](LICENSE)

원본: [gaebalai/claude-code-orchestrator](https://github.com/gaebalai/claude-code-orchestrator) (MDRULES Dev. by JAEWOO, KIM.) — 이 포크는 Codex CLI 역할을 Claude의 deep-reasoning 서브에이전트로 대체하고, Gemini CLI를 후속 도구인 Antigravity CLI(agy)로 마이그레이션한 버전입니다.
