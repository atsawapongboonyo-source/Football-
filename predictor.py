import math
from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd

from data_engine import FootballDataEngine

CURRENT_TEAMS = [
    "AFC Bournemouth", "Arsenal", "Aston Villa", "Brentford",
    "Brighton & Hove Albion", "Chelsea", "Coventry City", "Crystal Palace",
    "Everton", "Fulham", "Hull City", "Ipswich Town", "Leeds United",
    "Liverpool", "Manchester City", "Manchester United", "Newcastle United",
    "Nottingham Forest", "Sunderland", "Tottenham Hotspur",
]
PROMOTED = {"Coventry City","Hull City","Ipswich Town"}

@dataclass
class TeamRates:
    home_attack: float = 1.0
    home_defense: float = 1.0
    away_attack: float = 1.0
    away_defense: float = 1.0

class FooballPredictor:
    def __init__(self):
        self.current_teams = CURRENT_TEAMS
        self.engine = FootballDataEngine()
        self.rates: Dict[str, TeamRates] = {}
        self.elo = {}
        self.home_avg = 1.5
        self.away_avg = 1.2
        self._signature = None

    def _ensure_model(self):
        self.engine.refresh()
        if self.engine.epl.empty:
            raise RuntimeError("ไม่สามารถโหลดข้อมูล Premier League ได้")

        signature = (len(self.engine.epl), self.engine.last_refresh)
        if self._signature == signature and self.rates:
            return

        m = self.engine.epl.copy()
        w = m["recency_weight"].astype(float).to_numpy()
        self.home_avg = float(np.average(m["FTHG"], weights=w))
        self.away_avg = float(np.average(m["FTAG"], weights=w))
        self._fit_rates(m)
        self._fit_elo(m)
        self._apply_promoted_priors()
        self._signature = signature

    def _fit_rates(self, m):
        prior_weight = 7.0
        self.rates = {}
        for team in self.current_teams:
            hm = m[m.HomeTeam==team]
            am = m[m.AwayTeam==team]
            hw, aw = hm.recency_weight.sum(), am.recency_weight.sum()

            hgf = ((hm.FTHG*hm.recency_weight).sum()+prior_weight*self.home_avg)/(hw+prior_weight)
            hga = ((hm.FTAG*hm.recency_weight).sum()+prior_weight*self.away_avg)/(hw+prior_weight)
            agf = ((am.FTAG*am.recency_weight).sum()+prior_weight*self.away_avg)/(aw+prior_weight)
            aga = ((am.FTHG*am.recency_weight).sum()+prior_weight*self.home_avg)/(aw+prior_weight)

            self.rates[team] = TeamRates(
                max(.45,min(2.25,hgf/self.home_avg)),
                max(.45,min(2.25,hga/self.away_avg)),
                max(.45,min(2.25,agf/self.away_avg)),
                max(.45,min(2.25,aga/self.home_avg)),
            )

    def _fit_elo(self, m):
        teams = set(m.HomeTeam)|set(m.AwayTeam)|set(self.current_teams)
        elo = {t:1500.0 for t in teams}
        for _, r in m.iterrows():
            h,a = r.HomeTeam,r.AwayTeam
            rh,ra = elo[h],elo[a]
            eh = 1/(1+10**(-((rh+60)-ra)/400))
            sh = 1 if r.FTHG>r.FTAG else .5 if r.FTHG==r.FTAG else 0
            gd = abs(float(r.FTHG-r.FTAG))
            k = 18*float(r.recency_weight)*(1+.18*min(gd,4))
            d = k*(sh-eh)
            elo[h]+=d; elo[a]-=d
        self.elo = elo

    def _apply_promoted_priors(self):
        c = self.engine.champ
        if c.empty:
            return
        lh, la = c.FTHG.mean(), c.FTAG.mean()
        strength = .82
        epl_current = self.engine.epl[self.engine.epl.season=="2627"]

        for team in PROMOTED:
            hm, am = c[c.HomeTeam==team], c[c.AwayTeam==team]
            if len(hm)+len(am)<10: continue
            prior = TeamRates(
                1+((hm.FTHG.mean()/lh)-1)*strength,
                1+((hm.FTAG.mean()/la)-1)*strength,
                1+((am.FTAG.mean()/la)-1)*strength,
                1+((am.FTHG.mean()/lh)-1)*strength,
            )
            cur = self.rates.get(team,TeamRates())
            n = len(epl_current[(epl_current.HomeTeam==team)|(epl_current.AwayTeam==team)])
            prior_w = .80 if n<=5 else .60 if n<=10 else .35 if n<=20 else .10
            cur_w = 1-prior_w
            self.rates[team] = TeamRates(
                prior_w*prior.home_attack+cur_w*cur.home_attack,
                prior_w*prior.home_defense+cur_w*cur.home_defense,
                prior_w*prior.away_attack+cur_w*cur.away_attack,
                prior_w*prior.away_defense+cur_w*cur.away_defense,
            )

    @staticmethod
    def _poisson(k, lam):
        return math.exp(-lam)*(lam**k)/math.factorial(k)

    def _evidence(self, home, away):
        m = self.engine.epl
        c = self.engine.champ

        def venue(frame, team, venue, n=18):
            if venue=="home":
                x=frame[frame.HomeTeam==team].tail(n); gf="FTHG"; ga="FTAG"
            else:
                x=frame[frame.AwayTeam==team].tail(n); gf="FTAG"; ga="FTHG"
            if x.empty: return None
            G=x[gf].astype(float); A=x[ga].astype(float)
            return dict(matches=len(x), wins=int((G>A).sum()), draws=int((G==A).sum()),
                        losses=int((G<A).sum()), win_rate=float((G>A).mean()),
                        gf=float(G.mean()), ga=float(A.mean()),
                        scored=float((G>0).mean()), cs=float((A==0).mean()),
                        over25=float(((G+A)>=3).mean()), btts=float(((G>0)&(A>0)).mean()))

        def form(frame, team, n=5):
            x=frame[(frame.HomeTeam==team)|(frame.AwayTeam==team)].tail(n)
            if x.empty:return None
            seq=[]; gf=ga=0
            for _,r in x.iterrows():
                home_side=r.HomeTeam==team
                a=float(r.FTHG if home_side else r.FTAG)
                b=float(r.FTAG if home_side else r.FTHG)
                gf+=a; ga+=b
                seq.append("W" if a>b else "D" if a==b else "L")
            return dict(matches=len(x),seq=seq,gf=gf/len(x),ga=ga/len(x))

        def h2h(a,b,n=5):
            x=m[((m.HomeTeam==a)&(m.AwayTeam==b))|((m.HomeTeam==b)&(m.AwayTeam==a))].tail(n)
            if len(x)<2:return None
            aw=dw=bw=0; tg=0
            for _,r in x.iterrows():
                tg+=float(r.FTHG+r.FTAG)
                if r.FTHG==r.FTAG: dw+=1
                else:
                    winner=r.HomeTeam if r.FTHG>r.FTAG else r.AwayTeam
                    aw += winner==a; bw += winner==b
            return dict(matches=len(x),aw=int(aw),dw=dw,bw=int(bw),avg=tg/len(x))

        current=m[m.season=="2627"]
        home_frame,home_source=m,"Premier League"
        away_frame,away_source=m,"Premier League"

        if home in PROMOTED and len(current[(current.HomeTeam==home)|(current.AwayTeam==home)])<5 and not c.empty:
            home_frame,home_source=c,"Championship 2025/26"
        if away in PROMOTED and len(current[(current.HomeTeam==away)|(current.AwayTeam==away)])<5 and not c.empty:
            away_frame,away_source=c,"Championship 2025/26"

        hs=venue(home_frame,home,"home")
        av=venue(away_frame,away,"away")
        hf=form(home_frame,home)
        af=form(away_frame,away)
        hh=h2h(home,away)

        out=[]
        if hs:
            out.append({"title":f"สถิติในบ้านของ {home}",
                        "text":f"{home_source} · {hs['matches']} นัดล่าสุด: ชนะ {hs['wins']} เสมอ {hs['draws']} แพ้ {hs['losses']} · อัตราชนะ {hs['win_rate']*100:.0f}% · ยิงเฉลี่ย {hs['gf']:.2f} · เสียเฉลี่ย {hs['ga']:.2f} ประตู/นัด"})
            out.append({"title":f"เกมรุก/รับของ {home}",
                        "text":f"ยิงได้ {hs['scored']*100:.0f}% · ยิงไม่ได้ {(1-hs['scored'])*100:.0f}% · คลีนชีต {hs['cs']*100:.0f}% · สูง 2.5 {hs['over25']*100:.0f}% · BTTS {hs['btts']*100:.0f}%"})
        if av:
            out.append({"title":f"สถิติเกมเยือนของ {away}",
                        "text":f"{away_source} · {av['matches']} นัดล่าสุด: ชนะ {av['wins']} เสมอ {av['draws']} แพ้ {av['losses']} · อัตราชนะ {av['win_rate']*100:.0f}% · ยิงเฉลี่ย {av['gf']:.2f} · เสียเฉลี่ย {av['ga']:.2f} ประตู/นัด"})
            out.append({"title":f"เกมรุก/รับของ {away}",
                        "text":f"ยิงได้ {av['scored']*100:.0f}% · ยิงไม่ได้ {(1-av['scored'])*100:.0f}% · คลีนชีต {av['cs']*100:.0f}% · สูง 2.5 {av['over25']*100:.0f}% · BTTS {av['btts']*100:.0f}%"})
        if hf:
            out.append({"title":f"ฟอร์ม {hf['matches']} นัดล่าสุดของ {home}",
                        "text":f"{' – '.join(hf['seq'])} · ยิงเฉลี่ย {hf['gf']:.2f} · เสียเฉลี่ย {hf['ga']:.2f}"})
        if af:
            out.append({"title":f"ฟอร์ม {af['matches']} นัดล่าสุดของ {away}",
                        "text":f"{' – '.join(af['seq'])} · ยิงเฉลี่ย {af['gf']:.2f} · เสียเฉลี่ย {af['ga']:.2f}"})
        if hh:
            out.append({"title":"สถิติการพบกันย้อนหลัง",
                        "text":f"{hh['matches']} นัดล่าสุด: {home} ชนะ {hh['aw']} · เสมอ {hh['dw']} · {away} ชนะ {hh['bw']} · ประตูรวมเฉลี่ย {hh['avg']:.2f}"})
        else:
            out.append({"title":"สถิติการพบกันย้อนหลัง",
                        "text":"ข้อมูล H2H ไม่เพียงพอ จึงไม่ให้น้ำหนักส่วนนี้มากเกินไป"})
        return out


    def _goal_engine_context(self, team, venue, n=18):
        """Return venue-specific attack/defence context for the score engine.

        Promoted clubs use the same Championship fallback policy as the evidence
        cards until they have enough current Premier League matches.
        """
        m = self.engine.epl
        c = self.engine.champ
        current = m[m.season=="2627"]
        frame, source = m, "Premier League"
        if team in PROMOTED and len(current[(current.HomeTeam==team)|(current.AwayTeam==team)]) < 5 and not c.empty:
            frame, source = c, "Championship 2025/26"

        if venue == "home":
            x = frame[frame.HomeTeam==team].tail(n).copy()
            gf, ga = "FTHG", "FTAG"
            shots, sot = "HS", "HST"
        else:
            x = frame[frame.AwayTeam==team].tail(n).copy()
            gf, ga = "FTAG", "FTHG"
            shots, sot = "AS", "AST"

        if x.empty:
            return {
                "team": team, "venue": venue, "source": source, "matches": 0,
                "gf": None, "ga": None, "scored": None, "clean_sheet": None,
                "failed_to_score": None, "recent_gf": None, "recent_ga": None,
                "shots": None, "sot": None, "shot_accuracy": None, "conversion": None,
            }

        G = pd.to_numeric(x[gf], errors="coerce").astype(float)
        A = pd.to_numeric(x[ga], errors="coerce").astype(float)
        out = {
            "team": team,
            "venue": venue,
            "source": source,
            "matches": int(len(x)),
            "gf": float(G.mean()),
            "ga": float(A.mean()),
            "scored": float((G > 0).mean()),
            "clean_sheet": float((A == 0).mean()),
            "failed_to_score": float((G == 0).mean()),
            "recent_gf": float(G.tail(5).mean()),
            "recent_ga": float(A.tail(5).mean()),
        }
        sh = pd.to_numeric(x[shots], errors="coerce") if shots in x.columns else pd.Series(dtype=float)
        st = pd.to_numeric(x[sot], errors="coerce") if sot in x.columns else pd.Series(dtype=float)
        out["shots"] = float(sh.mean()) if len(sh) and sh.notna().any() else None
        out["sot"] = float(st.mean()) if len(st) and st.notna().any() else None
        out["shot_accuracy"] = (out["sot"] / out["shots"]) if out.get("shots") not in (None, 0) and out.get("sot") is not None else None
        out["conversion"] = (out["gf"] / out["shots"]) if out.get("shots") not in (None, 0) else None
        return out

    @staticmethod
    def _clip_factor(value, low=.90, high=1.10):
        return max(low, min(high, float(value)))

    def _goal_engine_adjustment(self, home, away, base_home, base_away):
        """Contextual adjustment used before building the score matrix.

        The baseline already contains recency-weighted attack/defence and Elo.
        This layer therefore stays deliberately small to avoid double-counting.
        Clean-sheet and failed-to-score rates are handled separately as a
        zero-goal probability adjustment in the matrix itself.
        """
        hc = self._goal_engine_context(home, "home")
        ac = self._goal_engine_context(away, "away")

        # Recent scoring form: only a modest adjustment around venue baseline.
        h_form = 1.0
        a_form = 1.0
        if hc.get("gf") and hc.get("recent_gf") is not None:
            h_form = self._clip_factor((hc["recent_gf"] + .35) / (hc["gf"] + .35), .92, 1.08)
        if ac.get("gf") and ac.get("recent_gf") is not None:
            a_form = self._clip_factor((ac["recent_gf"] + .35) / (ac["gf"] + .35), .92, 1.08)

        # Shot quality proxy: SOT rate + conversion. Compare each side to a
        # conservative football baseline and cap tightly because these metrics
        # can be noisy over 18 matches.
        def shot_factor(ctx):
            vals=[]
            if ctx.get("shot_accuracy") is not None:
                vals.append(self._clip_factor(ctx["shot_accuracy"] / .33, .95, 1.05))
            if ctx.get("conversion") is not None:
                vals.append(self._clip_factor(ctx["conversion"] / .105, .95, 1.05))
            return float(np.mean(vals)) if vals else 1.0

        h_shot = shot_factor(hc)
        a_shot = shot_factor(ac)
        lam_h = max(.2, min(3.8, base_home * h_form * h_shot))
        lam_a = max(.15, min(3.5, base_away * a_form * a_shot))

        # Target probability that each team scores zero.  Blend the attacking
        # team's failed-to-score rate with the opponent's venue clean-sheet rate.
        # Shrink toward the Poisson baseline to avoid overreacting to small samples.
        base_h0 = math.exp(-lam_h)
        base_a0 = math.exp(-lam_a)
        obs_h0 = np.mean([x for x in [hc.get("failed_to_score"), ac.get("clean_sheet")] if x is not None]) if any(x is not None for x in [hc.get("failed_to_score"), ac.get("clean_sheet")]) else base_h0
        obs_a0 = np.mean([x for x in [ac.get("failed_to_score"), hc.get("clean_sheet")] if x is not None]) if any(x is not None for x in [ac.get("failed_to_score"), hc.get("clean_sheet")]) else base_a0
        # 45% observed venue signal + 55% model baseline.
        target_h0 = .55 * base_h0 + .45 * float(obs_h0)
        target_a0 = .55 * base_a0 + .45 * float(obs_a0)

        return {
            "home": hc,
            "away": ac,
            "base_home_goals": float(base_home),
            "base_away_goals": float(base_away),
            "adjusted_home_goals": float(lam_h),
            "adjusted_away_goals": float(lam_a),
            "home_form_factor": float(h_form),
            "away_form_factor": float(a_form),
            "home_shot_factor": float(h_shot),
            "away_shot_factor": float(a_shot),
            "target_home_zero": float(max(.02, min(.78, target_h0))),
            "target_away_zero": float(max(.02, min(.78, target_a0))),
        }

    @staticmethod
    def _apply_zero_goal_context(mat, target_home_zero, target_away_zero):
        """Reweight 0-goal rows/columns to reflect CS + failed-to-score context."""
        out = mat.copy()
        cur_h0 = float(out[0, :].sum())
        cur_a0 = float(out[:, 0].sum())
        if cur_h0 > 0:
            out[0, :] *= max(.65, min(1.60, target_home_zero / cur_h0))
        if cur_a0 > 0:
            out[:, 0] *= max(.65, min(1.60, target_away_zero / cur_a0))
        total = float(out.sum())
        if total > 0:
            out /= total
        return out


    def _advanced_stats(self, home, away, n=18):
        m = self.engine.epl
        c = self.engine.champ
        current = m[m.season=="2627"]

        def source_for(team):
            if team in PROMOTED and len(current[(current.HomeTeam==team)|(current.AwayTeam==team)]) < 5 and not c.empty:
                return c, "Championship 2025/26"
            return m, "Premier League"

        def profile(team, venue):
            frame, source = source_for(team)
            if venue == "home":
                x = frame[frame.HomeTeam==team].tail(n).copy()
                cols = {"goals":"FTHG","shots":"HS","sot":"HST","corners":"HC","fouls":"HF","yellow":"HY","red":"HR"}
            else:
                x = frame[frame.AwayTeam==team].tail(n).copy()
                cols = {"goals":"FTAG","shots":"AS","sot":"AST","corners":"AC","fouls":"AF","yellow":"AY","red":"AR"}
            if x.empty:
                return {"team":team,"venue":venue,"source":source,"matches":0}

            out={"team":team,"venue":venue,"source":source,"matches":int(len(x))}
            for key,col in cols.items():
                if col in x.columns and x[col].notna().any():
                    out[key] = float(pd.to_numeric(x[col], errors="coerce").mean())
                else:
                    out[key] = None
            if out.get("shots") not in (None,0) and out.get("sot") is not None:
                out["shot_accuracy"] = out["sot"]/out["shots"]
            else:
                out["shot_accuracy"] = None
            if out.get("shots") not in (None,0) and out.get("goals") is not None:
                out["goal_conversion"] = out["goals"]/out["shots"]
            else:
                out["goal_conversion"] = None
            return out

        hp=profile(home,"home")
        ap=profile(away,"away")
        available=[]
        labels={"shots":"จำนวนยิง","sot":"ยิงตรงกรอบ","corners":"เตะมุม","fouls":"ฟาวล์","yellow":"ใบเหลือง","red":"ใบแดง"}
        for k,label in labels.items():
            if hp.get(k) is not None or ap.get(k) is not None:
                available.append(label)

        return {
            "home": hp,
            "away": ap,
            "available_metrics": available,
            "possession_available": False,
            "shot_location_available": False,
            "coverage_note": "Football-Data ชุดปัจจุบันรองรับ Shots, Shots on Target, Corners, Fouls และ Cards ในหลายฤดูกาล; ยังไม่มี possession และตำแหน่งยิงระดับ event/shot-location แบบสม่ำเสมอ จึงยังไม่สร้างค่าปลอมให้โมเดล",
        }


    @staticmethod
    def _goal_probability_interval(probs, coverage=0.80):
        """Discrete equal-tail interval for team goals.

        The previous 68% shortest interval often rendered 0–2 for many different
        lambdas. An 80% equal-tail interval is intentionally broader and easier
        to read as a plausible range rather than a pseudo exact-score forecast.
        """
        probs = [max(0.0, float(x)) for x in probs]
        total = sum(probs) or 1.0
        probs = [x / total for x in probs]
        tail = (1.0 - coverage) / 2.0
        cumulative = 0.0
        lo = 0
        for i, p in enumerate(probs):
            cumulative += p
            if cumulative >= tail:
                lo = i
                break
        cumulative = 0.0
        hi = len(probs) - 1
        for i, p in enumerate(probs):
            cumulative += p
            if cumulative >= 1.0 - tail:
                hi = i
                break
        mass = sum(probs[lo:hi+1])
        return {
            "low": int(lo),
            "high": int(hi),
            "probability": float(mass),
            "target_coverage": float(coverage),
            "method": "equal_tail_discrete",
        }

    def predict(self, home, away):
        self._ensure_model()
        hr=self.rates.get(home,TeamRates()); ar=self.rates.get(away,TeamRates())
        diff=self.elo.get(home,1500)-self.elo.get(away,1500)

        base_lam_h=max(.2,min(3.8,self.home_avg*hr.home_attack*ar.away_defense*math.exp(diff/1800)))
        base_lam_a=max(.15,min(3.5,self.away_avg*ar.away_attack*hr.home_defense*math.exp(-diff/1800)))
        goal_ctx=self._goal_engine_adjustment(home, away, base_lam_h, base_lam_a)
        lam_h=goal_ctx["adjusted_home_goals"]
        lam_a=goal_ctx["adjusted_away_goals"]

        n=8
        mat=np.zeros((n+1,n+1))
        for i in range(n+1):
            for j in range(n+1):
                mat[i,j]=self._poisson(i,lam_h)*self._poisson(j,lam_a)

        rho=-.08
        for (i,j),f in {
            (0,0):1-lam_h*lam_a*rho,
            (0,1):1+lam_h*rho,
            (1,0):1+lam_a*rho,
            (1,1):1-rho,
        }.items():
            mat[i,j]*=max(.5,f)
        mat/=mat.sum()
        # Clean-sheet + failed-to-score context directly changes the mass of
        # 0-goal outcomes rather than merely subtracting from expected goals.
        mat=self._apply_zero_goal_context(mat, goal_ctx["target_home_zero"], goal_ctx["target_away_zero"])

        home_win=float(np.tril(mat,-1).sum())
        draw=float(np.trace(mat))
        away_win=float(np.triu(mat,1).sum())
        over=float(sum(mat[i,j] for i in range(n+1) for j in range(n+1) if i+j>=3))
        btts=float(sum(mat[i,j] for i in range(1,n+1) for j in range(1,n+1)))

        flat=sorted([(float(mat[i,j]),i,j) for i in range(n+1) for j in range(n+1)],reverse=True)
        top=[{"score":f"{i}–{j}","probability":p} for p,i,j in flat[:3]]
        home_goal_probs = mat.sum(axis=1).tolist()
        away_goal_probs = mat.sum(axis=0).tolist()
        home_band = self._goal_probability_interval(home_goal_probs, .80)
        away_band = self._goal_probability_interval(away_goal_probs, .80)
        top3_mass = float(sum(x["probability"] for x in top))

        probs=[(home,home_win),("เสมอ",draw),(away,away_win)]
        view=max(probs,key=lambda x:x[1])[0]

        return {
            "api_version":"0.5.0",
            "season":"2026/27",
            "home_team":home,"away_team":away,
            "home_win":home_win,"draw":draw,"away_win":away_win,
            "expected_home_goals":lam_h,"expected_away_goals":lam_a,
            "expected_total_goals":lam_h+lam_a,
            "over_2_5":over,"under_2_5":1-over,"btts_yes":btts,
            "most_likely_score":top[0]["score"],
            "most_likely_score_prob":top[0]["probability"],
            "top_scorelines":top,
            "goal_prediction_engine": {
                **goal_ctx,
                "predicted_score": top[0]["score"],
                "predicted_score_probability": top[0]["probability"],
                "home_zero_probability": float(mat[0,:].sum()),
                "away_zero_probability": float(mat[:,0].sum()),
                "method_note": "สกอร์คาดการณ์ใช้พลังเกมเหย้า/เยือน + เกมรับคู่แข่ง + ฟอร์มล่าสุด + Shots/SOT/Conversion + Elo และปรับโอกาสยิง 0 ด้วย Clean Sheet และ Failed-to-score; H2H ใช้เป็นบริบทเมื่อตัวอย่างเพียงพอ",
            },
            "score_distribution": {
                "home_goal_band": home_band,
                "away_goal_band": away_band,
                "top3_probability_mass": top3_mass,
                "interval_coverage": 0.80,
                "note": "ช่วงประตูเป็น equal-tail probability interval ประมาณ 80%; สกอร์อันดับ 1 เป็นเพียงสกอร์เดี่ยวที่มีโอกาสสูงสุด ไม่ใช่คำยืนยันผล",
            },
            "model_view": "เกมมีแนวโน้มสูสี" if view=="เสมอ" else f"{view} ได้เปรียบ",
            "home_elo":round(self.elo.get(home,1500),1),
            "away_elo":round(self.elo.get(away,1500),1),
            "statistical_evidence":self._evidence(home,away),
            "advanced_stats":self._advanced_stats(home,away),
            "model":"Recency-weighted Poisson + Dixon-Coles + Elo + promoted-team prior + venue goal context",
            "data_source":"Football-Data.co.uk",
            "note":"Expected goals are model-implied scoring means. Clean-sheet and failed-to-score rates also adjust the probability of 0-goal outcomes; this is not shot-location xG."
        }

    def status(self):
        self._ensure_model()
        s=self.engine.status()
        s.update({"api_version":"0.5.0","teams":len(self.current_teams)})
        return s
