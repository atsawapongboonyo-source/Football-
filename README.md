# Fooball v0.3 — Render Ready

Real-data milestone for Premier League 2026/27.

## What changed
- Official 2026/27 team roster, including Coventry City, Hull City and Ipswich Town.
- Removed relegated Burnley, West Ham United and Wolverhampton Wanderers.
- Loads EPL match results from Football-Data.co.uk, from 2016/17 through 2026/27.
- Recency weighting.
- Poisson score matrix with Dixon-Coles-style low-score correction.
- Elo adjustment.
- 2025/26 Championship prior for promoted clubs with league-strength adjustment.
- Bookmaker odds are not model inputs.
- Mobile-first UI with working Analyze button.

## Render
Build:
`pip install -r requirements.txt`

Start:
`uvicorn main:app --host 0.0.0.0 --port $PORT`

Root Directory: blank

## Note
First prediction after a cold start may take longer because historical CSV files are downloaded and cached in memory.
