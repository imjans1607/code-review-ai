# Setup & Run Guide

> **Complete beginner?** Read **[START_HERE.md](START_HERE.md)** first. This file is the full reference.

Everything needed to run the **Automated Code Review AI** — locally, on GitHub,
and on other repositories. No paid services are required.

---

## 0. What's in the box

```
backend/      FastAPI backend — the review pipeline (Modules 1–4, 6) + API
frontend/     React dashboard (Module 6)
scripts/      run_review.py — the CI entrypoint
ml/notebooks/ Colab notebooks — data prep, fine-tuning, evaluation, model publish
.github/      the CI workflow (Module 5)
action.yml    reusable Action so ANY repo can use the reviewer
docs/         design notes, first-review content, this project's write-ups
```

## 1. Prerequisites

- **Python 3.11**, **Node.js 18+**, **git**
- A **GitHub account** (for the CI part)
- *(Optional)* a free **Hugging Face account** — only if you want to host your own copy of the model

---

## 2. Run the backend + dashboard locally (5 minutes)

**Backend (API):**
```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```
Check http://localhost:8000/health → `{"status":"ok",...}` and http://localhost:8000/docs for the API.

**Dashboard (in a second terminal):**
```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

**Put some data in it** — run a review through the API (the dashboard reads what's
saved). Uses only the standard library:
```bash
# from the backend/ folder, with the server running
python - <<'PY'
import json, urllib.request
payload = {
    "diff": open("examples/sample_change.diff").read(),
    "semgrep_json": json.load(open("examples/semgrep_sample_output.json")),
    "run_ai": False, "repo": "demo/repo", "pr_number": 1, "author": "you",
}
req = urllib.request.Request("http://localhost:8000/review",
    data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
print(json.load(urllib.request.urlopen(req))["summary"])
PY
```
Refresh the dashboard — the review appears with severity charts and filters.

> **Offline demos (no server needed):** each module runs on sample data:
> `python -m app.collector.collector examples/sample_change.diff` (collect),
> `python -m app.security.semgrep_scanner examples/semgrep_sample_output.json` (security),
> `python -m app.fusion.fusion examples/semgrep_sample_output.json` (fusion).

---

## 2b. Use PostgreSQL instead of SQLite (optional)

By default reviews are saved to a local SQLite file (`backend/reviews.db`) — nothing
to set up. For a deployed dashboard, or so CI runs can write to the same place the
dashboard reads from, point the backend at PostgreSQL with one setting:

```bash
DATABASE_URL=postgresql://codereview:change-me@localhost:5432/codereview
```

Put it in `backend/.env` (copy `backend/.env.example`) or export it before starting
the backend. `postgres://...` URLs from hosting providers work too. The table is
created automatically on startup, and `GET /health` reports which database is in
use (`"database": "postgresql"`).

Need a local Postgres to try it? Any works, for example with Docker:
```bash
docker run --name codereview-db -e POSTGRES_USER=codereview -e POSTGRES_PASSWORD=change-me \
  -e POSTGRES_DB=codereview -p 5432:5432 -d postgres:16
```

**Keep your existing history** when switching from SQLite — copy it across once
(the target must be empty; ids are preserved):
```bash
# from the repo root, with DATABASE_URL set as above
python scripts/migrate_db.py                       # backend/reviews.db -> $DATABASE_URL
```

**CI runs on PostgreSQL:** a GitHub runner is thrown away after each run, so by
default its saved review disappears with it. To make CI reviews show up on the
dashboard, store the full URL as a repo secret named `DATABASE_URL` (Settings →
Secrets and variables → Actions → Secrets); the workflow passes it through. The
reusable Action takes it as the `database-url` input. The database must be
reachable from GitHub's runners, and the secret is available to workflows from
branches of the same repo, so use a database user that can only touch this table
set and don't reuse it for anything else.

## 3. Publish your own copy of the model (optional, free)

A working model is already public at `Jabez0701/codereviewer-msg-pyjs`, so you can
skip this and just use that id. To host **your own** copy so the project depends on
nothing external:

1. Create a free account at https://huggingface.co and a **Write** token
   (Settings → Access Tokens → New token → role **Write**).
2. Open `ml/notebooks/06_publish_to_hf.ipynb` in Google Colab.
3. Either re-host the existing public model, or re-train first (`04_codereviewer_finetune.ipynb`).
   To **re-host** the existing one, run this in a Colab cell instead of loading from Drive:
   ```python
   from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
   src = "Jabez0701/codereviewer-msg-pyjs"
   AutoModelForSeq2SeqLM.from_pretrained(src).push_to_hub("YOUR-USERNAME/codereviewer-msg-pyjs")
   AutoTokenizer.from_pretrained(src).push_to_hub("YOUR-USERNAME/codereviewer-msg-pyjs")
   ```
   > Colab tip: if you get a 401, delete any stale `HF_TOKEN` in the Colab **Secrets**
   > panel (left sidebar 🔑) and restart the runtime — a stored token overrides login.

---

## 4. Put it on GitHub + turn on CI

1. Create a new repo on GitHub and push this project to it.
2. CI is already wired: `.github/workflows/code-review.yml` runs on every pull request —
   it scans the diff with Semgrep and posts a review.
3. *(Optional)* enable AI comments too: repo **Settings → Secrets and variables →
   Actions → Variables → New variable** → `AI_MODEL_PATH` =
   `YOUR-USERNAME/codereviewer-msg-pyjs` (or `Jabez0701/codereviewer-msg-pyjs`).
4. Open a test pull request that adds a small insecure snippet (see
   `backend/examples/vulnerable_samples/`) → the workflow posts the review on the PR.

---

## 5. Use it on ANY other repository (free)

The project doubles as a reusable GitHub Action, so other repos don't need a copy of
the code — just one small workflow file:

1. In the OTHER repo, add `.github/workflows/ai-code-review.yml`, copied from
   `docs/examples/consumer-workflow.yml` in this project.
2. Edit the one line marked `<-- EDIT THIS`: `uses: YOUR-GITHUB-USERNAME/YOUR-COPY-REPO-NAME@main`
   → your username and the repo where you pushed THIS project. The AI model line is
   optional (security-only is the default).
3. Open a pull request in that repo → it gets reviewed automatically.

If the repo holding this project is **private**, other repos can only use it after
**Settings → Actions → General → Access → "Accessible from repositories owned by the user"**
(otherwise the run fails with "Unable to resolve action … repository not found").
Public is simplest. Complete beginner steps: **[START_HERE.md](START_HERE.md)**.

That's the whole thing — no servers, no cost.

---

## Troubleshooting

- **`ModuleNotFoundError: psycopg2`** → the URL names the old driver. Use `postgresql://...` or `postgresql+psycopg://...` (the backend maps the first to psycopg 3), and re-run `pip install -r backend/requirements.txt`.
- **Backend import errors** → make sure you installed `backend/requirements.txt` in the venv.
- **Dashboard shows "Could not reach the backend"** → start the backend on port 8000 first.
- **Semgrep on Windows** → limited native support; it runs fine on the GitHub Actions
  (Linux) runner, which is where the CI uses it.
- **CI didn't post a comment** → check the workflow has `permissions: pull-requests: write`.
