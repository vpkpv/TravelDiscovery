"""Extract named venue candidates from a transcript using Gemini.

Uses the current `google-genai` SDK (the old `google-generativeai` package
is deprecated as of this writing). Structured output is enforced via
response_schema, not prompt-only instructions, so a malformed response
raises rather than silently passing bad data downstream.
"""

import logging
import os

from google import genai
from google.genai import types
from pydantic import BaseModel

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
# See api/curated_food.py's identical line for why this is `or`, not just
# a .get() default: Cloud Run can have this var explicitly set to "".
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.6-flash"

log = logging.getLogger("extract")

_client = None


class VenueCandidate(BaseModel):
    name: str
    why: str


class WorldVenueCandidate(BaseModel):
    name: str
    city: str
    country: str
    why: str


PROMPT_TEMPLATE = """You are extracting real restaurant/venue recommendations from a food \
travel video transcript. The video is about food in {city}.

Read the transcript below and extract every specific, named restaurant, market, or food \
venue the host actually visits or recommends by name — not generic dish names, not \
neighborhoods, only real business names.

For each one, write a short one-sentence "why" line explaining what makes it worth \
visiting, grounded only in what the transcript actually says — never invent a detail \
that isn't in the transcript.

If no real venues are named, return an empty list.

Transcript:
{transcript}
"""

# Separate from PROMPT_TEMPLATE, not reused with different wording plugged
# in: "the host actually visits" doesn't fit a written best-of article, and
# an article is structured very differently from a spoken transcript (an
# explicit list/ranking rather than a narrated visit).
ARTICLE_PROMPT_TEMPLATE = """You are extracting real restaurant recommendations from a food/\
travel publication's article. The article is about food in {city}.

Read the article text below and extract every specific, named restaurant it recommends or \
features — not generic dish names, not neighborhoods, only real business names.

For each one, write a short one-sentence "why" line explaining what makes it worth visiting, \
grounded only in what the article actually says — never invent a detail that isn't in the \
article.

If no real restaurants are named, return an empty list.

Article:
{article_text}
"""

# Separate again from ARTICLE_PROMPT_TEMPLATE: a "World's 50 Best
# Restaurants"-style list spans many cities and countries in one article,
# not one fixed city — so city/country have to be extracted per venue
# instead of supplied once for the whole piece (see WorldVenueCandidate
# and pipeline.ingest_world_article).
WORLD_ARTICLE_PROMPT_TEMPLATE = """You are extracting a ranked or curated list of top restaurants \
from a prestigious food/travel publication's article — something like "The World's 50 Best \
Restaurants" or "Top 100 Restaurants in the World," spanning many different cities and countries \
at once, not just one.

Read the article text below and extract every specific, named restaurant it lists — not generic \
mentions, only real, individually named restaurants. For each one:
- name: the restaurant's real name.
- city: the city it's actually located in, as stated or clearly implied by the article.
- country: the country it's located in.
- why: a short one-sentence reason it's notable, grounded only in what the article actually says \
— never invent a detail that isn't in the article.

If you can't determine a specific city for an entry, skip it rather than guessing — a wrong city \
would cause it to be searched for in the wrong place entirely.

If no real restaurants are named, return an empty list.

Article:
{article_text}
"""


def configured() -> bool:
    return bool(GEMINI_API_KEY)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _extract(prompt: str) -> list:
    """Shared by extract_venues() and extract_venues_from_article() below —
    both just build a different prompt around the same structured-output
    Gemini call and response handling.
    """
    try:
        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[VenueCandidate],
            ),
        )
    except Exception as exc:
        log.warning("Gemini extraction request failed: %s", exc)
        return []

    candidates = response.parsed
    if candidates is None:
        log.warning("Gemini response didn't parse against the schema: %r", response.text)
        return []

    return [{"name": c.name, "why": c.why} for c in candidates if c.name.strip()]


def extract_venues(transcript: str, city: str) -> list:
    """Returns [{"name": ..., "why": ...}, ...]. Empty list if not
    configured, the call fails, or no venues are named in the transcript.
    """
    if not configured() or not transcript.strip():
        return []
    return _extract(PROMPT_TEMPLATE.format(city=city, transcript=transcript[:60000]))


def extract_venues_from_article(article_text: str, city: str) -> list:
    """Same contract as extract_venues() but for a scraped article's text
    instead of a video transcript — see ARTICLE_PROMPT_TEMPLATE and
    ingest/scrape_articles.py.
    """
    if not configured() or not article_text.strip():
        return []
    return _extract(ARTICLE_PROMPT_TEMPLATE.format(city=city, article_text=article_text[:60000]))


def extract_world_venues(article_text: str) -> list:
    """Returns [{"name", "city", "country", "why"}, ...] — each venue
    carries its own city/country instead of one for the whole article, for
    a multi-city "world's best restaurants" style list. Empty list if not
    configured, the call fails, or no venues (with a determinable city)
    are named. See WORLD_ARTICLE_PROMPT_TEMPLATE and
    pipeline.ingest_world_article.
    """
    if not configured() or not article_text.strip():
        return []

    prompt = WORLD_ARTICLE_PROMPT_TEMPLATE.format(article_text=article_text[:60000])
    try:
        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[WorldVenueCandidate],
            ),
        )
    except Exception as exc:
        log.warning("Gemini world-article extraction request failed: %s", exc)
        return []

    candidates = response.parsed
    if candidates is None:
        log.warning("Gemini response didn't parse against the schema: %r", response.text)
        return []

    return [
        {"name": c.name, "city": c.city, "country": c.country, "why": c.why}
        for c in candidates
        if c.name.strip() and c.city.strip()
    ]
