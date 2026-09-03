from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from predictor import FooballPredictor
from fixture_engine import FixtureEngine
from prediction_store import save_prediction, list_predictions, all_predictions

ROOT = Path(__file__).resolve().parent
VERSION = "0.4.7"
app = FastAPI(title="Fooball", version=VERSION)
predictor = FooballPredictor()
fixture_engine = FixtureEngine()


class PredictRequest(BaseModel):
    home_team: str
    away_team: str


@app.get("/")
def home():
    return FileResponse(ROOT / "index.html", headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/styles.css")
def styles():
    return FileResponse(ROOT / "styles.css", media_type="text/css", headers={"Cache-Control": "no-cache"})


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(ROOT / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/service-worker.js")
def sw():
    return FileResponse(ROOT / "service-worker.js", media_type="application/javascript", headers={"Cache-Control": "no-store"})


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": VERSION,
        "frontend_expected": VERSION,
        "deployment_marker": "fixture-probability-047",
    }


@app.get("/api/version")
def api_version():
    return {
        "backend": VERSION,
        "frontend_expected": VERSION,
        "deployment_marker": "fixture-probability-047",
        "javascript_mode": "inline",
        "fixture_engine": "multi-source-day-by-day",
    }


@app.get("/api/teams")
def teams():
    return {
        "season": "2026/27",
        "teams": predictor.current_teams,
        "promoted": ["Coventry City", "Hull City", "Ipswich Town"],
    }


@app.get("/api/data-status")
def data_status():
    s = predictor.status()
    s["fixture_engine"] = fixture_engine.status()
    return s


@app.get("/api/fixture-status")
def fixture_status():
    return fixture_engine.status()


@app.get("/api/upcoming-fixtures")
def upcoming_fixtures(days: int = Query(10, ge=1, le=30)):
    return {
        "season": "2026/27",
        "provider": fixture_engine.status().get("provider"),
        "fixtures": fixture_engine.upcoming(days),
    }


@app.get("/api/fixture-debug")
def fixture_debug(force: bool = False):
    if force:
        fixture_engine.refresh(force=True)
    status = fixture_engine.status()
    return {
        "status": status,
        "next_10_days": fixture_engine.upcoming(10),
        "sample_all": fixture_engine.fixtures[:20],
    }


@app.get("/api/match-history")
def match_history(home_team: str, away_team: str, limit: int = Query(10, ge=1, le=20)):
    if home_team not in predictor.current_teams or away_team not in predictor.current_teams:
        raise HTTPException(400, "ไม่พบทีมใน Premier League 2026/27")
    return {
        "home_team": home_team,
        "away_team": away_team,
        "matches": predictor.engine.h2h_matches(home_team, away_team, limit),
    }


def enrich_prediction(r):
    row = dict(r)
    actual = predictor.engine.actual_for_fixture(r.get("home_team"), r.get("away_team"), r.get("fixture_date"))
    row["actual"] = actual
    if actual:
        hg, ag = actual["home_goals"], actual["away_goals"]
        actual_1x2 = "home" if hg > ag else "draw" if hg == ag else "away"
        pred_1x2 = max(
            (("home", r.get("home_win", 0)), ("draw", r.get("draw", 0)), ("away", r.get("away_win", 0))),
            key=lambda x: x[1],
        )[0]
        row["result_1x2_correct"] = pred_1x2 == actual_1x2
        row["exact_score_correct"] = r.get("predicted_score") == actual.get("score")
        row["over_2_5_correct"] = (r.get("over_2_5", 0) >= 0.5) == ((hg + ag) > 2.5)
        row["btts_correct"] = (r.get("btts_yes", 0) >= 0.5) == (hg > 0 and ag > 0)
    return row


@app.get("/api/prediction-history")
def prediction_history(home_team: str | None = None, away_team: str | None = None, limit: int = Query(20, ge=1, le=100)):
    return {"predictions": [enrich_prediction(r) for r in list_predictions(home_team, away_team, limit)]}


@app.get("/api/model-performance")
def model_performance():
    rows = [enrich_prediction(r) for r in all_predictions()]
    resolved = [r for r in rows if r.get("actual")]
    if not resolved:
        return {
            "resolved_predictions": 0,
            "pending_predictions": len(rows),
            "note": "ยังไม่มีคำทำนายก่อนแข่งที่มีผลจริงสำหรับคำนวณสถิติ",
        }
    n = len(resolved)
    brier = []
    for r in resolved:
        a = r["actual"]
        hg, ag = a["home_goals"], a["away_goals"]
        y = [1, 0, 0] if hg > ag else [0, 1, 0] if hg == ag else [0, 0, 1]
        p = [r.get("home_win", 0), r.get("draw", 0), r.get("away_win", 0)]
        brier.append(sum((pi - yi) ** 2 for pi, yi in zip(p, y)))
    return {
        "resolved_predictions": n,
        "pending_predictions": len(rows) - n,
        "accuracy_1x2": sum(bool(r.get("result_1x2_correct")) for r in resolved) / n,
        "accuracy_over_2_5": sum(bool(r.get("over_2_5_correct")) for r in resolved) / n,
        "accuracy_btts": sum(bool(r.get("btts_correct")) for r in resolved) / n,
        "exact_score_rate": sum(bool(r.get("exact_score_correct")) for r in resolved) / n,
        "brier_score": sum(brier) / n,
        "note": "นับเฉพาะ prediction ที่บันทึกก่อนแข่งและผูกกับ fixture จริง",
    }


@app.post("/api/predict")
def predict(req: PredictRequest):
    if req.home_team == req.away_team:
        raise HTTPException(400, "กรุณาเลือกคนละทีม")
    if req.home_team not in predictor.current_teams or req.away_team not in predictor.current_teams:
        raise HTTPException(400, "ไม่พบทีมใน Premier League 2026/27")
    try:
        result = predictor.predict(req.home_team, req.away_team)
        result["api_version"] = VERSION

        # Future fixtures come from the dedicated Fixture Engine. Historical results
        # stay in FootballDataEngine so prediction and result sources are separated.
        fixture = fixture_engine.find(req.home_team, req.away_team)
        if fixture:
            context = {"status": "upcoming", "fixture": fixture, "actual": None}
        else:
            context = predictor.engine.fixture_context(req.home_team, req.away_team)

        result["fixture_context"] = context
        result["fixture"] = context.get("fixture")
        result["h2h_matches"] = predictor.engine.h2h_matches(req.home_team, req.away_team, 10)

        if context.get("status") == "upcoming" and context.get("fixture"):
            f = context["fixture"]
            saved = save_prediction(
                result,
                fixture_date=f["date"],
                fixture_id=f.get("fixture_id"),
                kickoff_utc=f.get("kickoff_utc"),
                fixture_source=f.get("source"),
            )
            result["prediction_id"] = saved["id"] if saved else None
            result["tracking_status"] = "saved_pre_match"
        elif context.get("status") == "completed":
            result["prediction_id"] = None
            result["tracking_status"] = "retrospective_not_counted"
        else:
            result["prediction_id"] = None
            result["tracking_status"] = "no_fixture_not_saved"
        return result
    except Exception as exc:
        raise HTTPException(500, f"Prediction error: {exc}")
