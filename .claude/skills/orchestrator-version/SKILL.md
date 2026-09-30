---
name: orchestrator-version
description: Show which claude-code-orchestrator release this project's copy came from, and — only when asked — whether a newer release exists and what changed since. Use when the user asks "어느 버전", "which orchestrator version", "최신이야?", "업그레이드할 게 있어?", or before planning an upgrade of the template in a project.
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
