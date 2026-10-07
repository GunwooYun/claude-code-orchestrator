# Antigravity Delegation Rule

**Antigravity CLI (`agy`) reads wide: massive context, Google Search grounding,
PDF/image/video (Gemini models).** It is called through a general-purpose
subagent, never for judgement.

This file holds only what the orchestrator decides **before** a call: what goes
to agy, what to do when agy is unavailable, which tier. Command syntax, headless
flags and prompt templates live elsewhere:

| What | Where |
|---|---|
| Exact commands, headless flags, soft-deny handling | `.claude/agents/general-purpose.md` (the subagent that runs agy — rules files are not guaranteed to reach subagents, so it carries what it needs) |
| agy prompt templates | `.claude/agents/general-purpose.md` → "Common Task Patterns" |
| Measured CLI facts | `.claude/docs/research/antigravity-cli.md` |

## When agy is unavailable (CRITICAL)

Check once per unit of work (`/feature` Phase 1), not per call:
`.claude/bin/agy-probe` — exit 0 = `READY`; otherwise the
first word is the state: `MISSING` (not on PATH), `UNAUTHENTICATED` (log in),
`DEGRADED` (empty answers: soft-deny, quota, network).

| agy's job | Fallback | What is lost |
|---|---|---|
| Web research | general-purpose subagent with WebSearch/WebFetch → `.claude/docs/research/` | Breadth of Google grounding |
| Repo-wide analysis | general-purpose subagent, targeted Grep/Glob/Read — list what was read | It is not exhaustive |
| PDF / image | Claude's Read | Almost nothing |
| Video / audio | **None** — say it cannot be done | The task |
| Pre-filter for deep-reasoning | Skip it; deep-reasoning reads directly | Tokens |

- **Never degrade silently.** A research doc written without agy says so on its
  first line, and what replaced it.
- **Never plan without research.** If no fallback works, write "not researched"
  into the plan as a risk.
- Tell the user the state **once**.

## What goes to agy — by cost, not topic

Routing matrix: `CLAUDE.md` 「라우팅은 주제가 아니라 비용으로」.

**A. Many tokens, easy reasoning → agy**, even when it is not "research": first
pass over large logs / stack traces / CI output (failure points and candidate
causes), repo-wide impact ("every caller of X and how it is used"), pre-filtering
a large file to the relevant lines, translation and boilerplate.

**B. Many tokens, hard reasoning → two-stage funnel.** agy narrows, Claude judges.

- agy returns **locations and facts only** (`file:line` + what is there) — never
  "this is a bug" or "this design is right".
- Prompt for **recall**: "include it if unsure". What the filter drops,
  deep-reasoning never sees.
- Tell deep-reasoning its input was filtered and that it may read more.
- Only for large inputs (5+ files or 500+ lines, `CLAUDE.md` 「큰 변경의 기준」).

**Never to agy:** "is this safe", "is this design right", "A or B",
implementation decisions, conversation with the user.

## Model policy — choose `--model` by tier

The orchestrator picks the tier when it writes the Task prompt. A call without
`--model` falls to the most expensive default.

| Tier | Task | `--model` |
|---|---|---|
| T1 Quick lookup | One fact, yes/no, a version | `gemini-3.7-flash-low` |
| T2 Summarize / extract | One page or one small file; structured fields | `gemini-3.7-flash-high` (machine-consumed → `gemini-3.1-pro-low`) |
| T3 Research report | Comparison, best practice, multi-source synthesis | `gemini-3.1-pro-high` |
| T4 Whole repo / multimodal | Repo-wide analysis, cross-module tracing, PDF/image/video | `gemini-3.1-pro-high` + `--print-timeout 9m` |

1. Unsure between two tiers → the higher one. T4 is never lowered.
2. The user's instruction ("flash 로", "pro 로") wins.
3. Any prompt that names local files, a directory or "this repo" needs the
   headless flags and the "do not modify files" sentence, at any tier.
4. An empty answer: check for soft-deny first; then raise once to
   `gemini-3.1-pro-high`. No `--effort` flag — the slug suffix is the knob.

Ask agy in **English**; the subagent summarises and saves; the main session
reports to the user in **Korean**.
