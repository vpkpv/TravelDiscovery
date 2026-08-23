import random

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from data import CITIES, CUISINES, MUSIC_GENRES, RESULTS

app = FastAPI(title="TravelDiscovery API (dev)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only — tighten before this ever leaves localhost
    allow_methods=["*"],
    allow_headers=["*"],
)


def _split(param: str | None) -> set[str]:
    return {v for v in (param or "").split(",") if v}


@app.get("/api/cuisines")
def get_cuisines():
    return {"cuisines": CUISINES}


@app.get("/api/music-genres")
def get_music_genres():
    return {"genres": MUSIC_GENRES}


@app.get("/api/cities")
def get_cities(
    q: str = "",
    visited: str | None = Query(default=None, description="comma-separated city ids"),
):
    visited_ids = _split(visited)
    q_lower = q.strip().lower()
    out = []
    for city in CITIES:
        if q_lower and q_lower not in city["name"].lower():
            continue
        is_visited = city["id"] in visited_ids
        out.append({
            "id": city["id"],
            "name": city["name"],
            "country": city["country"],
            "visited": is_visited,
            "pitch": city["return_pitch"] if is_visited else city["first_time_pitch"],
        })
    return {"cities": out}


@app.get("/api/results")
def get_results(city: str, filter: str = "all"):
    items = RESULTS.get(city, [])
    if filter in ("food", "music"):
        items = [i for i in items if i["type"] == filter]
    return {"city": city, "count": len(RESULTS.get(city, [])), "items": items}


@app.get("/api/results/surprise")
def get_surprise(city: str, seed: int = 0):
    items = RESULTS.get(city, [])
    food = [i for i in items if i["type"] == "food"]
    music = [i for i in items if i["type"] == "music"]
    if not food or not music:
        return {"city": city, "items": []}
    rnd = random.Random(seed)
    pick_food = food[seed % len(food)] if seed else rnd.choice(food)
    pick_music = music[(seed * 2 + 1) % len(music)] if seed else rnd.choice(music)
    return {"city": city, "items": [pick_food, pick_music]}
