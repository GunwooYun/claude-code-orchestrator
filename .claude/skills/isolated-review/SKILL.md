---
name: isolated-review
description: Run a NEUTRAL review of the current branch by a separate `claude -p` reviewer that shares no context with this session and can only read. It is /feature Phase 6 Option A1 — the review by a context that did not write the change — launched by the orchestrator instead of by hand. Use it when implementation is finished and committed and the user wants the separate-session review. Always ask the user once before running it (it costs money and time). Do NOT use it for a quick in-session check (that is deep-reasoning), and do NOT use it to review a change to this skill itself (it refuses).
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

   **Docs and evidence files that inflate the count** can be left out of the
   cap — and only the cap — with a committed `.claude/isolated-review.json`:
   `{"cap_exclude": ["dev-docs/**", "dev-test/**/results/*"]}`. Those files are
   still in the diff and still must be in Coverage. A branch that changes this
   list is INCOMPLETE (the change under review must not decide how much of
   itself counts). Suggest it to the user; do not add it on your own.
2. **Ask the user once**: "격리 리뷰를 실행할까요? 기준 브랜치 `<base>`, Fable 모델,
   최대 $20, 최대 45분입니다." They may already be reviewing by hand, and they
   can correct the base.
3. **Run it in the background** — it can take up to 45 minutes, longer than the
   Bash tool's foreground limit:
   ```
   Bash(command=".claude/skills/isolated-review/run-review --base <base>",
        run_in_background=true)
   ```
   **Always pass `--base <the branch this work merges into>`** — the PR's
   target. The default, `origin/HEAD`, is the remote's default branch, which is
   wrong wherever work merges into another branch (e.g. `develop`): the review
   then covers already-merged work or hits the line cap. If you do not know the
   target, ask the user in the same question as step 2. The base is not read
   from `CLAUDE.md` on purpose: that file is written by the implementing
   session, and it must not set the review's scope. The report header records
   the base used.
   `--budget` and `--timeout` can only LOWER the ceilings. There is no way to
   add instructions for the reviewer, by design.
4. **While it runs, do not edit files and do not commit.** A tree that changes
   during the review makes the report INVALID.
5. **Show the report verbatim.** Print the `## Findings` and `## Not reviewed`
   sections exactly as written — no summary, no paraphrase, no ranking. Summarising
   is where this session's view would re-enter. Then, per finding, ask the user:
   fix / dispute / defer.
   **Before asking, check whether each finding's input occurs in real use** —
   logs, field reports, or the usage the templates prescribe — and show that
   next to the finding. A finding with no real occurrence (a usage nobody has,
   a condition that cannot arise, an input built only in theory) is recommended
   as defer, whatever its severity label: record it, do not start another
   implement → review → fix round for it. Rule: `CLAUDE.md` 운영 주의사항
   「일어나지 않는 조건을 이론만으로 쫓지 않는다」.

## Verdicts

| Exit | Verdict | Meaning |
|---|---|---|
| 0 | COMPLETE | The reviewer finished, isolation was confirmed, and every changed file was listed and actually opened — with Read, or searched with Grep on that file. Deleted files need no read; a file the branch **adds** counts as read when its whole content reached the reviewer in the diff (on stdin, or the diff file's Reads covered its lines). **Not an approval.** |
| 3 | INCOMPLETE | A changed file was listed in Coverage but never read — treat unread files as unreviewed. Or the branch changes the project's `Read(...)` denies, which are forwarded to the reviewer: the change under review set what its reviewer could not see (the header lists the rules added and removed). Or it changes `cap_exclude` |
| 1 | FAILED | Isolation not confirmed, probe failed, budget/timeout, wrong model, missing section, or a changed file missing from Coverage |
| 4 | INVALID | The tree changed during the run; the reason names what changed. The report is kept but describes a moving target — rerun. Dotfiles under `.claude/` (a hook's state, e.g. `.claude/hooks/.blocked-reviews`) are not counted |
| 2 | REFUSED | A precondition failed; nothing ran |

Reports are written to `.claude/docs/reviews/<branch>-<time>.md`
(`detached-<time>.md` on a detached HEAD; `-2`, `-3` appended when a report
with that name already exists) and the reviewer's transcript to
`.claude/logs/isolated-review/<run>/`. Keep both out of git. Later reviewers are
denied both, so a second round cannot anchor on the first.

**The transcript holds the full text of every file the reviewer read** (each
`tool_result`). Secrets are redacted by pattern only, so treat that directory
like the source itself: do not share or attach it. `field-report` never copies
it.

If the run-review process is signalled (SIGTERM, SIGHUP, Ctrl-C) it stops the
reviewer, redacts the transcript and still writes a FAILED report. SIGKILL
cannot be caught: then the reviewer runs on until its own budget or time
ceiling, and nothing is redacted.

## Locks (do not loosen without re-measuring)

- `--restricted --tools Read,Grep,Glob --strict-mcp-config --disable-slash-commands`
  — an allow list does NOT restrict; a reviewer wrote a file under
  `--allowedTools Read` because the project allowed `Write(*)`.
- The run's own `system/init` event must show exactly Read/Grep/Glob and no
  slash commands; otherwise FAILED.
- A Haiku probe with the same settings runs first and must be refused two reads
  (one inside the repo, one outside); otherwise the review never starts.
- Deny rules: secrets, the project's own Read denies, and — for neutrality —
  every `CLAUDE.md` and `CLAUDE.local.md` (nested ones too), `.agents/` (where
  `/checkpointing` also writes the session's history), checkpoints, logs and
  earlier reports. A change to one of those files is therefore reviewed from
  the diff only. The verification plan
  reaches the reviewer only as "implementer-authored claims".
- Model pinned to Fable; ceilings $20 / 45 min; no `--bare` (it drops OAuth
  login and CLAUDE.md). The neutrality measurements were made on Fable, so the
  pin is not a setting: **a project without Fable access cannot use this skill**
  (every run ends FAILED, "pinned model 'fable' did not run") and uses a
  person-opened A2 review instead. `/initproject` says so.
- The scripts run with the project's `python3`, 3.8 or newer; they use only the
  standard library.

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
- It reads; it does not run anything. Defects that only show when code runs —
  a mutation that leaves the tests green, a library that behaves differently
  from its types — are what it missed when replayed against person-opened
  reviews (2026-10-01). Its "this test would fail if…" claims are by reading,
  and its severities run high: weigh its facts, not its labels.
- Bias is reduced, not zero: this session still picks the base branch and when
  to run.
- Quality of the review itself cannot be checked automatically.
- In projects that keep `.claude/` out of git, the "branch changes the reviewer"
  check cannot see edits to this skill — they are untracked. The same holds for
  the deny-change check: only a committed `.claude/settings.json` is compared.
- A secret the branch itself commits (a new `.env`, a key in code) reaches the
  reviewer through the diff; the Read denies do not apply to text on stdin.
