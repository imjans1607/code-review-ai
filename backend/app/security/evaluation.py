"""Measure Semgrep's precision and recall on a labeled test suite (Module 3).

The suite lives in `backend/eval/semgrep_suite/cases/`. Each *case* is a small
piece of code delimited by marker comments:

    # @case <id> | vulnerable|safe | <class> | <source> | <note>
    ...code...
    cur.execute("..." + name)  # @sink        (vulnerable cases only)
    # @end

* `vulnerable` cases contain a real vulnerability; the line(s) tagged `@sink` are
  where a correct finding must land.
* `safe` cases are the fixed/benign counterparts. Any finding inside one is a
  false positive. They are what makes precision meaningful.
* `<class>` is one of sqli / xss / secret / path_traversal / eval.
* `<source>` says how the untrusted value arrives (see SOURCES) so recall can be
  reported for framework-sourced and bare-parameter code separately — most
  Semgrep security rules are taint rules that need a recognizable source.

Scoring rules (fixed before the first scored run)
-------------------------------------------------
* A vulnerable case is **detected** (true positive) when at least one finding in
  its file overlaps a `@sink` line. Extra findings on the same sink are counted
  as duplicates, not as extra true positives and not as false positives.
* A vulnerable case with no overlapping finding is a **false negative**.
* Every finding that does *not* overlap a vulnerable sink is a **false
  positive**: inside a safe case, on a non-sink line of a vulnerable case, or
  outside every case.
* precision = TP / (TP + FP), recall = TP / (TP + FN). Precision is also given
  restricted to findings whose CWE is one of the five target classes.
* "Class-correct" additionally requires a hit's CWE to be the case's class.
* 95% Wilson intervals are included: the suite is small, so one case moves a
  number a lot.

The functions here are pure (no Semgrep, no I/O besides reading case files) so
they can be tested offline against a captured Semgrep JSON; `run_semgrep` is the
only part that needs Semgrep installed.
"""

from __future__ import annotations

import json
import math
import os
import hashlib
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .semgrep_scanner import DEFAULT_CONFIGS, parse_semgrep_json

CLASSES = ("sqli", "xss", "secret", "path_traversal", "eval")
SOURCES = ("framework", "bare_param", "browser_source", "literal")

# CWE numbers that count as each target class.
CLASS_CWES: Dict[str, frozenset] = {
    "sqli": frozenset({89}),
    "xss": frozenset({79}),
    "secret": frozenset({798, 259, 321}),
    "path_traversal": frozenset({22, 23, 36, 73}),
    "eval": frozenset({94, 95}),
}

REPO_ROOT = Path(__file__).resolve().parents[3]

TARGET_PRECISION = 0.90
TARGET_RECALL = 0.85

_CASE_RE = re.compile(r"^\s*(?:#|//)\s*@case\s+(.+?)\s*$")
_END_RE = re.compile(r"^\s*(?:#|//)\s*@end\s*$")
_SINK_RE = re.compile(r"(?:#|//)\s*@sink\s*$")
_CWE_NUM_RE = re.compile(r"CWE-(\d+)", re.IGNORECASE)
_LANG_BY_EXT = {".py": "python", ".js": "javascript", ".jsx": "javascript"}


@dataclass
class Case:
    id: str
    file: str               # posix path relative to the cases root
    language: str
    vulnerable: bool
    vuln_class: str
    source: str
    note: str
    start_line: int         # first code line of the case (markers excluded)
    end_line: int           # last code line of the case
    sink_lines: List[int] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Labels: parsed from the marker comments in the case files
# --------------------------------------------------------------------------- #

def parse_cases(cases_root: Path) -> List[Case]:
    """Read every case file under `cases_root` and return its labeled cases."""
    cases_root = Path(cases_root)
    cases: List[Case] = []
    for path in sorted(p for p in cases_root.rglob("*") if p.suffix in _LANG_BY_EXT):
        rel = path.relative_to(cases_root).as_posix()
        current: Optional[Case] = None
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = _CASE_RE.match(line)
            if m:
                if current is not None:
                    raise ValueError(f"{rel}:{lineno}: @case inside case {current.id!r}")
                current = _new_case(m.group(1), rel, path.suffix, lineno, lineno + 1)
                continue
            if _END_RE.match(line):
                if current is None:
                    raise ValueError(f"{rel}:{lineno}: @end without @case")
                current.end_line = lineno - 1
                _validate(current, rel)
                cases.append(current)
                current = None
                continue
            if current is not None and _SINK_RE.search(line):
                current.sink_lines.append(lineno)
        if current is not None:
            raise ValueError(f"{rel}: case {current.id!r} is never closed with @end")

    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids: " + ", ".join(sorted({i for i in ids if ids.count(i) > 1})))
    return cases


def _new_case(spec: str, rel: str, suffix: str, lineno: int, start: int) -> Case:
    parts = [p.strip() for p in spec.split("|")]
    if len(parts) != 5:
        raise ValueError(f"{rel}:{lineno}: expected 'id | vulnerable|safe | class | source | note'")
    cid, kind, vclass, source, note = parts
    if kind not in ("vulnerable", "safe"):
        raise ValueError(f"{rel}:{lineno}: kind must be vulnerable or safe, got {kind!r}")
    if vclass not in CLASSES:
        raise ValueError(f"{rel}:{lineno}: unknown class {vclass!r}")
    if source not in SOURCES:
        raise ValueError(f"{rel}:{lineno}: unknown source {source!r}")
    return Case(cid, rel, _LANG_BY_EXT[suffix], kind == "vulnerable", vclass, source, note, start, start)


def _validate(case: Case, rel: str) -> None:
    if case.vulnerable and not case.sink_lines:
        raise ValueError(f"{rel}: vulnerable case {case.id!r} has no @sink line")
    if not case.vulnerable and case.sink_lines:
        raise ValueError(f"{rel}: safe case {case.id!r} must not have @sink lines")


def cases_to_labels(cases: Sequence[Case]) -> dict:
    """The committed `labels.json` snapshot (human-reviewable ground truth)."""
    return {
        "classes": list(CLASSES),
        "cases": [asdict(c) for c in cases],
    }


def case_files(cases_root: Path) -> List[str]:
    """Every source file in the suite, relative to `cases_root` (posix)."""
    root = Path(cases_root)
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.suffix in _LANG_BY_EXT)


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #

def cwe_numbers(cwe_strings: Iterable[str]) -> List[int]:
    nums = []
    for s in cwe_strings:
        nums += [int(n) for n in _CWE_NUM_RE.findall(s)]
    return nums


def class_of(cwe_strings: Iterable[str]) -> Optional[str]:
    """Target class a finding's CWE(s) belong to, or None if outside the five."""
    nums = set(cwe_numbers(cwe_strings))
    for cls, cwes in CLASS_CWES.items():
        if nums & cwes:
            return cls
    return None


def wilson(successes: int, n: int, z: float = 1.96) -> Optional[Tuple[float, float]]:
    """95% Wilson score interval for a proportion; None when n == 0."""
    if n == 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3))


def _rate(successes: int, n: int) -> dict:
    return {
        "value": round(successes / n, 3) if n else None,
        "successes": successes,
        "n": n,
        "ci95": wilson(successes, n),
    }


def _norm(path: str) -> str:
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def _resolve(path: str, files: Sequence[str]) -> Optional[str]:
    """Map a path as Semgrep printed it onto a suite file key."""
    p = _norm(path)
    for f in files:
        if p == f or p.endswith("/" + f):
            return f
    return None


def _overlaps(start: int, end: int, lo: int, hi: int) -> bool:
    return start <= hi and end >= lo


def score(cases: Sequence[Case], findings: Sequence, files: Optional[Sequence[str]] = None) -> dict:
    """Score `findings` (SecurityFinding objects) against the labeled `cases`."""
    files = list(files) if files is not None else sorted({c.file for c in cases})
    by_file: Dict[str, List[Case]] = defaultdict(list)
    for c in cases:
        by_file[c.file].append(c)

    # Attach every finding to a suite file; ignore findings in files we don't own.
    located = []
    for f in findings:
        key = _resolve(f.path, files)
        if key is not None:
            located.append((key, f))

    detail: Dict[str, dict] = {
        c.id: {"hits": [], "class_correct": False, "fps": []} for c in cases
    }
    fp_findings: List[dict] = []
    duplicates = 0

    for key, f in located:
        start, end = f.start_line, f.end_line or f.start_line
        fclass = class_of(f.cwe)
        on_sink = None
        for c in by_file[key]:
            if c.vulnerable and any(_overlaps(start, end, s, s) for s in c.sink_lines):
                on_sink = c
                break
        if on_sink is not None:
            d = detail[on_sink.id]
            if d["hits"]:
                duplicates += 1
            d["hits"].append(f.rule_id)
            if fclass == on_sink.vuln_class:
                d["class_correct"] = True
            continue

        # Not on a vulnerable sink => false positive. Say where it landed.
        where = "outside_cases"
        case_id = None
        for c in by_file[key]:
            if _overlaps(start, end, c.start_line, c.end_line):
                case_id = c.id
                where = "safe_case" if not c.vulnerable else "vulnerable_case_off_sink"
                break
        rec = {
            "file": key, "start_line": start, "end_line": end, "rule_id": f.rule_id,
            "class": fclass, "cwe": list(f.cwe), "where": where, "case": case_id,
        }
        fp_findings.append(rec)
        if case_id and not _is_vulnerable(cases, case_id):
            detail[case_id]["fps"].append(f.rule_id)

    vulnerable = [c for c in cases if c.vulnerable]
    detected = [c for c in vulnerable if detail[c.id]["hits"]]
    tp, fn, fp = len(detected), len(vulnerable) - len(detected), len(fp_findings)
    fp_in_scope = sum(1 for r in fp_findings if r["class"] is not None)
    class_correct = sum(1 for c in vulnerable if detail[c.id]["class_correct"])

    def recall_by(keyfn) -> Dict[str, dict]:
        groups: Dict[str, List[Case]] = defaultdict(list)
        for c in vulnerable:
            groups[keyfn(c)].append(c)
        return {k: _rate(sum(1 for c in v if detail[c.id]["hits"]), len(v)) for k, v in sorted(groups.items())}

    safe = [c for c in cases if not c.vulnerable]
    safe_with_fp = [c for c in safe if detail[c.id]["fps"]]
    fp_by_class: Dict[str, int] = defaultdict(int)
    for r in fp_findings:
        fp_by_class[r["class"] or "other"] += 1

    return {
        "counts": {
            "cases": len(cases), "vulnerable_cases": len(vulnerable), "safe_cases": len(safe),
            "true_positives": tp, "false_negatives": fn, "false_positives": fp,
            "false_positives_in_target_classes": fp_in_scope,
            "duplicate_findings_on_detected_sinks": duplicates,
            "class_correct_detections": class_correct,
            "findings_in_suite_files": len(located),
        },
        "precision": _rate(tp, tp + fp),
        "precision_target_classes_only": _rate(tp, tp + fp_in_scope),
        "recall": _rate(tp, tp + fn),
        "recall_class_correct": _rate(class_correct, len(vulnerable)),
        "safe_cases_with_false_positives": _rate(len(safe_with_fp), len(safe)),
        "by_class": {
            cls: {
                "recall": recall_by(lambda c: c.vuln_class).get(cls),
                "false_positives": fp_by_class.get(cls, 0),
            }
            for cls in CLASSES
        },
        "recall_by_language": recall_by(lambda c: c.language),
        "recall_by_source": recall_by(lambda c: c.source),
        "targets": {
            "precision": TARGET_PRECISION, "recall": TARGET_RECALL,
            "precision_met": (tp / (tp + fp) > TARGET_PRECISION) if (tp + fp) else None,
            "recall_met": (tp / (tp + fn) > TARGET_RECALL) if (tp + fn) else None,
        },
        "missed": [
            {"case": c.id, "class": c.vuln_class, "source": c.source, "language": c.language, "note": c.note}
            for c in vulnerable if not detail[c.id]["hits"]
        ],
        "detected": [
            {"case": c.id, "rules": sorted(set(detail[c.id]["hits"])),
             "class_correct": detail[c.id]["class_correct"]}
            for c in detected
        ],
        "false_positive_findings": fp_findings,
    }


def _is_vulnerable(cases: Sequence[Case], case_id: str) -> bool:
    return any(c.id == case_id and c.vulnerable for c in cases)


# --------------------------------------------------------------------------- #
# Config description and fingerprint
# --------------------------------------------------------------------------- #

def describe_config(cfg: str) -> str:
    """A repo-relative, machine-independent name for a `--config` value."""
    p = Path(cfg)
    if p.is_absolute():
        try:
            return p.relative_to(REPO_ROOT).as_posix() + "/"
        except ValueError:
            return p.name
    return cfg


def config_fingerprint(configs: Sequence[str]) -> str:
    """sha256 over the described config list plus the bytes of every local rule file.

    Changes whenever a pack/rule is added or removed or a custom rule is edited, so
    it can pin "the config that was validated" (see semgrep_holdout/DESIGN.md).
    """
    h = hashlib.sha256()
    h.update(json.dumps([describe_config(c) for c in configs]).encode())
    for c in configs:
        p = Path(c)
        if p.is_absolute() and p.is_dir():
            for f in sorted(p.glob("*.yml")):
                h.update(f.name.encode())
                h.update(f.read_bytes())
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Running Semgrep on the suite (the only part that needs Semgrep installed)
# --------------------------------------------------------------------------- #

def run_semgrep(
    cases_root: Path,
    out_json: Path,
    configs: Sequence[str] = DEFAULT_CONFIGS,
    semgrep_cmd: str = "semgrep",
    timeout: int = 600,
) -> dict:
    """Scan the suite with `configs` and return the raw Semgrep JSON.

    Uses the same rule packs the product ships with (`DEFAULT_CONFIGS`). Telemetry
    is switched off; that does not change results. Raises if Semgrep reports
    errors or silently skips any suite file, because a skipped file would
    otherwise be miscounted as a missed vulnerability.
    """
    cases_root = Path(cases_root)
    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    cmd = [semgrep_cmd, "--json", "--quiet", "--metrics", "off", "--no-git-ignore"]
    for cfg in configs:
        cmd += ["--config", cfg]
    cmd += ["--output", str(out_json.resolve()), "."]
    env = dict(os.environ, SEMGREP_SEND_METRICS="off", PYTHONUTF8="1")
    # Scan a copy outside the repository. Inside it, Semgrep applies the repo's
    # .semgrepignore (which hides this deliberately vulnerable suite from normal
    # code-review scans) and would skip every file.
    with tempfile.TemporaryDirectory(prefix="semgrep_suite_") as tmp:
        work = Path(tmp) / "cases"
        shutil.copytree(cases_root, work)
        proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True,
                              env=env, timeout=timeout)
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"Semgrep failed (exit {proc.returncode}): {proc.stderr.strip()[:500]}")
    data = json.loads(out_json.read_text(encoding="utf-8"))
    check_complete(data, case_files(cases_root))
    return data


def check_complete(data: dict, files: Sequence[str]) -> None:
    """Fail loudly if Semgrep errored or did not scan every suite file."""
    errors = data.get("errors") or []
    if errors:
        raise RuntimeError(f"Semgrep reported {len(errors)} error(s): {str(errors[0])[:300]}")
    scanned = [_norm(p) for p in (data.get("paths", {}).get("scanned") or [])]
    if not scanned:
        raise RuntimeError("Semgrep output has no paths.scanned; cannot verify coverage.")
    missing = [f for f in files if not any(s == f or s.endswith("/" + f) for s in scanned)]
    if missing:
        raise RuntimeError("Semgrep did not scan these suite files: " + ", ".join(missing))


def score_semgrep_json(cases: Sequence[Case], data: dict, files: Optional[Sequence[str]] = None) -> dict:
    """Score a (saved or live) Semgrep JSON document against `cases`."""
    return score(cases, parse_semgrep_json(data), files)
