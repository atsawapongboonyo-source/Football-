# Fooball v0.2 — Match Intelligence

Mobile-first football prediction project. The same backend API is intended to power Web, installable PWA, Android and iOS clients.

## Current build
- FastAPI backend
- Mobile-first web UI
- Installable PWA manifest + service worker
- Dixon–Coles / Poisson prediction endpoint
- 1X2, expected goals, O/U 2.5, BTTS, most-likely score
- EPL team selector
- Data download / preparation modules from v0.1

> Important: v0.2 ships with a deterministic synthetic demo dataset only to validate the UI/API. It must not be treated as a real forecast. The next model milestone is the trained 10-season historical model.

## Run locally
```bash
cd fooball
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000`.

## Mobile/App path
1. PWA: deploy the FastAPI app over HTTPS. Android Chrome can use “Add to Home screen / Install app”.
2. Native: keep `/api/*` unchanged and build an Expo/React Native or Flutter client later.
3. Production model: replace `build_demo_model()` with a serialized trained model loaded from `models/`.
