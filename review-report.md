# 리뷰 리포트 — `claude/eager-wozniak-wr8agz`

- **대상**: `git diff origin/main...HEAD` (31 커밋, 59 파일, +8,725 / -1,333)
- **HEAD**: `45c4afa`
- **리뷰 세션**: 구현 세션과 분리된 독립 세션. 이 변경에 대한 사전 맥락 없음.
- **날짜**: 2026-09-26
- **절차**: `.claude/skills/feature/SKILL.md` → Phase 6 Option A, `.claude/rules/testing.md`,
  `.claude/rules/writing-style.md` 를 기준으로 수행.

모든 주장에 **[확인함] / [추론] / [미확인]** 을 붙였다. 결함으로 단정한 것은 전부
재현 명령과 실제 출력을 함께 적었다.

**변경 작업 트리는 건드리지 않았다** — 모든 변형(mutation) 실험은
`/tmp/.../scratchpad/mut` 의 복제본에서 했고, 리뷰 종료 시점에
`git status --short` 가 비어 있음을 확인했다. [확인함]

---

## 0. 요약 — 무엇을 머지하지 않겠는가

**전체적으로 이 변경의 품질은 높다.** 특히 훅과 `checkpoint.py` 의 회귀 테스트는
내가 직접 변형을 넣어 확인한 결과 **문서가 주장하는 그대로 물었다**(§2). 자기 한계를
스스로 적어둔 문서(`DESIGN.md` Open Questions, 각 테스트 모듈 docstring)는 내가 측정한
사실과 거의 전부 일치했다 — 이 리포지토리의 정직성 기준은 실제로 지켜지고 있다.

그러나 **현 상태로 머지하지 않을 항목이 두 개**, 머지 전에 한 줄로 고칠 수 있는 항목이
두 개 있다.

| 머지 보류 | 이유 |
|---|---|
| **F1** `/feature` Phase 6 Option A | 문서대로 실행하면 **diff 가 비어 있다.** 이 저장소가 "생략하면 검증 체계에 구멍이 남는다"고 명시한 단계가, 이 변경으로 동작하지 않게 됐다 |
| **F2** `verify-save` 의 무음 의미 변경 | 저장할 때마다 `ruff check --fix` 가 **import 를 지우고**, 종료 코드 0 + 출력 0 으로 끝난다. 모델은 자기 파일이 바뀐 것을 알 수 없다 |

| 머지 전에 고칠 것 (각각 1~3줄) | 이유 |
|---|---|
| **F3** `CLAUDE.md` 공통 명령어 | `poe lint` 은 이 환경에서 **exit 127** 이다. 이 변경이 새로 그것을 가리키는 문장을 추가했다 |
| **F4** `.claude/rules/dev-environment.md` | 이 변경이 다시 쓴 `pyproject.toml` 과 **항상 로드되는 규칙**이 서로 다른 툴체인을 말한다 |

그리고 §2 에 **검증이 검증하지 않는 지점 4개**(변형을 넣어도 312개 테스트가 전부
초록인 지점 3개 + 공허한 테스트 1개)를 재현과 함께 적었다.

---

## 1. 결함 — 심각도 순

### F1 (높음) `/feature` Phase 6 Option A 를 그대로 따르면 diff 가 비어 있다 [확인함]

`.claude/skills/feature/SKILL.md:449-455`:

```
1. `git worktree add --detach ../<project>-review main` 으로 격리하고 ...
2. `git diff main...HEAD` 로 변경 전체를 본다.
```

워크트리를 `main` 에 체크아웃했으므로 그 안에서 `HEAD == main` 이고,
`git diff main...HEAD` 는 **아무것도 출력하지 않는다.**

재현:

```sh
$ git worktree add --detach ../wt-review main
Preparing worktree (detached HEAD 96d763a)
HEAD is now at 96d763a docs: warn that re-copying the template ...
$ cd ../wt-review
$ echo "HEAD=$(git rev-parse --short HEAD)  main=$(git rev-parse --short main)"
HEAD=96d763a  main=96d763a
$ git diff --stat main...HEAD
$                       # ← 출력 없음
```

리뷰 세션은 "변경 없음"을 보고 아무것도 검토하지 않거나, 리뷰할 것을 찾지 못한 채
끝난다. **조용히 실패한다** — 이 저장소가 반복해서 고쳐 온 실패 유형 그대로다
(`DESIGN.md`: "the failure looked like 'no changes' rather than an error").

**이 변경이 만든 모순이다.** [확인함] `origin/main` 의
`.claude/skills/startproject/SKILL.md:159-163` 에는 Phase 6 Option A 가
"1. Start new Claude Code session / 2. Run: `git diff main...HEAD`" 뿐이었고 워크트리
단계가 없었다. 워크트리 문장은 `CLAUDE.md` 운영 주의사항에만 있었고, 이번 재구성이
둘을 같은 절차에 붙였다.

**내부 모순도 같이 생겼다** [확인함]: `README.md:465-472` 는 같은 절차를 **다르게**
적는다 — 워크트리를 `main` 에 두고 `git diff <base>..main` 을 본다. 즉 README 는
"작업이 `main` 에 있다"고 전제하고 `/feature` 는 "작업이 `HEAD` 에 있다"고 전제한다.
둘 중 하나만 맞을 수 있다.

고치는 방향(둘 중 하나):
- 워크트리를 **작업 브랜치**에 체크아웃하고 `git diff main...HEAD` 를 유지, 또는
- 워크트리를 `main` 에 두고 `git diff main...<작업 브랜치>` 를 본다.

어느 쪽이든 `README.md` §5 와 `CLAUDE.md` 운영 주의사항을 같은 커밋에서 맞춘다.

> 참고: 내가 이 리뷰를 수행할 수 있었던 것은 하네스가 **작업 브랜치**를 체크아웃해
> 줬기 때문이고, 문서를 따랐기 때문이 아니다.

---

### F2 (높음) `verify-save` 가 저장할 때마다 파일을 의미적으로 바꾸고, 아무 말도 하지 않는다 [확인함]

`.claude/scripts/verify-save:52-56` 은 `ruff format`, `ruff check --fix`,
`ty check` 를 돌린다. 앞의 두 개는 **파일을 수정한다.** 이 스크립트는
`.claude/hooks/lint-on-save.py` 가 **모든 Edit/Write 직후** PostToolUse 로 호출한다
(`.claude/settings.json` PostToolUse → `Edit|Write`).

#### 재현 1 — 종료 코드 0, 출력 0, 그런데 파일이 바뀌었다

```sh
$ printf 'import os\n\n\ndef f(a: int, b: int) -> int:\n    return  a+b\n' > demo/quiet.py
$ md5sum demo/quiet.py
91e66107f32eeb107605a0bec1922db0  demo/quiet.py
$ out=$(.claude/scripts/verify-save demo/quiet.py 2>&1); echo "exit=$? output=[$out]"
exit=0 output=[]
$ md5sum demo/quiet.py
38e9ff92efefaf086113fdaa5e02ccc7  demo/quiet.py
$ cat demo/quiet.py


def f(a: int, b: int) -> int:
    return a + b
```

`import os` 가 사라졌다. 종료 코드는 0, 출력은 완전히 비어 있다.
`lint-on-save.py:163-170` 은 "exit 0 + 출력 없음" 을 침묵으로 처리하므로
**모델에게는 아무 일도 일어나지 않은 것으로 보인다.**

#### 재현 2 — 삭제되는 것은 포맷이 아니라 의미다

```sh
$ cat demo/sideeffect.py
"""Register the plugin by importing it."""

import myproject.plugins.registry  # noqa: F401 -- removed?

import myproject.plugins.side_effects


def main() -> None:
    print("go")
$ .claude/scripts/verify-save demo/sideeffect.py; echo exit=$?
ty check:
error[unresolved-import]: Cannot resolve imported module `myproject.plugins.registry`
 ...
exit=1
$ diff before after
5,6d4
< import myproject.plugins.side_effects
<
```

부수효과 목적의 import 가 삭제됐다. 보고된 출력은 **다른 줄**에 대한 것이었으므로,
삭제 사실은 어디에도 나타나지 않는다.

#### 왜 이것이 계약 위반이 아니라 설계 결함인가

`.claude/scripts/README.md:87` 은 `**파괴적 동작 금지.** 포맷터가 파일을 고치는 것은
허용되지만, 커밋·푸시·배포는 하지 않는다.` 라고 쓴다. 그래서 형식상 계약 위반은
아니다. 문제는 세 가지다.

1. `ruff check --fix` 는 포맷터가 아니다. 선택된 규칙 집합에는 `F`(unused import),
   `B`, `UP`(pyupgrade), `I` 가 들어 있고(`pyproject.toml:29-40`) 그중 여럿은
   **의미를 바꾸는 자동 수정**을 한다.
2. 계약은 변경을 **보고하라고 요구하지 않는다.** 그리고 `README.md:44-46` 은 침묵을
   "할 말이 없다"는 뜻으로 못 박아 뒀다. 여기서 침묵은 "네 파일을 다시 썼다"는 뜻이다.
3. 이 훅은 **모델이 방금 쓴 파일**을 바꾼다. 이후 같은 파일에 대한 Edit 은 모델이
   기억하는 내용과 디스크가 달라 실패하거나, 더 나쁘게는 모델이 이미 없는 import 를
   전제로 추론한다. [추론 — Claude Code 의 파일 상태 추적 내부는 이 세션에서 확인할 수
   없다. 디스크가 바뀐다는 사실은 위에서 확인했다]

`/initproject` Step 8 은 "포맷터를 켰다면 첫 편집 후 `git diff` 를 확인하라는 안내"를
보고에 넣으라고 한다 — 즉 설계자도 이 위험을 알고 있었다. 하지만 **이 저장소 자신의
`verify-save` 는 그 안내 없이 `--fix` 를 켜고 있다.**

최소 수정안:
- 저장 티어에서 `--fix` 를 빼고 `ruff check` 만 돌린다(게이트가 `poe fix` 를 이미
  갖고 있다), 또는
- 파일 해시를 전후로 비교해 바뀌었으면 `stderr` 에 "이 파일을 다시 썼다"를 **반드시**
  출력한다. 계약을 "변경했으면 침묵하지 않는다"로 한 줄 늘리는 쪽이 낫다.

#### 어떤 테스트도 이것을 잡지 못한다 [확인함]

`tests/test_verify_scripts.py:250-255` 의 `SaveTierContractTests` docstring 은
스스로 이렇게 적는다: *"Only paths it must ignore are used, so nothing runs and
nothing is mutated."* 즉 **실제 `.py` 파일로 `verify-save` 를 돌리는 테스트는 하나도
없다.** 빈 인자 / 없는 파일 / 디렉터리 / 확장자 없는 파일 4가지만 넣는다. 그것이
이 동작이 눈에 띄지 않은 이유다.

---

### F3 (중상) `CLAUDE.md` 의 `공통 명령어` 가 실행되지 않는다 [확인함]

`CLAUDE.md:192-197`:

```
- 공통 명령어
    ```
    poe lint
    poe test
    poe all
    ```
```

```sh
$ poe lint; echo "exit=$?"
/bin/bash: line 1: poe: command not found
exit=127
$ uv run poe lint; echo "exit=$?"
Poe => ruff check .
All checks passed!
exit=0
```

`poe` 는 프로젝트 환경 안에만 있다. 올바른 형태는 `uv run poe …` 이고,
`.claude/scripts/verify-task:19` 자신이 `exec uv run poe all` 을 쓴다.

**이 변경이 문제를 확대했다** [확인함]: 새로 추가된 `CLAUDE.md` 검증 원칙이
`검증 명령은 발명하지 않는다 — … 더 좁은 범위는 아래 `공통 명령어`` 라고 **그 블록을
가리킨다**(`CLAUDE.md:173-174`). `.claude/rules/testing.md` 의 `## 명령` 절도 같은 곳을
가리킨다. 즉 "명령을 발명하지 말고 여기를 보라"가 가리키는 곳이 exit 127 이다.
`.claude/rules/dev-environment.md:150` 도 같은 맨몸 `poe all` 을 적는다.

브랜치의 커밋 `456085` 는 "repair the quality gate — uv run" 이라는 제목으로 스크립트
쪽의 `uv run` 을 고쳤지만, 모델이 실제로 읽는 항상-로드 문서는 고치지 않았다.

---

### F4 (중) 항상 로드되는 `dev-environment.md` 가 이 변경이 다시 쓴 `pyproject.toml` 과 어긋난다 [확인함]

`.claude/rules/dev-environment.md` 는 `paths:` 프런트매터가 없어 **매 세션 로드된다**
(`AlwaysLoadedBudgetTests._always_loaded` 가 실제로 이 파일을 세는 것으로 확인).
이 브랜치는 `pyproject.toml` 을 크게 다시 썼지만 이 규칙 파일은 손대지 않았다
(`git log -1 -- .claude/rules/dev-environment.md` → `e96c71c chore: initial import`).

| 규칙 파일이 말하는 것 | 실제 (`pyproject.toml`) |
|---|---|
| `target-version = "py312"` (57행) | `target-version = "py311"` (27행), `requires-python = ">=3.11"` |
| `uv run ty check src/` (79, 147, 157행), `typecheck = "ty check src/"` (130행) | `typecheck = "ty check .claude/hooks .claude/skills/checkpointing/checkpoint.py"`. `src/` 는 존재하지 않는다 |
| `all = ["lint", "typecheck", "test"]` (132행) | `all = ["lint", "format-check", "typecheck", "test"]` |
| `lint`/`format` 만 (129-131행) | `lint`/`format-check`/`typecheck`/`test`/`all` + `fix`/`format` |

`src/` 항목은 특히 나쁘다 — **거짓 통과**를 만든다:

```sh
$ ls src
ls: cannot access 'src': No such file or directory
$ uv run ty check src/ ; echo "exit=$?"
WARN No python files found under the given path(s)
error[io]: `/home/user/claude-code-orchestrator/src`: No such file or directory (os error 2)
Found 1 diagnostic
exit=0
```

이 브랜치는 `pytest` 설정에서 `pythonpath = ["src"]` 를 **의도적으로 지웠다.** 즉
`src/` 전제는 다른 곳에서는 모두 폐기됐고, 항상 로드되는 규칙 하나에만 남았다.
`/initproject` Step 6 은 채택 프로젝트에서 이 파일을 다시 쓰라고 지시하지만
(`.claude/skills/initproject/SKILL.md:200`), **이 저장소 자신에게는 그 단계가 적용된
적이 없다.**

---

### F5 (중) `checkpoint.py --full` 에서 rename 된 파일이 사라진다 [확인함]

`get_file_changes` (`checkpoint.py:256-261`) 는 `A` / `M` / `D` 만 분류한다.
`git log --name-status` 는 rename 을 `R<점수>` 로 내므로 세 분기 어디에도 걸리지
않고 **조용히 버려진다.** `get_file_stats` 는 같은 줄에서 `old => new` 를 파일명으로
받아 쓸 수 없는 키를 만든다.

재현 (2 커밋 저장소, 두 번째 커밋이 rename + 1줄 추가):

```sh
$ git log --name-status --pretty=format: HEAD~1..HEAD
R075	a.txt	b.txt
$ git log --numstat --pretty=format: HEAD~1..HEAD
1	0	a.txt => b.txt
$ python3 -c '... get_file_changes(), get_file_stats() ...'
changes: {"created": [], "modified": [], "deleted": []}
stats  : {"a.txt => b.txt": [1, 0]}
```

`generate_full_checkpoint:618-620` 은 이 경우 `No file changes detected.` 를 쓴다.

**이 브랜치 자신이 rename 3개를 포함한다** [확인함] —
`git log --name-status --pretty=format: origin/main..HEAD | grep -cE '^R[0-9]'` → `3`:

```
R084  .claude/skills/startproject/SKILL.md      -> .claude/skills/feature/SKILL.md
R100  .claude/skills/startproject/references/... -> .claude/skills/feature/references/...
R099  .claude/skills/init/SKILL.md              -> .claude/skills/initproject/SKILL.md
```

`--find-renames` 를 끄거나(`--no-renames`) `R` 을 `deleted + created` 로 기록하면
해결된다. `FileStatsRangeTests` 의 불변식("changed 로 나온 모든 파일은 line count 를
가진다")은 rename 이 changed 에서 빠지기 때문에 **여전히 통과한다** — 즉 이 테스트는
이 결함을 구조적으로 볼 수 없다.

---

### F6 (중) `checkpoint.py --full` 의 요약이 서로 다른 범위를 섞는다 [확인함]

`--since` 없이 실행할 때:

- `get_git_commits` (`:172-195`) → `git log -n 100` — **범위 제한 없음, 전체 히스토리**
- `get_file_changes` / `get_file_stats` → `resolve_commit_range()` → **`HEAD~10..HEAD`**

실제 출력:

```
## Summary

- **Commits**: 50
- **Files changed**: 29 (26 modified, 3 created, 0 deleted)
```

`Commits: 50` 은 전체 히스토리, `Files changed: 29` 는 마지막 10 커밋만이다. 나란히
놓여 있어 같은 범위처럼 읽힌다.

이 브랜치의 커밋 `5d484b5`("get_file_stats walked HEAD~10 …")가 두 **파일** 워커를
`resolve_commit_range` 로 통일했지만, **커밋 워커는 통일하지 않았다.**
`DESIGN.md` 의 정정문("Only `get_file_changes` had been switched …")이 같은 종류의
누락을 한 번 기록했는데, 세 번째 호출 지점이 남아 있다.

---

### F7 (중) `/feature` 의 티어 어휘 테스트가 공허하다 [확인함]

`tests/test_feature_workflow.py:192-202`:

```python
def test_the_skill_uses_the_contract_tier_names(self) -> None:
    body = text()
    for tier in self.TIERS:
        self.assertIn(
            f"verify-{tier}" if tier != "save" else "verify-save",
            body + (REPO / ".claude" / "scripts" / "README.md").read_text(...),
            ...
        )
```

`.claude/scripts/README.md` 는 네 이름을 **항상** 담고 있으므로, 이 단정은
`/feature` SKILL.md 의 내용과 무관하게 참이다.

재현 — `/feature` SKILL.md 에서 `verify-*` 를 전부 지워도 초록:

```sh
$ sed -i 's/verify-save/VS/g; s/verify-task/VT/g; s/verify-unit/VU/g; s/verify-full/VF/g' \
    .claude/skills/feature/SKILL.md
$ grep -c "verify-" .claude/skills/feature/SKILL.md
1
$ uv run pytest tests/test_feature_workflow.py -q -k TierVocabulary
2 passed, 7 deselected in 0.01s
```

모듈 docstring 은 이것을 "W3 the verification tier vocabulary matches the project's
contract" 로 소개하고, 자기 자신을 drift tripwire 로 정직하게 표시한다. 그러나
tripwire 는 최소한 **사라지면 물어야** 한다. 이것은 물지 않는다. 실패 메시지
("the {tier} tier has no entrypoint name anywhere")만 정확하다.

수정: `body` 만 대상으로 하거나, 두 파일을 각각 별도 단정으로 나눈다.

---

### F8 (중) 실행자(general-purpose)에게 "규칙을 보라"고 하면서 "복제하지 말라"고 한다 [확인함/추론]

이 변경이 `.claude/agents/general-purpose.md:10-14` 에 추가한 문장:

> **agy 를 쓸 수 없을 때**: `…/agy-probe` 로 상태를 확인하고
> `.claude/rules/antigravity-delegation.md` 의 "agy 가 없을 때" 절을 따른다. …
> **이 문구를 복제하지 않는다 — 규칙이 단일 출처다.**

같은 변경의 `.claude/rules/antigravity-delegation.md` 는 정확히 반대의 근거를 세운다:

> **서브에이전트가 이 파일을 받는지는 보장되지 않는다.** … **그래서 실행에 필요한
> 것은 서브에이전트 자기 파일에 둔다**

`DESIGN.md` 의 Key Decision 도 같다 — *"anything an executor MUST have is duplicated
into `.claude/agents/general-purpose.md` on purpose, and a test asserts it is still
there"*. 그런데 그 테스트
(`test_the_executor_still_has_the_syntax_it_needs`)는 **agy 플래그 3개와 읽기 전용
문장만** 확인한다. 대체 경로(폴백 사다리)는 확인하지 않는다.

확인한 사실 [확인함]: `general-purpose.md` 에는 `MISSING`/`UNAUTHENTICATED`/
`DEGRADED` 문자열도, `WebSearch`로 대체하라는 지시도 없다
(`grep -n "MISSING\|UNAUTHENTICATED\|DEGRADED" .claude/agents/general-purpose.md`
→ 매치 없음).

완화 요소 [확인함]: `/feature` Phase 1 B 는 대체 경로 전문을 **Task 프롬프트에 직접**
써 넣는다. 따라서 `/feature` 경로로 들어온 서브에이전트는 필요한 것을 받는다.
남는 위험은 오케스트레이터가 프롬프트에 넣지 않은 경우 — 즉 이 문장이 대비하려는
바로 그 경우다. [추론]

---

### F9 (낮음~중) `DESIGN.md` 가 "MCP 도구 이름은 템플릿에 없다"고 단정하지만 있다 [확인함]

`DESIGN.md` Key Decision:

> No Confluence space, parent page or MCP tool name in the template. … **Tests
> assert both absences**

`.claude/skills/doc-write/SKILL.md:67-69`:

> Atlassian MCP 도구로 먼저 확인한다 — 도구 이름은 커넥터 설정에 따라 다르므로 이
> 세션에 실제로 있는 이름을 쓴다 (`atlassianUserInfo` /
> `getAccessibleAtlassianResources` 계열).

`atlassianUserInfo` 와 `getAccessibleAtlassianResources` 는 실제 커넥터의 정확한 도구
이름이다(이 세션에도 `mcp__…__atlassianUserInfo` 로 존재한다 [확인함]).

그리고 그 "absence 를 단정하는 테스트"
(`tests/test_doc_write_skill.py:143-149`)는 이것만 본다:

```python
self.assertNotIn("mcp__", skill_text())
self.assertIn("커넥터 설정에 따라 다르므로", skill_text())
```

즉 금지하는 것은 **`mcp__` 접두사**뿐이다. 모듈 docstring 의 D3("it must not
hard-code … an MCP tool name")과 실제 단정이 다르다.

실질 피해는 작다 — 바로 다음 문장이 "이 세션에 실제로 있는 이름을 쓴다"로 방어하고
있고, 예시 이름은 힌트로 유용하다. 하지만 **`DESIGN.md` 의 단정은 사실이 아니고,
테스트는 그 단정을 지키지 않는다.** 이 저장소의 정직성 기준으로는 고쳐야 한다:
`DESIGN.md` 를 "접두사 없는 예시 이름은 힌트로 허용한다"로 바로잡거나, 테스트를
D3 대로 강화한다.

---

### F10 (낮음) 항상-로드 예산 docstring 의 측정값이 낡았다 [확인함]

`tests/test_template_consistency.py:253, 265`:

> That layer had grown to 57,378 bytes … **It is now 48,236.**
> `# Measured 2026-09-26 after the routing-rule cut: 48,236 bytes.`

실측 (같은 `_always_loaded()` 선택 로직으로 계산):

```
  12291  CLAUDE.md
  12754  .claude/rules/antigravity-delegation.md
   1387  .claude/rules/coding-principles.md
   7061  .claude/rules/deep-reasoning-delegation.md
   2688  .claude/rules/dev-environment.md
    809  .claude/rules/language.md
   1710  .claude/rules/security.md
   7332  .claude/rules/testing.md
   2571  .claude/rules/writing-style.md
TOTAL 48603   (budget 53000)
```

367 바이트 차이. 이후 커밋(`bad487b`, `45c4afa`)이 문서를 늘린 결과로 보인다.
[추론] 예산 자체는 지켜지고 있으므로 테스트는 초록이다. 다만
`.claude/rules/writing-style.md` 의 "측정하지 않은 것을 측정한 것처럼 쓰지 않는다"를
이 저장소가 자기 테스트 docstring 에 적용하려면 갱신해야 한다.

참고로 같은 문단의 다른 두 측정값은 **정확히 맞았다** [확인함]:
`antigravity-delegation.md` = 12,754 바이트, `.claude/docs/writing-style.md` = 466 행.

---

### F11 (낮음) `README.md` 가 적은 테스트 명령은 0개를 돌리고 성공한다 [확인함]

`README.md:94`: `├── tests/ # 훅 단위 테스트 (python3 -m unittest)`

```sh
$ python3 -m unittest 2>&1 | tail -3
Ran 0 tests in 0.000s

OK
$ python3 -m unittest discover -s tests 2>&1 | tail -3
Ran 312 tests in 5.224s

OK
```

문서를 그대로 따르면 **아무것도 돌리지 않고 초록을 보고한다.** 이 저장소가
`.claude/rules/testing.md` 원칙 2 에서 금지하는 바로 그 형태다. `discover -s tests`
를 적거나 `uv run pytest` 로 바꾼다.

---

### F12 (낮음) 새 권한 허용이 모델이 스스로 쓰는 스크립트의 실행을 사전 승인한다 [추론]

이 변경은 `.claude/settings.json` 에 두 줄을 더한다:

```json
"Bash(.claude/scripts/*)",
"Bash(.claude/skills/antigravity-system/agy-probe)"
```

`/initproject` Step 5 는 **`.claude/scripts/verify-*` 를 모델이 작성한다**고 정의한다.
따라서 이 허용은 "모델이 방금 쓴 셸 스크립트를 프롬프트 없이 실행한다"를 뜻한다.
기존 허용 목록이 이미 넓으므로(`Bash(curl:*)`, `Bash(docker:*)`, `Bash(source:*)`,
`Bash(chmod:*)`, `Bash(pkill:*)`) 실질적 증분은 작지만, 검증 계약이 자기 실행 권한까지
포함한다는 점은 명시해 둘 가치가 있다. `.claude/scripts/README.md` 는 권한에 대해
아무 말도 하지 않는다. [확인함 — README 에 "권한"/"permission" 문자열 없음]

---

### F13 (낮음, 기존 결함) 설계 리뷰 알림이 거의 모든 쓰기에서 울린다 [확인함]

`.claude/hooks/suggest-deep-reasoning-before-write.py:85-88`:

```python
if content:
    if len(content) > 500:
        return True, "Creating new file with significant content"
```

500자를 넘는 모든 Write, 그리고 경로에 `design`/`model`/`config`/`settings`/`core/`
가 들어간 모든 Edit 에서 `[Design Review Reminder]` 가 붙는다.

같은 저장소의 `lint-on-save.py:100-107` 은 정반대를 명시한다:

> Repeating the notice on every save **trains people to ignore hook output.**

**이 리뷰 세션에서 실제로 관측했다** [확인함]. 이 리포트 파일(`review-report.md`,
마크다운, 설계와 무관)을 Write 할 때 하네스가 이것을 주입했다:

```
[Design Review Reminder] Creating new file with significant content. Consider
consulting the deep-reasoning subagent before this change.
```

**이 변경이 만든 것은 아니다** [확인함] — 이 파일의 diff 는 서식과 타입 힌트뿐이다.
다만 이 변경이 이 훅에 트리거/침묵 테스트를 붙여 현재 동작을 **고정**했으므로,
다음에 임계값을 조정할 때 테스트도 함께 고쳐야 한다는 사실만 남겨 둔다.

---

## 2. 검증이 실제로 검증하는가

이 항목은 이 저장소의 기준(`.claude/rules/testing.md` 원칙 2 — "통과만 확인한 것은
검증이 아니다")에 따라 **내가 직접 코드를 깨뜨려서** 판정했다. 모든 변형은 복제본에서
수행하고 매번 되돌렸다.

### 2.1 물었다 — 문서의 주장이 사실인 부분

`tests/test_hook_effects.py` docstring 은 변형 실험 결과표를 싣고 있다. **그 표를
재현했고, 전부 맞았다.** [확인함]

`main()` 첫 줄에 `return` 을 넣는 변형(no-op 훅) 8개:

| 훅 | `test_hook_contract.py` | `test_hook_effects.py` |
|---|---|---|
| agent-router.py | 13 passed | **2 failed** |
| suggest-deep-reasoning-before-write.py | 13 passed | **1 failed** |
| suggest-antigravity-research.py | 13 passed | **1 failed** |
| suggest-deep-reasoning-after-plan.py | 13 passed | **1 failed** |
| post-test-analysis.py | 13 passed | **1 failed** |
| log-cli-tools.py | 13 passed | **1 failed** |
| lint-on-save.py | 13 passed | **4 failed** |
| post-implementation-review.py | 13 passed | **2 failed** |

"항상 발화" 변형 4개 — 전부 `test_hook_effects.py` 에서 실패:

| 변형 | 결과 |
|---|---|
| `has_complex_failure` → `return True` | 3 failed |
| `should_suggest_review` → `return True` | 4 failed |
| `detect_agent` → `return "deep-reasoning"` | 2 failed |
| `is_source_file` → `return True` | 1 failed |

`checkpoint.py` 회귀 4개 — 전부 `test_checkpoint_hardening.py` 에서 실패:

| 되돌린 수정 | 실패한 테스트 |
|---|---|
| 펜스 인식 제거 | `SectionBoundaryTests::test_a_tilde_fence_is_honoured_too` (외 2) |
| 백업 생성 제거 | `AtomicWriteTests::test_write_is_atomic_and_keeps_a_backup` (외 1) |
| `HEAD~depth` 하드코딩 복원 | `FileStatsRangeTests::test_the_two_walkers_agree_on_which_files_changed` (외 3) |
| 깨진 타임스탬프 통과 | `LogParsingTests::test_a_missing_timestamp_is_skipped_not_fatal` (외 2) |

그 외:

| 변형 | 결과 |
|---|---|
| `/lens-review` 의 `500줄` → `300줄` | `LargeChangeThresholdTests::test_every_site_uses_the_same_line_count` **실패** |
| `post-implementation-review` 상태를 세션 공유로 되돌림 | 2 failed |
| 상태 정리(pruning) 무력화 | 1 failed |
| `MIN_FILES_FOR_REVIEW` 3 → 300 | 4 failed |
| `log-cli-tools` 의 셸 인식 토크나이즈 제거 | 11 failed |

**판정**: 훅과 `checkpoint.py` 의 회귀 테스트는 **진짜 검증이다.** 실패해야 할 때
실패한다. 이 저장소가 스스로 적어둔 측정값이 정확했다.

### 2.2 물지 않았다 — 전체 312개 테스트가 초록인 변형 3개 [확인함]

세 가지는 **전체 스위트를 돌려도** 잡히지 않는다. 각각 문서가 "고쳤다"고 기록한
항목이다.

#### G1. `post-implementation-review.py` 의 심볼릭 링크 거부 — 테스트 없음

```sh
# save_state 의  if path.is_symlink(): return  →  if False: return
$ uv run pytest -q | tail -1
312 passed in 5.40s
```

훅 자신의 docstring(결함 #2)과 `DESIGN.md` 가 모두 "symlinks refused" 를 고친 결함으로
기록하고 "16 regression tests" 를 붙였다. **그 16개 중 어느 것도 이것을 보지 않는다.**
(`tests/test_post_implementation_review.py` 만 돌려도 16 passed.)
`agy-probe` 쪽에는 심볼릭 링크 심기 테스트가 있는데, 여기에는 없다.

#### G2. `log-cli-tools.py` 의 soft-deny 판정 — 테스트 없음

```sh
# determine_success 의  if any(marker in stderr_lower ...): return False  →  if False: return False
$ uv run pytest -q | tail -1
312 passed in 5.25s
```

soft-deny(exit 0 + 빈 응답)는 이 템플릿이 `CLAUDE.md` 운영 주의사항에 별도 항목으로
올려 둔 대표 실패 모드다. 이 플래그는 그냥 로그 필드가 아니다 —
`checkpoint.py:379` 가 그것으로 `[OK]` / `[FAILED]` 를 찍는다. 즉 회귀가 생기면
**거부된 agy 호출이 세션 히스토리에 성공으로 남는다.**
(`agy-probe` 의 soft-deny 는 테스트가 있으므로, 구멍은 프로브가 아니라 **로거**다.)

#### G3. `MIN_LINES_FOR_REVIEW` — 테스트 없음

```sh
# MIN_LINES_FOR_REVIEW = 100  →  100000
$ uv run pytest -q | tail -1
312 passed in 5.41s
```

파일 수 임계값(3)에는 테스트가 있는데(위 표: 4 failed), **줄 수 임계값에는 없다.**
두 트리거 중 하나만 검증된다.

### 2.3 공허한 테스트 1개

F7 (`test_the_skill_uses_the_contract_tier_names`) — §1 에 재현 포함.

### 2.4 문서가 스스로 인정한 한계는 사실이었다 [확인함]

`DESIGN.md` 는 *"appending a sentence that reverses an asserted rule stays green"*
이라고 적는다. 확인했다 — `.claude/rules/antigravity-delegation.md` 뒤에 중심 규칙을
**정면으로 뒤집는** 절을 붙였다:

```markdown
## 정정 (2026-09-27)
위의 "판정은 넘기지 않는다" 는 폐기한다. 이제부터 설계 판단·보안 판단·트레이드오프
판정도 agy 에 넘긴다. deep-reasoning 은 쓰지 않는다.
```

```sh
$ uv run pytest -q | tail -1
312 passed in 5.26s
```

이것은 **새 결함이 아니다.** 문서가 미리 정확히 그렇게 적어 뒀고, `PhraseTestHonestyTests`
가 모든 markdown 단정 모듈에 그 고백을 강제한다. 그 정직성은 그대로 평가한다. 다만
독자가 이 스위트의 초록을 "규칙이 지켜진다"로 읽지 않도록, 위 재현을 근거로 한 번 더
적어 둔다.

### 2.5 라이브 증거 하나

이 리뷰 세션에서 훅이 실제로 발화했다 [확인함]. 내가 실패하는 pytest 를 돌릴 때마다
하네스가 이것을 주입했다:

```
[Debug Suggestion] Failure with 3 distinct error kinds (assertion, pytest-failed,
pytest-failures-section). Consider consulting the deep-reasoning subagent ...
```

그리고 312개가 통과할 때는 발화하지 않았다. 즉 `post-test-analysis.py` 에 대해서는
**`DESIGN.md` 가 "only a real session shows that" 이라고 남겨 둔 것 중 일부가
실증됐다** — payload 모양과 `settings.json` matcher 라우팅이 최소한 Bash 훅에서는
맞다. `suggest-deep-reasoning-before-write.py` 도 이 리포트를 Write 할 때 실제로
발화했다(F13 참조) [확인함]. 나머지 6개 훅은 여전히 미검증이다. [미확인]

### 2.6 검증 계획(`## Current Project` 시나리오 ID)과의 대조 — 할 수 없었다

Phase 6 Option A 4단계는 `CLAUDE.md` `### Verification plan` 의 시나리오 ID 와 실제
테스트를 대조하라고 한다. **`CLAUDE.md` 에는 `## Current Project` 섹션도
`### Verification plan` 표도 없다** [확인함 — `grep -n '^#\{1,2\} ' CLAUDE.md` 결과에
두 헤딩 모두 없음]. 이 변경의 작업 단위 자체가 `/feature` Phase 5 를 거치지 않았다는
뜻이다.

대신 `DESIGN.md` 의 TODO 항목이 시나리오 ID 를 부분적으로 담고 있어 그것으로 대조했다:

| `DESIGN.md` 가 말하는 ID | 실재하는가 |
|---|---|
| `C1-C7` (checkpoint) | `tests/test_checkpoint_hardening.py` 에 존재, 위 2.1 에서 4개를 변형으로 확인 [확인함] |
| `R1-R6` (post-implementation-review) | 존재. 단 §2.2 G1 이 커버되지 않음 [확인함] |
| `V1…` (`/feature` 검증 계획 표) | **어디에도 없음** — 이 작업 단위에는 검증 계획이 기록되지 않았다 [확인함] |

즉 **Phase 6 Option A 의 핵심 대조 단계는 이 변경에 대해 수행 불가능하다.** F1 과
합치면, 이 변경은 자기 자신의 리뷰 절차를 두 군데에서 만족시키지 못한다.

---

## 3. 특정 스택·장비·개인 환경에 묶이는 지점

템플릿이 남의 프로젝트로 복사된다는 점에서 본 항목.

| 위치 | 무엇이 묶여 있는가 | 판정 |
|---|---|---|
| `.claude/rules/dev-environment.md` (**항상 로드**) | uv / ruff / ty / marimo / `src/` / py312 를 규범으로 서술 | **F4.** `/initproject` Step 6 이 다시 쓰라고 하지만, 이 저장소 자신에게 적용되지 않았고 항상-로드 레이어에 남아 있다 |
| `.claude/settings.json` → `"env": {"EDITOR": "code --wait"}` | **VS Code 가 설치된 개인 환경**을 전제 | 기존 항목. `/initproject` Step 6 의 파일 표에 `settings.json` 행이 있지만 `env` 는 언급하지 않는다 → 채택 프로젝트에서 그대로 남는다 [확인함] |
| `settings.json` 훅 커맨드의 `python3` | `python3` 가 PATH 에 있고 3.10+ 인 전제 (훅 코드가 `X \| None` 문법 사용) | 기존 항목. Windows 기본 설치에는 `python3` 가 없다. `verify-*` 해석기 목록은 Windows 를 배려하는데(`.ps1`/`.cmd`) 훅 등록은 배려하지 않는다 — **비대칭** [추론] |
| `.claude/scripts/verify-save`, `verify-task` | uv / ruff / ty / poe | **의도된 것.** `README.md:111-118` 이 "이 저장소 자신의 구현이고 참고 답안이 아니다"라고 명시 [확인함] |
| `tests/test_template_consistency.py` | 이 저장소 전용 | **의도된 것.** docstring 이 "A project adopting the template does not need them" 이라고 명시 [확인함] |
| `tests/test_verify_scripts.py` | 언어 무관하게 작성 | **좋다.** 실제로 스텁으로만 구동한다 [확인함]. 단 `Quick Start` 의 `cp` 명령은 `tests/` 를 복사하지 않으므로, "copy it" 지시와 Quick Start 가 어긋난다 [확인함, 낮음] |
| `agy-probe` | `mktemp`, `command -v`, POSIX sh | 이식성 양호. Windows 에서는 안 돈다 [추론] |
| 모델 슬러그 (`gemini-3.7-flash-low` 등) | Gemini 슬러그가 유지된다는 전제 | `ModelTierConsistencyTests` 가 **사이트 간 일치**만 보장한다. 슬러그가 폐기되면 전부 함께 틀린다 — 문서가 이 한계를 적지 않았다 [확인함] |

**긍정 평가**: `lint-on-save.py` 는 실제로 어떤 도구 이름도 담지 않는다
(`grep -n "ruff\|ty \|pytest\|npm" .claude/hooks/lint-on-save.py` → 매치 없음
[확인함]). `post-implementation-review.py` 의 배제 기반 소스 판별도 언어 하드코딩을
실제로 제거했다. 이 변경의 핵심 목표는 달성됐다.

---

## 4. 내부 모순 — 두 파일이 같은 규칙을 다르게 말하는 곳

| # | 모순 | 근거 |
|---|---|---|
| 1 | 리뷰 워크트리를 어느 ref 에 두고 무엇을 diff 하는가 | `/feature` Phase 6 = `main` 체크아웃 + `main...HEAD`(빈 diff) / `README.md` §5 = `main` 체크아웃 + `<base>..main`. **F1** |
| 2 | 저장 티어가 파일을 고쳐도 되는가, 고쳤으면 말해야 하는가 | `scripts/README.md:87` 은 허용, `:44-46` 은 침묵을 "할 말 없음"으로 정의. 실제로는 침묵하며 import 를 지운다. **F2** |
| 3 | 품질 명령이 무엇인가 | `CLAUDE.md:192` = `poe lint`(exit 127) / `verify-task:19` = `uv run poe all`(정상) / `dev-environment.md:147` = `uv run …` 체인 / `:150` = `poe all`. **F3** |
| 4 | 타입 체크 대상과 파이썬 버전 | `dev-environment.md` = `src/`, py312 / `pyproject.toml` = `.claude/hooks`, py311. **F4** |
| 5 | 실행자가 규칙 파일을 받는다고 가정해도 되는가 | `general-purpose.md:10-14` = 규칙을 보라 + 복제 금지 / `antigravity-delegation.md` = 보장되지 않으니 실행자 파일에 둬라. **F8** |
| 6 | 템플릿에 MCP 도구 이름이 있는가 | `DESIGN.md` = 없다, 테스트가 단정한다 / `doc-write/SKILL.md:69` = 두 개 있다 / 테스트 = `mcp__` 접두사만 금지. **F9** |
| 7 | 항상-로드 레이어의 크기 | docstring = 48,236 / 실측 = 48,603. **F10** |
| 8 | `/feature` 단계 번호 체계 | `/feature` = Phase 1, 2, 2b, 3, 4, 4b, 5, Implementation Loop, 6 / `CLAUDE.md` 진행 순서 = 1~8 (승인이 **5번**). `DESIGN.md` 는 "Phase N is a public name … phases are never renumbered" 라고 못 박았지만, `CLAUDE.md` 의 번호는 그 이름 체계와 다르다. `PhaseReferenceTests` 는 `Phase N` 형태만 해석하므로 이 불일치를 보지 않는다 [확인함, 낮음] |
| 9 | 테스트 실행 명령 | `README.md:94` = `python3 -m unittest`(0개 실행) / `pyproject.toml` = `pytest`. **F11** |
| 10 | rename 을 checkpoint 가 본다 | `--full` 은 "Git commits and file changes" 를 포함한다고 출력하지만, rename 은 "No file changes detected." 가 된다. **F5** |

**존재하지 않는 대상을 가리키는 포인터**는 전수 스캔했고 [확인함], 실질적인 dangling
은 없었다. 걸린 것은 전부 산출물(`.claude/logs/`, `.claude/checkpoints/`), 이 저장소가
설정하지 않았다고 명시한 티어(`verify-unit`, `verify-full`), 또는 문서 안의 예시
(`_lib.sh`, `tests/test_user.py`)였다. 스캔 방법:

```python
pat = re.compile(r"(?<![\w/])((?:\.claude|\.agents|tests|\.github)/[A-Za-z0-9_./{}<>*-]+)")
# 모든 *.md 에서 추출 → (REPO/ref).exists() 확인
```

`SectionPointerTests` 가 섹션 앵커까지 해석하는 것도 확인했다 — 그 부분은 실제로
구조를 비교하는 테스트다 [확인함].

---

## 5. 내가 보지 않은 것 (커버리지 고백)

이 리뷰는 **코드와 스크립트에 깊이, 문서에 넓이, 새 스킬의 실행에는 전혀** 들어가지
않았다. 아래를 그대로 읽어 주기 바란다.

**전혀 실행하지 못한 것**
- `/feature`, `/initproject`, `/lens-review`, `/doc-write`, `/jira-setup`, `/ticket`
  — **한 번도 돌리지 않았다.** `DESIGN.md` Open Questions 가 적은 그대로다.
- agy 관련 실제 동작 전부. 이 컨테이너에 agy 가 없다
  (`command -v agy` → 없음, `agy-probe` → `MISSING`, exit 1 [확인함]). 따라서
  모델 정책, soft-deny 실동작, `--print-timeout 60s` 값의 유효성, T1~T4 품질 차이는
  전부 **[미확인]**.
- Jira / Confluence 커넥터 동작. `DESIGN.md` 가 "measured against a real connector"
  라고 적은 141개 프로젝트·`cloudId` 중복 등은 **검증하지 않았다** — 재측정 수단이 없다.
- Windows. 해석기 해석 테스트(`.py` 를 실행 권한 없이 찾는 것)는 Linux 에서 통과하는
  것만 봤고, 실제 Windows 체크아웃은 **[미확인]**.

**읽었지만 변형으로 검증하지 않은 테스트 모듈**
- `tests/test_jira_skills.py` (29), `tests/test_doc_write_skill.py` (16),
  `tests/test_lens_review_skill.py` (30), `tests/test_routing_rules.py` (17),
  `tests/test_hook_contract.py` (13), `tests/test_agy_probe.py` (22 — 스텁 구동
  방식만 확인).
  이들은 대부분 markdown 부분 문자열 단정이고, 각 모듈 docstring 이 스스로
  "drift tripwire, not behavioural coverage" 라고 적는다. §2.4 의 실험은 그 고백이
  사실임을 한 번 보였을 뿐, **모듈별로 확인하지는 않았다.**
- `tests/test_verify_scripts.py` 의 Windows 해석기 케이스와
  `tests/test_agy_probe.py` 의 심볼릭 링크 심기 케이스는 **변형을 넣어보지 않았다.**

**전혀 읽지 않은 파일**
- `.claude/docs/writing-style.md` (466행) 와
  `.claude/docs/templates/writing-style.template.md` (335행) — 두 파일의 **내용**은
  읽지 않았다. 행수와 `doc-write` 가 그것을 전사하지 않는다는 테스트의 존재만 확인했다.
- `.claude/skills/lens-review/SKILL.md`, `jira-setup/SKILL.md`,
  `doc-write/SKILL.md` 는 **일부만** 읽었다(프런트매터, 임계값, 문제된 절).
- `.claude/skills/initproject/references/known-pitfalls.md`,
  `.claude/docs/research/antigravity-cli.md` 는 읽지 않았다.
- `.agents/skills/context-loader/SKILL.md`, `uv.lock` 의 변경 내용.

**구조적으로 판정할 수 없는 것**
- 항상-로드 레이어의 **토큰** 비용. 바이트만 측정했고, 테스트 docstring 이 이미
  "bytes are not tokens" 라고 적는다.
- 프롬프트가 모델의 실제 행동을 바꾸는지. 이 리포지토리 본체가 프롬프트이므로
  **리뷰로 판정 가능한 범위의 바깥**이다.
- 서브에이전트가 `.claude/rules/` 를 받는지. 이 세션에서는 받았다(시스템 프롬프트에
  8개 규칙 파일이 들어와 있다 [확인함]). 그러나 이것은 **메인 세션 관측이고
  서브에이전트 관측이 아니며**, 버전 간 보장도 아니다. `DESIGN.md` 의 신중한 표현이
  옳다.

---

## 6. 머지 판단

**머지 보류 (2건)** — 고치는 데 각각 몇 줄이면 된다:

1. **F1** — `/feature` Phase 6 Option A. 이 저장소가 자기 품질 체계의 마지막 안전판이라
   부르는 절차가 문서대로는 빈 diff 를 낸다. `README.md` §5 와 `CLAUDE.md` 운영
   주의사항을 같은 커밋에서 맞춘다.
2. **F2** — `verify-save` 의 무음 의미 변경. `--fix` 를 빼거나, 파일이 바뀌면 반드시
   보고하도록 계약을 한 줄 늘린다. 그리고 `verify-save` 를 **실제 `.py` 파일로**
   돌리는 테스트를 하나 추가한다 — 그 테스트가 없었기 때문에 이 동작이 남았다.

**같은 커밋에 넣기를 권함 (2건, 각 1~3줄)**: **F3**(`uv run poe`), **F4**
(`dev-environment.md` 를 py311 / `.claude/hooks` / 실제 poe 태스크로 정정).

**후속 티켓으로 충분 (6건)**: F5, F6(checkpoint 의 rename·범위), F7(공허한 테스트),
F8(실행자 폴백 중복), F9(`DESIGN.md` 단정 정정), F10~F12.

**§2.2 의 세 구멍(G1 심볼릭 링크 / G2 soft-deny / G3 줄 수 임계값)은 테스트 3개로
막힌다.** 특히 G2 는 잘못되면 `/checkpointing` 이 거부된 agy 호출을 `[OK]` 로 기록하게
되므로, 이 저장소의 "성공 로그는 검증이 아니다" 원칙에 직접 걸린다.

---

## 부록 — 재현 환경

```
HEAD            45c4afa  (claude/eager-wozniak-wr8agz)
base            96d763a  (origin/main)
uv sync --all-extras  →  pytest 9.0.2, ruff 0.14.14, ty 0.0.84
uv run pytest -q      →  312 passed in 5.21s
Python                   3.11.15
agy                      설치되지 않음 (agy-probe → MISSING, exit 1)
poe (PATH)               없음 (exit 127);  uv run poe → 정상
git status --short       비어 있음 (리뷰 시작 시점과 종료 시점 모두)
```

변형 실험은 전부 `cp -a` 로 만든 복제본에서 수행했고, 각 변형 후 원본으로 되돌렸다.
원본 작업 트리는 이 리포트 파일 외에 어떤 변경도 없다. [확인함]
