"""One-off: write ingest/output.json into Firestore without re-grounding.

For when a run.py invocation already paid for Places/Gemini lookups and
wrote output.json, but AUTH_ENABLED wasn't set so none of it reached
Firestore (see run.py's own warning when db is None). Re-running run.py
to fix that re-pays for every lookup; this just replays the already-fetched
output.json through the same per-city merge run.py itself uses, so nothing
previously ingested for a city (from a source this file doesn't cover) is
lost.

Usage: source deploy-env.sh && python -m ingest.load_output_json
"""
import json
import sys
from pathlib import Path

import auth
import places

OUTPUT_FILE = Path(__file__).resolve().parent / "output.json"


def main():
    if not auth.configured():
        print("AUTH_ENABLED not set — nothing to load into. See api/.env.example "
              "(source deploy-env.sh first).", file=sys.stderr)
        sys.exit(1)
    db = auth.firestore_client()

    items = json.loads(OUTPUT_FILE.read_text())
    by_city = {}
    for item in items:
        by_city.setdefault(item["city"], []).append(item)

    for city, city_items in by_city.items():
        slug = places._slugify(city)
        doc = db.collection("venues").document(slug).get()
        existing = list((doc.to_dict() or {}).get("items", [])) if doc.exists else []
        # Same merge rule as run.py's own _merge_items: a same-named new item
        # replaces its existing counterpart, everything else passes through.
        by_name = {places._normalize(i["name"]): i for i in existing if i.get("name")}
        for new_item in city_items:
            by_name[places._normalize(new_item["name"])] = new_item
        merged = list(by_name.values())
        db.collection("venues").document(slug).set({"city": city, "items": merged})
        print(f"{city}: wrote {len(merged)} total items ({len(city_items)} from output.json)")


if __name__ == "__main__":
    main()
