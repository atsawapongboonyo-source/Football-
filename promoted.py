def promoted_blend_weight(matches_played: int) -> float:
    """Weight retained on prior/lower-league estimate."""
    if matches_played <= 5:
        return 0.80
    if matches_played <= 10:
        return 0.60
    if matches_played <= 20:
        return 0.35
    return 0.10


def blend_strength(prior_strength: float, epl_strength: float, matches_played: int) -> float:
    w = promoted_blend_weight(matches_played)
    return w * prior_strength + (1.0 - w) * epl_strength
