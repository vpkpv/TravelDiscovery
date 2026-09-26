"""One-time backfill: tags cuisine on every existing Firestore venue that
predates cuisine tagging at ingestion time (extract.py and curated_food.py
only started tagging cuisine after ~237 venues were already ingested).
Run once after pulling that change:

    python -m ingest.backfill_cuisine

Safe to re-run — only classifies items missing a cuisine tag, so a
partial or interrupted run just picks up where it left off next time.
Music items are untouched; cuisine is a food-only concept.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

import auth
from ingest.classify_cuisine import classify_batch, configured as gemini_configured


def main():
    if not gemini_configured():
        print("GEMINI_API_KEY not set — nothing to do. See api/.env.example.", file=sys.stderr)
        sys.exit(1)
    if not auth.configured():
        print("AUTH_ENABLED not set — nothing to backfill (no Firestore to read/write).", file=sys.stderr)
        sys.exit(1)

    db = auth.firestore_client()
    docs = list(db.collection("venues").stream())
    print(f"Found {len(docs)} cities in Firestore.", file=sys.stderr)

    total_tagged = 0
    for doc in docs:
        city_data = doc.to_dict()
        city = city_data.get("city", doc.id)
        items = city_data.get("items", [])
        untagged = [
            it for it in items
            if it.get("type") == "food" and not (it.get("cuisine") or "").strip()
        ]
        if not untagged:
            continue

        print(f"{city}: classifying {len(untagged)} untagged food item(s)...", file=sys.stderr)
        tags = classify_batch([{"name": it["name"], "why": it.get("why", ""), "city": city} for it in untagged])

        changed = False
        for it in items:
            if it.get("type") == "food" and not (it.get("cuisine") or "").strip():
                tag = tags.get(it["name"])
                if tag:
                    it["cuisine"] = tag
                    changed = True

        if changed:
            doc.reference.set({"city": city, "items": items})
            newly_tagged = sum(1 for it in items if it.get("type") == "food" and it.get("cuisine"))
            total_tagged += newly_tagged
            print(f"  -> wrote back, {newly_tagged} food item(s) tagged for {city}", file=sys.stderr)
        else:
            print("  -> classification returned nothing usable for this batch, left as-is", file=sys.stderr)

    print(f"Done. {total_tagged} food item(s) tagged across {len(docs)} cities.", file=sys.stderr)


if __name__ == "__main__":
    main()
