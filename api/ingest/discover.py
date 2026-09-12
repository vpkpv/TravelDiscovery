"""Find candidate YouTube videos for a city using Supadata's video search,
instead of guessing/manually browsing for reputable food-tour channels.

CLI usage (from the api/ directory, with SUPADATA_API_KEY set):

    python -m ingest.discover "Tokyo street food tour"

This only prints candidates — it does NOT add anything to ingest/run.py's
VIDEOS list automatically. Reputable-channel judgment (subscriber count,
whether it's actually the host's own content vs. a reupload, whether the
video genuinely covers the target city) still needs a human to look at the
results, same as every existing entry in VIDEOS was manually verified.

The exact request/response shape for Supadata's /v1/youtube/search wasn't
available to verify against real docs when this was written (only the base
URL and x-api-key auth header, shared with the transcript endpoint already
in transcripts.py, were confirmed) — parsing below tries a few plausible
key names and logs the raw response if none match, so a wrong guess here is
a one-time fix, not silent failure.
"""

import json
import logging
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()  # picks up api/.env, same as ingest/run.py

SUPADATA_API_KEY = os.environ.get("SUPADATA_API_KEY", "").strip()
SEARCH_URL = "https://api.supadata.ai/v1/youtube/search"

log = logging.getLogger("discover")


def configured() -> bool:
    return bool(SUPADATA_API_KEY)


def _extract_list(data: dict) -> list:
    for key in ("videos", "results", "items", "data"):
        if isinstance(data.get(key), list):
            return data[key]
    return []


def _extract_field(item: dict, *candidates: str) -> str:
    for key in candidates:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def search_videos(query: str, limit: int = 10) -> list:
    """Returns [{"video_id", "title", "channel"}, ...]. Empty list if not
    configured or the request/parse fails — check the logged warning for
    the raw response shape if this comes back empty unexpectedly.
    """
    if not configured():
        log.warning("SUPADATA_API_KEY not set — nothing to search with.")
        return []

    try:
        resp = httpx.get(
            SEARCH_URL,
            params={"query": query, "limit": limit},
            headers={"x-api-key": SUPADATA_API_KEY},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Supadata search request failed: %s", exc)
        return []

    raw_items = data if isinstance(data, list) else _extract_list(data)
    if not raw_items:
        log.warning(
            "Got a response but couldn't find a results list in it — raw response: %s",
            json.dumps(data)[:2000],
        )
        return []

    out = []
    for item in raw_items:
        video_id = _extract_field(item, "videoId", "video_id", "id")
        title = _extract_field(item, "title", "name")
        channel = _extract_field(item, "channel", "channelName", "channelTitle", "channel_title")
        if not video_id:
            log.warning("Result missing a recognizable video id field: %s", json.dumps(item)[:500])
            continue
        out.append({"video_id": video_id, "title": title, "channel": channel})
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m ingest.discover \"<search query>\"", file=sys.stderr)
        sys.exit(1)

    results = search_videos(sys.argv[1])
    if not results:
        print("No results (or the response shape didn't match — check the warning above).", file=sys.stderr)
        sys.exit(1)

    print(f"{'video_id':<14}  {'channel':<30}  title")
    for r in results:
        print(f"{r['video_id']:<14}  {r['channel']:<30}  {r['title']}")
    print(
        "\nReview these yourself before adding any to ingest/run.py's VIDEOS list — "
        "check the channel is reputable and the video actually covers the target city.",
        file=sys.stderr,
    )
