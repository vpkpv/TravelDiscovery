"""Spotify OAuth: derive a music-taste profile from the user's real listening
history instead of the manual genre quick-pick.

Runs against Spotify's standard (Dev Mode) tier deliberately — see
docs/2026-08-20-taste-matched-discovery-design.md's "Spotify quota
constraint" section. Dev Mode caps the app to accounts explicitly
allowlisted in the Spotify dashboard's User Management tab, which lines up
with this app's closed-pilot access model rather than fighting it.

Flow: browser -> /auth/spotify/login (redirect to Spotify) -> user approves
-> Spotify redirects to /auth/spotify/callback with a code -> we exchange it
for a token, read the user's top artists, and map their genres onto this
app's fixed MUSIC_GENRES vocabulary (the same list the manual picker uses,
so both paths produce an identical taste-profile shape per the design doc).
We then redirect back to the web app with the derived genres in the URL —
there's no user-account/session store yet (that's Firebase+Firestore, a
separate not-yet-built task), so the token is used once for this exchange
and discarded rather than persisted.
"""

import base64
import logging
import os
from collections import Counter

import httpx

from data import MUSIC_GENRES

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "").strip()

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
TOP_ARTISTS_URL = "https://api.spotify.com/v1/me/top/artists"
SCOPE = "user-top-read"

log = logging.getLogger("spotify")

# Keyword -> app genre. A Spotify artist genre (e.g. "chicago blues", "indie
# folk") is matched by substring against each keyword; one Spotify genre can
# credit multiple app genres (e.g. "indie rock" credits both).
_GENRE_KEYWORDS = {
    "Jazz": ["jazz"],
    "Fado / World": ["fado", "world"],
    "Classical": ["classical", "orchestra", "opera"],
    "Rock": ["rock"],
    "Indie": ["indie"],
    "Electronic": ["electronic", "edm", "house", "techno", "dance", "dubstep"],
    "Soul / R&B": ["soul", "r&b", "rnb", "funk"],
    "Country": ["country"],
    "Blues": ["blues"],
    "Folk": ["folk", "singer-songwriter"],
    "Pop": ["pop"],
    "Hip-Hop / Rap": ["hip hop", "hip-hop", "rap", "trap"],
    "Latin": ["latin", "reggaeton", "salsa", "bachata", "banda", "corrido"],
}


def configured() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET and REDIRECT_URI)


def authorize_url(state: str) -> str:
    from urllib.parse import urlencode

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": SCOPE,
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> str:
    """Returns an access token, or "" if the exchange fails."""
    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                },
                headers={
                    "Authorization": f"Basic {basic}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            resp.raise_for_status()
            return resp.json().get("access_token", "")
    except httpx.HTTPError as exc:
        log.warning("Spotify token exchange failed: %s", exc)
        return ""


async def top_genres(access_token: str, limit: int = 6) -> list:
    """Returns up to `limit` app-vocabulary genres (from MUSIC_GENRES),
    ranked by how often they show up across the user's top artists. Empty
    list if the API call fails or nothing maps onto our vocabulary.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                TOP_ARTISTS_URL,
                params={"limit": 50, "time_range": "medium_term"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            body = resp.json()
            artists = body.get("items", [])
    except httpx.HTTPError as exc:
        log.warning("Spotify top-artists request failed: %s", exc)
        return []

    # Temporary: pin down whether an empty result means "no top artists at
    # all" (thin listening history under medium_term) vs "artists returned,
    # but Spotify's genres field on them is empty" — two different problems.
    log.warning(
        "Spotify top-artists: %d returned, total=%s, names=%s",
        len(artists), body.get("total"), [a.get("name") for a in artists[:10]],
    )

    counts = Counter()
    raw_seen = set()
    for artist in artists:
        for raw_genre in artist.get("genres", []):
            raw_seen.add(raw_genre)
            raw_lower = raw_genre.lower()
            for app_genre, keywords in _GENRE_KEYWORDS.items():
                if any(kw in raw_lower for kw in keywords):
                    counts[app_genre] += 1

    matched = [g for g, _ in counts.most_common(limit) if g in MUSIC_GENRES]
    if not matched:
        # Temporary: surfaces exactly what didn't map, so the keyword table
        # can be fixed with real data instead of guesswork. Remove once the
        # vocabulary has stabilized against real-world Spotify genre tags.
        log.warning("no app genre matched; raw Spotify genres seen: %s", sorted(raw_seen))
    return matched
