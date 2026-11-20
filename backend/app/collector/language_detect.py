"""Language identification for a changed file.

The project scope is Python + JavaScript, so we map a file's extension to one of
those two languages (with a few close relatives), and label everything else
"other" so the pipeline can skip it. Extension-based detection is simple,
fast, and reliable for this scope — we do not need to read file contents.
"""

from __future__ import annotations

import os

# Extension -> canonical language name. Kept small and explicit on purpose:
# the project only reviews Python and JavaScript, so anything not listed here
# is treated as "other" and ignored by the review pipeline.
_EXTENSION_MAP = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "javascript",   # TypeScript reviewed under the JS umbrella for this project
    ".tsx": "javascript",
}

SUPPORTED_LANGUAGES = ("python", "javascript")


def detect_language(path: str) -> str:
    """Return 'python', 'javascript', or 'other' for a file path.

    Only the extension is used. The path may be a full path or just a name.
    """
    _, ext = os.path.splitext(path.lower())
    return _EXTENSION_MAP.get(ext, "other")


def is_supported(path: str) -> bool:
    """True if the file is in a language the review pipeline handles."""
    return detect_language(path) in SUPPORTED_LANGUAGES
