"""Fetch YouTube video transcripts for the extraction pipeline.

Two paths:

1. Supadata (https://supadata.ai), when SUPADATA_API_KEY is set — runs on
   Supadata's own infrastructure, sidestepping the IP-based rate limiting /
   blocking that plain YouTube requests run into at any real volume
   (confirmed live: fetching 18 videos back-to-back from one home IP via
   the direct method below got rate-limited partway through).
2. Direct fetch via youtube-transcript-api, used when no Supadata key is
   configured (or as a fallback if a Supadata call itself fails). Free,
   but subject to YouTube's per-IP throttling at volume.
"""

import logging
import os

import httpx
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

SUPADATA_API_KEY = os.environ.get("SUPADATA_API_KEY", "").strip()
SUPADATA_URL = "https://api.supadata.ai/v1/youtube/transcript"

log = logging.getLogger("transcripts")


def _fetch_via_supadata(video_id: str) -> str:
    try:
        resp = httpx.get(
            SUPADATA_URL,
            params={"videoId": video_id, "text": "true"},
            headers={"x-api-key": SUPADATA_API_KEY},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Supadata transcript request failed for %s: %s", video_id, exc)
        return ""

    content = data.get("content", "")
    return content if isinstance(content, str) else ""


def _fetch_direct(video_id: str) -> str:
    try:
        api = YouTubeTranscriptApi()
        segments = api.fetch(video_id)
        return " ".join(seg.text for seg in segments)
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as exc:
        log.warning("no transcript for %s: %s", video_id, exc)
        return ""
    except Exception as exc:  # library also raises generic errors (e.g. rate limiting)
        log.warning("direct transcript fetch failed for %s: %s", video_id, exc)
        return ""


def fetch_transcript(video_id: str) -> str:
    """Returns the full transcript text for a video, or "" if unavailable
    from every configured path (disabled captions, no transcript, private/
    deleted video, rate limiting, etc).
    """
    if SUPADATA_API_KEY:
        text = _fetch_via_supadata(video_id)
        if text:
            return text
        log.warning("Supadata returned nothing for %s, falling back to a direct fetch", video_id)

    return _fetch_direct(video_id)
