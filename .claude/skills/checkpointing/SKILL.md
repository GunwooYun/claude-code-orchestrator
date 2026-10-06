---
name: checkpointing
description: |
  Write the agy consultation history from .claude/logs/cli-tools.jsonl into the
  `## Session History` section of CLAUDE.md and `## Consultation History` of
  .agents/rules/AGENTS.md, so the next session (and agy) can see what was asked.
metadata:
  short-description: Write agy consultation history into the context files
---

# Checkpointing — 세션 기록

`.claude/logs/cli-tools.jsonl` 의 agy 상담 이력을 날짜별로 정리해서 두 파일에 쓴다.

| 파일 | 헤딩 |
|---|---|
| `CLAUDE.md` | `## Session History` |
| `.agents/rules/AGENTS.md` | `## Consultation History` |

헤딩이 파일마다 다르다 — 같다고 가정하면 AGENTS.md 에 두 번째 섹션이 계속 덧붙는다(실제로 그랬다).

## 사용법

```bash
/checkpointing                       # 전체 로그
/checkpointing --since "2026-01-26"  # 이 날짜(로컬)부터
```

## 형식

라벨과 상태는 영어다(이 섹션은 agy 도 읽는다):

```markdown
## Session History

### 2026-01-26

**agy:**
- [OK] MCP vs CLI comparison...
- [FAILED] a call that returned nothing
- [UNKNOWN] a call whose stdout went to a file
```

`[UNKNOWN]` 은 훅이 결과를 판정할 수 없는 모양으로 부른 호출이다 — 훅은 `agy …` 를 한 줄에 단독으로
부른 호출(`2>파일`, `<파일`, 끝의 `| tee 파일` 까지만 허용)만 판정하고, 파일·파이프·`$(...)`·
`|| echo`·`2>&1` 등 나머지는 전부 여기로 간다(로그의 `success: null`, 사유는 `stdout_target`).
실패로 세지도, 성공으로 세지도 않는다.

위 예시가 코드 펜스 안에 있는 것은 의도다 — `checkpoint.py` 는 펜스 안의 헤딩을 섹션 경계로 보지 않는다.

## 주의사항

- **기존 히스토리 섹션을 덮어쓴다.** 실행 전에 커밋하고, 리뷰 전용 세션에서는 쓰지 않는다.
- 섹션 순서: `## Project Setup` → `## Current Project` → `## Session History`(항상 마지막) —
  `CLAUDE.md` 「`CLAUDE.md` 섹션의 수명」. 그 뒤에 오는 H1/H2 섹션은 보존된다.
- 로그가 비어 있으면 아무것도 쓰지 않는다. 로그 파일은 읽기만 한다.
- 예전의 `--full`(체크포인트 파일)과 `--analyze`(스킬 후보 발굴)는 2026-10-03 에 뺐다 — 한 번도
  쓰이지 않았고, 새 스킬은 실사용 리포트로만 만든다. 태그 `v1.1.0` 에 남아 있다.
