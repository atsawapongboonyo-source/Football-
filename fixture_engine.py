import io
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "data_cache"
CACHE_DIR.mkdir(exist_ok=True)

FIXTURES_URL = "https://www.football-data.co.uk/matches/resources/fixtures.csv"
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"

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
    "Sunderland": "Sunderland",
}

ESPN_NAMES = {
    "AFC Bournemouth": "AFC Bournemouth",
    "Bournemouth": "AFC Bournemouth",
    "Brighton & Hove Albion": "Brighton & Hove Albion",
    "Brighton": "Brighton & Hove Albion",
    "Manchester City": "Manchester City",
    "Manchester United": "Manchester United",
    "Newcastle United": "Newcastle United",
    "Nottingham Forest": "Nottingham Forest",
    "Tottenham Hotspur": "Tottenham Hotspur",
    "Coventry City": "Coventry City",
    "Hull City": "Hull City",
    "Ipswich Town": "Ipswich Town",
    "Leeds United": "Leeds United",
    "Sunderland": "Sunderland",
    "Sunderland AFC": "Sunderland",
    "Brentford": "Brentford",
    "Brentford FC": "Brentford",
    "Fulham": "Fulham",
    "Fulham FC": "Fulham",
    "Crystal Palace": "Crystal Palace",
    "Aston Villa": "Aston Villa",
    "Arsenal": "Arsenal",
    "Chelsea": "Chelsea",
    "Everton": "Everton",
    "Liverpool": "Liverpool",
}


def norm_fd(x):
    x = str(x).strip()
    return FD_NAMES.get(x, x)


def norm_espn(x):
    x = str(x).strip()
    return ESPN_NAMES.get(x, x)


def slug(x):
    return re.sub(r"[^a-z0-9]+", "-", x.lower()).strip("-")


class FixtureEngine:
    """Future fixture source separated from historical result data.

    Provider order:
    1) Football-Data weekly fixtures.csv (E0)
    2) ESPN public EPL scoreboard as a no-key fallback

    No bookmaker odds are returned or used by the model.
    """

    def __init__(self, refresh_seconds=1800, horizon_days=21):
        self.refresh_seconds = refresh_seconds
        self.horizon_days = horizon_days
        self.fixtures = []
        self.last_refresh = None
        self.errors = []
        self.provider = None

    def _cache_path(self):
        return CACHE_DIR / "fixtures_latest.csv"

    def _football_data(self):
        cache = self._cache_path()
        use_cache = cache.exists() and time.time() - cache.stat().st_mtime < self.refresh_seconds
        if use_cache:
            text = cache.read_text(encoding="utf-8", errors="ignore")
        else:
            r = requests.get(FIXTURES_URL, timeout=15, headers={"User-Agent": "Fooball/0.4.5"})
            r.raise_for_status()
            text = r.text
            cache.write_text(text, encoding="utf-8")
        df = pd.read_csv(io.StringIO(text))
        if "Div" in df.columns:
            df = df[df["Div"].astype(str).str.upper() == "E0"]
        required = {"Date", "HomeTeam", "AwayTeam"}
        if not required.issubset(df.columns):
            raise ValueError("fixtures.csv ไม่มีคอลัมน์ Date/HomeTeam/AwayTeam")

        london = ZoneInfo("Europe/London")
        out = []
        for _, r in df.iterrows():
            dt = pd.to_datetime(r.get("Date"), dayfirst=True, errors="coerce")
            if pd.isna(dt):
                continue
            date_str = dt.date().isoformat()
            time_str = str(r.get("Time", "")).strip()
            kickoff_utc = None
            if time_str and time_str.lower() != "nan":
                try:
                    hh, mm = [int(v) for v in time_str.split(":")[:2]]
                    local_dt = datetime(dt.year, dt.month, dt.day, hh, mm, tzinfo=london)
                    kickoff_utc = local_dt.astimezone(timezone.utc).isoformat()
                except Exception:
                    kickoff_utc = None
            home, away = norm_fd(r.get("HomeTeam")), norm_fd(r.get("AwayTeam"))
            out.append({
                "fixture_id": f"fd-e0-{date_str}-{slug(home)}-{slug(away)}",
                "date": date_str,
                "kickoff_utc": kickoff_utc,
                "home_team": home,
                "away_team": away,
                "competition": "Premier League",
                "source": "Football-Data Fixtures",
            })
        if not out:
            raise ValueError("ไม่พบ Premier League fixtures ใน fixtures.csv")
        return out

    def _espn(self):
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=self.horizon_days)
        dates = f"{today.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"
        r = requests.get(ESPN_URL, params={"dates": dates, "limit": 100}, timeout=15,
                         headers={"User-Agent": "Fooball/0.4.5"})
        r.raise_for_status()
        data = r.json()
        london = ZoneInfo("Europe/London")
        out = []
        for ev in data.get("events", []):
            comps = ev.get("competitions") or []
            if not comps:
                continue
            comp = comps[0]
            competitors = comp.get("competitors") or []
            home_obj = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away_obj = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home_obj or not away_obj:
                continue
            home = norm_espn((home_obj.get("team") or {}).get("displayName") or (home_obj.get("team") or {}).get("shortDisplayName") or "")
            away = norm_espn((away_obj.get("team") or {}).get("displayName") or (away_obj.get("team") or {}).get("shortDisplayName") or "")
            iso = ev.get("date") or comp.get("date")
            if not iso:
                continue
            try:
                kdt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
                date_str = kdt.astimezone(london).date().isoformat()
                kickoff_utc = kdt.astimezone(timezone.utc).isoformat()
            except Exception:
                continue
            out.append({
                "fixture_id": f"espn-{ev.get('id') or slug(home+'-'+away+'-'+date_str)}",
                "date": date_str,
                "kickoff_utc": kickoff_utc,
                "home_team": home,
                "away_team": away,
                "competition": "Premier League",
                "source": "ESPN Schedule fallback",
            })
        if not out:
            raise ValueError("ESPN fallback ไม่คืน Premier League fixtures")
        return out

    def refresh(self, force=False):
        if self.last_refresh and not force and time.time() - self.last_refresh < self.refresh_seconds:
            return
        self.errors = []
        fixtures = []
        try:
            fixtures = self._football_data()
            self.provider = "Football-Data Fixtures"
        except Exception as exc:
            self.errors.append(f"Football-Data Fixtures: {exc}")
            try:
                fixtures = self._espn()
                self.provider = "ESPN Schedule fallback"
            except Exception as exc2:
                self.errors.append(f"ESPN fallback: {exc2}")
                self.provider = None
        self.fixtures = fixtures
        self.last_refresh = time.time()

    def find(self, home_team, away_team):
        self.refresh()
        today = datetime.now(timezone.utc).date()
        rows = [f for f in self.fixtures if f["home_team"] == home_team and f["away_team"] == away_team]
        rows = [f for f in rows if datetime.fromisoformat(f["date"]).date() >= today]
        rows.sort(key=lambda f: (f["date"], f.get("kickoff_utc") or ""))
        return rows[0] if rows else None

    def upcoming(self, days=10):
        self.refresh()
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=days)
        rows = [f for f in self.fixtures if today <= datetime.fromisoformat(f["date"]).date() <= end]
        rows.sort(key=lambda f: (f["date"], f.get("kickoff_utc") or "", f["home_team"]))
        return rows

    def status(self):
        self.refresh()
        return {
            "provider": self.provider,
            "fixture_count": len(self.fixtures),
            "last_refresh_unix": self.last_refresh,
            "refresh_interval_seconds": self.refresh_seconds,
            "errors": self.errors[-5:],
        }
