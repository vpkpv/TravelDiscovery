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

Both calls are billed per request (Text Search here is the Enterprise SKU
because the field mask includes `rating`), so successful answers are cached
in-process: a venue's grounding barely changes week to week, and a city
name's autocomplete suggestions never do. Concurrent callers for the same
key share one in-flight request. Transport/API errors are never cached, so
a transient failure doesn't pin a venue as "ungrounded".
"""

import asyncio
import logging
import os
import time
from difflib import SequenceMatcher

import httpx

API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
BASE = "https://places.googleapis.com/v1"
CLOSED_STATUSES = {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}
MATCH_THRESHOLD = 0.5
GROUNDING_TTL = 7 * 24 * 3600
AUTOCOMPLETE_TTL = 24 * 3600

log = logging.getLogger("places")


def configured() -> bool:
    return bool(API_KEY)


def _slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def _normalize(s: str) -> str:
    return " ".join(s.lower().split())


class _TTLCache:
    """key -> (expires_at, Task). Storing the task rather than its result
    lets concurrent callers await the same request instead of each firing
    their own. A task that resolves to None (request failed) is evicted.
    """

    def __init__(self, ttl: float, max_entries: int = 5000):
        self.ttl = ttl
        self.max_entries = max_entries
        self._entries: dict = {}

    async def get_or_fetch(self, key, fetch):
        now = time.monotonic()
        hit = self._entries.get(key)
        if hit and hit[0] > now:
            task = hit[1]
        else:
            if len(self._entries) >= self.max_entries:
                self._entries = {k: v for k, v in self._entries.items() if v[0] > now}
                if len(self._entries) >= self.max_entries:
                    self._entries.clear()
            task = asyncio.ensure_future(fetch())
            self._entries[key] = (now + self.ttl, task)
        try:
            result = await asyncio.shield(task)
        except Exception:
            self._entries.pop(key, None)
            raise
        if result is None:
            if self._entries.get(key, (None, None))[1] is task:
                self._entries.pop(key, None)
        return result


_grounding_cache = _TTLCache(GROUNDING_TTL)
_autocomplete_cache = _TTLCache(AUTOCOMPLETE_TTL)


def _looks_like_match(candidate: str, found: str) -> bool:
    c, f = _normalize(candidate), _normalize(found)
    if not c or not f:
        return False
    if c in f or f in c:
        return True
    return SequenceMatcher(None, c, f).ratio() >= MATCH_THRESHOLD


async def _post(path: str, body: dict, field_mask: str = "") -> "dict | None":
    """None on any transport or API error (so callers can tell a failure
    apart from a genuine empty answer and avoid caching it)."""
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": API_KEY}
    if field_mask:
        headers["X-Goog-FieldMask"] = field_mask
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{BASE}/{path}", json=body, headers=headers)
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("%s request failed: %s", path, exc)
        return None

    if "error" in data:
        err = data["error"]
        log.warning(
            "%s error status=%s message=%r — check your API key, billing, and that "
            "the Places API (New) is enabled",
            path, err.get("status"), err.get("message"),
        )
        return None
    return data


async def autocomplete_cities(query: str) -> list:
    """Real-world city search. Returns [{id, name, country}, ...]."""
    if not configured() or not query.strip():
        return []
    out = await _autocomplete_cache.get_or_fetch(
        _normalize(query), lambda: _fetch_autocomplete(query),
    )
    return out or []


async def _fetch_autocomplete(query: str) -> "list | None":
    data = await _post("places:autocomplete", {
        "input": query,
        "includedPrimaryTypes": ["locality"],
    })
    if data is None:
        return None

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


async def find_place(name: str, city: str) -> dict:
    """Ground a candidate venue name against a real place record.

    Returns {} if nothing resolves to a close-enough real match — callers
    should drop the candidate rather than show it, per the design doc's
    grounding rule.
    """
    if not configured():
        return {}
    ground = await _grounding_cache.get_or_fetch(
        (_normalize(name), _normalize(city)), lambda: _fetch_place(name, city),
    )
    return ground or {}


async def _fetch_place(name: str, city: str) -> "dict | None":
    data = await _post(
        "places:searchText",
        # Only the top result is ever used; Text Search bills per request,
        # not per result, so this trims payload rather than cost.
        {"textQuery": f"{name}, {city}", "pageSize": 1},
        field_mask="places.id,places.formattedAddress,places.rating,places.businessStatus,places.displayName",
    )
    if data is None:
        return None

    places_found = data.get("places", [])
    if not places_found:
        return {}

    place = places_found[0]
    found_name = place.get("displayName", {}).get("text", "")

    if not _looks_like_match(name, found_name):
        log.info("grounding rejected: %r did not match closest result %r", name, found_name)
        return {}

    if place.get("businessStatus") in CLOSED_STATUSES:
        return {}

    return {
        "addr": place.get("formattedAddress", ""),
        "rating": place.get("rating"),
        "place_id": place.get("id"),
    }
