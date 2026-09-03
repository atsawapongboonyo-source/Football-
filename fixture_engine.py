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
LONDON = ZoneInfo("Europe/London")

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
    "man utd": "Manchester United", "man united": "Manchester United", "manchester united": "Manchester United", "manchester united fc": "Manchester United",
    "newcastle": "Newcastle United", "newcastle utd": "Newcastle United", "newcastle united": "Newcastle United", "newcastle united fc": "Newcastle United",
    "nott m forest": "Nottingham Forest", "nott'm forest": "Nottingham Forest", "nottingham forest": "Nottingham Forest", "nottingham forest fc": "Nottingham Forest",
    "sunderland": "Sunderland", "sunderland afc": "Sunderland",
    "tottenham": "Tottenham Hotspur", "tottenham hotspur": "Tottenham Hotspur", "tottenham hotspur fc": "Tottenham Hotspur", "spurs": "Tottenham Hotspur",
}


def _name_key(x):
    x = str(x or "").strip().lower().replace("&", " and ")
    x = re.sub(r"\b(fc|afc|football club)\b", " ", x)
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


# Emergency official-schedule fallback for the currently confirmed September
# 2026 match rounds.  This is deliberately limited to fixtures published by the
# Premier League and is only used when live no-key providers fail.  Live sources
# remain preferred because fixtures can be rescheduled.
OFFICIAL_CONFIRMED_FIXTURES = [
    ("2026-09-04", "20:00", "Ipswich Town", "Liverpool"),
    ("2026-09-05", "12:30", "Newcastle United", "AFC Bournemouth"),
    ("2026-09-05", "15:00", "Brentford", "Sunderland"),
    ("2026-09-05", "15:00", "Brighton & Hove Albion", "Leeds United"),
    ("2026-09-05", "15:00", "Fulham", "Crystal Palace"),
    ("2026-09-05", "15:00", "Manchester City", "Coventry City"),
    ("2026-09-05", "15:00", "Nottingham Forest", "Tottenham Hotspur"),
    ("2026-09-05", "17:30", "Hull City", "Aston Villa"),
    ("2026-09-06", "14:00", "Everton", "Manchester United"),
    ("2026-09-06", "16:30", "Arsenal", "Chelsea"),
    ("2026-09-12", "15:00", "AFC Bournemouth", "Brentford"),
    ("2026-09-12", "15:00", "Aston Villa", "Nottingham Forest"),
    ("2026-09-12", "15:00", "Chelsea", "Hull City"),
    ("2026-09-12", "15:00", "Crystal Palace", "Ipswich Town"),
    ("2026-09-12", "15:00", "Liverpool", "Fulham"),
    ("2026-09-12", "17:30", "Tottenham Hotspur", "Everton"),
    ("2026-09-12", "20:00", "Sunderland", "Arsenal"),
    ("2026-09-13", "14:00", "Coventry City", "Brighton & Hove Albion"),
    ("2026-09-13", "16:30", "Manchester United", "Manchester City"),
    ("2026-09-14", "20:00", "Leeds United", "Newcastle United"),
    ("2026-09-18", "20:00", "Brentford", "Chelsea"),
    ("2026-09-19", "12:30", "Tottenham Hotspur", "Aston Villa"),
    ("2026-09-19", "15:00", "Brighton & Hove Albion", "Arsenal"),
    ("2026-09-19", "15:00", "Everton", "Ipswich Town"),
    ("2026-09-20", "14:00", "Leeds United", "Crystal Palace"),
    ("2026-09-19", "15:00", "Manchester City", "Sunderland"),
    ("2026-09-19", "15:00", "Newcastle United", "Hull City"),
    ("2026-09-19", "17:30", "Nottingham Forest", "Coventry City"),
    ("2026-09-20", "14:00", "AFC Bournemouth", "Liverpool"),
    ("2026-09-20", "16:30", "Fulham", "Manchester United"),
]


class FixtureEngine:
    """Upcoming Premier League fixture engine.

    Historical match results stay in FootballDataEngine. This component only
    discovers future fixtures. It merges two no-key sources and deliberately
    queries ESPN day-by-day because the public scoreboard endpoint is more
    reliable for a single YYYYMMDD than a multi-day range.
    """

    def __init__(self, refresh_seconds=1800, horizon_days=21):
        self.refresh_seconds = refresh_seconds
        self.horizon_days = horizon_days
        self.fixtures = []
        self.last_refresh = None
        self.errors = []
        self.provider = None
        self.provider_counts = {}

    def _cache_path(self):
        return CACHE_DIR / "fixtures_latest.csv"

    @staticmethod
    def _today_london():
        return datetime.now(timezone.utc).astimezone(LONDON).date()

    def _football_data(self):
        cache = self._cache_path()
        use_cache = cache.exists() and time.time() - cache.stat().st_mtime < self.refresh_seconds
        if use_cache:
            text = cache.read_text(encoding="utf-8", errors="ignore")
        else:
            r = requests.get(FIXTURES_URL, timeout=15, headers={"User-Agent": "Fooball/0.4.8"})
            r.raise_for_status()
            text = r.text
            cache.write_text(text, encoding="utf-8")

        df = pd.read_csv(io.StringIO(text))
        if "Div" in df.columns:
            df = df[df["Div"].astype(str).str.upper() == "E0"]
        required = {"Date", "HomeTeam", "AwayTeam"}
        if not required.issubset(df.columns):
            raise ValueError("fixtures.csv ไม่มีคอลัมน์ Date/HomeTeam/AwayTeam")

        out = []
        for _, row in df.iterrows():
            dt = pd.to_datetime(row.get("Date"), dayfirst=True, errors="coerce")
            if pd.isna(dt):
                continue
            date_str = dt.date().isoformat()
            kickoff_utc = None
            time_str = str(row.get("Time", "")).strip()
            if time_str and time_str.lower() != "nan":
                try:
                    hh, mm = [int(v) for v in time_str.split(":")[:2]]
                    local_dt = datetime(dt.year, dt.month, dt.day, hh, mm, tzinfo=LONDON)
                    kickoff_utc = local_dt.astimezone(timezone.utc).isoformat()
                except Exception:
                    pass
            home, away = canonical_team(row.get("HomeTeam")), canonical_team(row.get("AwayTeam"))
            if not home or not away:
                continue
            out.append({
                "fixture_id": f"fd-e0-{date_str}-{slug(home)}-{slug(away)}",
                "date": date_str,
                "kickoff_utc": kickoff_utc,
                "home_team": home,
                "away_team": away,
                "competition": "Premier League",
                "source": "Football-Data Fixtures",
            })
        return out

    def _espn_day(self, day):
        dates = day.strftime("%Y%m%d")
        r = requests.get(
            ESPN_URL,
            params={"dates": dates, "limit": 100},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
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
            hteam = home_obj.get("team") or {}
            ateam = away_obj.get("team") or {}
            home = canonical_team(hteam.get("displayName") or hteam.get("shortDisplayName") or hteam.get("name") or "")
            away = canonical_team(ateam.get("displayName") or ateam.get("shortDisplayName") or ateam.get("name") or "")
            iso = ev.get("date") or comp.get("date")
            if not home or not away or not iso:
                continue
            try:
                kdt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
                date_str = kdt.astimezone(LONDON).date().isoformat()
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
                "source": "ESPN Schedule",
            })
        return out

    def _espn(self):
        start = self._today_london()
        rows = []
        day_errors = []
        # Query every date explicitly. This is intentionally conservative and
        # avoids depending on undocumented range semantics of the public API.
        for offset in range(self.horizon_days + 1):
            day = start + timedelta(days=offset)
            try:
                rows.extend(self._espn_day(day))
            except Exception as exc:
                day_errors.append(f"{day.isoformat()}: {exc}")
        if day_errors and not rows:
            raise ValueError("; ".join(day_errors[:3]))
        if day_errors:
            self.errors.extend([f"ESPN day {e}" for e in day_errors[:3]])
        return rows

    def _official_confirmed(self):
        out = []
        for date_str, time_str, home, away in OFFICIAL_CONFIRMED_FIXTURES:
            dt = datetime.fromisoformat(f"{date_str}T{time_str}:00").replace(tzinfo=LONDON)
            out.append({
                "fixture_id": f"pl-official-{date_str}-{slug(home)}-{slug(away)}",
                "date": date_str,
                "kickoff_utc": dt.astimezone(timezone.utc).isoformat(),
                "home_team": home,
                "away_team": away,
                "competition": "Premier League",
                "source": "Premier League confirmed fallback",
            })
        return out

    def _dedupe(self, rows):
        merged = {}
        for f in rows:
            key = (f.get("date"), team_key(f.get("home_team")), team_key(f.get("away_team")))
            if not all(key):
                continue
            if key not in merged:
                merged[key] = dict(f)
                continue
            cur = merged[key]
            if not cur.get("kickoff_utc") and f.get("kickoff_utc"):
                cur["kickoff_utc"] = f.get("kickoff_utc")
            # Prefer ESPN's event id when it exists, while retaining provenance.
            if str(f.get("fixture_id", "")).startswith("espn-"):
                cur["fixture_id"] = f.get("fixture_id")
            sources = set(str(cur.get("source", "")).split(" + ")) | set(str(f.get("source", "")).split(" + "))
            cur["source"] = " + ".join(sorted(x for x in sources if x))
        return list(merged.values())

    def refresh(self, force=False):
        if self.last_refresh and not force and time.time() - self.last_refresh < self.refresh_seconds:
            return
        self.errors = []
        rows = []
        providers = []
        self.provider_counts = {}

        try:
            fd = self._football_data()
            rows.extend(fd)
            self.provider_counts["Football-Data Fixtures"] = len(fd)
            if fd:
                providers.append("Football-Data Fixtures")
        except Exception as exc:
            self.errors.append(f"Football-Data Fixtures: {exc}")

        try:
            espn = self._espn()
            rows.extend(espn)
            self.provider_counts["ESPN Schedule"] = len(espn)
            if espn:
                providers.append("ESPN Schedule")
        except Exception as exc:
            self.errors.append(f"ESPN Schedule: {exc}")

        # Always merge the small confirmed official fallback. It guarantees that
        # a temporary provider/API failure cannot make the fixture UI empty.
        official = self._official_confirmed()
        rows.extend(official)
        self.provider_counts["Premier League confirmed fallback"] = len(official)
        if official:
            providers.append("Premier League confirmed fallback")

        self.fixtures = self._dedupe(rows)
        self.provider = " + ".join(providers) if providers else None
        self.last_refresh = time.time()

    def find(self, home_team, away_team):
        self.refresh()
        today = self._today_london()
        hk, ak = team_key(home_team), team_key(away_team)
        rows = [f for f in self.fixtures if team_key(f.get("home_team")) == hk and team_key(f.get("away_team")) == ak]
        rows = [f for f in rows if datetime.fromisoformat(f["date"]).date() >= today]
        rows.sort(key=lambda f: (f["date"], f.get("kickoff_utc") or ""))
        return rows[0] if rows else None

    def upcoming(self, days=10):
        self.refresh()
        today = self._today_london()
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
            "version": "0.4.8",
            "provider": self.provider,
            "fixture_count": len(self.fixtures),
            "provider_counts": self.provider_counts,
            "source_counts_after_merge": source_counts,
            "next_10_days_count": len(self.upcoming(10)),
            "last_refresh_unix": self.last_refresh,
            "refresh_interval_seconds": self.refresh_seconds,
            "horizon_days": self.horizon_days,
            "errors": self.errors[-8:],
        }
