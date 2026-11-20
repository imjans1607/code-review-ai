"""Report export (Module 6): turn stored reviews into downloadable CSV / JSON.

Pure functions over the dicts that `storage` returns, so they are easy to test
and have no web or database dependencies.

Review text comes from code under review and from the AI model, i.e. it is
untrusted. A CSV cell that starts with `=`, `+`, `-` or `@` can be run as a
formula when opened in Excel/Sheets, so such cells are neutralised (see
`_safe_cell`).
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from .security.findings import SEVERITY_ORDER

REVIEW_COLUMNS = [
    "review_id", "created_at", "repo", "pr_number", "author", "commit_sha",
    "total", *[s.lower() for s in SEVERITY_ORDER],
    "response_time_ms", "ai_findings", "security_findings", "fused_findings",
]

FINDING_COLUMNS = [
    "review_id", "created_at", "repo", "pr_number", "author", "commit_sha",
    "severity", "category", "source", "path", "line", "rule_id", "cwe",
    "message", "rationale",
]

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value: Any) -> Any:
    """Neutralise spreadsheet-formula injection in text cells."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _write_csv(columns: List[str], rows: Iterable[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=columns, extrasaction="ignore", lineterminator="\r\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {k: _safe_cell("" if row.get(k) is None else row.get(k)) for k in columns}
        )
    return buf.getvalue()


def reviews_to_csv(reviews: List[dict]) -> str:
    """One row per review (the dashboard table, plus per-run metrics)."""
    rows = []
    for r in reviews:
        row = {
            "review_id": r["id"],
            "created_at": r["created_at"],
            "repo": r["repo"],
            "pr_number": r["pr_number"],
            "author": r["author"],
            "commit_sha": r["commit_sha"],
            "total": r["total"],
            "response_time_ms": r.get("response_time_ms"),
            "ai_findings": r.get("ai_findings"),
            "security_findings": r.get("security_findings"),
            "fused_findings": r.get("fused_findings"),
        }
        for sev in SEVERITY_ORDER:
            row[sev.lower()] = r["summary"].get(sev, 0)
        rows.append(row)
    return _write_csv(REVIEW_COLUMNS, rows)


def findings_to_csv(reviews: List[dict]) -> str:
    """One row per finding; `reviews` must include each review's `report`."""
    rows = []
    for r in reviews:
        for c in r.get("report", {}).get("comments", []):
            rows.append(
                {
                    "review_id": r["id"],
                    "created_at": r["created_at"],
                    "repo": r["repo"],
                    "pr_number": r["pr_number"],
                    "author": r["author"],
                    "commit_sha": r["commit_sha"],
                    "severity": c.get("severity", ""),
                    "category": c.get("category", ""),
                    "source": c.get("source", ""),
                    "path": c.get("path", ""),
                    "line": c.get("line", ""),
                    "rule_id": c.get("rule_id", ""),
                    "cwe": "; ".join(c.get("cwe") or []),
                    "message": c.get("message", ""),
                    "rationale": c.get("rationale", ""),
                }
            )
    return _write_csv(FINDING_COLUMNS, rows)


def reviews_to_json(reviews: List[dict], filters: Dict[str, Any]) -> str:
    """Full reports (with run metrics) wrapped with export metadata."""
    return json.dumps(
        {
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "filters": {k: v for k, v in filters.items() if v},
            "count": len(reviews),
            "reviews": reviews,
        },
        indent=2,
    )
