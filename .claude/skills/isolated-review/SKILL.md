---
name: isolated-review
description: Run a NEUTRAL review of the current branch by a separate `claude -p` reviewer that shares no context with this session and can only read. It is /feature Phase 6 Option A1 — the review by a context that did not write the change — launched by the orchestrator instead of by hand. Use it when implementation is finished and committed and the user wants the separate-session review. Always ask the user once before running it (it costs money and time). Do NOT use it for a quick in-session check (that is deep-reasoning or /lens-review), and do NOT use it to review a change to this skill itself (it refuses).
---

# Isolated Review

**A reviewer that did not write the change, cannot be steered by the session that
did, and cannot touch anything.** This skill only launches it and shows you what
it said. It never decides whether the change is good.

Design, measurements and every rejected alternative: `docs/isolated-review.md` in
the template repository. Read it before changing anything here — each lock below
exists because a weaker one was measured to fail.

## What it is and is not

| | `/isolated-review` (A1) | Person-opened session (A2) |
|---|---|---|
| Shares context with the implementer | No | No |
| Request text | Fixed `prompt.md`; nobody adds to it | Whatever the person writes |
| Can be questioned or argued with | **No** — one report | Yes |
| Can write or run anything | **No** — Read/Grep/Glob only | Whatever the person allows |

It does not replace A2. When a finding needs discussion, or the change touches a
security boundary or a public interface, also ask the user for an A2 review.

## Procedure

1. **Preconditions** — the script checks and refuses (exit 2) otherwise:
   committed and clean working tree; the branch differs from its base; the
   branch does not change `.claude/skills/isolated-review/` itself; at most 3000
   changed lines. If refused, tell the user the reason verbatim. Do not work
   around it (do not commit "just to make it clean" without asking).
2. **Ask the user once**: "격리 리뷰를 실행할까요? Fable 모델, 최대 $20, 최대 45분입니다."
   They may already be reviewing by hand.
3. **Run it in the background** — it can take up to 45 minutes, longer than the
   Bash tool's foreground limit:
   ```
   Bash(command=".claude/skills/isolated-review/run-review --base <base>",
        run_in_background=true)
   ```
   `--base` defaults to `origin/HEAD`. Pass the branch this work merges into.
   `--budget` and `--timeout` can only LOWER the ceilings. There is no way to
   add instructions for the reviewer, by design.
4. **While it runs, do not edit files and do not commit.** A tree that changes
   during the review makes the report INVALID.
5. **Show the report verbatim.** Print the `## Findings` and `## Not reviewed`
   sections exactly as written — no summary, no paraphrase, no ranking. Summarising
   is where this session's view would re-enter. Then, per finding, ask the user:
   fix / dispute / defer.

## Verdicts

| Exit | Verdict | Meaning |
|---|---|---|
| 0 | COMPLETE | The reviewer finished, isolation was confirmed, and every changed file was listed and actually read. **Not an approval.** |
| 3 | INCOMPLETE | A changed file was listed in Coverage but never read. Treat unread files as unreviewed |
| 1 | FAILED | Isolation not confirmed, probe failed, budget/timeout, wrong model, missing section, or a changed file missing from Coverage |
| 4 | INVALID | The tree changed during the run. The report is kept but describes a moving target — rerun |
| 2 | REFUSED | A precondition failed; nothing ran |

Reports are written to `.claude/docs/reviews/<branch>-<time>.md` (keep out of git)
and the reviewer's transcript to `.claude/logs/isolated-review/<run>/`. Later
reviewers are denied both, so a second round cannot anchor on the first.

## Locks (do not loosen without re-measuring)

- `--restricted --tools Read,Grep,Glob --strict-mcp-config --disable-slash-commands`
  — an allow list does NOT restrict; a reviewer wrote a file under
  `--allowedTools Read` because the project allowed `Write(*)`.
- The run's own `system/init` event must show exactly Read/Grep/Glob and no
  slash commands; otherwise FAILED.
- A Haiku probe with the same settings runs first and must be refused two reads
  (one inside the repo, one outside); otherwise the review never starts.
- Deny rules: secrets, the project's own Read denies, and — for neutrality —
  `CLAUDE.md`, checkpoints, logs and earlier reports. The verification plan
  reaches the reviewer only as "implementer-authored claims".
- Model pinned to Fable; ceilings $20 / 45 min; no `--bare` (it drops OAuth
  login and CLAUDE.md).

## Field reports

This skill is being validated on real work in repositories its developers cannot
see. After a few runs, the user sends a field report:
`.claude/skills/isolated-review/field-report` drafts it (facts only — verdicts,
costs, tool set, finding counts; never review text, code or secrets; paths
hidden unless `--include-paths`), and the person adds a real / false / unsure
verdict per finding and anything the review missed. How to fill it in:
`.claude/docs/templates/field-report.md`. REFUSED runs write no report, so
`run-review` records them in `.claude/logs/isolated-review/refusals.jsonl`.

## Limits

- One report, no follow-up questions.
- Bias is reduced, not zero: this session still picks the base branch and when
  to run.
- Quality of the review itself cannot be checked automatically.
- In projects that keep `.claude/` out of git, the "branch changes the reviewer"
  check cannot see edits to this skill — they are untracked.
