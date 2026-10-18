"""Server-side Google OAuth, used only to sign a user in — this is NOT
the same Google sign-in as firebase.js used to do with signInWithPopup.

Why this exists: signInWithPopup (and signInWithRedirect before it — see
firebase.js's own postmortem comment) both depend on a hidden iframe
Firebase's SDK uses to hand the sign-in result back to the app, and
Safari's storage partitioning (ITP) makes that handback genuinely flaky —
confirmed live, worst right after the user clears history/cookies. There's
no fix for that left to try on the client-SDK side.

This sidesteps it entirely with a plain, textbook OAuth 2.0 authorization
code flow against Google directly: a full top-level browser redirect (not
a popup, not an XHR — same reasoning as spotify.py's own flow) to Google's
consent screen, a redirect back here with a code, and a server-to-server
exchange for that code — no browser-mediated handback, no iframe, nothing
for Safari's privacy protections to partition. See main.py's
/auth/google/login and /auth/google/callback for the request handlers;
this module only talks to Google.

Once we have a verified email from Google, auth.py's
custom_token_for_email mints a Firebase custom token for that email (an
existing user if one already exists — e.g. someone who signed in via the
old popup flow keeps the same uid/Firestore data — or a new one), and the
browser is redirected back to the web app with that token, which
firebase.js's completeSignInFromUrl exchanges for a real session via
signInWithCustomToken. That call is a plain authenticated network request,
not dependent on any popup/redirect choreography, so it works the same on
Safari as everywhere else.
"""

import logging
import os

import httpx

CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "").strip()

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
SCOPE = "openid email"

log = logging.getLogger("google_oauth")


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
        # Without this, a user who's signed into multiple Google accounts
        # gets silently signed back in with whichever one Google remembers
        # last, no chance to pick — surprising for anyone using this on a
        # shared/work machine.
        "prompt": "select_account",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> str:
    """Returns an access token, or "" if the exchange fails."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                },
            )
            resp.raise_for_status()
            return resp.json().get("access_token", "")
    except httpx.HTTPError as exc:
        log.warning("Google token exchange failed: %s", exc)
        return ""


async def get_verified_email(access_token: str) -> str:
    """Returns the account's email, or "" if the request fails or the
    email isn't verified on Google's side — an unverified email is one
    anyone could have typed in without proving they own it, not a safe
    identity to sign someone into this app as.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
            resp.raise_for_status()
            info = resp.json()
    except httpx.HTTPError as exc:
        log.warning("Google userinfo request failed: %s", exc)
        return ""

    if not info.get("email_verified"):
        log.warning("Google account %r has an unverified email — refusing to sign in", info.get("email"))
        return ""
    return info.get("email", "")
