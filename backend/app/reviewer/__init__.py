"""Module 2 — AI Code Review (inference side).

Loads the fine-tuned review model and turns a code change (a diff) into a
natural-language reviewer comment. This is the *use* side of Module 2; the
*training* side lives in the Colab notebooks (`ml/notebooks/`).

The two files here mirror how the model was trained, so inference sees the
exact same input format as training:
  - diff_encoder.py : encodes a raw diff with <add>/<del>/<keep> markers
  - reviewer.py     : loads the model and generates the comment
"""

from .diff_encoder import format_diff
from .reviewer import AICodeReviewer

__all__ = ["format_diff", "AICodeReviewer"]
