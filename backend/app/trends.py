"""Per-author improvement trend (Module 6).

Answers "is each developer's code getting cleaner over time?" from stored
reviews. Pure functions over the review rows that `storage` returns, so there is
no web or database dependency.

Method
------
* The metric is **findings per review** (the fused total), per author.
* Reviews with no author are ignored: there is nobody to attribute them to.
* For each author the chronological reviews inside the window are split into an
  earlier half and a later half (the middle review is dropped when the count is
  odd). The trend is the relative change in the average of the two halves.
* A change of 10% or less in either direction counts as "steady", and authors
  with fewer than `min_reviews` reviews report "insufficient_data" rather than a
  trend that isn't meaningful.

This is a simple, explainable comparison, not a statistical test: with few
reviews per author a single noisy PR can swing it.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

STEADY_THRESHOLD_PCT = 10.0
DEFAULT_MIN_REVIEWS = 4


def _critical_high(review: dict) -> int:
    s = review.get("summary", {})
    return int(s.get("Critical", 0)) + int(s.get("High", 0))


def _avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _direction(
    totals: List[int], min_reviews: int
) -> "tuple[str, Optional[float]]":
    """(direction, change_pct) from chronological per-review totals."""
    n = len(totals)
    if n < max(min_reviews, 2):
        return "insufficient_data", None
    half = n // 2
    earlier, later = _avg(totals[:half]), _avg(totals[n - half:])
    if earlier == 0:
        if later == 0:
            return "steady", 0.0
        return "worsening", None  # no baseline to express a percentage against
    change = (later - earlier) / earlier * 100.0
    if change <= -STEADY_THRESHOLD_PCT:
        return "improving", round(change, 1)
    if change >= STEADY_THRESHOLD_PCT:
        return "worsening", round(change, 1)
    return "steady", round(change, 1)


def compute_author_trends(
    reviews: List[dict],
    days: int = 30,
    min_reviews: int = DEFAULT_MIN_REVIEWS,
    max_authors: int = 8,
    now: Optional[datetime] = None,
) -> dict:
    """Per-author series and summary for reviews created in the last `days`.

    Returns `{"days", "min_reviews", "authors": [...]}`, authors ordered by
    review count (then name). Each author has: `author`, `reviews`,
    `total_findings`, `avg_findings`, `avg_critical_high`, `direction`
    (improving | worsening | steady | insufficient_data), `change_pct`, and
    `series` — one point per day that had reviews, with `date`, `reviews` and
    `avg_findings`.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = (now.date() - timedelta(days=days - 1)).isoformat()

    by_author: Dict[str, List[dict]] = defaultdict(list)
    for r in reviews:
        author = (r.get("author") or "").strip()
        if not author or r["created_at"][:10] < cutoff:
            continue
        by_author[author].append(r)

    authors = []
    for author, rows in by_author.items():
        rows.sort(key=lambda r: (r["created_at"], r["id"]))
        totals = [int(r["total"]) for r in rows]
        per_day: Dict[str, List[int]] = defaultdict(list)
        for r in rows:
            per_day[r["created_at"][:10]].append(int(r["total"]))
        direction, change = _direction(totals, min_reviews)
        authors.append(
            {
                "author": author,
                "reviews": len(rows),
                "total_findings": sum(totals),
                "avg_findings": round(_avg(totals), 2),
                "avg_critical_high": round(_avg([_critical_high(r) for r in rows]), 2),
                "direction": direction,
                "change_pct": change,
                "series": [
                    {
                        "date": day,
                        "reviews": len(vals),
                        "avg_findings": round(_avg(vals), 2),
                    }
                    for day, vals in sorted(per_day.items())
                ],
            }
        )

    authors.sort(key=lambda a: (-a["reviews"], a["author"]))
    return {"days": days, "min_reviews": min_reviews, "authors": authors[:max_authors]}
