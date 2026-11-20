"""Encode a raw diff into the marker format the review model expects.

The model was trained to read a diff where every line is prefixed with an
explicit edit tag instead of the usual +/-/space:

    +new line     ->  <add> new line
    -old line     ->  <del> old line
     kept line    ->  <keep> kept line

Why: a plain +/- diff hides the *structure* of the change from the model.
By giving each line an explicit <add>/<del>/<keep> token, the model clearly
sees what was added, removed, or left alone — which is exactly what a human
reviewer looks at. Training and inference MUST use the same encoding, so this
function is the single source of truth for both.
"""

from __future__ import annotations


def format_diff(patch: str) -> str:
    """Convert a +/-/space patch body into <add>/<del>/<keep> marker lines."""
    lines = []
    for ln in str(patch).splitlines():
        # Skip hunk headers ("@@ ... @@") and blank separators — they carry no
        # reviewable content and were dropped during training too.
        if ln.startswith("@@") or ln == "":
            continue
        if ln.startswith("+"):
            tag, body = "<add>", ln[1:]
        elif ln.startswith("-"):
            tag, body = "<del>", ln[1:]
        else:
            # A leading space means "context"; some tools omit it, so strip at
            # most one space and treat the rest as a kept line.
            tag, body = "<keep>", (ln[1:] if ln.startswith(" ") else ln)
        lines.append(f"{tag} {body}")
    return "\n".join(lines)
