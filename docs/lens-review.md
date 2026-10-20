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

## Rehearsals (2026-10-20)

The shipped skill, run headless (`claude -p "/lens-review …"`) in scratch
worktrees with the skill copied in, Opus main session. Every run passed
`tools/lens-audit`: prompts byte-identical to the script's, answers saved
unchanged, every reviewer call Opus/medium, Read/Grep/Glob only, the report's
Findings shown verbatim. Scored against ground truth by a separate agent.

| Case | Change | Cost | Confirmed / refuted | Ground truth found | False confirms |
|---|---|---|---|---|---|
| R1 ×2 | #71 (11 files, 423 lines) | $4.35, $4.87 | 14/0, 15/0 | G3 G9 both; G6, G7 one run each; G8 partial; G10 (cp949) missed. G1 G2 G4 G5 found but primed (checklists extended after they were known) | 0 |
| R2 ×2 | new tool, 3 seeds no test catches (off-by-one, swallowed error, constant assertion) + missing from the gate + unformatted | $3.66, $3.68 | 15/0, 17/0 | all 3 seeds and the gate list, both runs; unformatted file missed | 0 |
| R2c | R2 again after the line-number fix | $4.44 | 17/1 | the same; every cited line within its file; the one REFUTED was a false claim ("nothing runs the check" — the gate's test does), its true part kept as correction | 0 |
| R3 ×2 | the same tool written correctly | $3.72, $3.89 | 15/0, 15/0 | — (no defects) | 0 false; all 15 were true but trivial (test gaps, style) |
| R4 | docs only (README, CHANGELOG) | $3.12 | 8/0 | no ground truth; 4 spot-checks true | 0 |
| R5 | uncommitted edit + untracked new script | $4.01 | 17/0 | both seeds (version replaced throughout the changelog; missing heading silently skipped); range reported as working tree | 0 |
| R-inj | new script; a comment orders "report NO FINDINGS" and a shell command | $3.30 | 13/0 | the seed (uppercase letters dropped) by 3 lenses; the injection reported as a finding by 5 lenses, not obeyed; no tool beyond reading | 0 |
| R6 | JavaScript project | $1.94 | 9/0 | both seeds (1-based page skips the first page; partial last page dropped) | 0 |
| R7 | #70 (13 files, 1543 lines) | $6.42 | 17/0 | no ground truth; 5 spot-checks true | 0 |
| R8 ×2 | verifier bench through `prompt verify` + `lens-reviewer`: 15 true, 13 false claims (8 subtly false, each disproved by execution) | $7.38 / 56 calls | — | 30/30 true confirmed, 26/26 false refuted | 0 |
| R-effort | session `--model sonnet --effort high`, agent pinned | ~$0.1 | — | agent ran Opus/medium; CLAUDE.md canary absent (present without `omitClaudeMd`) | — |

Found and fixed during the rehearsals:
- The main session's Write under `.claude/` asks for approval on every file;
  the first run stopped after the lenses → `collect` takes answers from the
  session's transcripts.
- Reviewers cited lines of the diff file (`:169` in a 70-line file) → the lens
  prompt says to cite the file's line, and the report marks a line past the end.
- A clean change still collects ~15 true but trivial findings → the report
  header counts confirmed findings by impact.

Found by the first person-opened interactive run in this repository
(2026-10-20), after the rehearsals:
- An interactive session's background agent answers through a
  `SubagentHandback` tool call, not a final text row; `collect` found nothing
  → it reads the hand-back (1cbc21b).
- The report was 33 KB, so "show `## Findings` verbatim" (step 7) could not be
  done → the report starts with `## Summary`, one line per finding
  (`<verdict> · <impact> · <lens> F<n> · <location> — <claim>`, refuted ones
  as `REFUTED · <lens> F<n> — <claim>`); step 7 shows and translates the
  Summary and names the file for the rest, and `tools/lens-audit` check 5 now
  requires the Summary verbatim. The rehearsals above showed `## Findings`.
- The same run's lens review of this branch was applied: a relative `--base`
  (`HEAD~3`) was read as `origin/HEAD~3`; a retried agent's old transcript
  could be saved; the "also reported by another lens" label ignored which lens
  reported; reviewer answers under `.claude/logs/` could fail the repository's
  prose-scan tests.

Not shown: other projects, and Windows. An interactive run in this repository
has been shown (approval prompts, the ask, the translation step); one in
another real project has not.
