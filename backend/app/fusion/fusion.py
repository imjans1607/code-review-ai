"""Module 4 — Review Fusion & Prioritization.

Takes the two independent review streams — security findings (Module 3) and AI
comments (Module 2) — and produces ONE clean review:

    1. Convert both into a common `ReviewComment`.
    2. De-duplicate: drop repeats, and let a security finding supersede a style
       comment sitting on the same line (the security issue is the more
       important thing to say about that line).
    3. Rank by severity (Critical first), then file, then line.
    4. Summarize counts per severity.

This module is pure Python and fully offline-testable — run it directly to see
it merge the sample security findings with a couple of AI comments.
"""

from __future__ import annotations

import sys
from typing import List, Sequence

from ..security.findings import SEVERITY_ORDER, SecurityFinding
from .models import AIComment, ReviewComment, ReviewReport

# AI style/logic comments are advisory, so they default low on the ladder —
# security findings carry their own (usually higher) severity.
DEFAULT_AI_SEVERITY = "Low"


def _rationale_from_finding(finding: SecurityFinding) -> str:
    """Build the 'why it matters' text for a security finding from its metadata."""
    bits = []
    if finding.cwe:
        bits.append(finding.cwe[0])
    if finding.owasp:
        bits.append(finding.owasp[0])
    tag = " · ".join(bits)
    return f"Flagged by rule '{finding.rule_id}'." + (f" ({tag})" if tag else "")


def _from_security(finding: SecurityFinding) -> ReviewComment:
    return ReviewComment(
        path=finding.path,
        line=finding.start_line,
        severity=finding.severity,
        category="security",
        message=finding.message,
        source="semgrep",
        rationale=_rationale_from_finding(finding),
        rule_id=finding.rule_id,
        cwe=finding.cwe,
    )


def _from_ai(comment: AIComment) -> ReviewComment:
    return ReviewComment(
        path=comment.path,
        line=comment.line,
        severity=DEFAULT_AI_SEVERITY,
        category=comment.category,
        message=comment.message,
        source="ai-model",
        rationale="Suggested by the AI reviewer to improve code quality/readability.",
    )


def _dedupe(comments: List[ReviewComment]) -> List[ReviewComment]:
    """Remove duplicates and let security supersede style on the same line.

    - A style/logic comment on a (file, line) that also has a security finding is
      dropped — the security issue takes that line.
    - Exact repeats (same file, line, and message) are collapsed to one.
    """
    security_lines = {
        (c.path, c.line) for c in comments if c.category == "security"
    }
    kept: List[ReviewComment] = []
    seen = set()
    for c in comments:
        if c.category != "security" and (c.path, c.line) in security_lines:
            continue
        key = (c.path, c.line, c.message.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        kept.append(c)
    return kept


def _short_rule(rule_id: str) -> str:
    return rule_id.split(".")[-1] if rule_id else "rule"


def _collapse_security(comments: List[ReviewComment], max_listed: int = 3) -> List[ReviewComment]:
    """One security comment per (file, line).

    Several overlapping Semgrep rules often fire on the same line for the same
    underlying issue (3 eval rules, 3 XSS rules...). GitHub shows each as a
    separate comment, so one bug reads as many. The most severe finding on the
    line is kept (ties: the first seen) and the others are named in its
    rationale, so no rule is silently lost.
    """
    groups: dict = {}
    order: List[tuple] = []
    for c in comments:
        if c.category != "security":
            continue
        key = (c.path, c.line)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(c)

    primary_of = {}
    for key in order:
        group = groups[key]
        best = min(group, key=lambda c: c.severity_rank())   # min() keeps the first on ties
        others = [c for c in group if c is not best]
        if others:
            names = []
            for c in others:
                n = _short_rule(c.rule_id)
                if n != _short_rule(best.rule_id) and n not in names:
                    names.append(n)
            extra = f" Also flagged by {len(others)} other rule(s) on this line"
            if names:
                shown = ", ".join(f"'{n}'" for n in names[:max_listed])
                more = len(names) - max_listed
                extra += f": {shown}" + (f" and {more} more" if more > 0 else "")
            best.rationale = (best.rationale + extra + ".").strip()
        primary_of[key] = best

    kept: List[ReviewComment] = []
    for c in comments:
        if c.category == "security":
            if primary_of[(c.path, c.line)] is not c:
                continue
        kept.append(c)
    return kept


def _summarize(comments: Sequence[ReviewComment]) -> dict:
    """Count comments per severity, in ladder order."""
    counts = {sev: 0 for sev in SEVERITY_ORDER}
    for c in comments:
        counts[c.severity] = counts.get(c.severity, 0) + 1
    # Drop zero rows to keep the summary compact.
    return {sev: n for sev, n in counts.items() if n}


def fuse(
    security_findings: Sequence[SecurityFinding],
    ai_comments: Sequence[AIComment],
    notes: Sequence[str] = (),
) -> ReviewReport:
    """Merge, de-duplicate, and rank the two review streams into one report."""
    comments = [_from_security(f) for f in security_findings]
    comments += [_from_ai(a) for a in ai_comments]

    comments = _dedupe(_collapse_security(comments))
    comments.sort(key=lambda c: (c.severity_rank(), c.path, c.line))

    return ReviewReport(
        comments=comments,
        summary=_summarize(comments),
        notes=list(notes),
    )


def _demo(semgrep_json_path: str) -> None:
    """Merge the sample security findings with a couple of AI comments."""
    from ..security import load_findings_from_file

    findings = load_findings_from_file(semgrep_json_path)
    # Stand-in AI comments (Module 2 would generate these from the diffs).
    ai = [
        AIComment(path="examples/vulnerable_samples/app.py", line=8,
                  message="Consider adding a docstring describing what get_user returns.",
                  category="style"),
        # This one sits on the SQL-injection line — fusion should drop it in favor
        # of the security finding.
        AIComment(path="examples/vulnerable_samples/app.py", line=11,
                  message="This line is a bit long; consider splitting it.",
                  category="style"),
    ]

    report = fuse(findings, ai)
    print(f"Fused review — {len(report.comments)} comment(s)")
    print(f"Severity summary: {report.summary}\n")
    for c in report.comments:
        print(f"[{c.severity:<13}] {c.category:<8} {c.path}:{c.line}")
        print(f"                {c.message}")
        print(f"                why: {c.rationale}\n")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "examples/semgrep_sample_output.json"
    _demo(target)
