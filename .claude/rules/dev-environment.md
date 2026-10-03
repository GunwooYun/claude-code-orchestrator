# Development Environment

This repository's toolchain. `/initproject` rewrites this file for each project.

## Package management: uv

**Do not use pip directly — everything goes through uv.**

```bash
uv add <package>            # runtime dependency
uv add --dev <package>      # dev dependency
uv sync --all-extras        # install, including dev extras
uv run <command>            # run inside the project environment
```

## Quality tools

| Tool | Check (read-only) | Fix (on purpose, never in the gate) |
|---|---|---|
| ruff lint | `uv run ruff check .` | `uv run ruff check --fix .` |
| ruff format | `uv run ruff format --check .` | `uv run ruff format .` |
| ty | `uv run ty check <paths>` | — |
| pytest | `uv run pytest` | — |

- **The gate must be read-only** so it can fail: no auto-fixing command in `poe all`.
- **Do not assume `src/`.** `ty` exits 0 on a path that does not exist (a false pass), so name real
  paths. This repository checks `.claude/hooks`, `checkpoint.py` and the extensionless scripts
  listed in `pyproject.toml`.

## Task runner (poe)

```bash
uv run poe all     # lint + format-check + typecheck + test — the gate
uv run poe fix     # mutating helpers, run deliberately
```

`poe` exists only inside the project environment — called bare it exits 127.

## Before committing

`uv run poe all` passes, and `git status` shows only what you meant to change.
