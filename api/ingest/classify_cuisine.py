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

from data import CUISINES

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.6-flash"

log = logging.getLogger("classify_cuisine")

_client = None

# Keeps each prompt/response small enough to stay reliable — a single
# request covering all ~237 existing venues at once risks a truncated or
# malformed response with no way to tell which entries got lost.
BATCH_SIZE = 40


def configured() -> bool:
    return bool(GEMINI_API_KEY)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _classify_one_batch(venues: list) -> dict:
    """Matches results back to venues by position, not by name — asking
    Gemini to echo back each restaurant's exact original name (matching by
    name) turned out unreliable in practice: every single batch came back
    as an unusable, empty match on a real backfill run, most likely
    because Gemini didn't reproduce names character-for-character. A flat,
    ordered list of cuisine labels avoids that failure mode entirely, at
    the cost of the whole batch being unusable if Gemini doesn't return
    exactly one entry per venue in order — checked below and safe to
    retry, since the backfill script is idempotent.
    """
    listing = "\n".join(f"{i + 1}. {v['name']} ({v.get('city', '')}): {v.get('why', '')}" for i, v in enumerate(venues))
    prompt = (
        f"For each of the {len(venues)} numbered restaurants below, pick the single cuisine "
        f"that best describes it from this exact list: {', '.join(CUISINES)}. If genuinely "
        f"none fit, answer \"Other\" instead of guessing. Return exactly {len(venues)} entries, "
        f"one per restaurant, in the same order as given — never skip, merge, or reorder any.\n\n"
        f"{listing}"
    )
    try:
        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[str],
            ),
        )
    except Exception as exc:
        log.warning("cuisine classification request failed for a batch of %d: %s", len(venues), exc)
        return {}

    cuisines = response.parsed
    if cuisines is None:
        log.warning("cuisine classification response didn't parse against the schema: %r", response.text)
        return {}
    if len(cuisines) != len(venues):
        log.warning(
            "cuisine classification returned %d entries for %d venues — order can't be "
            "trusted, skipping this batch (will retry on the next backfill run)",
            len(cuisines), len(venues),
        )
        return {}
    return {v["name"]: c for v, c in zip(venues, cuisines)}


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
