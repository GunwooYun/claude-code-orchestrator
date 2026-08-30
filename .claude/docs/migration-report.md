# Migration Report — Codex → deep-reasoning subagent, Gemini CLI → Antigravity CLI

Prepared for code review. Period: 2026-08-28 → 2026-08-30. Branch: `main` of
`GunwooYun/claude-code-orchestrator` (fork of `gaebalai/claude-code-orchestrator`,
upstream is a single squashed commit `e96c71c`).

## 1. Background and goals

The upstream template orchestrates two external CLIs from Claude Code:
Codex CLI (deep reasoning: design review, debugging, trade-offs) and Gemini CLI
(research, large-context codebase analysis, multimodal), both called from a
`general-purpose` subagent to keep the main context small.

Constraints from the user's environment:

1. **No OpenAI account** → Codex's role must be taken over by Claude itself
   (Claude Fable 5), preserving the context-isolation design.
2. **Gemini CLI is deprecated upstream** → migrate to its successor,
   Antigravity CLI (`agy` 1.1.22), which the user installed and authenticated.
3. `.claude/` must only change where the functional migration requires it;
   unrelated rules (coding-principles, testing, security, language,
   dev-environment), docs templates, and unrelated skills stay untouched.
4. Template stays standalone: adopters copy only `.claude/`, `.agents/`,
   `CLAUDE.md`.
5. Commit messages carry no `Co-Authored-By` trailer (user preference).

## 2. Key design decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Codex replaced by a new **`deep-reasoning`** subagent (`.claude/agents/deep-reasoning.md`), invoked **directly from the main orchestrator** via `Task(subagent_type="deep-reasoning")`. | Subagents cannot spawn subagents, so the old "general-purpose shells out to codex" pattern cannot become "general-purpose spawns deep-reasoning". Main → deep-reasoning keeps the isolation property. |
| D2 | `deep-reasoning` is **read-only** (`tools: Read, Grep, Glob, Bash, WebFetch, WebSearch`, no Edit/Write), `model: inherit`. | Mirrors Codex `--sandbox read-only`; the session model is Fable 5, so the reviewer quality is preserved. Implementation stays with main/general-purpose. |
| D3 | Name is role-based (`deep-reasoning`), not model-based (`claude-fable`); docs write "deep-reasoning (Claude Fable)". | Stays correct if the session model changes; matches Claude Code's own agent naming (`general-purpose`, `Explore`, `Plan`). User confirmed. |
| D4 | Gemini-named files renamed to **`antigravity-*`** (external CLI keeps product naming). | Consistent with how the template already named Gemini/Codex artifacts. User chose this over keeping `gemini-*` or role-based `research-*`. |
| D5 | Project config moves from `.gemini/` to **`.agents/`** (`rules/AGENTS.md`, `skills/context-loader/`). `.gemini/settings.json` deleted. | agy reads `.agents/` (skills, rules, mcp, hooks) and `AGENTS.md`/`GEMINI.md` context files; it does **not** scan a project `.gemini/` dir and has no `.antigravity/` convention (verified against the binary and the official migration page). |
| D6 | Headless file access: file-reading patterns (codebase analysis, multimodal) carry **`--dangerously-skip-permissions --sandbox`**; web-research patterns carry no flags. A global `read_file(*)` allow rule is documented as optional hardening. | agy permissions cannot be defined inside the repo; the flag approach keeps the template self-contained and avoids a silent-failure mode on new machines (see §5). User chose this over the global rule. |
| D7 | `checkpoint.py` keeps its `codex` log-parsing branch as harmless dead code; everything else Codex-related is removed. | Minimal diff; it only renders historical log entries. |

## 3. Changes by commit

Commit hashes are on `origin/main`.

### Codex → deep-reasoning (2026-08-28)

- `0362c51 feat: add deep-reasoning subagent` — new `.claude/agents/deep-reasoning.md`.
- `90305b2 refactor: replace Codex with deep-reasoning subagent in rules and skills`
  - `.claude/rules/codex-delegation.md` → `deep-reasoning-delegation.md` (rewritten; How-to-Consult is now a Task-tool block).
  - `.claude/skills/codex-system/` → `.claude/skills/deep-reasoning/` (SKILL.md rewritten; `references/code-review-task.md`, `refactoring-task.md` wrappers converted from `codex exec` to Task prompts; `troubleshooting.md`, `delegation-patterns.md` deleted as CLI-specific; `agent-prompts.md` unchanged).
  - `startproject/SKILL.md` Phase 3 and Phase 6 Option B now spawn `deep-reasoning`; `references/task-patterns.md` wording.
  - `gemini-delegation.md`, `gemini-system/*` "use Codex" → deep-reasoning; `checkpointing/SKILL.md` labels; `agents/general-purpose.md` Codex sections removed, plus an explicit note that design/debug questions go back to the orchestrator (no nested subagents).
  - Fixed a leftover Japanese trigger phrase in `lib-research-task.md`.
- `10c83dd refactor: rewire hooks and settings from Codex CLI to deep-reasoning subagent`
  - `check-codex-before-write.py` → `suggest-deep-reasoning-before-write.py`, `check-codex-after-plan.py` → `suggest-deep-reasoning-after-plan.py`; suggestion strings in `agent-router.py`, `post-test-analysis.py`, `post-implementation-review.py` now point to `Task(subagent_type='deep-reasoning')`.
  - `log-cli-tools.py`: codex parsing removed.
  - `settings.json`: hook paths synced, `Bash(codex:*)` removed. (Lesson: a hook rename with stale `settings.json` blocks every Edit — the PreToolUse hook errors out. settings.json must be updated first / in the same commit.)
- `c14ebd3 chore: remove .codex and drop Codex from checkpoint/Gemini context` — `.codex/` deleted (its `skills/design-tracker` was a symlink into `.claude`), `checkpoint.py` CONTEXT_FILES, `.gemini/GEMINI.md` escalation table.
- `372ff6b docs: rewrite CLAUDE.md and README for Claude+Gemini architecture`.

### Gemini CLI → Antigravity CLI (2026-08-29/30)

- `477cfe7 refactor: migrate project config from .gemini to .agents`
  - `.gemini/GEMINI.md` → `.agents/rules/AGENTS.md` (content rewritten for agy: call signatures, path-in-prompt multimodal, soft-deny instruction to the agent).
  - `.gemini/skills/context-loader/` → `.agents/skills/context-loader/`.
  - `.gemini/settings.json` removed (old Gemini CLI schema; agy does not read it).
- `4a6d843 refactor: migrate rules, skills, and agent docs from Gemini CLI to Antigravity CLI`
  - `rules/gemini-delegation.md` → `rules/antigravity-delegation.md` (rewritten; adds "Headless Caveats").
  - `skills/gemini-system/` → `skills/antigravity-system/` (SKILL.md rewritten; `references/use-cases.md` and `lib-research-task.md` transformed: `gemini -p` → `agy -p`, `--include-directories` dropped, stdin `< file` → "Read the file at ./file." path-in-prompt, `2>/dev/null` removed, old rate-limit section replaced by quota note).
  - `startproject` Phase 1, `deep-reasoning/SKILL.md` integration table, `checkpointing/SKILL.md` diagram (now CLAUDE.md + `.agents/rules/AGENTS.md`), `agents/general-purpose.md` "Calling Antigravity CLI".
- `8f54538 refactor: rewire hooks, settings, and checkpoint for agy`
  - `suggest-gemini-research.py` → `suggest-antigravity-research.py` (settings.json synced first, via Bash, to avoid the hook-desync trap).
  - `agent-router.py`: `ANTIGRAVITY_TRIGGERS`, suggestion text.
  - `log-cli-tools.py`: detects `agy` with a word-boundary regex (`(?:^|[\s;&|])agy\s`) to avoid substring false positives; parses `-p|--print|--prompt`; `tool: "antigravity"`; model from `--model` else `"default"`.
  - `settings.json`: `Bash(gemini:*)` → `Bash(agy:*)`.
  - `checkpoint.py`: CONTEXT_FILES `antigravity → .agents/rules/AGENTS.md`; log tool key `antigravity`.
- `dbe6d8f docs: update CLAUDE.md/README for agy and add Antigravity CLI research notes` — `.claude/docs/research/antigravity-cli.md` (official-docs digest + empirical findings).
- (uncommitted at time of writing → next commit) **Option (b) headless flags**: `--dangerously-skip-permissions --sandbox` added to every file-reading pattern in `antigravity-delegation.md`, `antigravity-system/SKILL.md`, `references/use-cases.md` (13 commands), `agents/general-purpose.md`, `startproject` Phase 1; README paragraph reworded (global rule now optional); research notes updated.

### Environment changes (outside the repo)

- Installed: Claude CLI 2.1.250 (native installer), node (brew), Antigravity CLI 1.1.22 (user).
- Removed: `@google/gemini-cli` 0.57.0 (npm) — installed on 08-28, superseded the next day.
- Repo-local git identity set to the user's name/email; four early commits had a `Co-Authored-By` trailer stripped via `filter-branch` before push.
- `~/.gemini/` is agy's own global directory (auth `oauth-personal`, `antigravity-cli/`, `config/`); nothing there was modified by this work.

## 4. Verification performed

| Check | Result |
|-------|--------|
| `grep -rni` sweep for `codex`, `gemini -p`, `gemini cli`, `--include-directories`, `gemini-3-pro-preview`, `.gemini/`, `GEMINI.md` (excluding `.git`, `docs/research`, `logs`) | Clean except intentional mentions ("successor of Gemini CLI", `~/.gemini/` auth path, README fork note, `checkpoint.py` codex dead code). |
| `python3 -m py_compile` on all hooks + `checkpoint.py` | OK |
| `agent-router.py` sample prompts ("설계", "조사해") | Correct deep-reasoning / agy suggestions |
| `log-cli-tools.py` with `agy -p "..." --model gemini-3.1-pro-high` | Logged `tool=antigravity`, model captured |
| `log-cli-tools.py` false-positive check (`echo strategy`) | No log (word-boundary regex works) |
| `suggest-antigravity-research.py` WebSearch sample | Suggestion emitted |
| `checkpoint.py` dry run | Runs; writes Session History to CLAUDE.md and `.agents/rules/AGENTS.md` (test pollution was stripped afterwards) |
| Live hooks during the session | The renamed hooks fired with the new wording during later edits |
| `deep-reasoning` subagent | Spawned successfully via Task; confirmed its own definition |
| `agy -p "Reply with exactly: OK" --output-format json` | `status: SUCCESS`, `response: "OK"` |
| Multimodal, plain `agy -p` reading `summary.png` | `read_file` **auto-denied**, empty response, `status: SUCCESS` (soft-deny reproduced) |
| Same with `--dangerously-skip-permissions` | Image read and described accurately |
| Same with `--dangerously-skip-permissions --sandbox` | Works (basis for D6) |

## 5. Empirical findings worth reviewer attention

1. **Headless soft-deny**: in `agy -p`, a tool without permission is skipped silently, the run exits 0 and reports `status: SUCCESS` with an empty response. Contrary to the docs' "workspace reads are auto-allowed", `read_file` on a workspace file was denied in print mode. All docs now instruct: never `2>/dev/null` an agy call, gate scripted calls on JSON `.status`, and the agent-side `AGENTS.md` asks agy to state a denial explicitly instead of returning empty.
2. **No in-repo permissions**: `.agents/` supports skills/rules/mcp/hooks/agents but not permissions; those live only in `~/.gemini/antigravity-cli/settings.json` or agy-managed `~/.gemini/config/projects/<id>.json`. Hence D6.
3. **Docs reliability**: `--cwd` in best-practices does not exist; one docs page gives the wrong global skills path; model slug `gemini-3-pro-preview` no longer exists (`agy models` lists `gemini-3.1-pro-high/low`, `gemini-3.7-flash-*`, …).
4. **Multimodal coverage**: images verified (PNG). PDF/video/audio via path-in-prompt are documented in the template but **not empirically tested** (PDF is not in agy's documented paste-support list).

## 6. Known limitations / open risks

- `--dangerously-skip-permissions` auto-approves writes and MCP tools for the duration of that call; `--sandbox` restricts terminal commands only. Mitigation is procedural: these flags appear only in read-only research prompts inside git-tracked repos. Reviewers may want to weigh a stricter default.
- `general-purpose` subagent runs on `model: sonnet` (unchanged from upstream); it now carries slightly more instruction text about soft-deny handling.
- `checkpoint.py` still contains codex parsing branches (dead code by decision D7) and its `--full` mode diffs `HEAD~10` when `--since` is absent (upstream behaviour, untouched).
- Pre-existing upstream quirks not addressed (out of scope by constraint 3): `lint-on-save.py` reads `CLAUDE_TOOL_INPUT` env instead of stdin JSON; two hooks read `tool_output` where the actual key is `tool_response`; `pyproject.toml` pins mypy/py311 while rules/hooks assume ty/py312; `post-implementation-review.py` state file is a fixed `/tmp` path; `design-tracker` skill still has Japanese trigger phrases.
- Template tech-stack rules (uv/ruff/ty/pytest) were deliberately kept even though the user's target project is Django(pip)+Vite.

## 7. Suggested review focus

1. D1/D2 — is a read-only `deep-reasoning` subagent an adequate substitute for Codex `workspace-write` implementation mode? (Implementation now always goes through main/general-purpose.)
2. D6 — flag-based headless access vs. global permission rule; is `--sandbox` sufficient mitigation?
3. `log-cli-tools.py` regexes — prompt extraction assumes a single quoted argument; multi-line prompts with embedded quotes are not handled (same limitation as upstream).
4. Consistency: every `deep-reasoning` / `antigravity-system` / `agy` reference across rules, skills, hooks, `settings.json`, `CLAUDE.md`, `README.md`, `.agents/rules/AGENTS.md`.
5. Whether `.agents/rules/AGENTS.md` (auto-loaded by agy) contains only agy-facing instructions (no Claude-facing rules leaked in).
