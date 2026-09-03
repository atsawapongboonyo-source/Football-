from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from predictor import FooballPredictor

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Fooball", version="0.4.0")
predictor = FooballPredictor()

class PredictRequest(BaseModel):
    home_team: str
    away_team: str

@app.get("/")
def home():
    return FileResponse(ROOT/"index.html")

@app.get("/styles.css")
def styles():
    return FileResponse(ROOT/"styles.css", media_type="text/css")

@app.get("/app.js")
def js():
    return FileResponse(ROOT/"app.js", media_type="application/javascript")

@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(ROOT/"manifest.webmanifest", media_type="application/manifest+json")

@app.get("/service-worker.js")
def sw():
    return FileResponse(ROOT/"service-worker.js", media_type="application/javascript")

@app.get("/health")
def health():
    return {"status":"ok","version":"0.4.0"}

@app.get("/api/teams")
def teams():
    return {"season":"2026/27","teams":predictor.current_teams,
            "promoted":["Coventry City","Hull City","Ipswich Town"]}

@app.get("/api/data-status")
def data_status():
    return predictor.status()

@app.post("/api/predict")
def predict(req: PredictRequest):
    if req.home_team == req.away_team:
        raise HTTPException(400,"กรุณาเลือกคนละทีม")
    if req.home_team not in predictor.current_teams or req.away_team not in predictor.current_teams:
        raise HTTPException(400,"ไม่พบทีมใน Premier League 2026/27")
    try:
        return predictor.predict(req.home_team,req.away_team)
    except Exception as exc:
        raise HTTPException(500,f"Prediction error: {exc}")
