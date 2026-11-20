"""FastAPI application entrypoint.

Exposes the review pipeline as an HTTP API. `/review` wires the four modules
together for one code change:

    Module 1 (collect)  ->  Module 2 (AI review) + Module 3 (security scan)
                        ->  Module 4 (fuse + rank)  ->  JSON report

The heavy pieces (the AI model, Semgrep) are optional and loaded lazily, so the
service — and the /health check — start instantly, and /review degrades
gracefully (with a note) when a piece isn't available in the current
environment. That is why importing this file never pulls in torch/transformers.
"""

from __future__ import annotations

import os
import tempfile
import time
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from . import export, storage, trends
from .collector import ChangedFile, collect_from_diff_text
from .fusion import AIComment, fuse
from .schemas import ReviewRequest

app = FastAPI(
    title="Automated Code Review AI",
    description=(
        "Backend for the Automated Code Review AI with Vulnerability & Style "
        "Feedback. Fuses AI review comments with Semgrep security findings and "
        "posts them back to GitHub PRs."
    ),
    version="0.2.0",
)

# Allow the React dashboard (a separate dev server) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",  # Vite default
        "http://localhost:3000", "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create the reviews table on import if it doesn't exist (idempotent).
storage.init_db()


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness probe. Returns 200 with basic service metadata."""
    return {
        "status": "ok",
        "service": app.title,
        "version": app.version,
        "database": storage.backend_name(),
    }


@app.get("/", tags=["meta"])
def root() -> dict:
    """Root route with a pointer to the interactive API docs."""
    return {"message": f"{app.title} v{app.version}", "docs": "/docs"}


# --------------------------------------------------------------------------- #
# /review — the end-to-end pipeline
# --------------------------------------------------------------------------- #

@app.post("/review", tags=["review"])
def review(req: ReviewRequest) -> dict:
    """Review one code change and return a fused, ranked report."""
    started = time.perf_counter()
    notes: List[str] = []

    # Module 1 — collect changed (Python/JS) files from the diff.
    changed = collect_from_diff_text(req.diff)
    if not changed:
        notes.append("No supported (Python/JavaScript) files found in the diff.")

    # Module 3 — security findings.
    security_executed = False
    findings = []
    if req.run_security:
        findings, security_executed = _run_security(req, notes)

    # Module 2 — AI review comments (one per changed file).
    ai_executed = False
    ai_comments = []
    misses_before = _get_reviewer.cache_info().misses
    if req.run_ai:
        ai_comments, ai_executed = _run_ai(req, changed, notes)
    # True when this request had to load the model (a one-time cost that
    # inflates response_time_ms), so the dashboard can flag the outlier.
    cold_start = ai_executed and _get_reviewer.cache_info().misses > misses_before

    # Module 4 — merge, de-duplicate, and rank.
    report = fuse(findings, ai_comments, notes=notes)
    fused_findings = len(report.comments)

    run_metrics = {
        "response_time_ms": None,  # filled after persistence (full API processing)
        "ai_findings": len(ai_comments) if ai_executed else None,
        "security_findings": len(findings) if security_executed else None,
        "fused_findings": fused_findings,
        "cold_start": cold_start,
    }

    # Module 6 (data layer) — persist so the dashboard has history.
    review_id = storage.save_report(
        report,
        repo=req.repo,
        pr_number=req.pr_number,
        commit_sha=req.commit_sha,
        author=req.author,
        run_metrics=run_metrics,
    )

    # "API response time" here means full backend /review handling, including
    # persistence. This excludes client/network transfer time.
    response_time_ms = round((time.perf_counter() - started) * 1000.0, 3)
    run_metrics["response_time_ms"] = response_time_ms
    storage.update_run_metrics(review_id, run_metrics)

    result = report.to_dict()
    result["review_id"] = review_id
    result["run_metrics"] = run_metrics
    return result


# --------------------------------------------------------------------------- #
# Dashboard read endpoints (Module 6)
# --------------------------------------------------------------------------- #

@app.get("/reviews", tags=["dashboard"])
def list_reviews(limit: int = 20) -> dict:
    """Recent reviews (compact rows), newest first."""
    return {"reviews": storage.list_reviews(limit=limit)}


def _download(body: str, media_type: str, filename: str) -> Response:
    return Response(
        content=body,
        media_type=f"{media_type}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


# NOTE: declared before /reviews/{review_id} so "export" is not read as an id.
@app.get("/reviews/export", tags=["dashboard"])
def export_reviews(
    format: str = Query("csv", pattern="^(csv|json)$"),
    scope: str = Query("reviews", pattern="^(reviews|findings)$"),
    repo: str = "",
    author: str = "",
    severity: str = "",
    file: str = "",
    limit: int = Query(1000, ge=1, le=5000),
) -> Response:
    """Download review history as CSV or JSON, with the dashboard's filters.

    - `format=csv&scope=reviews`  one row per review (default)
    - `format=csv&scope=findings` one row per finding
    - `format=json`               full reports plus run metrics
    """
    try:
        reviews = storage.query_reviews(
            repo=repo,
            author=author,
            severity=severity,
            file=file,
            limit=limit,
            with_reports=(format == "json" or scope == "findings"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if format == "json":
        filters = {"repo": repo, "author": author, "severity": severity, "file": file}
        return _download(
            export.reviews_to_json(reviews, filters),
            "application/json",
            f"reviews-{_stamp()}.json",
        )
    if scope == "findings":
        return _download(
            export.findings_to_csv(reviews), "text/csv", f"findings-{_stamp()}.csv"
        )
    return _download(
        export.reviews_to_csv(reviews), "text/csv", f"reviews-{_stamp()}.csv"
    )


@app.get("/reviews/{review_id}/export", tags=["dashboard"])
def export_review(
    review_id: int,
    format: str = Query("csv", pattern="^(csv|json)$"),
) -> Response:
    """Download one review: its findings as CSV, or the full report as JSON."""
    review = storage.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")
    if format == "json":
        return _download(
            export.reviews_to_json([review], {}),
            "application/json",
            f"review-{review_id}.json",
        )
    return _download(
        export.findings_to_csv([review]),
        "text/csv",
        f"review-{review_id}-findings.csv",
    )


@app.get("/reviews/{review_id}", tags=["dashboard"])
def get_review(review_id: int) -> dict:
    """The full stored report for one review."""
    review = storage.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")
    return review


@app.get("/stats", tags=["dashboard"])
def stats(days: int = 14, runs: int = 30) -> dict:
    """Aggregate numbers for the dashboard cards and charts.

    `runs` caps how many of the most recent runs appear in `run_history`.
    """
    return storage.get_stats(days=days, run_limit=max(1, min(runs, 500)))


@app.get("/stats/authors", tags=["dashboard"])
def author_trends(
    days: int = Query(30, ge=1, le=365),
    min_reviews: int = Query(trends.DEFAULT_MIN_REVIEWS, ge=2, le=100),
) -> dict:
    """Per-author findings-per-review trend over the last `days` days."""
    reviews = storage.query_reviews(limit=5000)
    return trends.compute_author_trends(reviews, days=days, min_reviews=min_reviews)


def _first_line(cf: ChangedFile) -> int:
    """Best-effort anchor line for an AI comment: the first changed hunk's start."""
    return cf.hunks[0].start_line if cf.hunks else 0


def _run_security(req: ReviewRequest, notes: List[str]) -> Tuple[list, bool]:
    """Module 3 with graceful fallbacks (pre-computed JSON, live scan, or skip)."""
    from .security import load_findings_from_file  # noqa: F401  (kept for parity)
    from .security import parse_semgrep_json, scan_paths, semgrep_available

    # 1. CI already ran Semgrep and handed us the JSON — just parse it.
    if req.semgrep_json is not None:
        return parse_semgrep_json(req.semgrep_json), True

    # 2. We have file contents and Semgrep is installed — scan them live.
    if req.files and semgrep_available():
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for rel_path, content in req.files.items():
                dest = os.path.join(tmp, rel_path.replace("/", os.sep))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "w", encoding="utf-8") as fh:
                    fh.write(content)
                paths.append(dest)
            return scan_paths(paths), True

    # 3. Nothing to scan with.
    notes.append(
        "Security scan skipped: provide `semgrep_json`, or `files` with Semgrep installed."
    )
    return [], False


def _run_ai(
    req: ReviewRequest,
    changed: List[ChangedFile],
    notes: List[str],
) -> Tuple[List[AIComment], bool]:
    """Module 2 with a graceful fallback when the model can't be loaded."""
    reviewer = _get_reviewer(req.model_path)
    if reviewer is None:
        notes.append(
            "AI review skipped: model could not be loaded (set `model_path` to the "
            "fine-tuned weights, or run where transformers + the model are available)."
        )
        return [], False

    comments: List[AIComment] = []
    for cf in changed:
        try:
            message = reviewer.review(cf.patch)
        except Exception as exc:  # keep the endpoint resilient to a single bad file
            notes.append(f"AI review failed for {cf.path}: {exc}")
            continue
        if message.strip():
            comments.append(
                AIComment(path=cf.path, line=_first_line(cf), message=message.strip())
            )
    return comments, True


@lru_cache(maxsize=2)
def _get_reviewer(model_path: Optional[str]):
    """Load (and cache) the AI reviewer, or return None if it can't be loaded.

    Cached so the model is loaded once per process, not once per request.
    """
    try:
        from .reviewer import AICodeReviewer

        return AICodeReviewer(model_path) if model_path else AICodeReviewer()
    except Exception:
        return None
