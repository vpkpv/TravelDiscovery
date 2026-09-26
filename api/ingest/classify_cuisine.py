"""Classifies a food venue's cuisine from the fixed CUISINES list via
Gemini, batching many venues into one call — used by backfill_cuisine.py
to tag venues that were ingested before extract.py/curated_food.py tagged
cuisine at the source. See main.py's _grounded_items for why this
matters: the cuisine quick-pick actually filters on this tag now, so an
untagged venue is treated the same as "Other" and hidden whenever a
specific cuisine is selected — confirmed live, this is exactly what a
user saw before any of this existed.
"""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # import data, sibling to ingest/

from google import genai
from google.genai import types
from pydantic import BaseModel

from data import CUISINES

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.6-flash"

log = logging.getLogger("classify_cuisine")

_client = None

# Keeps each prompt/response small enough to stay reliable — a single
# request covering all ~237 existing venues at once risks a truncated or
# malformed response with no way to tell which entries got lost.
BATCH_SIZE = 40


class CuisineTag(BaseModel):
    name: str
    cuisine: str


def configured() -> bool:
    return bool(GEMINI_API_KEY)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _classify_one_batch(venues: list) -> dict:
    listing = "\n".join(f"- {v['name']} ({v.get('city', '')}): {v.get('why', '')}" for v in venues)
    prompt = (
        f"For each restaurant below, pick the single cuisine that best describes it from "
        f"this exact list: {', '.join(CUISINES)}. If genuinely none fit, answer \"Other\" "
        f"instead of guessing. Return one entry per restaurant, using its exact name as given "
        f"below.\n\n{listing}"
    )
    try:
        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[CuisineTag],
            ),
        )
    except Exception as exc:
        log.warning("cuisine classification request failed for a batch of %d: %s", len(venues), exc)
        return {}

    tags = response.parsed
    if tags is None:
        log.warning("cuisine classification response didn't parse against the schema: %r", response.text)
        return {}
    return {t.name: t.cuisine for t in tags if t.name.strip()}


def classify_batch(venues: list) -> dict:
    """venues: [{"name", "why", "city"}, ...] (extra keys ignored). Returns
    {name: cuisine}. Chunks internally so one oversized request can't fail
    the whole thing; a name missing from the result (a failed chunk, or
    Gemini skipping an entry) should be treated as unclassified/"Other" by
    the caller, same as any other venue that's never been tagged.
    """
    if not configured() or not venues:
        return {}
    tags = {}
    for i in range(0, len(venues), BATCH_SIZE):
        tags.update(_classify_one_batch(venues[i:i + BATCH_SIZE]))
    return tags
