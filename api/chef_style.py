"""Resolves a followed name (chef, foodie account, or restaurant) to the
chef most associated with it, plus their cuisine/style, via Gemini — e.g.
"Le Bernardin" -> chef "Eric Ripert", style "elevated French seafood
fine dining". A chef's own name resolves to itself.

Used by places.find_chef_venues() as a fallback when the input has no
restaurant of its own in the searched city: instead of literally
re-searching a one-location restaurant's name in an unrelated city (which
usually finds nothing), this derives the actual chef behind it and
searches for *their* style instead. This is a live, request-time Gemini
call (unlike ingest/extract.py's offline use), so it's deliberately a
separate, minimal client rather than importing that module — keeps the
two isolated and avoids risking the already-working ingest path.

A specific, well-known place (e.g. Le Bernardin) resolves to a real chef
name. A smaller/local place Gemini has no specific knowledge of (most
restaurants, realistically — confirmed live: "The Happy Crane" found
nothing at all under the old all-or-nothing version of this) still gets a
best-effort cuisine-style guess from the name/context alone, with
chef_name left empty — this is a *style* hint for a Places search, not a
factual claim about the place, so a reasonable guess is fine to act on;
main.py's wording stays honest about it not being a specific match either
way.
"""

import logging
import os

from google import genai
from google.genai import types
from pydantic import BaseModel

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
# See curated_food.py's identical line for why this is `or`, not just a
# .get() default: Cloud Run can have this var explicitly set to "".
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.6-flash"

log = logging.getLogger("chef_style")

_client = None
_cache = {}  # input name (lowercased) -> {"chef_name", "style"} or {} (unknown/failed). Process-lifetime only.


class ChefStyleResult(BaseModel):
    chef_name: str
    style: str


def configured() -> bool:
    return bool(GEMINI_API_KEY)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def resolve_chef_style(name: str) -> dict:
    """Returns {"chef_name": ..., "style": ...} — chef_name is "" when
    Gemini doesn't recognize this as a specific real chef/restaurant but
    can still make a reasonable style guess from the name/context (see
    module docstring); style is only ever "" when it can't infer anything
    plausible at all. Returns {} if not configured or the request fails —
    callers should treat {} the same as "no fallback available" and just
    show nothing, same convention as the rest of the Places-grounding code
    in this app.

    Cached per-process by the input name: a cold start re-resolves once per
    name seen since boot. Not persisted to Firestore — the cost of asking
    again after a redeploy is one cheap Gemini call per name, not worth the
    extra plumbing for.
    """
    if not configured():
        return {}
    key = name.strip().lower()
    if not key:
        return {}
    if key in _cache:
        return _cache[key]

    prompt = (
        f'The input "{name}" is something a person follows for food/dining inspiration — '
        f'it could be a chef\'s name, a foodie/influencer account, or a specific restaurant, '
        f'possibly a small or local one you have no specific knowledge of. Identify two things:\n'
        f'1. chef_name: if you recognize this as a specific real chef, restaurant, or food '
        f'personality, the chef most associated with it (a restaurant\'s head/founding chef, or '
        f'the same name if it\'s already a chef). If you don\'t recognize it as a specific real '
        f'entity, leave this empty ("").\n'
        f'2. style: in 3 to 6 words, its cuisine style and dining vibe, e.g. "modern French fine '
        f'dining" or "casual Thai street food". If you recognized a specific place, describe its '
        f'actual known style. If you didn\'t, make your best reasonable guess from the name/'
        f'context alone instead of giving up — this only biases a search for a similar real '
        f'restaurant nearby, it is never shown as a claim about "{name}" itself, so a sensible '
        f'guess is fine. Only leave style empty ("") too if you truly cannot infer anything '
        f'plausible even from the name.'
    )
    try:
        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ChefStyleResult,
            ),
        )
        result = response.parsed
    except Exception as exc:
        log.warning("resolve_chef_style request failed for %r: %s", name, exc)
        return {}

    if result is None or not result.style.strip():
        _cache[key] = {}
        return {}

    resolved = {"chef_name": result.chef_name.strip(), "style": result.style.strip()}
    _cache[key] = resolved
    return resolved
