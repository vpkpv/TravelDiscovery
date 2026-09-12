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

import places
from ingest.extract import configured as gemini_configured
from ingest.pipeline import ingest_video

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
    # Seoul — already in the app's curated "trending" city list
    {
        "video_id": "RbpKkvlHYTw",
        "city": "Seoul",
        "source": "Mark Wiens — Best Korean Food Tour Ever (Seoul to Busan)",
    },
]


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

    all_results = []
    blocked_count = 0
    for i, v in enumerate(VIDEOS):
        print(f"Ingesting: {v['source']} ({v['video_id']})...", file=sys.stderr)
        items = await ingest_video(v["video_id"], v["city"], v["source"])
        print(f"  -> {len(items)} grounded venue(s)", file=sys.stderr)
        if not items:
            blocked_count += 1  # could be a real zero-venue video too, not just a block
        all_results.extend(items)

        # Save after every video, not just at the end — a mid-run IP block
        # (YouTube's, not ours) shouldn't lose everything fetched so far.
        OUTPUT_FILE.write_text(json.dumps(all_results, indent=2))

        if i < len(VIDEOS) - 1:
            await asyncio.sleep(DELAY_SECONDS)

    print(f"\nDone: {len(all_results)} venues from {len(VIDEOS)} videos "
          f"({blocked_count} videos produced zero venues — check the warnings above for why).",
          file=sys.stderr)
    print(f"Full results written to {OUTPUT_FILE}", file=sys.stderr)
    print(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
