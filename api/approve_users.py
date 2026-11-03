"""Admin tool for the closed-pilot approval gate (see CLAUDE.md's "Access
control is manual Firestore approval" and auth.py's docstring) — makes
that manual approval faster without replacing it with self-serve signup:
approval is still a deliberate per-person decision, this just saves
hopping between the Firebase Auth console (to find a uid by email) and
the Firestore console (to hand-write the approved_users/{uid} doc).

The same operations are also available from a browser, behind sign-in +
ADMIN_EMAILS, via main.py's /api/admin/* routes — this CLI and that page
both call the same auth.py functions (list_pending_users, approve_email,
etc.), so neither one can drift from what the other actually does. Use
whichever's more convenient; nothing here requires the page or vice versa.

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

from dotenv import load_dotenv

load_dotenv()

import auth


def _fmt(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "never seen"


def cmd_list(_args):
    pending = auth.list_pending_users()
    if not pending:
        print("No pending (signed-in-but-unapproved) users.")
        return
    print(f"{len(pending)} pending:")
    for u in pending:
        print(f"  {u['email'] or '(no email)'}  uid={u['uid']}")


def cmd_status(_args):
    """Approved users and when they were last seen (main.py's /api/me
    bumps last_active once per sign-in — see auth.touch_last_active) —
    missing for anyone approved before that existed, or who hasn't
    opened the app since. Also lists anyone preapproved but still waiting
    on their first sign-in (see cmd_preapprove) — these migrate into the
    "approved" list above automatically once they do (auth.is_approved).
    """
    approved = auth.list_approved_users()
    preapproved = auth.list_preapproved_emails()

    if approved:
        print(f"{len(approved)} approved:")
        for u in approved:
            label = u["email"] or f"(no email, uid={u['uid']})"
            print(f"  {label}  last active: {_fmt(u['last_active'])}")
    else:
        print("No approved users yet.")

    if preapproved:
        print(f"\n{len(preapproved)} preapproved, waiting on first sign-in:")
        for u in preapproved:
            print(f"  {u['email']}")


def cmd_approve(args):
    for email in args.emails:
        try:
            result = auth.approve_email(email)
        except ValueError:
            print(f"  {email}: not found — they need to sign in at least once first (or use `preapprove`).")
            continue
        print(f"  {email}: approved (uid={result['uid']})")


def cmd_preapprove(args):
    """Grants access before the person has ever signed in — no Firebase
    Auth uid exists yet to key approved_users on, so this writes
    approved_emails/{email} instead. auth.is_approved() checks that as a
    fallback and migrates it into a real approved_users/{uid} doc the
    moment they actually do sign in; nothing else needs to run this
    approve_users.py command again for that person.
    """
    for email in args.emails:
        auth.preapprove_email(email)
        print(f"  {email}: preapproved — will unlock automatically on their first sign-in")


def cmd_usage(args):
    """Per-user activity summary from main.py's auth.log_event calls
    (sign_in, view_city, save, booking_click — see those call sites).
    Sorted by total activity, most active first, so "who's actually
    using this" is the first thing you see rather than alphabetical by
    email.
    """
    rows = auth.usage_summary(args.email or "")
    if args.email and not rows:
        print(f"{args.email}: not an approved user.")
        return
    if not rows:
        print("No approved users yet.")
        return
    for r in rows:
        print(f"  {r['email']}: {r['sign_ins']} sign-ins, {len(r['cities'])} cities browsed, {r['saves']} saves, "
              f"{r['booking_clicks']} booking clicks  (last active: {_fmt(r['last_active'])})")
        if args.cities and r["cities"]:
            print(f"      cities: {', '.join(r['cities'])}")


def cmd_revoke(args):
    for email in args.emails:
        result = auth.revoke_email(email)
        if result["had_account"]:
            print(f"  {email}: access revoked (uid={result['uid']})")
        else:
            print(f"  {email}: no Firebase account yet — any pending preapproval was cleared.")


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
