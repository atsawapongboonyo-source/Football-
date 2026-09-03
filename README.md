# Fooball v0.4.8 — Fixture Engine Fix

This build keeps the v0.4.7 prediction model unchanged and fixes fixture discovery.

## What changed
- ESPN requests no longer send a custom User-Agent because the public endpoint may reject spoofed/custom headers.
- Keeps Football-Data fixture discovery as a source.
- Adds a confirmed Premier League September 2026 fallback so temporary provider failure does not leave the next-fixtures card empty.
- Merges and de-duplicates providers by date/home/away.
- `/api/fixture-status` shows provider counts and errors.
- `/api/upcoming-fixtures?days=10` should now return confirmed upcoming EPL fixtures when they fall in the window.
- Prediction tracking is still saved only when a genuine future fixture is found.

## Deploy
Upload all files to the GitHub repository root and commit, for example:
`Upgrade Fooball v0.4.8 fixture engine fix`

After Render deploy, test:
- `/health` -> 0.4.8
- `/api/fixture-status`
- `/api/upcoming-fixtures?days=10`

The statistical model itself is unchanged from v0.4.7.
