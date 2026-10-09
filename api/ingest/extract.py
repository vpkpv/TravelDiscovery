"""Extract named venue candidates from a transcript using Gemini.

Uses the current `google-genai` SDK (the old `google-generativeai` package
is deprecated as of this writing). Structured output is enforced via
response_schema, not prompt-only instructions, so a malformed response
raises rather than silently passing bad data downstream.
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
# See api/curated_food.py's identical line for why this is `or`, not just
# a .get() default: Cloud Run can have this var explicitly set to "".
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.6-flash"

log = logging.getLogger("extract")

_client = None

# Every extracted food candidate below also gets a cuisine tag — from this
# exact list (same one Settings/onboarding shows), or "Other" — so main.py's
# _grounded_items can actually filter by the cuisine quick-pick instead of
# only using it as a suggestion bias. Confirmed live: a user picked "Indian"
# and still saw non-Indian restaurants, since nothing was tagged at all.
_CUISINE_INSTRUCTION = (
    f"cuisine: the single closest match from this exact list: {', '.join(CUISINES)}. "
    f"If genuinely none fit, use \"Other\" instead of guessing."
)

# A specific, sourced credential — "#1, The World's 50 Best Bars 2026",
# "Michelin 2 Stars", "James Beard Award Winner, Best Chef: Texas 2026" —
# shown as its own badge in the app rather than buried in `why`'s prose
# (see ResultsFeed.jsx's credential badge). Deliberately conservative:
# empty is the common, correct case for most sources (a Time Out roundup
# rarely states a formal rank/award per venue), so the instruction leans
# hard on "don't invent one" rather than encouraging a guess.
_CREDENTIAL_INSTRUCTION = (
    "credential: ONLY if the source explicitly states a specific rank, award, or official "
    "recognition for this exact venue (e.g. \"#1 on The World's 50 Best Bars 2026\", "
    "\"Michelin 2 Stars\", \"James Beard Award Winner, Best Chef: Texas 2026\"), give it back "
    "concisely in that form. Otherwise an empty string — never invent or infer one just "
    "because the source is a roundup or list; most venues won't have one, and that's correct."
)

# For WORLD_ARTICLE_PROMPT_TEMPLATE specifically: the article itself *is* a
# ranked list, so unlike the two instructions above, this one actively asks
# for the list's name + this entry's stated position rather than treating
# that as the rare case — still never inventing a rank the article doesn't
# actually state for this specific entry.
_WORLD_CREDENTIAL_INSTRUCTION = (
    "credential: this entry's specific stated rank or placement in the list this article is "
    "about, using the list's actual name — e.g. \"#1, The World's 50 Best Bars 2026\" or "
    "\"#23, The World's 50 Best Restaurants 2026\". If the article doesn't clearly state an "
    "individual rank/number for this specific entry (not just that it's somewhere in the "
    "list), use an empty string instead of guessing a position."
)


class VenueCandidate(BaseModel):
    name: str
    why: str
    cuisine: str
    credential: str = ""


class WorldVenueCandidate(BaseModel):
    name: str
    city: str
    country: str
    why: str
    cuisine: str
    credential: str = ""


PROMPT_TEMPLATE = """You are extracting real restaurant/venue recommendations from a food \
travel video transcript. The video is about food in {city}.

Read the transcript below and extract every specific, named restaurant, market, or food \
venue the host actually visits or recommends by name — not generic dish names, not \
neighborhoods, only real business names. A single video often visits several venues: keep \
each one's own details strictly separate. A dish, cuisine, or specialty the transcript \
mentions at one stop (or as a general remark about the city's food scene) belongs ONLY to \
the venue it's actually said about — never attach it to a different venue just because it's \
thematically related, mentioned nearby, or a famous local dish in that city (confirmed live: \
"Bombay Duck" mentioned once in a Mumbai video got attached to other venues' "why" lines that \
never served it).

For each one, provide:
- why: a short one-sentence line explaining what makes it worth visiting, grounded only in \
what the transcript actually says about THIS SPECIFIC venue — never invent a detail, and \
never borrow one said about a different venue in the same transcript. Write it in English \
even if the transcript itself is in another language.
- {cuisine_instruction}
- {credential_instruction}

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
features — not generic dish names, not neighborhoods, only real business names. An article \
like this often covers several restaurants: keep each one's own details strictly separate. A \
dish, cuisine, or specialty the article mentions for one restaurant (or as a general remark \
about the city's food scene) belongs ONLY to that restaurant — never attach it to a different \
one just because it's thematically related or a famous local dish in that city.

For each one, provide:
- why: a short one-sentence line explaining what makes it worth visiting, grounded only in \
what the article actually says about THIS SPECIFIC restaurant — never invent a detail, and \
never borrow one said about a different restaurant in the same article. Write it in English \
even if the article itself is in another language (confirmed live: a French Time Out Paris \
article needs this spelled out explicitly, not assumed).
- {cuisine_instruction}
- {credential_instruction}

If no real restaurants are named, return an empty list.

Article:
{article_text}
"""

# A different shape of source again: a city-ranking piece (e.g. "CDMX is
# one of the best food cities in the world") that name-drops a handful of
# chefs behind standout dishes rather than running a restaurant-by-
# restaurant list — confirmed live with a Time Out Mexico CDMX article.
# extract_venues_from_article would mostly come up empty here (there's no
# clean "restaurant X, restaurant Y" list to lift), so this asks for the
# people instead; pipeline.ingest_article_via_chefs resolves each one to a
# real restaurant via places.find_chef_venues (the same resolution
# FavoriteChefs.jsx's manually-typed chef names go through) rather than
# grounding the raw name directly, which would fail for a chef whose own
# name isn't the restaurant's name.
ARTICLE_CHEF_PROMPT_TEMPLATE = """You are extracting named chefs from a food/travel publication's \
article about the food scene in {city}. The article names specific chefs (not just dishes or \
restaurants) behind standout food there.

Read the article text below and extract every specific, named chef or restaurateur it credits — \
a real person's name, not a restaurant name, a dish name, or a generic title like "the chef." If \
the article only names a restaurant or dish without crediting a specific chef by name, skip it \
rather than guessing a name. Keep each one's own details strictly separate — a dish or detail the \
article credits to one chef belongs ONLY to that chef, never a different one just because it's \
thematically related.

For each one, provide:
- name: the chef's real name, exactly as the article gives it.
- why: a short one-sentence reason they're notable, grounded only in what the article actually \
says about THIS SPECIFIC chef — never invent a detail, and never borrow one said about a \
different chef in the same article. Write it in English even if the article itself is in \
another language.
- {cuisine_instruction}
- {credential_instruction}

If no specific chefs are named, return an empty list.

Article:
{article_text}
"""

# Separate again from ARTICLE_PROMPT_TEMPLATE: a "World's 50 Best
# Restaurants"-style list spans many cities and countries in one article,
# not one fixed city — so city/country have to be extracted per venue
# instead of supplied once for the whole piece (see WorldVenueCandidate
# and pipeline.ingest_world_article). Parameterized on venue kind
# (restaurant/bar) via {venue_singular}/{venue_plural}/{venue_plural_title}
# rather than a second near-duplicate template — unlike PROMPT_TEMPLATE vs.
# ARTICLE_PROMPT_TEMPLATE (a genuinely different source shape), this is a
# pure noun swap: "World's 50 Best Restaurants" and "World's 50 Best Bars"
# are the same kind of article about a different kind of venue.
_VENUE_KIND_WORDS = {
    "restaurant": {"singular": "restaurant", "plural": "restaurants", "plural_title": "Restaurants"},
    "bar": {"singular": "bar", "plural": "bars", "plural_title": "Bars"},
}

WORLD_ARTICLE_PROMPT_TEMPLATE = """You are extracting a ranked or curated list of top {venue_plural} \
from a prestigious food/travel publication's article — something like "The World's 50 Best \
{venue_plural_title}" or "Top 100 {venue_plural_title} in the World," spanning many different \
cities and countries at once, not just one.

Read the article text below and extract every specific, named {venue_singular} it lists — not \
generic mentions, only real, individually named {venue_plural}, spanning many cities: keep each \
one's own details strictly separate — a dish, cuisine, or specialty the article mentions for one \
entry belongs ONLY to that entry, never a different one just because it's thematically related. \
For each one:
- name: the {venue_singular}'s real name.
- city: the city it's actually located in, as stated or clearly implied by the article.
- country: the country it's located in.
- why: a short one-sentence reason it's notable, grounded only in what the article actually says \
about THIS SPECIFIC entry — never invent a detail, and never borrow one said about a different \
entry in the same article. Write it in English even if the article itself is in another language.
- {cuisine_instruction}
- {credential_instruction}

If you can't determine a specific city for an entry, skip it rather than guessing — a wrong city \
would cause it to be searched for in the wrong place entirely.

If no real {venue_plural} are named, return an empty list.

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

    return [
        {"name": c.name, "why": c.why, "cuisine": c.cuisine, "credential": c.credential}
        for c in candidates if c.name.strip()
    ]


def extract_venues(transcript: str, city: str) -> list:
    """Returns [{"name": ..., "why": ..., "cuisine": ..., "credential": ...}, ...].
    Empty list if not configured, the call fails, or no venues are named in
    the transcript.
    """
    if not configured() or not transcript.strip():
        return []
    return _extract(PROMPT_TEMPLATE.format(
        city=city, transcript=transcript[:60000],
        cuisine_instruction=_CUISINE_INSTRUCTION, credential_instruction=_CREDENTIAL_INSTRUCTION,
    ))


def extract_venues_from_article(article_text: str, city: str) -> list:
    """Same contract as extract_venues() but for a scraped article's text
    instead of a video transcript — see ARTICLE_PROMPT_TEMPLATE and
    ingest/scrape_articles.py.
    """
    if not configured() or not article_text.strip():
        return []
    return _extract(ARTICLE_PROMPT_TEMPLATE.format(
        city=city, article_text=article_text[:60000],
        cuisine_instruction=_CUISINE_INSTRUCTION, credential_instruction=_CREDENTIAL_INSTRUCTION,
    ))


def extract_chefs_from_article(article_text: str, city: str) -> list:
    """Same contract as extract_venues_from_article() but pulls named
    chefs instead of restaurant names — see ARTICLE_CHEF_PROMPT_TEMPLATE
    and pipeline.ingest_article_via_chefs, which resolves each extracted
    chef to a real restaurant via places.find_chef_venues.
    """
    if not configured() or not article_text.strip():
        return []
    return _extract(ARTICLE_CHEF_PROMPT_TEMPLATE.format(
        city=city, article_text=article_text[:60000],
        cuisine_instruction=_CUISINE_INSTRUCTION, credential_instruction=_CREDENTIAL_INSTRUCTION,
    ))


def extract_world_venues(article_text: str, kind: str = "restaurant") -> list:
    """Returns [{"name", "city", "country", "why", "cuisine", "credential"}, ...] — each venue
    carries its own city/country instead of one for the whole article, for
    a multi-city "world's best restaurants" (or, with kind="bar", "world's
    best bars") style list. Empty list if not configured, the call fails,
    or no venues (with a determinable city) are named. See
    WORLD_ARTICLE_PROMPT_TEMPLATE and pipeline.ingest_world_article.
    """
    if not configured() or not article_text.strip():
        return []

    words = _VENUE_KIND_WORDS.get(kind, _VENUE_KIND_WORDS["restaurant"])
    prompt = WORLD_ARTICLE_PROMPT_TEMPLATE.format(
        article_text=article_text[:60000],
        cuisine_instruction=_CUISINE_INSTRUCTION, credential_instruction=_WORLD_CREDENTIAL_INSTRUCTION,
        venue_singular=words["singular"], venue_plural=words["plural"], venue_plural_title=words["plural_title"],
    )
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
        {
            "name": c.name, "city": c.city, "country": c.country,
            "why": c.why, "cuisine": c.cuisine, "credential": c.credential,
        }
        for c in candidates
        if c.name.strip() and c.city.strip()
    ]
