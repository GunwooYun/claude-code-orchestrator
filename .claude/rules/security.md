# Security Rules

Applies to every file, not only code — secrets leak through settings, CI and shell files too.

- **No secrets in the repository**: no hardcoded API keys or passwords; never commit `.env`.
  Read secrets from the environment and fail loudly when one is missing.
- **No secrets in logs.**
- **Validate external input** at the boundary; parameterize queries, never concatenate them.
- **Terse error messages**: details go to private logs, not to the caller.
- **Dependencies**: pin versions, remove unused ones.

Python examples: `.claude/rules/coding-principles.md` (loaded when a Python file is opened).
