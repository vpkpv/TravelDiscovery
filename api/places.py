"""Thin wrapper around Google's Places API (New).

Two calls: city autocomplete for the "where are you headed?" search box, and
a text-search-based grounding call for verifying a candidate venue name
against a real place record (address, rating, open/closed) — the mechanism
described in the design doc for dropping hallucinated or defunct venues.

Text Search (New) is a fuzzy full-text search, not a lookup: a nonsense
query still returns *some* real place in the area rather than "not found"
(confirmed empirically — a garbage venue name for Lisbon returned an
unrelated real bar). So find_place() only accepts a result whose name is
actually close to the candidate; otherwise it treats the candidate as
ungrounded, same as a zero-result response.

Every function returns None (or an empty list) on any failure — missing
key, network error, no close-enough match — so callers can fall back to
mock data without extra try/except noise at each call site.
"""

import logging
import os
from difflib import SequenceMatcher
from typing import Optional

import httpx

API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
BASE = "https://places.googleapis.com/v1"
CLOSED_STATUSES = {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}
MATCH_THRESHOLD = 0.5

log = logging.getLogger("places")


def configured() -> bool:
    return bool(API_KEY)


def _slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def _normalize(s: str) -> str:
    return " ".join(s.lower().split())


def _looks_like_match(candidate: str, found: str) -> bool:
    c, f = _normalize(candidate), _normalize(found)
    if not c or not f:
        return False
    if c in f or f in c:
        return True
    return SequenceMatcher(None, c, f).ratio() >= MATCH_THRESHOLD


def _in_target_country(address: str, country: str) -> bool:
    """Text Search is fuzzy enough that a short/generic candidate name (e.g.
    "Le", "Kikuya") can match a same-named real place in a totally different
    city or country and still pass _looks_like_match — confirmed live: a
    Tokyo candidate named "Le" grounded to a result in Gurugram, India, and
    "Kikuya" grounded to one in Bangkok, Thailand. Name similarity alone
    isn't enough.

    Checks country, not city: Places renders the country in English
    regardless of locale, but the city/region portion of the address often
    isn't (e.g. Mexico City's addresses read "Ciudad de México", never the
    literal string "Mexico City") — a city-name substring check would
    reject every legitimate result for cities like that. `country` is
    optional; when the caller doesn't have one (e.g. an ad-hoc city search
    with no known country), this check is skipped rather than guessed at.
    """
    if not country:
        return True
    return _normalize(country) in _normalize(address)


async def _post(path: str, body: dict, field_mask: str = "") -> dict:
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": API_KEY}
    if field_mask:
        headers["X-Goog-FieldMask"] = field_mask
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{BASE}/{path}", json=body, headers=headers)
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("%s request failed: %s", path, exc)
        return {}

    if "error" in data:
        err = data["error"]
        log.warning(
            "%s error status=%s message=%r — check your API key, billing, and that "
            "the Places API (New) is enabled",
            path, err.get("status"), err.get("message"),
        )
        return {}
    return data


async def autocomplete_cities(query: str) -> list:
    """Real-world city search. Returns [{id, name, country}, ...]."""
    if not configured() or not query.strip():
        return []

    data = await _post("places:autocomplete", {
        "input": query,
        "includedPrimaryTypes": ["locality"],
    })

    out = []
    for suggestion in data.get("suggestions", []):
        pred = suggestion.get("placePrediction", {})
        structured = pred.get("structuredFormat", {})
        name = structured.get("mainText", {}).get("text", "")
        country = structured.get("secondaryText", {}).get("text", "")
        place_id = pred.get("placeId", "")
        if not name:
            continue
        out.append({
            "id": place_id or _slugify(f"{name}-{country}"),  # unique per real place
            "slug": _slugify(name),  # groups "Lisbon, Portugal" with our curated "lisbon" content
            "name": name,
            "country": country,
        })
    return out


async def find_place(name: str, city: str, country: str = "") -> dict:
    """Ground a candidate venue name against a real place record.

    Returns {} if nothing resolves to a close-enough real match — callers
    should drop the candidate rather than show it, per the design doc's
    grounding rule. Pass `country` when known (see _in_target_country) to
    catch a same-named result in the wrong country entirely.
    """
    if not configured():
        return {}

    data = await _post(
        "places:searchText",
        {"textQuery": f"{name}, {city}"},
        field_mask="places.id,places.formattedAddress,places.rating,places.businessStatus,places.displayName,places.photos",
    )

    places_found = data.get("places", [])
    if not places_found:
        return {}

    place = places_found[0]
    found_name = place.get("displayName", {}).get("text", "")

    if not _looks_like_match(name, found_name):
        # WARNING, not INFO: a venue silently disappearing from what's
        # served is worth being able to see in Cloud Run's default log
        # capture, which doesn't pick up INFO without extra config —
        # confirmed missing exactly this way debugging a prior issue.
        log.warning("grounding rejected: %r did not match closest result %r", name, found_name)
        return {}

    address = place.get("formattedAddress", "")
    if not _in_target_country(address, country):
        log.warning(
            "grounding rejected: %r matched %r by name, but its address %r isn't in %r",
            name, found_name, address, country,
        )
        return {}

    if place.get("businessStatus") in CLOSED_STATUSES:
        return {}

    return {
        "addr": place.get("formattedAddress", ""),
        "rating": place.get("rating"),
        "place_id": place.get("id"),
        "photo_ref": _first_photo_ref(place),
    }


def _first_photo_ref(place: dict):
    """The resource name (e.g. "places/ABC/photos/XYZ") of a place's first
    Places photo, if it has one — passed to photo_media() to fetch the
    actual image bytes. None (not a fixed placeholder) when a place has no
    photos, which is common enough (smaller/newer venues) that the frontend
    needs a fallback anyway.
    """
    photos = place.get("photos", [])
    return photos[0]["name"] if photos else None


async def photo_media(photo_ref: str, max_width: int = 400) -> Optional[tuple]:
    """Fetches actual image bytes for a photo_ref from find_place()/
    find_music_venues(), for main.py's /api/photo to proxy back to the
    browser. Proxied server-side (rather than handing the browser a Places
    URL with our API key attached) so the key never reaches the client.

    Returns (content_bytes, content_type), or None on any failure — the
    caller (an <img> tag) just gets a missing image, same as a venue with
    no photo at all.
    """
    if not configured() or not photo_ref:
        return None
    url = f"{BASE}/{photo_ref}/media"
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            resp = await client.get(url, params={"key": API_KEY, "maxWidthPx": max_width})
        if resp.status_code != 200:
            return None
        return resp.content, resp.headers.get("content-type", "image/jpeg")
    except httpx.HTTPError as exc:
        log.warning("photo media fetch failed for %r: %s", photo_ref, exc)
        return None


# Genre -> a Text Search query that tends to surface a real venue of that
# type. Falls back to a generic live-music search for anything unmapped —
# notably the Spotify/artist-name taste signal, which has no genre to key
# off (see api/spotify.py's docstring on why artist genres aren't reliable).
_MUSIC_SEARCH_TERMS = {
    "Jazz": "jazz club",
    "Fado / World": "world music bar",
    "Classical": "concert hall",
    "Rock": "live rock music venue",
    "Indie": "indie live music venue",
    "Electronic": "nightclub",
    "Soul / R&B": "soul music bar",
    "Country": "country music bar",
    "Blues": "blues bar",
    "Folk": "folk music venue",
    "Pop": "live music venue",
    "Hip-Hop / Rap": "hip hop club",
    "Latin": "latin music club",
}


async def find_music_venues(city: str, genre_hint: str = "", limit: int = 4, country: str = "") -> list:
    """Real, Places-sourced live-music venues for a city, for cities with no
    hand-curated or ingested music picks. Unlike find_place(), there's no
    "candidate name" to ground here — these results are themselves the real
    venues, straight from Places — but the underlying textQuery is still
    fuzzy enough to drift to a same-named place in the wrong country for an
    ambiguous city name, same failure mode as find_place(); pass `country`
    when known to filter those out too.
    """
    if not configured():
        return []

    query = _MUSIC_SEARCH_TERMS.get(genre_hint, "live music venue")
    data = await _post(
        "places:searchText",
        {"textQuery": f"{query} in {city}"},
        field_mask="places.id,places.formattedAddress,places.rating,places.businessStatus,places.displayName,places.photos",
    )

    out = []
    for place in data.get("places", []):
        if place.get("businessStatus") in CLOSED_STATUSES:
            continue
        name = place.get("displayName", {}).get("text", "")
        if not name:
            continue
        if not _in_target_country(place.get("formattedAddress", ""), country):
            continue
        out.append({
            "place_id": place.get("id"),
            "name": name,
            "addr": place.get("formattedAddress", ""),
            "rating": place.get("rating"),
            "genre": genre_hint or "Live music",
            "photo_ref": _first_photo_ref(place),
        })
        if len(out) >= limit:
            break
    return out
