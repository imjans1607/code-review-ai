from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app import storage
from app.fusion.models import ReviewComment, ReviewReport
from app.main import app
from app.trends import compute_author_trends

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def _row(i, author, total, day, high=0):
    return {
        "id": i, "author": author, "total": total,
        "created_at": f"2026-11-{day:02d}T10:00:00+00:00",
        "summary": {"High": high},
    }


def _author(result, name):
    return next(a for a in result["authors"] if a["author"] == name)


class ComputeTrendTests(unittest.TestCase):
    def test_improving_when_later_reviews_have_fewer_findings(self) -> None:
        rows = [_row(i, "ann", t, 10 + i) for i, t in enumerate([10, 8, 4, 2], 1)]
        a = _author(compute_author_trends(rows, now=NOW), "ann")
        self.assertEqual(a["direction"], "improving")
        self.assertEqual(a["change_pct"], -66.7)  # avg 9 -> avg 3
        self.assertEqual(a["reviews"], 4)
        self.assertEqual(a["total_findings"], 24)

    def test_worsening_and_steady(self) -> None:
        up = [_row(i, "bo", t, 10 + i) for i, t in enumerate([2, 2, 6, 6], 1)]
        flat = [_row(10 + i, "cy", t, 10 + i) for i, t in enumerate([5, 5, 5, 5], 1)]
        res = compute_author_trends(up + flat, now=NOW)
        self.assertEqual(_author(res, "bo")["direction"], "worsening")
        self.assertEqual(_author(res, "bo")["change_pct"], 200.0)
        self.assertEqual(_author(res, "cy")["direction"], "steady")

    def test_zero_baseline_does_not_divide_by_zero(self) -> None:
        up = [_row(i, "di", t, 10 + i) for i, t in enumerate([0, 0, 3, 3], 1)]
        zero = [_row(10 + i, "ed", 0, 10 + i) for i in range(1, 5)]
        res = compute_author_trends(up + zero, now=NOW)
        self.assertEqual(_author(res, "di")["direction"], "worsening")
        self.assertIsNone(_author(res, "di")["change_pct"])
        self.assertEqual(_author(res, "ed")["direction"], "steady")

    def test_insufficient_data_below_min_reviews(self) -> None:
        rows = [_row(i, "fay", t, 10 + i) for i, t in enumerate([9, 1, 1], 1)]
        a = _author(compute_author_trends(rows, now=NOW), "fay")
        self.assertEqual(a["direction"], "insufficient_data")
        self.assertIsNone(a["change_pct"])

    def test_odd_count_drops_the_middle_review(self) -> None:
        rows = [_row(i, "gus", t, 10 + i) for i, t in enumerate([10, 10, 99, 5, 5], 1)]
        a = _author(compute_author_trends(rows, now=NOW), "gus")
        self.assertEqual(a["change_pct"], -50.0)  # 10 -> 5, ignoring the 99

    def test_blank_authors_and_old_reviews_are_excluded(self) -> None:
        rows = [
            _row(1, "", 5, 12),
            _row(2, "hal", 5, 12),
            {"id": 3, "author": "hal", "total": 99, "summary": {},
             "created_at": "2026-09-01T10:00:00+00:00"},
        ]
        res = compute_author_trends(rows, days=30, now=NOW)
        self.assertEqual([a["author"] for a in res["authors"]], ["hal"])
        self.assertEqual(_author(res, "hal")["reviews"], 1)

    def test_series_buckets_by_day_and_averages(self) -> None:
        rows = [_row(1, "ivy", 2, 12), _row(2, "ivy", 6, 12), _row(3, "ivy", 3, 13)]
        s = _author(compute_author_trends(rows, now=NOW), "ivy")["series"]
        self.assertEqual(
            s,
            [
                {"date": "2026-11-12", "reviews": 2, "avg_findings": 4.0},
                {"date": "2026-11-13", "reviews": 1, "avg_findings": 3.0},
            ],
        )

    def test_critical_high_average_and_author_ordering(self) -> None:
        rows = [_row(1, "zed", 4, 12, high=2), _row(2, "zed", 4, 13, high=0),
                _row(3, "amy", 1, 12), _row(4, "amy", 1, 13), _row(5, "amy", 1, 14)]
        res = compute_author_trends(rows, now=NOW)
        self.assertEqual([a["author"] for a in res["authors"]], ["amy", "zed"])
        self.assertEqual(_author(res, "zed")["avg_critical_high"], 1.0)

    def test_max_authors_caps_the_list(self) -> None:
        rows = [_row(i, f"u{i}", 1, 12) for i in range(1, 12)]
        self.assertEqual(len(compute_author_trends(rows, now=NOW, max_authors=3)["authors"]), 3)


class AuthorTrendEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_engine = storage._engine
        self._tmp = tempfile.TemporaryDirectory()
        storage._engine = create_engine(
            f"sqlite:///{Path(self._tmp.name) / 't.db'}", future=True
        )
        storage.init_db()

    def tearDown(self) -> None:
        storage._engine.dispose()
        storage._engine = self._old_engine
        self._tmp.cleanup()

    def test_endpoint_returns_trend_for_stored_reviews(self) -> None:
        for n in (6, 5, 2, 1):
            comments = [
                ReviewComment(path="a.py", line=i + 1, severity="High", category="security",
                              message="m", source="semgrep")
                for i in range(n)
            ]
            storage.save_report(
                ReviewReport(comments=comments, summary={"High": n}, notes=[]),
                repo="o/r", pr_number=n, author="kim",
            )
        c = TestClient(app)
        data = c.get("/stats/authors").json()
        kim = data["authors"][0]
        self.assertEqual((kim["author"], kim["reviews"]), ("kim", 4))
        self.assertEqual(kim["direction"], "improving")
        self.assertEqual(c.get("/stats/authors", params={"days": 0}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
