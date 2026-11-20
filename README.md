# Automated Code Review AI — with Vulnerability & Style Feedback

An automated pull-request reviewer that fuses two layers of feedback and posts them
inline on GitHub pull requests:

- **AI review layer** — a CodeT5-family model (`microsoft/codereviewer`) fine-tuned on
  the CodeReviewer dataset → style/logic comments **with a rationale**.
- **Security layer** — Semgrep (OWASP Top 10, CWE-mapped rules) → vulnerability findings.
- **Fusion engine** — de-duplicates and severity-ranks the merged findings
  (Critical → Informational).
- **Delivery** — FastAPI backend + GitHub Actions (on PR) → inline PR comments.
- **Dashboard** — React + Tailwind review-history view with severity/author/file filters.
- **Storage** — SQLite out of the box; set `DATABASE_URL` to use PostgreSQL (see HANDOFF.md §2b).

It extends the base paper *"Generating Vulnerability Security Fixes with Code Language
Models"* (Elsevier, *Information and Software Technology*, 2025) — which only *fixes*
vulnerabilities — into a complete, deployable review platform: adding style feedback,
explainable comments, unified quality + security review, CI/CD automation, and analytics.

## The six modules

| # | Module | Where |
|---|---|---|
| 1 | Intelligent Code Collection | `backend/app/collector/` |
| 2 | AI Code Review | `backend/app/reviewer/` |
| 3 | Security Vulnerability Detection (Semgrep) | `backend/app/security/` |
| 4 | Review Fusion & Prioritization | `backend/app/fusion/` |
| 5 | Automated CI/CD Review | `.github/workflows/`, `scripts/`, `backend/app/publisher/` |
| 6 | Analytics Dashboard | `backend/app/storage.py`, `frontend/` |

## Repo layout

```
backend/      FastAPI backend — the review pipeline + REST API
frontend/     React + Tailwind dashboard
scripts/      run_review.py — the CI entrypoint
ml/notebooks/ Colab notebooks — data prep, fine-tuning, evaluation, model publishing
.github/      GitHub Actions workflow (CI/CD)
action.yml    reusable Action so any repo can run the reviewer
docs/         design and report material
```

## Results

- **AI review:** BLEU-4 = **7.26** (official CodeReviewer smoothed-BLEU), above the
  published reference (~5.73). Model published at
  [`Jabez0701/codereviewer-msg-pyjs`](https://huggingface.co/Jabez0701/codereviewer-msg-pyjs).
- **Security (Semgrep):** finds SQL injection, XSS, hard-coded secrets, path traversal, and
  insecure `eval`, each ranked and CWE-tagged, but not all of them. On a held-out test of 67
  cases it found **58%** of the vulnerabilities (target 85%) with **85%** precision (target
  90%). It is strongest on code that takes input from a framework object such as
  `request.args`, and weakest on plain function parameters. Details:
  [docs/evaluation/semgrep/SUMMARY.md](docs/evaluation/semgrep/SUMMARY.md).
- **End-to-end:** live dashboard, and automated reviews posted on pull requests via CI. In a
  live check, a PR with three planted vulnerabilities got inline comments on all three lines
  within 32 s (security layer only; the AI layer was not timed).

## Getting started

**Never used this before? Start with [START_HERE.md](START_HERE.md)**: no installs, about 30 minutes.

**New to the project?** Read **[docs/MODULES_EXPLAINED.md](docs/MODULES_EXPLAINED.md)** — a
plain-English, module-by-module walkthrough of how everything works.

See **[HANDOFF.md](HANDOFF.md)** for full setup — running the backend and dashboard
locally, publishing the model, enabling CI, and using it on other repositories.

Quick backend check:

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
uvicorn app.main:app --reload   # http://127.0.0.1:8000/health
```
