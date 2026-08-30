# Antigravity CLI (`agy`) — Reference Notes

Researched 2026-08-29 from https://antigravity.google/docs/cli/ (subpages: overview,
gcli-migration, headless, permissions, settings, reference, skills, plugins, subagents,
best-practices) cross-checked against the installed binary (`agy --help`, `agy models`)
and its bundled docs under `~/.gemini/antigravity-cli/builtin/skills/`.

agy is the successor of Gemini CLI. It reuses `~/.gemini/` for global config and auth.

## 1. Project-level configuration (`.agents/`)

There is **no `.antigravity/` directory and no `.antigravity.md`** — neither string exists
in the binary. The workspace convention is `.agents/` (aliases: `.agent/`, `_agents/`,
`_agent/`), discovered by walking up from CWD to the repo root.

| Path | Purpose |
|---|---|
| `.agents/rules/AGENTS.md` | Recommended consolidated project rules/context |
| `.agents/skills/<name>/SKILL.md` | Workspace skills |
| `.agents/mcp_config.json` | Workspace MCP servers |
| `.agents/hooks.json` | Lifecycle hooks |
| `.agents/agents/<name>.md` | Custom agents / subagents (`subagent: true` frontmatter) |
| `.agents/skills.json`, `plugins.json` | Registries pointing at out-of-tree dirs |

**Context files**: only `AGENTS.md` and `GEMINI.md` are recognized (peers, both loaded,
no frontmatter). They may live in any directory and scope to that directory and below.
`CLAUDE.md` is NOT read. The old workspace `.gemini/` directory is NOT scanned —
official migration doc: "relocate `.gemini/skills/` to `.agents/skills/`".

**Loading priority** (high → low): workspace project → declared configs
(`skills.json`/`plugins.json`) → global `~/.gemini/config/` → built-ins → global declared.

## 2. Settings

| Path | Contents |
|---|---|
| `~/.gemini/antigravity-cli/settings.json` | CLI settings + `permissions` |
| `~/.gemini/config/` | Shared config: `mcp_config.json`, `hooks.json`, `skills/`, `agents/`, `plugins/` |
| `~/.gemini/config/projects/<id>.json` | Per-project settings (override global) |
| `~/.gemini/GEMINI.md` | Global context file (auto-loaded) |

Notable keys: `toolPermission` (`request-review` default | `proceed-in-sandbox` |
`always-proceed` | `strict`), `enableTerminalSandbox`, `allowNonWorkspaceAccess`,
`verbosity`, `permissions` ({allow, deny, ask} — precedence Deny > Ask > Allow; actions
`read_file`, `write_file`, `read_url`, `execute_url`, `command`, `unsandboxed`, `mcp`).
There is **no `model` settings key** — default model is set via `/model` in the TUI;
per-run override with `--model`.

## 3. Headless / print mode

`-p` / `--print` / `--prompt` are aliases. Response → stdout, diagnostics → stderr.

```bash
agy -p "prompt"
agy -p "prompt" --output-format json | jq          # {conversation_id,status,response,usage,...}
agy -p "prompt" --output-format stream-json         # NDJSON: init, step_update*, result
agy -p "prompt" --json-schema '{"type":"object",...}' --output-format json
agy -p "follow-up" --continue                       # or --conversation <id>
```

**soft-deny trap (critical for scripting)**: a tool that needs approval it cannot get is
silently skipped; the run continues and **exits 0** with a notice on stderr. Gate on
`.status == "SUCCESS"` (values: SUCCESS, ERROR, CANCELED, INTERRUPTED, INVALID, WAITING,
RUNNING) rather than exit code, and do not discard stderr.

Ways to let tools run headlessly: `--dangerously-skip-permissions`, `permissions.allow`
in settings.json, or `--mode accept-edits` (file edits only).

Other flags: `--print-timeout` (**default 5m**), `--add-dir` (repeatable; replaces
`--include-directories`), `--effort low|medium|high`, `--sandbox`, `--agent`, `--project`,
`--disable-slash-commands` (use with templated prompts), `--log-file`.
**`--cwd` does not exist** despite the best-practices page.

Recommended CI pattern:
```bash
result=$(agy -p "Prompt" --output-format json --print-timeout 10m)
[[ "$(echo "$result" | jq -r .status)" == "SUCCESS" ]] || exit 1
echo "$result" | jq -r .response
```

## 4. Models (`agy models`, 2026-08-29)

```
gemini-3.7-flash-high|medium|low
gemini-3.6-flash-high|medium|low
gemini-3.5-flash-high|medium|low
gemini-3.1-pro-high|low
claude-sonnet-4-6, claude-opus-4-6-thinking, gpt-oss-120b-medium
```
Unknown slugs fail loudly (non-zero, status ERROR). `gemini-3-pro-preview` no longer exists.

## 5. Multimodal

Documented input path is clipboard paste (ctrl+v) in the interactive TUI for images
(PNG/JPEG/GIF/WebP/BMP/TIFF/SVG) and video (MP4/MOV/WebM/AVI). PDF is not in the documented
list. **No `@file`, `--attach`, or stdin-media flag exists for `-p`.**

Headless approach used in this repo: put the absolute file path in the prompt and let the
agent's `read_file` tool open it.

**Empirical result (2026-08-30, agy 1.1.22, PNG inside the workspace):**
- Plain `agy -p "Read the image file at /abs/summary.png ..."` → `read_file` auto-denied
  (stderr: `a tool required the "read_file" permission that headless mode cannot prompt
  for, so it was auto-denied`), `status: SUCCESS`, `response: ""`. The docs' claim that
  workspace reads are auto-allowed does NOT hold in print mode.
- Same prompt with `--dangerously-skip-permissions` → the image was read and described
  accurately. So path-in-prompt multimodal works once `read_file` is permitted.
- Fix: `"permissions": {"allow": ["read_file(*)"]}` in `~/.gemini/antigravity-cli/settings.json`
  (targets: `read_file(*)`, `read_file(/abs/path)`, `read_file(dir)`; recursive) or the
  per-call `--dangerously-skip-permissions` flag.

## 6. Skills

Directory with `SKILL.md` (YAML frontmatter `name`, `description`; optional `scripts/`,
`references/`, ...) — materially identical to Claude Code skills. Locations: workspace
`.agents/skills/`, global `~/.gemini/config/skills/` (the `~/.gemini/antigravity-cli/skills/`
path in one docs page is wrong per the binary changelog). Skills become slash commands in
the TUI.

## 7. Migration from Gemini CLI

One-time auto-import on first launch: extensions → plugins, global settings, session tokens.
`GEMINI.md`/`AGENTS.md` work unchanged. Manual: workspace skills → `.agents/skills/`;
remote MCP key `url`/`httpUrl` → `serverUrl`; `agy plugin import gemini` (also `claude`).

## 8. Doc-page reliability

| Page | Notes |
|---|---|
| `/docs/cli/headless/` | Good — most complete |
| `/docs/cli/permissions/`, `/docs/cli/mcp/`, `/docs/skills` | Good |
| `/docs/cli/reference/` | Settings table good; slash commands stale; no CLI flags |
| `/docs/cli/best-practices/` | Mentions non-existent `--cwd` |
| `/docs/cli/plugins/` | Global skills path likely wrong |
| `/docs/cli/prompting/`, `/docs/cli/projects/` | Thin |
