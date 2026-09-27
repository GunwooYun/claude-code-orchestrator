#!/usr/bin/env python3
"""
PreToolUse hook: Suggest deep-reasoning consultation before Write/Edit.

This hook analyzes the file being modified and suggests deep-reasoning consultation
for design decisions, complex implementations, or architectural changes.
"""

import json
import sys

# Input validation constants
MAX_PATH_LENGTH = 4096
MAX_CONTENT_LENGTH = 1_000_000


def validate_input(file_path: str, content: str) -> bool:
    """Validate input for security."""
    if not file_path or len(file_path) > MAX_PATH_LENGTH:
        return False
    if len(content) > MAX_CONTENT_LENGTH:
        return False
    # Check for path traversal
    if ".." in file_path:
        return False
    return True


# Patterns that suggest design/architecture decisions
DESIGN_INDICATORS = [
    # File patterns
    "DESIGN.md",
    "ARCHITECTURE.md",
    "architecture",
    "design",
    "schema",
    "model",
    "interface",
    "abstract",
    "base_",
    "core/",
    "/core/",
    "config",
    "settings",
    # Code patterns in content
    "class ",
    "interface ",
    "abstract class",
    "def __init__",
    "from abc import",
    "Protocol",
    "@dataclass",
    "TypedDict",
]

# Prose, data and config. The SIZE rule below does not apply to these: a long
# document is not a design decision, and a hook that fires on every substantial
# write trains people to ignore hook output (the same argument lint-on-save.py
# makes about repeating its notice). A path that looks like design still
# triggers, whatever it contains — DESIGN.md is prose and is exactly the case
# this hook exists for.
NON_DESIGN_SUFFIXES = frozenset(
    {
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".adoc",
        ".tex",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".csv",
        ".tsv",
        ".lock",
        ".log",
        ".jsonl",
    }
)

# Files that are typically simple edits (skip suggestion)
SIMPLE_EDIT_PATTERNS = [
    ".gitignore",
    "README.md",
    "CHANGELOG.md",
    "requirements.txt",
    "package.json",
    "pyproject.toml",
    ".env.example",
]


def should_suggest_deep_reasoning(
    file_path: str, content: str | None = None
) -> tuple[bool, str]:
    """Determine if deep-reasoning consultation should be suggested."""
    filepath_lower = file_path.lower()

    # Skip simple edits
    for pattern in SIMPLE_EDIT_PATTERNS:
        if pattern.lower() in filepath_lower:
            return False, ""

    # Check file path for design indicators
    for indicator in DESIGN_INDICATORS:
        if indicator.lower() in filepath_lower:
            return True, f"File path contains '{indicator}' - likely a design decision"

    # Content rules apply to source only. Prose and config reach this point when
    # their PATH did not look like design, and for those the size of the write
    # says nothing about whether a design decision is being made.
    suffix = filepath_lower.rsplit(".", 1)
    extension = f".{suffix[1]}" if len(suffix) == 2 else ""
    if extension in NON_DESIGN_SUFFIXES:
        return False, ""

    # Check content if available
    if content:
        # New file with significant content
        if len(content) > 500:
            return True, "Creating new file with significant content"

        # Check for design patterns in content
        for indicator in DESIGN_INDICATORS:
            if indicator in content:
                return (
                    True,
                    f"Content contains '{indicator}' - likely architectural code",
                )

    # New files in src/ directory
    if "/src/" in file_path or file_path.startswith("src/"):
        if content and len(content) > 200:
            return True, "New source file - consider design review"

    return False, ""


def main() -> None:
    try:
        data = json.load(sys.stdin)
        tool_input = data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("content", "") or tool_input.get("new_string", "")

        # Validate input
        if not validate_input(file_path, content):
            sys.exit(0)

        should_suggest, reason = should_suggest_deep_reasoning(file_path, content)

        if should_suggest:
            # Return additional context to Claude
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": (
                        f"[Design Review Reminder] {reason}. "
                        "Consider consulting the deep-reasoning subagent before this change. "
                        "**Recommended**: Use Task tool with subagent_type='deep-reasoning' "
                        "(isolated context; returns a concise recommendation). "
                        "If you are a subagent, report back to the orchestrator instead."
                    ),
                }
            }
            print(json.dumps(output))

        sys.exit(0)  # Always allow, just add context

    except Exception as e:
        # Don't block on errors
        print(f"Hook error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
