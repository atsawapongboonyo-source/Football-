from dataclasses import dataclass, field

@dataclass
class EloTracker:
    base: float = 1500.0
    k: float = 20.0
    home_advantage: float = 60.0
    ratings: dict = field(default_factory=dict)

    def rating(self, team: str) -> float:
        return self.ratings.get(team, self.base)

    def expected_home(self, home: str, away: str) -> float:
        rh = self.rating(home) + self.home_advantage
        ra = self.rating(away)
        return 1.0 / (1.0 + 10 ** ((ra - rh) / 400.0))

    def update(self, home: str, away: str, home_goals: int, away_goals: int):
        exp_h = self.expected_home(home, away)
        if home_goals > away_goals:
            score_h = 1.0
        elif home_goals == away_goals:
            score_h = 0.5
        else:
            score_h = 0.0
        delta = self.k * (score_h - exp_h)
        self.ratings[home] = self.rating(home) + delta
        self.ratings[away] = self.rating(away) - delta
