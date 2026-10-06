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

# citySlug -> {normalized_name: item}, built lazily per city the first time
# this run touches it. Process-local, not persisted — a fresh `ingest.run`
# invocation starts empty and reloads from Firestore (via `db`) itself; this
# only avoids re-fetching the same city's doc repeatedly within one run
# (several different sources can touch the same city).
_known_cache: dict = {}


def _known_venues(db, city: str) -> dict:
    """Venues already in Firestore for this city, grounded recently enough
    (see GROUNDING_REFRESH_DAYS) that re-grounding them again now would only
    spend a billed Places call to re-confirm the same answer. `db` is None
    when AUTH_ENABLED isn't set — nothing persisted across runs to check
    against, so every candidate grounds fresh, same as before this existed.
    An item with no `grounded_at` (from before this field existed) is
    treated as due for re-verification rather than assumed fresh.
    """
    slug = places._slugify(city)
    if slug in _known_cache:
        return _known_cache[slug]
    out = {}
    if db is not None:
        doc = db.collection("venues").document(slug).get()
        if doc.exists:
            cutoff = time.time() - GROUNDING_REFRESH_DAYS * 86400
            for item in (doc.to_dict() or {}).get("items", []):
                if item.get("type") != "food":
                    continue
                grounded_at = item.get("grounded_at")
                if grounded_at is None or grounded_at < cutoff:
                    continue
                out[places._normalize(item["name"])] = item
    _known_cache[slug] = out
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


async def ingest_world_article(url: str, source_label: str, db=None) -> list:
    """Same idea as ingest_article(), but for a multi-city "World's 50 Best
    Restaurants" style list — each extracted venue carries its own city
    and country (see extract.extract_world_venues) instead of one city for
    the whole article, since a list like this spans many places at once.
    Results can span several different cities' worth of RESULTS entries
    from a single call. `db` — see ingest_video.
    """
    article_text = scrape_url(url)
    if not article_text:
        return []

    candidates = extract_world_venues(article_text)

    grounded = []
    for candidate in candidates:
        city = candidate["city"]
        known = _known_venues(db, city)
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
