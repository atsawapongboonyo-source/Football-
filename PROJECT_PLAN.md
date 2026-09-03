# Fooball Roadmap

## Goal
A mobile-first football intelligence product predicting home/draw/away, goals and likely scores from historical statistics.

## Model track
- Up to 10 seasons of Premier League history, recent seasons weighted more heavily.
- Poisson -> Dixon–Coles baseline.
- Elo/team-strength, form, goals, shots and xG where available.
- Promoted clubs: Championship strength adjustment, historical promoted-team prior, Bayesian shrinkage and cross-league Elo.
- Walk-forward: 2016/17–2022/23 train, 2023/24–2024/25 validation, 2025/26 final test, 2026/27 live.
- Bookmaker odds are benchmarking/calibration context, not a core model feature.

## Product track
- v0.1: statistical engine skeleton — done.
- v0.2: FastAPI + mobile web + installable PWA — done.
- v0.3: real 10-season ingestion, training, model persistence, backtest report.
- v0.4: fixtures dashboard, team pages, recent-form cards and richer score distributions.
- v0.5: deployed HTTPS beta usable from a phone.
- v1.0: native Android/iOS shell/client sharing the same Fooball API.
