"""Structured security findings and severity handling for Module 3.

Semgrep reports issues in its own vocabulary (ERROR / WARNING / INFO). The rest
of the review pipeline speaks a single, ranked severity ladder shared with the
idea doc:

    Critical > High > Medium > Low > Informational

This file defines the clean `SecurityFinding` object the pipeline passes around,
and the small function that translates Semgrep's severity into our ladder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# The one severity ladder used everywhere downstream, highest first. The fusion
# engine (Module 4) ranks all findings — security and style — against this list.
SEVERITY_ORDER = ["Critical", "High", "Medium", "Low", "Informational"]

# Semgrep's three severities mapped onto our ladder.
_SEMGREP_SEVERITY = {
    "ERROR": "High",
    "WARNING": "Medium",
    "INFO": "Low",
}


@dataclass
class SecurityFinding:
    """One security issue found in a changed file, ready for Module 4."""

    rule_id: str          # which Semgrep rule fired (e.g. "...sql-injection")
    message: str          # human-readable explanation of the issue
    severity: str         # one of SEVERITY_ORDER
    path: str             # file the issue is in
    start_line: int       # first line of the issue (in the new file)
    end_line: int
    cwe: List[str] = field(default_factory=list)    # e.g. ["CWE-89: SQL Injection"]
    owasp: List[str] = field(default_factory=list)  # e.g. ["A03:2021 - Injection"]
    snippet: str = ""     # the offending source line(s), for context

    def severity_rank(self) -> int:
        """Position on the ladder (0 = most severe) — used for sorting."""
        if self.severity in SEVERITY_ORDER:
            return SEVERITY_ORDER.index(self.severity)
        return len(SEVERITY_ORDER)  # unknown severities sort last


def normalize_severity(semgrep_severity: Optional[str], metadata: Optional[dict] = None) -> str:
    """Translate a Semgrep severity into the project's ladder.

    Rules, in order:
    1. If a rule's metadata already states a ladder severity, trust it.
    2. Otherwise map ERROR->High, WARNING->Medium, INFO->Low.
    3. Promote a High-severity issue to Critical when Semgrep marks its impact
       as HIGH — so genuinely dangerous issues (injection, hard-coded secrets)
       outrank ordinary warnings when everything is ranked later.
    """
    metadata = metadata or {}

    explicit = str(metadata.get("severity", "")).capitalize()
    if explicit in SEVERITY_ORDER:
        return explicit

    mapped = _SEMGREP_SEVERITY.get(str(semgrep_severity).upper(), "Low")
    if mapped == "High" and str(metadata.get("impact", "")).upper() == "HIGH":
        return "Critical"
    return mapped
