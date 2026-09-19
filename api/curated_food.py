"""Live, Gemini-generated food suggestions for a city with no curated or
ingested content of its own (see main.py's _grounded_items — this only
fires when a city has zero food items after everything else).

Unlike ingest/extract.py, which extracts venues a real video actually
named, this asks Gemini directly for restaurant suggestions from its own
knowledge — meaningfully more prone to hallucination (a wrong or defunct
name, not just a mis-transcribed one). So every suggestion here still goes
through the exact same Places grounding (places.find_place) as everything
else in this app before it's shown — an ungrounded suggestion is dropped,
never shown, per CLAUDE.md's rule against showing unverified venues. This
module only produces candidates; it never itself decides what's real.
"""

import logging
import os

from google import genai
from google.genai import types
from pydantic import BaseModel

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
# `or` on top of .get(), not just a .get() default: Cloud Run can have this
# var explicitly set to "" (deploy.sh always passes it, even when left
# blank in deploy-env.sh) — .get()'s default only applies when the key is
# absent entirely, not when it's present-but-empty, and an empty model
# name reaching the Gemini SDK fails with "model is required".
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.6-flash"

log = logging.getLogger("curated_food")

_client = None


class VenueSuggestion(BaseModel):
    name: str
    why: str


def configured() -> bool:
    return bool(GEMINI_API_KEY)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def suggest_venues(city: str, cuisines: list, limit: int = 6) -> list:
    """Returns [{"name": ..., "why": ...}, ...] — real-name candidates per
    the prompt below, but still unverified until the caller grounds each
    one against Places. Empty list on any failure, same convention as
    everything else here.
    """
    if not configured():
        return []

    cuisine_hint = f" This person especially enjoys: {', '.join(cuisines)}." if cuisines else ""
    prompt = (
        f"You are a well-traveled local food guide for {city}. Suggest {limit} genuinely "
        f"interesting, currently-operating restaurants there for a visitor — a mix of "
        f"well-loved local spots and a couple of buzzy newer places, not just the single "
        f"most famous tourist stop.{cuisine_hint} Only name real restaurants you are "
        f"confident actually exist and are currently open — never invent a name. For each, "
        f"write a one-sentence reason it's worth visiting."
    )
    try:
        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[VenueSuggestion],
            ),
        )
    except Exception as exc:
        log.warning("curated_food suggestion request failed for %r: %s", city, exc)
        return []

    suggestions = response.parsed
    if suggestions is None:
        log.warning("curated_food response didn't parse against the schema: %r", response.text)
        return []
    return [{"name": s.name, "why": s.why} for s in suggestions if s.name.strip()]
