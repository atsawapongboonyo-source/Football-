from dataclasses import dataclass
import math
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

@dataclass
class DixonColesModel:
    teams: list | None = None
    params_: dict | None = None
    l2: float = 0.02

    def fit(self, df):
        teams = sorted(set(df.home_team) | set(df.away_team))
        self.teams = teams
        idx = {t:i for i,t in enumerate(teams)}
        n = len(teams)
        x0 = np.zeros(2*n + 2)
        x0[2*n] = 0.20
        x0[2*n+1] = -0.05

        def unpack(x):
            return x[:n], x[n:2*n], x[2*n], x[2*n+1]

        def tau(x, y, lam, mu, rho):
            if x == 0 and y == 0: return 1 - lam*mu*rho
            if x == 0 and y == 1: return 1 + lam*rho
            if x == 1 and y == 0: return 1 + mu*rho
            if x == 1 and y == 1: return 1 - rho
            return 1.0

        def objective(x):
            attack, defence, home_adv, rho = unpack(x)
            ll = 0.0
            for r in df.itertuples(index=False):
                hi, ai = idx[r.home_team], idx[r.away_team]
                lam = math.exp(home_adv + attack[hi] - defence[ai])
                mu  = math.exp(attack[ai] - defence[hi])
                t = tau(int(r.home_goals), int(r.away_goals), lam, mu, rho)
                if t <= 0:
                    return 1e12
                ll += poisson.logpmf(r.home_goals, lam) + poisson.logpmf(r.away_goals, mu) + math.log(t)
            ident = 1000.0 * (attack.mean() ** 2)
            reg = self.l2 * (np.square(attack).sum() + np.square(defence).sum())
            return -ll + ident + reg

        bounds = [(-3, 3)] * (2*n) + [(-1, 1), (-0.20, 0.20)]
        res = minimize(objective, x0, method="L-BFGS-B", bounds=bounds, options={"maxiter": 1000})
        attack, defence, home_adv, rho = unpack(res.x)
        self.params_ = {
            "attack": {t: float(attack[idx[t]]) for t in teams},
            "defence": {t: float(defence[idx[t]]) for t in teams},
            "home_adv": float(home_adv),
            "rho": float(rho),
            "success": bool(res.success),
            "optimizer_message": str(res.message),
        }
        return self

    def expected_goals(self, home, away):
        if self.params_ is None:
            raise RuntimeError("Fit the model first")
        p = self.params_
        if home not in p["attack"] or away not in p["attack"]:
            raise KeyError("Unknown team. Use promoted-team prior before prediction.")
        lam = math.exp(p["home_adv"] + p["attack"][home] - p["defence"][away])
        mu = math.exp(p["attack"][away] - p["defence"][home])
        return lam, mu

    def score_matrix(self, home, away, max_goals=10):
        lam, mu = self.expected_goals(home, away)
        h = poisson.pmf(np.arange(max_goals+1), lam)
        a = poisson.pmf(np.arange(max_goals+1), mu)
        m = np.outer(h, a)
        rho = self.params_["rho"]
        m[0,0] *= max(1-lam*mu*rho, 0)
        m[0,1] *= max(1+lam*rho, 0)
        m[1,0] *= max(1+mu*rho, 0)
        m[1,1] *= max(1-rho, 0)
        m /= m.sum()
        return m

    def predict(self, home, away, max_goals=10):
        m = self.score_matrix(home, away, max_goals)
        home_win = float(np.tril(m, -1).sum())
        draw = float(np.trace(m))
        away_win = float(np.triu(m, 1).sum())
        best = np.unravel_index(np.argmax(m), m.shape)
        lam, mu = self.expected_goals(home, away)
        total_goals = np.add.outer(np.arange(m.shape[0]), np.arange(m.shape[1]))
        over25 = float(m[total_goals >= 3].sum())
        btts = float(m[1:,1:].sum())
        return {
            "home": home,
            "away": away,
            "home_win": home_win,
            "draw": draw,
            "away_win": away_win,
            "expected_home_goals": lam,
            "expected_away_goals": mu,
            "expected_total_goals": lam + mu,
            "over_2_5": over25,
            "under_2_5": 1.0 - over25,
            "btts_yes": btts,
            "btts_no": 1.0 - btts,
            "most_likely_score": f"{best[0]}-{best[1]}",
            "most_likely_score_prob": float(m[best]),
        }
