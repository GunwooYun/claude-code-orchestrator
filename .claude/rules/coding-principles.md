---
paths:
  - "**/*.py"
  - ".claude/skills/isolated-review/run-review"
  - ".claude/skills/isolated-review/field-report"
  - ".claude/skills/orchestrator-version/check"
---
# Coding Principles (Python)

Loaded when a Python file is read or edited. `/initproject` adjusts the globs to the stack.

- **Simplicity first**: readable over clever; no abstraction without a second user.
- **Single responsibility**: one function, one job. Files 200–400 lines, 800 at most.
- **Early return** instead of nested conditions.
- **Type hints on every function** (ruff `ANN` enforces it in the gate).
- **Immutability**: build new objects (`{**data, "k": v}`) rather than mutating shared ones.
- **Naming**: snake_case functions/variables, PascalCase classes, UPPER_SNAKE_CASE constants,
  meaningful English names.
- **No magic numbers**: name the constant (`MAX_RETRIES = 3`).

## Security in Python

```python
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable is required")

cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))   # never an f-string

raise Exception("Database connection failed")                       # details to the log only
```

Audit dependencies regularly (`pip-audit`).
