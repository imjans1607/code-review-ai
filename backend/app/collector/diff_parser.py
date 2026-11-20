"""Parse a unified diff into structured, per-file hunks.

A "unified diff" is the standard text format that describes a code change:

    diff --git a/app.py b/app.py
    --- a/app.py
    +++ b/app.py
    @@ -10,6 +10,7 @@ def login(user):
     context line (unchanged)
    -old line that was removed
    +new line that was added
     another context line

Lines beginning with '+' were added, '-' were removed, and ' ' (space) are
unchanged "context". The '@@ ... @@' header says which line numbers the hunk
touches. This module turns that raw text into Python objects so the rest of the
pipeline never has to parse text again.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# Matches a hunk header like: @@ -10,6 +10,7 @@ optional section heading
# Groups: new-side start line number (the '+' side), which is what we report.
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class DiffLine:
    """One line inside a hunk, with its edit tag and new-file line number."""

    tag: str          # "add", "del", or "keep"
    text: str         # the line content, without the leading +/-/space marker
    new_lineno: Optional[int]  # line number in the new file (None for deletions)


@dataclass
class FileDiff:
    """All changes to a single file."""

    old_path: str
    new_path: str
    hunks: List[List[DiffLine]] = field(default_factory=list)

    @property
    def path(self) -> str:
        """The current (new) path of the file."""
        return self.new_path

    @property
    def patch_text(self) -> str:
        """Reconstruct the +/-/space patch body (what Module 2's encoder reads)."""
        marker = {"add": "+", "del": "-", "keep": " "}
        out: List[str] = []
        for hunk in self.hunks:
            for ln in hunk:
                out.append(f"{marker[ln.tag]}{ln.text}")
        return "\n".join(out)

    @property
    def added_lines(self) -> List[DiffLine]:
        return [ln for hunk in self.hunks for ln in hunk if ln.tag == "add"]

    @property
    def removed_lines(self) -> List[DiffLine]:
        return [ln for hunk in self.hunks for ln in hunk if ln.tag == "del"]


def _strip_ab_prefix(path: str) -> str:
    """Remove git's 'a/' or 'b/' prefix from a diff path."""
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def parse_unified_diff(diff_text: str) -> List[FileDiff]:
    """Turn raw unified-diff text into a list of FileDiff objects.

    How it works: we walk the diff line by line, tracking which file we are in
    (from the '+++'/'---' headers) and which hunk we are in (from '@@' headers).
    A running counter assigns the new-file line number to each added/kept line.
    """
    files: List[FileDiff] = []
    current: Optional[FileDiff] = None
    current_hunk: Optional[List[DiffLine]] = None
    new_lineno = 0

    for raw in diff_text.splitlines():
        # A new file section begins. Start a fresh FileDiff.
        if raw.startswith("diff --git"):
            parts = raw.split()
            # "diff --git a/x b/y" -> old=a/x new=b/y (fallbacks handled below)
            old = _strip_ab_prefix(parts[2]) if len(parts) >= 4 else ""
            new = _strip_ab_prefix(parts[3]) if len(parts) >= 4 else ""
            current = FileDiff(old_path=old, new_path=new)
            files.append(current)
            current_hunk = None
            continue

        # Explicit path headers refine the file names (handles renames, and
        # diffs produced without the 'diff --git' line).
        if raw.startswith("--- "):
            path = _strip_ab_prefix(raw[4:].strip())
            if current is None:
                current = FileDiff(old_path=path, new_path=path)
                files.append(current)
            if path != "/dev/null":
                current.old_path = path
            continue
        if raw.startswith("+++ "):
            path = _strip_ab_prefix(raw[4:].strip())
            if current is None:
                current = FileDiff(old_path=path, new_path=path)
                files.append(current)
            if path != "/dev/null":
                current.new_path = path
            continue

        # A hunk header resets the new-file line counter to the hunk's start.
        header = _HUNK_HEADER.match(raw)
        if header:
            new_lineno = int(header.group(1))
            current_hunk = []
            if current is not None:
                current.hunks.append(current_hunk)
            continue

        # Body lines only count once we are inside a hunk.
        if current_hunk is None:
            continue

        if raw.startswith("+"):
            current_hunk.append(DiffLine("add", raw[1:], new_lineno))
            new_lineno += 1
        elif raw.startswith("-"):
            current_hunk.append(DiffLine("del", raw[1:], None))
        elif raw.startswith(" "):
            current_hunk.append(DiffLine("keep", raw[1:], new_lineno))
            new_lineno += 1
        # Any other line (e.g. "\ No newline at end of file", index lines) is ignored.

    return files
