"""Translates a chef/foodie-account name into a short cuisine/style
descriptor via Gemini, e.g. "Gordon Ramsay" -> "modern French fine dining".

Used by places.find_chef_venues() as a fallback when a chef doesn't have
their own restaurant in the searched city: instead of finding nothing, we
search Places for that *style* of restaurant instead. This is a live,
request-time Gemini call (unlike ingest/extract.py's offline use), so it's
deliberately a separate, minimal client rather than importing that module —
keeps the two isolated and avoids risking the already-working ingest path.
"""

import logging
import os

from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

log = logging.getLogger("chef_style")

_client = None
_cache = {}  # chef name (lowercased) -> descriptor ("" = unknown/failed). Process-lifetime only.


def configured() -> bool:
    return bool(GEMINI_API_KEY)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def chef_style(chef: str) -> str:
    """Returns a short cuisine/style descriptor for a chef/food-personality
    name, or "" if not configured, the name isn't recognized, or the
    request fails — callers should treat "" the same as "no fallback
    available" and just show nothing, same convention as the rest of the
    Places-grounding code in this app.

    Cached per-process by name: a cold start re-asks Gemini once per chef
    seen since boot. Not persisted to Firestore — the cost of asking again
    after a redeploy is one cheap text-only Gemini call per chef, not worth
    the extra plumbing for.
    """
    if not configured():
        return ""
    key = chef.strip().lower()
    if not key:
        return ""
    if key in _cache:
        return _cache[key]

    prompt = (
        f'In 3 to 6 words, describe the cuisine style and dining vibe most associated '
        f'with the chef or food personality "{chef}" — for example "modern French fine '
        f'dining" or "casual Thai street food". Respond with only the descriptor, '
        f'nothing else. If you don\'t recognize this as a real chef or food personality, '
        f'respond with exactly: unknown'
    )
    try:
        response = _get_client().models.generate_content(model=GEMINI_MODEL, contents=prompt)
        text = (response.text or "").strip().strip('"')
    except Exception as exc:
        log.warning("chef_style request failed for %r: %s", chef, exc)
        return ""

    style = "" if text.lower() == "unknown" else text
    _cache[key] = style
    return style
