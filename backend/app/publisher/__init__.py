"""Module 5 (posting side) — publish a review back to a GitHub PR.

Public interface:
  - post_review             : post the fused report as one PR review
  - format_summary_markdown : the summary comment body
  - to_inline_comments      : per-line inline comment objects
"""

from .github import format_summary_markdown, post_review, to_inline_comments

__all__ = ["post_review", "format_summary_markdown", "to_inline_comments"]
