# Development Environment

Project development environment and toolchain.

## Package Management: uv

**Do not use pip directly. All commands must go through uv.**

```bash
# Add packages
uv add <package>
uv add --dev <package>    # Dev dependency

# Sync dependencies
uv sync

# Run scripts
uv run <command>
uv run python script.py
uv run pytest
```

### pyproject.toml

Manage dependencies in `pyproject.toml`:

```toml
[project]
dependencies = [
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.8",
]
```

## Linting & Formatting: ruff

```bash
# Check
uv run ruff check .

# Auto-fix
uv run ruff check --fix .

# Format
uv run ruff format .
```

### ruff Configuration (pyproject.toml)

```toml
[tool.ruff]
target-version = "py311"   # 이 저장소 기준. 프로젝트에 맞게
line-length = 88

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "UP",     # pyupgrade
]
ignore = ["E501"]  # line too long (formatter handles)

[tool.ruff.format]
quote-style = "double"
```

## Type Checking: ty

```bash
# Run type check
uv run ty check <체크할 경로>
```

### ty Features

- Fast Rust-based type checker (by Astral)
- Same ecosystem as ruff / uv
- mypy-compatible type annotations

## Notebooks: marimo

Interactive Python notebook environment.

```bash
# Create/edit notebook
uv run marimo edit notebook.py

# Run notebook (CLI)
uv run marimo run notebook.py

# Deploy as app
uv run marimo run notebook.py --host 0.0.0.0 --port 8080
```

### marimo Features

- **Pure Python files** (.py): Git-friendly
- **Reactive**: Auto-tracks cell dependencies
- **Reproducible**: No execution order dependency

### marimo Best Practices

```python
# Bad: Mutating global state
data = []
def add_item(item):
    data.append(item)  # Side effect

# Good: Pure function
def add_item(data: list, item) -> list:
    return [*data, item]
```

## Task Runner

Manage multiple tool executions in `pyproject.toml` scripts or poe:

```toml
[tool.poe.tasks]
# 게이트는 읽기 전용이어야 실패할 수 있다 — 자동 수정 명령을 게이트에 넣지 않는다.
lint = "ruff check ."
format-check = "ruff format --check ."
typecheck = "ty check <체크할 경로>"
test = "pytest"
all = ["lint", "format-check", "typecheck", "test"]

# 파일을 고치는 것은 사람이 의도적으로 돌리는 쪽에 둔다.
fix = "ruff check --fix ."
format = "ruff format ."
```

**`src/` 를 전제하지 않는다.** 없는 경로에 `ty` 는 **exit 0** 을 내므로(거짓 통과)
체크 대상은 실제로 존재하는 경로로 적는다. 이 저장소 자신은 `.claude/hooks` 와
`.claude/skills/checkpointing/checkpoint.py` 를 체크한다 — `/initproject` 가
프로젝트마다 이 파일을 다시 쓴다.

## Common Commands

```bash
# Initialize
uv init
uv venv
source .venv/bin/activate

# Install dev dependencies
uv sync --all-extras

# Quality check (all)
uv run ruff check . && uv run ruff format --check . && uv run ty check <체크할 경로> && uv run pytest

# Or via poe — `poe` 는 프로젝트 환경 안에만 있다. 맨몸으로 부르면 exit 127
uv run poe all
```

## Pre-commit Checklist

- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format --check .` passes
- [ ] `uv run ty check <체크할 경로>` passes
- [ ] `uv run pytest` passes
