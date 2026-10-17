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

from data import CUISINES

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
    cuisine: str


class BarSuggestion(BaseModel):
    name: str
    why: str


def configured() -> bool:
    return bool(GEMINI_API_KEY)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def suggest_venues(city: str, cuisines: list, limit: int = 10) -> list:
    """Returns [{"name": ..., "why": ..., "cuisine": ...}, ...] — real-name
    candidates per the prompt below, but still unverified until the caller
    grounds each one against Places. Empty list on any failure, same
    convention as everything else here.
    """
    if not configured():
        return []

    # A soft "especially enjoys" hint used to just bias suggestions rather
    # than require them — confirmed live: picking "Indian" for New York (a
    # city with plenty of real Indian restaurants) still surfaced only a
    # handful, because main.py's cuisine filter runs afterward and silently
    # drops any suggestion Gemini didn't itself tag as Indian, and a mere
    # hint let plenty of non-Indian suggestions through. Made into a hard
    # requirement instead, so what's generated already matches what the
    # filter downstream will keep.
    if cuisines:
        cuisine_list = ", ".join(cuisines)
        cuisine_hint = (
            f" Every single suggestion must genuinely be {cuisine_list} cuisine — not "
            f"fusion, not merely influenced by it, not a place that only sometimes serves "
            f"it alongside other cuisines. If {city} genuinely doesn't have {limit} such "
            f"restaurants, return fewer rather than padding with off-cuisine picks."
        )
    else:
        cuisine_hint = ""
    prompt = (
        f"You are a well-traveled local food guide for {city}. Suggest {limit} genuinely "
        f"interesting, currently-operating restaurants there for a visitor — the kind a "
        f"well-connected local or food writer would specifically recommend by name, not "
        f"generic category picks. A mix of well-loved local spots and a couple of buzzy "
        f"newer places, not just the single most famous tourist stop.{cuisine_hint} Only "
        f"name real restaurants you are confident actually exist and are currently open — "
        f"never invent a name. For each, provide a one-sentence reason it's worth visiting, "
        f"and its cuisine as the single closest match from this exact list: "
        f"{', '.join(CUISINES)} (use \"Other\" if genuinely none fit)."
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
    return [{"name": s.name, "why": s.why, "cuisine": s.cuisine} for s in suggestions if s.name.strip()]


def suggest_bars(city: str, limit: int = 10) -> list:
    """Same contract as suggest_venues, for bars/speakeasies — used in
    main.py as a top-up alongside places.find_bars_venues' raw Places
    category search, for a city with too few real bar picks. Unlike that
    raw search, this asks for specific, well-regarded names rather than
    whatever Places' generic "bar" category happens to return, same gap
    this closes for food vs. a flat restaurant-category search.
    """
    if not configured():
        return []

    prompt = (
        f"You are a well-traveled local nightlife guide for {city}. Suggest {limit} "
        f"genuinely interesting, currently-operating bars there for a visitor — the kind a "
        f"well-connected local would specifically recommend by name (a great cocktail bar, "
        f"speakeasy, wine bar, rooftop, or neighborhood favorite), not generic category "
        f"picks. A mix of well-loved local spots and a couple of buzzy newer places, not "
        f"just the single most famous tourist stop. Only name real bars you are confident "
        f"actually exist and are currently open — never invent a name. For each, provide a "
        f"one-sentence reason it's worth visiting."
    )
    try:
        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[BarSuggestion],
            ),
        )
    except Exception as exc:
        log.warning("curated_food bar suggestion request failed for %r: %s", city, exc)
        return []

    suggestions = response.parsed
    if suggestions is None:
        log.warning("curated_food bar response didn't parse against the schema: %r", response.text)
        return []
    return [{"name": s.name, "why": s.why} for s in suggestions if s.name.strip()]
