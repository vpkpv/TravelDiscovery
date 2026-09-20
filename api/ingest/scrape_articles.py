"""Scrapes a real article URL (an "Eater's Best New Restaurants," a Condé
Nast Traveler city guide, etc.) into clean text via Supadata's web-scrape
endpoint, for the same extraction pipeline used for YouTube transcripts —
see ingest/extract.py's extract_venues_from_article and
ingest/pipeline.py's ingest_article.

The exact request/response shape for Supadata's /v1/web/scrape wasn't
available to verify against real docs when this was written (this sandbox
can't reach docs.supadata.ai; only the base URL pattern and x-api-key auth
header, shared with the transcript/search endpoints already in
transcripts.py and discover.py, were confirmed) — parsing below tries a
few plausible key names and logs the raw response if none match, same
approach discover.py already used for the same reason, so a wrong guess
here is a one-time fix, not a silent failure.
"""

import json
import logging
import os

import httpx

SUPADATA_API_KEY = os.environ.get("SUPADATA_API_KEY", "").strip()
SCRAPE_URL = "https://api.supadata.ai/v1/web/scrape"

log = logging.getLogger("scrape_articles")


def configured() -> bool:
    return bool(SUPADATA_API_KEY)


def scrape_url(url: str) -> str:
    """Returns the page's content as text/markdown, or "" if not
    configured or the request/parse fails — check the logged warning for
    the raw response shape if this comes back empty unexpectedly.
    """
    if not configured():
        log.warning("SUPADATA_API_KEY not set — nothing to scrape with.")
        return ""

    try:
        resp = httpx.get(
            SCRAPE_URL,
            params={"url": url},
            headers={"x-api-key": SUPADATA_API_KEY},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Supadata scrape request failed for %s: %s", url, exc)
        return ""

    for key in ("content", "markdown", "text", "html"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value

    log.warning(
        "Got a response for %s but couldn't find content in it — raw response: %s",
        url, json.dumps(data)[:2000],
    )
    return ""
