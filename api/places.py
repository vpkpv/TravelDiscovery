"""Thin wrapper around the Google Places (legacy) REST API.

Two calls: city autocomplete for the "where are you headed?" search box, and
find-place for grounding a candidate venue name against a real place record
(address, rating, open/closed) — the mechanism described in the design doc
for dropping hallucinated or defunct venues.

Every function returns None (or an empty list) on any failure — missing key,
network error, zero results — so callers can fall back to mock data without
extra try/except noise at each call site.
"""

import logging
import os

import httpx

API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
BASE = "https://maps.googleapis.com/maps/api/place"

log = logging.getLogger("places")


def configured() -> bool:
    return bool(API_KEY)


def _slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


async def autocomplete_cities(query: str) -> list:
    """Real-world city search. Returns [{id, name, country}, ...]."""
    if not configured() or not query.strip():
        return []
    params = {
        "input": query,
        "types": "(cities)",
        "key": API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BASE}/autocomplete/json", params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("autocomplete request failed: %s", exc)
        return []

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        log.warning(
            "autocomplete status=%s error_message=%r — check your API key, billing, and that "
            "the Places API is enabled",
            data.get("status"), data.get("error_message"),
        )
        return []

    out = []
    for pred in data.get("predictions", []):
        structured = pred.get("structured_formatting", {})
        name = structured.get("main_text") or pred.get("description", "")
        country = structured.get("secondary_text", "")
        if not name:
            continue
        out.append({"id": _slugify(name), "name": name, "country": country})
    return out


async def find_place(name: str, city: str) -> dict:
    """Ground a candidate venue name against a real place record.

    Returns {} if nothing resolves — callers should drop the candidate
    rather than show it, per the design doc's grounding rule.
    """
    if not configured():
        return {}
    query = f"{name}, {city}"
    params = {
        "input": query,
        "inputtype": "textquery",
        "fields": "formatted_address,rating,business_status,place_id",
        "key": API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BASE}/findplacefromtext/json", params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("find_place request failed for %r: %s", query, exc)
        return {}

    candidates = data.get("candidates", [])
    if data.get("status") != "OK" or not candidates:
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            log.warning(
                "find_place status=%s error_message=%r for %r — check your API key, billing, "
                "and that the Places API is enabled",
                data.get("status"), data.get("error_message"), query,
            )
        return {}

    place = candidates[0]
    if place.get("business_status") == "CLOSED_PERMANENTLY":
        return {}

    return {
        "addr": place.get("formatted_address", ""),
        "rating": place.get("rating"),
        "place_id": place.get("place_id"),
    }
