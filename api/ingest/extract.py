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
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

log = logging.getLogger("extract")

_client = None


class VenueCandidate(BaseModel):
    name: str
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


def configured() -> bool:
    return bool(GEMINI_API_KEY)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def extract_venues(transcript: str, city: str) -> list:
    """Returns [{"name": ..., "why": ...}, ...]. Empty list if not
    configured, the call fails, or no venues are named in the transcript.
    """
    if not configured() or not transcript.strip():
        return []

    prompt = PROMPT_TEMPLATE.format(city=city, transcript=transcript[:60000])

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
