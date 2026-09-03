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
                        "text":f"ยิงได้ {hs['scored']*100:.0f}% · คลีนชีต {hs['cs']*100:.0f}% · สูง 2.5 {hs['over25']*100:.0f}% · BTTS {hs['btts']*100:.0f}%"})
        if av:
            out.append({"title":f"สถิติเกมเยือนของ {away}",
                        "text":f"{away_source} · {av['matches']} นัดล่าสุด: ชนะ {av['wins']} เสมอ {av['draws']} แพ้ {av['losses']} · อัตราชนะ {av['win_rate']*100:.0f}% · ยิงเฉลี่ย {av['gf']:.2f} · เสียเฉลี่ย {av['ga']:.2f} ประตู/นัด"})
            out.append({"title":f"เกมรุก/รับของ {away}",
                        "text":f"ยิงได้ {av['scored']*100:.0f}% · คลีนชีต {av['cs']*100:.0f}% · สูง 2.5 {av['over25']*100:.0f}% · BTTS {av['btts']*100:.0f}%"})
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

    def predict(self, home, away):
        self._ensure_model()
        hr=self.rates.get(home,TeamRates()); ar=self.rates.get(away,TeamRates())
        diff=self.elo.get(home,1500)-self.elo.get(away,1500)

        lam_h=max(.2,min(3.8,self.home_avg*hr.home_attack*ar.away_defense*math.exp(diff/1800)))
        lam_a=max(.15,min(3.5,self.away_avg*ar.away_attack*hr.home_defense*math.exp(-diff/1800)))

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

        home_win=float(np.tril(mat,-1).sum())
        draw=float(np.trace(mat))
        away_win=float(np.triu(mat,1).sum())
        over=float(sum(mat[i,j] for i in range(n+1) for j in range(n+1) if i+j>=3))
        btts=float(sum(mat[i,j] for i in range(1,n+1) for j in range(1,n+1)))

        flat=sorted([(float(mat[i,j]),i,j) for i in range(n+1) for j in range(n+1)],reverse=True)
        top=[{"score":f"{i}–{j}","probability":p} for p,i,j in flat[:3]]

        probs=[(home,home_win),("เสมอ",draw),(away,away_win)]
        view=max(probs,key=lambda x:x[1])[0]

        return {
            "api_version":"0.4.2.1",
            "season":"2026/27",
            "home_team":home,"away_team":away,
            "home_win":home_win,"draw":draw,"away_win":away_win,
            "expected_home_goals":lam_h,"expected_away_goals":lam_a,
            "expected_total_goals":lam_h+lam_a,
            "over_2_5":over,"under_2_5":1-over,"btts_yes":btts,
            "most_likely_score":top[0]["score"],
            "most_likely_score_prob":top[0]["probability"],
            "top_scorelines":top,
            "model_view": "เกมมีแนวโน้มสูสี" if view=="เสมอ" else f"{view} ได้เปรียบ",
            "home_elo":round(self.elo.get(home,1500),1),
            "away_elo":round(self.elo.get(away,1500),1),
            "statistical_evidence":self._evidence(home,away),
            "advanced_stats":self._advanced_stats(home,away),
            "model":"Recency-weighted Poisson + Dixon-Coles + Elo + promoted-team prior",
            "data_source":"Football-Data.co.uk",
            "note":"Expected goals shown here are model-implied goals, not shot-location xG."
        }

    def status(self):
        self._ensure_model()
        s=self.engine.status()
        s.update({"api_version":"0.4.2.1","teams":len(self.current_teams)})
        return s
