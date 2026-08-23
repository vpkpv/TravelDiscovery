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

**Stubbed, needs real work before this is a product:**
- Spotify OAuth (no real connection — see `web/src/screens/Welcome.jsx`)
- Auth / user accounts / the closed-pilot Firestore approval gate described in the design
  doc — nothing here is per-user yet, state lives in `localStorage` on one device
- The actual YouTube transcript → Gemini extraction → Google Places grounding pipeline —
  `api/data.py` is hand-written placeholder data for one city
- Persistence — saved/bookmarked picks reset on refresh; nothing is written to a database
- The itinerary screen and rewards-portfolio ideas from the design canvas aren't wired
  into this app yet — they're still exploratory mockups, not scoped for this build

## Design canvas

The full visual exploration (all screen states, the itinerary sketch, age-profile
variants, the rewards-portfolio idea) lives in a separate interactive design canvas
published as a Claude Artifact during this project's design sessions — ask in a Claude
Code session if you need the link again, it isn't tracked in this repo.
