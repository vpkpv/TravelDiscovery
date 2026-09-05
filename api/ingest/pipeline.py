"""Orchestrates one video end to end: transcript -> Gemini extraction ->
Places grounding. This is the real version of what api/data.py currently
hand-writes for Lisbon.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # import places, sibling to ingest/

import places
from ingest.extract import extract_venues
from ingest.transcripts import fetch_transcript


async def ingest_video(video_id: str, city: str, source_label: str) -> list:
    """Returns a list of grounded venue dicts shaped like api/data.py's
    RESULTS entries (missing only an id, which the caller assigns).
    Empty list if the transcript is unavailable, Gemini finds nothing, or
    nothing grounds against a real Places record.
    """
    transcript = fetch_transcript(video_id)
    if not transcript:
        return []

    candidates = extract_venues(transcript, city)

    grounded = []
    for candidate in candidates:
        ground = await places.find_place(candidate["name"], city)
        if not ground:
            continue  # ungrounded — could be a mishear, a closed business, or hallucinated
        grounded.append({
            "type": "food",
            "name": candidate["name"],
            "meta": source_label,
            "rating": ground.get("rating"),
            "addr": ground["addr"],
            "why": candidate["why"],
            "source_video_id": video_id,
        })
    return grounded
