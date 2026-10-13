---
name: orchestrator-version
description: Show which claude-code-orchestrator release this project's copy came from, and — only when asked — whether a newer release exists and what changed since. Use when the user asks "어느 버전", "which orchestrator version", "최신이야?", "업그레이드할 게 있어?", or to plan an upgrade of the template in a project — `--plan` prints the per-file classification, read-only.
---

# Orchestrator Version

```sh
.claude/skills/orchestrator-version/check                 # installed version only, no network
.claude/skills/orchestrator-version/check --check-latest  # plus newest release and changes since
```

- **Installed** comes from `.claude/ORCHESTRATOR_VERSION`, which travels with the
  copied `.claude/`. Missing means the copy predates versioning (before v0.1.0).
- **`--check-latest`** reads the release tags and `CHANGELOG.md` from GitHub. Run
  it only when the user wants the comparison: company networks often block it,
  and then it prints `latest: unavailable (...)` and exits 0 — say that plainly,
  do not guess the latest version.
- Show the output as it is. If a newer release exists, the upgrade is **not** a
  copy-over: README 「자주 밟는 함정」 describes comparing each file with the
  template's history and merging what the project changed.
- `## Project Setup` in `CLAUDE.md` records the version `/initproject` adopted;
  if it disagrees with the file, say so — someone upgraded part of `.claude/`.

## Upgrade plan (read-only)

```sh
git -C <template clone> fetch --tags
python3 <template clone>/.claude/skills/orchestrator-version/check --plan <project root>
```

- Run the **template clone's** script: the project's own copy is the old version.
  The old version is the project's `ORCHESTRATOR_VERSION` (`--from X.Y.Z` when it
  has none — ask the user, do not guess); the new one is the clone's newest tag
  (`--to X.Y.Z` to stop earlier). Exit 2 names what to fix.
- It changes nothing. Show the classes to the user and get approval before any
  backup, replace or delete — that is README 「업그레이드 절차」.
- `PROJECT-ONLY` grouped under "last shipped in X" are leftovers of earlier
  upgrades; "never shipped" are the project's own files. Whether either goes is
  the user's decision. `[project-owned]` files are merged by hand, never replaced.
- Act on `HOOKS` in the same step as the deletes it names.
