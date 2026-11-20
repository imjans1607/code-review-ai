from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import storage
from app.fusion.models import ReviewComment, ReviewReport
from scripts import migrate_db


def _report(n: int = 1, message: str = "m") -> ReviewReport:
    comments = [
        ReviewComment(path=f"src/f{i}.py", line=i + 1, severity="High",
                      category="security", message=message, source="semgrep")
        for i in range(n)
    ]
    return ReviewReport(comments=comments, summary={"High": n}, notes=[])


class DatabaseUrlTests(unittest.TestCase):
    def test_provider_style_urls_map_to_psycopg3(self) -> None:
        n = storage.normalize_database_url
        self.assertEqual(n("postgres://u:p@h:5432/db"), "postgresql+psycopg://u:p@h:5432/db")
        self.assertEqual(n("postgresql://u:p@h/db"), "postgresql+psycopg://u:p@h/db")
        self.assertEqual(n("  postgresql://u@h/db \n"), "postgresql+psycopg://u@h/db")

    def test_explicit_drivers_and_sqlite_are_left_alone(self) -> None:
        n = storage.normalize_database_url
        for url in ("postgresql+psycopg://u@h/db", "postgresql+asyncpg://u@h/db",
                    "sqlite:///x.db", "sqlite://"):
            self.assertEqual(n(url), url)

    def test_default_is_the_local_sqlite_file(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            self.assertEqual(storage.database_url(), f"sqlite:///{storage.DB_PATH}")

    def test_blank_database_url_falls_back_to_sqlite(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "   "}):
            self.assertTrue(storage.database_url().startswith("sqlite:///"))

    def test_database_url_env_is_used_and_normalised(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://u:p@h/db"}):
            self.assertEqual(storage.database_url(), "postgresql+psycopg://u:p@h/db")

    def test_postgres_engines_probe_connections_sqlite_engines_do_not(self) -> None:
        pg = storage.make_engine("postgresql://u:p@localhost:1/db")  # lazy: no connect
        self.assertTrue(pg.pool._pre_ping)
        self.assertEqual(pg.dialect.name, "postgresql")
        lite = storage.make_engine("sqlite://")
        self.assertFalse(lite.pool._pre_ping)

    def test_backend_name_reports_dialect_without_credentials(self) -> None:
        old = storage._engine
        try:
            storage._engine = storage.make_engine("sqlite://")
            self.assertEqual(storage.backend_name(), "sqlite")
        finally:
            storage._engine = old


class _SwappedEngine(unittest.TestCase):
    """Point `storage` at a throwaway SQLite file for the test's duration."""

    def setUp(self) -> None:
        self._old = storage._engine
        self._tmp = tempfile.TemporaryDirectory()
        self.db_file = Path(self._tmp.name) / "t.db"
        storage._engine = create_engine(f"sqlite:///{self.db_file}", future=True)
        storage.init_db()

    def tearDown(self) -> None:
        storage._engine.dispose()
        storage._engine = self._old
        self._tmp.cleanup()


class FieldClippingTests(_SwappedEngine):
    def test_overlong_inputs_are_clipped_to_column_widths(self) -> None:
        rid = storage.save_report(
            _report(), repo="r" * 500, author="a" * 500, commit_sha="c" * 500
        )
        row = storage.get_review(rid)
        self.assertEqual(len(row["repo"]), 200)
        self.assertEqual(len(row["author"]), 120)
        self.assertEqual(len(row["commit_sha"]), 64)

    def test_none_fields_become_empty_strings(self) -> None:
        rid = storage.save_report(_report(), repo=None, author=None, commit_sha=None)
        self.assertEqual(storage.get_review(rid)["repo"], "")


class MigrationTests(_SwappedEngine):
    def _target(self, name: str = "target.db") -> str:
        return f"sqlite:///{Path(self._tmp.name) / name}"

    def test_copies_all_reviews_preserving_ids_and_content(self) -> None:
        a = storage.save_report(_report(2, "first"), repo="o/a", pr_number=1, author="x",
                                run_metrics={"response_time_ms": 5.5, "fused_findings": 2})
        b = storage.save_report(_report(1, "second"), repo="o/b", pr_number=2, author="y")
        n = migrate_db.migrate(str(self.db_file), self._target())
        self.assertEqual(n, 2)

        dst = storage.make_engine(self._target())
        old, storage._engine = storage._engine, dst
        try:
            self.assertEqual(
                [r["id"] for r in storage.query_reviews(with_reports=False)], [b, a]
            )
            copied = storage.get_review(a)
            self.assertEqual(copied["report"]["comments"][0]["message"], "first")
            self.assertEqual(copied["response_time_ms"], 5.5)
            # New rows continue after the copied ids.
            self.assertGreater(storage.save_report(_report()), b)
        finally:
            storage._engine = old
            dst.dispose()

    def test_refuses_a_non_empty_target_and_never_duplicates(self) -> None:
        storage.save_report(_report(), repo="o/a")
        target = self._target()
        self.assertEqual(migrate_db.migrate(str(self.db_file), target), 1)
        with self.assertRaises(ValueError):
            migrate_db.migrate(str(self.db_file), target)

    def test_refuses_to_copy_a_database_onto_itself(self) -> None:
        with self.assertRaises(ValueError):
            migrate_db.migrate(str(self.db_file), f"sqlite:///{self.db_file}")

    def test_cli_requires_a_target(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            with self.assertRaises(SystemExit):
                migrate_db.main(["--source", str(self.db_file)])


@unittest.skipUnless(
    os.environ.get("TEST_DATABASE_URL"),
    "set TEST_DATABASE_URL to a throwaway PostgreSQL database to run these",
)
class PostgresIntegrationTests(unittest.TestCase):
    """Runs the real storage / API paths against PostgreSQL.

    WARNING: drops and recreates the `reviews` table in TEST_DATABASE_URL.
    """

    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        from app.main import app

        self._old = storage._engine
        storage._engine = storage.make_engine(
            storage.normalize_database_url(os.environ["TEST_DATABASE_URL"])
        )
        storage.Base.metadata.drop_all(storage._engine)
        storage.init_db()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        storage.Base.metadata.drop_all(storage._engine)
        storage._engine.dispose()
        storage._engine = self._old

    def test_is_really_postgres(self) -> None:
        self.assertEqual(storage.backend_name(), "postgresql")
        self.assertEqual(self.client.get("/health").json()["database"], "postgresql")
        self.assertTrue(inspect(storage._engine).has_table("reviews"))

    def test_save_update_query_and_stats(self) -> None:
        rid = storage.save_report(
            _report(3), repo="o/r", pr_number=4, author="ann", commit_sha="abc",
            run_metrics={"response_time_ms": 12.5, "security_findings": 3,
                         "fused_findings": 3, "cold_start": True},
        )
        storage.update_run_metrics(
            rid, {"response_time_ms": 20.0, "security_findings": 3, "fused_findings": 3}
        )
        row = storage.get_review(rid)
        self.assertEqual(row["total"], 3)
        self.assertEqual(row["response_time_ms"], 20.0)
        self.assertEqual(row["report"]["comments"][0]["severity"], "High")

        self.assertEqual([r["id"] for r in storage.query_reviews(severity="High")], [rid])
        self.assertEqual(storage.query_reviews(author="nobody"), [])
        stats = storage.get_stats()
        self.assertEqual((stats["total_reviews"], stats["total_findings"]), (1, 3))
        self.assertEqual(stats["run_history"][0]["review_id"], rid)

    def test_api_endpoints_work_end_to_end(self) -> None:
        for n in (6, 5, 2, 1):
            storage.save_report(_report(n), repo="o/r", pr_number=n, author="kim")
        self.assertEqual(self.client.get("/reviews").json()["reviews"][0]["total"], 1)
        csv_text = self.client.get("/reviews/export", params={"scope": "findings"}).text
        self.assertEqual(len(csv_text.strip().splitlines()), 1 + 14)
        trend = self.client.get("/stats/authors").json()["authors"][0]
        self.assertEqual((trend["author"], trend["direction"]), ("kim", "improving"))

    def test_overlong_fields_are_clipped_not_rejected(self) -> None:
        rid = storage.save_report(_report(), repo="r" * 500, author="a" * 500)
        self.assertEqual(len(storage.get_review(rid)["repo"]), 200)

    def test_ids_are_sequential_and_review_endpoint_persists_metrics(self) -> None:
        diff = (Path(__file__).resolve().parents[1] / "examples" / "sample_change.diff").read_text()
        r = self.client.post("/review", json={"diff": diff, "run_ai": False,
                                              "run_security": False, "repo": "o/r"})
        self.assertEqual(r.status_code, 200)
        rid = r.json()["review_id"]
        self.assertGreaterEqual(storage.get_review(rid)["response_time_ms"], 0)

    def test_sqlite_to_postgres_migration_keeps_ids_and_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = f"sqlite:///{Path(tmp) / 's.db'}"
            src_engine = storage.make_engine(src)
            old, storage._engine = storage._engine, src_engine
            try:
                storage.init_db()
                ids = [storage.save_report(_report(i + 1), repo="o/r", pr_number=i)
                       for i in range(3)]
            finally:
                storage._engine = old
                src_engine.dispose()
            # Start the target clean (setUp already created an empty table).
            with storage._engine.begin() as conn:
                conn.execute(text("DELETE FROM reviews"))
            n = migrate_db.migrate(src, os.environ["TEST_DATABASE_URL"])
            self.assertEqual(n, 3)
            self.assertEqual(
                sorted(r["id"] for r in storage.query_reviews()), sorted(ids)
            )
            # The sequence was advanced: a new review must not collide.
            self.assertGreater(storage.save_report(_report()), max(ids))


if __name__ == "__main__":
    unittest.main()
