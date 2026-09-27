# 인계 문서 — 클라우드 세션 → 로컬 세션

이 파일은 **문맥이 전혀 없는 새 세션**이 이 작업을 이어받기 위한 것이다.
처음 읽는 순서는 위에서 아래 그대로다.

- **작성**: 2026-09-26, 클라우드 세션 `session_01QyHaMR7m3ZRi3RWkdMV2hZ`
- **대상 커밋**: `393f9d1` (브랜치 `claude/eager-wozniak-wr8agz`, `origin/main` 기준 35 커밋)
- **상태**: 331 테스트 통과, `.claude/scripts/verify-task` exit 0, 워킹 트리 깨끗, 전부 push 됨

> 이 파일은 **루트에 있고 `.claude/` 안에 없다.** README 의 Quick Start 는
> `.claude` · `.agents` · `CLAUDE.md` 만 복사하므로, 이 파일은 템플릿을 채택하는
> 남의 프로젝트로 따라가지 않는다. 의도된 배치다.

---

## 0. 이 저장소가 무엇인가 (3줄)

- **제품 코드가 아니다.** 본체가 프롬프트·규칙·스킬·훅이고, 남의 프로젝트로 **복사되는 템플릿**이다.
- 그래서 **한 스택·한 머신·한 사람 환경에 의존하는 것이 곧 결함**이다. 이 제약은 사용자가 반복해서 못 박았다.
- Python + uv 구현은 **이 저장소 자신의 사정**이고 채택자에게 강요하는 답이 아니다.

## 1. 먼저 읽을 세 문서 — 무엇이 어디 있는가

| 문서 | 담는 것 | 언제 보는가 |
|---|---|---|
| `CLAUDE.md` | **항상 로드되는 규칙.** 라우팅, 검증 원칙, 큰 변경의 기준, `CLAUDE.md` 섹션 수명, 운영 주의사항 | 자동 로드됨 — 따로 읽을 필요 없음 |
| `.claude/docs/DESIGN.md` | **왜 이렇게 됐는지.** Key Decisions 표(결정 / 근거 / 기각한 대안 / 날짜), TODO, Open Questions, Changelog | **작업 시작 전 Key Decisions 를 훑는다.** 여기 없는 근거는 대화 안에만 있었고 이제 없다 |
| `README.md` | 사용자용 안내. **§"지금 쓸 수 있는가 — 검증된 것과 아닌 것"** 표가 현재 검증 상태의 단일 출처 | 무엇이 검증됐는지 확인할 때 |

**DESIGN.md 를 신뢰해도 되는 이유**: 이 세션은 결정마다 근거와 **기각한 대안**을
같이 적었고, 틀린 기록을 발견하면 조용히 고치지 않고 정정문을 남겼다(예:
`HEAD~10` 을 닫힌 결함으로 잘못 기록한 것). 그래서 "왜 이렇게 안 했나"는 대부분
거기 답이 있다.

## 2. 로컬 설정 — 명령과 기대 출력

```bash
git clone https://github.com/GunwooYun/claude-code-orchestrator.git
cd claude-code-orchestrator
git checkout claude/eager-wozniak-wr8agz          # 작업 브랜치. main 아님
git log --oneline -1                               # -> 393f9d1 ... (또는 그 이후)

uv sync --all-extras
uv run pytest -q                                   # -> 331 passed
.claude/scripts/verify-task; echo $?               # -> 0

claude                                             # 여기서 세션 시작
```

첫 메시지로 이렇게 말하면 된다:

```
@HANDOFF.md 를 읽고, 5장 작업 대기열 중 <항목>부터 이어서 진행해줘.
```

**리뷰 리포트 두 개는 별도 브랜치에 있다** (작업 브랜치에는 없다):

```bash
git fetch origin 'refs/heads/claude/review-45c4afa:refs/remotes/origin/claude/review-45c4afa'
git show origin/claude/review-45c4afa:review-report.md          # 828줄, 중립 리뷰
git fetch origin 'refs/heads/claude/skilltest-initproject:refs/remotes/origin/claude/skilltest-initproject'
git show origin/claude/skilltest-initproject:skill-test-initproject.md   # 962줄, /initproject 첫 실전
```

### 로컬에서만 가능해지는 것

| | 클라우드에서 못 했던 이유 |
|---|---|
| **agy 실제 동작** | 컨테이너에 agy 가 없었다(`agy-probe` → `MISSING`). 로그인이 브라우저에서 일어나므로 사람이 필요하다 |
| **대화형 `claude` 세션** | TTY 를 띄울 수 없었다. `/initproject` 가 끝까지 완주하는지가 여기 달려 있다 (5장 A 항목) |
| **Jira/Confluence 쓰기** | 실제 사이트에 코멘트·상태 전이·페이지를 만드는 일이라 승인 없이 하지 않았다 |
| **Windows** | 확인 수단이 없었다 |

## 3. 지금까지 무엇을 어떻게 검증했나 — 그리고 무엇을 안 했나

현재 상태 표는 `README.md` §"지금 쓸 수 있는가"가 단일 출처다. 요약하면:

- **검증됨**: 훅 8개(발동/침묵 쌍 + no-op 뮤테이션), `verify-save`/`verify-task`,
  `checkpoint.py`, 문서 일관성 테스트(등급↔슬러그, 섹션 포인터, 임계값, 예산 래칫)
- **실행됨**: `/lens-review`, `/deep-reasoning`(진짜 결함을 찾았다),
  `/initproject`(Step 1~4 까지, 비대화형에서)
- **미실행**: 나머지 스킬 13개 — `/feature` 포함
- **미확인**: agy 연동 전체, Jira/Confluence 쓰기, Windows, 대화형 완주

### 이 저장소의 검증 방식 (따라야 함)

`CLAUDE.md` 검증 원칙과 `.claude/rules/testing.md` 에 정식으로 있지만, 실제로
지켜온 방식은 이것이다:

1. **테스트를 먼저 쓴다.** 그리고 **빨간불이 나는 것을 확인한다.**
2. 고친다.
3. **고친 것을 되돌려서 다시 빨간불이 나는지 확인한다** (뮤테이션).
4. 통과만 확인한 것은 검증이 아니다. "331 passed" 는 증거가 아니다.

**이 방식이 실제로 잡은 것**: 이 세션이 쓴 테스트 중 **공허한 것 2개**를 그 절차가
잡아냈다. 하나는 항상 참인 단정(`README.md` 를 검사 대상에 붙여서), 하나는
동어반복(검사할 상수를 입력으로 써서 상수를 바꿔도 초록). 뮤테이션 없이는 둘 다
초록으로 남았다.

**시나리오가 틀렸으면 테스트를 고친다 — 단, 무엇을 왜 바꿨는지 남긴다.**
`tests/test_feature_workflow.py` 의 `test_the_skill_invents_no_verification_command`
docstring 이 그 예시다(두 번의 정정을 적어 뒀다).

## 4. 이 저장소에서 일할 때의 함정 (전부 실제로 밟았다)

- **저장 게이트는 읽기 전용이다.** `verify-save` 는 이제 `--fix` 를 돌리지 않는다.
  그래서 lint 오류가 **저장 시점에 조용히 고쳐지지 않고** `poe lint`/게이트에서
  터진다. 고치는 것은 `uv run poe fix` / `uv run poe format` — 사람이 부른다.
- **맨몸 `poe` 는 exit 127.** 항상 `uv run poe`. `python3 -m unittest` 는 **0개를
  돌리고 OK** 를 낸다 — `uv run pytest` 를 쓴다.
- **`/checkpointing` 기본 모드는 `CLAUDE.md` 와 `.agents/rules/AGENTS.md` 의
  Session History 섹션을 덮어쓴다.** 실행 전에 커밋한다. 리뷰 전용 세션에서는
  실행하지 않는다.
- **`## Project Setup` / `## Current Project` / `## Session History` 는 수명이
  다르다.** 표는 `CLAUDE.md` 「`CLAUDE.md` 섹션의 수명」에 있다. 섞으면 남의 상태가
  지워진다 — 실제로 그랬다.
- **파일을 Python 스크립트로 편집하면 포매터 훅을 우회한다.** 커밋 전에
  `.claude/scripts/verify-task` 를 돌린다.
- **문서 헤딩 이름을 바꾸면 다른 파일의 포인터가 깨진다.** 11개 파일이 섹션
  이름으로 서로를 가리킨다. `tests/test_template_consistency.py` 가 잡지만,
  포인터가 헤딩 **일부만** 인용하면 못 잡는 경우가 있다.
- **`Phase N` 은 공개 이름이다.** 8개 파일이 `/feature` 를 phase 번호로 가리킨다.
  번호를 바꾸지 않는다.

## 5. 작업 대기열 — `/initproject` 첫 실전에서 나온 것

전문은 `claude/skilltest-initproject` 브랜치의 `skill-test-initproject.md`(962줄).
아래 9건은 **클라우드 세션이 직접 재현 확인했다.**

**진행 상황 (2026-09-27, 로컬 세션)**: B·D·E·H·I 는 완료(`b94c2fb`). 대기열 밖에서
발견한 `SKILL.md` Step 5 의 "a formatter may rewrite the file" 허용(계약 문서
`.claude/scripts/README.md` 는 이미 철회했는데 스킬에만 남아 있었다)도 함께
고쳤다. C·F·G 도 완료. **남은 것: A** (대화형 완주 확인이 먼저).

**대기열 밖 추가 (사용자 요구, 절대 규칙)**: 채택 프로젝트의 커밋·PR 에 오케스트레이터가
귀속 푸터를 넣지 않는다 — `.claude/settings.json` `attribution` + `CLAUDE.md` 운영 주의사항 한 줄.
이미 템플릿을 복사한 프로젝트는 `settings.json` 이 프로젝트 소유라 자동으로 받지 못한다.

### A. 비대화형에서 Step 2 에서 멈춘다 — 가장 큰 것

- **어디**: `.claude/skills/initproject/SKILL.md:37` (`## Step 2 — Ask the user (one AskUserQuestion, several questions)`), `:69`
- **무엇**: 사람이 응답할 수 없는 환경에서 질문을 내놓고 **턴이 끝난다.** Step 1~3 을
  완벽히 해놓고 4~8 을 하나도 하지 않은 상태로 `subtype=success` 로 종료했다.
- **확인**: `grep -c "기본값\|non-interactive" .claude/skills/initproject/SKILL.md` → **0**
- **왜 결함인가**: 같은 템플릿이 agy 에 대해서는 이미
  `.claude/rules/antigravity-delegation.md` 에 *"실행 중에는 사용자를 기다릴 수 없으므로
  대체 경로로 진행하고 사실만 보고한다"* 를 적어 뒀다. **배려가 한쪽에만 있다.**
- **제안**: Step 2·3 의 각 질문에 "사람이 없으면 이 기본값을 쓰고, 썼다는 사실을
  보고한다"를 적는다. **기본값을 무엇으로 할지는 판단이 필요하다** — 특히 "커밋할지
  여부"는 사용자 결정이라 기본값을 두는 것 자체가 옳은지 먼저 정해야 한다.
- **[미확인]**: 대화형 세션에서는 문제가 없을 가능성이 높다(승인 클릭 몇 번).
  **로컬에서 이것부터 확인하는 것이 순서상 맞다** — 대화형에서 완주하면 이 항목의
  성격이 "버그"에서 "헤드리스 자동화 미지원 명시"로 바뀐다.

### B. `.claude/**` 쓰기가 승인을 요구한다 — 예고가 없다 — **완료**

- **무엇**: 비대화형에서 `.claude/scripts/_lib.sh` 등의 Write 가
  `"... which is a sensitive file"` 로 거부됐다. `--permission-mode acceptEdits`,
  `--allowedTools Write Edit` 둘 다 못 뚫는다. 같은 세션에서 `CLAUDE.md`·`.gitignore`
  쓰기는 성공했다.
- **성격**: 하네스 동작이고 템플릿 결함이 아니다. 그런데 **`/initproject` 산출물이
  거의 전부 `.claude/` 안에 있다.**
- **제안**: `SKILL.md` Ground rules 또는 README Step A 에 "이 스킬은 `.claude/` 안에
  여러 파일을 쓰므로 승인 요청이 여러 번 뜬다"를 한 줄.

### C. 티어 예산에 5~10분 구멍 — **완료** (`unit` 을 5~60분으로, 6곳)

- **어디**: `.claude/rules/testing.md:70-71` (`task ≤5분` / `unit 10~60분`), `CLAUDE.md` 의 같은 표
- **확인**: 타깃의 e2e 가 **392초 = 6분 32초** — 어느 티어 예산에도 없다
- **제안**: 경계를 붙인다(`unit` 을 `5~60분`으로) 또는 원칙 4 의 "모르면 느린 쪽"
  타이브레이크를 표 안에 명시한다. **`CLAUDE.md` 와 `testing.md` 를 같은 커밋에서
  함께 고친다** — 두 곳에 같은 표가 있다.

### D. README 가 "검증 스크립트 4개"라고 약속한다 — **완료**

- **어디**: `README.md:347`
- **모순**: `.claude/skills/initproject/SKILL.md:158` — *"A tier with no honest answer
  gets no script."* 실제 테스트에서 리포터는 `verify-full` 을 **만들지 않는 것이 맞다고
  판단**했다(CI job 이 둘뿐이라 `unit` 보다 느린 티어가 없다).
- **제안**: "4개" → "이 프로젝트에 정직하게 존재하는 티어만큼".

### E. Step 6 의 드리프트 grep 이 스킬 자기 파일을 잡는다 — **완료**

- **어디**: `.claude/skills/initproject/SKILL.md:215` — `| grep -v initproject/references`
- **확인**: 그 grep 이 `initproject/SKILL.md` 를 **3건** 잡는다. 스킬의 지시문 자체라
  매번 사람이 눈으로 무시해야 한다.
- **제안**: 제외 패턴을 `initproject/` 로 넓힌다. 한 글자 수정.

### F. `verify-save` 의 구조적 침묵 — **완료** (문서화)

- **확인**: 이 저장소의 `verify-save` 에 `.ts` 파일을 주면 `exit 0`, 출력 없음
  (계약상 정당 — `case` 가 `*.py` 만 다룬다)
- **위험**: `/initproject` 를 돌리지 않거나 **중간에 실패하면** 저장 게이트가 모든
  파일에 침묵하고, 그게 정상과 구별되지 않는다. 대비되게 `verify-task` 는 같은
  상황에서 큰 소리로 실패한다(`.claude/scripts/verify-task:14`).
- **성격**: 파일 종류로 분기하는 구조상 완전 해결은 어렵다. **알고 있어야 할 사실**로
  문서화하는 것이 현실적이다.

### G. 복사된 `CLAUDE.md` 의 H1 이 남의 프로젝트 이름이다 — **완료**

- **확인**: 타깃 프로젝트의 `CLAUDE.md` 1행이 `# Claude Code Orchestrator`. 270줄 중
  ~224줄이 템플릿 자기 설명.
- **성격**: `SKILL.md:15` Ground rules 가 다른 섹션을 건드리지 말라고 하므로 **의도된
  동작**이다. 다만 결과적으로 채택 프로젝트의 유일한 상시 컨텍스트가 "나는
  오케스트레이터다"로 시작한다.
- **제안**: Step 4 에 "H1 을 프로젝트 이름으로 바꾼다"를 한 줄 추가. 단 Ground rules 의
  "never add a second H1" 과 충돌하지 않게 문구를 맞춘다.

### H. workspace trust — `settings.json` 허용 79개가 조용히 무시된다 — **완료**

- **확인**: 신뢰 대화상자를 수락하지 않은 워크스페이스에서 헤드리스로 돌리면
  `Ignoring 79 permissions.allow entries ... this workspace has not been trusted`
- **성격**: Quick Start 는 `&& claude` 로 끝나 대화형으로 켜지므로 **문서를 그대로
  따르면 해결된다.** "복사만 하고 나중에 헤드리스로 돌리는" 경로의 함정.
- **제안**: README 함정 절에 한 줄.

### I. `_lib.sh` 가 `SKILL.md` Step 5 에 없다 — **완료**

- **어디**: `.claude/scripts/README.md:76` 에만 있고 `SKILL.md` Step 5 의
  "Rules for what you write" 에는 없다. 그래도 스킬은 알아서 잘 만들었다.
- **제안**: `SKILL.md:162` 부근에 한 줄 포인터.

---

## 6. 사용자 결정이 필요한 것 — 손대지 말 것

### `origin/main` 에 이번 작업이 없다

**확인함**: `origin/main` 에 없는 것 —
`.claude/skills/initproject/`, `.claude/skills/feature/`, `.claude/skills/lens-review/`,
``.claude/scripts/`` 전체, `agy-probe`, `rules/writing-style.md`.
대신 옛 이름 `init/` · `startproject/` 가 있다.

**결과**: **지금 README 의 Quick Start 를 따른 사람은 `/initproject` 를 받지 못한다.**
35 커밋이 `origin/main` 에 없다. 공개 `main` 의 README 는 `initproject` 를 언급하지
않아서 공개된 것끼리는 일관되지만, **이 브랜치의 README 는 아직 push 되지 않은
스킬을 문서화하고 있다.**

**이것은 머지 판단이므로 사용자가 정한다.** 세션은 다음 중 하나를 **지시받은 뒤에만**
한다:
1. Quick Start 에 "브랜치를 직접 지정해 받는 법" + 검증 중이라는 경고만 추가
2. `claude/eager-wozniak-wr8agz` → `main` PR 생성
3. 아무것도 안 함 (사용자가 로컬에서 직접 머지)

사용자는 이 질문을 한 번 받고 **답하지 않았다**(대기 선택). 다시 묻기 전에 진행하지
않는다.

## 7. 지켜야 하는 작업 규칙

- **브랜치**: `claude/eager-wozniak-wr8agz` 에만 커밋·push 한다. 다른 브랜치로 push
  하려면 **명시적 허락**을 받는다. PR 은 **요청받지 않으면 만들지 않는다.**
- **커밋 메시지**: 무엇을 왜 고쳤는지, 어떻게 확인했는지(뮤테이션 결과 포함).
  이 브랜치의 기존 메시지들이 그 형식이다. **이 저장소 자신의** 커밋 푸터는
  있어도 없어도 된다. 모델 식별자는 커밋·PR·코드 주석에 넣지 않는다.
  - **정정 (2026-09-27)**: `a0edc2d` 는 이 항목을 "푸터를 넣지 않는다"로 바꿨는데,
    사용자 지시를 잘못 넓게 읽은 것이다. 사용자가 금지한 것은 **템플릿을 채택한
    프로젝트 저장소의 커밋에 오케스트레이터가 푸터를 넣는 것**이다(절대 금지).
    그것은 이 문서가 아니라 템플릿 자체(`.claude/settings.json`·`CLAUDE.md`)가
    막아야 한다.
- **언어**: 사고·코드·커밋 메시지는 영어, 사용자 대화는 한국어
  (`.claude/rules/language.md`).
- **정직성** (`.claude/rules/writing-style.md`, 예외 없음):
  확인하지 않은 것을 단정하지 않는다 / 측정하지 않은 것을 측정한 것처럼 쓰지 않는다 /
  `[확인함]` `[추론]` `[미확인]` 을 구분한다 / **이전에 쓴 것이 틀렸으면 조용히 고치지
  않고 무엇이 왜 틀렸는지 남긴다.**
- **서브에이전트 보고를 그대로 믿지 않는다.** 이 세션은 리뷰어의 12개 주장을 전부
  직접 재현했고(전부 맞았다), 그래도 다음 리포트에서 검증을 생략하지 않았다.
  실제로 deep-reasoning 서브에이전트가 **틀린 근거**를 댄 적이 두 번 있다.
- **리뷰는 별도 세션에서.** 구현한 세션은 자기 코드에 편향된다. 방법은 `CLAUDE.md`
  운영 주의사항에 있다 — **워크트리를 `main` 에 체크아웃하지 않는다**(빈 diff 가 나온다).

## 8. 남은 큰 항목 (대기열 밖)

- **루프/그래프 엔지니어링** — 사용자의 선택사항이고 **아직 조사하지 않았다.**
  검증되지 않은 `/feature` 위에 한 겹을 더 얹는 일이므로, 실제 사용 경험을 먼저
  보는 편이 순서상 맞다는 의견을 전달해 뒀다.
- **나머지 스킬 12개 실행 테스트** — `/feature` 가 가장 값지다. 방법은 5장 A 항목과
  같다: 문맥 없는 세션에 시키고, 막힌 문장을 인용하게 한다.

## 9. 이 문서의 한계

- **판단이 진행 중이던 것은 옮기지 못한다.** 5장 A 의 "기본값을 무엇으로 할지"가
  그 예다 — 사실은 옮겼지만 결정은 못 옮겼다.
- **대화의 맥락은 없다.** 왜 그 순서로 고쳤는지, 어떤 대안을 왜 버렸는지는
  `DESIGN.md` Key Decisions 에 있고, 거기 없으면 사라졌다.
- **리포트 두 개는 이 파일에 요약만 있다.** 재현 명령과 출력 전문은 각 브랜치의
  원문에 있고, 그쪽이 훨씬 구체적이다.
