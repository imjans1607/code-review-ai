"""Module 3 — Security Vulnerability Detection.

Runs Semgrep against changed source files and turns its findings into clean,
severity-ranked `SecurityFinding` objects for the fusion engine (Module 4).

Public interface:
  - scan_paths            : run Semgrep live on files/directories
  - load_findings_from_file: parse a saved Semgrep JSON (offline / teaching)
  - parse_semgrep_json    : parse an already-loaded Semgrep JSON dict
  - semgrep_available     : is the Semgrep CLI installed?
  - SecurityFinding       : the structured finding object
  - SEVERITY_ORDER        : the shared severity ladder
"""

from .findings import SEVERITY_ORDER, SecurityFinding, normalize_severity
from .semgrep_scanner import (
    load_findings_from_file,
    parse_semgrep_json,
    scan_paths,
    semgrep_available,
)

__all__ = [
    "SecurityFinding",
    "SEVERITY_ORDER",
    "normalize_severity",
    "scan_paths",
    "parse_semgrep_json",
    "load_findings_from_file",
    "semgrep_available",
]
