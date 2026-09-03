from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from predictor import FooballPredictor
from prediction_store import save_prediction, list_predictions

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Fooball", version="0.4.3")
predictor = FooballPredictor()

class PredictRequest(BaseModel):
    home_team: str
    away_team: str

@app.get("/")
def home():
    return FileResponse(ROOT/"index.html", headers={"Cache-Control":"no-cache"})

@app.get("/styles.css")
def styles():
    return FileResponse(ROOT/"styles.css", media_type="text/css", headers={"Cache-Control":"no-cache"})

@app.get("/app.js")
def js():
    return FileResponse(ROOT/"app.js", media_type="application/javascript", headers={"Cache-Control":"no-store, max-age=0, must-revalidate"})

@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(ROOT/"manifest.webmanifest", media_type="application/manifest+json")

@app.get("/service-worker.js")
def sw():
    return FileResponse(ROOT/"service-worker.js", media_type="application/javascript", headers={"Cache-Control":"no-cache"})

@app.get("/health")
def health():
    return {"status":"ok","version":"0.4.3","frontend_expected":"0.4.3","deployment_marker":"inline-frontend-043"}

@app.get("/api/version")
def api_version():
    return {
        "backend":"0.4.3",
        "frontend_expected":"0.4.3",
        "deployment_marker":"inline-frontend-043",
        "javascript_mode":"inline",
    }

@app.get("/api/teams")
def teams():
    return {"season":"2026/27","teams":predictor.current_teams,
            "promoted":["Coventry City","Hull City","Ipswich Town"]}

@app.get("/api/data-status")
def data_status():
    return predictor.status()

@app.get("/api/match-history")
def match_history(home_team: str, away_team: str, limit: int = Query(10, ge=1, le=20)):
    if home_team not in predictor.current_teams or away_team not in predictor.current_teams:
        raise HTTPException(400,"ไม่พบทีมใน Premier League 2026/27")
    return {
        "home_team": home_team,
        "away_team": away_team,
        "matches": predictor.engine.h2h_matches(home_team, away_team, limit),
    }

@app.get("/api/prediction-history")
def prediction_history(home_team: str | None = None, away_team: str | None = None, limit: int = Query(20, ge=1, le=100)):
    rows = list_predictions(home_team, away_team, limit)
    enriched=[]
    for r in rows:
        row=dict(r)
        actual = predictor.engine.actual_for_fixture(r.get("home_team"), r.get("away_team"), r.get("fixture_date"))
        row["actual"] = actual
        if actual:
            row["exact_score_correct"] = r.get("predicted_score") == actual.get("score")
            hg, ag = actual["home_goals"], actual["away_goals"]
            actual_1x2 = "home" if hg>ag else "draw" if hg==ag else "away"
            pred_1x2 = max((("home",r.get("home_win",0)),("draw",r.get("draw",0)),("away",r.get("away_win",0))), key=lambda x:x[1])[0]
            row["result_1x2_correct"] = pred_1x2 == actual_1x2
        enriched.append(row)
    return {"predictions": enriched}

@app.post("/api/predict")
def predict(req: PredictRequest):
    if req.home_team == req.away_team:
        raise HTTPException(400,"กรุณาเลือกคนละทีม")
    if req.home_team not in predictor.current_teams or req.away_team not in predictor.current_teams:
        raise HTTPException(400,"ไม่พบทีมใน Premier League 2026/27")
    try:
        result = predictor.predict(req.home_team, req.away_team)
        fixture = predictor.engine.upcoming_fixture(req.home_team, req.away_team)
        result["fixture"] = fixture
        result["h2h_matches"] = predictor.engine.h2h_matches(req.home_team, req.away_team, 10)
        saved = save_prediction(result, fixture_date=fixture["date"] if fixture else None)
        result["prediction_id"] = saved["id"]
        return result
    except Exception as exc:
        raise HTTPException(500,f"Prediction error: {exc}")
