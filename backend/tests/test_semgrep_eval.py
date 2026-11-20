from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.security import evaluation as ev
from app.security.findings import SecurityFinding

REPO = Path(__file__).resolve().parents[2]
SUITE = REPO / "backend" / "eval" / "semgrep_suite"
RESULTS = REPO / "docs" / "evaluation" / "semgrep"


def _case(cid, vuln=True, cls="sqli", sinks=(5,), start=3, end=8, file="python/a.py", source="framework"):
    return ev.Case(cid, file, "python", vuln, cls, source, "n", start, end, list(sinks) if vuln else [])


def _f(line, cwe="CWE-89: SQL Injection", path="python/a.py", rule="r.rule", end=None):
    return SecurityFinding(rule_id=rule, message="m", severity="High", path=path,
                           start_line=line, end_line=end or line, cwe=[cwe] if cwe else [])


needs_eval = unittest.skipUnless(
    (REPO / "backend" / "eval").is_dir(),
    "the evaluation suites (backend/eval) are not included in the student zip",
)


class ScoringTests(unittest.TestCase):
    def test_detected_missed_and_safe_counts(self) -> None:
        cases = [
            _case("hit", start=3, end=8, sinks=(5,)),
            _case("miss", start=13, end=18, sinks=(15,)),
            _case("ctrl", vuln=False, start=23, end=28),
        ]
        m = ev.score(cases, [_f(5)])
        c = m["counts"]
        self.assertEqual((c["true_positives"], c["false_negatives"], c["false_positives"]), (1, 1, 0))
        self.assertEqual(m["precision"]["value"], 1.0)
        self.assertEqual(m["recall"]["value"], 0.5)
        self.assertEqual([x["case"] for x in m["missed"]], ["miss"])

    def test_finding_in_a_safe_case_is_a_false_positive(self) -> None:
        cases = [_case("hit"), _case("ctrl", vuln=False, start=23, end=28)]
        m = ev.score(cases, [_f(5), _f(25)])
        self.assertEqual(m["counts"]["false_positives"], 1)
        self.assertEqual(m["false_positive_findings"][0]["where"], "safe_case")
        self.assertEqual(m["precision"]["value"], 0.5)
        self.assertEqual(m["safe_cases_with_false_positives"]["successes"], 1)

    def test_off_sink_and_outside_findings_are_false_positives(self) -> None:
        cases = [_case("hit", start=3, end=8, sinks=(5,))]
        m = ev.score(cases, [_f(5), _f(7), _f(40)])
        where = sorted(r["where"] for r in m["false_positive_findings"])
        self.assertEqual(where, ["outside_cases", "vulnerable_case_off_sink"])

    def test_duplicate_findings_on_one_sink_count_once(self) -> None:
        m = ev.score([_case("hit")], [_f(5), _f(5, rule="r.other")])
        c = m["counts"]
        self.assertEqual((c["true_positives"], c["false_positives"]), (1, 0))
        self.assertEqual(c["duplicate_findings_on_detected_sinks"], 1)

    def test_multiline_finding_overlapping_the_sink_is_a_hit(self) -> None:
        m = ev.score([_case("hit", sinks=(5,))], [_f(4, end=6)])
        self.assertEqual(m["counts"]["true_positives"], 1)

    def test_any_of_several_sink_lines_counts(self) -> None:
        m = ev.score([_case("hit", sinks=(4, 6))], [_f(6)])
        self.assertEqual(m["counts"]["true_positives"], 1)

    def test_class_correctness_is_separate_from_detection(self) -> None:
        cases = [_case("a", cls="sqli", sinks=(5,), start=3, end=8),
                 _case("b", cls="sqli", sinks=(15,), start=13, end=18)]
        m = ev.score(cases, [_f(5, cwe="CWE-89: x"), _f(15, cwe="CWE-704: wrong tag")])
        self.assertEqual(m["counts"]["true_positives"], 2)
        self.assertEqual(m["counts"]["class_correct_detections"], 1)
        self.assertEqual(m["recall_class_correct"]["value"], 0.5)

    def test_target_class_precision_ignores_out_of_class_false_positives(self) -> None:
        cases = [_case("hit")]
        m = ev.score(cases, [_f(5), _f(40, cwe="CWE-327: weak hash"), _f(41, cwe="")])
        self.assertEqual(m["counts"]["false_positives"], 2)
        self.assertEqual(m["precision"]["value"], round(1 / 3, 3))
        self.assertEqual(m["precision_target_classes_only"]["value"], 1.0)

    def test_findings_in_unknown_files_are_ignored_and_paths_normalised(self) -> None:
        m = ev.score([_case("hit")], [_f(5, path=".\\python\\a.py"), _f(5, path="elsewhere/x.py")])
        self.assertEqual(m["counts"]["true_positives"], 1)
        self.assertEqual(m["counts"]["findings_in_suite_files"], 1)

    def test_recall_breakdown_by_source_and_class(self) -> None:
        cases = [_case("a", source="framework", start=3, end=8, sinks=(5,)),
                 _case("b", source="bare_param", start=13, end=18, sinks=(15,), cls="eval")]
        m = ev.score(cases, [_f(5)])
        self.assertEqual(m["recall_by_source"]["framework"]["value"], 1.0)
        self.assertEqual(m["recall_by_source"]["bare_param"]["value"], 0.0)
        self.assertEqual(m["by_class"]["eval"]["recall"]["successes"], 0)

    def test_no_findings_gives_zero_recall_and_undefined_precision(self) -> None:
        m = ev.score([_case("hit")], [])
        self.assertEqual(m["recall"]["value"], 0.0)
        self.assertIsNone(m["precision"]["value"])
        self.assertFalse(m["targets"]["recall_met"])
        self.assertIsNone(m["targets"]["precision_met"])

    def test_wilson_interval(self) -> None:
        self.assertIsNone(ev.wilson(0, 0))
        lo, hi = ev.wilson(5, 10)
        self.assertAlmostEqual(lo, 0.237, places=2)
        self.assertAlmostEqual(hi, 0.763, places=2)
        self.assertEqual(ev.wilson(10, 10)[1], 1.0)

    def test_cwe_mapping(self) -> None:
        self.assertEqual(ev.class_of(["CWE-89: SQL"]), "sqli")
        self.assertEqual(ev.class_of(["CWE-73: External Control of File Name"]), "path_traversal")
        self.assertEqual(ev.class_of(["CWE-704: Incorrect Type Conversion"]), None)
        self.assertEqual(ev.class_of([]), None)


class ParsingTests(unittest.TestCase):
    def _parse(self, text: str, name: str = "x.py"):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / name).write_text(text, encoding="utf-8")
            return ev.parse_cases(Path(tmp))

    def test_parses_ranges_and_sinks(self) -> None:
        cases = self._parse(
            "import os\n"
            "# @case a | vulnerable | eval | bare_param | note\n"
            "def f(x):\n"
            "    return eval(x)  # @sink\n"
            "# @end\n"
            "// not a marker\n"
            "# @case b | safe | eval | literal | n\n"
            "y = 1\n"
            "# @end\n"
        )
        a, b = cases
        self.assertEqual((a.start_line, a.end_line, a.sink_lines), (3, 4, [4]))
        self.assertEqual((b.vulnerable, b.sink_lines, b.start_line, b.end_line), (False, [], 8, 8))

    def test_js_markers(self) -> None:
        cases = self._parse(
            "// @case a | vulnerable | xss | browser_source | n\n"
            "el.innerHTML = location.hash; // @sink\n"
            "// @end\n", "x.js")
        self.assertEqual(cases[0].language, "javascript")
        self.assertEqual(cases[0].sink_lines, [2])

    def test_rejects_bad_labels(self) -> None:
        bad = {
            "no sink": "# @case a | vulnerable | eval | literal | n\nx = 1\n# @end\n",
            "sink on safe": "# @case a | safe | eval | literal | n\nx = 1  # @sink\n# @end\n",
            "unclosed": "# @case a | safe | eval | literal | n\nx = 1\n",
            "stray end": "# @end\n",
            "bad class": "# @case a | safe | nope | literal | n\n# @end\n",
            "bad source": "# @case a | safe | eval | nope | n\n# @end\n",
            "bad kind": "# @case a | risky | eval | literal | n\n# @end\n",
            "nested": "# @case a | safe | eval | literal | n\n# @case b | safe | eval | literal | n\n# @end\n",
            "wrong field count": "# @case a | safe | eval\n# @end\n",
        }
        for name, text in bad.items():
            with self.subTest(name), self.assertRaises(ValueError):
                self._parse(text)

    def test_rejects_duplicate_ids(self) -> None:
        text = "# @case a | safe | eval | literal | n\nx=1\n# @end\n"
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text(text, encoding="utf-8")
            (Path(tmp) / "b.py").write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                ev.parse_cases(Path(tmp))


class CompletenessTests(unittest.TestCase):
    def test_missing_scanned_file_is_an_error_not_a_miss(self) -> None:
        data = {"errors": [], "paths": {"scanned": ["python/a.py"]}}
        ev.check_complete(data, ["python/a.py"])
        with self.assertRaises(RuntimeError):
            ev.check_complete(data, ["python/a.py", "javascript/b.js"])

    def test_semgrep_errors_and_missing_coverage_info_are_errors(self) -> None:
        with self.assertRaises(RuntimeError):
            ev.check_complete({"errors": [{"msg": "x"}], "paths": {"scanned": ["a.py"]}}, ["a.py"])
        with self.assertRaises(RuntimeError):
            ev.check_complete({"errors": [], "paths": {}}, ["a.py"])


@needs_eval
class CommittedSuiteTests(unittest.TestCase):
    """Checks on the real suite and the real captured Semgrep output."""

    def test_labels_json_matches_the_case_files(self) -> None:
        cases = ev.parse_cases(SUITE / "cases")
        expected = json.dumps(ev.cases_to_labels(cases), indent=2) + "\n"
        self.assertEqual((SUITE / "labels.json").read_text(encoding="utf-8"), expected,
                         "labels.json is stale; run: python scripts/eval_semgrep.py --write-labels")

    def test_suite_covers_every_class_with_vulnerable_and_safe_cases(self) -> None:
        cases = ev.parse_cases(SUITE / "cases")
        for cls in ev.CLASSES:
            for vulnerable in (True, False):
                self.assertTrue(
                    any(c.vuln_class == cls and c.vulnerable == vulnerable for c in cases),
                    f"{cls} has no {'vulnerable' if vulnerable else 'safe'} case",
                )
        self.assertEqual({c.language for c in cases}, {"python", "javascript"})

    def test_captured_semgrep_output_reproduces_the_committed_results(self) -> None:
        raw = json.loads((RESULTS / "semgrep_raw.json").read_text(encoding="utf-8"))
        committed = json.loads((RESULTS / "results.json").read_text(encoding="utf-8"))
        cases = ev.parse_cases(SUITE / "cases")
        files = ev.case_files(SUITE / "cases")
        ev.check_complete(raw, files)
        # Round-trip through JSON so tuples compare equal to the stored lists.
        metrics = json.loads(json.dumps(ev.score_semgrep_json(cases, raw, files)))
        self.assertEqual(metrics["counts"], committed["metrics"]["counts"])
        self.assertEqual(metrics["precision"], committed["metrics"]["precision"])
        self.assertEqual(metrics["recall"], committed["metrics"]["recall"])

    def test_suite_is_excluded_from_normal_scans(self) -> None:
        ignore = (REPO / ".semgrepignore").read_text(encoding="utf-8")
        self.assertIn("backend/eval/", ignore)
        self.assertIn("docs/evaluation/", ignore)


@unittest.skipUnless(
    shutil.which("semgrep") and os.environ.get("RUN_LIVE_SEMGREP_EVAL"),
    "set RUN_LIVE_SEMGREP_EVAL=1 with Semgrep installed (needs network for rule packs)",
)
@needs_eval
class LiveSemgrepTests(unittest.TestCase):
    def test_live_run_scans_every_file_and_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw = ev.run_semgrep(SUITE / "cases", Path(tmp) / "raw.json")
        cases = ev.parse_cases(SUITE / "cases")
        m = ev.score_semgrep_json(cases, raw)
        # Rule packs drift over time, so only structure is asserted here, not numbers.
        self.assertEqual(m["counts"]["cases"], len(cases))
        self.assertGreater(m["counts"]["findings_in_suite_files"], 0)


if __name__ == "__main__":
    unittest.main()
