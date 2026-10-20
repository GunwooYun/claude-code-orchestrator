---
name: lens-review
description: Review a change in this session through five lenses (correctness, security, integration, tests, simplicity), each a separate read-only Opus reviewer, then have every finding checked for truth by a separate verifier. It is /feature Phase 6 Option B — the in-session review before /isolated-review. Works on committed or uncommitted changes. Run it when the user types /lens-review or accepts it in Phase 6; always ask once first (it costs a few dollars and minutes).
disable-model-invocation: true
---

# Lens Review

**Five reviewers, one concern each, then a verifier per finding.** You (the main
session) only start the agents; the script's `collect` saves what they say.
Everything that must not depend on how you read or retype text — the scope, the
prompts, the answers, the report — is done by the script.

Design, measurements and rejected alternatives: `docs/lens-review.md` in the
template repository. Read it before changing anything here.

## Where it sits

| Review | Who writes the prompt | Sees | Use |
|---|---|---|---|
| **this skill** | the script (fixed templates) | committed or uncommitted change | in-session, before committing or before A1 |
| `/isolated-review` (A1) | fixed `prompt.md` | committed branch only | last word, separate process |
| A2 | a person | anything | discussion, security boundaries |

They find different things: in the measurements the lenses caught weak tests and
dead code that A1 missed, A1 caught broken guides and procedures the lenses
missed, and neither caught a bug that only shows when the code runs on another
platform. Order: **lens review → fix → commit → /isolated-review**. The review
round ends when neither has a Medium-or-higher finding the user accepts.

## Procedure

Run every script call as `python3 .claude/skills/lens-review/lens-review …`
(works on Windows too).

1. **Ask the user once**: "관점 리뷰를 실행할까요? 기준 `<base>`, Opus 리뷰어 5명 +
   지적마다 검증자 1명, 약 $2–6, 5–10분입니다." The base is the branch this work
   merges into; ask for it in the same question if you do not know it.

2. **Scope.**
   ```
   python3 .claude/skills/lens-review/lens-review scope --base <base>
   ```
   It prints `run: <dir>`, the range and the size. A clean tree reviews the
   committed branch; uncommitted or untracked changes switch it to the working
   tree, and the range line says so — tell the user which. Exit 2 is a refusal:
   show the reason verbatim. Over 3000 changed lines it refuses; offer to narrow
   with `--paths <dir> …` (per-file sizes are in `<dir>/scope.json`).

3. **Lenses — five agents in parallel, in the background.** For each lens in
   `correctness security integration tests simplicity`:
   ```
   python3 .claude/skills/lens-review/lens-review prompt lens --run <dir> <lens>
   ```
   and pass its output **as the whole prompt, unchanged**:
   `Agent(subagent_type="lens-reviewer", run_in_background=true, prompt=<output>)`.
   Add nothing — no context, no hints, no summary of the change, no reason it was
   built this way. The reviewer must not know what you think.

4. **Collect — do not save answers yourself.** When all five have finished:
   ```
   python3 .claude/skills/lens-review/lens-review collect --run <dir>
   ```
   It takes each agent's final message from this session's transcripts,
   matched by the prompt the script printed, and saves it in `<dir>`. You never
   copy or retype an answer (writing under `.claude/` would also ask for
   approval on every file). `missing:` lists answers not found yet — wait for
   those agents, then run it again. An answer that never appears means its
   prompt was changed on the way: say so; do not work around it.

5. **Verify every finding.** `collect` printed the verifier answers still
   missing as `verify-<lens>-<n>.md`; for each:
   ```
   python3 .claude/skills/lens-review/lens-review prompt verify --run <dir> --finding <lens>:<n>
   ```
   and pass its output unchanged:
   `Agent(subagent_type="lens-reviewer", run_in_background=true, prompt=<output>)`.
   The verifier judges whether the claim is TRUE, not whether it matters. Never
   add questions about impact, real-world occurrence or the project's rules:
   that turned true findings into "real, but REFUTED" when it was measured.
   When they have finished, run `collect` again until `missing: none`.

6. **Report.**
   ```
   python3 .claude/skills/lens-review/lens-review report --run <dir>
   ```
   It prints the report path under `.claude/docs/reviews/`. Exit 3 means the
   report was written but something is missing (a lens answer, a verdict, text
   the parser could not read) — the report's `## Incomplete` section says what.

7. **Show the report.** The full report is long (tens of KB); do not paste it.
   Print its `## Summary` — one line per finding, refuted ones included — and any
   `## Unparsed` / `## Incomplete` sections verbatim, then a complete translation
   of them into the user's language: every line, in order, nothing merged or
   dropped. Give the report path; the full findings (claim, failure, evidence,
   verifier's correction) are there. Then, per finding, ask: fix / dispute /
   defer, reading the finding's section in the report as needed. **This is where the
   real-occurrence rule applies** (`CLAUDE.md` 운영 주의사항 「일어나지 않는 조건을
   이론만으로 쫓지 않는다」): show next to each finding whether its input occurs in real use,
   and recommend defer when it does not. The verifier never makes that call.

While the agents run, do not edit the files under review: the lenses read the
working tree.

## Limits

- Reviewers and verifiers only read (Read, Grep, Glob). Defects that only show
  when code runs — a platform's encoding, a test that passes for the wrong
  reason without anyone reading it — can be missed.
- The model and effort are pinned in `.claude/agents/lens-reviewer.md` (Opus,
  medium). A project without Opus access cannot use this skill as is.
- `CLAUDE_CODE_EFFORT_LEVEL`, when set, overrides the pinned effort.
- Steps 3 and 5 depend on you passing prompts unchanged. A changed prompt
  shows up as a missing answer in `collect`; `tools/lens-audit` in the template
  repository checks the rest from transcripts.
- `collect` reads this session's transcripts under `~/.claude/projects/` (or
  `$CLAUDE_CONFIG_DIR`), found by `$CLAUDE_CODE_SESSION_ID`.
- Bias is reduced, not removed: this session still picks the base and when to
  run.
