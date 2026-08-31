# Review Request #2 — Post-review fixes, agy model policy, README usage guide

Prepared 2026-08-31 for an independent review session. Range to review:
`git diff 1672e90^..main` (everything since review #1's findings were applied,
including the fix commit itself). Review #1 report was deleted after its findings
were applied; its dispositions are summarized in §1 so you can verify them.

Please write your findings to `.claude/docs/review-report-2.md` only — do not
modify any other file, and do not run `/checkpointing`.

## 1. What changed since review #1 (commits)

| Commit | Scope |
|---|---|
| `1672e90` fix: address migration code review findings | All 17 findings of review #1 — see §1.1 |
| `95f75b4` docs: README usage guide + mismatch fixes + `/init` retarget | README "실전 활용 가이드" (8 sections); hooks table, skills list, `/checkpointing --full --analyze`, `tests/`, mypy-vs-ty note; `init` skill now updates `CLAUDE.md` instead of a root `AGENTS.md` (which agy auto-loads) |
| `96945c3` docs: operational notes in CLAUDE.md | 6 bullets so sessions avoid known pitfalls |
| (this commit) agy **model policy** | New "Model Policy" in `rules/antigravity-delegation.md`; `--model` pinned in every template/example (rule, `antigravity-system` skill + `use-cases.md`, `general-purpose.md`, `startproject` Phase 1); README §6 |

### 1.1 Review #1 dispositions (verify)

- **Applied**: A-1..A-6 (`log-cli-tools.py` rewritten on `shlex`, command-position anchoring, flag-order-agnostic prompt, `--model=`, soft-deny-aware `success`, `systemMessage` output; 23 unit tests in `tests/test_log_cli_tools.py`), A-7/B-1 (agy read-only in `.agents/rules/AGENTS.md` + context-loader; "do not create or modify files" in every flagged template; `Bash(agy:*)` exposure documented), B-3 (out-of-workspace PNG and PDF verified; absolute paths), B-4 (`--print-timeout 10m`), B-5 (English outputs), B-6 (context-loader softened), B-8 (hooks tell subagents to report back), A-8 (codex remnants removed from `checkpoint.py`), A-9 (`PDF`/duplicate trigger), A-10 (`systemMessage`), B-7 nits, D2 note (refactoring asks for a diff, not full file), D5 note (root `AGENTS.md` coexistence in README).
- **Handled differently**: B-2 — chose "document read-only as instruction-only" (README, CLAUDE.md, `deep-reasoning.md` now lists forbidden Bash usage) instead of a deny hook, because hook payloads do not reliably identify the running agent and a mis-scoped deny would block the main session.
- **Left as-is**: A-9's `"문서"` over-broad trigger — it backs a documented trigger phrase ("최신 문서를 확인해 줘"); flagged in README §7 as a customization point.

## 2. Model policy — please review as a *policy*, not just text

Location: `.claude/rules/antigravity-delegation.md` → "Model Policy"; mirrored in
`antigravity-system/SKILL.md` and applied to all examples.

| Tier | Task shape | `--model` |
|---|---|---|
| T1 Quick lookup | one fact / yes-no / version; ≤ 1 paragraph; single source; no file reads | `gemini-3.7-flash-low` |
| T2 Summarize / extract | one page or one file; structured fields from a known input; explain one module | `gemini-3.7-flash-high` |
| T3 Research report | library comparison, best practices, multi-source synthesis | `gemini-3.1-pro-high` |
| T4 Whole-repo / multimodal | repo-wide analysis, cross-module tracing, PDF/image/video | `gemini-3.1-pro-high` + `--print-timeout 10m` |

Rules: (1) unsure → higher tier; (2) never downgrade T4; (3) explicit user
instruction wins; (4) empty/shallow T1–T2 answer → re-run once at T3, never loop
at the same tier.

Design rationale (author's position — challenge it):
- Savings come from the call *distribution* (most calls are T1/T2), not from
  table granularity; beyond ~5 tiers the routing decision itself becomes a
  source of errors, and a wrong downgrade costs a re-run (net loss).
- Effort is expressed via the slug suffix (`-low/-high`); the separate
  `--effort` flag is intentionally not used to keep one knob.
- The user's global default (`/model` → `gemini-3.1-pro-high`) still applies to
  any call without `--model`; templates always pin, so the default is a fallback.
- Claude-side model choice is left to agent frontmatter (`general-purpose:
  sonnet`, `deep-reasoning: inherit`) and not made per-call.

Questions for the reviewer:
1. Are the tier boundaries operational — can a `general-purpose` subagent (sonnet)
   classify a task into T1–T4 reliably from these descriptions? Which boundary
   is most ambiguous?
2. Is T2 on Flash safe for *extraction* tasks feeding scripts (`--json-schema`)?
   Would you move structured extraction to `gemini-3.1-pro-low`?
3. Is rule (4) (one escalation) sufficient, or should T1 answers that cite no
   source be escalated automatically?
4. Anything in the policy that conflicts with the soft-deny / read-only guard
   introduced after review #1?
5. Would a finer table (e.g. 6–8 tiers, or per-use-case rows) actually save
   quota, or add mis-routing? The user asked this explicitly.

## 3. Verification already done by the author

- `python3 -m unittest tests.test_log_cli_tools` → 23 pass; `py_compile` all hooks.
- Live hook checks: agy call logged with model; soft-deny stderr → `success: false`;
  `grep 'agy -p "x"'` not logged.
- `agy -p … --model gemini-3.7-flash-low` executed successfully (slug valid).
- Empirical: headless `read_file` denied without flags; with
  `--dangerously-skip-permissions --sandbox` a workspace PNG, an out-of-workspace
  PNG (no `--add-dir`), and a PDF were read correctly. Video/audio untested.
- `grep` sweep: no `gemini -p`, `--include-directories`, `gemini-3-pro-preview`,
  `GEMINI.md`, or Codex references outside intentional mentions.

## 4. Known/open items (not addressed on purpose)

- `pyproject.toml` uses mypy while rules/hook assume ty (upstream mismatch;
  documented in README, left for the adopting project to unify — uv is not
  installed here, so the lock file cannot be regenerated).
- Upstream hook quirks unchanged: `lint-on-save.py` reads `CLAUDE_TOOL_INPUT`
  instead of stdin JSON; two hooks read `tool_output` instead of `tool_response`;
  `/tmp` state file in `post-implementation-review.py`.
- `design-tracker` skill still contains Japanese trigger phrases.
