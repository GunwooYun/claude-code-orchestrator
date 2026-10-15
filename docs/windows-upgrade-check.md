# Windows 에서 업그레이드 확인하기

`/orchestrator-upgrade` 와 `tools/hook-check` 가 Windows 에서도 동작하는지 사람이 직접 확인하는 가이드다.
같은 시나리오를 macOS 에서는 돌려 봤지만, Windows 에서는 아직 아무도 돌려 보지 않았다. 확인되는 것은 아래
W1~W6 이다. 결과는 맨 아래 양식에 붙여 넣는다.

Windows 에서 따로 확인해야 하는 이유는 세 가지다.

- **Git Bash** — Claude Code 는 Git Bash 로 명령을 실행한다. 템플릿의 훅도 Git Bash 가 있어야 돈다.
- **Python 실행 이름** — Windows 에서는 `python3`, `python`, `py -3` 중 무엇이 되는지가 PC 마다 다르다.
- **임시 폴더 경로** — `mktemp -d` 가 만드는 `/tmp/...` 경로를 Windows 의 Python 과 `rm -rf` 가 제대로
  다루는지.

모든 명령은 **Git Bash** 창에 붙여 넣는다(시작 메뉴 → Git Bash). PowerShell 이 아니다. 💬 는 Claude 세션에
입력하는 것이다.

손으로 하지 않고 **Claude 에게 맡길 수도 있다** — 바로 아래 절. 사람이 할 일은 클론 한 번, 붙여 넣기 한 번,
보고서 전달뿐이다.

---

## Claude 에게 맡기기

🖥️ Git Bash 에서(처음 한 번):

```bash
mkdir -p ~/upg-rehearsal && cd ~/upg-rehearsal
[ -d template ] || git clone -b claude/orchestrator-upgrade https://github.com/GunwooYun/claude-code-orchestrator.git template
claude
```

💬 이 세션(테스터)에 붙여 넣는다:

```text
~/upg-rehearsal/template/docs/windows-upgrade-check.md 의 「테스터 세션이 따를 것」을 처음부터 끝까지 따라 해 줘.
끝나면 ~/upg-rehearsal/REPORT.md 경로만 알려 줘.
```

테스터는 W1~W6 을 돌리는 동안 Claude 세션을 여러 번 새로 띄운다(헤드리스 `claude -p`). 권한을 묻는 창이 뜨면
리허설 폴더(`~/upg-rehearsal`) 안의 일이면 승인한다. 비용은 대략 $5~10, 시간은 30~60분이다[추론: macOS 에서
같은 시나리오가 그 정도였다]. 끝나면 `REPORT.md` 내용을 그대로 템플릿 저장소의 Claude 세션에 붙여 넣는다.

### 테스터 세션이 따를 것

너는 테스터다. 이 문서의 시나리오를 돌리고 **있는 그대로 보고**한다. 템플릿 파일(`~/upg-rehearsal/template`
안의 코드·문서)을 고치지 않는다. 실패는 고치지 말고 출력과 함께 적는다. 모든 명령은 Bash 도구(Git Bash)로 한다.

1. **준비.** `R=~/upg-rehearsal`. W1 을 돌려 `PY` 를 정한다. 「준비」 1번에서 `rm -rf`·`git clone`·`cd template`·
   `git switch` 줄은 건너뛴다(클론은 이미 있다; 그 클론에 `v5.0.1` 태그가 이미 있으면 1번 전체를 건너뛴다).
   나머지 줄은 `~/upg-rehearsal/template` 에서 돌린다. 「준비」 2번의 함수는 Bash 호출 사이에 남지 않으므로
   `~/upg-rehearsal/make_project.sh` 로 저장해 두고 매번 `source` 한다. `R` 과 `PY` 도 매번 다시 정한다.
2. **W1, W2** 는 문서의 명령을 그대로 돌린다.
3. **W3~W6 은 새 Claude 세션이 사용자 역할을 받아 진행한다.** 아래 함수로 한 턴씩 보낸다. 권한 확인을 끄는
   옵션(`--dangerously-skip-permissions`)은 쓰지 않는다.

   ```bash
   turn() {  # turn <프로젝트 폴더> <new | 세션 id> <메시지> [blockgh]
     ( cd "$1" || exit 9
       [ "$4" = blockgh ] && export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=url.http://127.0.0.1:9/.insteadOf GIT_CONFIG_VALUE_0=https://github.com/
       res=(); [ "$2" != new ] && res=(--resume "$2")
       claude -p "${res[@]}" "$3" --output-format json --allowedTools "Bash,Read,Edit,Write,Glob,Grep" > "$1.turn.json" 2> "$1.turn.err"
       $PY -c 'import json,sys; d=json.load(open(sys.argv[1],encoding="utf-8")); open(sys.argv[2],"w").write(d.get("session_id","")); print(d.get("result",""))' "$1.turn.json" "$1.sid" )
   }
   ```

   - 첫 턴: `turn "$R/p-full" new "/orchestrator-upgrade" blockgh`. 다음 턴: `turn "$R/p-full" "$(cat "$R/p-full.sid")" "<답>" blockgh`.
     W3 만 `blockgh`, W4·W5 는 붙이지 않는다. W6 의 첫 메시지는 W6 절의 붙여 넣기 문장이다.
   - 답은 각 W 절의 표·설명대로 한다. 표에 없는 질문은 리허설이 계속되는 쪽으로 답하고 그 사실을 적는다.
   - `.claude/` 아래 편집이 권한 때문에 막혔다고 하면 "Bash 로 써도 된다"고 답한다(헤드리스에서는 승인 창이
     없다). W5 의 임시 클론 삭제(`rm -rf`)도 같은 이유로 막힐 수 있다 — 막히면 그대로 적고, 남은 경로는 네가
     지운다.
   - 각 W 가 끝나면 그 절의 확인 명령을 직접 돌린다.
4. **보고서** `~/upg-rehearsal/REPORT.md` — 맨 아래 「결과 기록 양식」을 채우고, 시나리오마다 덧붙인다:
   스킬이 한 질문 목록(순서대로), 보낸 답, 확인 명령의 출력 그대로, 스킬 세션의 마지막 보고, 각 턴의 `.turn.err`
   에 나온 경고·오류, 그리고 Windows 에서만 보인 것(인코딩, 경로, 줄바꿈, 권한). 판정은 각 절의 "통과/실패"
   기준으로만 한다. 확인하지 못한 것은 [미확인] 으로 적는다.

---

## W1 — 준비물

```bash
git --version
for c in python3 python "py -3"; do $c -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null && { echo "PY=$c"; break; }; done
claude --version
```

**통과:** 세 줄 모두 버전이 나오고, 두 번째 줄이 `PY=...` 를 출력한다.
**실패:** `PY=` 줄이 없다 → Python 3.10 이상이 없다. 설치하고 다시 한다. 이후 단계는 진행하지 않는다.

이후 명령을 위해 `PY` 를 설정한다(위에서 나온 값으로):

```bash
PY=python        # 예: W1 이 PY=python 을 출력했으면
```

## 준비 — 연습용 템플릿과 프로젝트 만들기

아래는 홈 폴더의 `upg-rehearsal` 안에만 파일을 만든다. 끝나면 그 폴더를 지우면 된다.

1. 템플릿을 클론하고, 연습용 릴리스 `v5.0.1` 을 **로컬에만** 만든다. 이 릴리스는 세 가지를 바꾼다.
   프로젝트도 고친 파일 하나(MERGE 가 나오게), 프로젝트 소유인 `CLAUDE.md`(MERGE 로 나오지만 덮어쓰면 안 된다),
   손으로 할 단계 하나(CHANGELOG)다.

```bash
R=~/upg-rehearsal
rm -rf "$R" && mkdir -p "$R" && cd "$R"
git clone https://github.com/GunwooYun/claude-code-orchestrator.git template
cd template
git switch claude/orchestrator-upgrade     # 머지된 뒤에는: git switch develop
echo 5.0.1 > .claude/ORCHESTRATOR_VERSION
printf '\n- Rehearsal: an upstream line.\n' >> .claude/rules/security.md
printf '\n<!-- rehearsal upstream CLAUDE.md line -->\n' >> CLAUDE.md
$PY - <<'EOF'
from pathlib import Path
p = Path("CHANGELOG.md")
entry = (
    "## [5.0.1] - rehearsal\n\n"
    "**Upgrade:**\n\n"
    "1. Add the line `<!-- rehearsal hand step -->` at the end of `CLAUDE.md`.\n\n"
)
text = p.read_text(encoding="utf-8")
i = text.index("## [5.0.0]")
p.write_text(text[:i] + entry + text[i:], encoding="utf-8")
EOF
git -c user.name=r -c user.email=r@r commit -qam "rehearsal release 5.0.1"
git tag v5.0.1
```

2. 프로젝트 사본을 만드는 함수다. **이 블록은 고치지 않고 그대로 붙여 넣는다** — 아무것도 출력되지 않으면
   정상이다. 폴더 이름·버전·스킬 여부는 아래 각 W 의 명령(`make_project p-full 5.0.0 skill` 등)에 이미 들어 있다.
   함수와 `R`·`PY` 는 이 Git Bash 창에서만 살아 있다. 창을 새로 열면 `PY=…`, `R=~/upg-rehearsal`, 이 블록을
   다시 붙여 넣는다(1번은 다시 할 필요 없다).

```bash
make_project() {
  P="$R/$1"; rm -rf "$P"; mkdir -p "$P"
  git -C "$R/template" archive "v$2" .claude .agents CLAUDE.md | tar x -C "$P"
  printf '#!/bin/sh\necho "rehearsal gate ok"\n' > "$P/.claude/scripts/verify-task"
  printf '\n- Project edit: keep this line.\n' >> "$P/.claude/rules/security.md"
  printf '\n## Project Setup\n\n- Rehearsal project section: keep it.\n' >> "$P/CLAUDE.md"
  if [ "$3" = skill ]; then
    mkdir -p "$P/.claude/skills/orchestrator-upgrade"
    cp "$R/template/.claude/skills/orchestrator-upgrade/SKILL.md" "$P/.claude/skills/orchestrator-upgrade/"
  fi
  git -C "$P" init -q && git -C "$P" add -A && git -C "$P" -c user.name=r -c user.email=r@r commit -qm "project at $2"
  echo "$P"
}
```

---

## W2 — hook-check 를 직접 돌리기 (Claude 없이, 1분)

```bash
make_project p-hooks 5.0.1
$PY "$R/template/tools/hook-check" "$R/p-hooks"; echo "exit=$?"
```

**통과:** 모든 줄이 `ok` 로 시작하고 `exit=0`.

이번에는 일부러 고장 난 훅을 심는다. **실패해야 정상이다.**

```bash
printf 'raise SystemExit("boom")\n' > "$R/p-hooks/.claude/hooks/broken.py"
$PY - "$R/p-hooks/.claude/settings.json" <<'EOF'
import json, sys
p = sys.argv[1]
s = json.load(open(p, encoding="utf-8"))
s["hooks"].setdefault("PostToolUse", []).append(
    {"matcher": "Bash", "hooks": [{"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/broken.py"'}]}
)
json.dump(s, open(p, "w", encoding="utf-8"), indent=2)
EOF
$PY "$R/template/tools/hook-check" "$R/p-hooks"; echo "exit=$?"
```

**통과:** `FAIL` 줄 하나가 `broken.py` 를 가리키고 `exit=1`.
**실패:** `exit=0` 이 나온다 → hook-check 가 고장을 못 잡는다. 출력 전체를 붙여 넣는다.

> 템플릿의 훅 명령은 `python3` 으로 등록돼 있다. W1 에서 `python3` 이 안 됐다면 W2 의 첫 실행부터 `FAIL` 이
> 나올 수 있다. 그것도 **알아야 할 결과**다 — 그대로 기록한다.

## W3 — GitHub 접속 실패 + 내 클론 경로로 전체 업그레이드 (Claude, 10~20분)

GitHub 접속을 **git 에서만** 막고 Claude 를 연다(Claude 자체의 연결은 막지 않는다).

```bash
make_project p-full 5.0.0 skill
cd "$R/p-full" && pwd                                     # .../upg-rehearsal/p-full 로 끝나야 한다
GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=url.http://127.0.0.1:9/.insteadOf GIT_CONFIG_VALUE_0=https://github.com/ \
  git ls-remote https://github.com/GunwooYun/claude-code-orchestrator.git; echo "exit=$?"   # 0 이 아니어야 한다
[ "$(basename "$PWD")" = p-full ] && \
  GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=url.http://127.0.0.1:9/.insteadOf GIT_CONFIG_VALUE_0=https://github.com/ claude
```

마지막 줄은 `p-full` 안에 있을 때만 Claude 를 연다. 아무 일도 없으면 `make_project` 줄의 오류부터 본다.

💬 `/orchestrator-upgrade` — 이후 질문에는 이렇게 답한다.

| Claude 가 묻는 것 | 답 |
|---|---|
| GitHub 접속 실패: 재시도 / 클론 경로 / 중단 | 클론 경로: `~/upg-rehearsal/template` |
| 5.0.0 → 5.0.1 로 올릴지 | 예 |
| 분류표 적용 | 예 |
| MERGE `security.md` 결과 확인 | 두 줄(`Project edit`, `Rehearsal: an upstream line`)이 모두 있으면 예 |
| `CLAUDE.md` 에 손 단계 한 줄 추가 | 예 |
| 커밋되지 않은 파일(`__pycache__`, `logs`)이 있다고 하면 | 그대로 진행 — 훅이 만든 실행 산출물이다 |
| 커밋 | 예 |
| 클론 삭제 | 묻지 않아야 한다(내 클론이다) |

`.claude/` 아래 파일을 고칠 때 Claude Code 가 편집 권한을 물으면 승인한다.

끝나면 Claude 를 닫고 확인한다.

```bash
cat .claude/ORCHESTRATOR_VERSION                         # 5.0.1
grep -c "Project edit\|Rehearsal: an upstream line" .claude/rules/security.md   # 2
tail -1 CLAUDE.md                                        # <!-- rehearsal hand step -->
grep -c "Rehearsal project section" CLAUDE.md            # 1 (내 섹션이 남았다)
grep -c "rehearsal upstream CLAUDE.md line" CLAUDE.md    # 0 (템플릿 쪽 줄은 들어오지 않는다)
git log --oneline -1                                     # chore: upgrade ... v5.0.1
ls -d "$R/template"                                      # 아직 있어야 한다
$PY "$R/template/tools/upgrade-plan" . --from 5.0.0      # MERGE 는 security.md·CLAUDE.md, KEEP 은 verify-task 뿐
```

> 2026-10-15 의 첫 Windows 실행에서 마지막 줄이 MERGE 5개·KEEP 31개를 냈다. 줄바꿈(CRLF) 차이를 수정으로
> 본 것이고, 이어서 고쳤다. 고치기 전에 받은 템플릿이면 1번부터 다시 한다(`rm -rf ~/upg-rehearsal`).
> 줄바꿈을 직접 볼 때 Windows 의 `grep -c $'\r'` 는 CR 을 지우고 세므로 0 이 나온다 — `git hash-object`
> 로 비교한다.

**통과:** 위 주석대로 나온다. 그리고 Claude 의 보고에서 hook-check 가 `exit 0` 이다.
**실패:** 어느 줄이 다른지 그 출력과 Claude 의 마지막 보고를 붙여 넣는다.

## W4 — 이미 최신일 때 (Claude, 1분)

```bash
make_project p-latest 5.0.0 skill
cd "$R/p-latest" && claude
```

💬 `/orchestrator-upgrade`

**통과:** "이미 최신(5.0.0)"이라고 말하고 멈춘다. `git status` 가 깨끗하다. (GitHub 의 최신 릴리스가
5.0.0 인 동안만 맞는 시나리오다.)

## W5 — 임시 클론 만들고 지우기 (Claude, 2~3분)

GitHub 의 최신 릴리스(5.0.0)에는 아직 `tools/UPGRADE.md` 가 없다. 그래서 스킬이 **임시 폴더에 클론 → 절차
문서가 없음을 알림 → 임시 클론 삭제**까지 가는지 볼 수 있다. Windows 의 임시 폴더 처리를 보는 시나리오다.

```bash
make_project p-temp 4.3.1 skill
cd "$R/p-temp" && claude
```

💬 `/orchestrator-upgrade`

**통과:** 클론한 뒤 "이 릴리스에는 절차 문서가 없다 → README 9장"이라고 멈추고, 임시 클론을 지웠다고 하거나
경로를 알려 준다. Claude 가 알려 준 임시 경로가 지워졌는지 확인한다: `ls <경로>` → "No such file".
**실패:** 경로가 남아 있는데 지웠다고 한다, 또는 프로젝트 안에 클론이 생겼다(`git status` 에 나온다).
(다음 릴리스가 나오면 이 시나리오는 더 이상 재현되지 않는다.)

## W6 — 스킬 없는 프로젝트에서 붙여 넣기로 (Claude, 10분)

```bash
make_project p-noskill 5.0.0
cd "$R/p-noskill" && claude
```

💬 (연습용이라 GitHub 대신 로컬 클론을 쓰게 한다)

```text
claude-code-orchestrator 템플릿을 업그레이드해 줘. 클론은 ~/upg-rehearsal/template 에 있어(CLONE_KIND=user-supplied).
그 클론의 tools/UPGRADE.md 를 처음부터 따라 해 줘.
```

질문에는 W3 와 같이 답한다. **통과:** W3 의 확인 명령이 같은 결과를 낸다. 그리고 프로젝트에
`.claude/skills/orchestrator-upgrade/SKILL.md` 가 새로 생긴다.

---

## 결과 기록 양식

아래를 복사해 채운 뒤 Claude 세션에 붙여 넣는다.

```text
Windows 업그레이드 확인 결과
- Windows 버전:            Git 버전:            Claude Code 버전:
- W1 PY=
- W2 정상: 통과/실패   고장 심은 뒤: 통과/실패   (출력)
- W3 통과/실패   (다른 줄과 Claude 의 마지막 보고)
- W4 통과/실패
- W5 통과/실패   (임시 경로와 ls 결과)
- W6 통과/실패
- 그 밖에 이상했던 것:
```

정리: `rm -rf ~/upg-rehearsal`
