"""Module 3 — Security Vulnerability Detection (Semgrep wrapper).

Semgrep is an open-source static-analysis engine with hundreds of security
rules (OWASP Top 10, language-specific packs, secret detection). *Semgrep* does
the actual detection; this module's job is to **drive** it and turn its raw JSON
output into the clean `SecurityFinding` objects the fusion engine (Module 4)
consumes — with a normalized severity, CWE, and line number per issue.

Two ways to run it, mirroring Module 1:
  - `scan_paths(...)`         → run Semgrep live on real files (needs Semgrep).
  - `load_findings_from_file` → parse a saved Semgrep JSON, so the module can be
                                run and explained offline without Semgrep.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence

from .findings import SecurityFinding, normalize_severity

# The four packs the product shipped with up to 2026-11-18. Kept unchanged so the
# baseline measurement in docs/evaluation/semgrep/ stays reproducible.
BASELINE_CONFIGS = ("p/python", "p/javascript", "p/owasp-top-ten", "p/secrets")

# Registry packs added on top of the baseline. Each was kept only because it found
# vulnerabilities the baseline missed on the dev evaluation suite without adding
# false positives there (see docs/evaluation/semgrep/extended-*/).
EXTRA_PACKS = ("p/security-audit", "p/expressjs", "p/gitleaks")

# Individual registry rules pulled from Semgrep's much noisier `p/default` pack.
# The whole pack added 7 false positives on the dev suite; these specific audit
# rules supplied its extra detections (bare-parameter eval/exec/SQL/XSS cases)
# without them.
EXTRA_RULES = tuple(
    "r/" + rule_id
    for rule_id in (
        "javascript.browser.security.eval-detected.eval-detected",
        "javascript.lang.security.audit.sqli.node-mysql-sqli.node-mysql-sqli",
        "python.lang.security.audit.exec-detected.exec-detected",
        "python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query",
        "python.lang.security.audit.formatted-sql-query.formatted-sql-query",
        "python.flask.security.xss.audit.explicit-unescape-with-markup.explicit-unescape-with-markup",
    )
)

# This project's own rules: taint rules that treat function parameters, and
# browser-controlled values, as untrusted input. The registry packs mostly start
# only from framework sources such as Flask's `request.args`.
RULES_DIR = Path(__file__).resolve().parent / "rules"

# Everything the scanner runs. NOTE: `.github/workflows/code-review.yml` and
# `action.yml` spell the same list out as `--config` flags; a test keeps all three
# in sync, so change them together.
DEFAULT_CONFIGS = BASELINE_CONFIGS + EXTRA_PACKS + EXTRA_RULES + (str(RULES_DIR),)


def semgrep_available() -> bool:
    """True if the Semgrep CLI is installed and on PATH."""
    return shutil.which("semgrep") is not None


def scan_paths(
    paths: Sequence[str],
    configs: Sequence[str] = DEFAULT_CONFIGS,
    timeout: int = 120,
) -> List[SecurityFinding]:
    """Run Semgrep on the given files/directories and return findings.

    In the real pipeline these paths are the files Module 1 flagged as changed
    (already checked out on disk by GitHub Actions). Semgrep scans the actual
    file contents — not the diff — which is how static analysis is meant to work.
    """
    if not paths:
        return []
    if not semgrep_available():
        raise RuntimeError(
            "Semgrep is not installed or not on PATH. Install it (see ml/README "
            "or https://semgrep.dev) or use load_findings_from_file() for an "
            "offline run."
        )

    cmd = ["semgrep", "--json", "--quiet", "--timeout", str(timeout)]
    for cfg in configs:
        cmd += ["--config", cfg]
    cmd += list(paths)

    # Semgrep exits 0 (no findings) or 1 (findings present); both are success and
    # both print JSON to stdout. A different exit code means a real error.
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"Semgrep failed (exit {proc.returncode}): {proc.stderr.strip()}")

    return parse_semgrep_json(json.loads(proc.stdout))


def parse_semgrep_json(data: dict) -> List[SecurityFinding]:
    """Turn Semgrep's JSON into a sorted list of SecurityFinding objects.

    Semgrep's JSON has a top-level "results" list; each result carries the rule
    id, file path, line range, and an "extra" block with the message, severity,
    and metadata (CWE / OWASP / impact). We read exactly those fields.
    """
    findings: List[SecurityFinding] = []
    for result in data.get("results", []):
        extra = result.get("extra", {})
        metadata = extra.get("metadata", {})
        findings.append(
            SecurityFinding(
                rule_id=result.get("check_id", "unknown-rule"),
                message=str(extra.get("message", "")).strip(),
                severity=normalize_severity(extra.get("severity"), metadata),
                path=result.get("path", ""),
                start_line=result.get("start", {}).get("line", 0),
                end_line=result.get("end", {}).get("line", 0),
                cwe=_as_str_list(metadata.get("cwe")),
                owasp=_as_str_list(metadata.get("owasp")),
                snippet=str(extra.get("lines", "")).strip(),
            )
        )

    # Rank most-severe first; ties broken by file then line for a stable order.
    findings.sort(key=lambda f: (f.severity_rank(), f.path, f.start_line))
    return findings


def load_findings_from_file(path: str) -> List[SecurityFinding]:
    """Parse findings from a saved Semgrep `--json` output file (offline)."""
    with open(path, encoding="utf-8") as fh:
        return parse_semgrep_json(json.load(fh))


def _as_str_list(value) -> List[str]:
    """Normalize a metadata field that may be missing, a string, or a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _demo(json_path: str) -> None:
    """Print parsed findings from a saved Semgrep JSON — for the CLI / teaching."""
    findings = load_findings_from_file(json_path)
    print(f"Parsed {len(findings)} security finding(s) from {json_path}\n")
    for f in findings:
        cwe = f.cwe[0] if f.cwe else "-"
        print(f"[{f.severity:<13}] {f.path}:{f.start_line}  {cwe}")
        print(f"                rule: {f.rule_id}")
        print(f"                {f.message}\n")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "examples/semgrep_sample_output.json"
    _demo(target)
