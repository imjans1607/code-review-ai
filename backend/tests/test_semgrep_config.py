from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.security import evaluation as ev
from app.security.findings import normalize_severity
from app.security.semgrep_scanner import (
    BASELINE_CONFIGS,
    DEFAULT_CONFIGS,
    EXTRA_PACKS,
    EXTRA_RULES,
    RULES_DIR,
)

try:
    import yaml
except ImportError:  # PyYAML ships with Semgrep but is not a backend dependency
    yaml = None

REPO = Path(__file__).resolve().parents[2]
EVAL = REPO / "docs" / "evaluation" / "semgrep"
DEV = REPO / "backend" / "eval" / "semgrep_suite"
HOLDOUT = REPO / "backend" / "eval" / "semgrep_holdout"


def _semgrep_configs(yaml_path: Path) -> list:
    """The `--config` values of the `semgrep ...` command in a workflow/action file."""
    text = yaml_path.read_text(encoding="utf-8")
    start = text.index("semgrep --json")
    end = text.index("|| true", start)
    return re.findall(r"--config\s+(\"?[^\s\\]+\"?)", text[start:end])


def _normalised_sha(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


needs_eval = unittest.skipUnless(
    (REPO / "backend" / "eval").is_dir(),
    "the evaluation suites (backend/eval) are not included in the student zip",
)


class ConfigDefinitionTests(unittest.TestCase):
    def test_baseline_is_the_original_four_packs_and_never_changes(self) -> None:
        self.assertEqual(BASELINE_CONFIGS, ("p/python", "p/javascript", "p/owasp-top-ten", "p/secrets"))

    def test_default_configs_extend_the_baseline(self) -> None:
        self.assertEqual(DEFAULT_CONFIGS[: len(BASELINE_CONFIGS)], BASELINE_CONFIGS)
        self.assertEqual(
            DEFAULT_CONFIGS,
            BASELINE_CONFIGS + EXTRA_PACKS + EXTRA_RULES + (str(RULES_DIR),),
        )
        self.assertEqual(len(set(DEFAULT_CONFIGS)), len(DEFAULT_CONFIGS), "duplicate config entries")

    def test_custom_rules_directory_exists_and_has_rules(self) -> None:
        self.assertTrue(RULES_DIR.is_dir())
        self.assertTrue(list(RULES_DIR.glob("*.yml")))

    def test_registry_rules_are_individually_referenced(self) -> None:
        for cfg in EXTRA_RULES:
            self.assertRegex(cfg, r"^r/[a-z]+\.[\w.\-]+$")


class CiConfigSyncTests(unittest.TestCase):
    """The scanner, the workflow and the reusable Action must run the same rules."""

    @staticmethod
    def _expected(rules_value: str) -> list:
        return [c for c in DEFAULT_CONFIGS[:-1]] + [rules_value]

    def test_workflow_matches_default_configs(self) -> None:
        got = _semgrep_configs(REPO / ".github" / "workflows" / "code-review.yml")
        self.assertEqual(got, self._expected("backend/app/security/rules"))

    def test_action_matches_default_configs(self) -> None:
        got = _semgrep_configs(REPO / "action.yml")
        # The Action scans the consumer's repo, so its rules come from the Action's own checkout.
        self.assertEqual(got, self._expected('"$GITHUB_ACTION_PATH/backend/app/security/rules"'))

    def test_custom_rules_are_not_hidden_from_scans_by_semgrepignore_by_accident(self) -> None:
        # Ignoring a path does not stop it loading as a --config, but ignoring the
        # whole rules directory would hide rule-file edits from review scans.
        ignore = (REPO / ".semgrepignore").read_text(encoding="utf-8")
        self.assertNotIn("security/rules", ignore)


@unittest.skipIf(yaml is None, "PyYAML not installed")
class CustomRuleHygieneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = []
        for f in sorted(RULES_DIR.glob("*.yml")):
            self.rules += yaml.safe_load(f.read_text(encoding="utf-8"))["rules"]

    def test_rules_are_namespaced_unique_and_documented(self) -> None:
        ids = [r["id"] for r in self.rules]
        self.assertEqual(len(ids), len(set(ids)))
        for r in self.rules:
            self.assertTrue(r["id"].startswith("codereview."), r["id"])
            self.assertTrue(r["message"].strip(), r["id"])
            self.assertTrue(r["metadata"]["cwe"], f"{r['id']} has no CWE")
            self.assertEqual(r["metadata"]["source"], "codereview-custom")

    def test_low_confidence_rules_never_surface_as_high_or_critical(self) -> None:
        # normalize_severity promotes ERROR+impact HIGH to Critical; these rules are
        # heuristics (a function parameter is not always attacker-controlled).
        for r in self.rules:
            self.assertEqual(r["severity"], "WARNING", r["id"])
            self.assertNotEqual(str(r["metadata"].get("impact", "")).upper(), "HIGH", r["id"])
            self.assertEqual(normalize_severity(r["severity"], r["metadata"]), "Medium", r["id"])


@needs_eval
class HoldoutIntegrityTests(unittest.TestCase):
    """The holdout only means something if it and the config were not edited after scoring."""

    def test_labels_are_in_sync_with_the_case_files(self) -> None:
        cases = ev.parse_cases(HOLDOUT / "cases")
        expected = json.dumps(ev.cases_to_labels(cases), indent=2) + "\n"
        self.assertEqual((HOLDOUT / "labels.json").read_text(encoding="utf-8"), expected)

    def test_holdout_is_distinct_from_the_dev_suite_and_well_formed(self) -> None:
        dev = {c.id for c in ev.parse_cases(DEV / "cases")}
        hold = ev.parse_cases(HOLDOUT / "cases")
        self.assertFalse(dev & {c.id for c in hold}, "case ids overlap the dev suite")
        for cls in ev.CLASSES:
            for vulnerable in (True, False):
                self.assertTrue(any(c.vuln_class == cls and c.vulnerable == vulnerable for c in hold), cls)
        self.assertEqual({c.language for c in hold}, {"python", "javascript"})

    def test_holdout_files_match_the_frozen_hashes(self) -> None:
        design = (HOLDOUT / "DESIGN.md").read_text(encoding="utf-8")
        self.assertIn(_normalised_sha(HOLDOUT / "labels.json"), design,
                      "holdout labels changed after they were frozen")
        h = hashlib.sha256()
        for p in sorted((HOLDOUT / "cases").rglob("*")):
            if p.is_file():
                h.update(p.relative_to(HOLDOUT).as_posix().encode())
                h.update(p.read_text(encoding="utf-8").encode())
        self.assertIn(h.hexdigest(), design, "holdout case files changed after they were frozen")

    def test_config_matches_the_one_frozen_before_the_holdout_was_scored(self) -> None:
        design = (HOLDOUT / "DESIGN.md").read_text(encoding="utf-8")
        self.assertIn(
            ev.config_fingerprint(DEFAULT_CONFIGS), design,
            "The Semgrep config (packs, rules or custom rule files) changed after the holdout "
            "result was recorded. Re-measure on a NEW validation set and record the new "
            "fingerprint; do not just update this value.",
        )


@needs_eval
class CapturedRunsReproduceTests(unittest.TestCase):
    """Every committed run can be re-scored offline from its saved Semgrep output."""

    RUNS = (
        ("dev", "extended-dev"),
        ("holdout", "baseline-holdout"),
        ("holdout", "extended-holdout"),
    )

    def test_each_saved_run_reproduces_its_results(self) -> None:
        suites = {"dev": DEV, "holdout": HOLDOUT}
        for suite, folder in self.RUNS:
            with self.subTest(run=folder):
                raw = json.loads((EVAL / folder / "semgrep_raw.json").read_text(encoding="utf-8"))
                committed = json.loads((EVAL / folder / "results.json").read_text(encoding="utf-8"))
                cases = ev.parse_cases(suites[suite] / "cases")
                files = ev.case_files(suites[suite] / "cases")
                ev.check_complete(raw, files)
                metrics = json.loads(json.dumps(ev.score_semgrep_json(cases, raw, files)))
                self.assertEqual(metrics["counts"], committed["metrics"]["counts"])
                self.assertEqual(metrics["recall"], committed["metrics"]["recall"])
                self.assertEqual(metrics["precision"], committed["metrics"]["precision"])

    def test_extended_run_records_the_configs_it_actually_used(self) -> None:
        info = json.loads((EVAL / "extended-holdout" / "run_info.json").read_text(encoding="utf-8"))
        self.assertEqual(info["configs"], [ev.describe_config(c) for c in DEFAULT_CONFIGS])
        base = json.loads((EVAL / "baseline-holdout" / "run_info.json").read_text(encoding="utf-8"))
        self.assertEqual(base["configs"], list(BASELINE_CONFIGS))

    def test_extended_never_loses_a_detection_the_baseline_had(self) -> None:
        def detected(folder):
            return {d["case"] for d in json.loads(
                (EVAL / folder / "results.json").read_text(encoding="utf-8"))["metrics"]["detected"]}
        self.assertLessEqual(detected("baseline-holdout"), detected("extended-holdout"))


@unittest.skipUnless(
    shutil.which("semgrep") and os.environ.get("RUN_LIVE_SEMGREP_EVAL"),
    "set RUN_LIVE_SEMGREP_EVAL=1 with Semgrep installed",
)
class LiveRuleValidationTests(unittest.TestCase):
    def test_custom_rules_are_valid_semgrep_rules(self) -> None:
        proc = subprocess.run(
            ["semgrep", "--validate", "--config", str(RULES_DIR), "--metrics", "off"],
            capture_output=True, text=True, env=dict(os.environ, PYTHONUTF8="1"),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
