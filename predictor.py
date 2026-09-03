import io
import math
import time
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import requests

CURRENT_TEAMS = [
    "AFC Bournemouth", "Arsenal", "Aston Villa", "Brentford",
    "Brighton & Hove Albion", "Chelsea", "Coventry City", "Crystal Palace",
    "Everton", "Fulham", "Hull City", "Ipswich Town", "Leeds United",
    "Liverpool", "Manchester City", "Manchester United", "Newcastle United",
    "Nottingham Forest", "Sunderland", "Tottenham Hotspur",
]

PROMOTED = {"Coventry City", "Hull City", "Ipswich Town"}

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

EPL_SEASONS = ["1617","1718","1819","1920","2021","2122","2223","2324","2425","2526","2627"]
BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/E0.csv"
CHAMP_URL = "https://www.football-data.co.uk/mmz4281/2526/E1.csv"

@dataclass
class TeamRates:
    home_attack: float = 1.0
    home_defense: float = 1.0
    away_attack: float = 1.0
    away_defense: float = 1.0

class FooballPredictor:
    def __init__(self):
        self.current_teams = CURRENT_TEAMS
        self.data_mode = "loading-on-first-prediction"
        self._loaded = False
        self._last_refresh = None
        self.rates: Dict[str, TeamRates] = {}
        self.elo: Dict[str, float] = {}
        self.home_avg = 1.52
        self.away_avg = 1.22
        self.matches_loaded = 0
        self.current_matches_loaded = 0
        self.matches = pd.DataFrame()
        self.champ_matches = pd.DataFrame()

    def _name(self, x):
        return FD_NAMES.get(str(x).strip(), str(x).strip())

    def _fetch_csv(self, url, timeout=12):
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Fooball/0.3"})
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text))

    def _load_data(self):
        frames = []
        now_year = 2026
        for idx, season in enumerate(EPL_SEASONS):
            try:
                df = self._fetch_csv(BASE_URL.format(season=season))
            except Exception:
                continue
            required = {"Date","HomeTeam","AwayTeam","FTHG","FTAG"}
            if not required.issubset(df.columns):
                continue
            df = df[list(required)].dropna(subset=["HomeTeam","AwayTeam","FTHG","FTAG"]).copy()
            df["HomeTeam"] = df["HomeTeam"].map(self._name)
            df["AwayTeam"] = df["AwayTeam"].map(self._name)
            df["season_index"] = idx
            # Exponential recency: latest complete/current seasons matter most.
            age = len(EPL_SEASONS) - 1 - idx
            df["weight"] = 0.78 ** age
            # Current-season matches receive an extra bump.
            if season == "2627":
                df["weight"] *= 1.45
                self.current_matches_loaded = len(df)
            frames.append(df)

        if not frames:
            self.data_mode = "fallback-priors"
            self._build_fallback()
            self._loaded = True
            return

        allm = pd.concat(frames, ignore_index=True)
        allm["FTHG"] = pd.to_numeric(allm["FTHG"], errors="coerce")
        allm["FTAG"] = pd.to_numeric(allm["FTAG"], errors="coerce")
        allm = allm.dropna(subset=["FTHG","FTAG"])
        self.matches_loaded = len(allm)
        self.matches = allm.copy()

        w = allm["weight"].to_numpy(float)
        self.home_avg = float(np.average(allm["FTHG"], weights=w))
        self.away_avg = float(np.average(allm["FTAG"], weights=w))

        self._fit_rates(allm)
        self._fit_elo(allm)
        self._apply_promoted_priors()

        self.data_mode = "football-data-live"
        self._last_refresh = time.time()
        self._loaded = True

    def _fit_rates(self, m):
        # Bayesian-like shrinkage via pseudo-match weight.
        prior_weight = 7.0
        for team in self.current_teams:
            hm = m[m.HomeTeam == team]
            am = m[m.AwayTeam == team]

            hw = hm["weight"].sum()
            aw = am["weight"].sum()

            hgf = ((hm["FTHG"] * hm["weight"]).sum() + prior_weight*self.home_avg) / (hw + prior_weight)
            hga = ((hm["FTAG"] * hm["weight"]).sum() + prior_weight*self.away_avg) / (hw + prior_weight)
            agf = ((am["FTAG"] * am["weight"]).sum() + prior_weight*self.away_avg) / (aw + prior_weight)
            aga = ((am["FTHG"] * am["weight"]).sum() + prior_weight*self.home_avg) / (aw + prior_weight)

            self.rates[team] = TeamRates(
                home_attack=max(0.45, min(2.25, hgf/self.home_avg)),
                home_defense=max(0.45, min(2.25, hga/self.away_avg)),
                away_attack=max(0.45, min(2.25, agf/self.away_avg)),
                away_defense=max(0.45, min(2.25, aga/self.home_avg)),
            )

    def _fit_elo(self, m):
        teams = set(m.HomeTeam) | set(m.AwayTeam) | set(self.current_teams)
        elo = {t:1500.0 for t in teams}
        # Preserve chronological season order; within files row order is match order.
        for _, row in m.iterrows():
            h, a = row.HomeTeam, row.AwayTeam
            rh, ra = elo[h], elo[a]
            expected_h = 1/(1 + 10**(-(rh + 60 - ra)/400))
            if row.FTHG > row.FTAG:
                score_h = 1.0
            elif row.FTHG == row.FTAG:
                score_h = 0.5
            else:
                score_h = 0.0
            gd = abs(row.FTHG-row.FTAG)
            margin = 1.0 + 0.18*min(gd,4)
            k = 18 * float(row.weight) * margin
            delta = k*(score_h-expected_h)
            elo[h] += delta
            elo[a] -= delta
        self.elo = elo

    def _apply_promoted_priors(self):
        # Championship 2025/26 is used only to form priors for promoted clubs.
        try:
            c = self._fetch_csv(CHAMP_URL)
            c = c.dropna(subset=["HomeTeam","AwayTeam","FTHG","FTAG"]).copy()
            c["HomeTeam"] = c["HomeTeam"].map(self._name)
            c["AwayTeam"] = c["AwayTeam"].map(self._name)
            c["FTHG"] = pd.to_numeric(c["FTHG"], errors="coerce")
            c["FTAG"] = pd.to_numeric(c["FTAG"], errors="coerce")
            c = c.dropna(subset=["FTHG","FTAG"])
            self.champ_matches = c.copy()
            league_home = c["FTHG"].mean()
            league_away = c["FTAG"].mean()
            league_strength = 0.82

            for team in PROMOTED:
                hm = c[c.HomeTeam == team]
                am = c[c.AwayTeam == team]
                if len(hm)+len(am) < 10:
                    continue
                ch = TeamRates(
                    home_attack=((hm.FTHG.mean()/league_home)-1)*league_strength + 1,
                    home_defense=((hm.FTAG.mean()/league_away)-1)*league_strength + 1,
                    away_attack=((am.FTAG.mean()/league_away)-1)*league_strength + 1,
                    away_defense=((am.FTHG.mean()/league_home)-1)*league_strength + 1,
                )
                current = self.rates.get(team, TeamRates())
                # Early-season mix: 80% prior, 20% current EPL evidence.
                n_current = int(((c.iloc[:0]).shape[0]))
                # Count handled approximately through current season data availability.
                blend_prior = 0.80 if self.current_matches_loaded <= 20 else 0.60
                blend_cur = 1-blend_prior
                self.rates[team] = TeamRates(
                    home_attack=blend_prior*ch.home_attack + blend_cur*current.home_attack,
                    home_defense=blend_prior*ch.home_defense + blend_cur*current.home_defense,
                    away_attack=blend_prior*ch.away_attack + blend_cur*current.away_attack,
                    away_defense=blend_prior*ch.away_defense + blend_cur*current.away_defense,
                )
                # Promoted teams get a conservative cross-league Elo prior.
                perf = ((hm.FTHG.mean()-hm.FTAG.mean()) + (am.FTAG.mean()-am.FTHG.mean()))/2
                self.elo[team] = 1480 + max(-35, min(55, perf*28))
        except Exception:
            pass

    def _build_fallback(self):
        self.rates = {t:TeamRates() for t in self.current_teams}
        self.elo = {t:1500.0 for t in self.current_teams}

    def _ensure(self):
        if not self._loaded:
            self._load_data()

    @staticmethod
    def _poisson(k, lam):
        return math.exp(-lam) * (lam**k) / math.factorial(k)

    def _team_evidence(self, home, away):
        if self.matches.empty:
            return []

        epl = self.matches.copy()

        def venue_stats(frame, team, venue, n=18):
            if venue == "home":
                x = frame[frame.HomeTeam == team].tail(n)
                gf_col, ga_col = "FTHG", "FTAG"
            else:
                x = frame[frame.AwayTeam == team].tail(n)
                gf_col, ga_col = "FTAG", "FTHG"
            if x.empty:
                return None
            gf = x[gf_col].astype(float)
            ga = x[ga_col].astype(float)
            wins = int((gf > ga).sum())
            draws = int((gf == ga).sum())
            losses = int((gf < ga).sum())
            return {
                "matches": len(x),
                "wins": wins, "draws": draws, "losses": losses,
                "win_rate": wins/len(x),
                "gf": float(gf.mean()),
                "ga": float(ga.mean()),
                "scored_rate": float((gf > 0).mean()),
                "clean_sheet": float((ga == 0).mean()),
                "over25": float(((gf+ga) >= 3).mean()),
                "btts": float(((gf > 0) & (ga > 0)).mean()),
            }

        def last_form(frame, team, n=5):
            x = frame[(frame.HomeTeam == team) | (frame.AwayTeam == team)].tail(n)
            if x.empty:
                return None
            sequence, gf, ga = [], 0.0, 0.0
            for _, r in x.iterrows():
                is_home = r.HomeTeam == team
                tgf = float(r.FTHG if is_home else r.FTAG)
                tga = float(r.FTAG if is_home else r.FTHG)
                gf += tgf; ga += tga
                sequence.append("W" if tgf > tga else "D" if tgf == tga else "L")
            return {
                "matches": len(x),
                "sequence": sequence,
                "wins": sequence.count("W"),
                "draws": sequence.count("D"),
                "losses": sequence.count("L"),
                "gf": gf/len(x), "ga": ga/len(x)
            }

        def h2h(a, b, n=5):
            x = epl[((epl.HomeTeam == a)&(epl.AwayTeam == b)) |
                    ((epl.HomeTeam == b)&(epl.AwayTeam == a))].tail(n)
            if x.empty:
                return None
            aw=dw=bw=0
            total_goals = 0.0
            for _, r in x.iterrows():
                total_goals += float(r.FTHG + r.FTAG)
                if r.FTHG == r.FTAG:
                    dw += 1
                else:
                    winner = r.HomeTeam if r.FTHG > r.FTAG else r.AwayTeam
                    if winner == a: aw += 1
                    elif winner == b: bw += 1
            return {
                "matches":len(x), "home_team_wins":aw, "draws":dw,
                "away_team_wins":bw, "avg_goals":total_goals/len(x)
            }

        # EPL evidence first. For promoted clubs with too little EPL evidence,
        # use their real 2025/26 Championship venue/form record and label it clearly.
        home_frame, home_source = epl, "Premier League"
        away_frame, away_source = epl, "Premier League"

        epl_home_count = len(epl[epl.HomeTeam == home])
        epl_away_count = len(epl[epl.AwayTeam == away])

        if home in PROMOTED and epl_home_count < 5 and not self.champ_matches.empty:
            home_frame, home_source = self.champ_matches, "Championship 2025/26"
        if away in PROMOTED and epl_away_count < 5 and not self.champ_matches.empty:
            away_frame, away_source = self.champ_matches, "Championship 2025/26"

        hs = venue_stats(home_frame, home, "home")
        av = venue_stats(away_frame, away, "away")
        hf = last_form(home_frame, home)
        af = last_form(away_frame, away)
        head = h2h(home, away)

        evidence = []
        if hs:
            evidence.append({
                "title": f"สถิติในบ้านของ {home}",
                "text": (
                    f"{home_source} · {hs['matches']} นัดล่าสุด: ชนะ {hs['wins']} เสมอ {hs['draws']} แพ้ {hs['losses']} "
                    f"· อัตราชนะ {hs['win_rate']*100:.0f}% · ยิงเฉลี่ย {hs['gf']:.2f} · เสียเฉลี่ย {hs['ga']:.2f} ประตู/นัด"
                )
            })
            evidence.append({
                "title": f"ประสิทธิภาพเกมรุก/รับของ {home}",
                "text": (
                    f"ยิงได้อย่างน้อย 1 ประตู {hs['scored_rate']*100:.0f}% · คลีนชีต {hs['clean_sheet']*100:.0f}% "
                    f"· สูง 2.5 ประตู {hs['over25']*100:.0f}% · BTTS {hs['btts']*100:.0f}%"
                )
            })

        if av:
            evidence.append({
                "title": f"สถิติเกมเยือนของ {away}",
                "text": (
                    f"{away_source} · {av['matches']} นัดล่าสุด: ชนะ {av['wins']} เสมอ {av['draws']} แพ้ {av['losses']} "
                    f"· อัตราชนะ {av['win_rate']*100:.0f}% · ยิงเฉลี่ย {av['gf']:.2f} · เสียเฉลี่ย {av['ga']:.2f} ประตู/นัด"
                )
            })
            evidence.append({
                "title": f"ประสิทธิภาพเกมรุก/รับของ {away}",
                "text": (
                    f"ยิงได้อย่างน้อย 1 ประตู {av['scored_rate']*100:.0f}% · คลีนชีต {av['clean_sheet']*100:.0f}% "
                    f"· สูง 2.5 ประตู {av['over25']*100:.0f}% · BTTS {av['btts']*100:.0f}%"
                )
            })

        if hf:
            evidence.append({
                "title": f"ฟอร์ม {hf['matches']} นัดล่าสุดของ {home}",
                "text": f"{' – '.join(hf['sequence'])} · ยิงเฉลี่ย {hf['gf']:.2f} · เสียเฉลี่ย {hf['ga']:.2f} ประตู/นัด"
            })
        if af:
            evidence.append({
                "title": f"ฟอร์ม {af['matches']} นัดล่าสุดของ {away}",
                "text": f"{' – '.join(af['sequence'])} · ยิงเฉลี่ย {af['gf']:.2f} · เสียเฉลี่ย {af['ga']:.2f} ประตู/นัด"
            })

        if head and head["matches"] >= 2:
            evidence.append({
                "title": "สถิติการพบกันย้อนหลัง",
                "text": (
                    f"{head['matches']} นัดล่าสุด: {home} ชนะ {head['home_team_wins']} · เสมอ {head['draws']} "
                    f"· {away} ชนะ {head['away_team_wins']} · ประตูรวมเฉลี่ย {head['avg_goals']:.2f} ลูก/นัด"
                )
            })
        else:
            evidence.append({
                "title": "สถิติการพบกันย้อนหลัง",
                "text": "ยังมีข้อมูลการพบกันโดยตรงไม่เพียงพอ จึงไม่ให้น้ำหนัก H2H มากเกินไป"
            })

        if home in PROMOTED or away in PROMOTED:
            promoted = home if home in PROMOTED else away
            evidence.append({
                "title": f"การประเมินทีมน้องใหม่: {promoted}",
                "text": (
                    "ช่วงต้นฤดูกาลใช้ผลงาน Championship 2025/26 เป็น prior แล้วลดน้ำหนักลงเมื่อมีข้อมูล "
                    "Premier League 2026/27 มากขึ้น เพื่อไม่ให้ทีมที่เพิ่งเลื่อนชั้นเสียเปรียบเพราะมีข้อมูล EPL น้อย"
                )
            })

        return evidence

    def predict(self, home, away):
        self._ensure()
        hr = self.rates.get(home, TeamRates())
        ar = self.rates.get(away, TeamRates())

        base_h = self.home_avg * hr.home_attack * ar.away_defense
        base_a = self.away_avg * ar.away_attack * hr.home_defense

        # Elo adjustment is intentionally modest; core remains football performance data.
        elo_diff = self.elo.get(home,1500)-self.elo.get(away,1500)
        elo_mult_h = math.exp(elo_diff/1800)
        elo_mult_a = math.exp(-elo_diff/1800)
        lam_h = max(0.20, min(3.8, base_h*elo_mult_h))
        lam_a = max(0.15, min(3.5, base_a*elo_mult_a))

        max_goals = 8
        mat = np.zeros((max_goals+1,max_goals+1), dtype=float)
        for i in range(max_goals+1):
            for j in range(max_goals+1):
                mat[i,j] = self._poisson(i,lam_h)*self._poisson(j,lam_a)

        # Dixon-Coles-style low-score correction.
        rho = -0.08
        tau = {
            (0,0): 1 - lam_h*lam_a*rho,
            (0,1): 1 + lam_h*rho,
            (1,0): 1 + lam_a*rho,
            (1,1): 1 - rho,
        }
        for (i,j), factor in tau.items():
            mat[i,j] *= max(0.5, factor)
        mat /= mat.sum()

        home_win = float(np.tril(mat,-1).sum())
        draw = float(np.trace(mat))
        away_win = float(np.triu(mat,1).sum())
        over25 = float(sum(mat[i,j] for i in range(max_goals+1) for j in range(max_goals+1) if i+j>=3))
        btts = float(sum(mat[i,j] for i in range(1,max_goals+1) for j in range(1,max_goals+1)))
        idx = np.unravel_index(np.argmax(mat), mat.shape)
        score_prob = float(mat[idx])

        flat = []
        for i in range(max_goals+1):
            for j in range(max_goals+1):
                flat.append((float(mat[i,j]), i, j))
        flat.sort(reverse=True, key=lambda x: x[0])
        top_scorelines = [
            {"score": f"{i}–{j}", "probability": prob}
            for prob, i, j in flat[:3]
        ]

        statistical_evidence = self._team_evidence(home, away)

        reasons = []
        if abs(elo_diff) >= 35:
            stronger = home if elo_diff > 0 else away
            reasons.append(f"{stronger} มีคะแนนความแข็งแกร่ง Elo สูงกว่า")
        reasons.append(f"โมเดลคำนึงถึงความได้เปรียบจากการเล่นในบ้าน โดยค่าเฉลี่ยประตูเจ้าบ้านในข้อมูลอยู่ที่ {self.home_avg:.2f} ประตู")
        if home in PROMOTED or away in PROMOTED:
            reasons.append("มีทีมน้องใหม่ในคู่นี้ จึงนำผลงาน Championship 2025/26 มาปรับเทียบกับระดับ Premier League")
        if self.current_matches_loaded:
            reasons.append(f"ใช้ผลการแข่งขัน Premier League 2026/27 ที่มีในฐานข้อมูลแล้ว {self.current_matches_loaded} นัด")

        return {
            "season":"2026/27",
            "home_team":home,
            "away_team":away,
            "home_win":home_win,
            "draw":draw,
            "away_win":away_win,
            "expected_home_goals":lam_h,
            "expected_away_goals":lam_a,
            "expected_total_goals":lam_h+lam_a,
            "over_2_5":over25,
            "under_2_5":1-over25,
            "btts_yes":btts,
            "most_likely_score":f"{idx[0]}–{idx[1]}",
            "most_likely_score_prob":score_prob,
            "top_scorelines":top_scorelines,
            "home_elo":round(self.elo.get(home,1500),1),
            "away_elo":round(self.elo.get(away,1500),1),
            "reasons":reasons,
            "statistical_evidence":statistical_evidence,
            "model":"Recency-weighted Poisson + Dixon-Coles low-score adjustment + Elo + promoted-team prior",
            "data_source":"Football-Data.co.uk; Premier League official team list used for 2026/27 roster",
            "note":"Bookmaker odds are not used as model inputs."
        }

    def status(self):
        if not self._loaded:
            return {
                "loaded":False,
                "mode":self.data_mode,
                "message":"Real match data loads on the first prediction."
            }
        return {
            "loaded":True,
            "mode":self.data_mode,
            "matches_loaded":self.matches_loaded,
            "current_season_matches":self.current_matches_loaded,
            "last_refresh_unix":self._last_refresh,
        }
