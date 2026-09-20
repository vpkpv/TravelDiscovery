"""Orchestrates one video (or article) end to end: transcript/article text
-> Gemini extraction -> Places grounding. This is the real version of what
api/data.py currently hand-writes for Lisbon.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # import places, sibling to ingest/

import places
from ingest.extract import extract_venues, extract_venues_from_article
from ingest.scrape_articles import scrape_url
from ingest.transcripts import fetch_transcript


async def ingest_video(video_id: str, city: str, source_label: str, country: str = "") -> list:
    """Returns a list of grounded venue dicts shaped like api/data.py's
    RESULTS entries (missing only an id, which the caller assigns).
    Empty list if the transcript is unavailable, Gemini finds nothing, or
    nothing grounds against a real Places record.

    `country`, when known, guards against Text Search matching a
    same-named real place in the wrong country entirely — confirmed live:
    a Tokyo candidate named "Le" grounded to a result in India before this
    check existed. See places._in_target_country.
    """
    transcript = fetch_transcript(video_id)
    if not transcript:
        return []

    candidates = extract_venues(transcript, city)

    grounded = []
    for candidate in candidates:
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
            "city": city,
            "source_video_id": video_id,
            "photo_ref": ground.get("photo_ref"),
        })
    return grounded


async def ingest_article(url: str, city: str, source_label: str, country: str = "") -> list:
    """Same contract as ingest_video() (real venue dicts, missing only an
    id) but sourced from a scraped article — an Eater "Best New
    Restaurants," a Condé Nast Traveler city guide, etc. — instead of a
    YouTube transcript. See scrape_articles.scrape_url and extract.
    extract_venues_from_article.
    """
    article_text = scrape_url(url)
    if not article_text:
        return []

    candidates = extract_venues_from_article(article_text, city)

    grounded = []
    for candidate in candidates:
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
            "city": city,
            "source_url": url,
            "photo_ref": ground.get("photo_ref"),
        })
    return grounded
