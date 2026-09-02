from __future__ import annotations

from automation.listening.models import Segment
from automation.listening.script.canonical import segments_from_raw
from automation.listening.utils import cleanup_caption_text


def fetch_caption_segments(video_id: str) -> tuple[list[Segment], bool, float]:
    """Returns (segments, is_auto_generated, inferred_duration)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise RuntimeError("youtube-transcript-api is required") from exc

    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)

    transcript = None
    is_auto = True
    for t in transcript_list:
        if t.language_code.startswith("en") and not t.is_generated:
            transcript = t.fetch()
            is_auto = False
            break
    if transcript is None:
        for t in transcript_list:
            if t.language_code.startswith("en"):
                transcript = t.fetch()
                is_auto = bool(t.is_generated)
                break
    if transcript is None:
        raise RuntimeError("No English captions available")

    raw = []
    for item in transcript:
        text = cleanup_caption_text(item.text.replace("\n", " "))
        raw.append({"start": float(item.start), "duration": float(item.duration), "text": text})

    segments = segments_from_raw(raw, source="caption")
    duration = 0.0
    if segments:
        duration = max(s.end for s in segments)
    return segments, is_auto, duration
