import io
import time
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "data_cache"
CACHE_DIR.mkdir(exist_ok=True)

EPL_SEASONS = ["1617","1718","1819","1920","2021","2122","2223","2324","2425","2526","2627"]
CHAMP_SEASONS = ["2526"]
EPL_URL = "https://www.football-data.co.uk/mmz4281/{season}/E0.csv"
CHAMP_URL = "https://www.football-data.co.uk/mmz4281/{season}/E1.csv"

FD_NAMES = {
    "Bournemouth": "AFC Bournemouth",
    "Brighton": "Brighton & Hove Albion",
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Newcastle": "Newcastle United",
    "Nott'm Forest": "Nottingham Forest",
    "Tottenham": "Tottenham Hotspur",
    "Coventry": "Coventry City",
    "Hull": "Hull City",
    "Ipswich": "Ipswich Town",
    "Leeds": "Leeds United",
}

CORE_COLS = [
    "Date","HomeTeam","AwayTeam","FTHG","FTAG",
    "HS","AS","HST","AST","HC","AC","HF","AF","HY","AY","HR","AR"
]

def norm_name(x):
    x = str(x).strip()
    return FD_NAMES.get(x, x)

class FootballDataEngine:
    def __init__(self, refresh_seconds=3600):
        self.refresh_seconds = refresh_seconds
        self.epl = pd.DataFrame()
        self.champ = pd.DataFrame()
        self.current_schedule = pd.DataFrame()
        self.last_refresh = None
        self.errors = []

    def _cache_path(self, league, season):
        return CACHE_DIR / f"{league}_{season}.csv"

    def _download_csv(self, url, cache_path):
        use_cache = cache_path.exists() and (time.time() - cache_path.stat().st_mtime < self.refresh_seconds)
        if use_cache:
            return pd.read_csv(cache_path)

        try:
            r = requests.get(url, timeout=15, headers={"User-Agent":"Fooball/0.4"})
            r.raise_for_status()
            cache_path.write_text(r.text, encoding="utf-8")
            return pd.read_csv(io.StringIO(r.text))
        except Exception as exc:
            if cache_path.exists():
                self.errors.append(f"ใช้ cache แทน {url}: {exc}")
                return pd.read_csv(cache_path)
            raise

    def _clean(self, df, season, league):
        required = {"HomeTeam","AwayTeam","FTHG","FTAG"}
        if not required.issubset(df.columns):
            return pd.DataFrame()

        cols = [c for c in CORE_COLS if c in df.columns]
        out = df[cols].copy()
        out = out.dropna(subset=["HomeTeam","AwayTeam","FTHG","FTAG"])
        out["HomeTeam"] = out["HomeTeam"].map(norm_name)
        out["AwayTeam"] = out["AwayTeam"].map(norm_name)

        for c in ["FTHG","FTAG","HS","AS","HST","AST","HC","AC","HF","AF","HY","AY","HR","AR"]:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce")

        out["season"] = season
        out["league"] = league
        return out

    def _clean_schedule(self, df, season):
        required = {"Date","HomeTeam","AwayTeam"}
        if not required.issubset(df.columns):
            return pd.DataFrame()
        cols = [c for c in ["Date","HomeTeam","AwayTeam","FTHG","FTAG"] if c in df.columns]
        out = df[cols].copy()
        out = out.dropna(subset=["HomeTeam","AwayTeam"])
        out["HomeTeam"] = out["HomeTeam"].map(norm_name)
        out["AwayTeam"] = out["AwayTeam"].map(norm_name)
        for c in ["FTHG","FTAG"]:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce")
        out["match_date"] = pd.to_datetime(out["Date"], dayfirst=True, errors="coerce")
        out["season"] = season
        return out

    def refresh(self, force=False):
        if self.last_refresh and not force and (time.time()-self.last_refresh < self.refresh_seconds):
            return

        self.errors = []
        epl_frames = []
        for season in EPL_SEASONS:
            try:
                df = self._download_csv(EPL_URL.format(season=season), self._cache_path("E0", season))
                if season == "2627":
                    self.current_schedule = self._clean_schedule(df, season)
                clean = self._clean(df, season, "Premier League")
                if not clean.empty:
                    age = EPL_SEASONS.index(EPL_SEASONS[-1]) - EPL_SEASONS.index(season)
                    clean["recency_weight"] = 0.78 ** age
                    if season == "2627":
                        clean["recency_weight"] *= 1.45
                    epl_frames.append(clean)
            except Exception as exc:
                self.errors.append(f"EPL {season}: {exc}")

        champ_frames = []
        for season in CHAMP_SEASONS:
            try:
                df = self._download_csv(CHAMP_URL.format(season=season), self._cache_path("E1", season))
                clean = self._clean(df, season, "Championship")
                if not clean.empty:
                    clean["recency_weight"] = 1.0
                    champ_frames.append(clean)
            except Exception as exc:
                self.errors.append(f"Championship {season}: {exc}")

        if epl_frames:
            self.epl = pd.concat(epl_frames, ignore_index=True)
        if champ_frames:
            self.champ = pd.concat(champ_frames, ignore_index=True)

        self.last_refresh = time.time()

    def upcoming_fixture(self, home_team, away_team):
        self.refresh()
        if self.current_schedule.empty:
            return None
        x = self.current_schedule[(self.current_schedule.HomeTeam==home_team) & (self.current_schedule.AwayTeam==away_team)].copy()
        if x.empty:
            return None
        x = x[x["FTHG"].isna() | x["FTAG"].isna()]
        x = x.dropna(subset=["match_date"]).sort_values("match_date")
        if x.empty:
            return None
        r = x.iloc[0]
        return {"date": r.match_date.date().isoformat(), "home_team": home_team, "away_team": away_team}


    def fixture_context(self, home_team, away_team):
        """Return upcoming fixture when available, otherwise the most recent completed
        current-season meeting in the same home/away orientation.
        """
        self.refresh()
        if self.current_schedule.empty:
            return {"status": "not_found", "fixture": None, "actual": None}
        x = self.current_schedule[(self.current_schedule.HomeTeam==home_team) & (self.current_schedule.AwayTeam==away_team)].copy()
        if x.empty:
            return {"status": "not_found", "fixture": None, "actual": None}
        x = x.dropna(subset=["match_date"]).sort_values("match_date")
        upcoming = x[x["FTHG"].isna() | x["FTAG"].isna()]
        if not upcoming.empty:
            r=upcoming.iloc[0]
            fixture={"date":r.match_date.date().isoformat(),"home_team":home_team,"away_team":away_team}
            return {"status":"upcoming","fixture":fixture,"actual":None}
        completed = x.dropna(subset=["FTHG","FTAG"])
        if completed.empty:
            return {"status": "not_found", "fixture": None, "actual": None}
        r=completed.iloc[-1]
        fixture={"date":r.match_date.date().isoformat(),"home_team":home_team,"away_team":away_team}
        actual={"date":fixture["date"],"home_goals":int(r.FTHG),"away_goals":int(r.FTAG),"score":f"{int(r.FTHG)}–{int(r.FTAG)}"}
        return {"status":"completed","fixture":fixture,"actual":actual}

    def h2h_matches(self, team_a, team_b, limit=10):
        self.refresh()
        frames = [self.epl]
        if not self.champ.empty:
            frames.append(self.champ)
        m = pd.concat(frames, ignore_index=True)
        x = m[((m.HomeTeam==team_a)&(m.AwayTeam==team_b))|((m.HomeTeam==team_b)&(m.AwayTeam==team_a))].copy()
        if x.empty:
            return []
        x["match_date"] = pd.to_datetime(x.get("Date"), dayfirst=True, errors="coerce")
        x = x.sort_values("match_date", ascending=False).head(limit)
        out=[]
        for _,r in x.iterrows():
            out.append({
                "date": r.match_date.date().isoformat() if pd.notna(r.match_date) else str(r.get("Date", "")),
                "season": str(r.get("season", "")),
                "league": str(r.get("league", "")),
                "home_team": r.HomeTeam, "away_team": r.AwayTeam,
                "home_goals": int(r.FTHG), "away_goals": int(r.FTAG),
            })
        return out

    def actual_for_fixture(self, home_team, away_team, fixture_date):
        self.refresh()
        if self.current_schedule.empty or not fixture_date:
            return None
        x = self.current_schedule[(self.current_schedule.HomeTeam==home_team) & (self.current_schedule.AwayTeam==away_team)].copy()
        if x.empty:
            return None
        x = x.dropna(subset=["match_date"])
        x = x[x.match_date.dt.date.astype(str) == fixture_date]
        x = x.dropna(subset=["FTHG","FTAG"])
        if x.empty:
            return None
        r=x.iloc[0]
        return {"date": fixture_date, "home_goals": int(r.FTHG), "away_goals": int(r.FTAG), "score": f"{int(r.FTHG)}–{int(r.FTAG)}"}

    def status(self):
        self.refresh()
        return {
            "epl_matches": int(len(self.epl)),
            "championship_matches": int(len(self.champ)),
            "current_season_matches": int((self.epl["season"]=="2627").sum()) if not self.epl.empty else 0,
            "last_refresh_unix": self.last_refresh,
            "scheduled_rows": int(len(self.current_schedule)),
            "refresh_interval_seconds": self.refresh_seconds,
            "errors": self.errors[-5:],
        }
