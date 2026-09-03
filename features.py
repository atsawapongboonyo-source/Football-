import pandas as pd
from .elo import EloTracker


def add_pre_match_elo(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("date").copy()
    tracker = EloTracker()
    home_elos, away_elos, elo_probs = [], [], []
    for r in df.itertuples():
        home_elos.append(tracker.rating(r.home_team))
        away_elos.append(tracker.rating(r.away_team))
        elo_probs.append(tracker.expected_home(r.home_team, r.away_team))
        tracker.update(r.home_team, r.away_team, int(r.home_goals), int(r.away_goals))
    df["home_elo_pre"] = home_elos
    df["away_elo_pre"] = away_elos
    df["elo_home_win_expectation"] = elo_probs
    return df
