---
name: lens-review
description: |
  Review a substantial change through several independent lenses in parallel,
  then aggregate — deduplicating overlaps and, above all, surfacing where the
  lenses DISAGREE. Use it when the user asks for a review ("리뷰해줘",
  "검토해줘", "review this") AND the change is substantial (roughly 5+ files or
  500+ changed lines, or any change to a security boundary or a public
  interface). For a small change, one deep-reasoning call is cheaper and just as
  good — say so and do that instead. Do NOT use it to answer a question about
  code, and do NOT use it as the final review of work done in this same session:
  the session that wrote the code is the worst judge of it, so a separate session
  still owns that (see CLAUDE.md 운영 주의사항).
metadata:
  short-description: Parallel multi-lens review with conflict surfacing
---

# Lens Review

**같은 변경을 서로 다른 관점으로 병렬 검토하고, 취합할 때 관점 간 충돌을 드러낸다.**

단일 프롬프트에 여러 관점을 한꺼번에 요구하면 모델이 한 축으로 쏠린다. 관점을
나누면 각 관점이 자기 축에서 끝까지 본다. 그리고 각 렌즈가 독립 컨텍스트를 쓰므로
메인 컨텍스트가 보호된다 — 이 프로젝트의 기본 원칙과 같은 방향이다.

## 언제 쓰고, 언제 쓰지 않는가

| 상황 | 방법 |
|---|---|
| 리뷰 요청 + **큰 변경** (파일 5개 또는 500줄 이상, 또는 보안 경계·공개 인터페이스 변경 — 기준은 `CLAUDE.md` 「큰 변경」의 기준 하나뿐이다) | **이 스킬** |
| 리뷰 요청 + 작은 변경 | **deep-reasoning 한 번.** 렌즈 3개는 비용이 3배인데 얻는 것이 그만큼 늘지 않는다 |
| 코드에 대한 질문 | 답변한다. 리뷰가 아니다 |
| **이 세션에서 쓴 코드의 최종 리뷰** | **별도 세션이 담당한다** — 아래 참조 |

### 이 스킬이 별도 세션 리뷰를 대체하지 않는다

`CLAUDE.md` 운영 주의사항: **구현한 세션은 자기 코드에 편향된다.** 이 스킬은
격리된 컨텍스트를 쓰지만 **프롬프트를 내가 쓴다** — 내 프레이밍이 결론을 밀어낸다.

| | 담당 |
|---|---|
| 세션 안의 리뷰 (빠르고, 편향 일부 남음) | **이 스킬** |
| 최종 리뷰 (편향 제거) | `git worktree add --detach ../<project>-review main` 로 격리한 **새 세션** |

이 스킬을 돌렸다고 최종 리뷰를 건너뛰지 않는다. 반대로, 최종 리뷰 전에 이 스킬로
명백한 것들을 먼저 걷어내면 최종 리뷰가 어려운 것에 집중한다.

---

## Step 1 — 큰 입력이면 프리필터를 먼저, 한 번만

변경이 크면 **agy 로 검토 지점을 한 번 뽑아서 모든 렌즈에 같은 목록을 준다.**

**렌즈마다 프리필터를 돌리지 않는다** — 같은 일을 3번 하는 것이고, 렌즈마다 다른
목록을 받으면 취합 단계에서 비교가 불가능해진다.

기준과 절대 규칙은 `.claude/rules/antigravity-delegation.md` → "라우팅은 주제가
아니라 비용으로 한다" → B. 2단계 퍼널. 요약하면 **agy 는 `file:line` 과 사실만
반환하고 판정은 하지 않으며**, 각 렌즈에게 "걸러진 목록이다, 부족하면 직접 읽어라"를
명시한다.

agy 를 쓸 수 없으면 프리필터를 생략하고 각 렌즈가 직접 읽는다.

## Step 2 — 렌즈를 고른다

기본 3개다. **서로 겹치지 않는 축이어야 한다** — 겹치면 같은 지적이 3번 올라오고
비용만 3배가 된다.

| 렌즈 | 무엇을 보는가 | 무엇을 보지 않는가 |
|---|---|---|
| **correctness** | 주장한 동작을 실제로 하는가. 경계값, 오류 경로, 상태 전이, 되돌림 | 스타일, 구조의 아름다움 |
| **design** | 구조가 유지되는가. 책임 분리, 중복, 이 추상화가 다음 변경을 견디는가 | 개별 버그 |
| **robustness** | 적대적 입력, 실패 모드, 비밀값 노출, 부분 실패 시 상태 | 정상 경로의 정확성 |

**바꿔 끼우는 경우:**

| 변경의 성격 | 교체 |
|---|---|
| 테스트가 거의 없는 변경 | `design` → **verification adequacy** (어떤 동작이 테스트로 안 덮였는지, 실패해야 할 때 실패하는지) |
| 성능이 요구사항인 변경 | `robustness` → **efficiency** |
| 순수 리팩터링 (동작 불변) | `correctness` → **behaviour preservation** (동작이 정말 같은지) |

**3개를 넘기지 않는 것을 권한다.** 비용은 렌즈 수에 선형이고, 4개 이상에서는
새 발견보다 중복이 빠르게 늘어난다. 넘겨야 할 이유가 있으면 이유를 말한다.

## Step 3 — 병렬로 띄운다 (한 메시지에)

**렌즈 전부를 한 메시지에서 동시에 spawn 한다.** 순차로 띄우면 병렬성을 잃는다.

각 렌즈는 `deep-reasoning` 서브에이전트다. 프롬프트에 반드시 넣을 것:

```
You are reviewing {target} through ONE lens: {lens name}.
{lens definition — what to look at}
{what this lens explicitly does NOT cover — another lens has it}

{if prefiltered:}
These locations were pre-filtered by another tool and are NOT exhaustive.
Read anything else you need directly.
{locations}

Return, in at most {N} lines:
- Findings in YOUR dimension only, each with file:line and the concrete
  failure it predicts (inputs → wrong outcome). No style notes.
- For each: how confident you are, and what would settle it.
- **If you find nothing in this dimension, say so.** Finding nothing is a
  result. Do NOT invent a finding to look useful.
- Anything you saw that belongs to another lens: one line, so the aggregate
  can route it.
```

마지막 두 줄이 중요하다. **발견이 없는 렌즈에게 압박을 주면 소음을 만든다.**
그리고 자기 축이 아닌 것을 억지로 자기 축으로 해석하지 않게 한다.

## Step 4 — 취합: 충돌이 핵심 산출물이다

메인이 취합한다(서브에이전트는 서브에이전트를 못 띄운다). 순서대로:

1. **중복 제거** — 두 렌즈가 같은 지점을 지적했으면 **하나의 발견에 두 관점**이다.
   두 개로 세지 않는다. 다만 두 렌즈가 독립적으로 찾았다는 사실은 신뢰도를 높인다.
2. **충돌 노출 — 이 스킬의 가장 큰 가치다.** 렌즈가 서로 반대되는 권고를 하면
   그것이 **진짜 설계 결정 지점**이다. 예:
   - correctness: "여기 가드를 추가하라" ↔ design: "이 함수는 존재하지 않아야 한다"
   - robustness: "실패 시 롤백하라" ↔ design: "그 트랜잭션 경계가 잘못 그려져 있다"

   **충돌을 임의로 판정하지 않는다.** 양쪽 권고와 각각의 근거를 나란히 제시하고,
   무엇을 선택하면 무엇을 잃는지 쓴다. 판단은 사용자 또는 후속 deep-reasoning 이
   한다.
3. **심각도 정렬** — 예측된 실패의 크기로. 렌즈 이름이 아니라 결과로 정렬한다.
4. **덮이지 않은 축** — 어느 렌즈도 보지 않은 영역이 있으면 적는다. "발견 없음"과
   "보지 않음"은 다르다.

산출 형식:

```markdown
## 리뷰 결과: {target}

### 충돌 — 결정이 필요한 지점 ({N}개)
| 지점 | 렌즈 A 권고 | 렌즈 B 권고 | 무엇을 잃는가 |

### 발견 (심각도 순)
| # | 지점 | 예측되는 실패 | 렌즈 | 신뢰도 |

### 발견 없음
- {렌즈}: 이 축에서 발견 없음

### 보지 않은 것
- {영역} — 어느 렌즈도 다루지 않았다
```

## Step 5 — 검증은 조건부로

발견을 **적대적으로 재검증**하면 오탐이 걸러지지만 **비용이 한 라운드 늘어난다.**
항상 하지 않는다.

| 하는 경우 | 안 하는 경우 |
|---|---|
| 렌즈가 신뢰도를 낮게 표시한 발견 | 렌즈가 확신하고 `file:line` 이 명확한 발견 |
| 그 발견을 근거로 **자동으로 코드를 고칠** 때 | 사람이 읽고 판단할 때 |
| 반복해서 같은 지적이 올라오는데 고쳐지지 않을 때 | 발견이 3개 이하일 때 |

검증은 **발견당 하나의 deep-reasoning 호출**로, "이 발견을 반박해 보라"는 방향으로
프롬프트한다. 재현 가능한 실패 경로를 제시하지 못하면 그 발견은 내린다.

## 실패 모드

- **렌즈가 직교하지 않는다** → 같은 지적이 3번. 비용 3배, 가치 1배. Step 2 의
  "무엇을 보지 않는가" 칸을 프롬프트에 그대로 넣어야 한다.
- **발견이 없는 렌즈가 억지로 발견을 만든다** → 소음이 진짜 발견을 묻는다.
  "발견 없음은 결과다"를 프롬프트에 넣는다.
- **충돌을 내가 조용히 판정한다** → 가장 값진 정보를 버린다. 양쪽을 제시한다.
- **렌즈마다 프리필터를 돌린다** → 3배 비용에, 목록이 달라 비교가 불가능.
- **이걸로 최종 리뷰를 대체한다** → 내가 프롬프트를 썼으므로 내 편향이 남는다.
  별도 세션이 최종을 담당한다.
- **렌즈를 5개 이상 늘린다** → 중복이 새 발견보다 빠르게 늘어난다.

→ 라우팅·프리필터: `.claude/rules/antigravity-delegation.md`
→ deep-reasoning 위임: `.claude/rules/deep-reasoning-delegation.md`
