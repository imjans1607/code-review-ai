"""Module 6 (data layer) — persist review reports so the dashboard has history.

Every `/review` result is saved as one row in a small relational database. The
dashboard reads back the recent reviews and some aggregate statistics (severity
distribution, a per-day trend) from here.

Which database: SQLite by default (zero-setup, one local file) and PostgreSQL
when the `DATABASE_URL` environment variable is set, e.g.

    DATABASE_URL=postgresql://user:password@host:5432/codereview

This is the "SQLite local dev / PostgreSQL deployed" choice named in the idea
doc. `backend/.env` is loaded automatically if present. The same SQLAlchemy
models serve both; there is no database-specific SQL in this file.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy import Integer, String, Text, create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .fusion.models import ReviewReport
from .security.findings import SEVERITY_ORDER

# Default database: one SQLite file next to the backend package (gitignored: *.db).
DB_PATH = Path(__file__).resolve().parent.parent / "reviews.db"

# Pick up DATABASE_URL from backend/.env for local runs. Real environment
# variables win (override=False), so CI and deployments are unaffected.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)


def normalize_database_url(url: str) -> str:
    """Accept the URL forms people actually paste and map them to psycopg 3.

    Hosts such as Heroku/Render hand out `postgres://...`, and plain
    `postgresql://...` would make SQLAlchemy look for the old psycopg2 driver.
    URLs that already name a driver (`postgresql+psycopg://`) or another database
    (`sqlite:///...`) are left alone.
    """
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def database_url() -> str:
    """The configured database URL: `DATABASE_URL` if set, else local SQLite."""
    raw = os.environ.get("DATABASE_URL", "").strip()
    return normalize_database_url(raw) if raw else f"sqlite:///{DB_PATH}"


def make_engine(url: Optional[str] = None) -> Engine:
    """Create an engine for `url` (default: the configured database)."""
    url = normalize_database_url(url) if url else database_url()
    options: Dict[str, Any] = {"future": True}
    if url.startswith("postgresql"):
        # Hosted Postgres closes idle connections; probe before reusing one.
        options["pool_pre_ping"] = True
    return create_engine(url, **options)


_engine = make_engine()

# Column widths. SQLite ignores them but PostgreSQL enforces them, so inputs are
# clipped on write instead of failing the request.
_REPO_MAX, _AUTHOR_MAX, _SHA_MAX = 200, 120, 64


def backend_name() -> str:
    """Dialect in use ("sqlite" / "postgresql"), safe to expose (no credentials)."""
    return _engine.dialect.name


class Base(DeclarativeBase):
    pass


class ReviewRecord(Base):
    """One saved review: who/when, the severity counts, and the full report."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[str] = mapped_column(String(32))  # ISO-8601 UTC
    repo: Mapped[str] = mapped_column(String(200), default="")
    pr_number: Mapped[int] = mapped_column(Integer, default=0)
    author: Mapped[str] = mapped_column(String(120), default="")
    commit_sha: Mapped[str] = mapped_column(String(64), default="")
    total: Mapped[int] = mapped_column(Integer, default=0)
    critical: Mapped[int] = mapped_column(Integer, default=0)
    high: Mapped[int] = mapped_column(Integer, default=0)
    medium: Mapped[int] = mapped_column(Integer, default=0)
    low: Mapped[int] = mapped_column(Integer, default=0)
    informational: Mapped[int] = mapped_column(Integer, default=0)
    report_json: Mapped[str] = mapped_column(Text)

    def summary_row(self) -> dict:
        """A compact record for the reviews list (no full comment payload).

        Includes the distinct file paths touched by this review's comments so the
        dashboard can offer a file filter without loading every full report.
        """
        report = json.loads(self.report_json)
        files = sorted(
            {
                c.get("path", "")
                for c in report.get("comments", [])
                if c.get("path")
            }
        )
        metrics = _extract_run_metrics(report, fallback_total=self.total)
        return {
            "id": self.id,
            "created_at": self.created_at,
            "repo": self.repo,
            "pr_number": self.pr_number,
            "author": self.author,
            "commit_sha": self.commit_sha,
            "total": self.total,
            "files": files,
            "response_time_ms": metrics["response_time_ms"],
            "ai_findings": metrics["ai_findings"],
            "security_findings": metrics["security_findings"],
            "fused_findings": metrics["fused_findings"],
            "cold_start": metrics["cold_start"],
            "summary": {
                "Critical": self.critical,
                "High": self.high,
                "Medium": self.medium,
                "Low": self.low,
                "Informational": self.informational,
            },
        }


def init_db() -> None:
    """Create the table if it doesn't exist yet. Safe to call on every startup."""
    Base.metadata.create_all(_engine)


def save_report(
    report: ReviewReport,
    repo: str = "",
    pr_number: int = 0,
    commit_sha: str = "",
    author: str = "",
    run_metrics: Optional[Dict[str, Any]] = None,
) -> int:
    """Persist one fused report and return its new database id."""
    s = report.summary
    payload = report.to_dict()
    payload["run_metrics"] = _normalize_run_metrics(run_metrics, fallback_total=len(report.comments))
    record = ReviewRecord(
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        repo=(repo or "")[:_REPO_MAX],
        pr_number=pr_number,
        author=(author or "")[:_AUTHOR_MAX],
        commit_sha=(commit_sha or "")[:_SHA_MAX],
        total=len(report.comments),
        critical=s.get("Critical", 0),
        high=s.get("High", 0),
        medium=s.get("Medium", 0),
        low=s.get("Low", 0),
        informational=s.get("Informational", 0),
        report_json=json.dumps(payload),
    )
    with Session(_engine) as db:
        db.add(record)
        db.commit()
        db.refresh(record)
        return record.id


def update_run_metrics(review_id: int, run_metrics: Optional[Dict[str, Any]]) -> None:
    """Patch stored run metrics for an existing review row (idempotent)."""
    with Session(_engine) as db:
        record = db.get(ReviewRecord, review_id)
        if record is None:
            return
        payload = json.loads(record.report_json)
        payload["run_metrics"] = _normalize_run_metrics(run_metrics, fallback_total=record.total)
        record.report_json = json.dumps(payload)
        db.commit()


def list_reviews(limit: int = 20) -> List[dict]:
    """The most recent reviews (compact rows), newest first."""
    with Session(_engine) as db:
        rows = db.scalars(
            select(ReviewRecord).order_by(ReviewRecord.id.desc()).limit(limit)
        ).all()
        return [r.summary_row() for r in rows]


_SEVERITY_COLUMNS = {
    "Critical": ReviewRecord.critical,
    "High": ReviewRecord.high,
    "Medium": ReviewRecord.medium,
    "Low": ReviewRecord.low,
    "Informational": ReviewRecord.informational,
}


def query_reviews(
    repo: str = "",
    author: str = "",
    severity: str = "",
    file: str = "",
    limit: int = 1000,
    with_reports: bool = False,
) -> List[dict]:
    """Reviews matching the dashboard's filters, newest first (for export).

    Mirrors the dashboard filter bar: exact `repo` / `author`, `severity` =
    reviews with at least one finding of that severity, `file` = case-insensitive
    substring of a touched path. Unlike `list_reviews` it searches the whole
    history, then applies `limit`. Raises ValueError for an unknown severity.
    """
    if severity and severity not in _SEVERITY_COLUMNS:
        raise ValueError(f"Unknown severity: {severity!r}")
    stmt = select(ReviewRecord).order_by(ReviewRecord.id.desc())
    if repo:
        stmt = stmt.where(ReviewRecord.repo == repo)
    if author:
        stmt = stmt.where(ReviewRecord.author == author)
    if severity:
        stmt = stmt.where(_SEVERITY_COLUMNS[severity] > 0)

    needle = file.strip().lower()
    out: List[dict] = []
    with Session(_engine) as db:
        for rec in db.scalars(stmt):
            row = rec.summary_row()
            if needle and not any(needle in p.lower() for p in row["files"]):
                continue
            if with_reports:
                row["report"] = json.loads(rec.report_json)
            out.append(row)
            if len(out) >= limit:
                break
    return out


def get_review(review_id: int) -> Optional[dict]:
    """The full stored report for one review, or None if not found."""
    with Session(_engine) as db:
        record = db.get(ReviewRecord, review_id)
        if record is None:
            return None
        row = record.summary_row()
        row["report"] = json.loads(record.report_json)
        return row


def get_stats(days: int = 14, run_limit: int = 30) -> dict:
    """Aggregate numbers for the dashboard's cards and charts.

    `run_history` holds only the `run_limit` most recent runs (oldest first) so
    the run-metric charts stay readable and the payload stays bounded.
    """
    with Session(_engine) as db:
        records = db.scalars(select(ReviewRecord)).all()

    severity_totals = {sev: 0 for sev in SEVERITY_ORDER}
    category_totals: Counter = Counter()
    rule_totals: Counter = Counter()
    per_day: dict = defaultdict(int)

    reports = {rec.id: json.loads(rec.report_json) for rec in records}

    for rec in records:
        severity_totals["Critical"] += rec.critical
        severity_totals["High"] += rec.high
        severity_totals["Medium"] += rec.medium
        severity_totals["Low"] += rec.low
        severity_totals["Informational"] += rec.informational
        per_day[rec.created_at[:10]] += rec.total  # group by YYYY-MM-DD

        for comment in reports[rec.id].get("comments", []):
            category_totals[comment.get("category", "other")] += 1
            if comment.get("rule_id"):
                rule_totals[comment["rule_id"]] += 1

    # Fill a continuous date range so the trend line has no gaps.
    today = datetime.now(timezone.utc).date()
    trend = []
    for i in range(days - 1, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        trend.append({"date": day, "findings": per_day.get(day, 0)})

    run_history = []
    recent = sorted(records, key=lambda r: r.id)[-run_limit:]
    for rec in recent:
        metrics = _extract_run_metrics(reports[rec.id], fallback_total=rec.total)
        run_history.append(
            {
                "review_id": rec.id,
                "pr_number": rec.pr_number,
                "created_at": rec.created_at,
                "response_time_ms": metrics["response_time_ms"],
                "ai_findings": metrics["ai_findings"],
                "security_findings": metrics["security_findings"],
                "fused_findings": metrics["fused_findings"],
                "cold_start": metrics["cold_start"],
            }
        )

    return {
        "total_reviews": len(records),
        "total_findings": sum(severity_totals.values()),
        "severity_totals": severity_totals,
        "category_totals": dict(category_totals),
        "top_rules": [
            {"rule_id": rid, "count": n} for rid, n in rule_totals.most_common(5)
        ],
        "trend": trend,
        "run_history": run_history,
    }


def _normalize_nullable_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_nullable_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_run_metrics(
    run_metrics: Optional[Dict[str, Any]],
    fallback_total: int,
) -> dict:
    data = run_metrics or {}
    return {
        "response_time_ms": _normalize_nullable_float(data.get("response_time_ms")),
        "ai_findings": _normalize_nullable_int(data.get("ai_findings")),
        "security_findings": _normalize_nullable_int(data.get("security_findings")),
        "fused_findings": _normalize_nullable_int(data.get("fused_findings"))
        if data.get("fused_findings") is not None
        else int(fallback_total),
        "cold_start": bool(data.get("cold_start", False)),
    }


def _extract_run_metrics(report: dict, fallback_total: int) -> dict:
    return _normalize_run_metrics(report.get("run_metrics"), fallback_total=fallback_total)
