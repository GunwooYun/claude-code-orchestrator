---
name: agy-models
description: Choose which agy (Gemini) model each delegation tier T1–T4 uses — shows the Model policy table and the slugs agy offers, asks the user per tier, writes the table and re-probes. Run from /initproject Step 3c, and again whenever .claude/bin/agy-probe reports STALE or the user wants different tiers (e.g. high everywhere when agy quota is spare).
disable-model-invocation: true
---

# agy models per tier

The Model policy table in `.claude/rules/antigravity-delegation.md` is the only
place a slug is written (the probe and every copy read it), so a choice here
edits that table and nothing else.

**Run only when `.claude/bin/agy-probe` reports `READY` or `STALE`.** On
`MISSING` or `UNAUTHENTICATED` agy cannot list its models — install or log in
first (`/initproject` Step 3b says how).

1. Show the current table (tier, task, slug) and the Gemini slugs agy offers:
   `agy models` — the first column of each `gemini-*` line. The others it lists
   are out of scope: agy is used for Gemini's breadth and grounding.
2. One AskUserQuestion with four questions, T1, T2, T3, T4: options are the
   offered Gemini slugs, the current slug first when it is still offered. A
   question takes 2–4 options: with more than four offered (eleven on
   2026-08-29), list them all in text, offer the current slug and the newest
   family's, and take any other through "Other" — only a slug `agy models`
   listed. Say the trade-off once — a higher tier per call costs more agy
   quota; with quota to spare, high everywhere is a reasonable choice.
3. Write the four slugs into the table rows (keep T4's `--print-timeout 9m`).
4. Re-run `.claude/bin/agy-probe`; done at `READY`. On `STALE`, the table and
   `agy models` disagree — fix the row it names.

Report the four slugs to the user. The template's next upgrade shows the rule
file as MERGE: keep the table rows.
