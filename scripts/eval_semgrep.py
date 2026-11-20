#!/usr/bin/env python3
"""Measure Semgrep precision/recall on the labeled suite and write a report.

Scans a labeled suite with a chosen rule-pack set, scores the findings against
the labels, and writes (to --out-dir):

    semgrep_raw.json   raw Semgrep output (evidence)
    run_info.json      what was actually run: configs, Semgrep version, date
    results.json       metrics + run metadata
    REPORT.md          human-readable results

Suites:        dev (backend/eval/semgrep_suite), holdout (backend/eval/semgrep_holdout)
Config sets:   baseline (the original four packs), extended (the current DEFAULT_CONFIGS)

Usage (from the repo root; Semgrep must be installed):
    python scripts/eval_semgrep.py                                  # dev + baseline
    python scripts/eval_semgrep.py --suite holdout --config-set extended
    python scripts/eval_semgrep.py --from-json <dir>/semgrep_raw.json --out-dir <dir>
    python scripts/eval_semgrep.py --suite holdout --write-labels   # refresh labels.json only

Default output directory: docs/evaluation/semgrep for dev+baseline (the committed
baseline report), otherwise docs/evaluation/semgrep/<config-set>-<suite>/.

`--from-json` re-scores a saved Semgrep run without needing Semgrep (used to
re-check the numbers offline). Semgrep's registry rule packs change over time, so
the raw JSON and Semgrep version are saved with every result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.security import evaluation as ev                    # noqa: E402
from app.security.semgrep_scanner import BASELINE_CONFIGS, DEFAULT_CONFIGS  # noqa: E402

SUITES = {
    "dev": REPO_ROOT / "backend" / "eval" / "semgrep_suite",
    "holdout": REPO_ROOT / "backend" / "eval" / "semgrep_holdout",
}
CONFIG_SETS = {"baseline": BASELINE_CONFIGS, "extended": DEFAULT_CONFIGS}
EVAL_ROOT = REPO_ROOT / "docs" / "evaluation" / "semgrep"


def _pct(rate: Optional[dict]) -> str:
    if not rate or rate["value"] is None:
        return "n/a"
    lo, hi = rate["ci95"]
    return f"{rate['value'] * 100:.1f}% ({rate['successes']}/{rate['n']}; 95% CI {lo * 100:.0f}–{hi * 100:.0f}%)"


def _meta(run_info: dict, labels_text: str) -> dict:
    """Report metadata. Configs/version/date come from what was actually run
    (run_info.json), never from the current defaults, so re-scoring a saved run
    after the defaults change still reports the right configuration."""
    return {
        "date_utc": run_info["date_utc"],
        "semgrep_version": run_info["semgrep_version"],
        "configs": run_info["configs"],
        "config_set": run_info.get("config_set", "?"),
        "suite": run_info.get("suite", "?"),
        "labels_sha256": hashlib.sha256(labels_text.encode("utf-8")).hexdigest(),
        "platform": run_info.get("platform", platform.platform()),
    }


def render_report(meta: dict, m: dict, amendments: Optional[list] = None,
                  initial: Optional[dict] = None) -> str:
    c = m["counts"]
    t = m["targets"]
    met = lambda v: "met" if v else "**not met**"      # noqa: E731
    out = [
        "# Semgrep precision / recall — measured results",
        "",
        f"Run on {meta['date_utc']} with Semgrep {meta['semgrep_version']} on {meta['platform']}.",
        f"Suite: `{meta['suite']}`. Config set: `{meta['config_set']}`"
        + (" (the product's shipped config as of 2026-11-18)." if meta['config_set'] == 'baseline' else "."),
        f"Rule sources: `{'`, `'.join(meta['configs'])}`.",
        f"Current `labels.json` sha256 `{meta['labels_sha256'][:16]}…`.",
        "",
        "## Headline",
        "",
        "| Metric | Target | Measured | Result |",
        "|---|---|---|---|",
        f"| Precision | > {t['precision'] * 100:.0f}% | {_pct(m['precision'])} | {met(t['precision_met'])} |",
        f"| Recall | > {t['recall'] * 100:.0f}% | {_pct(m['recall'])} | {met(t['recall_met'])} |",
        "",
        f"* Precision counting only findings in the five target classes: {_pct(m['precision_target_classes_only'])}.",
        f"* Recall requiring the *right* class (CWE) as well: {_pct(m['recall_class_correct'])}.",
        f"* Safe (fixed) cases that still got a finding: {_pct(m['safe_cases_with_false_positives'])}.",
        "",
        f"Raw counts: {c['vulnerable_cases']} vulnerable cases ({c['true_positives']} detected, "
        f"{c['false_negatives']} missed), {c['safe_cases']} safe cases, "
        f"{c['false_positives']} false-positive findings "
        f"({c['false_positives_in_target_classes']} in the target classes), "
        f"{c['duplicate_findings_on_detected_sinks']} duplicate findings on already-detected sinks.",
        "",
        *_amendment_lines(amendments, initial),
        "## Recall by vulnerability class",
        "",
        "| Class | Recall | False-positive findings |",
        "|---|---|---|",
    ]
    for cls, v in m["by_class"].items():
        out.append(f"| {cls} | {_pct(v['recall'])} | {v['false_positives']} |")
    out += ["", "## Recall by how the untrusted value arrives", "",
            "Most Semgrep security rules are taint rules that need a recognisable source "
            "(e.g. `request.args`). `bare_param` cases pass the value as a plain function "
            "argument, which is common in real code but gives such rules nothing to start from.",
            "", "| Source | Recall |", "|---|---|"]
    for k, v in m["recall_by_source"].items():
        out.append(f"| {k} | {_pct(v)} |")
    out += ["", "## Recall by language", "", "| Language | Recall |", "|---|---|"]
    for k, v in m["recall_by_language"].items():
        out.append(f"| {k} | {_pct(v)} |")

    out += ["", "## Missed vulnerabilities (false negatives)", ""]
    if m["missed"]:
        out += ["| Case | Class | Source | What it is |", "|---|---|---|---|"]
        out += [f"| `{x['case']}` | {x['class']} | {x['source']} | {x['note']} |" for x in m["missed"]]
    else:
        out.append("None.")

    out += ["", "## Detected", ""]
    if m["detected"]:
        out += ["| Case | Rule(s) | Right class? |", "|---|---|---|"]
        out += [f"| `{x['case']}` | {', '.join('`' + r.split('.')[-1] + '`' for r in x['rules'])} | "
                f"{'yes' if x['class_correct'] else 'no'} |" for x in m["detected"]]
    else:
        out.append("None.")

    out += ["", "## False-positive findings", ""]
    if m["false_positive_findings"]:
        out += ["| Where | Case | Line | Rule | Class |", "|---|---|---|---|---|"]
        for r in m["false_positive_findings"]:
            out.append(f"| {r['where']} | `{r['case'] or '-'}` | {r['file']}:{r['start_line']} | "
                       f"`{r['rule_id'].split('.')[-1]}` | {r['class'] or 'other'} |")
    else:
        out.append("None.")

    out += [
        "", "## How to read this", "",
        "* The suite is small, so each number comes with a 95% Wilson interval; "
        "one case moves a percentage by several points.",
        "* Cases were written and labeled **before** the first scored run and were not "
        "adjusted to the output. See `backend/app/security/evaluation.py` for the exact "
        "scoring rules.",
        "* This measures the rule set named at the top. A config that was tuned while "
        "looking at this same suite gives an optimistic result; only a suite the config "
        "was never tuned against is a fair estimate.",
        "* Semgrep registry packs change over time; `semgrep_raw.json` is the exact output "
        "these numbers come from.",
        "",
    ]
    return "\n".join(out)


def _amendment_lines(amendments: Optional[list], initial: Optional[dict]) -> list:
    if not amendments:
        return []
    out = ["## Label amendments", "",
           "Labels were frozen before the first scored run. They were amended once afterwards; "
           "everything is disclosed here.", ""]
    for a in amendments:
        out += [f"**{a['id']}** (labels before: sha256 `{a['labels_sha256_before'][:16]}…`) — {a['reason']}", ""]
    if initial:
        im = initial["metrics"]
        out += ["| | Precision | Recall |", "|---|---|---|",
                f"| As first scored (original labels) | {_pct(im['precision'])} | {_pct(im['recall'])} |",
                "| After amendment (current) | see Headline | see Headline |", ""]
    return out


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Semgrep precision/recall on a labeled suite.")
    ap.add_argument("--suite", choices=sorted(SUITES), default="dev")
    ap.add_argument("--config-set", choices=sorted(CONFIG_SETS), default="baseline")
    ap.add_argument("--out-dir", help="Output directory (default depends on suite and config set).")
    ap.add_argument("--from-json", help="Re-score a saved Semgrep JSON instead of running Semgrep.")
    ap.add_argument("--write-labels", action="store_true", help="Write the suite's labels.json and exit.")
    ap.add_argument("--semgrep-cmd", default="semgrep")
    args = ap.parse_args(argv)

    suite = SUITES[args.suite]
    cases_root = suite / "cases"
    labels_path = suite / "labels.json"
    amendments_path = suite / "AMENDMENTS.json"
    if args.out_dir:
        out_dir = Path(args.out_dir)
    elif (args.suite, args.config_set) == ("dev", "baseline"):
        out_dir = EVAL_ROOT                      # the committed baseline report
    else:
        out_dir = EVAL_ROOT / f"{args.config_set}-{args.suite}"

    cases = ev.parse_cases(cases_root)
    labels_text = json.dumps(ev.cases_to_labels(cases), indent=2) + "\n"
    if args.write_labels:
        labels_path.write_text(labels_text, encoding="utf-8")
        print(f"Wrote {labels_path} ({len(cases)} cases).")
        return 0
    if not labels_path.exists() or labels_path.read_text(encoding="utf-8") != labels_text:
        print("labels.json is missing or out of date; run with --write-labels first.",
              file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    files = ev.case_files(cases_root)
    run_info_path = out_dir / "run_info.json"
    if args.from_json:
        raw_path = Path(args.from_json)
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        ev.check_complete(raw, files)
        info_path = raw_path.parent / "run_info.json"
        if not info_path.exists():
            print(f"{info_path} is missing: it records which configs produced this run.",
                  file=sys.stderr)
            return 2
        run_info = json.loads(info_path.read_text(encoding="utf-8"))
    else:
        configs = CONFIG_SETS[args.config_set]
        started = datetime.now(timezone.utc)
        raw = ev.run_semgrep(cases_root, out_dir / "semgrep_raw.json",
                             configs=configs, semgrep_cmd=args.semgrep_cmd)
        run_info = {
            "date_utc": started.isoformat(timespec="seconds"),
            "semgrep_version": raw.get("version"),
            "configs": [ev.describe_config(c) for c in configs],
            "config_set": args.config_set,
            "suite": args.suite,
            "platform": platform.platform(),
            "scan_seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
        }
        run_info_path.write_text(json.dumps(run_info, indent=2) + "\n", encoding="utf-8")

    metrics = ev.score_semgrep_json(cases, raw, files)
    meta = _meta(run_info, labels_text)
    (out_dir / "results.json").write_text(
        json.dumps({"meta": meta, "metrics": metrics}, indent=2) + "\n", encoding="utf-8")
    amendments = json.loads(amendments_path.read_text(encoding="utf-8")) if amendments_path.exists() else None
    initial_path = out_dir / "results_initial.json"
    initial = json.loads(initial_path.read_text(encoding="utf-8")) if initial_path.exists() else None
    report = render_report(meta, metrics, amendments, initial)
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
