"""Fetch YouTube video transcripts for the extraction pipeline.

Note: this makes a real network call to YouTube's caption endpoints. It
could not be tested from the Claude Code sandbox this was written in —
that sandbox's egress policy blocks youtube.com entirely (confirmed via
the proxy status endpoint, unrelated to this code). It should work
unmodified on a normal machine or in Cloud Run, both of which have normal
internet access; test it there.
"""

import logging

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

log = logging.getLogger("transcripts")


def fetch_transcript(video_id: str) -> str:
    """Returns the full transcript text for a video, or "" if unavailable
    (disabled captions, no transcript, private/deleted video, etc).
    """
    try:
        api = YouTubeTranscriptApi()
        segments = api.fetch(video_id)
        return " ".join(seg.text for seg in segments)
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as exc:
        log.warning("no transcript for %s: %s", video_id, exc)
        return ""
    except Exception as exc:  # library also raises generic errors on parse failures
        log.warning("transcript fetch failed for %s: %s", video_id, exc)
        return ""
