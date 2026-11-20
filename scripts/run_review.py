#!/usr/bin/env python3
"""GitHub Actions entrypoint — review a pull request and post the result.

Runs the pipeline in-process (Module 1 collect -> Module 3 parse Semgrep ->
Module 4 fuse) and posts via Module 5. Semgrep itself is run by the workflow
step before this script (it runs natively on the Linux runner); this script just
parses its JSON. The AI reviewer (Module 2) runs only if AI_MODEL_PATH is set.

Usage (from the repo root, as the workflow calls it):
    python scripts/run_review.py --diff change.diff --semgrep semgrep.json \
        --repo owner/name --pr 42 --commit <sha>

Environment:
    GITHUB_TOKEN   — required to actually post (otherwise runs as a dry-run)
    AI_MODEL_PATH  — optional fine-tuned model (HF id or path) to enable Module 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# The posted comments use emoji; make stdout UTF-8 so a dry-run print doesn't
# crash on a non-UTF-8 console (e.g. Windows cp1252). No-op where already UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Make the backend package importable (repo_root/backend/app).
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app import storage                                     # noqa: E402
from app.collector import collect_from_diff_text          # noqa: E402
from app.fusion import AIComment, fuse, restrict_to_added_lines  # noqa: E402
from app.publisher import post_review                       # noqa: E402
from app.security import parse_semgrep_json                 # noqa: E402


def _read(path: str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Review a PR and post comments.")
    ap.add_argument("--diff", required=True, help="Unified diff file for the PR.")
    ap.add_argument("--semgrep", help="Semgrep --json output file (optional).")
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--pr", type=int, required=True, help="Pull request number.")
    ap.add_argument("--commit", required=True, help="Head commit SHA.")
    ap.add_argument("--author", default="", help="Login of the PR author.")
    ap.add_argument("--dry-run", action="store_true", help="Print instead of posting.")
    args = ap.parse_args()

    started = time.perf_counter()
    notes = []
    diff_text = _read(args.diff)

    # Module 3 — Semgrep already ran in the workflow; just parse its output.
    findings = []
    security_executed = False
    if args.semgrep and Path(args.semgrep).exists():
        findings = parse_semgrep_json(json.loads(_read(args.semgrep)))
        security_executed = True
        # Semgrep scanned the whole checkout; keep only what this PR changed.
        scope = restrict_to_added_lines(findings, diff_text)
        findings = scope.findings
        if not scope.scoped:
            notes.append("Could not read the PR diff, so security findings are not limited "
                         "to changed lines")
        elif scope.dropped:
            notes.append(f"{scope.dropped} security finding(s) on code this PR did not "
                         "change were left out")
    else:
        notes.append("Security scan output not found.")

    # Module 2 — AI review, only when a model is configured.
    ai_comments = []
    ai_executed = False
    model_path = os.environ.get("AI_MODEL_PATH")
    if model_path:
        try:
            from app.reviewer import AICodeReviewer

            reviewer = AICodeReviewer(model_path)
            for cf in collect_from_diff_text(diff_text):
                message = reviewer.review(cf.patch)
                if message.strip():
                    line = cf.hunks[0].start_line if cf.hunks else 0
                    ai_comments.append(
                        AIComment(path=cf.path, line=line, message=message.strip())
                    )
            ai_executed = True
        except Exception as exc:  # never fail the job over the AI step
            notes.append(f"AI review skipped: {exc}")
    else:
        notes.append("AI review skipped: AI_MODEL_PATH not set.")

    # Module 4 — fuse + rank.
    report = fuse(findings, ai_comments, notes=notes)

    # Module 6 — persist so the dashboard shows this CI run.
    # Same metric definitions as the /review endpoint; here the model is loaded
    # fresh in this process, so any run that used the AI layer is a cold start.
    run_metrics = {
        "response_time_ms": None,
        "ai_findings": len(ai_comments) if ai_executed else None,
        "security_findings": len(findings) if security_executed else None,
        "fused_findings": len(report.comments),
        "cold_start": ai_executed,
    }
    try:
        storage.init_db()
        review_id = storage.save_report(
            report, repo=args.repo, pr_number=args.pr,
            commit_sha=args.commit, author=args.author,
            run_metrics=run_metrics,
        )
        # Review pipeline + persistence; excludes the GitHub post below.
        run_metrics["response_time_ms"] = round(
            (time.perf_counter() - started) * 1000.0, 3
        )
        storage.update_run_metrics(review_id, run_metrics)
    except Exception as exc:  # never fail the job over persistence
        print("Warning: could not persist review:", exc)

    # Module 5 — post (or dry-run when no token).
    token = os.environ.get("GITHUB_TOKEN")
    result = post_review(
        report,
        repo=args.repo,
        pr_number=args.pr,
        commit_id=args.commit,
        token=token,
        dry_run=args.dry_run or not token,
        diff_text=diff_text,
    )
    print("\nPosted:", json.dumps(result)[:300])


if __name__ == "__main__":
    main()
