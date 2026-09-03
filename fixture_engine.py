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

TEAM_ALIASES = {
    "afc bournemouth": "AFC Bournemouth", "bournemouth": "AFC Bournemouth",
    "arsenal": "Arsenal", "arsenal fc": "Arsenal",
    "aston villa": "Aston Villa", "aston villa fc": "Aston Villa",
    "brentford": "Brentford", "brentford fc": "Brentford",
    "brighton": "Brighton & Hove Albion", "brighton hove albion": "Brighton & Hove Albion",
    "brighton and hove albion": "Brighton & Hove Albion", "brighton & hove albion": "Brighton & Hove Albion",
    "chelsea": "Chelsea", "chelsea fc": "Chelsea",
    "coventry": "Coventry City", "coventry city": "Coventry City", "coventry city fc": "Coventry City",
    "crystal palace": "Crystal Palace", "crystal palace fc": "Crystal Palace",
    "everton": "Everton", "everton fc": "Everton",
    "fulham": "Fulham", "fulham fc": "Fulham",
    "hull": "Hull City", "hull city": "Hull City", "hull city afc": "Hull City",
    "ipswich": "Ipswich Town", "ipswich town": "Ipswich Town", "ipswich town fc": "Ipswich Town",
    "leeds": "Leeds United", "leeds united": "Leeds United", "leeds united fc": "Leeds United",
    "liverpool": "Liverpool", "liverpool fc": "Liverpool",
    "man city": "Manchester City", "manchester city": "Manchester City", "manchester city fc": "Manchester City",
    "man united": "Manchester United", "manchester united": "Manchester United", "manchester united fc": "Manchester United",
    "newcastle": "Newcastle United", "newcastle united": "Newcastle United", "newcastle united fc": "Newcastle United",
    "nott m forest": "Nottingham Forest", "nottingham forest": "Nottingham Forest", "nottingham forest fc": "Nottingham Forest",
    "sunderland": "Sunderland", "sunderland afc": "Sunderland",
    "tottenham": "Tottenham Hotspur", "tottenham hotspur": "Tottenham Hotspur", "tottenham hotspur fc": "Tottenham Hotspur",
}


def _name_key(x):
    x = str(x or "").strip().lower().replace("&", " and ")
    x = re.sub(r"[^a-z0-9]+", " ", x)
    return re.sub(r"\s+", " ", x).strip()


def canonical_team(x):
    raw = str(x or "").strip()
    key = _name_key(raw)
    return TEAM_ALIASES.get(key, raw)


def team_key(x):
    return _name_key(canonical_team(x))


def slug(x):
    return re.sub(r"[^a-z0-9]+", "-", str(x).lower()).strip("-")


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
            home, away = canonical_team(r.get("HomeTeam")), canonical_team(r.get("AwayTeam"))
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
            home = canonical_team((home_obj.get("team") or {}).get("displayName") or (home_obj.get("team") or {}).get("shortDisplayName") or "")
            away = canonical_team((away_obj.get("team") or {}).get("displayName") or (away_obj.get("team") or {}).get("shortDisplayName") or "")
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

    def _dedupe(self, rows):
        merged = {}
        for f in rows:
            key = (f.get("date"), team_key(f.get("home_team")), team_key(f.get("away_team")))
            if key not in merged:
                merged[key] = f
            else:
                # Prefer a row with kickoff time; keep source provenance.
                cur = merged[key]
                if not cur.get("kickoff_utc") and f.get("kickoff_utc"):
                    cur["kickoff_utc"] = f.get("kickoff_utc")
                sources = set(str(cur.get("source", "")).split(" + ")) | set(str(f.get("source", "")).split(" + "))
                cur["source"] = " + ".join(sorted(x for x in sources if x))
        return list(merged.values())

    def refresh(self, force=False):
        if self.last_refresh and not force and time.time() - self.last_refresh < self.refresh_seconds:
            return
        self.errors = []
        rows = []
        providers = []

        # Important: query both providers. A provider can be reachable yet still
        # have an incomplete/stale fixture list, so success from one source must
        # not prevent the other source from contributing missing fixtures.
        try:
            fd = self._football_data()
            rows.extend(fd)
            providers.append("Football-Data Fixtures")
        except Exception as exc:
            self.errors.append(f"Football-Data Fixtures: {exc}")

        try:
            espn = self._espn()
            rows.extend(espn)
            providers.append("ESPN Schedule fallback")
        except Exception as exc:
            self.errors.append(f"ESPN fallback: {exc}")

        self.fixtures = self._dedupe(rows)
        self.provider = " + ".join(providers) if providers else None
        self.last_refresh = time.time()

    def find(self, home_team, away_team):
        self.refresh()
        today = datetime.now(timezone.utc).date()
        hk, ak = team_key(home_team), team_key(away_team)
        rows = [f for f in self.fixtures if team_key(f.get("home_team")) == hk and team_key(f.get("away_team")) == ak]
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
        source_counts = {}
        for f in self.fixtures:
            src = f.get("source") or "unknown"
            source_counts[src] = source_counts.get(src, 0) + 1
        return {
            "provider": self.provider,
            "fixture_count": len(self.fixtures),
            "source_counts": source_counts,
            "last_refresh_unix": self.last_refresh,
            "refresh_interval_seconds": self.refresh_seconds,
            "errors": self.errors[-5:],
        }
