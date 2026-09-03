from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

COLUMN_MAP = {
    "Date": "date", "HomeTeam": "home_team", "AwayTeam": "away_team",
    "FTHG": "home_goals", "FTAG": "away_goals",
    "HS": "home_shots", "AS": "away_shots",
    "HST": "home_sot", "AST": "away_sot",
    "B365H": "home_odds", "B365D": "draw_odds", "B365A": "away_odds",
}


def season_label(code: str) -> str:
    a, b = int(code[:2]), int(code[2:])
    return f"20{a:02d}/{str(2000+b)[-2:]}"


def load_division(prefix: str, competition: str):
    frames = []
    for p in sorted(RAW.glob(f"{prefix}_*.csv")):
        code = p.stem.split("_")[-1]
        d = pd.read_csv(p, encoding_errors="ignore")
        cols = [c for c in COLUMN_MAP if c in d.columns]
        d = d[cols].rename(columns=COLUMN_MAP)
        d["season"] = season_label(code)
        d["competition"] = competition
        d["date"] = pd.to_datetime(d["date"], dayfirst=True, errors="coerce")
        d = d.dropna(subset=["date","home_team","away_team","home_goals","away_goals"])
        frames.append(d)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main():
    epl = load_division("premier_league", "EPL")
    champ = load_division("championship", "Championship")
    if not epl.empty:
        epl.sort_values("date").to_csv(OUT / "epl_matches.csv", index=False)
        print("EPL rows:", len(epl))
    if not champ.empty:
        champ.sort_values("date").to_csv(OUT / "championship_matches.csv", index=False)
        print("Championship rows:", len(champ))

if __name__ == "__main__":
    main()
