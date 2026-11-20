"""The unified data shapes for Module 4 (fusion).

Module 2 produces AI style/logic comments; Module 3 produces security findings.
They start as different objects, but the final review is one ranked list. This
file defines the common `ReviewComment` that both are converted into, and the
`ReviewReport` that wraps the merged result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List

from ..security.findings import SEVERITY_ORDER


@dataclass
class AIComment:
    """An AI review comment (Module 2 output) tied to a place in the code."""

    path: str
    line: int
    message: str
    category: str = "style"   # "style" or "logic"


@dataclass
class ReviewComment:
    """One unified review comment — what the developer finally sees.

    Both security findings and AI comments become this, so they can be
    de-duplicated and ranked together.
    """

    path: str
    line: int
    severity: str           # shared ladder (Critical .. Informational)
    category: str           # "security" | "style" | "logic"
    message: str
    source: str             # "semgrep" | "ai-model"
    rationale: str = ""     # the "why" behind the comment (gap #3: explainability)
    rule_id: str = ""       # security only: which rule fired
    cwe: List[str] = field(default_factory=list)

    def severity_rank(self) -> int:
        """Position on the ladder (0 = most severe)."""
        if self.severity in SEVERITY_ORDER:
            return SEVERITY_ORDER.index(self.severity)
        return len(SEVERITY_ORDER)


@dataclass
class ReviewReport:
    """The merged, ranked result the API returns and the dashboard stores."""

    comments: List[ReviewComment] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)  # counts per severity
    notes: List[str] = field(default_factory=list)         # e.g. "AI step skipped"

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "total": len(self.comments),
            "comments": [asdict(c) for c in self.comments],
            "notes": self.notes,
        }
