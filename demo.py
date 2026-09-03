import pandas as pd
from .poisson_dc import DixonColesModel


def main():
    # Synthetic round-robin sample only to verify the engine works.
    teams = ["Arsenal","Chelsea","Liverpool","Man City"]
    rows = []
    scores = [(2,1),(1,1),(0,2),(3,1),(1,2),(2,0),(1,0),(2,2),(0,1),(3,0),(1,1),(2,1)]
    k = 0
    for rnd in range(4):
        for i, home in enumerate(teams):
            away = teams[(i+rnd+1)%len(teams)]
            if home == away: continue
            hg, ag = scores[k % len(scores)]; k += 1
            rows.append((f"2026-08-{k:02d}",home,away,hg,ag))
    df = pd.DataFrame(rows, columns=["date","home_team","away_team","home_goals","away_goals"])
    model = DixonColesModel().fit(df)
    print(model.params_["success"], model.params_["rho"])
    print(model.predict("Arsenal", "Chelsea"))

if __name__ == "__main__":
    main()
