"""CLI runner: ingest a fixed list of real videos and print the resulting
grounded venue records as JSON.

Usage (from the api/ directory, with GEMINI_API_KEY and
GOOGLE_PLACES_API_KEY set in .env or the environment):

    python -m ingest.run

Requires real internet access (YouTube + Gemini + Places) — this cannot
run inside the Claude Code sandbox this pipeline was written in, which
blocks youtube.com by policy. Run it on a normal machine or in Cloud Run.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

import auth
import places
from ingest.extract import configured as gemini_configured
from ingest.pipeline import ingest_article, ingest_video

# Real, verified videos from a small stable of reputable, broad-coverage
# food-travel channels (Mark Wiens, Best Ever Food Review Show, The Food
# Ranger — all verified via web search for subscriber count/reputation and
# genuine coverage of the target city before being added here; none of
# these video IDs are guessed). Add more as the channel/city list grows.
VIDEOS = [
    # Lisbon
    {
        "video_id": "sLtuZEtCSLA",
        "city": "Lisbon",
        "source": "Mark Wiens — Portuguese Food Tour",
    },
    {
        "video_id": "3mJ7YVF8tpw",
        "city": "Lisbon",
        "source": "Mark Wiens — Cervejaria Ramiro deep dive",
    },
    {
        "video_id": "yNEGYdZIsbo",
        "city": "Lisbon",
        "source": "Mark Wiens — Egg Tarts & Chinese Food in Lisbon",
    },
    # Mumbai
    {
        "video_id": "vLSqdRODai0",
        "city": "Mumbai",
        "source": "Mark Wiens — Bombay Duck Fry and Vada Pav",
    },
    {
        "video_id": "VfNqA2ukNrk",
        "city": "Mumbai",
        "source": "Mark Wiens — Nalli Nihari and Bombay Street Sandwich",
    },
    {
        "video_id": "ksubPh-Of4M",
        "city": "Mumbai",
        "source": "Best Ever Food Review Show — Exotic Street Food Tour",
    },
    {
        "video_id": "ltUDZD1vgxQ",
        "city": "Mumbai",
        "source": "The Food Ranger — Street Food Tour, Best Curry",
    },
    # New York City (US) — Mark Wiens x National Geographic co-production,
    # still his content/voice, just cross-posted rather than his own channel.
    {
        "video_id": "CE6Y8tqhO4A",
        "city": "New York City",
        "source": "Mark Wiens x Nat Geo — NYC's Most Iconic Foods in 24 Hours",
    },
    # Paris (Europe)
    {
        "video_id": "k0B7Va-te44",
        "city": "Paris",
        "source": "Mark Wiens — Paris Street Food, 10 Cheap Eats",
    },
    # Found via ingest/discover.py's Supadata search, 2026-09-17 — Paris only
    # had 1 source video (2 grounded venues). Les Frenchies verified via web
    # search: 437K subscribers, dedicated Paris/France food & travel channel.
    {
        "video_id": "h13cCP9wCpw",
        "city": "Paris",
        "source": "Mark Wiens — Best French Food in Paris for 24 Hours",
    },
    {
        "video_id": "I_Xx1B8Tm-w",
        "city": "Paris",
        "source": "Les Frenchies — Paris Street Food That Locals Actually Eat",
    },
    {
        "video_id": "r62zdMEy7vM",
        "city": "Paris",
        "source": "Les Frenchies — 12 Street Food Where Locals Eat in Paris",
    },
    # Rome (Europe)
    {
        "video_id": "vPVqo3MvfVo",
        "city": "Rome",
        "source": "Mark Wiens — Amazing Roman Food and Attractions",
    },
    # Chicago (US) — second US city
    {
        "video_id": "YmEJzrDVACg",
        "city": "Chicago",
        "source": "Mark Wiens — Ultimate Chicago Pizza Tour",
    },
    # Tokyo — already in the app's curated "trending" city list
    {
        "video_id": "u1YtIwW6HGY",
        "city": "Tokyo",
        "source": "Mark Wiens — Tokyo Nightlife Food Tour",
    },
    {
        "video_id": "iszTT9U4OA8",
        "city": "Tokyo",
        "source": "Mark Wiens — Tokyo Hidden Gems Food Tour",
    },
    # Found via ingest/discover.py's Supadata search, 2026-09-12 — reviewed for
    # channel reputation and city relevance before adding, same as the rest.
    {
        "video_id": "90_z41hZg0Y",
        "city": "Tokyo",
        "source": "TabiEats — Tokyo's Ultimate Street Food Tour",
    },
    {
        "video_id": "PuZ4tvODw60",
        "city": "Tokyo",
        "source": "TabiEats — Tokyo Japan Street Food Tour",
    },
    {
        "video_id": "y0-LwK9Ni9U",
        "city": "Tokyo",
        "source": "Strictly Dumpling — 18 Best Local Japanese Cheap Eats in Tokyo",
    },
    {
        "video_id": "An6cuIMTgxo",
        "city": "Tokyo",
        "source": "Best Ever Food Review Show — Japan Street Food $100 Challenge in Asakusa, Tokyo",
    },
    # Mexico City — already in the app's curated "trending" city list
    {
        "video_id": "Xcbf0LyGHpw",
        "city": "Mexico City",
        "source": "Mark Wiens x Nat Geo — Huarache, Tacos & More",
    },
    {
        "video_id": "DGFYeusTrKc",
        "city": "Mexico City",
        "source": "The Food Ranger — Huge Street Food Tour",
    },
    # Bangkok — already in the app's curated "trending" city list
    {
        "video_id": "MY3Qy6vAbZQ",
        "city": "Bangkok",
        "source": "Mark Wiens x Nat Geo — 24 Hour Thai Street Food Challenge",
    },
    {
        "video_id": "eCFV-_0UeSI",
        "city": "Bangkok",
        "source": "Mark Wiens x Best Ever Food Review Show — Thailand Collab",
    },
    # Found via ingest/discover.py's Supadata search, 2026-09-15 — the two
    # existing Bangkok videos above produced zero venues (one copyright-
    # removed, one just didn't yield named venues), so this needed backfill.
    {
        "video_id": "bpd6uGHpoYY",
        "city": "Bangkok",
        "source": "Mark Wiens — Chatuchak Weekend Market Street Food Tour",
    },
    {
        "video_id": "Y8TwAYjDkQI",
        "city": "Bangkok",
        "source": "Doobydobap — Michelin Street Food in Bangkok",
    },
    # Seoul — already in the app's curated "trending" city list
    {
        "video_id": "RbpKkvlHYTw",
        "city": "Seoul",
        "source": "Mark Wiens — Best Korean Food Tour Ever (Seoul to Busan)",
    },
]

# Real article URLs from reputable food/travel publications (Eater, Condé
# Nast Traveler, local press, etc.) — same manual-vetting principle as
# VIDEOS above: a human confirms each one is a real, currently-live
# article from a real publication before it's added here, same as every
# VIDEOS entry was manually verified against the channel's reputation.
# There's no discover.py equivalent for these yet — find them by browsing
# the publication directly. Empty until the first one is added.
#
# This exists to catch real, well-regarded, currently-open restaurants a
# YouTube-food-influencer-only pipeline structurally can't — confirmed
# live: "The Happy Crane," a real, highly-rated, hard-to-book San
# Francisco restaurant, wasn't findable any other way this app had until
# this was added.
ARTICLES = [
    # {
    #     "url": "https://www.eater.com/maps/best-new-restaurants-san-francisco",
    #     "city": "San Francisco",
    #     "source": "Eater SF — Best New Restaurants",
    # },
]

# city -> country, so places.find_place can reject a same-named result in
# the wrong country entirely (confirmed live: a Tokyo candidate named "Le"
# grounded to a result in India before this check existed). Keyed by city
# name rather than repeated on every VIDEOS entry above.
CITY_COUNTRIES = {
    "Lisbon": "Portugal",
    "Mumbai": "India",
    "New York City": "USA",
    "Paris": "France",
    "Rome": "Italy",
    "Chicago": "USA",
    "Tokyo": "Japan",
    "Mexico City": "Mexico",
    "Bangkok": "Thailand",
    "Seoul": "South Korea",
}


# Seconds to wait between videos. YouTube rate-limits (sometimes outright
# blocks) an IP that fires many transcript requests back-to-back — this
# spacing is a mitigation, not a guarantee. Override with INGEST_DELAY_SECONDS.
DELAY_SECONDS = float(os.environ.get("INGEST_DELAY_SECONDS", "8"))

OUTPUT_FILE = Path(__file__).resolve().parent / "output.json"


async def main():
    if not gemini_configured():
        print("GEMINI_API_KEY not set — nothing to do. See api/.env.example.", file=sys.stderr)
        sys.exit(1)
    if not places.configured():
        print(
            "GOOGLE_PLACES_API_KEY not set — extraction would run but nothing would "
            "ground, so every candidate gets dropped. See api/.env.example.",
            file=sys.stderr,
        )
        sys.exit(1)

    db = auth.firestore_client() if auth.configured() else None
    if db is None:
        print(
            "AUTH_ENABLED not set — skipping Firestore writes, output.json is the "
            "only copy. See api/.env.example if you've set up Firebase and want this to "
            "persist there instead of needing a manual copy-and-redeploy each time.",
            file=sys.stderr,
        )

    all_results = []
    by_city = {}  # slug -> {city, items} — rebuilt fully each video, written to
                  # Firestore after every video (not just at the end): this is
                  # meant to run as an ephemeral Cloud Run Job, which can be
                  # killed mid-run by a timeout, so the same "don't lose
                  # everything fetched so far" reasoning that already applies
                  # to the local output.json below applies doubly to Firestore,
                  # since nothing else reads output.json back afterwards.
    def _save(city: str, items: list) -> None:
        """Shared by both loops below: incremental output.json + Firestore
        save after every single source (video or article), not just at the
        end — see the loops' own comments for why.
        """
        all_results.extend(items)
        OUTPUT_FILE.write_text(json.dumps(all_results, indent=2))
        if items and db is not None:
            slug = places._slugify(city)
            by_city.setdefault(slug, {"city": city, "items": []})["items"].extend(items)
            try:
                db.collection("venues").document(slug).set(by_city[slug])
            except Exception as exc:
                print(f"  Firestore write for {slug} failed (output.json still has it): {exc}", file=sys.stderr)

    blocked_count = 0
    for i, v in enumerate(VIDEOS):
        print(f"Ingesting: {v['source']} ({v['video_id']})...", file=sys.stderr)
        items = await ingest_video(v["video_id"], v["city"], v["source"], CITY_COUNTRIES.get(v["city"], ""))
        print(f"  -> {len(items)} grounded venue(s)", file=sys.stderr)
        if not items:
            blocked_count += 1  # could be a real zero-venue video too, not just a block

        # Save after every video, not just at the end — a mid-run IP block
        # (YouTube's, not ours) shouldn't lose everything fetched so far.
        _save(v["city"], items)

        if i < len(VIDEOS) - 1 or ARTICLES:
            await asyncio.sleep(DELAY_SECONDS)

    for i, a in enumerate(ARTICLES):
        print(f"Scraping: {a['source']} ({a['url']})...", file=sys.stderr)
        items = await ingest_article(a["url"], a["city"], a["source"], CITY_COUNTRIES.get(a["city"], ""))
        print(f"  -> {len(items)} grounded venue(s)", file=sys.stderr)
        if not items:
            blocked_count += 1

        # Same reasoning as the video loop's save — a mid-run failure
        # shouldn't lose articles already scraped, and this is also
        # deliberately being polite to Supadata's own rate limits, not
        # just working around YouTube's.
        _save(a["city"], items)

        if i < len(ARTICLES) - 1:
            await asyncio.sleep(DELAY_SECONDS)

    total_sources = len(VIDEOS) + len(ARTICLES)
    print(f"\nDone: {len(all_results)} venues from {len(VIDEOS)} videos and {len(ARTICLES)} articles "
          f"({blocked_count} of {total_sources} sources produced zero venues — check the warnings "
          f"above for why).", file=sys.stderr)
    print(f"Full results written to {OUTPUT_FILE}", file=sys.stderr)
    if db is not None:
        print(f"Wrote {len(by_city)} cities to Firestore (venues/{{slug}}), incrementally per source.", file=sys.stderr)

    print(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
