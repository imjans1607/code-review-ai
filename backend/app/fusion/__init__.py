"""Module 4 — Review Fusion & Prioritization.

Merges Module 2 (AI comments) and Module 3 (security findings) into one
de-duplicated, severity-ranked review report.

Public interface:
  - fuse           : merge security findings + AI comments -> ReviewReport
  - AIComment      : an AI comment tied to a file/line (fusion input)
  - ReviewComment  : one unified comment in the final report
  - ReviewReport   : the merged, ranked result (has .to_dict())
"""

from .fusion import fuse
from .models import AIComment, ReviewComment, ReviewReport
from .scope import restrict_to_added_lines

__all__ = ["fuse", "AIComment", "ReviewComment", "ReviewReport", "restrict_to_added_lines"]
