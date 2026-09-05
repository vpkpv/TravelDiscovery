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
]


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
    for v in VIDEOS:
        print(f"Ingesting: {v['source']} ({v['video_id']})...", file=sys.stderr)
        items = await ingest_video(v["video_id"], v["city"], v["source"])
        print(f"  -> {len(items)} grounded venue(s)", file=sys.stderr)
        all_results.extend(items)

    print(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
