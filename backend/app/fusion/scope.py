"""Keep security findings to what the pull request actually changed.

The CI workflow runs Semgrep over the whole checkout, so its output also holds
every older issue in the repository. A review that comments on code the author
never touched is noise, and it is the first thing a new user notices. This
module keeps only the findings that overlap a line **added** by the PR.

If the diff is empty or unreadable the scope is unknown, so nothing is dropped
(fail open) and the caller is told via the `scoped` flag.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Sequence, Set

from ..collector.diff_parser import parse_unified_diff
from ..security.findings import SecurityFinding


@dataclass
class ScopeResult:
    findings: List[SecurityFinding]
    dropped: int          # findings outside the PR's added lines
    scoped: bool          # False when no usable diff was available


def normalize_path(path: str) -> str:
    clean = (path or "").replace("\\", "/").strip()
    while clean.startswith("./"):
        clean = clean[2:]
    return clean


def added_lines_by_path(diff_text: str) -> Dict[str, Set[int]]:
    """{file path: set of line numbers added in the new version of the file}."""
    out: Dict[str, Set[int]] = {}
    for fd in parse_unified_diff(diff_text or ""):
        path = normalize_path(fd.path)
        if path:
            out.setdefault(path, set()).update(
                ln.new_lineno for ln in fd.added_lines if ln.new_lineno is not None
            )
    return out


def restrict_to_added_lines(findings: Sequence[SecurityFinding], diff_text: str) -> ScopeResult:
    """Drop findings that do not overlap a line the PR added.

    A finding that spans several lines is kept if any of them was added; its
    `start_line` is moved to the first added line in the span so the inline
    comment can be anchored inside the diff.
    """
    if not (diff_text or "").strip():
        return ScopeResult(list(findings), 0, False)
    added = added_lines_by_path(diff_text)
    if not added:
        return ScopeResult(list(findings), 0, False)

    kept: List[SecurityFinding] = []
    for f in findings:
        lines = added.get(normalize_path(f.path))
        if not lines:
            continue
        end = max(f.end_line or f.start_line, f.start_line)
        hits = sorted(n for n in lines if f.start_line <= n <= end)
        if not hits:
            continue
        kept.append(f if f.start_line in lines else replace(f, start_line=hits[0]))
    return ScopeResult(kept, len(findings) - len(kept), True)
