#!/usr/bin/env python3
"""
Checkpoint script: Read CLI logs and update agent context files.

Usage:
    python checkpoint.py [--since YYYY-MM-DD]           # Session history mode
    python checkpoint.py --full [--since YYYY-MM-DD]    # Full checkpoint mode
    python checkpoint.py --full --analyze               # Full checkpoint + skill analysis

Session History Mode (default):
    Updates CLAUDE.md, .agents/rules/AGENTS.md with CLI consultation history.

Full Checkpoint Mode (--full):
    Creates comprehensive checkpoint file in .claude/checkpoints/ including:
    - Git commits and file changes
    - CLI tool consultations (agy)
    - Design decisions changes
    - Session summary

Analyze Mode (--full --analyze):
    After creating checkpoint, outputs a prompt for AI analysis to extract
    reusable skill patterns. Use with subagent to analyze and suggest new skills.
"""

import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
LOG_FILE = PROJECT_ROOT / ".claude" / "logs" / "cli-tools.jsonl"
CHECKPOINTS_DIR = PROJECT_ROOT / ".claude" / "checkpoints"
DESIGN_FILE = PROJECT_ROOT / ".claude" / "docs" / "DESIGN.md"

SESSION_HISTORY_HEADER = "## Session History"

# Each context file names the heading its history lives under. AGENTS.md uses a
# different one, and assuming a single header made this script append a second,
# parallel section instead of updating the one already there.
CONTEXT_FILES: dict[str, dict[str, object]] = {
    "claude": {
        "path": PROJECT_ROOT / "CLAUDE.md",
        "header": SESSION_HISTORY_HEADER,
    },
    "antigravity": {
        "path": PROJECT_ROOT / ".agents" / "rules" / "AGENTS.md",
        "header": "## Consultation History",
    },
}

# How far back to look when no --since is given. A hard-coded `HEAD~10` failed
# outright on a repository with fewer than 11 commits, and the failure looked
# like "no changes" rather than an error.
DEFAULT_HISTORY_DEPTH = 10


def parse_since(value: str) -> datetime:
    """
    Turn a --since value into the start of that day in LOCAL time.

    Local, not UTC: entries are grouped by local date (see local_date), so a UTC
    boundary drops entries that belong to the requested local day.

    Raises ValueError on anything unparseable, so the caller can report it
    instead of dying with a traceback.
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def since_argument(value: str) -> str:
    """
    argparse type for --since: validate now, report cleanly, keep the string.

    Without this a malformed value reached datetime.fromisoformat deep in
    parse_logs and surfaced as a traceback.
    """
    try:
        parse_since(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--since must be a date such as 2026-09-25 (got {value!r}): {exc}"
        ) from exc
    return value


def parse_entry_timestamp(raw: object) -> datetime | None:
    """Parse one entry's timestamp, or None when it is unusable."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def parse_logs(since: str | None = None, log_file: Path | None = None) -> list[dict]:
    """
    Parse the JSONL log and return entries, newest-first order preserved.

    A malformed line, a missing timestamp or an unparseable one skips that entry
    only. Previously a single bad timestamp raised an uncaught ValueError and
    aborted the whole checkpoint, losing the rest of the session.
    """
    path = log_file or LOG_FILE
    if not path.exists():
        return []

    since_dt = parse_since(since) if since else None

    entries: list[dict] = []
    skipped = 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not isinstance(entry, dict):
                skipped += 1
                continue
            # Always require a usable timestamp, not only when filtering. An
            # unparseable one used to reach local_date, which fell back to the
            # first ten characters and produced headings like "### broken-tim".
            entry_dt = parse_entry_timestamp(entry.get("timestamp"))
            if entry_dt is None:
                skipped += 1
                continue
            if since_dt is not None and entry_dt < since_dt:
                continue
            entries.append(entry)

    if skipped:
        print(
            f"Note: skipped {skipped} unusable log line(s) in {path} "
            "(malformed JSON or timestamp)"
        )

    return entries


def run_git_command(args: list[str], cwd: Path | None = None) -> str | None:
    """Run a git command and return output, or None if failed."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd or PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_git_commits(since: str | None = None) -> list[dict]:
    """Get git commits since the specified date."""
    args = ["log", "--pretty=format:%H|%ai|%s", "-n", "100"]
    if since:
        args.extend(["--since", since])

    output = run_git_command(args)
    if not output:
        return []

    commits = []
    for line in output.split("\n"):
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append(
                {
                    "hash": parts[0][:7],
                    "date": parts[1],
                    "message": parts[2],
                }
            )
    return commits


def resolve_commit_range(
    depth: int = DEFAULT_HISTORY_DEPTH, cwd: Path | None = None
) -> list[str] | None:
    """
    Build git arguments covering the last `depth` commits.

    Falls back as the history allows: `HEAD~<depth>..HEAD` when that many
    commits exist, otherwise the root commit onwards, otherwise the single
    commit. Returns None only when there is no commit at all. A hard-coded
    `HEAD~10` failed on any younger repository, and the failure was reported as
    "no changes detected".
    """
    root = cwd or PROJECT_ROOT
    count = run_git_command(["rev-list", "--count", "HEAD"], cwd=root)
    if count is None or not count.strip().isdigit():
        return None
    total = int(count.strip())
    if total == 0:
        return None
    if total > depth:
        return [f"HEAD~{depth}..HEAD"]
    if total > 1:
        return [f"HEAD~{total - 1}..HEAD"]
    # A single commit has no parent to diff against; use git's empty-tree hash.
    return ["--root", "HEAD"]


def get_file_changes(since: str | None = None) -> dict[str, list[str]]:
    """Get file changes (created, modified, deleted) since the specified date."""
    changes: dict[str, list[str]] = {"created": [], "modified": [], "deleted": []}

    if since:
        args = ["log", "--since", since, "--name-status", "--pretty=format:"]
    else:
        rev_range = resolve_commit_range()
        if rev_range is None:
            return changes
        args = ["log", "--name-status", "--pretty=format:", *rev_range]

    output = run_git_command(args)
    if not output:
        return changes

    seen: set[str] = set()
    for line in output.split("\n"):
        line = line.strip()
        if not line or "\t" not in line:
            continue

        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue

        status, filepath = parts[0], parts[1]
        if filepath in seen:
            continue
        seen.add(filepath)

        if status.startswith("A"):
            changes["created"].append(filepath)
        elif status.startswith("M"):
            changes["modified"].append(filepath)
        elif status.startswith("D"):
            changes["deleted"].append(filepath)

    return changes


def get_file_stats(since: str | None = None) -> dict[str, tuple[int, int]]:
    """Get line additions/deletions per file."""
    if since:
        args = ["log", "--since", since, "--numstat", "--pretty=format:"]
    else:
        args = ["diff", "--numstat", "HEAD~10", "HEAD"]

    output = run_git_command(args)
    if not output:
        return {}

    stats: dict[str, tuple[int, int]] = {}
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) != 3:
            continue

        added, deleted, filepath = parts
        try:
            add_count = int(added) if added != "-" else 0
            del_count = int(deleted) if deleted != "-" else 0
            if filepath in stats:
                prev = stats[filepath]
                stats[filepath] = (prev[0] + add_count, prev[1] + del_count)
            else:
                stats[filepath] = (add_count, del_count)
        except ValueError:
            continue

    return stats


def local_date(timestamp: str) -> str:
    """Return the local calendar date (YYYY-MM-DD) of an ISO timestamp."""
    if not timestamp:
        return "unknown"
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return timestamp[:10]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone().date().isoformat()


def summarize_entries(entries: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """
    Group entries by local date, then by tool.

    Every tool is kept. The previous version pre-seeded only "antigravity" and
    gated on membership, so an entry from any other tool was silently discarded
    — the log recorded it and the checkpoint claimed it never happened.
    """
    by_date: dict[str, dict[str, list[dict]]] = {}

    for entry in entries:
        date = local_date(entry.get("timestamp", ""))
        tool = entry.get("tool") or "unknown"
        by_date.setdefault(date, {}).setdefault(tool, []).append(
            {
                "prompt": (entry.get("prompt") or "")[:200],
                "response_preview": (entry.get("response") or "")[:300],
                "success": bool(entry.get("success", False)),
            }
        )

    return by_date


# Display names for tools that have one; anything else is shown as logged.
TOOL_LABELS = {"antigravity": "agy", "claude": "Claude"}

MAX_ENTRIES_PER_TOOL_PER_DAY = 5
PROMPT_SUMMARY_LENGTH = 100


def generate_session_history(
    by_date: dict, header: str = SESSION_HISTORY_HEADER
) -> str:
    """
    Render the history section under the given heading.

    Labels are English per .claude/rules/language.md — the previous version
    hard-coded a Korean label into a file that also serves agy.
    """
    if not by_date:
        return ""

    lines = [header, ""]

    for date in sorted(by_date.keys(), reverse=True):
        lines.append(f"### {date}")
        lines.append("")
        for tool in sorted(by_date[date]):
            items = by_date[date][tool]
            if not items:
                continue
            lines.append(f"**{TOOL_LABELS.get(tool, tool)}:**")
            for item in items[:MAX_ENTRIES_PER_TOOL_PER_DAY]:
                summary = item["prompt"][:PROMPT_SUMMARY_LENGTH].replace("\n", " ")
                status = "OK" if item["success"] else "FAILED"
                lines.append(f"- [{status}] {summary}")
            remaining = len(items) - MAX_ENTRIES_PER_TOOL_PER_DAY
            if remaining > 0:
                lines.append(f"- ... and {remaining} more")
            lines.append("")

    return "\n".join(lines)


def update_context_file(
    file_path: Path, session_history: str, header: str = SESSION_HISTORY_HEADER
) -> bool:
    """Update one context file's history section, under that file's own heading."""
    if not file_path.exists():
        print(f"Warning: {file_path} does not exist, skipping")
        return False

    content = file_path.read_text(encoding="utf-8")
    updated = replace_session_history(content, session_history, header=header)
    if updated == content:
        return True
    write_text_atomic(file_path, content_new=updated, previous=content)
    return True


def write_text_atomic(
    path: Path, content_new: str, previous: str | None = None
) -> None:
    """
    Replace a file's contents without ever leaving it truncated.

    Writes a sibling temp file, flushes and fsyncs it, keeps the old contents as
    `<name>.bak`, then renames over the target. The previous implementation did
    read-then-write, so a crash mid-write truncated the file this whole framework
    depends on.
    """
    path = Path(path)
    if previous is None and path.exists():
        previous = path.read_text(encoding="utf-8")

    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)

    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=directory,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(content_new)
            handle.flush()
            os.fsync(handle.fileno())
        if previous is not None:
            backup = path.with_suffix(path.suffix + ".bak")
            backup.write_text(previous, encoding="utf-8")
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def history_section_pattern(header: str) -> re.Pattern[str]:
    """
    Match the history section that starts with `header`, up to the next heading.

    The section ends at the next H1 **or** H2. Ending only at `^## ` meant an
    intervening `# Heading` was treated as part of the section and destroyed on
    rewrite — real data loss, since the overwrite is by design.
    """
    return re.compile(
        rf"^{re.escape(header)}[ \t]*\n(?:(?!^#{{1,2}} ).*\n?)*",
        flags=re.MULTILINE,
    )


def replace_session_history(
    content: str, session_history: str, header: str = SESSION_HISTORY_HEADER
) -> str:
    """Replace (or append) the history section without touching anything else.

    Only a heading line that is exactly `header` starts the section, so inline
    mentions in prose are safe. The section ends at the next H1 or H2 heading, so
    everything after it survives.
    """
    new_section = session_history.rstrip() + "\n"
    match = history_section_pattern(header).search(content)
    if match:
        before = content[: match.start()].rstrip("\n")
        after = content[match.end() :].lstrip("\n")
        result = before + "\n\n" + new_section
        if after:
            result += "\n" + after
        return result
    return content.rstrip() + "\n\n" + new_section


def generate_full_checkpoint(since: str | None = None) -> Path | None:
    """Generate a comprehensive checkpoint file."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S")
    checkpoint_file = CHECKPOINTS_DIR / f"{timestamp}.md"

    # Ensure checkpoints directory exists
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

    # Gather data
    entries = parse_logs(since)
    commits = get_git_commits(since)
    file_changes = get_file_changes(since)
    file_stats = get_file_stats(since)

    # Count CLI consultations
    agy_count = sum(1 for e in entries if e.get("tool") == "antigravity")

    # Build checkpoint content
    lines: list[str] = []

    # Header
    lines.append(f"# Checkpoint: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    total_files = (
        len(file_changes["created"])
        + len(file_changes["modified"])
        + len(file_changes["deleted"])
    )
    lines.append(f"- **Commits**: {len(commits)}")
    lines.append(
        f"- **Files changed**: {total_files} "
        f"({len(file_changes['modified'])} modified, "
        f"{len(file_changes['created'])} created, "
        f"{len(file_changes['deleted'])} deleted)"
    )
    lines.append(f"- **agy researches**: {agy_count}")
    if since:
        lines.append(f"- **Since**: {since}")
    lines.append("")

    # Git History
    lines.append("## Git History")
    lines.append("")

    if commits:
        lines.append("### Commits")
        lines.append("")
        for commit in commits[:20]:  # Limit to 20 commits
            lines.append(f"- `{commit['hash']}` {commit['message']}")
        if len(commits) > 20:
            lines.append(f"- ... and {len(commits) - 20} more commits")
        lines.append("")

    # File Changes
    lines.append("### File Changes")
    lines.append("")

    if file_changes["created"]:
        lines.append("**Created:**")
        for f in file_changes["created"][:15]:
            stat = file_stats.get(f, (0, 0))
            lines.append(f"- `{f}` (+{stat[0]})")
        if len(file_changes["created"]) > 15:
            lines.append(f"- ... and {len(file_changes['created']) - 15} more files")
        lines.append("")

    if file_changes["modified"]:
        lines.append("**Modified:**")
        for f in file_changes["modified"][:15]:
            stat = file_stats.get(f, (0, 0))
            lines.append(f"- `{f}` (+{stat[0]}, -{stat[1]})")
        if len(file_changes["modified"]) > 15:
            lines.append(f"- ... and {len(file_changes['modified']) - 15} more files")
        lines.append("")

    if file_changes["deleted"]:
        lines.append("**Deleted:**")
        for f in file_changes["deleted"][:15]:
            lines.append(f"- `{f}`")
        if len(file_changes["deleted"]) > 15:
            lines.append(f"- ... and {len(file_changes['deleted']) - 15} more files")
        lines.append("")

    if not any(file_changes.values()):
        lines.append("No file changes detected.")
        lines.append("")

    # CLI Tool Consultations
    lines.append("## CLI Tool Consultations")
    lines.append("")

    agy_entries = [e for e in entries if e.get("tool") == "antigravity"]

    if agy_entries:
        lines.append(f"### Antigravity ({len(agy_entries)} researches)")
        lines.append("")
        for entry in agy_entries[:10]:
            status = "✓" if entry.get("success", False) else "✗"
            prompt = entry.get("prompt", "")[:80].replace("\n", " ")
            lines.append(f"- {status} {prompt}...")
        if len(agy_entries) > 10:
            lines.append(f"- ... and {len(agy_entries) - 10} more researches")
        lines.append("")

    if not entries:
        lines.append("No CLI tool consultations recorded.")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Generated by checkpointing skill at {timestamp}*")

    # Write checkpoint file
    checkpoint_file.write_text("\n".join(lines), encoding="utf-8")

    return checkpoint_file


def generate_skill_analysis_prompt(checkpoint_content: str) -> str:
    """Generate a prompt for AI to analyze checkpoint and suggest skills."""
    return f"""Analyze the following checkpoint and identify reusable work patterns that could become skills.

A "skill" is a repeatable workflow pattern that can be triggered by specific phrases and executed consistently.

## Checkpoint Content

{checkpoint_content}

## Analysis Instructions

1. **Identify Patterns**: Look for regularities in:
   - Sequences of commits that form a logical workflow
   - File change patterns (e.g., test + implementation together)
   - CLI consultation patterns (design → implementation → review)
   - Multi-step operations that could be templated

2. **For each potential skill, provide**:
   - **Name**: Short, descriptive name (e.g., "tdd-feature", "research-implement")
   - **Description**: What this skill accomplishes
   - **Trigger phrases**: When should this skill be invoked (Korean + English)
   - **Workflow steps**: Ordered list of actions
   - **Files typically involved**: Patterns like `tests/**/*.py`, `src/**/*.py`
   - **Confidence**: How confident are you this is a reusable pattern (0.0-1.0)
   - **Evidence**: What in the checkpoint suggests this pattern

3. **Output format**:

```markdown
## Skill Suggestions

### Skill 1: {{name}}
**Confidence:** {{0.0-1.0}}
**Description:** {{description}}

**Trigger phrases:**
- "{{Korean phrase}}"
- "{{English phrase}}"

**Workflow:**
1. {{step 1}}
2. {{step 2}}
3. {{step 3}}

**Files involved:**
- `{{pattern 1}}`
- `{{pattern 2}}`

**Evidence:**
- {{evidence from checkpoint}}
```

4. **Quality criteria**:
   - Only suggest skills with confidence >= 0.6
   - Skip trivial patterns (single file edits, simple commits)
   - Focus on multi-step workflows that save time when repeated
   - Consider what would be valuable to automate in future sessions

Provide your analysis:"""


def save_skill_suggestions(checkpoint_file: Path, suggestions: str) -> Path:
    """Save skill suggestions to a file next to the checkpoint."""
    suggestions_file = checkpoint_file.with_suffix(".skills.md")
    suggestions_file.write_text(suggestions, encoding="utf-8")
    return suggestions_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Checkpoint session context",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python checkpoint.py                    # Update session history in agent configs
  python checkpoint.py --full             # Create full checkpoint file
  python checkpoint.py --full --since 2026-01-26  # Full checkpoint since date
  python checkpoint.py --full --analyze   # Full checkpoint + skill analysis prompt
        """,
    )
    parser.add_argument(
        "--since",
        type=since_argument,
        help="Only include data from this local date onwards (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Create full checkpoint file with git history and file changes",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Output skill analysis prompt (use with --full)",
    )
    args = parser.parse_args()

    if args.full:
        # Full checkpoint mode
        print("Creating full checkpoint...")
        checkpoint_file = generate_full_checkpoint(args.since)
        if checkpoint_file:
            print(f"\nCheckpoint created: {checkpoint_file}")
            print("\nCheckpoint includes:")
            print("  - Git commits and file changes")
            print("  - CLI tool consultations (agy)")
            print("  - Session summary")

            if args.analyze:
                # Generate skill analysis prompt
                checkpoint_content = checkpoint_file.read_text(encoding="utf-8")
                prompt = generate_skill_analysis_prompt(checkpoint_content)

                # Save prompt to file
                prompt_file = checkpoint_file.with_suffix(".analyze-prompt.md")
                prompt_file.write_text(prompt, encoding="utf-8")

                print(f"\n{'=' * 60}")
                print("SKILL ANALYSIS MODE")
                print(f"{'=' * 60}")
                print(f"\nAnalysis prompt saved to: {prompt_file}")
                print("\nNext step: Use a subagent to analyze and suggest skills:")
                print("  Read the prompt file and pass it to a subagent for analysis.")
                print(
                    "\nThe subagent will identify reusable patterns and suggest new skills."
                )
        else:
            print("Failed to create checkpoint.")
        return

    # Session history mode (default)
    entries = parse_logs(args.since)
    if not entries:
        print("No log entries found.")
        print(f"Log file: {LOG_FILE}")
        return

    print(f"Found {len(entries)} log entries")

    # Summarize
    by_date = summarize_entries(entries)

    # Update each context file under the heading that file actually uses.
    wrote_any = False
    for target in CONTEXT_FILES.values():
        file_path = target["path"]
        header = target["header"]
        assert isinstance(file_path, Path) and isinstance(header, str)
        session_history = generate_session_history(by_date, header=header)
        if not session_history:
            print("No session history to write")
            return
        if update_context_file(file_path, session_history, header=header):
            print(f"Updated: {file_path}")
            wrote_any = True
        else:
            print(f"Skipped: {file_path}")

    if not wrote_any:
        print("No context file was updated.")
        return

    print("\nSession history has been written to all context files.")
    print("All agents (Claude, agy) can now see the session history.")


if __name__ == "__main__":
    main()
