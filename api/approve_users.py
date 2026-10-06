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
    python approve_users.py list                 # signed in, waiting on approval
    python approve_users.py status                # approved users, last seen
    python approve_users.py approve a@b.com ...   # grant access
    python approve_users.py revoke a@b.com ...    # remove access

A "not found" on approve/revoke means that email hasn't signed in with
Google yet — Firebase only knows about an account once it's done that at
least once, so there's nothing yet to approve by email; ask them to sign
in first, then re-run.

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
    opened the app since.
    """
    docs = list(auth.firestore_client().collection("approved_users").stream())
    if not docs:
        print("No approved users yet.")
        return

    def _fmt(ts):
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "never seen"

    rows = sorted(docs, key=lambda d: (d.to_dict() or {}).get("last_active", 0), reverse=True)
    print(f"{len(rows)} approved:")
    for d in rows:
        data = d.to_dict() or {}
        print(f"  {data.get('email') or f'(no email, uid={d.id})'}  last active: {_fmt(data.get('last_active'))}")


def cmd_approve(args):
    for email in args.emails:
        try:
            user = firebase_auth.get_user_by_email(email)
        except firebase_auth.UserNotFoundError:
            print(f"  {email}: not found — they need to sign in at least once first.")
            continue
        _approved_ref(user.uid).set({"email": email, "approved_at": int(time.time())}, merge=True)
        print(f"  {email}: approved (uid={user.uid})")


def cmd_revoke(args):
    for email in args.emails:
        try:
            user = firebase_auth.get_user_by_email(email)
        except firebase_auth.UserNotFoundError:
            print(f"  {email}: not found in Firebase Auth.")
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

    p_revoke = sub.add_parser("revoke", help="remove access for one or more emails")
    p_revoke.add_argument("emails", nargs="+")
    p_revoke.set_defaults(func=cmd_revoke)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
