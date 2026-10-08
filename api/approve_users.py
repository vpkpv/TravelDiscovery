"""Admin tool for the closed-pilot approval gate (see CLAUDE.md's "Access
control is manual Firestore approval" and auth.py's docstring) — makes
that manual approval faster without replacing it with self-serve signup:
approval is still a deliberate per-person decision, this just saves
hopping between the Firebase Auth console (to find a uid by email) and
the Firestore console (to hand-write the approved_users/{uid} doc).

Run locally — needs the same Application Default Credentials setup as
auth.py's Firestore client does for local dev (GOOGLE_APPLICATION_
CREDENTIALS, or `gcloud auth application-default login` against the
right project) plus AUTH_ENABLED=1 in api/.env.

Usage (from api/):
    python approve_users.py list                   # signed in, waiting on approval
    python approve_users.py status                  # approved users, last seen
    python approve_users.py approve a@b.com ...     # grant access (they've signed in once)
    python approve_users.py preapprove a@b.com ...  # grant access before they've ever signed in
    python approve_users.py revoke a@b.com ...      # remove access (either kind)
    python approve_users.py usage [a@b.com]         # per-user activity: sign-ins, cities, saves, clicks

A "not found" on approve/revoke means that email hasn't signed in with
Google yet — Firebase only knows about an account once it's done that at
least once, so `approve` has no uid yet to key approved_users on; either
have them sign in first and re-run `approve`, or use `preapprove` instead,
which doesn't need a uid — it writes approved_emails/{email}, and the app
itself migrates it into a real approved_users/{uid} doc the first time
that person actually signs in (see auth.is_approved).

If every command hangs for a long time or dies with a DNS/"UNAVAILABLE"
error resolving firestore.googleapis.com — confirmed live on macOS even
with working internet (`ping firestore.googleapis.com` resolves fine) —
it's gRPC's own bundled DNS resolver misbehaving, not a real network
problem. Force it to use the system resolver instead:

    GRPC_DNS_RESOLVER=native python approve_users.py ...
"""

import argparse
import datetime
import sys
import time

from dotenv import load_dotenv

load_dotenv()

import auth
from firebase_admin import auth as firebase_auth


def _approved_ref(uid: str):
    return auth.firestore_client().collection("approved_users").document(uid)


def _approved_email_ref(email: str):
    return auth.firestore_client().collection("approved_emails").document(auth._normalize_email(email))


def cmd_list(_args):
    pending = [
        user for user in firebase_auth.list_users().iterate_all()
        if not _approved_ref(user.uid).get().exists
    ]
    if not pending:
        print("No pending (signed-in-but-unapproved) users.")
        return
    print(f"{len(pending)} pending:")
    for user in pending:
        print(f"  {user.email or '(no email)'}  uid={user.uid}")


def cmd_status(_args):
    """Approved users and when they were last seen (main.py's /api/me
    bumps last_active once per sign-in — see auth.touch_last_active) —
    missing for anyone approved before that existed, or who hasn't
    opened the app since. Also lists anyone preapproved but still waiting
    on their first sign-in (see cmd_preapprove) — these migrate into the
    "approved" list above automatically once they do (auth.is_approved).
    """
    docs = list(auth.firestore_client().collection("approved_users").stream())
    pending_preapprovals = list(auth.firestore_client().collection("approved_emails").stream())

    def _fmt(ts):
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "never seen"

    if docs:
        rows = sorted(docs, key=lambda d: (d.to_dict() or {}).get("last_active", 0), reverse=True)
        print(f"{len(rows)} approved:")
        for d in rows:
            data = d.to_dict() or {}
            print(f"  {data.get('email') or f'(no email, uid={d.id})'}  last active: {_fmt(data.get('last_active'))}")
    else:
        print("No approved users yet.")

    if pending_preapprovals:
        print(f"\n{len(pending_preapprovals)} preapproved, waiting on first sign-in:")
        for d in pending_preapprovals:
            data = d.to_dict() or {}
            print(f"  {data.get('email', d.id)}")


def cmd_approve(args):
    for email in args.emails:
        try:
            user = firebase_auth.get_user_by_email(email)
        except firebase_auth.UserNotFoundError:
            print(f"  {email}: not found — they need to sign in at least once first (or use `preapprove`).")
            continue
        _approved_ref(user.uid).set({"email": email, "approved_at": int(time.time())}, merge=True)
        print(f"  {email}: approved (uid={user.uid})")


def cmd_preapprove(args):
    """Grants access before the person has ever signed in — no Firebase
    Auth uid exists yet to key approved_users on, so this writes
    approved_emails/{email} instead. auth.is_approved() checks that as a
    fallback and migrates it into a real approved_users/{uid} doc the
    moment they actually do sign in; nothing else needs to run this
    approve_users.py command again for that person.
    """
    for email in args.emails:
        _approved_email_ref(email).set({"email": email, "preapproved_at": int(time.time())})
        print(f"  {email}: preapproved — will unlock automatically on their first sign-in")


def cmd_usage(args):
    """Per-user activity summary from main.py's auth.log_event calls
    (sign_in, view_city, save, booking_click — see those call sites).
    Reads the whole usage_events collection in one query rather than a
    per-user sub-collection listing, since a closed pilot's event volume
    is small enough that this doesn't need to scale further. Sorted by
    total activity, most active first, so "who's actually using this" is
    the first thing you see rather than alphabetical by email.
    """
    approved = {d.id: (d.to_dict() or {}) for d in auth.firestore_client().collection("approved_users").stream()}
    target = args.email.strip().lower() if args.email else None
    if target:
        approved = {uid: info for uid, info in approved.items() if info.get("email", "").strip().lower() == target}
        if not approved:
            print(f"{args.email}: not an approved user.")
            return

    by_uid = {}
    for doc in auth.firestore_client().collection("usage_events").stream():
        data = doc.to_dict() or {}
        by_uid.setdefault(data.get("uid", ""), []).append(data)

    def _fmt(ts):
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "never seen"

    rows = []
    for uid, info in approved.items():
        events = by_uid.get(uid, [])
        sign_ins = sum(1 for e in events if e.get("type") == "sign_in")
        cities = {e["detail"] for e in events if e.get("type") == "view_city" and e.get("detail")}
        saves = sum(1 for e in events if e.get("type") == "save")
        clicks = sum(1 for e in events if e.get("type") == "booking_click")
        total = sign_ins + len(cities) + saves + clicks
        rows.append((total, info.get("email") or f"(uid={uid})", sign_ins, cities, saves, clicks, info.get("last_active")))
    rows.sort(key=lambda r: r[0], reverse=True)

    if not rows:
        print("No approved users yet.")
        return
    for _total, email, sign_ins, cities, saves, clicks, last_active in rows:
        print(f"  {email}: {sign_ins} sign-ins, {len(cities)} cities browsed, {saves} saves, {clicks} booking clicks"
              f"  (last active: {_fmt(last_active)})")
        if args.cities and cities:
            print(f"      cities: {', '.join(sorted(cities))}")


def cmd_revoke(args):
    for email in args.emails:
        _approved_email_ref(email).delete()  # a no-op if there was no pending preapproval
        try:
            user = firebase_auth.get_user_by_email(email)
        except firebase_auth.UserNotFoundError:
            print(f"  {email}: no Firebase account yet — any pending preapproval was cleared.")
            continue
        _approved_ref(user.uid).delete()
        print(f"  {email}: access revoked (uid={user.uid})")


def main():
    if not auth.configured():
        print("AUTH_ENABLED not set — nothing to approve against (no approval gate configured).", file=sys.stderr)
        sys.exit(1)

    # auth.py only initializes the Firebase Admin app lazily, inside
    # firestore_client() — every cmd_* function below calls firebase_auth.*
    # directly first, which needs that same app already initialized.
    # Confirmed live: skipping this raised "The default Firebase app does
    # not exist" from inside firebase_admin.auth.get_user_by_email.
    auth.firestore_client()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show signed-in users waiting on approval").set_defaults(func=cmd_list)
    sub.add_parser("status", help="show approved users and when each was last seen").set_defaults(func=cmd_status)

    p_approve = sub.add_parser("approve", help="grant access to one or more emails")
    p_approve.add_argument("emails", nargs="+")
    p_approve.set_defaults(func=cmd_approve)

    p_preapprove = sub.add_parser("preapprove", help="grant access before they've ever signed in")
    p_preapprove.add_argument("emails", nargs="+")
    p_preapprove.set_defaults(func=cmd_preapprove)

    p_usage = sub.add_parser("usage", help="show per-user activity: sign-ins, cities browsed, saves, booking clicks")
    p_usage.add_argument("email", nargs="?", help="limit to one user's email (default: everyone)")
    p_usage.add_argument("--cities", action="store_true", help="also list which cities each user browsed")
    p_usage.set_defaults(func=cmd_usage)

    p_revoke = sub.add_parser("revoke", help="remove access for one or more emails")
    p_revoke.add_argument("emails", nargs="+")
    p_revoke.set_defaults(func=cmd_revoke)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
