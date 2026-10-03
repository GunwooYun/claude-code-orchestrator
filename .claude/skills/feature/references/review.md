# Phase 6 — review procedures

Loaded on demand from `/feature` Phase 6. The default (A1, `/isolated-review`) and when to end a round stay in SKILL.md.

## A2 — person-opened session

리포트에 되묻거나 반박해야 할 때, 또는 보안 경계·공개 인터페이스 변경일 때 A1 에 더해
사용자에게 요청한다. A1 은 되묻기가 불가능하다.

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

## Option B — deep-reasoning review prompt

변경이 크면(파일 5개 또는 500줄 이상 — `CLAUDE.md` 「큰 변경의 기준」) 앞단에
agy 프리필터를 두고, deep-reasoning 에게 걸러진 입력임을 알린다.

**Option A(별도 세션)를 대체하지 않는다.** 이 세션이 프롬프트를 쓰므로 편향이 남는다.

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

## Why a separate session

- **Fresh perspective**: New session has no bias from implementation
- **Neutral judgement on its own tests**: the session that wrote a test is the
  worst judge of whether it proves anything
- **Different context**: Can focus purely on review, not implementation details
- **Isolated context**: Deep analysis without context pollution

---
