#!/usr/bin/env python3
"""Copy saved reviews from one database to another (e.g. SQLite -> PostgreSQL).

Run this once when switching a deployment from the local SQLite file to
PostgreSQL, so the dashboard keeps its history. Review ids are preserved and, on
PostgreSQL, the id sequence is moved past the copied rows so new reviews don't
collide with them.

The target must be empty (re-running never duplicates rows) and is created if it
does not exist yet. The source is only read.

Usage (from the repo root; put the target in the environment so the password
does not end up in your shell history):

    export DATABASE_URL=postgresql://user:password@host:5432/codereview
    python scripts/migrate_db.py                       # backend/reviews.db -> $DATABASE_URL
    python scripts/migrate_db.py --source other.db     # a different SQLite file
    python scripts/migrate_db.py --source postgresql://... --target sqlite:///copy.db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import func, select, text          # noqa: E402
from sqlalchemy.orm import Session                  # noqa: E402

from app import storage                             # noqa: E402


def _as_url(source: str) -> str:
    """A bare file path means a SQLite file; anything with a scheme is a URL."""
    if "://" in source:
        return storage.normalize_database_url(source)
    return f"sqlite:///{Path(source).resolve()}"


def migrate(source: str, target: str) -> int:
    """Copy every review from `source` to the empty `target`; return the count.

    Both are database URLs (or, for `source`, a SQLite file path).
    """
    src_engine = storage.make_engine(_as_url(source))
    dst_engine = storage.make_engine(storage.normalize_database_url(target))
    try:
        return _copy(src_engine, dst_engine)
    finally:
        src_engine.dispose()
        dst_engine.dispose()


def _copy(src_engine, dst_engine) -> int:
    if src_engine.url == dst_engine.url:
        raise ValueError("Source and target are the same database.")

    storage.Base.metadata.create_all(dst_engine)
    columns = [c.name for c in storage.ReviewRecord.__table__.columns]

    with Session(src_engine) as src, Session(dst_engine) as dst:
        already = dst.scalar(select(func.count()).select_from(storage.ReviewRecord))
        if already:
            raise ValueError(
                f"Target already holds {already} review(s); refusing to copy into it."
            )
        count = 0
        for rec in src.scalars(
            select(storage.ReviewRecord).order_by(storage.ReviewRecord.id)
        ):
            dst.add(storage.ReviewRecord(**{c: getattr(rec, c) for c in columns}))
            count += 1
        dst.commit()

        if dst_engine.dialect.name == "postgresql":
            # Explicit ids were inserted, so the SERIAL sequence is still at 1.
            dst.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('reviews', 'id'), "
                    "COALESCE((SELECT MAX(id) FROM reviews), 1), "
                    "(SELECT COUNT(*) > 0 FROM reviews))"
                )
            )
            dst.commit()
    return count


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Copy reviews between databases.")
    ap.add_argument(
        "--source",
        default=str(storage.DB_PATH),
        help="SQLite file or database URL to read (default: backend/reviews.db).",
    )
    ap.add_argument(
        "--target",
        default=os.environ.get("DATABASE_URL", ""),
        help="Database URL to write (default: the DATABASE_URL environment variable).",
    )
    args = ap.parse_args(argv)
    if not args.target:
        ap.error("no target: set DATABASE_URL or pass --target")
    try:
        n = migrate(args.source, args.target)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Copied {n} review(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
