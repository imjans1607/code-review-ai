# Backend (FastAPI)

The API layer for the Automated Code Review AI. Grows over the phases:

- **Phase 0 (now):** health check only.
- **Phase 4:** the `/review` webhook — runs CodeT5+ inference + Semgrep + the fusion engine.
- **Phase 5:** receives PR events from GitHub Actions, posts fused comments back.
- **Phase 6:** serves stored review history to the React dashboard.

## Run locally

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# Git Bash / macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then check:

- http://127.0.0.1:8000/health  → `{"status": "ok", ...}`
- http://127.0.0.1:8000/docs    → interactive Swagger UI

> Note: `torch`/`transformers` are intentionally **not** installed here. Model
> fine-tuning and heavy inference happen on Google Colab (see `../ml/`). The
> backend will load a lightweight/exported model or call out to a model endpoint
> in later phases.
