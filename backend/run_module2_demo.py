"""Module 1 + Module 2 pipeline demo.

Reads a diff (Module 1: collect), then for each changed file generates a review
comment (Module 2: AI review). Run it on a machine/Colab where the fine-tuned
model is available.

Usage:
    # Use the model weights we trained (local folder or a Hugging Face id):
    python run_module2_demo.py --model /path/to/weights/codereviewer-msg-pyjs
    python run_module2_demo.py --model your-username/codereviewer-msg-pyjs

    # Just show the encoded model input without loading the model (no ML libs):
    python run_module2_demo.py --encode-only
"""

import argparse

from app.collector import collect_from_diff_file
from app.reviewer.diff_encoder import format_diff


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", default="examples/sample_change.diff")
    ap.add_argument("--model", default="microsoft/codereviewer",
                    help="Local weights folder or Hugging Face model id.")
    ap.add_argument("--encode-only", action="store_true",
                    help="Show the <add>/<del>/<keep> model input, skip the model.")
    args = ap.parse_args()

    # --- Module 1: collect the changed files (Python/JS only) ---
    files = collect_from_diff_file(args.diff, supported_only=True)
    print(f"Module 1 collected {len(files)} reviewable file(s).\n")

    if args.encode_only:
        for f in files:
            print("=" * 70)
            print(f"FILE: {f.path}  [{f.language}]")
            print("-- model input (encoded diff) --")
            print(format_diff(f.patch))
        print("\n(--encode-only: model not loaded)")
        return

    # --- Module 2: load the model once, then review each file ---
    from app.reviewer import AICodeReviewer  # imported here so --encode-only needs no torch
    print(f"Loading review model: {args.model} ...")
    reviewer = AICodeReviewer(model_path=args.model)

    comments = reviewer.review_batch([f.patch for f in files])
    for f, comment in zip(files, comments):
        print("=" * 70)
        print(f"FILE: {f.path}  [{f.language}]  +{f.added_lines}/-{f.removed_lines}")
        print(f"REVIEW COMMENT: {comment}")


if __name__ == "__main__":
    main()
