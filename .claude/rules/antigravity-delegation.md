# Antigravity Delegation Rule

**Antigravity CLI (`agy`) is the research specialist: massive context, Google
Search grounding, PDF/image/video (Gemini models).**

## 이 파일은 결정만 담는다

이 파일은 **항상 로드된다**. 그래서 여기에는 **호출하기 전에 정해야 하는 것**만 둔다
— 무엇을 agy 로 보낼지, agy 를 쓸 수 없을 때 무엇으로 대체할지, 어느 티어로 부를지.
**명령 문법·플래그·프롬프트 템플릿은 여기에 없다.**

| 무엇 | 어디 | 누가 읽는가 |
|---|---|---|
| 라우팅(무엇을 agy 로), 폴백 사다리, 티어 선택, 판정 위임 금지 | **이 파일** | 메인 오케스트레이터 |
| 정확한 명령 문법, 헤드리스 플래그, soft-deny 대처 | `.claude/agents/general-purpose.md` | **실행하는 서브에이전트** |
| Task 프롬프트 템플릿, 용례 | `.claude/skills/antigravity-system/SKILL.md` (+ `references/`) | 프롬프트를 쓰는 오케스트레이터 |
| 측정된 CLI 사실·검증 날짜 | `.claude/docs/research/antigravity-cli.md` | 사람 |

**서브에이전트가 이 파일을 받는지는 보장되지 않는다.** Claude Code 문서는
`CLAUDE.md` 가 서브에이전트에 로드된다고 명시하지만 `.claude/rules/` 에 대해서는
말하지 않는다(2026-09-26 확인). 이 저장소의 한 서브에이전트는 자기 컨텍스트에 규칙
파일이 들어와 있다고 보고했지만, 그것은 이 런타임의 관찰이고 버전 간 보장이 아니다.
**그래서 실행에 필요한 것은 서브에이전트 자기 파일에 둔다** — 위 표의 둘째 줄이
중복이 아니라 그 이유다. 스킬도 서브에이전트에서 자동 발동하지 않는다(`skills:`
프론트매터로 명시 로드해야 한다).

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

"리서치면 agy" 는 **주제**로 분류한 것이다. 그것만으로는 부족하다. 실제로 비용을
결정하는 축은 **토큰량 × 추론 난이도** 두 개다.

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
  입력이 **파일 5개 또는 500줄 미만이면 퍼널 없이** deep-reasoning 에 바로 준다
  (이 숫자는 `CLAUDE.md` 「큰 변경의 기준」에서 정의되고, 여기서는 인용한다).
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

## Model Policy (choose `--model` by task tier)

**오케스트레이터가 Task 프롬프트를 쓸 때 티어를 정하고 슬러그를 박는다.**
`--model` 없는 호출은 사용자의 전역 기본값(현재 가장 비싼 티어)으로 떨어지고
로그에 `"default"` 로 남는다. 슬러그 목록: `agy models`.

| Tier | Task shape | `--model` |
|------|-----------|-----------|
| **T1 Quick lookup** | One fact / yes-no / version check; single web source | `gemini-3.7-flash-low` |
| **T2 Summarize / extract** | One web page or one small local file; structured fields from a known input | `gemini-3.7-flash-high` (machine-consumed → `gemini-3.1-pro-low`) |
| **T3 Research report** | Comparison, best practices, multi-source synthesis, migration guides | `gemini-3.1-pro-high` |
| **T4 Whole-repo / multimodal** | Repo-wide analysis, "explain this module", cross-module tracing, PDF/image/video | `gemini-3.1-pro-high` + `--print-timeout 10m` |

1. **두 티어 사이에서 애매하면 위쪽.** 잘못된 하향은 재실행을 부르고, 그게 아끼려던
   Pro 호출보다 비싸다.
2. **T4 는 하향 금지.** 대용량 컨텍스트 정확도가 agy 를 쓰는 이유 그 자체다.
3. **사용자 지시가 이 표를 이긴다** ("flash 로", "pro 로").
4. **헤드리스 플래그는 티어가 아니라 입력으로 결정된다.** 프롬프트가 로컬 파일·
   디렉토리·모듈·"이 레포"를 언급하면 **어느 티어에서든** 헤드리스 플래그와
   "파일 수정 금지" 문장이 함께 가야 한다. 순수 웹 프롬프트는 필요 없다.
   **정확한 플래그 문자열은 이 파일에 없다** — `.claude/agents/general-purpose.md`
   와 `.claude/skills/antigravity-system/SKILL.md` 가 가진다.
5. **빈 답은 먼저 soft-deny 인지 확인하고, 한 번만 올린다.** 플래그 문제면 같은
   티어로 재실행한다. 그래도 얕으면 `gemini-3.1-pro-high` 로 **한 번** 올리고,
   같은 티어에서 반복하지 않는다.
6. `--effort` 를 쓰지 않는다. 슬러그 접미사(`-low`/`-high`)가 유일한 노브다.

절감은 표의 세밀함이 아니라 **호출 분포**(대다수가 T1/T2)에서 나온다. 티어는 4개로
두고, 실제 분포는 위 "측정할 수 있는 것과 없는 것"의 명령으로 본다.

## 언어

agy 에게는 **영어로** 묻는다. 서브에이전트는 영어 응답을 받아 요약하고 파일에
저장하며, 메인이 사용자에게 **한국어로** 보고한다 (`.claude/rules/language.md`).

→ 문법·템플릿: `.claude/skills/antigravity-system/SKILL.md`
→ 실행자용 명령: `.claude/agents/general-purpose.md`
→ 측정된 CLI 사실: `.claude/docs/research/antigravity-cli.md`
