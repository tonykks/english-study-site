from __future__ import annotations

from automation.listening.models import Segment


def segments_from_raw(raw: list[dict], source: str = "caption") -> list[Segment]:
    segments: list[Segment] = []
    for idx, item in enumerate(raw, start=1):
        start = float(item["start"])
        duration = float(item.get("duration", max(0.5, len(item.get("text", "")) * 0.05)))
        end = float(item.get("end", start + duration))
        text = (item.get("text") or "").strip()
        if not text:
            continue
        segments.append(
            Segment(
                segment_id=f"seg_{idx:05d}",
                start=start,
                end=end,
                text_en=text,
                source=source,
            )
        )
    return segments


def merge_overlapping_segments(chunks: list[list[Segment]]) -> list[Segment]:
    if not chunks:
        return []
    merged: list[Segment] = []
    counter = 1
    from automation.listening.utils import normalize_text

    for chunk in chunks:
        for seg in chunk:
            key = normalize_text(seg.text_en)
            if not key:
                continue
            duplicate_overlap = False
            for kept in merged:
                if normalize_text(kept.text_en) != key:
                    continue
                overlap = max(0.0, min(seg.end, kept.end) - max(seg.start, kept.start))
                if overlap > 0:
                    duplicate_overlap = True
                    break
            if duplicate_overlap:
                continue
            merged.append(
                Segment(
                    segment_id=f"seg_{counter:05d}",
                    start=seg.start,
                    end=seg.end,
                    text_en=seg.text_en,
                    source=seg.source,
                )
            )
            counter += 1
    for i, seg in enumerate(merged, start=1):
        seg.segment_id = f"seg_{i:05d}"
    return merged


def group_paragraphs(segments: list[Segment], min_sentences: int = 3, max_sentences: int = 8) -> list[str]:
    from automation.listening.utils import split_sentences

    paragraphs: list[str] = []
    buf: list[str] = []
    for seg in segments:
        for sent in split_sentences(seg.text_en):
            buf.append(sent)
            if len(buf) >= max_sentences:
                paragraphs.append(" ".join(buf))
                buf = []
    if buf:
        if paragraphs and len(buf) < min_sentences:
            paragraphs[-1] = paragraphs[-1] + " " + " ".join(buf)
        else:
            paragraphs.append(" ".join(buf))
    if not paragraphs and segments:
        paragraphs.append(" ".join(s.text_en for s in segments))
    return paragraphs
