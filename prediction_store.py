import json
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STORE_PATH = ROOT / "prediction_history.json"
_lock = threading.Lock()


def _read():
    if not STORE_PATH.exists():
        return []
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write(rows):
    STORE_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def save_prediction(prediction, fixture_date=None):
    now = datetime.now(timezone.utc)
    record = {
        "id": f"p-{int(now.timestamp()*1000)}",
        "created_at": now.isoformat(),
        "fixture_date": fixture_date,
        "home_team": prediction["home_team"],
        "away_team": prediction["away_team"],
        "predicted_score": prediction["most_likely_score"],
        "predicted_score_prob": prediction["most_likely_score_prob"],
        "home_win": prediction["home_win"],
        "draw": prediction["draw"],
        "away_win": prediction["away_win"],
        "expected_home_goals": prediction["expected_home_goals"],
        "expected_away_goals": prediction["expected_away_goals"],
        "over_2_5": prediction["over_2_5"],
        "btts_yes": prediction["btts_yes"],
        "api_version": prediction.get("api_version"),
    }
    with _lock:
        rows = _read()
        # Keep one snapshot per exact fixture per model version when possible.
        if fixture_date:
            rows = [r for r in rows if not (
                r.get("home_team") == record["home_team"] and
                r.get("away_team") == record["away_team"] and
                r.get("fixture_date") == fixture_date and
                r.get("api_version") == record["api_version"]
            )]
        rows.append(record)
        _write(rows[-1000:])
    return record


def list_predictions(home_team=None, away_team=None, limit=20):
    rows = _read()
    if home_team:
        rows = [r for r in rows if r.get("home_team") == home_team]
    if away_team:
        rows = [r for r in rows if r.get("away_team") == away_team]
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return rows[:limit]
