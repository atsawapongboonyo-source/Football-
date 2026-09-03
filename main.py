from pathlib import Path
import sys
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.poisson_dc import DixonColesModel

app = FastAPI(title="Fooball API", version="0.2.0")
STATIC = ROOT / "app" / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# Bundled demo dataset only so the UI/API can be exercised immediately.
# The production pipeline will replace this with the trained 10-season model.
def build_demo_model():
    teams = [
        "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
        "Burnley", "Chelsea", "Crystal Palace", "Everton", "Fulham",
        "Leeds United", "Liverpool", "Manchester City", "Manchester United",
        "Newcastle United", "Nottingham Forest", "Sunderland", "Tottenham",
        "West Ham United", "Wolverhampton"
    ]
    # Deterministic synthetic fixtures for product/UI validation, not betting advice.
    rows = []
    for i, home in enumerate(teams):
        for j, away in enumerate(teams):
            if home == away:
                continue
            hg = (i * 7 + j * 3 + 2) % 4
            ag = (j * 5 + i * 2 + 1) % 3
            rows.append(("2026-01-01", home, away, hg, ag))
    df = pd.DataFrame(rows, columns=["date","home_team","away_team","home_goals","away_goals"])
    return DixonColesModel(l2=0.08).fit(df)

MODEL = build_demo_model()

class PredictionRequest(BaseModel):
    home_team: str
    away_team: str

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")

@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")

@app.get("/service-worker.js")
def service_worker():
    return FileResponse(STATIC / "service-worker.js", media_type="application/javascript")

@app.get("/health")
def health():
    return {"status": "ok", "project": "Fooball", "version": "0.2.0", "model_mode": "demo"}

@app.get("/api/teams")
def teams():
    return {"teams": MODEL.teams, "competition": "Premier League", "model_mode": "demo"}

@app.post("/api/predict")
def predict(req: PredictionRequest):
    if req.home_team == req.away_team:
        raise HTTPException(status_code=400, detail="Home and away teams must be different")
    try:
        p = MODEL.predict(req.home_team, req.away_team)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        **p,
        "model_mode": "demo",
        "model_note": "UI demo model. Replace with trained historical model before real forecasting."
    }
