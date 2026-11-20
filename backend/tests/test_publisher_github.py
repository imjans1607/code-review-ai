from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.fusion.models import ReviewComment, ReviewReport
from app.publisher.github import format_summary_markdown, post_review, to_inline_comments


DIFF_TEXT = """diff --git a/src/a.py b/src/a.py
index 0000000..1111111 100644
--- a/src/a.py
+++ b/src/a.py
@@ -1,2 +1,3 @@
 keep
+added
 keep2
"""


def _report_with_three_findings() -> ReviewReport:
    comments = [
        ReviewComment(
            path="src/a.py",
            line=2,
            severity="High",
            category="security",
            message="valid added line",
            source="semgrep",
        ),
        ReviewComment(
            path="src/a.py",
            line=1,
            severity="Medium",
            category="security",
            message="unchanged line",
            source="semgrep",
        ),
        ReviewComment(
            path="src/outside.py",
            line=10,
            severity="Low",
            category="style",
            message="outside diff",
            source="ai-model",
        ),
    ]
    return ReviewReport(comments=comments, summary={"High": 1, "Medium": 1, "Low": 1}, notes=[])


class PublisherGithubTests(unittest.TestCase):
    def test_inline_comments_include_only_valid_added_lines(self) -> None:
        report = _report_with_three_findings()
        inline = to_inline_comments(report, diff_text=DIFF_TEXT)
        self.assertEqual(len(inline), 1)
        self.assertEqual(inline[0]["path"], "src/a.py")
        self.assertEqual(inline[0]["line"], 2)
        self.assertEqual(inline[0]["side"], "RIGHT")

    def test_summary_retains_all_findings_when_inline_filtered(self) -> None:
        report = _report_with_three_findings()
        inline = to_inline_comments(report, diff_text=DIFF_TEXT)
        summary = format_summary_markdown(report)
        self.assertEqual(len(inline), 1)
        self.assertIn("`src/a.py:2`", summary)
        self.assertIn("`src/a.py:1`", summary)
        self.assertIn("`src/outside.py:10`", summary)

    def test_inline_comments_accept_multi_hunk_added_lines(self) -> None:
        report = ReviewReport(
            comments=[
                ReviewComment(
                    path="src/multi.py",
                    line=2,
                    severity="High",
                    category="security",
                    message="first hunk add",
                    source="semgrep",
                ),
                ReviewComment(
                    path="src/multi.py",
                    line=11,
                    severity="Medium",
                    category="security",
                    message="second hunk add",
                    source="semgrep",
                ),
            ],
            summary={"High": 1, "Medium": 1},
            notes=[],
        )
        diff_text = (
            "diff --git a/src/multi.py b/src/multi.py\n"
            "--- a/src/multi.py\n"
            "+++ b/src/multi.py\n"
            "@@ -1,1 +1,2 @@\n"
            " keep\n"
            "+add1\n"
            "@@ -10,1 +10,2 @@\n"
            " keep\n"
            "+add2\n"
        )

        inline = to_inline_comments(report, diff_text=diff_text)
        self.assertEqual([(c["path"], c["line"]) for c in inline], [("src/multi.py", 2), ("src/multi.py", 11)])

    def test_inline_comment_paths_are_normalized(self) -> None:
        report = ReviewReport(
            comments=[
                ReviewComment(
                    path=".\\src\\a.py",
                    line=2,
                    severity="High",
                    category="security",
                    message="normalized path",
                    source="semgrep",
                )
            ],
            summary={"High": 1},
            notes=[],
        )

        inline = to_inline_comments(report, diff_text=DIFF_TEXT)
        self.assertEqual(len(inline), 1)
        self.assertEqual(inline[0]["path"], "src/a.py")

    def test_inline_comments_handle_renamed_and_new_files(self) -> None:
        report = ReviewReport(
            comments=[
                ReviewComment(
                    path="src/new_name.py",
                    line=5,
                    severity="High",
                    category="security",
                    message="rename target",
                    source="semgrep",
                ),
                ReviewComment(
                    path="src/old_name.py",
                    line=5,
                    severity="High",
                    category="security",
                    message="rename source path should not post",
                    source="semgrep",
                ),
                ReviewComment(
                    path="src/brand_new.py",
                    line=1,
                    severity="Medium",
                    category="security",
                    message="new file line",
                    source="semgrep",
                ),
            ],
            summary={"High": 2, "Medium": 1},
            notes=[],
        )
        diff_text = (
            "diff --git a/src/old_name.py b/src/new_name.py\n"
            "--- a/src/old_name.py\n"
            "+++ b/src/new_name.py\n"
            "@@ -4,1 +4,2 @@\n"
            " keep\n"
            "+renamed_add\n"
            "diff --git a/src/brand_new.py b/src/brand_new.py\n"
            "--- /dev/null\n"
            "+++ b/src/brand_new.py\n"
            "@@ -0,0 +1 @@\n"
            "+new_line\n"
        )

        inline = to_inline_comments(report, diff_text=diff_text)
        self.assertEqual([(c["path"], c["line"]) for c in inline], [("src/new_name.py", 5), ("src/brand_new.py", 1)])

    @patch("httpx.post")
    def test_post_review_submits_summary_when_no_valid_inline_comments(self, mock_post: Mock) -> None:
        report = ReviewReport(
            comments=[
                ReviewComment(
                    path="src/a.py",
                    line=99,
                    severity="High",
                    category="security",
                    message="not in diff",
                    source="semgrep",
                )
            ],
            summary={"High": 1},
            notes=[],
        )
        response = Mock()
        response.raise_for_status = Mock()
        response.json = Mock(return_value={"id": 123})
        mock_post.return_value = response

        result = post_review(
            report,
            repo="owner/repo",
            pr_number=1,
            commit_id="abc123",
            token="token",
            dry_run=False,
            diff_text=DIFF_TEXT,
        )

        self.assertEqual(result, {"id": 123})
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["comments"], [])
        self.assertIn("not in diff", payload["body"])

    @patch("httpx.post")
    def test_post_review_422_logs_response_body(self, mock_post: Mock) -> None:
        report = ReviewReport(
            comments=[
                ReviewComment(
                    path="src/a.py",
                    line=2,
                    severity="High",
                    category="security",
                    message="valid",
                    source="semgrep",
                )
            ],
            summary={"High": 1},
            notes=[],
        )
        request = httpx.Request("POST", "https://api.github.com/repos/owner/repo/pulls/1/reviews")
        response = httpx.Response(
            422,
            request=request,
            text=json.dumps({"message": "Validation Failed", "errors": [{"field": "line"}]}),
        )
        mock_post.return_value = response

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            with self.assertRaises(httpx.HTTPStatusError):
                post_review(
                    report,
                    repo="owner/repo",
                    pr_number=1,
                    commit_id="abc123",
                    token="token",
                    dry_run=False,
                    diff_text=DIFF_TEXT,
                )

        logged = stderr.getvalue()
        self.assertIn("GitHub review post failed: HTTP 422", logged)
        self.assertIn("GitHub response body:", logged)
        self.assertIn("Validation Failed", logged)


if __name__ == "__main__":
    unittest.main()
