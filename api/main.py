import asyncio
import json
import logging
import math
import os
import random
import secrets
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from dotenv import load_dotenv

load_dotenv()  # picks up api/.env for local dev — see .env.example

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from firebase_admin import firestore
from pydantic import BaseModel

import auth
import curated_food
import places
import spotify
from data import CITIES, CUISINES, MUSIC_GENRES, RESULTS

log = logging.getLogger("main")

app = FastAPI(title="TravelDiscovery API (dev)")

# Below this many real food items, top up with curated_food's Gemini
# suggestions (see _grounded_items) — a city with exactly one chef-matched
# pick is still too thin to feel like "matched to your taste", not just a
# city with literally zero.
MIN_FOOD_ITEMS = 8


def _merge_ingested_items(items: list, city_lookup: dict) -> None:
    """Shared by both loaders below: merges a flat list of ingested venue
    dicts into RESULTS, grouped by city slug, deduped against whatever's
    already there (curated data or an earlier video covering the same
    venue).
    """
    for i, item in enumerate(items):
        city = item.get("city") or city_lookup.get(item.get("source_video_id"))
        if not city:
            log.warning("skipping ingested item with no attributable city: %r", item.get("name"))
            continue
        slug = places._slugify(city)
        existing = RESULTS.setdefault(slug, [])
        if any(e["name"].lower() == item["name"].lower() for e in existing):
            continue
        entry = {
            "id": f"ingest-{slug}-{i}",
            "type": item["type"],
            "name": item["name"],
            "meta": item["meta"],
            "addr": item["addr"],
            "why": item["why"],
            # Already went through Places grounding once during ingest —
            # _grounded_items skips re-verifying anything with this set,
            # so it isn't re-searched (and potentially dropped by a
            # different fuzzy-match result) on every single request.
            "place_verified": True,
        }
        if item.get("rating") is not None:
            entry["rating"] = item["rating"]
        if item.get("photo_ref"):
            entry["photo_ref"] = item["photo_ref"]
        if item.get("cuisine"):
            entry["cuisine"] = item["cuisine"]
        if item.get("lat") is not None and item.get("lng") is not None:
            entry["lat"] = item["lat"]
            entry["lng"] = item["lng"]
        existing.append(entry)


# True only after a genuine Firestore read error (network blip, transient
# permission issue, etc.) — never after a legitimately empty collection,
# which is a real, stable state with nothing worth retrying. Cloud Run can
# run several container instances at once, each loading this exactly once
# at cold start; without tracking this and retrying, one instance hitting
# a transient error at startup used to stay silently empty for every city,
# for its entire lifetime, while other instances worked fine — confirmed
# live: identical requests for the same city intermittently came back
# with zero picks depending on which instance handled them.
_ingested_load_failed = False


def _load_ingested_results_from_firestore() -> bool:
    """Reads every venues/{slug} doc (written by `python -m ingest.run`
    once AUTH_ENABLED/Firestore is set up) and merges its items into
    RESULTS. Returns False (so the caller falls back to the local file) on
    any failure, AND when the collection is simply empty — turning
    AUTH_ENABLED on doesn't retroactively migrate anything already sitting
    in a local output.json; without this, a real deploy hit exactly that:
    Firestore reachable but never written to yet, silently serving zero
    ingested venues for every city instead of falling back.
    """
    global _ingested_load_failed
    try:
        docs = list(auth.firestore_client().collection("venues").stream())
        if not docs:
            _ingested_load_failed = False
            return False
        flat = []
        for doc in docs:
            data = doc.to_dict() or {}
            for item in data.get("items", []):
                flat.append({**item, "city": item.get("city") or data.get("city")})
        _merge_ingested_items(flat, {})
        _ingested_load_failed = False
        return True
    except Exception as exc:
        log.warning("Firestore venue load failed, falling back to local output.json: %s", exc)
        _ingested_load_failed = True
        return False


def _load_ingested_results_from_file() -> None:
    """Merges ingest/output.json (written by `python -m ingest.run` before
    Firestore storage existed, or still today when AUTH_ENABLED isn't set)
    into RESULTS. A missing file is a no-op — the curated Lisbon set keeps
    working either way.
    """
    output_path = Path(__file__).resolve().parent / "ingest" / "output.json"
    if not output_path.exists():
        return
    try:
        items = json.loads(output_path.read_text())
    except (OSError, ValueError) as exc:
        log.warning("couldn't read %s: %s", output_path, exc)
        return

    # Runs from before pipeline.py tagged each item with "city" only carry
    # source_video_id — reconstruct the city from ingest/run.py's VIDEOS
    # list so an already-generated output.json still loads without a rerun.
    try:
        from ingest.run import VIDEOS
        video_city = {v["video_id"]: v["city"] for v in VIDEOS}
    except ImportError:
        video_city = {}

    _merge_ingested_items(items, video_city)


def _load_ingested_results() -> None:
    if not (auth.configured() and _load_ingested_results_from_firestore()):
        _load_ingested_results_from_file()


def _ensure_ingested_results_loaded() -> None:
    """Called at the top of every request that needs RESULTS — a one-shot
    load at cold start (below) has no way to recover from a transient
    Firestore error on its own. Retries at most once per request, and only
    when the last attempt actually errored (see _ingested_load_failed) —
    a real empty collection isn't retried, there's nothing to find there.
    """
    if _ingested_load_failed and auth.configured():
        _load_ingested_results_from_firestore()


_load_ingested_results()

# "*" (the default, dev-friendly) or a comma-separated allowlist, e.g.
# ALLOWED_ORIGINS=https://travel-web-xyz.a.run.app — set once the web
# service's URL is known, to stop any origin from calling this API.
_allowed = os.environ.get("ALLOWED_ORIGINS", "*").strip()
_origins = ["*"] if _allowed == "*" else [o.strip() for o in _allowed.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Where to send the browser back to once Spotify OAuth finishes. Defaults to
# localhost for local dev; set to the deployed web service's URL in prod.
WEB_URL = os.environ.get("WEB_URL", "http://localhost:5173").rstrip("/")


@app.get("/auth/spotify/login")
def spotify_login(popup: bool = Query(default=False)):
    """Kicks off the OAuth flow: a full browser redirect to Spotify's
    consent screen, not a fetch — Spotify won't authorize inside an XHR.

    `popup=1` marks this as opened in a popup window rather than navigating
    the main app tab — see App.jsx's connectSpotify. That distinction rides
    along in `state` (echoed back verbatim by Spotify) since there's nowhere
    server-side to stash it between these two requests. No user-session
    store exists yet (that's Firebase+Firestore, tracked separately), so the
    rest of `state` is a CSRF nonce only, not verified against anything
    stored server-side. Acceptable for now: worth revisiting once real user
    accounts exist.
    """
    if not spotify.configured():
        return RedirectResponse(f"{WEB_URL}/?spotify_error=not_configured")
    nonce = secrets.token_urlsafe(16)
    state = f"popup:{nonce}" if popup else f"redirect:{nonce}"
    return RedirectResponse(spotify.authorize_url(state))


@app.get("/auth/spotify/callback")
async def spotify_callback(code: str = "", error: str = "", state: str = ""):
    """Spotify redirects here after the user approves/denies. Exchanges the
    code, reads top artists, and hands the result back to the web app —
    redirected to a tiny static handoff page (spotify-popup-done.html,
    served by the web app itself) if this came from a popup (see
    spotify_login), else the original full-redirect-with-query-string
    handoff, for callers that predate the popup flow or whose popup got
    blocked. There's no session to store the result in yet, so it's passed
    through directly either way.

    Popup mode used to render an inline page here that called
    window.opener.postMessage() directly from the API's own origin —
    confirmed live: on iOS Safari, window.open() often produces a plain new
    tab rather than a true child popup window, and window.opener on that
    tab wasn't reliable for messaging back (the app tab just sat frozen,
    never advancing past "Connect Spotify"). Redirecting to a page on the
    web app's own origin instead lets that page use localStorage + the
    'storage' event to hand the result to the app tab — same-origin
    browser tabs can always see each other's storage, with no dependency on
    the opener relationship surviving the popup's multi-hop navigation
    (our domain -> spotify.com -> our domain again).

    Artist names, not a genre bucket: Spotify's Web API returns an empty
    `genres` field on essentially every artist in practice, so there's no
    genre data to map onto our fixed vocabulary. Names are always present.
    """
    is_popup = state.startswith("popup:")

    def _finish(*, artists: Optional[list] = None, error_code: str = ""):
        if is_popup:
            query = {"error": error_code} if error_code else {"artists": json.dumps(artists)}
            return RedirectResponse(f"{WEB_URL}/spotify-popup-done.html?{urlencode(query)}")
        if error_code:
            return RedirectResponse(f"{WEB_URL}/?spotify_error={error_code}")
        return RedirectResponse(f"{WEB_URL}/?{urlencode({'spotify_artists': json.dumps(artists)})}")

    if error or not code:
        return _finish(error_code="denied")

    token = await spotify.exchange_code(code)
    if not token:
        return _finish(error_code="token_exchange_failed")

    artists = await spotify.top_artists(token)
    if not artists:
        log.warning("Spotify auth succeeded but no top artists were returned")
        return _finish(error_code="no_artists_found")

    return _finish(artists=artists)

_CITY_BY_ID = {c["id"]: c for c in CITIES}


def _split(param: Optional[str]) -> set:
    return {v for v in (param or "").split(",") if v}


def _city_display_name(city_id: str) -> str:
    city = _CITY_BY_ID.get(city_id)
    return city["name"] if city else city_id.replace("-", " ").title()


def _city_country(city_id: str) -> str:
    city = _CITY_BY_ID.get(city_id)
    return city["country"] if city else ""


async def _grounded_items(
    city_id: str, music_genre: str = "", chefs: Optional[list] = None, cuisines: Optional[list] = None
) -> list:
    """The RESULTS mock list for a city, ground-truthed against Google Places
    when a key is configured. A candidate that doesn't resolve to a real
    place (or resolves to one marked permanently closed) is dropped rather
    than shown — see docs/2026-08-20-taste-matched-discovery-design.md.

    Falls back to the raw mock data untouched when no API key is set, so the
    scaffold keeps working for anyone who hasn't configured Places yet.

    Music picks only exist at all for Lisbon (hand-written) — no city has a
    music-venue content pipeline, ingested or otherwise. So for any city
    with zero music items after the above, this supplements with real
    live-music venues straight from Places (see places.find_music_venues) —
    these are the venues themselves, not candidates needing grounding.
    `music_genre`, when it's one of the fixed vocabulary values (only
    meaningful for the manual taste-entry path — Spotify's artist-name
    signal has no genre to key off), biases which kind of venue gets found.

    `chefs`, when given (manually typed, see FavoriteChefs.jsx), supplements
    the food list with any real restaurant Places finds for that chef/foodie
    account's name in this city — see places.find_chef_venues.

    A city with fewer than MIN_FOOD_ITEMS real food picks after everything
    above (curated/ingested content plus any chef matches — could be zero,
    could be a single thin chef match) gets topped up from curated_food.
    suggest_venues — Gemini's own restaurant suggestions, ground-truthed
    against Places the same as every other candidate in this app (an
    ungrounded suggestion is dropped like any other, and a suggestion that
    duplicates an existing pick by name is skipped). `cuisines` (the
    onboarding quick-pick) biases what it suggests. This only *adds*, never
    replaces — real curated/ingested picks are always kept as-is.

    `cuisines`, when given, also actually filters the final food list down
    to items tagged with one of those cuisines (every extraction path
    tags cuisine at ingestion time — see ingest/extract.py, curated_food.py)
    — confirmed live: before this filter existed, picking "Indian" still
    showed non-Indian restaurants, since the quick-pick only ever biased
    suggestions rather than filtering anything. A favorite-chef match
    (`chef_match`) is exempt from this filter: an explicit favorite is a
    stronger signal than the cuisine quick-pick and shouldn't be hidden by
    it. Music items are never affected either way.
    """
    _ensure_ingested_results_loaded()

    items = RESULTS.get(city_id, [])
    to_verify = [i for i in items if not i.get("place_verified")]
    already_verified = [i for i in items if i.get("place_verified")]

    if to_verify and places.configured():
        city_name = _city_display_name(city_id)
        country = _city_country(city_id)
        grounded = await asyncio.gather(*(places.find_place(i["name"], city_name, country) for i in to_verify))

        out = []
        for item, ground in zip(to_verify, grounded):
            if not ground:
                continue  # didn't resolve to a real place — drop it
            merged = {**item, "addr": ground["addr"], "place_verified": True}
            if item["type"] == "food" and ground.get("rating") is not None:
                merged["rating"] = ground["rating"]
            if ground.get("photo_ref"):
                merged["photo_ref"] = ground["photo_ref"]
            out.append(merged)
        to_verify = out

    items = already_verified + to_verify

    if places.configured() and not any(i["type"] == "music" for i in items):
        city_name = _city_display_name(city_id)
        venues = await places.find_music_venues(city_name, music_genre, country=_city_country(city_id))
        items = items + [
            {
                "id": v["place_id"] or f"places-music-{city_id}-{i}",
                "type": "music",
                "name": v["name"],
                "meta": v["genre"],
                "genre": v["genre"],
                "addr": v["addr"],
                "rating": v["rating"],
                "why": (
                    f"A real, Google-verified {v['genre'].lower()} spot in {city_name}"
                    if music_genre
                    else f"A real, Google-verified live-music spot in {city_name}"
                ),
                "place_verified": True,
                **({"photo_ref": v["photo_ref"]} if v.get("photo_ref") else {}),
            }
            for i, v in enumerate(venues)
        ]

    # Bars/speakeasies — same live-Places top-up as music above, since
    # there's no ingest content pipeline for this category either.
    if places.configured() and not any(i["type"] == "bar" for i in items):
        city_name = _city_display_name(city_id)
        bars = await places.find_bars_venues(city_name, country=_city_country(city_id))
        items = items + [
            {
                "id": b["place_id"] or f"places-bar-{city_id}-{i}",
                "type": "bar",
                "name": b["name"],
                "meta": "Bar",
                "addr": b["addr"],
                "rating": b["rating"],
                "why": f"A real, Google-verified bar/speakeasy pick in {city_name}",
                "place_verified": True,
                **({"photo_ref": b["photo_ref"]} if b.get("photo_ref") else {}),
                **({"lat": b["lat"], "lng": b["lng"]} if b.get("lat") is not None and b.get("lng") is not None else {}),
            }
            for i, b in enumerate(bars)
        ]

    if places.configured() and chefs:
        city_name = _city_display_name(city_id)
        chef_venues = await places.find_chef_venues(city_name, chefs, country=_city_country(city_id))
        existing_names = {i["name"].lower() for i in items}

        def _chef_meta_why(v: dict) -> tuple:
            if v["match_type"] == "own_restaurant":
                return f"{v['chef']}'s restaurant", f"This is {v['chef']}'s own restaurant in {city_name}."
            # similar_style: no restaurant of the original typed entry here,
            # so say so honestly rather than implying an endorsement that
            # doesn't exist. `chef` was resolved from `original_input` (e.g.
            # a restaurant name resolves to its head chef) — name both when
            # they differ so it's clear why an unrelated-looking result
            # showed up for what was typed.
            original = v.get("original_input", v["chef"])
            if not v["chef"]:
                # Gemini didn't recognize the original entry as a specific
                # real chef/restaurant — only inferred a plausible cuisine
                # style from its name (see chef_style.resolve_chef_style),
                # so don't invent a chef identity that was never actually
                # found; a small/local place like this is the common case,
                # not the exception.
                return (
                    f"In the style of {original}",
                    f"We don't have a specific match for \"{original}\" in {city_name}, but "
                    f"this looks like a similar {v['style']} spot.",
                )
            if original.lower() == v["chef"].lower():
                return (
                    f"In the style of {v['chef']}",
                    f"{v['chef']} doesn't have a restaurant in {city_name}, but this matches their "
                    f"{v['style']} style.",
                )
            return (
                f"In the style of {original}",
                f"{original} doesn't have a location in {city_name}, but this matches "
                f"{v['chef']}'s {v['style']} style.",
            )

        items = items + [
            {
                "id": v["place_id"] or f"places-chef-{city_id}-{i}",
                "type": "food",
                "name": v["name"],
                "meta": _chef_meta_why(v)[0],
                "addr": v["addr"],
                "why": _chef_meta_why(v)[1],
                "place_verified": True,
                # Exempts this from the cuisine filter below — an explicit
                # favorite (a named chef/restaurant) is a stronger signal
                # than the cuisine quick-pick, so it shouldn't get hidden
                # just because it happens to be a different cuisine than
                # what was picked.
                "chef_match": True,
                **({"rating": v["rating"]} if v.get("rating") is not None else {}),
                **({"photo_ref": v["photo_ref"]} if v.get("photo_ref") else {}),
            }
            for i, v in enumerate(chef_venues)
            if v["name"].lower() not in existing_names
        ]

    # Counts only what would actually survive the cuisine filter below (a
    # chef_match always would; anything else needs a matching cuisine tag),
    # not the city's total food count — confirmed live: New York had ~9
    # total food items, well above MIN_FOOD_ITEMS, so this top-up never
    # fired even though only 1 of those 9 happened to be tagged Indian and
    # the user had picked only Indian. Same wanted-set logic as the filter
    # itself, so a suggestion generated here (already biased toward the
    # selected cuisines) reliably passes it afterward.
    if cuisines:
        wanted_cuisines = {c.strip().lower() for c in cuisines}
        food_count = sum(
            1 for i in items
            if i["type"] == "food"
            and (i.get("chef_match") or (i.get("cuisine") or "").strip().lower() in wanted_cuisines)
        )
    else:
        food_count = sum(1 for i in items if i["type"] == "food")

    if places.configured() and curated_food.configured() and food_count < MIN_FOOD_ITEMS:
        city_name = _city_display_name(city_id)
        country = _city_country(city_id)
        existing_names = {i["name"].lower() for i in items}
        # suggest_venues makes a synchronous (blocking) Gemini SDK call —
        # run it off the event loop so a slow Gemini response doesn't
        # freeze every other concurrent request this server is handling.
        # Ask for more than MIN_FOOD_ITEMS when a cuisine filter is active:
        # the filter below only keeps suggestions genuinely tagged with a
        # wanted cuisine, and grounding drops some outright — asking for
        # only MIN_FOOD_ITEMS-worth here reliably left the final count well
        # under it once both of those losses were accounted for.
        suggestion_limit = 16 if cuisines else 10
        suggestions = await asyncio.to_thread(curated_food.suggest_venues, city_name, cuisines or [], suggestion_limit)
        grounded = await asyncio.gather(*(places.find_place(s["name"], city_name, country) for s in suggestions))
        items = items + [
            {
                "id": ground["place_id"] or f"llm-food-{city_id}-{i}",
                "type": "food",
                "name": s["name"],
                "meta": "Suggested pick",
                "addr": ground["addr"],
                "why": s["why"],
                "cuisine": s.get("cuisine", ""),
                "place_verified": True,
                **({"rating": ground["rating"]} if ground.get("rating") is not None else {}),
                **({"photo_ref": ground["photo_ref"]} if ground.get("photo_ref") else {}),
                **({"lat": ground["lat"], "lng": ground["lng"]} if ground.get("lat") is not None and ground.get("lng") is not None else {}),
            }
            for i, (s, ground) in enumerate(zip(suggestions, grounded))
            if ground and s["name"].lower() not in existing_names
        ]

    if cuisines:
        # Only food items are subject to this — music is untouched, and a
        # chef_match (an explicit favorite) is exempt (see where it's set,
        # above) since it's a stronger signal than this quick-pick. Any
        # food item with no cuisine tag at all (a venue ingested before
        # this field existed and not yet backfilled) is treated the same
        # as "Other" — excluded once a specific cuisine is selected, same
        # as anything else that doesn't match.
        wanted_cuisines = {c.strip().lower() for c in cuisines}
        items = [
            i for i in items
            if i["type"] != "food" or i.get("chef_match") or (i.get("cuisine") or "").strip().lower() in wanted_cuisines
        ]

    return items


# _grounded_items does several sequential network round trips per call
# (Places grounding, a live-music search, a chef search, and — often, since
# MIN_FOOD_ITEMS was raised — a Gemini top-up call plus grounding for each
# of its suggestions), and none of that changes between one request for a
# city/filter combo and the next one moments later — content only changes
# when `python -m ingest.run` runs, at most a few times a day. Confirmed
# live: this was the main driver behind "performance is still a big issue"
# reports, since every single page load re-did all of it from scratch, per
# instance, with nothing to show for the repeat work. A short in-memory TTL
# turns every request after the first (per Cloud Run instance) into a
# straight dict lookup instead. Per-instance and lost on redeploy/restart is
# fine here — it's a speed optimization, not a source of truth.
_RESULTS_CACHE_TTL = 900  # seconds
_results_cache: dict = {}
_city_photo_cache: dict = {}


async def _cached_grounded_items(
    city_id: str, music_genre: str = "", chefs: Optional[list] = None, cuisines: Optional[list] = None
) -> list:
    key = (city_id, music_genre, tuple(sorted(chefs or [])), tuple(sorted(cuisines or [])))
    now = time.monotonic()
    cached = _results_cache.get(key)
    if cached and now - cached[0] < _RESULTS_CACHE_TTL:
        return cached[1]
    items = await _grounded_items(city_id, music_genre, chefs, cuisines)
    _results_cache[key] = (now, items)
    return items


async def _cached_city_photo(city_id: str) -> Optional[str]:
    now = time.monotonic()
    cached = _city_photo_cache.get(city_id)
    if cached and now - cached[0] < _RESULTS_CACHE_TTL:
        return cached[1]
    ref = await places.find_city_photo(_city_display_name(city_id), _city_country(city_id))
    _city_photo_cache[city_id] = (now, ref)
    return ref


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


_DISTANCE_RANKED_TYPES = {"food", "bar"}


async def _rank_by_trip_distance(items: list, trip_id: str, uid: str) -> list:
    """Orders food and bar picks by distance from the trip's base address
    (the hotel) — "a restaurant itinerary around where the hotel booking
    is," with bars brought up to the same treatment (confirmed live: bars
    were passing through unranked, a second-class citizen next to food).
    Combines the backlog's distance-ranking story with the base address
    captured at trip setup. Picks missing lat/lng (chef-venue matches
    never carry it, and an ingested food venue only gets it once
    re-grounded after this field was added — see pipeline.py's
    GROUNDING_REFRESH_DAYS) sort after every measured pick rather than
    being dropped — an unmeasured distance isn't evidence it's far away.
    Music items and an unknown/base-address-less trip are left untouched.
    """
    doc = _trips_collection(uid).document(trip_id).get()
    if not doc.exists:
        return items
    trip = doc.to_dict()
    base_lat, base_lng = trip.get("base_lat"), trip.get("base_lng")
    if base_lat is None or base_lng is None:
        return items

    other = [i for i in items if i["type"] not in _DISTANCE_RANKED_TYPES]
    measured, unmeasured = [], []
    for i in items:
        if i["type"] not in _DISTANCE_RANKED_TYPES:
            continue
        if i.get("lat") is None or i.get("lng") is None:
            unmeasured.append(i)
        else:
            measured.append((_haversine_km(base_lat, base_lng, i["lat"], i["lng"]), i))
    measured.sort(key=lambda pair: pair[0])

    ranked = [{**i, "distance_km": round(d, 2)} for d, i in measured] + unmeasured
    return ranked + other


@app.get("/api/me")
async def get_me(authorization: str = Header(default="")):
    """Reports auth/approval status without raising — unlike the
    auth.current_user dependency used on the data endpoints below, this
    always returns 200 so the frontend can render the right screen (no
    login needed, please sign in, or waiting on approval) instead of
    treating every non-approved state as an error to recover from.
    """
    if not auth.configured():
        return {"auth_enabled": False, "signed_in": True, "approved": True}

    if not authorization.startswith("Bearer "):
        return {"auth_enabled": True, "signed_in": False}

    user = await auth.verify_token(authorization.removeprefix("Bearer ").strip())
    if not user:
        return {"auth_enabled": True, "signed_in": False}

    approved = auth.is_approved(user["uid"])
    if approved:
        # A lightweight usage signal — AuthGate.jsx calls /api/me once per
        # sign-in/session, so this is roughly "last time this person opened
        # the app." See approve_users.py for a way to check it.
        auth.touch_last_active(user["uid"])

    return {
        "auth_enabled": True,
        "signed_in": True,
        "uid": user["uid"],
        "email": user["email"],
        "approved": approved,
    }


@app.post("/api/tokens")
async def create_token(user: dict = Depends(auth.current_user)):
    """Mints a personal access token for the MCP server (see
    mcp_server.py) to authenticate as this already-approved user. Shown
    once in the response — there's no way to retrieve it again, only mint
    a new one. Requires AUTH_ENABLED (the current_user dependency 403s
    otherwise-anonymous callers aren't "approved").
    """
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    return {"token": auth.mint_token(user["uid"])}


class PrefsBody(BaseModel):
    prefs: dict


@app.get("/api/prefs")
async def get_prefs(user: dict = Depends(auth.current_user)):
    """Cross-device sync for onboarding preferences (taste method, cuisines,
    favorite chefs, visited cities, ...) — keyed by the signed-in Firebase
    uid, so a device with no localStorage of its own (or one that's been
    cleared) still picks up where the account left off, instead of these
    being stuck in a single browser. Requires AUTH_ENABLED — same reasoning
    as /api/tokens: with no real uid to key on, there's no meaningful way
    to scope this per-account.
    """
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    doc = auth.firestore_client().collection("user_prefs").document(user["uid"]).get()
    return {"prefs": doc.to_dict() if doc.exists else None}


@app.post("/api/prefs")
async def save_prefs(body: PrefsBody, user: dict = Depends(auth.current_user)):
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    auth.firestore_client().collection("user_prefs").document(user["uid"]).set(body.prefs)
    return {"ok": True}


class SavedItemBody(BaseModel):
    item: dict


@app.get("/api/saved")
async def get_saved(user: dict = Depends(auth.current_user)):
    """Cross-device/session persistence for saved picks — a browsable
    history across cities and trips, not the in-page-only toggle that
    used to vanish the moment the tab closed (see ResultsFeed.jsx). Same
    auth-required reasoning as /api/prefs: with no real uid to key on,
    there's no meaningful way to scope this per-account.
    """
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    doc = auth.firestore_client().collection("saved_picks").document(user["uid"]).get()
    return {"items": doc.to_dict().get("items", {}) if doc.exists else {}}


@app.put("/api/saved/{item_id}")
async def save_item(item_id: str, body: SavedItemBody, user: dict = Depends(auth.current_user)):
    """Upserts one saved item, keyed by its own id within the user's single
    saved_picks doc — merge=True so this never touches any other saved
    item, only ever adding/replacing this one key.
    """
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    ref = auth.firestore_client().collection("saved_picks").document(user["uid"])
    ref.set({"items": {item_id: body.item}}, merge=True)
    return {"ok": True}


@app.delete("/api/saved/{item_id}")
async def unsave_item(item_id: str, user: dict = Depends(auth.current_user)):
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    ref = auth.firestore_client().collection("saved_picks").document(user["uid"])
    try:
        ref.update({f"items.{item_id}": firestore.DELETE_FIELD})
    except Exception:
        pass  # nothing to delete (no doc yet) — same end state either way
    return {"ok": True}


class TripBody(BaseModel):
    city: str
    start_date: str  # "YYYY-MM-DD" — plain date, no time/timezone needed for a trip
    end_date: str
    base_address: str
    party_size: int = 1


def _trips_collection(uid: str):
    return auth.firestore_client().collection("users").document(uid).collection("trips")


@app.get("/api/trips")
async def list_trips(user: dict = Depends(auth.current_user)):
    """A user's saved trips — trip planning's foundational story (see the
    Product Backlog artifact's "Trips" epic). Stored under
    users/{uid}/trips, the target per-user subcollection shape (see
    CLAUDE.md's Current scope section), not bolted onto the flat
    user_prefs doc the onboarding quick-picks use — a trip needs its own
    id to hang anchor events, time slots, and scores off of later.
    """
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    docs = _trips_collection(user["uid"]).order_by("start_date").stream()
    return {"trips": [{"id": d.id, **d.to_dict()} for d in docs]}


async def _geocoded_trip_data(body: TripBody) -> dict:
    """body's fields plus base_lat/base_lng when the base address resolves
    — the distance-ranking story (_rank_by_trip_distance) needs real
    coordinates for the hotel, not just the free-text address the user
    typed. Best-effort: an address that doesn't geocode just means
    distance ranking falls back to showing everything unranked, same as
    a Places-not-configured dev setup.
    """
    data = body.model_dump()
    if places.configured():
        geo = await places.geocode_address(body.base_address)
        if geo:
            data["base_lat"] = geo["lat"]
            data["base_lng"] = geo["lng"]
    return data


@app.post("/api/trips")
async def create_trip(body: TripBody, user: dict = Depends(auth.current_user)):
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    data = await _geocoded_trip_data(body)
    ref = _trips_collection(user["uid"]).document()
    ref.set(data)
    return {"id": ref.id, **data}


@app.get("/api/trips/{trip_id}")
async def get_trip(trip_id: str, user: dict = Depends(auth.current_user)):
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    doc = _trips_collection(user["uid"]).document(trip_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="trip not found")
    return {"id": doc.id, **doc.to_dict()}


@app.put("/api/trips/{trip_id}")
async def update_trip(trip_id: str, body: TripBody, user: dict = Depends(auth.current_user)):
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    ref = _trips_collection(user["uid"]).document(trip_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="trip not found")
    data = await _geocoded_trip_data(body)
    ref.set(data)
    return {"id": trip_id, **data}


@app.delete("/api/trips/{trip_id}")
async def delete_trip(trip_id: str, user: dict = Depends(auth.current_user)):
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    _trips_collection(user["uid"]).document(trip_id).delete()
    return {"ok": True}


class AnchorEventBody(BaseModel):
    venue_name: str
    start_time: str  # ISO datetime (e.g. "2026-11-03T19:30") — a specific moment, not just a date


@app.put("/api/trips/{trip_id}/anchor")
async def set_anchor_event(trip_id: str, body: AnchorEventBody, user: dict = Depends(auth.current_user)):
    """The trip's anchor — a concert, show, or reservation the rest of the
    trip gets planned around (see the Product Backlog's "Anchor event"
    story; "Done when: the concert shows on the LA trip"). Grounded
    against Places when possible, same mechanism as every other venue in
    this app, so the next story (distance/slot-aware ranking) has a real
    address to compute walking distance from without needing to touch
    this again. Not subject to CLAUDE.md's drop-if-ungrounded rule,
    though — that rule is about venues *we* recommend; an anchor is the
    user's own plan, so it's saved either way, just without a resolved
    address if grounding doesn't find a match.
    """
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    ref = _trips_collection(user["uid"]).document(trip_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="trip not found")
    trip = doc.to_dict()

    ground = {}
    if places.configured():
        ground = await places.find_place(
            body.venue_name, _city_display_name(trip.get("city", "")), _city_country(trip.get("city", ""))
        )
    anchor = {
        "venue_name": body.venue_name,
        "start_time": body.start_time,
        "addr": ground.get("addr", ""),
        "place_id": ground.get("place_id", ""),
    }
    ref.update({"anchor": anchor})
    return {"id": trip_id, **trip, "anchor": anchor}


@app.delete("/api/trips/{trip_id}/anchor")
async def clear_anchor_event(trip_id: str, user: dict = Depends(auth.current_user)):
    if not auth.configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    ref = _trips_collection(user["uid"]).document(trip_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="trip not found")
    ref.update({"anchor": firestore.DELETE_FIELD})
    return {"ok": True}


@app.get("/api/cuisines")
def get_cuisines():
    return {"cuisines": CUISINES}


@app.get("/api/music-genres")
def get_music_genres():
    return {"genres": MUSIC_GENRES}


@app.get("/api/photo")
async def get_photo(ref: str, w: int = 400):
    """Proxies a Places photo (see places.photo_media) so the browser never
    sees our Places API key — an <img src="/api/photo?ref=...">  hits this
    instead of a Places URL with the key attached as a query param.

    Deliberately not behind auth.current_user: an <img> tag can't attach an
    Authorization header without extra client-side plumbing (fetch + blob
    URL), and `ref` is an opaque Places resource name only ever handed out
    by the already-gated /api/results and /api/results/surprise, so there's
    nothing meaningful to discover by guessing at this endpoint.
    """
    result = await places.photo_media(ref, max_width=w)
    if not result:
        raise HTTPException(status_code=404, detail="photo not found")
    content, content_type = result
    return Response(content=content, media_type=content_type, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/cities")
async def get_cities(
    q: str = "",
    visited: Optional[str] = Query(default=None, description="comma-separated city ids"),
    _user: dict = Depends(auth.current_user),
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
async def get_results(
    city: str, filter: str = "all", music_genre: str = "", chefs: str = "", cuisines: str = "", trip_id: str = "",
    user: dict = Depends(auth.current_user),
):
    # Run together, not sequentially — the city photo is unrelated to which
    # venues get returned, just an extra Places lookup for ResultsFeed's
    # header banner (see places.find_city_photo).
    items, city_photo_ref = await asyncio.gather(
        _cached_grounded_items(city, music_genre, list(_split(chefs)), list(_split(cuisines))),
        _cached_city_photo(city),
    )
    # trip_id, when given, orders food picks by distance from the trip's
    # base address (the hotel) — see _rank_by_trip_distance. Applied before
    # the filter below so "food only" and "all" both reflect the same order.
    if trip_id and auth.configured():
        items = await _rank_by_trip_distance(items, trip_id, user["uid"])
    if filter in ("food", "music", "bar"):
        items = [i for i in items if i["type"] == filter]
    return {"city": city, "count": len(items), "items": items, "city_photo_ref": city_photo_ref}


@app.get("/api/results/surprise")
async def get_surprise(
    city: str, seed: int = 0, music_genre: str = "", chefs: str = "", cuisines: str = "",
    _user: dict = Depends(auth.current_user),
):
    items = await _cached_grounded_items(city, music_genre, list(_split(chefs)), list(_split(cuisines)))
    # Bars are an equally valid "main pick" alongside food now, not a
    # second-class category only food got to be — see _DISTANCE_RANKED_TYPES.
    food_or_bar = [i for i in items if i["type"] in _DISTANCE_RANKED_TYPES]
    music = [i for i in items if i["type"] == "music"]
    if not food_or_bar or not music:
        return {"city": city, "items": []}
    rnd = random.Random(seed)
    pick_main = food_or_bar[seed % len(food_or_bar)] if seed else rnd.choice(food_or_bar)
    pick_music = music[(seed * 2 + 1) % len(music)] if seed else rnd.choice(music)
    return {"city": city, "items": [pick_main, pick_music]}
