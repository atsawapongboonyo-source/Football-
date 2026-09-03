import math
import numpy as np
import pandas as pd
from data_engine import FootballDataEngine

def result_class(hg,ag):
    return "H" if hg>ag else "D" if hg==ag else "A"

def run_backtest(test_season="2526"):
    eng=FootballDataEngine()
    eng.refresh()
    data=eng.epl.copy()
    test=data[data.season==test_season]
    train=data[data.season!=test_season]

    if test.empty or train.empty:
        return {"error":"ข้อมูลไม่เพียงพอ"}

    home_avg=train.FTHG.mean()
    away_avg=train.FTAG.mean()
    correct=0
    brier=[]
    rows=[]

    for _,r in test.iterrows():
        # lightweight team-strength estimate using only prior-season training set
        hm=train[train.HomeTeam==r.HomeTeam].tail(38)
        am=train[train.AwayTeam==r.HomeTeam].tail(38)
        ha=train[train.HomeTeam==r.AwayTeam].tail(38)
        aa=train[train.AwayTeam==r.AwayTeam].tail(38)

        h_att=(hm.FTHG.mean()/home_avg) if len(hm)>=5 else 1
        h_def=(hm.FTAG.mean()/away_avg) if len(hm)>=5 else 1
        a_att=(aa.FTAG.mean()/away_avg) if len(aa)>=5 else 1
        a_def=(aa.FTHG.mean()/home_avg) if len(aa)>=5 else 1

        lh=max(.2,min(3.8,home_avg*h_att*a_def))
        la=max(.15,min(3.5,away_avg*a_att*h_def))

        mat=np.zeros((9,9))
        for i in range(9):
            for j in range(9):
                mat[i,j]=math.exp(-lh)*lh**i/math.factorial(i)*math.exp(-la)*la**j/math.factorial(j)
        mat/=mat.sum()
        pH=float(np.tril(mat,-1).sum()); pD=float(np.trace(mat)); pA=float(np.triu(mat,1).sum())
        pred=max([("H",pH),("D",pD),("A",pA)],key=lambda x:x[1])[0]
        actual=result_class(r.FTHG,r.FTAG)
        correct += pred==actual
        y=np.array([1,0,0]) if actual=="H" else np.array([0,1,0]) if actual=="D" else np.array([0,0,1])
        p=np.array([pH,pD,pA])
        brier.append(float(((p-y)**2).sum()))
        rows.append((pred,actual))

    return {
        "test_season":test_season,
        "matches":len(test),
        "1x2_accuracy":correct/len(test),
        "brier_score":sum(brier)/len(brier),
        "note":"Baseline walk-forward checkpoint; v0.4.1 will add full chronological refit and calibration."
    }

if __name__=="__main__":
    print(run_backtest())
