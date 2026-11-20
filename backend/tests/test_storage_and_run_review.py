from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import storage
from app.fusion.models import ReviewComment, ReviewReport
from scripts import run_review


class StorageInitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_engine = storage._engine
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmpdir.name) / "reviews.db"
        storage._engine = create_engine(f"sqlite:///{self._db_path}", future=True)

    def tearDown(self) -> None:
        storage._engine.dispose()
        storage._engine = self._old_engine
        self._tmpdir.cleanup()

    @staticmethod
    def _sample_report(message: str) -> ReviewReport:
        return ReviewReport(
            comments=[
                ReviewComment(
                    path="src/a.py",
                    line=2,
                    severity="High",
                    category="security",
                    message=message,
                    source="semgrep",
                )
            ],
            summary={"High": 1},
            notes=[],
        )

    def test_init_db_creates_reviews_table_for_fresh_sqlite(self) -> None:
        self.assertFalse(inspect(storage._engine).has_table("reviews"))
        storage.init_db()
        self.assertTrue(inspect(storage._engine).has_table("reviews"))

    def test_init_db_keeps_existing_records_unchanged(self) -> None:
        storage.init_db()
        first_id = storage.save_report(self._sample_report("first"), repo="owner/repo", pr_number=1)
        storage.init_db()
        second_id = storage.save_report(self._sample_report("second"), repo="owner/repo", pr_number=2)

        self.assertGreater(first_id, 0)
        self.assertGreater(second_id, first_id)
        stats = storage.get_stats(days=14)
        self.assertEqual(stats["total_reviews"], 2)


    def test_run_history_is_capped_to_most_recent_runs_in_order(self) -> None:
        storage.init_db()
        ids = [
            storage.save_report(self._sample_report(f"r{i}"), repo="o/r", pr_number=i)
            for i in range(1, 6)
        ]
        history = storage.get_stats(days=14, run_limit=3)["run_history"]
        self.assertEqual([h["review_id"] for h in history], ids[-3:])

    def test_run_history_includes_cold_start_and_defaults_for_legacy_rows(self) -> None:
        storage.init_db()
        legacy = storage.save_report(self._sample_report("old"), repo="o/r", pr_number=1)
        cold = storage.save_report(
            self._sample_report("new"), repo="o/r", pr_number=2,
            run_metrics={"response_time_ms": 900.5, "ai_findings": 1,
                         "security_findings": 1, "fused_findings": 1, "cold_start": True},
        )
        by_id = {h["review_id"]: h for h in storage.get_stats()["run_history"]}
        self.assertFalse(by_id[legacy]["cold_start"])
        self.assertIsNone(by_id[legacy]["response_time_ms"])
        self.assertTrue(by_id[cold]["cold_start"])
        self.assertEqual(by_id[cold]["response_time_ms"], 900.5)


class RunReviewOrderTests(unittest.TestCase):
    def test_run_review_initializes_db_before_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            diff_path = Path(tmp) / "change.diff"
            diff_path.write_text(
                "diff --git a/src/a.py b/src/a.py\n"
                "--- a/src/a.py\n"
                "+++ b/src/a.py\n"
                "@@ -1 +1,2 @@\n"
                " keep\n"
                "+added\n",
                encoding="utf-8",
            )

            order = []

            def _init_db() -> None:
                order.append("init")

            saved = {}
            updated = {}

            def _save_report(*args, **kwargs) -> int:
                order.append("save")
                saved.update(kwargs)
                return 1

            def _update_run_metrics(review_id, metrics) -> None:
                updated["id"] = review_id
                updated["metrics"] = dict(metrics)

            argv = [
                "run_review.py",
                "--diff",
                str(diff_path),
                "--repo",
                "owner/repo",
                "--pr",
                "1",
                "--commit",
                "abc123",
                "--dry-run",
            ]
            env = dict(os.environ)
            env.pop("AI_MODEL_PATH", None)
            env.pop("GITHUB_TOKEN", None)

            with patch.object(sys, "argv", argv):
                with patch.dict(os.environ, env, clear=True):
                    with patch.object(run_review.storage, "init_db", side_effect=_init_db):
                        with patch.object(run_review.storage, "save_report", side_effect=_save_report):
                            with patch.object(
                                run_review.storage, "update_run_metrics", side_effect=_update_run_metrics
                            ):
                                with patch.object(run_review, "post_review", return_value={"dry_run": True}):
                                    run_review.main()

            self.assertGreaterEqual(len(order), 2)
            self.assertEqual(order[0], "init")
            self.assertEqual(order[1], "save")

            # CI runs persist run metrics too (no Semgrep file and no model here).
            self.assertIn("run_metrics", saved)
            self.assertIsNone(saved["run_metrics"]["ai_findings"])
            self.assertIsNone(saved["run_metrics"]["security_findings"])
            self.assertFalse(saved["run_metrics"]["cold_start"])
            self.assertEqual(updated["id"], 1)
            self.assertGreaterEqual(updated["metrics"]["response_time_ms"], 0)


if __name__ == "__main__":
    unittest.main()
