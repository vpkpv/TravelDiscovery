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
from ingest.pipeline import ingest_article, ingest_article_via_chefs, ingest_video, ingest_world_article

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
    # New York (US) — Mark Wiens x National Geographic co-production, still
    # his content/voice, just cross-posted rather than his own channel.
    # City string is "New York", not "New York City" — matches both Google
    # Places' own naming and how Gemini independently tagged NYC venues
    # from World's 50 Best/CNT Hot List, so all NYC content lands in one
    # Firestore doc instead of splitting across two differently-slugged
    # ones (confirmed live: a user filtering to Indian cuisine only saw
    # the smaller of the two buckets, missing everything in the other).
    {
        "video_id": "CE6Y8tqhO4A",
        "city": "New York",
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
    # URL confirmed live by user in their own browser, 2026-09-20 (this
    # sandbox's tools can't reach eater.com at all — see scrape_articles.py
    # and this file's ARTICLES comment history for why).
    {
        "url": "https://sf.eater.com/maps/best-restaurants-san-francisco-38",
        "city": "San Francisco",
        "source": "Eater SF — 38 Essential Restaurants",
    },
    # Both URLs confirmed live by user in their own browser, 2026-09-30
    # (this sandbox's WebFetch is blocked for dmagazine.com, same as
    # eater.com/cntraveler.com/laliste.com — see this file's other ARTICLES
    # comments). Added after a live report that Sanjh and Jashan — two
    # real, recently-opened (2024, Nov 2025) Dallas Indian restaurants —
    # weren't showing up: Dallas has no curated/ingested content of its
    # own, so results there depend entirely on curated_food.py's live
    # Gemini suggestions, which predictably missed both for being too new.
    {
        "url": "https://www.dmagazine.com/guides/these-are-the-best-indian-restaurants-in-dallas-fort-worth/",
        "city": "Dallas",
        "source": "D Magazine — Best Indian Restaurants in Dallas",
    },
    {
        "url": "https://www.dmagazine.com/guides/best-dallas-restaurants-right-now/",
        "city": "Dallas",
        "source": "D Magazine — The 50 Best Restaurants in Dallas",
    },
    # All four URLs below confirmed live by user in their own browser,
    # 2026-10-03 — single-city guides for cities already covered elsewhere
    # in this file (Paris, Tokyo, Rome, Chicago), adding depth rather than
    # new geographic coverage.
    {
        "url": "https://www.timeout.com/paris/en/restaurants/best-restaurants-in-paris",
        "city": "Paris",
        "source": "Time Out Paris — Best Restaurants in Paris",
    },
    {
        "url": "https://www.timeout.com/tokyo/restaurants/best-restaurants-tokyo",
        "city": "Tokyo",
        "source": "Time Out Tokyo — Best Restaurants",
    },
    {
        "url": "https://www.timeout.com/rome/restaurants/best-restaurants-in-rome",
        "city": "Rome",
        "source": "Time Out Rome — Best Restaurants",
    },
    {
        "url": "https://www.timeout.com/chicago/restaurants/best-new-restaurants-chicago",
        "city": "Chicago",
        "source": "Time Out Chicago — Best New Restaurants",
    },
    # URL confirmed live by user in their own browser, 2026-10-03 (this
    # sandbox's WebFetch is blocked for guide.michelin.com too). Single-city
    # — Tokyo is already covered elsewhere in this file.
    {
        "url": "https://guide.michelin.com/en/article/michelin-guide-ceremony/michelin-guide-tokyo-2026-stars-reveal",
        "city": "Tokyo",
        "source": "MICHELIN Guide — Tokyo 2026 Stars Reveal",
    },
    # All three URLs below confirmed live by user in their own browser,
    # 2026-10-04.
    {
        "url": "https://www.timeout.com/bangkok/restaurants/the-50-best-restaurants-in-bangkok",
        "city": "Bangkok",
        "source": "Time Out Bangkok — The 50 Best Restaurants",
    },
    {
        "url": "https://guide.michelin.com/en/article/travel/michelin-starred-restaurants-paris",
        "city": "Paris",
        "source": "MICHELIN Guide — Starred Restaurants in Paris",
    },
    # URL provided directly by user, 2026-10-04 — added alongside making Los
    # Angeles a fully curated city (see CITIES in data.py and
    # CITY_COUNTRIES below), not just a live-top-up-only destination, ahead
    # of an actual trip there.
    {
        "url": "https://guide.michelin.com/us/en/california/us-los-angeles/restaurants",
        "city": "Los Angeles",
        "source": "MICHELIN Guide — Los Angeles Restaurants",
    },
    # URL confirmed live by user in their own browser, 2026-10-05. London
    # had no dedicated source before — only reachable via the multi-city
    # MICHELIN Guide Great Britain & Ireland list below.
    {
        "url": "https://www.timeout.com/london/news/best-london-restaurants-2026-mapped-061726",
        "city": "London",
        "source": "Time Out — Mapped: 50 Best Restaurants in London 2026",
    },
    # URL confirmed live by user in their own browser, 2026-10-07. New York
    # had no dedicated source before — only ever reachable via live
    # curated_food top-up, same gap London had before the entry above.
    {
        "url": "https://www.timeout.com/newyork/restaurants/best-restaurants-in-nyc",
        "city": "New York",
        "source": "Time Out New York — Best Restaurants in NYC",
    },
    # All four entries below confirmed live by user in their own browser,
    # 2026-10-09.
    {
        "url": "https://www.timeout.fr/paris/actualites/time-out-food-drink-awards-2026-le-palmares-complet-qui-fait-vibrer-les-gastronomies-du-grand-paris-042226",
        "city": "Paris",
        "source": "Time Out Paris — Food & Drink Awards 2026",
    },
    {
        "url": "https://www.esquireindia.co.in/food-and-drinks/what-to-eat/indias-best-restaurants-in-2026-mumbai-delhi-bengaluru-or-goa-who-dominates-the-rankings",
        "city": "Mumbai",
        "source": "Esquire India — India's Best Restaurants in 2026",
    },
    {
        "url": "https://www.freepressjournal.in/lifestyle/mumbai-dominates-indias-50-best-restaurants-list-these-3-eateries-rank-in-top-10",
        "city": "Mumbai",
        "source": "Free Press Journal — Mumbai Dominates India's 50 Best Restaurants",
    },
    # "mode": "chefs" — this one names chefs behind standout CDMX dishes
    # rather than running a restaurant-by-restaurant list (see
    # ingest_article_via_chefs in pipeline.py).
    {
        "url": "https://www.timeoutmexico.mx/ciudad-de-mexico/restaurantes/cdmx-en-top-3-de-mejores-ciudades-para-comer-en-el-mundo-en-2026",
        "city": "Mexico City",
        "source": "Time Out Mexico — CDMX, Top 3 Best Food Cities 2026",
        "mode": "chefs",
    },
    # Both URLs confirmed live by user in their own browser, 2026-10-10.
    # Seoul had only the global multi-city lists before — first dedicated
    # single-city source for it. (A third candidate, a Korea Times "Seoul
    # Gourmet 100" piece, was confirmed to open but with no actual list
    # content visible on the page — not added, since scrape_url would have
    # nothing to extract from it.)
    {
        "url": "https://guide.michelin.com/sg/en/article/michelin-guide-ceremony/all-the-stars-michelin-guide-seoul-busan-2026",
        "city": "Seoul",
        "source": "MICHELIN Guide — Seoul & Busan 2026 Stars Reveal",
    },
    {
        "url": "https://blog.resy.com/the-hit-list/sf-restaurants-june-2026/",
        "city": "San Francisco",
        "source": "Resy Hit List — San Francisco, June 2026",
    },
]

# Same manual-vetting principle as ARTICLES above, but for a multi-city
# "World's 50 Best Restaurants" / "Top 100 Restaurants in the World" style
# list, spanning many cities and countries in one article — no `city`
# field here, since each extracted venue carries its own (see
# extract.extract_world_venues / pipeline.ingest_world_article).
WORLD_ARTICLES = [
    # URL confirmed live via web search, 2026-09-20. Shows the current
    # standing list — the 2026 rankings aren't announced until Nov 4 in
    # Lima, so this is last year's edition until then, still real content.
    {
        "url": "https://www.theworlds50best.com/restaurants/best-in-the-world/list/1-50",
        "source": "The World's 50 Best Restaurants",
    },
    # URL confirmed live by user in their own browser, 2026-09-20 (this
    # sandbox's tools can't reach cntraveler.com at all — same reason
    # noted for the Eater SF entry in ARTICLES above).
    {
        "url": "https://www.cntraveler.com/story/best-new-restaurants-in-the-world-hot-list-2026",
        "source": "Condé Nast Traveler — The Hot List 2026",
    },
    # URL surfaced directly in web search results (not a guess, unlike the
    # Eater/CNT entries above) and confirmed live by user in their own
    # browser, 2026-09-27 — this sandbox's tools can't reach laliste.com
    # either. La Liste ranks its Top 1000 by analyzing 1,100+ international
    # press/guide/platform sources, distinct methodology from World's 50
    # Best's own panel voting and CNT's editorial picks — a third real,
    # independent source, not a repeat of the same two lists' restaurants.
    {
        "url": "https://www.laliste.com/lists/top-1000-restaurants",
        "source": "La Liste — Top 1000 Restaurants",
    },
    # URL confirmed live by user directly, 2026-09-27, found browsing Food &
    # Wine's Global Tastemakers hub. Small (3 restaurants) but a strong fit:
    # Padma Lakshmi is already one of this app's own real favorite-chef
    # picks (see FavoriteChefs.jsx), and this is a multi-city Indian-food
    # list from her personally — directly relevant to the Indian-cuisine
    # thinness already found and fixed once for New York specifically.
    {
        "url": "https://www.foodandwine.com/padma-lakshmi-favorite-indian-restaurants-11958093",
        "source": "Food & Wine — Padma Lakshmi's Favorite Indian Restaurants",
    },
    # URL confirmed live by user directly, 2026-09-27. Food & Wine's annual
    # "Best New Chefs" — profiles span chefs across different US cities, so
    # this is multi-city like the others above, not single-city.
    {
        "url": "https://www.foodandwine.com/bnc-chefs-11723569/",
        "source": "Food & Wine — Best New Chefs",
    },
    # URL confirmed live by user directly, 2026-09-27 — a direct-fit
    # multi-city "world's best" style list, same pattern as World's 50
    # Best/CNT Hot List/La Liste above, just a different publication's take.
    {
        "url": "https://www.foodandwine.com/top-international-restaurants-2026-11916852",
        "source": "Food & Wine — Top International Restaurants 2026",
    },
    # URL confirmed live by user directly, 2026-09-27 — the US-focused
    # sibling list to Top International Restaurants above, same publication.
    {
        "url": "https://www.foodandwine.com/top-united-states-restaurants-2026-11919583",
        "source": "Food & Wine — Top United States Restaurants 2026",
    },
    # All three URLs below confirmed live by user in their own browser,
    # 2026-10-03 (this sandbox's WebFetch is blocked for jamesbeard.org and
    # guide.michelin.com too). Added at the user's explicit request to pull
    # in Michelin-starred/recognized and James Beard winners specifically —
    # a different, independent-expert-panel kind of signal than the
    # critic/editorial "best of" lists already in this file.
    {
        "url": "https://www.jamesbeard.org/stories/james-beard-award-winners-2026",
        "source": "James Beard Foundation — 2026 Award Winners",
    },
    {
        "url": "https://guide.michelin.com/us/en/article/michelin-guide-ceremony/guide-michelin-california",
        "source": "MICHELIN Guide — California 2026 (83 Starred Restaurants)",
    },
    {
        "url": "https://guide.michelin.com/gb/en/article/michelin-guide-ceremony/every-michelin-star-restaurant-in-great-britain-ireland",
        "source": "MICHELIN Guide — Great Britain & Ireland 2026",
    },
    # URL confirmed live by user in their own browser, 2026-10-04. Multi-city
    # — 62 new stars across France (Paris, Reims, Langres, Savoie, etc.).
    {
        "url": "https://guide.michelin.com/us/en/article/news-and-views/michelin-starred-restaurants-france-new",
        "source": "MICHELIN Guide — New Starred Restaurants in France 2026",
    },
    # URL confirmed live by user in their own browser, 2026-10-05. A new
    # country, not just depth on an existing one — multi-city (Barcelona,
    # Madrid, Málaga, San Sebastián, and more), 307 starred restaurants.
    {
        "url": "https://guide.michelin.com/us/en/article/michelin-guide-ceremony/all-michelin-star-restaurants-in-spain-2026-the-full-list",
        "source": "MICHELIN Guide — All Starred Restaurants in Spain 2026",
    },
    # URL confirmed live by user in their own browser, 2026-10-07 — the
    # North America regional edition of theworlds50best.com's restaurant
    # list already above, a different panel vote than the global one
    # (Smyth in Chicago is #1 regionally). Real credential-badge candidates:
    # ranked restaurants in Chicago, Montréal, New Orleans and more.
    {
        "url": "https://www.theworlds50best.com/restaurants/best-in-north-america/index.html",
        "source": "North America's 50 Best Restaurants 2026",
    },
    # URL confirmed live by user in their own browser, 2026-10-07 — the
    # bars sibling of the restaurant list above, same site, same North
    # America regional edition (Sip & Guzzle, NYC, is #1). First bar
    # source ingest_world_article can actually handle correctly: `kind`
    # tags these as type "bar", not "food" — see pipeline.ingest_world_
    # article and _TYPE_BY_KIND.
    {
        "url": "https://www.theworlds50best.com/bars/best-in-north-america/index.html",
        "source": "North America's 50 Best Bars 2026",
        "kind": "bar",
    },
]

# city -> country, so places.find_place can reject a same-named result in
# the wrong country entirely (confirmed live: a Tokyo candidate named "Le"
# grounded to a result in India before this check existed). Keyed by city
# name rather than repeated on every VIDEOS entry above.
CITY_COUNTRIES = {
    "Lisbon": "Portugal",
    "Mumbai": "India",
    "New York": "USA",
    "Paris": "France",
    "Rome": "Italy",
    "Chicago": "USA",
    "Los Angeles": "USA",
    "London": "United Kingdom",
    "Tokyo": "Japan",
    "Mexico City": "Mexico",
    "Bangkok": "Thailand",
    "Seoul": "South Korea",
    "San Francisco": "USA",
    "Dallas": "USA",
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

    def _save_multi(items: list) -> None:
        """Like _save(), but for a source whose results can each carry a
        different city (see WORLD_ARTICLES / ingest_world_article) —
        groups by each item's own "city" field instead of one city passed
        in for the whole batch.
        """
        all_results.extend(items)
        OUTPUT_FILE.write_text(json.dumps(all_results, indent=2))
        if not items or db is None:
            return
        by_this_batch = {}
        for item in items:
            by_this_batch.setdefault(item["city"], []).append(item)
        for city, city_items in by_this_batch.items():
            slug = places._slugify(city)
            by_city.setdefault(slug, {"city": city, "items": []})["items"].extend(city_items)
            try:
                db.collection("venues").document(slug).set(by_city[slug])
            except Exception as exc:
                print(f"  Firestore write for {slug} failed (output.json still has it): {exc}", file=sys.stderr)

    blocked_count = 0
    for i, v in enumerate(VIDEOS):
        print(f"Ingesting: {v['source']} ({v['video_id']})...", file=sys.stderr)
        items = await ingest_video(v["video_id"], v["city"], v["source"], CITY_COUNTRIES.get(v["city"], ""), db=db)
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
        # "mode": "chefs" — a source that names chefs rather than listing
        # restaurants directly (see ingest_article_via_chefs and its first
        # live use, the Time Out Mexico CDMX entry below).
        ingest_fn = ingest_article_via_chefs if a.get("mode") == "chefs" else ingest_article
        items = await ingest_fn(a["url"], a["city"], a["source"], CITY_COUNTRIES.get(a["city"], ""), db=db)
        print(f"  -> {len(items)} grounded venue(s)", file=sys.stderr)
        if not items:
            blocked_count += 1

        # Same reasoning as the video loop's save — a mid-run failure
        # shouldn't lose articles already scraped, and this is also
        # deliberately being polite to Supadata's own rate limits, not
        # just working around YouTube's.
        _save(a["city"], items)

        if i < len(ARTICLES) - 1 or WORLD_ARTICLES:
            await asyncio.sleep(DELAY_SECONDS)

    for i, w in enumerate(WORLD_ARTICLES):
        print(f"Scraping: {w['source']} ({w['url']})...", file=sys.stderr)
        items = await ingest_world_article(w["url"], w["source"], db=db, kind=w.get("kind", "restaurant"))
        cities = sorted({item["city"] for item in items})
        print(f"  -> {len(items)} grounded venue(s) across {len(cities)} cities: {', '.join(cities)}", file=sys.stderr)
        if not items:
            blocked_count += 1

        _save_multi(items)

        if i < len(WORLD_ARTICLES) - 1:
            await asyncio.sleep(DELAY_SECONDS)

    total_sources = len(VIDEOS) + len(ARTICLES) + len(WORLD_ARTICLES)
    print(f"\nDone: {len(all_results)} venues from {len(VIDEOS)} videos, {len(ARTICLES)} articles, "
          f"and {len(WORLD_ARTICLES)} world-list articles "
          f"({blocked_count} of {total_sources} sources produced zero venues — check the warnings "
          f"above for why).", file=sys.stderr)
    print(f"Full results written to {OUTPUT_FILE}", file=sys.stderr)
    if db is not None:
        print(f"Wrote {len(by_city)} cities to Firestore (venues/{{slug}}), incrementally per source.", file=sys.stderr)

    print(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
