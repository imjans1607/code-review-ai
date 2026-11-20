"""The PR review must be about the PR: only changed lines, one comment per issue."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.fusion import AIComment, fuse, restrict_to_added_lines
from app.publisher.github import to_inline_comments
from app.security.findings import SecurityFinding

DIFF = """diff --git a/src/a.py b/src/a.py
index 0000000..1111111 100644
--- a/src/a.py
+++ b/src/a.py
@@ -1,3 +1,5 @@
 keep
+added_one
+added_two
 keep2
 keep3
"""


def finding(rule, line, severity="Medium", path="src/a.py", end=None, cwe=("CWE-95",)):
    return SecurityFinding(rule_id=rule, message=f"msg {rule}", severity=severity, path=path,
                           start_line=line, end_line=end or line, cwe=list(cwe))


class ScopeTests(unittest.TestCase):
    def test_keeps_only_findings_on_added_lines(self):
        fs = [finding("r.on_added", 2), finding("r.old_line", 1), finding("r.other_file", 2, path="x/b.py"),
              finding("r.past_end", 40)]
        res = restrict_to_added_lines(fs, DIFF)
        self.assertEqual([f.rule_id for f in res.findings], ["r.on_added"])
        self.assertEqual(res.dropped, 3)
        self.assertTrue(res.scoped)

    def test_multiline_finding_is_anchored_inside_the_diff(self):
        res = restrict_to_added_lines([finding("r.span", 1, end=3)], DIFF)
        self.assertEqual(len(res.findings), 1)
        self.assertEqual(res.findings[0].start_line, 2)   # first added line in the span

    def test_path_spelling_is_normalised(self):
        res = restrict_to_added_lines([finding("r.dot", 3, path="./src\\a.py")], DIFF)
        self.assertEqual(len(res.findings), 1)

    def test_missing_diff_fails_open(self):
        fs = [finding("r.a", 1), finding("r.b", 2)]
        for empty in ("", "   \n"):
            res = restrict_to_added_lines(fs, empty)
            self.assertEqual(len(res.findings), 2)
            self.assertFalse(res.scoped)
            self.assertEqual(res.dropped, 0)


class CollapseTests(unittest.TestCase):
    def test_overlapping_rules_on_one_line_become_one_comment(self):
        fs = [finding("a.eval-detected", 2, "Medium"),
              finding("b.user-eval", 2, "High"),
              finding("c.user-eval", 2, "Medium"),
              finding("d.sqli", 3, "High", cwe=("CWE-89",))]
        report = fuse(fs, [])
        self.assertEqual(len(report.comments), 2)
        by_line = {c.line: c for c in report.comments}
        self.assertEqual(by_line[2].severity, "High")             # most severe kept
        self.assertEqual(by_line[2].rule_id, "b.user-eval")
        self.assertIn("Also flagged by 2 other rule(s)", by_line[2].rationale)
        self.assertIn("eval-detected", by_line[2].rationale)      # nothing silently lost
        self.assertEqual(report.summary, {"High": 2})

    def test_ties_keep_the_first_finding(self):
        report = fuse([finding("first.x", 2), finding("second.y", 2)], [])
        self.assertEqual([c.rule_id for c in report.comments], ["first.x"])

    def test_same_rule_twice_is_not_listed_as_other(self):
        report = fuse([finding("r.same", 2), finding("r.same", 2)], [])
        self.assertEqual(len(report.comments), 1)
        self.assertNotIn("'same'", report.comments[0].rationale)

    def test_different_lines_and_files_are_kept_separate(self):
        fs = [finding("r.a", 2), finding("r.a", 3), finding("r.a", 2, path="src/b.py")]
        self.assertEqual(len(fuse(fs, []).comments), 3)

    def test_security_still_supersedes_style_on_the_same_line(self):
        report = fuse([finding("r.a", 2)], [AIComment("src/a.py", 2, "nit"), AIComment("src/a.py", 3, "other nit")])
        self.assertEqual(sorted((c.category, c.line) for c in report.comments),
                         [("security", 2), ("style", 3)])


class EndToEndTests(unittest.TestCase):
    def test_posted_inline_comments_match_the_pr(self):
        fs = [finding("a.eval-detected", 2), finding("b.user-eval", 2, "High"),
              finding("old.issue", 1), finding("elsewhere.issue", 9, path="docs/x.py")]
        scoped = restrict_to_added_lines(fs, DIFF).findings
        inline = to_inline_comments(fuse(scoped, []), diff_text=DIFF)
        self.assertEqual([(c["path"], c["line"]) for c in inline], [("src/a.py", 2)])


if __name__ == "__main__":
    unittest.main()
