# Windows 에서 템플릿 점검하기

저장 검사(`verify-save`)가 Windows 에서 실제로 도는지, 그리고 템플릿의 다른 Windows 경로(agy 프로브, 사용
기록, 격리 리뷰 시작)가 깨지지 않는지 확인한다. 업그레이드 확인은 [windows-upgrade-check.md](windows-upgrade-check.md)
가 따로 맡는다 — 테스터 세션의 방식(`turn` 함수)은 그 문서와 같다.

이미 확인된 것(다시 하지 않는다): Git Bash 에서 `verify-task` 실행(업그레이드 W3), hook-check·upgrade-plan
(업그레이드 W1~W6), 실제 프로젝트의 sh 스크립트 줄바꿈이 LF(2026-10-15, `night clock`).

## Claude 에게 맡기기

🖥️ Git Bash 에서:

```bash
mkdir -p ~/win-check && cd ~/win-check
[ -d template ] || git clone -b claude/windows-save-check https://github.com/GunwooYun/claude-code-orchestrator.git template
claude
```

💬 이 세션(테스터)에 붙여 넣는다:

```text
~/win-check/template/docs/windows-check.md 의 「테스터 세션이 따를 것」을 처음부터 끝까지 따라 해 줘.
끝나면 ~/win-check/REPORT.md 경로만 알려 줘.
```

권한 창이 뜨면 `~/win-check` 안의 일이면 승인한다. W11 은 격리 리뷰를 **$0.5 상한**으로 짧게 띄운다(Fable
모델 권한이 필요하다). 끝나면 `REPORT.md` 를 템플릿 저장소의 Claude 세션에 넘긴다.

## 테스터 세션이 따를 것

너는 테스터다. 아래 시나리오를 돌리고 **있는 그대로 보고**한다. 템플릿 파일을 고치지 않는다. 모든 명령은 Bash
도구(Git Bash)로 한다. Bash 호출 사이에 변수가 남지 않으므로 `~/win-check/env.sh` 에 `R`·`PY`·`turn` 을 저장하고
매번 `source` 한다.

1. **준비.** `R=~/win-check`. `PY` 는 업그레이드 가이드 W1 의 반복문으로 정한다. `turn` 함수는
   `template/docs/windows-upgrade-check.md` 「테스터 세션이 따를 것」 3번의 것을 그대로 쓴다(`blockgh` 는 쓰지 않는다).
   점검용 프로젝트를 만든다 — 저장 검사는 받은 경로를 출력하고 exit 1 로 끝나는 스텁이다(도구 없이 "돌았는가"만 본다):

   ```bash
   P="$R/p-save"; rm -rf "$P"; mkdir -p "$P"
   git -C "$R/template" archive HEAD .claude .agents CLAUDE.md | tar x -C "$P"
   printf '#!/bin/sh\necho "SAVE-CHECK-RAN $1"\nexit 1\n' > "$P/.claude/scripts/verify-save"
   printf '#!/bin/sh\necho "rehearsal gate ok"\n' > "$P/.claude/scripts/verify-task"
   chmod +x "$P/.claude/scripts/verify-save" "$P/.claude/scripts/verify-task"
   git -C "$P" init -q -b main && git -C "$P" add -A && git -C "$P" -c user.name=r -c user.email=r@r commit -qm base
   head -1 "$P/.claude/scripts/verify-save" | od -c | head -1     # \n 으로 끝나야 한다(\r 없음)
   ```

2. **W7 — 저장 검사가 돈다 (Claude 2턴).**
   - `turn "$P" new "Write 도구로 migrations/m.py 파일을 만들고 내용은 x = 1 한 줄로 해 줘. 그 직후 훅이 너에게 보여 준 내용을 한 글자도 바꾸지 말고 인용해 줘."`
   - `turn "$P" "$(cat "$P.sid")" "Bash 로 printf 'y = 2\n' > u.py 를 실행하고, 훅이 보여 준 내용을 그대로 인용해 줘."`
   - **통과:** 두 인용 모두 `SAVE-CHECK-RAN` 이 있고, 경로가 `/` 로 구분돼 있다(`.../migrations/m.py`). 경로에
     `/` 가 있어야 실제 `verify-save` 의 `*/migrations/*` 같은 제외 규칙이 맞는다.
   - **실패:** `could not run`, `WinError`, `no sh was found` 가 보이거나, 훅 내용이 없다. `.turn.json` 의
     전문도 함께 남긴다.
3. **W7b — hook-check (Claude 없이).** `$PY "$R/template/tools/hook-check" "$P"; echo exit=$?`
   **통과:** 3/3 ok, `exit=0`. **실패:** `FAIL … could not run` — 그 줄 그대로 적는다.
4. **W9 — agy 프로브 (Claude 없이).** `cd "$P" && .claude/bin/agy-probe; echo exit=$?`
   **통과:** 첫 단어가 `READY`·`MISSING`·`UNAUTHENTICATED`·`DEGRADED`·`STALE` 중 하나(agy 가 없으면 `MISSING`
   이 정답이다). **실패:** `bad interpreter`, `command not found`, `\r` 이 섞인 오류.
5. **W10 — 사용 기록 (Claude 없이, W7 뒤).** `cd "$P" && $PY .claude/bin/usage-report | head -30`
   **통과:** 세션이 1개 이상 집계되고 Hooks 표에 `lint-on-save.py`·`bash-write-check.py` 가 있다.
   **실패:** "no transcripts" — 그때 `ls ~/.claude/projects | grep -i save` 출력을 적는다(실제 폴더 이름과
   도구가 계산한 이름을 비교하려는 것).
6. **W11 — 격리 리뷰 시작 (Claude 없이, ≤ $0.5).**

   ```bash
   cd "$P" && where claude
   git switch -q -c probe && echo "# probe" >> CLAUDE.md && git -c user.name=r -c user.email=r@r commit -qam probe
   .claude/skills/isolated-review/run-review --base refs/heads/main --budget 0.5 --timeout 3; echo exit=$?
   ```

   **통과:** Python traceback 이 없다. 판정 줄(COMPLETE·INCOMPLETE·FAILED·REFUSED 중 무엇이든)과 리포트 경로가
   나온다 — 예산·시간 상한에 걸린 FAILED 도 통과다(시작이 되는지만 본다). **실패:** `FileNotFoundError`,
   `ValueError: … same drive`, `bad interpreter`, `OSError` — 그대로 적는다. `where claude` 의 결과(`.exe`/`.cmd`)도
   적는다.
7. **보고서** `~/win-check/REPORT.md` — 시나리오마다 판정(통과/실패), 명령 출력 그대로, W7 의 인용 두 개,
   Windows 에서만 보인 것(경로, 인코딩, 권한). 확인하지 못한 것은 [미확인].

정리: `rm -rf ~/win-check`
