from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app import export, storage
from app.fusion.models import ReviewComment, ReviewReport
from app.main import app


def _report(*comments: ReviewComment) -> ReviewReport:
    summary: dict = {}
    for c in comments:
        summary[c.severity] = summary.get(c.severity, 0) + 1
    return ReviewReport(comments=list(comments), summary=summary, notes=[])


def _comment(path="src/a.py", line=2, severity="High", message="msg", **kw):
    return ReviewComment(
        path=path, line=line, severity=severity, category="security",
        message=message, source="semgrep", **kw,
    )


def _rows(text: str):
    return list(csv.DictReader(io.StringIO(text)))


class ExportFormatTests(unittest.TestCase):
    def test_formula_like_cells_are_neutralised(self) -> None:
        review = {
            "id": 1, "created_at": "t", "repo": "o/r", "pr_number": 1,
            "author": "=HYPERLINK(\"http://evil\")", "commit_sha": "abc",
            "summary": {}, "total": 1,
            "report": {"comments": [
                {"severity": "High", "message": "@SUM(1)", "path": "+cmd", "line": 1}
            ]},
        }
        reviews = _rows(export.reviews_to_csv([review]))
        findings = _rows(export.findings_to_csv([review]))
        self.assertTrue(reviews[0]["author"].startswith("'="))
        self.assertEqual(findings[0]["message"], "'@SUM(1)")
        self.assertEqual(findings[0]["path"], "'+cmd")

    def test_commas_quotes_and_newlines_round_trip(self) -> None:
        msg = 'has, comma "quote"\nand newline'
        review = {
            "id": 1, "created_at": "t", "repo": "o/r", "pr_number": 1,
            "author": "a", "commit_sha": "c", "summary": {}, "total": 1,
            "report": {"comments": [{"severity": "Low", "message": msg}]},
        }
        self.assertEqual(_rows(export.findings_to_csv([review]))[0]["message"], msg)

    def test_empty_export_still_has_header(self) -> None:
        self.assertEqual(_rows(export.reviews_to_csv([])), [])
        self.assertIn("review_id", export.reviews_to_csv([]))


class ExportEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_engine = storage._engine
        self._tmp = tempfile.TemporaryDirectory()
        storage._engine = create_engine(
            f"sqlite:///{Path(self._tmp.name) / 'r.db'}", future=True
        )
        storage.init_db()
        self.a = storage.save_report(
            _report(_comment(path="src/a.py", severity="High", rationale="because", cwe=["CWE-89"])),
            repo="o/one", pr_number=1, author="alice",
            run_metrics={"response_time_ms": 12.5, "security_findings": 1,
                         "ai_findings": None, "fused_findings": 1},
        )
        self.b = storage.save_report(
            _report(_comment(path="web/b.js", severity="Low")),
            repo="o/two", pr_number=2, author="bob",
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        storage._engine.dispose()
        storage._engine = self._old_engine
        self._tmp.cleanup()

    def test_reviews_csv_is_a_download_with_metrics(self) -> None:
        r = self.client.get("/reviews/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers["content-disposition"])
        self.assertTrue(r.headers["content-type"].startswith("text/csv"))
        rows = {int(x["review_id"]): x for x in _rows(r.text)}
        self.assertEqual(set(rows), {self.a, self.b})
        self.assertEqual(rows[self.a]["high"], "1")
        self.assertEqual(rows[self.a]["response_time_ms"], "12.5")
        self.assertEqual(rows[self.b]["response_time_ms"], "")  # legacy/CI-less row

    def test_filters_match_the_dashboard_semantics(self) -> None:
        def ids(**params):
            r = self.client.get("/reviews/export", params=params)
            self.assertEqual(r.status_code, 200)
            return {int(x["review_id"]) for x in _rows(r.text)}

        self.assertEqual(ids(author="alice"), {self.a})
        self.assertEqual(ids(repo="o/two"), {self.b})
        self.assertEqual(ids(severity="Low"), {self.b})
        self.assertEqual(ids(file="B.JS"), {self.b})
        self.assertEqual(ids(author="alice", repo="o/two"), set())

    def test_findings_scope_has_one_row_per_finding(self) -> None:
        r = self.client.get("/reviews/export", params={"scope": "findings"})
        rows = _rows(r.text)
        self.assertEqual(len(rows), 2)
        high = next(x for x in rows if x["severity"] == "High")
        self.assertEqual(high["cwe"], "CWE-89")
        self.assertEqual(high["rationale"], "because")

    def test_json_export_has_full_reports_and_metadata(self) -> None:
        r = self.client.get("/reviews/export", params={"format": "json", "author": "alice"})
        data = json.loads(r.text)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["filters"], {"author": "alice"})
        self.assertEqual(data["reviews"][0]["report"]["comments"][0]["severity"], "High")

    def test_limit_applies_after_filtering(self) -> None:
        r = self.client.get("/reviews/export", params={"limit": 1, "author": "alice"})
        self.assertEqual({int(x["review_id"]) for x in _rows(r.text)}, {self.a})

    def test_bad_inputs_are_rejected(self) -> None:
        self.assertEqual(self.client.get("/reviews/export", params={"severity": "Nope"}).status_code, 400)
        self.assertEqual(self.client.get("/reviews/export", params={"format": "xml"}).status_code, 422)

    def test_single_review_export(self) -> None:
        csv_r = self.client.get(f"/reviews/{self.a}/export")
        self.assertEqual(len(_rows(csv_r.text)), 1)
        json_r = self.client.get(f"/reviews/{self.a}/export", params={"format": "json"})
        self.assertEqual(json.loads(json_r.text)["reviews"][0]["id"], self.a)
        self.assertEqual(self.client.get("/reviews/9999/export").status_code, 404)

    def test_export_route_is_not_shadowed_by_review_id_route(self) -> None:
        self.assertEqual(self.client.get("/reviews/export").status_code, 200)
        self.assertEqual(self.client.get(f"/reviews/{self.a}").status_code, 200)


if __name__ == "__main__":
    unittest.main()
