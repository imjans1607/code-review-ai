"""Request/response shapes for the backend API (the /review contract).

Kept in one place so the API's inputs and outputs are easy to see and version.
"""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReviewRequest(BaseModel):
    """Everything the /review endpoint needs to review one code change.

    In the CI/CD flow (Module 5), GitHub Actions fills this in: it always sends
    the `diff`, and — because Semgrep runs best on real files — it can either send
    the changed file contents in `files` (backend runs Semgrep) or run Semgrep
    itself and send the result in `semgrep_json` (backend just parses it).
    """

    # `model_path` starts with "model_", which pydantic reserves by default; opt
    # out of that protection so the natural field name works without a warning.
    model_config = ConfigDict(protected_namespaces=())

    diff: str = Field(..., description="Unified-diff text of the change under review.")
    files: Optional[Dict[str, str]] = Field(
        None, description="path -> full new file content, for a live Semgrep scan."
    )
    semgrep_json: Optional[dict] = Field(
        None, description="Pre-computed Semgrep --json output (CI can supply this)."
    )
    run_ai: bool = Field(True, description="Run the AI reviewer (Module 2).")
    run_security: bool = Field(True, description="Run the security scan (Module 3).")
    model_path: Optional[str] = Field(
        None, description="Override the AI model location (weights folder or HF id)."
    )
    # Optional PR metadata — recorded with the saved review for the dashboard.
    repo: str = Field("", description="owner/name of the repository under review.")
    pr_number: int = Field(0, description="Pull request number, if any.")
    author: str = Field("", description="Login of the developer who opened the PR.")
    commit_sha: str = Field("", description="Head commit SHA, if any.")
