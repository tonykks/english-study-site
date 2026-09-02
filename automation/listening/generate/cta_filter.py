"""Filter YouTube CTA segments from learning section scope (not from full script)."""

from __future__ import annotations

import re

from automation.listening.models import Segment
from automation.listening.utils import normalize_text

CTA_PHRASES = (
    "subscribe",
    "like this video",
    "hit the like",
    "smash the like",
    "click the bell",
    "notification bell",
    "turn on notifications",
    "share this video",
    "share the video",
    "leave a comment",
    "comment below",
    "thanks for watching",
    "thank you for watching",
    "see you in the next",
    "next video",
    "support the channel",
    "channel membership",
    "patreon",
    "follow us",
    "follow me",
)


def _is_cta_segment(text: str) -> bool:
    norm = normalize_text(text)
    if not norm:
        return False
    return any(phrase in norm for phrase in CTA_PHRASES)


def segments_for_learning(segments: list[Segment], *, tail_only: bool = True) -> list[Segment]:
    """Return segments for Section/Core/Summary, excluding trailing YouTube CTA."""
    if not segments:
        return segments

    if not tail_only:
        return [s for s in segments if not _is_cta_segment(s.text_en)]

    cta_start = len(segments)
    for i in range(len(segments) - 1, -1, -1):
        if _is_cta_segment(segments[i].text_en):
            cta_start = i
        else:
            break

    if cta_start >= len(segments):
        return segments
    learning = segments[:cta_start]
    return learning if learning else segments
