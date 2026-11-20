"""Module 1 — Intelligent Code Collection.

Collects the *changed* source code for review from a code change (a "diff"),
and reports, per file: which language it is and exactly which lines were added,
removed, or kept. The output is the structured input that Module 2 (AI review)
and Module 3 (security scan) consume.

This module is deliberately dependency-free (Python standard library only) and
works **offline** on a saved diff file — it does not call git or GitHub at
runtime — so it is easy to run and explain.
"""

from .collector import ChangedFile, DiffHunk, collect_from_diff_file, collect_from_diff_text
from .language_detect import detect_language

__all__ = [
    "ChangedFile",
    "DiffHunk",
    "collect_from_diff_file",
    "collect_from_diff_text",
    "detect_language",
]
