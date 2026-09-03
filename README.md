# Fooball v0.2.1 — Render Ready (flat repository)

This build is intentionally **flat** so it can be uploaded from a phone to the root of a GitHub repository without losing folder structure.

## Render settings
- Language: Python 3
- Root Directory: leave blank
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Environment Variables: none required for this demo build

## Important
The current prediction model uses deterministic synthetic demo data only. It is for validating the web/PWA/API deployment, not for real football forecasting or betting decisions.

## After deployment
- `/` — mobile web app
- `/health` — health check
- `/api/teams` — team list
- `/api/predict` — prediction endpoint
