# Lens review — design and measurements

`/lens-review` (`.claude/skills/lens-review/`) reviews a change in the current
session through five lenses, then has every finding checked for truth by a
separate verifier. This file records why it is built this way. Read it before
changing the skill, the script, the prompts or the `lens-reviewer` agent.

## History

- The early adapted copy of the template had a `/review` skill: five lenses as
  parallel subagents, then an adversarial "try to REFUTE" pass on critical and
  major findings. A work project ran it four times.
- This repository had `/lens-review` (three lenses, conflict surfacing) from
  2026-09-26. It found three real defects here (commit 393f9d1, DESIGN.md) and
  was removed in 2.0.0 (2026-10-03) as "never run in real work" — a judgement
  made without counting use in any adopting project.
- 2026-10-19/20: the review group was re-examined against the fork baselines,
  and the early `/review` was measured before anything was restored.

## Measurements (2026-10-19/20)

All runs reviewed the same change unless stated: #71 (Windows save check, 11
files, 423 lines, `734701e` against `4ec31a9`), whose defects are known — from
its /isolated-review report, from a later real Windows run, and from mutation
runs. Opus throughout; the early skill was installed in a scratch worktree and
run headless.

| Question | Result |
|---|---|
| Cost of five lenses (+ refutation of majors) | $1.64–3.24 per run (8 runs). Estimated $12–30 beforehand; the estimate was wrong |
| Effort medium vs high (4 runs each) | $1.97 vs $2.96 average; 8.75 vs 11.75 findings. The only real defect high added: a guide that clones a branch deleted after merge (2 of 4 high runs; /isolated-review also found it) |
| Lenses vs /isolated-review on #71 | Different finds. Lenses: five weak tests, confirmed by mutation (a test that ignores the hook's exit code, an environment variable not restored, a conversion tested only for one runner, a marker checked only as source text, untested shebang cases), a leftover `__pycache__` after upgrade. A1: the branch-clone guide, POSIX-only tests, a README contradiction. Neither: the cp949 stdin bug that only a real Windows run showed |
| Scope resolved by the main session | Run 1 read `/review <ref>` as one commit and sent all five lenses to the previous change. → the scope is resolved by the script |
| Refutation, majors only (as shipped in the early copy) | Ran in 3 of 8 runs: lenses rated almost everything minor |
| Refutation of every finding, original prompt (2 runs) | $6.47 per run; 10 of 31 refuted, including two findings mutation had confirmed (the exit-code test; the environment leak, refuted as "harmless") |
| Why | The main session had rewritten the verifier prompts, adding "determine real impact", "weigh real occurrence, not theoretical possibility" and an example answer "leaks but has no effect". Verifiers answered "the gap is real, but REFUTED" |
| Verifier bench: 12 fixed claims (7 true, 5 false) × 3 prompts × 2 | Original "try to REFUTE", truth-only rules, truth-only + execution: all 14/14 true confirmed, 10/10 false refuted. Execution added nothing and cost 1.6× |
| Full pipeline with the verifier prompt locked (2 runs) | 27/27 prompts byte-identical in the transcripts; 0 wrong refutations; corrections still made (a proposed fix that would break code, a narrower scenario, wrong line numbers); $5.81 / $5.92 at effort high |
| Seeded majors (3, each broke a branch test), original skill (2 runs) | Found 3/3 in both, all rated major; refuters confirmed 3/3. Easy seeds — not evidence for subtle defects |
| Agent frontmatter vs session flags | A session started with `--model sonnet --effort high` ran the agent as Opus/medium; with `omitClaudeMd: true` a canary in CLAUDE.md did not reach the agent, without it the agent quoted it |

Raw results: `.claude/docs/research/fork-review-group1-review.md` in the
maintainer's clone (local, not shipped).

## Design

| Decision | Because |
|---|---|
| Five lenses, always | The lenses found what A1 missed; choosing lenses per change was the main session's judgement, which is what failed on scope |
| Scope by script (`scope`) | The main session misread the scope once and five reviewers followed it |
| Fixed prompts printed by the script; the verifier prompt built from the saved lens answer | The only measured cause of wrong refutations was the main session editing verifier prompts |
| Verify every finding; truth only; impact separate; drop only REFUTED | Lenses rate most findings minor, so "verify majors" rarely ran; verifying all costs ~2× and turned wrong kills into corrections once the prompt was locked. Whether a finding matters in real use is the user's call (CLAUDE.md), not the verifier's |
| Report never refuses; missing verdicts are UNVERIFIED, unparsed text is shown, exit 3 | A refusing report throws away a paid run; a silent parser loses findings nobody sees |
| Agent: Opus, effort medium, Read/Grep/Glob, `omitClaudeMd` | The measured configuration; medium is ⅔ the cost of high for almost the same finds. No shell: reviewers read untrusted diffs, and execution did not improve verification. CLAUDE.md holds the author's rationale |
| Next to /isolated-review, not instead | They find different things; A1 is the separate-process last word |

Rejected:
- **Restore the early `/review` as is.** Its scope came from the main
  session's reading of the arguments, and its refutation pass ran for majors
  only, which almost never happened.
- **Lenses inside /isolated-review.** One process cannot run five agents;
  several `claude -p` processes would triple cost and the report could no
  longer be shown verbatim.
- **Verifiers that run code.** No accuracy gain on the bench, 1.6× cost, and a
  shell for an agent that reads untrusted text.

## Limits

- Read-only reviewers miss defects that only show when code runs.
- The lens checklists were extended (branch names in guides, leftovers from the
  previous version, tests that ignore results or leak environment) after the
  #71 measurements. Results on #71 after that change do not show general
  recall; the other rehearsal cases do.
- Steps that pass text unchanged are the main session's; the script cannot
  enforce them. `tools/lens-audit` checks them from transcripts.
- `CLAUDE_CODE_EFFORT_LEVEL` overrides the agent's pinned effort.
- Projects without Opus cannot run it as shipped.

## Rehearsals

See the table appended below by the implementation unit (2026-10-20).
