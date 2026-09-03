import io
import time
from pathlib import Path
from typing import List, Dict, Tuple

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
    "HS","AS","HST","AST","HC","AC","HY","AY"
]

def norm_name(x):
    x = str(x).strip()
    return FD_NAMES.get(x, x)

class FootballDataEngine:
    def __init__(self, refresh_seconds=3600):
        self.refresh_seconds = refresh_seconds
        self.epl = pd.DataFrame()
        self.champ = pd.DataFrame()
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

        for c in ["FTHG","FTAG","HS","AS","HST","AST","HC","AC","HY","AY"]:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce")

        out["season"] = season
        out["league"] = league
        return out

    def refresh(self, force=False):
        if self.last_refresh and not force and (time.time()-self.last_refresh < self.refresh_seconds):
            return

        self.errors = []
        epl_frames = []
        for season in EPL_SEASONS:
            try:
                df = self._download_csv(EPL_URL.format(season=season), self._cache_path("E0", season))
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

    def status(self):
        self.refresh()
        return {
            "epl_matches": int(len(self.epl)),
            "championship_matches": int(len(self.champ)),
            "current_season_matches": int((self.epl["season"]=="2627").sum()) if not self.epl.empty else 0,
            "last_refresh_unix": self.last_refresh,
            "errors": self.errors[-5:],
        }
