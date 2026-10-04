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

Every billed call below (Text Search, Autocomplete, Photo Media) is
wrapped in an in-process, long-TTL cache — confirmed live: Places billing
was a real, significant cost, and main.py's own cache (which wraps the
*whole* computed result list per city/filter combo, for 15 minutes) only
dedupes identical combos over a short window. It can't help two different
users asking about the same restaurant, or the same request five minutes
after its own TTL expired. Keying on the actual venue/photo/query being
looked up, with a much longer TTL (a venue's address and rating, or a
city's photo, barely change week to week), catches that sharing. A
transient failure is never cached — only a genuine answer (including a
genuine "nothing found") is, so a temporary Places outage doesn't get
pinned in place for a week.
"""

import asyncio
import logging
import os
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

import httpx

import chef_style

API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
BASE = "https://places.googleapis.com/v1"
CLOSED_STATUSES = {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}
MATCH_THRESHOLD = 0.5

GROUNDING_TTL = 7 * 24 * 3600  # a venue's address/rating/open-status barely changes week to week
AUTOCOMPLETE_TTL = 24 * 3600  # a city query's suggestions essentially never change
PHOTO_TTL = 7 * 24 * 3600
PHOTO_CACHE_MAX_ENTRIES = 300  # bounds memory — images are real payload, not a few bytes each

log = logging.getLogger("places")


class _TTLCache:
    """key -> (expires_at, asyncio.Task). Storing the in-flight task, not
    just its eventual result, means concurrent callers for the same key
    share one real request instead of each firing their own — relevant
    right after a cold start, when several requests can race to ground the
    same popular venue at once.

    `fetch` must return None to mean "the request itself failed" (network
    error, API error) — that's evicted immediately so the next call retries
    fresh rather than pinning a failure in place for the full TTL. Any
    other value, including an empty dict/list/string, is treated as a real,
    stable answer (e.g. "this candidate name genuinely has no match") and
    stays cached for the full TTL.
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
        if result is None and self._entries.get(key, (None, None))[1] is task:
            self._entries.pop(key, None)
        return result


_autocomplete_cache = _TTLCache(AUTOCOMPLETE_TTL)
_grounding_cache = _TTLCache(GROUNDING_TTL)
_music_cache = _TTLCache(GROUNDING_TTL)
_restaurant_search_cache = _TTLCache(GROUNDING_TTL)
_photo_cache = _TTLCache(PHOTO_TTL, max_entries=PHOTO_CACHE_MAX_ENTRIES)


def configured() -> bool:
    return bool(API_KEY)


def _slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def _normalize(s: str) -> str:
    # Strips accents (é -> e, ü -> u, ô -> o, ...) before comparing — confirmed
    # live: a World's 50 Best candidate in "Côte d'Ivoire" (Gemini-extracted,
    # plain ASCII) was rejected against Places' own "Côte d'Ivoire" (accented)
    # even though they're the same word. NFKD decomposition only affects
    # Latin-script combining marks, so CJK/Hangul/Thai text passes through
    # unchanged.
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def _looks_like_match(candidate: str, found: str) -> bool:
    c, f = _normalize(candidate), _normalize(found)
    if not c or not f:
        return False
    if c in f or f in c:
        return True
    return SequenceMatcher(None, c, f).ratio() >= MATCH_THRESHOLD


# Google Places renders a US address ending in "USA" and a UK one often
# just "UK" — but extract_world_venues' Gemini prompt (WORLD_ARTICLE_
# PROMPT_TEMPLATE) naturally writes full country names instead ("United
# States", "United Kingdom"), so a plain substring check between the two
# rejects real matches — confirmed live: "Kol" (a real, well-known London
# restaurant, from World's 50 Best) and "Kabawa" (a real NYC restaurant,
# from Condé Nast Traveler's Hot List) were both wrongly dropped this way.
#
# China also needs Hong Kong/Macau as aliases — confirmed live: "The
# Chairman" and "Wing" (Hong Kong) and "Chef Tam's Seasons" (Macau), all
# from World's 50 Best, were wrongly dropped because Places renders their
# addresses as "Hong Kong"/"Macao" rather than "China", even though Gemini
# (correctly) named the sovereign country.
#
# Turkey/Türkiye isn't just an accent difference (stripped by _normalize
# above) — "turkiye" and "turkey" are different words entirely, so it needs
# its own alias, same as China. Confirmed live: "Neolokal" (Istanbul, from
# World's 50 Best) was wrongly dropped because Places renders "Türkiye"
# where Gemini wrote "Turkey".
_COUNTRY_ALIASES = {
    "united states": ["usa", "united states", "united states of america", "us"],
    "united kingdom": ["uk", "united kingdom", "great britain"],
    "china": ["china", "hong kong", "macau", "macao"],
    "turkey": ["turkey", "turkiye"],
}


def _country_variants(country: str) -> list:
    normalized = _normalize(country)
    for aliases in _COUNTRY_ALIASES.values():
        if normalized in aliases:
            return aliases
    return [normalized]


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
    normalized_address = _normalize(address)
    return any(variant in normalized_address for variant in _country_variants(country))


async def _post(path: str, body: dict, field_mask: str = "") -> Optional[dict]:
    """None on any transport or API error — distinct from a valid response
    with an empty `places` list, which means "no error, genuinely nothing
    found" and is safe for a caller to cache as a real answer.
    """
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
    result = await _autocomplete_cache.get_or_fetch(_normalize(query), lambda: _fetch_autocomplete(query))
    return result if result is not None else []


async def _fetch_autocomplete(query: str) -> Optional[list]:
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


async def find_place(name: str, city: str, country: str = "") -> dict:
    """Ground a candidate venue name against a real place record.

    Returns {} if nothing resolves to a close-enough real match — callers
    should drop the candidate rather than show it, per the design doc's
    grounding rule. Pass `country` when known (see _in_target_country) to
    catch a same-named result in the wrong country entirely.
    """
    if not configured():
        return {}
    key = (_normalize(name), _normalize(city), _normalize(country))
    result = await _grounding_cache.get_or_fetch(key, lambda: _fetch_place(name, city, country))
    return result if result is not None else {}


async def _fetch_place(name: str, city: str, country: str) -> Optional[dict]:
    data = await _post(
        "places:searchText",
        # Only the top result is ever used; Text Search bills per request,
        # not per result, so this trims payload rather than cost.
        {"textQuery": f"{name}, {city}", "pageSize": 1},
        field_mask="places.id,places.formattedAddress,places.rating,places.businessStatus,places.displayName,places.photos",
    )
    if data is None:
        return None

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

    Cached — confirmed live: this was the single biggest driver of Places
    billing, since every photo rendered anywhere in the app hit this with
    zero server-side caching. The Cache-Control header main.py's /api/photo
    sends only helps a repeat view from the *same* browser; every other
    user looking at the same popular venue re-fetched the same bytes from
    Google fresh. Capped entry count (not just TTL) since these are real
    image payloads, not small JSON blobs.
    """
    if not configured() or not photo_ref:
        return None
    return await _photo_cache.get_or_fetch((photo_ref, max_width), lambda: _fetch_photo_media(photo_ref, max_width))


async def _fetch_photo_media(photo_ref: str, max_width: int) -> Optional[tuple]:
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
    key = (_normalize(city), genre_hint, _normalize(country))
    result = await _music_cache.get_or_fetch(key, lambda: _fetch_music_venues(city, genre_hint, country))
    return (result or [])[:limit]


async def _fetch_music_venues(city: str, genre_hint: str, country: str) -> Optional[list]:
    # Deliberately not truncated to any particular limit here — this is the
    # cached fetch, shared by every caller regardless of the `limit` they
    # asked for; find_music_venues slices it after the cache lookup.
    query = _MUSIC_SEARCH_TERMS.get(genre_hint, "live music venue")
    data = await _post(
        "places:searchText",
        {"textQuery": f"{query} in {city}"},
        field_mask="places.id,places.formattedAddress,places.rating,places.businessStatus,places.displayName,places.photos",
    )
    if data is None:
        return None

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
    return out


async def _search_one_restaurant(text_query: str, country: str) -> Optional[dict]:
    """Shared by find_chef_venues()'s two query strategies below: runs a
    Text Search and returns the first result that passes the same
    open/real-address checks as everywhere else in this module, or None.
    """
    key = (_normalize(text_query), _normalize(country))
    result = await _restaurant_search_cache.get_or_fetch(key, lambda: _fetch_one_restaurant(text_query, country))
    return result or None


async def _fetch_one_restaurant(text_query: str, country: str) -> Optional[dict]:
    data = await _post(
        "places:searchText",
        {"textQuery": text_query, "pageSize": 1},
        field_mask="places.id,places.formattedAddress,places.rating,places.businessStatus,places.displayName,places.photos",
    )
    if data is None:
        return None
    found = data.get("places", [])
    if not found:
        return {}  # genuinely no match — a stable, cacheable negative, not a failure
    place = found[0]
    if place.get("businessStatus") in CLOSED_STATUSES:
        return {}
    name = place.get("displayName", {}).get("text", "")
    if not name:
        return {}
    address = place.get("formattedAddress", "")
    if not _in_target_country(address, country):
        return {}
    return {
        "place_id": place.get("id"),
        "name": name,
        "addr": address,
        "rating": place.get("rating"),
        "photo_ref": _first_photo_ref(place),
    }


async def find_chef_venues(city: str, chefs: list, country: str = "") -> list:
    """Real, Places-sourced restaurants tied to a chef, foodie account, or
    restaurant the user follows. `chefs` is always manually typed input
    (see web/src/screens/FavoriteChefs.jsx) — this deliberately never reads
    from Instagram or any other social API; CLAUDE.md's food-taste rule
    ("explicit quick-pick, not inferred from an external API") applies here
    the same as it does to cuisines, just via a free-text field instead of
    a fixed vocabulary.

    Two-step search per entry:
    1. Does this exact name have a real restaurant in this city? (direct
       search — handles a chef's own place, or a restaurant/chain with a
       branch here.)
    2. If not, resolve it to the chef actually behind it (chef_style.
       resolve_chef_style — a restaurant name resolves to its head/founding
       chef, a chef's name resolves to itself) and search for *their*
       style instead — e.g. "Le Bernardin" has no location in this city,
       but Eric Ripert's elevated-French-seafood style does have a real
       match. Searching the restaurant's own (usually one-location) name
       in an unrelated city would otherwise almost always find nothing.
       Result is tagged match_type, and carries the original typed input
       separately from the resolved chef name, so main.py can be honest
       about which kind of match it is rather than overclaiming a
       connection that isn't there.

    Same fuzzy-search caveat as find_music_venues(): there's no candidate
    name to fuzzy-match against here either, so `country` is checked to
    filter out a same-named place in the wrong country.

    Entries are processed concurrently (asyncio.gather), not one at a
    time — with several chefs typed in, a sequential loop meant waiting
    out each one's Places/Gemini round trip in turn, compounding latency
    for no reason since they're fully independent of each other.
    """
    if not configured():
        return []

    async def _one(entry: str):
        entry = entry.strip()
        if not entry:
            return None

        # find_place, not _search_one_restaurant, for the direct step: same
        # "{name}, {city}" phrasing (not "{name} restaurant in {city}" —
        # appending a generic word onto an already-specific proper name can
        # throw off Google's fuzzy text search for a smaller/newer place)
        # plus real name-similarity verification, the exact function that's
        # reliably grounded every ingested venue all session. Confirmed
        # live: a real, currently-open, well-reviewed SF restaurant ("The
        # Happy Crane") found nothing under the old phrasing.
        direct = await find_place(entry, city, country)
        if direct:
            return {**direct, "name": entry, "chef": entry, "match_type": "own_restaurant"}

        # chef_style.resolve_chef_style makes a synchronous (blocking) Gemini
        # SDK call — run it off the event loop via to_thread so a slow
        # Gemini response doesn't freeze every other concurrent request this
        # server is handling, not just this one.
        resolved = await asyncio.to_thread(chef_style.resolve_chef_style, entry)
        if not resolved:
            return None
        similar = await _search_one_restaurant(f"{resolved['style']} restaurant in {city}", country)
        if not similar:
            return None
        return {
            **similar,
            "chef": resolved["chef_name"],
            "original_input": entry,
            "match_type": "similar_style",
            "style": resolved["style"],
        }

    results = await asyncio.gather(*(_one(entry) for entry in chefs))
    return [r for r in results if r]


async def find_city_photo(city: str, country: str = "") -> Optional[str]:
    """A real photo representing the city itself (skyline/landmark), for the
    results screen's header banner — not tied to any one venue. Best-effort:
    None if Places doesn't have anything landmark-y for an obscure
    destination, same graceful-degradation stance as everything else here.
    """
    if not configured():
        return None

    data = await _post(
        "places:searchText",
        {"textQuery": f"{city} skyline landmark"},
        field_mask="places.formattedAddress,places.photos",
    )
    if data is None:
        return None
    for place in data.get("places", []):
        if not _in_target_country(place.get("formattedAddress", ""), country):
            continue
        ref = _first_photo_ref(place)
        if ref:
            return ref
    return None
