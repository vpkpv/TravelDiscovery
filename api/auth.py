"""Firebase Auth verification + the closed-pilot manual approval gate.

Same pattern as FfAdvisor's approved_users/{uid}: signing in with Google
proves who you are, but doesn't grant access by itself — a document has to
exist at approved_users/{uid} in Firestore, added manually by whoever runs
the pilot. There's still no self-serve signup path — see CLAUDE.md's
"Access control is manual Firestore approval" — but there is now a small
admin page (main.py's /api/admin/* routes, gated by ADMIN_EMAILS below)
for making that same manual, per-person decision without needing shell
access to run approve_users.py. Every grant is still a deliberate choice
by whoever runs the pilot; this just changes the interface for making it.

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


# The admin approval page (see main.py's /api/admin/* routes and
# require_admin below) is gated by a fixed, comma-separated allowlist of
# emails rather than a Firestore role — this module's own docstring notes
# there was deliberately no admin UI for the approval gate; adding one
# still doesn't make this self-serve signup (every grant is still a
# deliberate per-person decision, same as approve_users.py), it's just a
# page instead of a CLI for making that decision. A fixed allowlist is
# enough since this is expected to be the pilot's own owner(s), a handful
# of people at most, not something that itself needs admin-management UI.
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}


def is_admin(email: str) -> bool:
    return bool(email) and email.strip().lower() in ADMIN_EMAILS


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


def custom_token_for_email(email: str) -> str:
    """Mints a Firebase custom token for this email — see
    google_oauth.py for why this exists (a server-side OAuth exchange,
    sidestepping signInWithPopup's Safari flakiness). Returns an existing
    user's uid if one was ever created for this email by any sign-in
    method (Admin SDK looks these up by email regardless of which
    provider originally created the account), so someone who signed in
    before via the old popup flow keeps the exact same uid — same
    approved_users/user_prefs/saved_picks Firestore data, not a fresh
    account. Creates a new user only if none exists yet.
    """
    _ensure_initialized()
    try:
        user = firebase_auth.get_user_by_email(email)
    except firebase_auth.UserNotFoundError:
        user = firebase_auth.create_user(email=email, email_verified=True)
    return firebase_auth.create_custom_token(user.uid).decode("utf-8")


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


def log_taste_edit(uid: str, prefs: dict) -> None:
    """Append-only snapshot of this account's taste prefs right after an
    edit — a history trail of what taste looked like at each point in
    time, not just whatever user_prefs/{uid} happens to hold now. Backs
    any future "why this matched" line or before/after-trip comparison
    that needs the taste a pick was actually matched against, not
    today's. Flat collection, auto-id, same shape and best-effort stance
    as log_event — a failed write here shouldn't block saving prefs.
    """
    try:
        firestore_client().collection("taste_history").document().set({
            "uid": uid, "prefs": prefs, "ts": time.time(),
        })
    except Exception as exc:
        log.warning("couldn't log taste history for %s: %s", uid, exc)


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

    Accepts a personal access token (see mint_token/verify_pat below) as
    well as a Firebase ID token — same bearer-token endpoints this app
    already has, now usable by an external agent (e.g. a ChatGPT Action)
    carrying a PAT instead of a browser session's short-lived ID token.
    PATs are routed by their fixed prefix rather than trying one
    verification path and falling back, so a malformed/expired Firebase
    token never gets misread as a PAT lookup miss or vice versa.
    """
    if not configured():
        return {"uid": "anonymous", "email": ""}

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    raw_token = authorization.removeprefix("Bearer ").strip()

    if raw_token.startswith(_TOKEN_PREFIX):
        uid = verify_pat(raw_token)
        if not uid:
            raise HTTPException(status_code=401, detail="invalid or expired token")
        # verify_pat already re-checks is_approved itself, and a PAT
        # carries no email — nothing left to gate or enrich here.
        return {"uid": uid, "email": ""}

    user = await verify_token(raw_token)
    if not user:
        raise HTTPException(status_code=401, detail="invalid or expired token")

    if not is_approved(user["uid"], user["email"]):
        raise HTTPException(status_code=403, detail="account not yet approved")

    return user


async def require_admin(authorization: str = Header(default="")) -> dict:
    """FastAPI dependency for the admin approval page's endpoints (see
    main.py's /api/admin/* routes) — deliberately separate from
    current_user rather than layered on top of it: a personal access
    token (minted via mint_token for an external agent acting on one
    already-approved pilot user's own behalf) must never grant access to
    every other pilot user's approval status, so a PAT is rejected
    outright here rather than just happening to fail some other check.
    Gated by ADMIN_EMAILS — see that constant's own comment.
    """
    if not configured():
        raise HTTPException(status_code=404, detail="auth not enabled")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    raw_token = authorization.removeprefix("Bearer ").strip()
    if raw_token.startswith(_TOKEN_PREFIX):
        raise HTTPException(status_code=403, detail="admin access needs a direct sign-in, not a personal access token")

    user = await verify_token(raw_token)
    if not user:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    if not is_admin(user["email"]):
        raise HTTPException(status_code=403, detail="not an admin")
    return user


# --- Admin approval operations, shared by approve_users.py's CLI and
# main.py's /api/admin/* routes (the admin approval page) — one
# implementation of each, so the CLI and the page can't quietly drift
# apart on what "approve" or "revoke" actually does. ---

def list_pending_users() -> list:
    """Signed in, not yet approved — see approve_users.py's `list`."""
    return [
        {"email": u.email or "", "uid": u.uid}
        for u in firebase_auth.list_users().iterate_all()
        if not firestore_client().collection("approved_users").document(u.uid).get().exists
    ]


def list_approved_users() -> list:
    """Approved users, most recently active first — see
    approve_users.py's `status`."""
    docs = list(firestore_client().collection("approved_users").stream())
    rows = sorted(docs, key=lambda d: (d.to_dict() or {}).get("last_active", 0), reverse=True)
    return [
        {
            "uid": d.id,
            "email": (d.to_dict() or {}).get("email", ""),
            "approved_at": (d.to_dict() or {}).get("approved_at"),
            "last_active": (d.to_dict() or {}).get("last_active"),
        }
        for d in rows
    ]


def list_preapproved_emails() -> list:
    """Preapproved but still waiting on their first sign-in — see
    approve_users.py's `status`."""
    return [
        {
            "email": (d.to_dict() or {}).get("email", d.id),
            "preapproved_at": (d.to_dict() or {}).get("preapproved_at"),
        }
        for d in firestore_client().collection("approved_emails").stream()
    ]


def approve_email(email: str) -> dict:
    """Grants access to an email that's already signed in once (mirrors
    approve_users.py's `approve`). Raises ValueError if it hasn't — the
    caller should use preapprove_email instead, which doesn't need a uid.
    """
    try:
        user = firebase_auth.get_user_by_email(email)
    except firebase_auth.UserNotFoundError:
        raise ValueError(f"{email} hasn't signed in yet — use preapprove instead")
    firestore_client().collection("approved_users").document(user.uid).set(
        {"email": email, "approved_at": int(time.time())}, merge=True
    )
    return {"email": email, "uid": user.uid}


def preapprove_email(email: str) -> dict:
    """Grants access before the person has ever signed in (mirrors
    approve_users.py's `preapprove`) — see is_approved's approved_emails
    fallback, which migrates this into a real approved_users/{uid} doc
    the moment they do.
    """
    firestore_client().collection("approved_emails").document(_normalize_email(email)).set(
        {"email": email, "preapproved_at": int(time.time())}
    )
    return {"email": email}


def revoke_email(email: str) -> dict:
    """Removes access for an email — clears a pending preapproval and/or
    an approved_users doc, whichever applies (mirrors approve_users.py's
    `revoke`).
    """
    firestore_client().collection("approved_emails").document(_normalize_email(email)).delete()
    try:
        user = firebase_auth.get_user_by_email(email)
    except firebase_auth.UserNotFoundError:
        return {"email": email, "had_account": False}
    firestore_client().collection("approved_users").document(user.uid).delete()
    return {"email": email, "had_account": True, "uid": user.uid}


def usage_summary(email: str = "") -> list:
    """Per-approved-user activity: sign-ins, cities browsed, saves,
    booking clicks — the same data approve_users.py's `usage` command
    prints, as rows instead of lines. Optionally scoped to one email.
    Sorted by total activity, most active first.
    """
    approved = {d.id: (d.to_dict() or {}) for d in firestore_client().collection("approved_users").stream()}
    target = _normalize_email(email) if email else None
    if target:
        approved = {
            uid: info for uid, info in approved.items()
            if _normalize_email(info.get("email", "")) == target
        }

    by_uid = {}
    for doc in firestore_client().collection("usage_events").stream():
        data = doc.to_dict() or {}
        by_uid.setdefault(data.get("uid", ""), []).append(data)

    rows = []
    for uid, info in approved.items():
        events = by_uid.get(uid, [])
        sign_ins = sum(1 for e in events if e.get("type") == "sign_in")
        cities = sorted({e["detail"] for e in events if e.get("type") == "view_city" and e.get("detail")})
        saves = sum(1 for e in events if e.get("type") == "save")
        clicks = sum(1 for e in events if e.get("type") == "booking_click")
        rows.append({
            "uid": uid,
            "email": info.get("email") or f"(uid={uid})",
            "sign_ins": sign_ins, "cities": cities, "saves": saves,
            "booking_clicks": clicks, "last_active": info.get("last_active"),
        })
    rows.sort(key=lambda r: r["sign_ins"] + len(r["cities"]) + r["saves"] + r["booking_clicks"], reverse=True)
    return rows


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
