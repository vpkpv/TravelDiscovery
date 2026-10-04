"""One-time cleanup: deletes the orphaned venues/new-york-city Firestore
doc, left behind from before data.py's New York entry was renamed to match
what Places actually returns ("New York", not "New York City" — see
places._slugify and CITIES in data.py). All of its content has been
superseded by venues/new-york since; this doc has been dead weight,
invisible to the app (only venues/new-york is ever queried), since that
fix. Run once:

    python -m ingest.cleanup_old_ny_doc

Safe to re-run — a no-op if the doc is already gone.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

import auth

OLD_DOC_ID = "new-york-city"
CURRENT_DOC_ID = "new-york"


def main():
    if not auth.configured():
        print("AUTH_ENABLED not set — nothing to clean up (no Firestore to touch).", file=sys.stderr)
        sys.exit(1)

    db = auth.firestore_client()
    old_ref = db.collection("venues").document(OLD_DOC_ID)
    old_doc = old_ref.get()
    if not old_doc.exists:
        print(f"venues/{OLD_DOC_ID} doesn't exist — already cleaned up, nothing to do.", file=sys.stderr)
        return

    # Refuse to delete unless the current doc is confirmed present and
    # actually has content — the whole point of this script is that
    # venues/new-york already has everything, so if that's somehow not
    # true, deleting the old one would be a real data loss, not cleanup.
    current_doc = db.collection("venues").document(CURRENT_DOC_ID).get()
    current_items = (current_doc.to_dict() or {}).get("items", []) if current_doc.exists else []
    if not current_items:
        print(
            f"Refusing to delete venues/{OLD_DOC_ID}: venues/{CURRENT_DOC_ID} "
            f"doesn't exist or has no items — that's not the expected state, "
            f"so this isn't just cleaning up a confirmed-superseded doc.",
            file=sys.stderr,
        )
        sys.exit(1)

    old_item_count = len((old_doc.to_dict() or {}).get("items", []))
    old_ref.delete()
    print(
        f"Deleted venues/{OLD_DOC_ID} ({old_item_count} item(s)) — "
        f"venues/{CURRENT_DOC_ID} has {len(current_items)} item(s) and is unaffected.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
