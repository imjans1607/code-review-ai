"""The Module 1 orchestrator: diff in, structured changed-files out.

This is the public face of Module 1. It ties together the diff parser and the
language detector and produces a clean list of `ChangedFile` objects — the
exact "modified source code files" the idea doc names as Module 1's output.

Run it directly to see it work on the sample change:

    python -m app.collector.collector examples/sample_change.diff
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from typing import List

from .diff_parser import FileDiff, parse_unified_diff
from .language_detect import detect_language


@dataclass
class DiffHunk:
    """A single reviewable hunk: its patch text plus the line range it touches."""

    patch: str
    start_line: int
    added_count: int
    removed_count: int


@dataclass
class ChangedFile:
    """One changed file, ready for Module 2 / Module 3 to review."""

    path: str
    language: str
    patch: str                       # the full +/-/space patch body for this file
    added_lines: int
    removed_lines: int
    hunks: List[DiffHunk] = field(default_factory=list)


def _to_changed_file(fd: FileDiff) -> ChangedFile:
    """Convert a parsed FileDiff into the pipeline's ChangedFile contract."""
    hunks: List[DiffHunk] = []
    for hunk in fd.hunks:
        start = next((ln.new_lineno for ln in hunk if ln.new_lineno is not None), 0)
        marker = {"add": "+", "del": "-", "keep": " "}
        patch = "\n".join(f"{marker[ln.tag]}{ln.text}" for ln in hunk)
        hunks.append(
            DiffHunk(
                patch=patch,
                start_line=start or 0,
                added_count=sum(1 for ln in hunk if ln.tag == "add"),
                removed_count=sum(1 for ln in hunk if ln.tag == "del"),
            )
        )
    return ChangedFile(
        path=fd.path,
        language=detect_language(fd.path),
        patch=fd.patch_text,
        added_lines=len(fd.added_lines),
        removed_lines=len(fd.removed_lines),
        hunks=hunks,
    )


def collect_from_diff_text(diff_text: str, supported_only: bool = True) -> List[ChangedFile]:
    """Collect changed files from raw unified-diff text.

    By default only Python/JavaScript files are returned (`supported_only`),
    because those are the languages the review pipeline handles.
    """
    changed = [_to_changed_file(fd) for fd in parse_unified_diff(diff_text)]
    if supported_only:
        changed = [c for c in changed if c.language != "other"]
    return changed


def collect_from_diff_file(path: str, supported_only: bool = True) -> List[ChangedFile]:
    """Same as `collect_from_diff_text`, but reads the diff from a file on disk."""
    with open(path, encoding="utf-8") as fh:
        return collect_from_diff_text(fh.read(), supported_only=supported_only)


def _demo(diff_path: str) -> None:
    """Print the collected files as pretty JSON — used for the CLI / teaching."""
    files = collect_from_diff_file(diff_path, supported_only=False)
    print(f"Collected {len(files)} changed file(s) from {diff_path}\n")
    for f in files:
        print(f"- {f.path}  [{f.language}]  +{f.added_lines}/-{f.removed_lines}, "
              f"{len(f.hunks)} hunk(s)")
    print("\nFull structured output:\n")
    print(json.dumps([asdict(f) for f in files], indent=2))


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "examples/sample_change.diff"
    _demo(target)
