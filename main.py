from pathlib import Path
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from poisson_dc import DixonColesModel

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Fooball API", version="0.2.1")


def build_demo_model():
    teams = [
        "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
        "Burnley", "Chelsea", "Crystal Palace", "Everton", "Fulham",
        "Leeds United", "Liverpool", "Manchester City", "Manchester United",
        "Newcastle United", "Nottingham Forest", "Sunderland", "Tottenham",
        "West Ham United", "Wolverhampton"
    ]
    rows = []
    for i, home in enumerate(teams):
        for j, away in enumerate(teams):
            if home == away:
                continue
            hg = (i * 7 + j * 3 + 2) % 4
            ag = (j * 5 + i * 2 + 1) % 3
            rows.append(("2026-01-01", home, away, hg, ag))
    df = pd.DataFrame(rows, columns=["date", "home_team", "away_team", "home_goals", "away_goals"])
    return DixonColesModel(l2=0.08).fit(df)


MODEL = build_demo_model()


class PredictionRequest(BaseModel):
    home_team: str
    away_team: str


@app.get("/")
def index():
    return FileResponse(ROOT / "index.html")


@app.get("/styles.css")
def styles():
    return FileResponse(ROOT / "styles.css", media_type="text/css")


@app.get("/app.js")
def javascript():
    return FileResponse(ROOT / "app.js", media_type="application/javascript")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(ROOT / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/service-worker.js")
def service_worker():
    return FileResponse(ROOT / "service-worker.js", media_type="application/javascript")


@app.get("/health")
def health():
    return {"status": "ok", "project": "Fooball", "version": "0.2.1", "model_mode": "demo"}


@app.get("/api/teams")
def teams():
    return {"teams": MODEL.teams, "competition": "Premier League", "model_mode": "demo"}


@app.post("/api/predict")
def predict(req: PredictionRequest):
    if req.home_team == req.away_team:
        raise HTTPException(status_code=400, detail="Home and away teams must be different")
    try:
        p = MODEL.predict(req.home_team, req.away_team)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        **p,
        "model_mode": "demo",
        "model_note": "UI demo model. Replace with trained historical model before real forecasting.",
    }
