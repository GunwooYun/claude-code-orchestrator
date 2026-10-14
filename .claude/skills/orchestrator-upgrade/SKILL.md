---
name: orchestrator-upgrade
description: Upgrade this project's copy of claude-code-orchestrator to the latest release. Clones the template into a temporary directory, follows the procedure shipped in that clone (tools/UPGRADE.md), asks the user at each decision point, and removes only the temporary clone it made. Run when the user asks to upgrade or update the template / orchestrator.
disable-model-invocation: true
---

# Upgrade the template

This file is a bootstrapper and stays small on purpose: an old project runs its old
copy of it, so the procedure itself lives in the clone, never here. Keep these four
things stable — the URL, the tag rule, the clone rule, the procedure path.

```
TEMPLATE_URL = https://github.com/GunwooYun/claude-code-orchestrator.git
PROCEDURE    = tools/UPGRADE.md          (inside the clone)
```

Talk to the user in their language. Check before you ask; ask only when a check fails
or the choice is theirs.

## 1. Latest release

```bash
git ls-remote --tags --refs "$TEMPLATE_URL" 'v*'
```

Take the highest `vX.Y.Z` (compare numerically). Compare it with
`.claude/ORCHESTRATOR_VERSION` in the project root: equal → tell the user the project
is already on the latest release and stop. Nothing is cloned.

**If the command fails**, show the error in one line and ask the user:

1. Retry (after they fix the network, proxy or credentials)
2. Use a clone they already have — they give its path
3. Stop

## 2. Get a clone

**Temporary clone** (the normal path): a full clone, never `--depth` — the procedure
compares the project against the old release's tag.

```bash
CLONE_PARENT=$(mktemp -d)
git clone --branch "v<latest>" "$TEMPLATE_URL" "$CLONE_PARENT/claude-code-orchestrator"
```

Record `CLONE_PARENT`. It is the only path this run may delete.

**User-supplied clone:** never delete it, never change it without asking.
`git -C <path> rev-parse --is-shallow-repository` prints `true` → ask before
`git -C <path> fetch --tags --unshallow`. If its `HEAD` is not the highest `v*` tag,
ask before `git -C <path> switch --detach v<latest>`, or stop.

## 3. Follow the procedure

Read `<clone>/tools/UPGRADE.md` and follow it from the top, with:
CLONE = the clone, PROJECT = this project's root, CLONE_KIND = `temporary` or
`user-supplied`. From here on that file decides every step, including deletion.

**If the file does not exist**, that release predates this skill: tell the user to
upgrade by README §9 of the clone, then go to step 4.

## 4. Before you stop early

Any stop before step 3 hands over: delete a temporary clone only after checking that
`$CLONE_PARENT/claude-code-orchestrator` holds `.git` and `.claude/ORCHESTRATOR_VERSION`;
otherwise leave it and print the path. On an error, leave it and print the path.

**Windows:** this needs Claude Code's Bash tool (Git Bash). If only PowerShell is
available, say so and stop.
