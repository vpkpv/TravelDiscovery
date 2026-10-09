"""Orchestrates one video (or article) end to end: transcript/article text
-> Gemini extraction -> Places grounding. This is the real version of what
api/data.py currently hand-writes for Lisbon.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # import places, sibling to ingest/

import places
from ingest.extract import extract_venues, extract_venues_from_article, extract_world_venues
from ingest.scrape_articles import scrape_url
from ingest.transcripts import fetch_transcript

# Re-verify a known venue against Places at most this often. Confirmed live:
# a full `python -m ingest.run` (or the weekly scheduled travel-ingest Cloud
# Run job) re-processes every source ever added, every single time, with
# nothing persisted across separate runs to say "already grounded this one
# recently" — one run alone billed ~2,927 Text Search Enterprise calls,
# almost entirely re-confirming venues a prior run had already verified
# weeks earlier and that hadn't changed. A restaurant's address/rating/
# open-status doesn't meaningfully change week to week, so this skips
# re-grounding anything already known and verified within this window,
# reusing its stored data instead of spending another billed call on it.
GROUNDING_REFRESH_DAYS = int(os.environ.get("INGEST_REFRESH_DAYS", "30"))

# (citySlug, item_type) -> {normalized_name: item}, built lazily the first
# time this run touches that combination. Process-local, not persisted — a
# fresh `ingest.run` invocation starts empty and reloads from Firestore (via
# `db`) itself; this only avoids re-fetching the same city's doc repeatedly
# within one run (several different sources can touch the same city).
_known_cache: dict = {}


def _known_venues(db, city: str, item_type: str = "food") -> dict:
    """Venues already in Firestore for this city, grounded recently enough
    (see GROUNDING_REFRESH_DAYS) that re-grounding them again now would only
    spend a billed Places call to re-confirm the same answer. `db` is None
    when AUTH_ENABLED isn't set — nothing persisted across runs to check
    against, so every candidate grounds fresh, same as before this existed.
    An item with no `grounded_at` (from before this field existed) is
    treated as due for re-verification rather than assumed fresh.

    `item_type` filters to the venue category actually being ingested
    ("food" for every video/article source, or "bar" for a world-list bar
    source — see ingest_world_article's `kind`) — a bar source shouldn't
    treat an already-known restaurant as "this bar is already known", and
    vice versa.
    """
    slug = places._slugify(city)
    cache_key = (slug, item_type)
    if cache_key in _known_cache:
        return _known_cache[cache_key]
    out = {}
    if db is not None:
        doc = db.collection("venues").document(slug).get()
        if doc.exists:
            cutoff = time.time() - GROUNDING_REFRESH_DAYS * 86400
            for item in (doc.to_dict() or {}).get("items", []):
                if item.get("type") != item_type:
                    continue
                grounded_at = item.get("grounded_at")
                if grounded_at is None or grounded_at < cutoff:
                    continue
                # grounded_at (added Oct 4) shipped a day before lat/lng
                # capture (Oct 5) — confirmed live: venues grounded in that
                # one-day window have a fresh grounded_at but no lat/lng,
                # and without this check they'd be "already known" for the
                # full 30 days, permanently missing from distance ranking
                # until that window passes. Treat missing lat/lng as due
                # for re-verification regardless of how fresh grounded_at is.
                if item.get("lat") is None or item.get("lng") is None:
                    continue
                out[places._normalize(item["name"])] = item
    _known_cache[cache_key] = out
    return out


async def ingest_video(video_id: str, city: str, source_label: str, country: str = "", db=None) -> list:
    """Returns a list of grounded venue dicts shaped like api/data.py's
    RESULTS entries (missing only an id, which the caller assigns).
    Empty list if the transcript is unavailable, Gemini finds nothing, or
    nothing grounds against a real Places record.

    `country`, when known, guards against Text Search matching a
    same-named real place in the wrong country entirely — confirmed live:
    a Tokyo candidate named "Le" grounded to a result in India before this
    check existed. See places._in_target_country. `db` (a Firestore client,
    or None) is how a known, recently-verified venue skips re-grounding —
    see _known_venues above.
    """
    transcript = fetch_transcript(video_id)
    if not transcript:
        return []

    candidates = extract_venues(transcript, city)
    known = _known_venues(db, city)

    grounded = []
    for candidate in candidates:
        hit = known.get(places._normalize(candidate["name"]))
        if hit is not None:
            grounded.append({
                **hit,
                "why": candidate["why"],
                "cuisine": candidate.get("cuisine") or hit.get("cuisine", ""),
                "credential": candidate.get("credential") or hit.get("credential", ""),
                "source_video_id": video_id,
            })
            continue
        ground = await places.find_place(candidate["name"], city, country)
        if not ground:
            continue  # ungrounded — could be a mishear, a closed business, or hallucinated
        grounded.append({
            "type": "food",
            "name": candidate["name"],
            "meta": source_label,
            "rating": ground.get("rating"),
            "addr": ground["addr"],
            "why": candidate["why"],
            "cuisine": candidate.get("cuisine", ""),
            "credential": candidate.get("credential", ""),
            "city": city,
            "source_video_id": video_id,
            "photo_ref": ground.get("photo_ref"),
            "lat": ground.get("lat"),
            "lng": ground.get("lng"),
            "grounded_at": time.time(),
        })
    return grounded


async def ingest_article(url: str, city: str, source_label: str, country: str = "", db=None) -> list:
    """Same contract as ingest_video() (real venue dicts, missing only an
    id) but sourced from a scraped article — an Eater "Best New
    Restaurants," a Condé Nast Traveler city guide, etc. — instead of a
    YouTube transcript. See scrape_articles.scrape_url and extract.
    extract_venues_from_article. `db` — see ingest_video.
    """
    article_text = scrape_url(url)
    if not article_text:
        return []

    candidates = extract_venues_from_article(article_text, city)
    known = _known_venues(db, city)

    grounded = []
    for candidate in candidates:
        hit = known.get(places._normalize(candidate["name"]))
        if hit is not None:
            grounded.append({
                **hit,
                "why": candidate["why"],
                "cuisine": candidate.get("cuisine") or hit.get("cuisine", ""),
                "credential": candidate.get("credential") or hit.get("credential", ""),
                "source_url": url,
            })
            continue
        ground = await places.find_place(candidate["name"], city, country)
        if not ground:
            continue
        grounded.append({
            "type": "food",
            "name": candidate["name"],
            "meta": source_label,
            "rating": ground.get("rating"),
            "addr": ground["addr"],
            "why": candidate["why"],
            "cuisine": candidate.get("cuisine", ""),
            "credential": candidate.get("credential", ""),
            "city": city,
            "source_url": url,
            "photo_ref": ground.get("photo_ref"),
            "lat": ground.get("lat"),
            "lng": ground.get("lng"),
            "grounded_at": time.time(),
        })
    return grounded


async def ingest_article_via_chefs(url: str, city: str, source_label: str, country: str = "", db=None) -> list:
    """Same contract as ingest_article(), but for a source that names
    chefs rather than listing restaurants directly — a city-ranking piece
    that credits a few standout chefs instead of running a venue-by-venue
    list (confirmed live: a Time Out Mexico CDMX article, see run.py's
    ARTICLES "mode": "chefs" entries). Each extracted chef name is
    resolved to a real restaurant via places.find_chef_venues — the same
    two-step own-restaurant-or-similar-style resolution FavoriteChefs.jsx's
    manually-typed chef names go through.

    Only an "own_restaurant" match (the chef's own real, currently-open
    restaurant in this exact city) is kept — a "similar_style" match
    (find_chef_venues' fallback for when the chef has no restaurant in the
    searched city at all) is an honest, clearly-labeled "in the style of"
    suggestion in the live FavoriteChefs feature, but not grounded enough
    to permanently ingest as real city content shown to everyone: this
    article is specifically about CDMX, so the named chef is expected to
    actually have a real restaurant here, just possibly under a different
    brand name than their own (e.g. a chef named directly but whose
    restaurant carries its own name) — a similar-style guess in that case
    would be a different restaurant than the one the article is actually
    about, not a reasonable substitute.
    """
    article_text = scrape_url(url)
    if not article_text:
        return []

    candidates = extract_chefs_from_article(article_text, city)
    if not candidates:
        return []
    known = _known_venues(db, city)

    chef_names = [c["name"] for c in candidates]
    resolved = await places.find_chef_venues(city, chef_names, country)
    resolved_by_chef = {
        places._normalize(r["chef"]): r for r in resolved if r.get("match_type") == "own_restaurant"
    }

    grounded = []
    for candidate in candidates:
        ground = resolved_by_chef.get(places._normalize(candidate["name"]))
        if not ground:
            continue  # no real restaurant resolves for this chef in this city — drop, don't guess
        hit = known.get(places._normalize(ground["name"]))
        if hit is not None:
            grounded.append({
                **hit,
                "why": candidate["why"],
                "cuisine": candidate.get("cuisine") or hit.get("cuisine", ""),
                "credential": candidate.get("credential") or hit.get("credential", ""),
                "source_url": url,
            })
            continue
        grounded.append({
            "type": "food",
            "name": ground["name"],
            "meta": source_label,
            "rating": ground.get("rating"),
            "addr": ground["addr"],
            "why": candidate["why"],
            "cuisine": candidate.get("cuisine", ""),
            "credential": candidate.get("credential", ""),
            "city": city,
            "source_url": url,
            "photo_ref": ground.get("photo_ref"),
            "lat": ground.get("lat"),
            "lng": ground.get("lng"),
            "grounded_at": time.time(),
        })
    return grounded


# World-list venue kind -> the `type` value stored on RESULTS/Firestore
# entries (see api/data.py and main.py's _grounded_items) — "restaurant" is
# the kind every prior world-list source was, stored as "food"; "bar" is a
# genuinely different displayed category (see places.find_bars_venues and
# ResultsFeed.jsx's Bars tab), not a food subtype.
_TYPE_BY_KIND = {"restaurant": "food", "bar": "bar"}


async def ingest_world_article(url: str, source_label: str, db=None, kind: str = "restaurant") -> list:
    """Same idea as ingest_article(), but for a multi-city "World's 50 Best
    Restaurants" (or, with kind="bar", "World's 50 Best Bars") style list —
    each extracted venue carries its own city and country (see extract.
    extract_world_venues) instead of one city for the whole article, since a
    list like this spans many places at once. Results can span several
    different cities' worth of RESULTS entries from a single call. `db` —
    see ingest_video.
    """
    article_text = scrape_url(url)
    if not article_text:
        return []

    candidates = extract_world_venues(article_text, kind=kind)
    venue_type = _TYPE_BY_KIND.get(kind, "food")

    grounded = []
    for candidate in candidates:
        city = candidate["city"]
        known = _known_venues(db, city, venue_type)
        hit = known.get(places._normalize(candidate["name"]))
        if hit is not None:
            grounded.append({
                **hit,
                "why": candidate["why"],
                "cuisine": candidate.get("cuisine") or hit.get("cuisine", ""),
                "credential": candidate.get("credential") or hit.get("credential", ""),
                "city": city,
                "source_url": url,
            })
            continue
        ground = await places.find_place(candidate["name"], city, candidate.get("country", ""))
        if not ground:
            continue
        grounded.append({
            "type": venue_type,
            "name": candidate["name"],
            "meta": source_label,
            "rating": ground.get("rating"),
            "addr": ground["addr"],
            "why": candidate["why"],
            "cuisine": candidate.get("cuisine", ""),
            "credential": candidate.get("credential", ""),
            "city": city,
            "source_url": url,
            "photo_ref": ground.get("photo_ref"),
            "lat": ground.get("lat"),
            "lng": ground.get("lng"),
            "grounded_at": time.time(),
        })
    return grounded
