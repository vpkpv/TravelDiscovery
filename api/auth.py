"""Firebase Auth verification + the closed-pilot manual approval gate.

Same pattern as FfAdvisor's approved_users/{uid}: signing in with Google
proves who you are, but doesn't grant access by itself — a document has to
exist at approved_users/{uid} in Firestore, added manually by whoever runs
the pilot. There's no self-serve signup path and no admin UI for this by
design; see CLAUDE.md's "Access control is manual Firestore approval."

Uses Application Default Credentials — on Cloud Run this is the service
account attached to the service, which needs the "Cloud Datastore User"
(or broader) IAM role for Firestore access. For local dev, set
GOOGLE_APPLICATION_CREDENTIALS to a service account key file path.
"""

import hashlib
import logging
import os
import secrets
import time

import firebase_admin
from fastapi import Header, HTTPException
from firebase_admin import auth as firebase_auth
from firebase_admin import firestore

log = logging.getLogger("auth")

_app = None
_db = None


def _ensure_initialized():
    global _app, _db
    if _app is None:
        _app = firebase_admin.initialize_app()
        _db = firestore.client()


def configured() -> bool:
    # Deliberately an explicit opt-in, not inferred from ambient platform
    # state — Cloud Run auto-sets GOOGLE_CLOUD_PROJECT on every deploy
    # regardless of whether Firebase has actually been set up, so checking
    # that would silently turn the approval gate on (locking everyone out)
    # the moment this code ships, before setup is done. AUTH_ENABLED must
    # be set on purpose, same pattern as every other integration here
    # (GOOGLE_PLACES_API_KEY, SPOTIFY_CLIENT_ID, ...).
    return os.environ.get("AUTH_ENABLED", "").strip().lower() in ("1", "true", "yes")


def firestore_client():
    _ensure_initialized()
    return _db


async def verify_token(id_token: str) -> dict:
    """Returns {"uid", "email"} for a valid token, or {} if invalid/expired."""
    _ensure_initialized()
    try:
        decoded = firebase_auth.verify_id_token(id_token)
    except Exception as exc:  # firebase_admin raises several distinct exception types
        log.info("ID token verification failed: %s", exc)
        return {}
    return {"uid": decoded.get("uid", ""), "email": decoded.get("email", "")}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def is_approved(uid: str, email: str = "") -> bool:
    """True if approved_users/{uid} exists — the normal, fast path for
    anyone who's ever been approved post-sign-in.

    Falls back to approved_emails/{email} when it doesn't: this is how
    `approve_users.py preapprove` lets someone be approved before they've
    ever signed in (uid doesn't exist yet to key approved_users on). The
    first time that fallback fires for a given uid, it migrates — writes a
    real approved_users/{uid} doc and deletes the pre-approval — so every
    later check for this account is the fast uid-only path again, and
    admin tooling (list/status) only ever has one place to look.
    """
    if firestore_client().collection("approved_users").document(uid).get().exists:
        return True
    if not email:
        return False
    pre_ref = firestore_client().collection("approved_emails").document(_normalize_email(email))
    pre = pre_ref.get()
    if not pre.exists:
        return False
    firestore_client().collection("approved_users").document(uid).set({
        "email": email,
        "approved_at": pre.to_dict().get("preapproved_at", time.time()),
    })
    pre_ref.delete()
    return True


def touch_last_active(uid: str) -> None:
    """Bumps last_active on an already-approved user's approved_users doc —
    a lightweight usage signal (when was each pilot user last seen), not a
    way to grant access: uses update() rather than set(merge=True), so it
    only ever modifies a doc that already exists and can't accidentally
    satisfy is_approved()'s plain existence check for someone who isn't.
    Best-effort — a failed write here shouldn't block anyone's request.
    """
    try:
        firestore_client().collection("approved_users").document(uid).update({"last_active": time.time()})
    except Exception as exc:
        log.warning("couldn't bump last_active for %s: %s", uid, exc)


def log_event(uid: str, email: str, event_type: str, detail: str = "") -> None:
    """Per-user usage event, read back by approve_users.py's `usage`
    command — a flat collection (not nested under approved_users) so that
    command can pull every event in one query rather than listing a
    sub-collection per user. Intentionally coarse (sign_in / view_city /
    save / booking_click, see call sites in main.py) — enough to answer
    "who's actually using this and for what," not a full analytics event
    schema. Best-effort, same stance as touch_last_active: a failed write
    here shouldn't block the request it's describing.
    """
    try:
        firestore_client().collection("usage_events").document().set({
            "uid": uid, "email": email, "type": event_type, "detail": detail, "ts": time.time(),
        })
    except Exception as exc:
        log.warning("couldn't log usage event %r for %s: %s", event_type, uid, exc)


async def current_user(authorization: str = Header(default="")) -> dict:
    """FastAPI dependency: returns {"uid", "email"} for a valid, approved
    user. Raises 401 for a missing/invalid token, 403 for a valid-but-
    unapproved account — the frontend distinguishes these (403 means "wait
    for approval", 401 means "sign in again").

    A no-op returning an anonymous pass-through user when AUTH_ENABLED
    isn't set, so every endpoint using this as a dependency keeps working
    unmodified before Firebase is set up — same graceful-degradation
    pattern as places.configured() elsewhere in this codebase.
    """
    if not configured():
        return {"uid": "anonymous", "email": ""}

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")

    user = await verify_token(authorization.removeprefix("Bearer ").strip())
    if not user:
        raise HTTPException(status_code=401, detail="invalid or expired token")

    if not is_approved(user["uid"], user["email"]):
        raise HTTPException(status_code=403, detail="account not yet approved")

    return user


# --- Personal access tokens, for the MCP server (see mcp_server.py) ---
#
# Only an already-approved Firebase user can mint one (POST /api/tokens,
# gated by the current_user dependency above) — this isn't a second way
# in, just a second credential shape for the same approved account, so an
# assistant can act on their behalf without carrying a Firebase ID token
# (which expires hourly and isn't meant for long-lived external clients).
#
# Stored as a SHA-256 hash, never the raw token — same reasoning as a
# password: nothing meaningful leaks from a Firestore read.

_TOKEN_PREFIX = "td_"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mint_token(uid: str) -> str:
    """Creates a new personal access token for an already-approved uid.
    Returns the raw token — shown once, never retrievable again (the
    Firestore doc only ever stores its hash).
    """
    token = _TOKEN_PREFIX + secrets.token_urlsafe(32)
    firestore_client().collection("api_tokens").document(_hash_token(token)).set({
        "uid": uid,
        "created_at": int(time.time()),
    })
    return token


def verify_pat(token: str) -> str:
    """Returns the uid a personal access token belongs to, or "" if it's
    invalid or belongs to an account that's since been unapproved.
    """
    if not token.startswith(_TOKEN_PREFIX):
        return ""
    doc = firestore_client().collection("api_tokens").document(_hash_token(token)).get()
    if not doc.exists:
        return ""
    uid = doc.to_dict().get("uid", "")
    return uid if uid and is_approved(uid) else ""
