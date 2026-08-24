# TravelDiscovery

Taste-matched travel experience discovery — food & music recommendations grounded in a
user's actual taste (Spotify listening history or manual genre entry, plus a cuisine
preference) and sourced from insider-curated venue data (YouTube food influencers,
verified against Google Places).

See [`docs/2026-08-20-taste-matched-discovery-design.md`](docs/2026-08-20-taste-matched-discovery-design.md)
for the MVP design doc and [`docs/2026-08-23-competitive-landscape.md`](docs/2026-08-23-competitive-landscape.md)
for competitive research.

## Status

Runnable dev scaffold — a real React + FastAPI app implementing the full onboarding →
discovery flow with mock data, in the current focus profile (40/50+: equal-weight
Spotify/manual taste entry, larger type, a "cities already visited" onboarding step).
This is a starting point to iterate on, not a finished product — see "What's stubbed"
below for what still needs real integrations.

## Stack

- `web/` — React (Vite), plain JS/JSX, no router (a 5-step flow driven by local state)
- `api/` — FastAPI, mock in-memory data (`api/data.py`) standing in for the real
  YouTube-transcript → Gemini → Places pipeline described in the design doc

## Running it locally

**Backend:**

```bash
cd api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --port 8000 --reload
```

**Frontend** (separate terminal):

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5173 — the frontend expects the API at `http://localhost:8000`
(override with a `VITE_API_URL` env var / `.env` file in `web/` if you run the API
elsewhere).

### Optional: real Google Places integration

Without any setup, city search and the results feed use the curated mock data in
`api/data.py`. To get real city search (any city, not just the 6 in the mock list) and
real Places grounding (verifying each food/music pick against a real address and rating,
dropping anything that doesn't resolve):

1. In [Google Cloud Console](https://console.cloud.google.com/), create or select a
   project, enable the **Places API** (the classic one — this code calls the legacy REST
   endpoints, not "Places API (New)"), and enable billing on the project (required even
   within the free tier).
2. Create an API key under Credentials, and restrict it to the Places API.
3. `cp api/.env.example api/.env` and paste your key into `GOOGLE_PLACES_API_KEY=`.
4. Restart the backend (`.env` is picked up automatically via `python-dotenv`).

`api/.env` is gitignored — never commit a real key. If something's wrong (bad key,
billing not enabled, API not enabled), the backend logs a clear warning in its terminal
rather than failing silently, and everything falls back to the mock data.

## The flow as built

1. **Welcome** — equal-weight "Connect Spotify" (currently a stub — clicking it just
   advances, no real OAuth) vs. "Tell us what you like" (manual genre picker)
2. **Cuisine quick-pick** — multi-select chips, from `GET /api/cuisines`
3. **Cities already visited** — new step, tap to mark, skippable
4. **City search** — live-filters as you type; a visited city gets a "Been here" tag and
   a "what's new" pitch instead of the first-timer pitch (`GET /api/cities`)
5. **Results feed** — combined food + music picks for the chosen city, with All/Food/Music
   filter pills, a "Something different" (surprise me) action that swaps the list for one
   random food+music pairing, and a per-card save/bookmark toggle (`GET /api/results`,
   `GET /api/results/surprise`)

Only Lisbon has sample result data (`api/data.py`) — every other city returns an empty
list, so the empty state is real and visible rather than papered over.

## What's stubbed vs. real

**Real:** the full UI flow, client/server split, API contract, and all the interactions
above are functioning code you can run and click through today.

**Real, when a `GOOGLE_PLACES_API_KEY` is configured (see above):** city search hits real
Google Places autocomplete instead of the 6-city mock list, and every result-feed pick is
grounded against a real place record (real address, real rating, dropped if it doesn't
resolve to a real, open business).

**Stubbed, needs real work before this is a product:**
- Spotify OAuth (no real connection — see `web/src/screens/Welcome.jsx`)
- Auth / user accounts / the closed-pilot Firestore approval gate described in the design
  doc — nothing here is per-user yet, state lives in `localStorage` on one device
- The actual YouTube transcript → Gemini extraction pipeline that would generate venue
  *candidates* in the first place — `api/data.py`'s venue names/why-copy are still
  hand-written for one city; Places only grounds/verifies those candidates, it doesn't
  discover them
- Persistence — saved/bookmarked picks reset on refresh; nothing is written to a database
- The itinerary screen and rewards-portfolio ideas from the design canvas aren't wired
  into this app yet — they're still exploratory mockups, not scoped for this build

## Design canvas

The full visual exploration (all screen states, the itinerary sketch, age-profile
variants, the rewards-portfolio idea) lives in a separate interactive design canvas
published as a Claude Artifact during this project's design sessions — ask in a Claude
Code session if you need the link again, it isn't tracked in this repo.
