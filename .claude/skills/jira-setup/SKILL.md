---
name: jira-setup
description: Connect this project to Jira, once. Detects whether the Atlassian connector is authenticated and whether Jira scopes are present, captures the site, project key, project style, issue types and transition names, and records the team's write policy for comments and status changes. Run once per project; /ticket uses what it records.
disable-model-invocation: true
---

# Jira Setup (once per project)

**이 프로젝트가 어느 Jira 프로젝트와 연결되는지 한 번 확정한다.** `/ticket` 이
매번 묻지 않도록 결과를 `CLAUDE.md` 에 기록한다.

이 스킬은 수동 전용이다(`disable-model-invocation`). 프로젝트당 한 번이고, 실수로
발동해서 기록을 덮으면 안 된다.

---

## Step 1 — 연결 상태를 판별한다

**도구 이름은 커넥터 설정에 따라 다르다.** 이 세션에 실제로 있는 이름을 쓴다
(Atlassian 계열: 사용자 정보 / 접근 가능 리소스 / 프로젝트 조회).

1. **사용자 정보 조회** — 실패하면 커넥터가 연결되지 않았다
2. **접근 가능 리소스 조회** — 사이트 목록과 각 사이트의 **스코프**가 나온다

상태는 셋이고 조치가 다르다.

| 상태 | 판별 | 조치 |
|---|---|---|
| 미연결 | 사용자 정보 조회 실패 / 도구 없음 | **여기서 멈춘다.** 커넥터 연결을 사용자에게 요청. **로그인은 대신 할 수 없다** — OAuth 는 클라이언트에서 사용자가 한다 |
| Confluence 만 | 리소스에 `*:confluence` 스코프만 있음 | Jira 스코프가 없다고 알리고, 커넥터 권한을 다시 승인해야 한다고 설명. `/doc-write` 는 계속 쓸 수 있다 |
| 연결됨 | `read:jira-work` 가 있음 | Step 2 로 |

**같은 사이트가 스코프 그룹별로 여러 번 나올 수 있다**(Confluence 용 항목과 Jira 용
항목이 별개). 사이트를 유일하다고 가정하지 말고 URL 로 묶는다.

쓰기 권한은 `write:jira-work` 로 확인한다. 없으면 읽기 전용이므로 코멘트·상태 전이가
불가능하다 — Step 4 에서 그 사실을 기록한다.

## Step 2 — 프로젝트를 묻는다 (목록을 보여주지 않는다)

**프로젝트가 수백 개일 수 있다** (측정된 한 조직: 141개). 목록을 나열하면 컨텍스트만
태우고 사용자는 어차피 자기 키를 안다.

AskUserQuestion 하나로 묻는다:

1. **프로젝트 키** — 이 저장소의 작업이 올라가는 프로젝트 (예: `ABC`). 여러 개면 전부
2. **기본 이슈 타입** — 새 티켓을 만들 때 (Task / Story / Bug ...)
3. **쓰기 정책** — 아래 Step 4 의 표를 그대로 보여주고 고르게 한다

사용자가 티켓 키나 링크를 이미 줬으면 거기서 프로젝트 키를 뽑아 확인만 받는다.

## Step 3 — 그 프로젝트만 조회한다

키를 받은 뒤, **그 프로젝트 하나만** 조회한다. 기록할 것:

- **`style`** — `classic`(company-managed) 인가 `next-gen`(team-managed) 인가.
  **이슈 타입과 워크플로 전이가 이 값에 따라 다르므로 반드시 기록한다.**
- **이슈 타입** 목록
- **전이 이름** — 실제 티켓 하나의 전이 목록을 조회해서 "진행 중"·"완료" 에 해당하는
  **정확한 이름**을 얻는다. 추측하지 않는다. 워크플로마다 문구가 다르다
- `isPrivate` 여부

응답에 아바타 URL 같은 불필요한 필드가 많다. **필요한 필드만 요청**한다.

## Step 4 — 쓰기 정책을 정하고 기록한다

Jira 코멘트와 상태 전이는 **팀이 보는 외부 동작**이다. 기본값을 임의로 정하지 않고
사용자에게 고르게 한다.

| 동작 | 성격 | 기본 제안 |
|---|---|---|
| **코멘트 추가** | 덧붙이는 동작. 되돌리기 쉬움 | 초안을 보여주고 승인 후 작성 |
| **상태 전이** | **공유 상태 변경.** 다른 사람의 작업 흐름에 영향 | **항상 확인받는다** |
| **설명(description) 수정** | 기존 내용을 덮음 | **항상 확인받는다** — 남이 쓴 것일 수 있다 |
| **새 티켓 생성** | 덧붙이는 동작 | 초안을 보여주고 승인 후 생성 |

이 기본값은 `.claude/docs/writing-style.md` §6.4 의 Confluence 정책과 같은 논리다 —
**덧붙이는 것은 보고, 덮는 것은 먼저 확인.**

## Step 5 — `CLAUDE.md` 에 기록한다

**이 스킬 파일이 아니라 `CLAUDE.md` 의 `## Project Setup` 에 쓴다.** 프로젝트별
값을 템플릿에 박으면 다음 프로젝트에서 틀린다.

**`## Current Project` 가 아니다.** 그 섹션은 `/feature` 가 작업 단위마다
교체하므로, 여기 기록한 사이트·전이·쓰기 정책이 다음 `/feature` 에서 사라진다.
`## Project Setup` 은 프로젝트 영구 상태이고, `## Session History` **앞**에 둔다
(수명 정의: `CLAUDE.md` 「`CLAUDE.md` 섹션의 수명」). 이미 `### Jira` 가 있으면
그 하위 섹션만 갱신하고 `## Project Setup` 블록 전체를 다시 쓰지 않는다.

```markdown
### Jira

- 사이트: `<site>.atlassian.net`  (cloudId 는 호스트명으로 대체 가능)
- 프로젝트: `<KEY>` — <이름>, style: `classic` | `next-gen`
- 이슈 타입: <목록>
- 전이: 진행 중 = `<정확한 이름>`, 완료 = `<정확한 이름>`
- 쓰기 권한: 있음 | 없음(읽기 전용)
- 쓰기 정책: 코멘트 <정책> / 상태 전이 <정책> / 설명 수정 <정책>
```

**자격증명·토큰은 절대 기록하지 않는다.** 인증은 커넥터가 관리한다.

연결되지 않았거나 Jira 스코프가 없으면, 그 사실과 날짜를
`.claude/docs/DESIGN.md` 의 Open Questions 에 남긴다 — 다음 세션이 다시 발견하지
않도록.

## Step 6 — 확인하고 보고한다

- 기록한 프로젝트 키로 티켓 하나를 조회해서 실제로 읽히는지 확인
- 한국어로 보고: 사이트·프로젝트·style·전이 이름·쓰기 권한·쓰기 정책, 그리고
  `/ticket` 을 이제 쓸 수 있다는 것

**루프하지 않는다.** 한 번 묻고, 사용자가 준비됐다고 하면 한 번 재확인하고 끝낸다.

→ 티켓 단위 작업: `.claude/skills/ticket/SKILL.md`
