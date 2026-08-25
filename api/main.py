import asyncio
import random
from typing import Optional

from dotenv import load_dotenv

load_dotenv()  # picks up api/.env for local dev — see .env.example

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

import places
from data import CITIES, CUISINES, MUSIC_GENRES, RESULTS

app = FastAPI(title="TravelDiscovery API (dev)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only — tighten before this ever leaves localhost
    allow_methods=["*"],
    allow_headers=["*"],
)

_CITY_BY_ID = {c["id"]: c for c in CITIES}


def _split(param: Optional[str]) -> set:
    return {v for v in (param or "").split(",") if v}


def _city_display_name(city_id: str) -> str:
    city = _CITY_BY_ID.get(city_id)
    return city["name"] if city else city_id.replace("-", " ").title()


async def _grounded_items(city_id: str) -> list:
    """The RESULTS mock list for a city, ground-truthed against Google Places
    when a key is configured. A candidate that doesn't resolve to a real
    place (or resolves to one marked permanently closed) is dropped rather
    than shown — see docs/2026-08-20-taste-matched-discovery-design.md.

    Falls back to the raw mock data untouched when no API key is set, so the
    scaffold keeps working for anyone who hasn't configured Places yet.
    """
    items = RESULTS.get(city_id, [])
    if not items or not places.configured():
        return items

    city_name = _city_display_name(city_id)
    grounded = await asyncio.gather(*(places.find_place(i["name"], city_name) for i in items))

    out = []
    for item, ground in zip(items, grounded):
        if not ground:
            continue  # didn't resolve to a real place — drop it
        merged = {**item, "addr": ground["addr"], "place_verified": True}
        if item["type"] == "food" and ground.get("rating") is not None:
            merged["rating"] = ground["rating"]
        out.append(merged)
    return out


@app.get("/api/cuisines")
def get_cuisines():
    return {"cuisines": CUISINES}


@app.get("/api/music-genres")
def get_music_genres():
    return {"genres": MUSIC_GENRES}


@app.get("/api/cities")
async def get_cities(
    q: str = "",
    visited: Optional[str] = Query(default=None, description="comma-separated city ids"),
):
    visited_ids = _split(visited)
    q_stripped = q.strip()

    # Empty query -> the curated "trending for your taste" list. This is
    # editorial, not a Places lookup, so it always comes from the mock list.
    if not q_stripped:
        return {
            "cities": [
                {
                    "id": c["id"],
                    "slug": c["id"],  # curated ids are already slug-shaped
                    "name": c["name"],
                    "country": c["country"],
                    "visited": c["id"] in visited_ids,
                    "pitch": c["return_pitch"] if c["id"] in visited_ids else c["first_time_pitch"],
                }
                for c in CITIES
            ],
            "source": "curated",
        }

    # A typed query: use real autocomplete if configured, else fall back to
    # substring-filtering the same curated list (old behavior). Visited-status
    # and the resulting pitch are matched on `slug`, not `id` — a real Places
    # result's `id` is an opaque place_id, but its `slug` (from the city name)
    # is what lines up with our curated visited-city ids and RESULTS data.
    if places.configured():
        results = await places.autocomplete_cities(q_stripped)
        return {
            "cities": [
                {
                    **r,
                    "visited": r["slug"] in visited_ids,
                    "pitch": "New spots since your last trip" if r["slug"] in visited_ids else "",
                }
                for r in results
            ],
            "source": "places",
        }

    q_lower = q_stripped.lower()
    out = [
        {
            "id": c["id"],
            "slug": c["id"],
            "name": c["name"],
            "country": c["country"],
            "visited": c["id"] in visited_ids,
            "pitch": c["return_pitch"] if c["id"] in visited_ids else c["first_time_pitch"],
        }
        for c in CITIES
        if q_lower in c["name"].lower()
    ]
    return {"cities": out, "source": "curated"}


@app.get("/api/results")
async def get_results(city: str, filter: str = "all"):
    items = await _grounded_items(city)
    if filter in ("food", "music"):
        items = [i for i in items if i["type"] == filter]
    return {"city": city, "count": len(items), "items": items}


@app.get("/api/results/surprise")
async def get_surprise(city: str, seed: int = 0):
    items = await _grounded_items(city)
    food = [i for i in items if i["type"] == "food"]
    music = [i for i in items if i["type"] == "music"]
    if not food or not music:
        return {"city": city, "items": []}
    rnd = random.Random(seed)
    pick_food = food[seed % len(food)] if seed else rnd.choice(food)
    pick_music = music[(seed * 2 + 1) % len(music)] if seed else rnd.choice(music)
    return {"city": city, "items": [pick_food, pick_music]}
