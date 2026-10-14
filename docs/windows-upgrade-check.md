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

1. 템플릿을 클론하고, 연습용 릴리스 `v5.0.1` 을 **로컬에만** 만든다. 이 릴리스는 두 가지를 바꾼다.
   프로젝트도 고친 파일 하나(MERGE 가 나오게)와, 손으로 할 단계 하나(CHANGELOG)다.

```bash
R=~/upg-rehearsal
rm -rf "$R" && mkdir -p "$R" && cd "$R"
git clone https://github.com/GunwooYun/claude-code-orchestrator.git template
cd template
git switch claude/orchestrator-upgrade     # 머지된 뒤에는: git switch develop
echo 5.0.1 > .claude/ORCHESTRATOR_VERSION
printf '\n- Rehearsal: an upstream line.\n' >> .claude/rules/security.md
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

2. 프로젝트 사본을 만드는 함수다. 버전을 고르고, 스킬을 넣을지 정할 수 있다.

```bash
make_project() {  # make_project <폴더 이름> <버전> [skill]
  P="$R/$1"; rm -rf "$P"; mkdir -p "$P"
  git -C "$R/template" archive "v$2" .claude .agents CLAUDE.md | tar x -C "$P"
  printf '#!/bin/sh\necho "rehearsal gate ok"\n' > "$P/.claude/scripts/verify-task"
  printf '\n- Project edit: keep this line.\n' >> "$P/.claude/rules/security.md"
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
cd "$R/p-full"
GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=url.http://127.0.0.1:9/.insteadOf GIT_CONFIG_VALUE_0=https://github.com/ \
  git ls-remote https://github.com/GunwooYun/claude-code-orchestrator.git; echo "exit=$?"   # 0 이 아니어야 한다
GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=url.http://127.0.0.1:9/.insteadOf GIT_CONFIG_VALUE_0=https://github.com/ claude
```

💬 `/orchestrator-upgrade` — 이후 질문에는 이렇게 답한다.

| Claude 가 묻는 것 | 답 |
|---|---|
| GitHub 접속 실패: 재시도 / 클론 경로 / 중단 | 클론 경로: `~/upg-rehearsal/template` |
| 5.0.0 → 5.0.1 로 올릴지 | 예 |
| 분류표 적용 | 예 |
| MERGE `security.md` 결과 확인 | 두 줄(`Project edit`, `Rehearsal: an upstream line`)이 모두 있으면 예 |
| `CLAUDE.md` 에 손 단계 한 줄 추가 | 예 |
| 커밋 | 예 |
| 클론 삭제 | 묻지 않아야 한다(내 클론이다) |

끝나면 Claude 를 닫고 확인한다.

```bash
cat .claude/ORCHESTRATOR_VERSION                         # 5.0.1
grep -c "Project edit\|Rehearsal: an upstream line" .claude/rules/security.md   # 2
tail -1 CLAUDE.md                                        # <!-- rehearsal hand step -->
git log --oneline -1                                     # chore: upgrade ... v5.0.1
ls -d "$R/template"                                      # 아직 있어야 한다
$PY "$R/template/tools/upgrade-plan" . --from 5.0.0      # MERGE 는 security.md 하나뿐
```

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
