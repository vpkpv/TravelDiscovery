"""Spotify OAuth: derive a music-taste signal from the user's real
listening history instead of the manual genre quick-pick.

Runs against Spotify's standard (Dev Mode) tier deliberately — see
docs/2026-08-20-taste-matched-discovery-design.md's "Spotify quota
constraint" section. Dev Mode caps the app to accounts explicitly
allowlisted in the Spotify dashboard's User Management tab, which lines up
with this app's closed-pilot access model rather than fighting it.

Flow: browser -> /auth/spotify/login (redirect to Spotify) -> user approves
-> Spotify redirects to /auth/spotify/callback with a code -> we exchange it
for a token, read the user's top artists, and redirect back to the web app
with those artist names in the URL. There's no user-account/session store
yet (that's Firebase+Firestore, a separate not-yet-built task), so the
token is used once for this exchange and discarded rather than persisted.

The taste signal here is artist names, not the manual picker's fixed genre
list (Jazz, Rock, ...) — an earlier version tried mapping Spotify's
per-artist `genres` field onto that vocabulary, but real-world testing
showed Spotify's Web API returns an empty `genres` array on essentially
every artist now (a platform-side gap, not something fixable by a better
keyword table), so there was no genre string to map from. Artist names are
always present and need no mapping.
"""

import base64
import logging
import os

import httpx

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "").strip()

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
TOP_ARTISTS_URL = "https://api.spotify.com/v1/me/top/artists"
SCOPE = "user-top-read"

log = logging.getLogger("spotify")


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


async def top_artists(access_token: str, limit: int = 6) -> list:
    """Returns up to `limit` of the user's top artist names, ranked by
    Spotify's own ordering. Empty list if the API call fails or the account
    has no top-artist data for this time range.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                TOP_ARTISTS_URL,
                params={"limit": limit, "time_range": "medium_term"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            artists = resp.json().get("items", [])
    except httpx.HTTPError as exc:
        log.warning("Spotify top-artists request failed: %s", exc)
        return []

    return [a["name"] for a in artists if a.get("name")]
