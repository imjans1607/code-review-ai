"""Module 1 demo runner — collect changed files from a diff and print them.

Usage:
    python run_module1_demo.py                       # uses the bundled sample
    python run_module1_demo.py path/to/change.diff   # your own saved diff

This is just a thin wrapper around app.collector so the demo runs with a clean
command (no package-execution warnings) during the walkthrough.
"""

import json
import sys
from dataclasses import asdict

from app.collector import collect_from_diff_file


def main() -> None:
    diff_path = sys.argv[1] if len(sys.argv) > 1 else "examples/sample_change.diff"
    # supported_only=False so we can SEE that "other" languages are labelled
    # (and would be filtered out in the real pipeline).
    files = collect_from_diff_file(diff_path, supported_only=False)

    print(f"Collected {len(files)} changed file(s) from {diff_path}\n")
    for f in files:
        print(f"  - {f.path:<20} [{f.language}]  +{f.added_lines}/-{f.removed_lines}, "
              f"{len(f.hunks)} hunk(s)")
    print("\nStructured output handed to Module 2 / Module 3:\n")
    print(json.dumps([asdict(f) for f in files], indent=2))


if __name__ == "__main__":
    main()
