"""Module 5 (posting side) — publish a ReviewReport back to a GitHub Pull Request.

Turns the fused review (Module 4) into GitHub comments:
  - a **summary** comment (a severity table + the full list), always reliable, and
  - **inline** comments on the exact changed lines, when the line is in the diff.

It posts a single PR *review* containing both. A `dry_run` mode prints exactly
what would be posted, so the whole thing is runnable and explainable offline,
without a token or network — the same offline-first style as the other modules.
"""

from __future__ import annotations

import sys
from typing import Dict, List, Optional, Set

from ..collector.diff_parser import parse_unified_diff
from ..fusion.models import ReviewComment, ReviewReport

GITHUB_API = "https://api.github.com"

# A small visual cue per severity for the posted comments.
SEVERITY_EMOJI = {
    "Critical": "🔴",
    "High": "🟠",
    "Medium": "🟡",
    "Low": "🔵",
    "Informational": "⚪",
}


def format_comment_body(c: ReviewComment) -> str:
    """The markdown body for a single inline comment."""
    emoji = SEVERITY_EMOJI.get(c.severity, "")
    parts = [f"{emoji} **{c.severity} · {c.category}**", "", c.message]
    if c.cwe:
        parts += ["", f"_{c.cwe[0]}_"]
    if c.rationale:
        parts += ["", f"> {c.rationale}"]
    return "\n".join(parts)


def format_summary_markdown(report: ReviewReport) -> str:
    """The top-level PR review body: a count table plus every comment."""
    lines = ["## 🤖 Automated Code Review", ""]

    if not report.comments:
        lines.append("No issues found in the changed Python/JavaScript lines. ✅")
    else:
        lines.append("| Severity | Count |")
        lines.append("|---|---|")
        for sev, n in report.summary.items():
            lines.append(f"| {SEVERITY_EMOJI.get(sev, '')} {sev} | {n} |")
        lines.append("")
        for c in report.comments:
            loc = f"`{c.path}:{c.line}`" if c.line else f"`{c.path}`"
            lines.append(f"- {SEVERITY_EMOJI.get(c.severity, '')} **{c.severity}** "
                         f"({c.category}) {loc} — {c.message}")

    if report.notes:
        lines += ["", "<sub>Notes: " + "; ".join(report.notes) + "</sub>"]
    return "\n".join(lines)


def _normalize_path(path: str) -> str:
    clean = path.replace("\\", "/").strip()
    while clean.startswith("./"):
        clean = clean[2:]
    return clean


def _valid_inline_lines_by_path(diff_text: Optional[str]) -> Optional[Dict[str, Set[int]]]:
    if not diff_text:
        return None
    valid: Dict[str, Set[int]] = {}
    for fd in parse_unified_diff(diff_text):
        path = _normalize_path(fd.path)
        if not path:
            continue
        added = {ln.new_lineno for ln in fd.added_lines if ln.new_lineno is not None}
        valid[path] = added
    return valid


def to_inline_comments(report: ReviewReport, diff_text: Optional[str] = None) -> List[dict]:
    """Build GitHub review-comment objects for issues that have a real line."""
    valid_lines = _valid_inline_lines_by_path(diff_text)
    comments = []
    for c in report.comments:
        if not (c.line and c.line > 0):
            continue

        path = _normalize_path(c.path)
        if valid_lines is not None:
            path_lines = valid_lines.get(path)
            if not path_lines or c.line not in path_lines:
                continue

        comments.append({
            "path": path,
            "line": c.line,
            "side": "RIGHT",   # the new version of the file
            "body": format_comment_body(c),
        })
    return comments


def post_review(
    report: ReviewReport,
    repo: str,
    pr_number: int,
    commit_id: str,
    token: Optional[str] = None,
    dry_run: bool = False,
    diff_text: Optional[str] = None,
) -> dict:
    """Post the report as one PR review (summary + inline comments).

    `repo` is "owner/name". With `dry_run=True` (or no token) it prints what would
    be sent instead of calling the API.
    """
    body = format_summary_markdown(report)
    inline = to_inline_comments(report, diff_text=diff_text)
    payload = {
        "commit_id": commit_id,
        "body": body,
        "event": "COMMENT",   # COMMENT = leave feedback without approving/blocking
        "comments": inline,
    }

    if dry_run or not token:
        print(f"[dry-run] would POST a review to {repo} PR #{pr_number} "
              f"({len(inline)} inline comment(s))\n")
        print(body)
        return {"dry_run": True, "inline_comments": len(inline)}

    import httpx

    try:
        resp = httpx.post(
            f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/reviews",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        reason = exc.response.reason_phrase if exc.response is not None else ""
        method = exc.request.method if exc.request is not None else "POST"
        url = str(exc.request.url) if exc.request is not None else "unknown-url"
        print(
            f"GitHub review post failed: HTTP {status} {reason} for {method} {url}",
            file=sys.stderr,
        )
        if exc.response is not None:
            body = exc.response.text.strip()
            if body:
                print(f"GitHub response body: {body}", file=sys.stderr)
        raise


def _demo(semgrep_json_path: str) -> None:
    """Build a report from the samples and dry-run the posting."""
    from ..fusion import AIComment, fuse
    from ..security import load_findings_from_file

    findings = load_findings_from_file(semgrep_json_path)
    ai = [AIComment(path="examples/vulnerable_samples/app.py", line=8,
                    message="Consider adding a docstring for get_user.")]
    report = fuse(findings, ai)
    post_review(report, repo="student/demo-repo", pr_number=1,
                commit_id="abc123", dry_run=True)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # emoji-safe on any console
    except Exception:
        pass
    target = sys.argv[1] if len(sys.argv) > 1 else "examples/semgrep_sample_output.json"
    _demo(target)
