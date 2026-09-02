"""Filter YouTube CTA from learning section scope (not from full script)."""

from __future__ import annotations

import re

from automation.listening.models import Segment
from automation.listening.utils import normalize_text, split_sentences

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
    "share this story",
    "leave a comment",
    "comment below",
    "thanks for watching",
    "thank you for watching",
    "thank you for listening",
    "see you in the next",
    "next video",
    "support the channel",
    "channel membership",
    "patreon",
    "follow us",
    "follow me",
)


def _is_cta_sentence(text: str) -> bool:
    norm = normalize_text(text)
    if not norm:
        return False
    return any(phrase in norm for phrase in CTA_PHRASES)


def _split_segment_into_sentences(seg: Segment) -> list[tuple[str, float, float]]:
    sentences = split_sentences(seg.text_en)
    if not sentences:
        return []
    words = seg.text_en.split()
    if not words:
        duration = max(seg.end - seg.start, 0.01)
        return [(seg.text_en.strip(), seg.start, seg.end)] if seg.text_en.strip() else []

    total_words = len(words)
    duration = max(seg.end - seg.start, 0.01)
    step = duration / total_words

    out: list[tuple[str, float, float]] = []
    cursor = 0
    for sentence in sentences:
        sent_words = re.findall(r"\S+", sentence)
        count = max(len(sent_words), 1)
        start = seg.start + cursor * step
        end = seg.start + min(total_words, cursor + count) * step
        cursor += count
        out.append((sentence.strip(), start, max(end, start + 0.01)))
    return out


def segments_for_learning(segments: list[Segment], *, tail_only: bool = True) -> list[Segment]:
    """Return sentence-level segments for Section/Core/Summary, excluding trailing CTA sentences."""
    if not segments:
        return segments

    sentence_rows: list[tuple[str, float, float]] = []
    for seg in segments:
        sentence_rows.extend(_split_segment_into_sentences(seg))

    if not sentence_rows:
        return segments

    if tail_only:
        while sentence_rows and _is_cta_sentence(sentence_rows[-1][0]):
            sentence_rows.pop()
    else:
        sentence_rows = [(t, s, e) for t, s, e in sentence_rows if not _is_cta_sentence(t)]

    if not sentence_rows:
        return segments

    learning: list[Segment] = []
    for i, (text, start, end) in enumerate(sentence_rows, start=1):
        learning.append(
            Segment(
                segment_id=f"learn_{i:05d}",
                start=start,
                end=end,
                text_en=text,
                source="learning",
            )
        )
    return learning
