#!/usr/bin/env python3
"""
Checkpoint script: write the agy consultation history from the CLI log into the
`## Session History` section of CLAUDE.md and .agents/rules/AGENTS.md.

Usage:
    python checkpoint.py [--since YYYY-MM-DD]

The "full checkpoint" and "skill analysis" modes were removed on 2026-10-03
(never run; skill mining contradicts "new skills only from field reports").
They remain in tag v1.1.0.
"""

import argparse
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
LOG_FILE = PROJECT_ROOT / ".claude" / "logs" / "cli-tools.jsonl"

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


FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING_LINE = re.compile(r"^#{1,2} ")


def _fence_closes(line: str, marker: str) -> bool:
    """True when `line` closes a fence opened with `marker`."""
    match = FENCE_LINE.match(line)
    if match is None:
        return False
    closer = match.group(1)
    return closer[0] == marker[0] and len(closer) >= len(marker)


def find_history_section(content: str, header: str) -> tuple[int, int] | None:
    """
    Locate the history section as (start, end) character offsets, or None.

    Scanned line by line rather than matched with a regex, because fenced code
    blocks have to be skipped in BOTH directions:

    - a `## Session History` line inside a ```markdown fence is documentation,
      not the section. The checkpointing skill shows the section it writes in
      exactly such a fence, and matching it there replaced everything up to the
      next heading — including the fence's closing backticks, leaving the rest of
      the document inside an unterminated code block.
    - a `## ...` line inside a fence must not END the section either, or the tail
      of a fenced example survives as if it were prose.

    A header on the last line with no trailing newline also counts; requiring the
    newline meant the section was not found and a second one was appended below
    it on every run.
    """
    offset = 0
    start: int | None = None
    fence: str | None = None

    for line in content.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        if fence is not None:
            if _fence_closes(bare, fence):
                fence = None
            offset += len(line)
            continue

        opening = FENCE_LINE.match(bare)
        if opening is not None:
            fence = opening.group(1)
            offset += len(line)
            continue

        if start is None:
            if bare.rstrip(" \t") == header:
                start = offset
        elif HEADING_LINE.match(bare):
            return (start, offset)

        offset += len(line)

    if start is None:
        return None
    return (start, len(content))


def replace_session_history(
    content: str, session_history: str, header: str = SESSION_HISTORY_HEADER
) -> str:
    """Replace (or append) the history section without touching anything else.

    Only a heading line that is exactly `header` starts the section, so inline
    mentions in prose are safe. The section ends at the next H1 or H2 heading, so
    everything after it survives.
    """
    new_section = session_history.rstrip() + "\n"
    span = find_history_section(content, header)
    if span:
        start, end = span
        before = content[:start].rstrip("\n")
        after = content[end:].lstrip("\n")
        result = before + "\n\n" + new_section
        if after:
            result += "\n" + after
        return result
    return content.rstrip() + "\n\n" + new_section


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the session history")
    parser.add_argument(
        "--since",
        type=since_argument,
        help="Only include data from this local date onwards (YYYY-MM-DD)",
    )
    args = parser.parse_args()

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
