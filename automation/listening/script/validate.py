from __future__ import annotations

from automation.listening.config import (
    COVERAGE_MIN,
    DIVERGENCE_DURATION_BLOCK,
    DIVERGENCE_WORD_THRESHOLD,
    DUPLICATE_BLOCK_COUNT,
    GAP_BLOCK_SECONDS,
)
from automation.listening.models import Segment, ValidationResult
from automation.listening.utils import normalize_text, word_divergence


def validate_segments(segments: list[Segment], duration: float) -> ValidationResult:
    if not segments:
        return ValidationResult(False, "Empty transcript")

    if duration <= 0:
        duration = max(s.end for s in segments)

    covered = sum(max(0.0, s.end - s.start) for s in segments)
    coverage = covered / duration if duration > 0 else 0.0
    if coverage < COVERAGE_MIN:
        return ValidationResult(
            False,
            f"Coverage {coverage:.1%} below {COVERAGE_MIN:.0%}",
            {"coverage": coverage},
        )

    prev_end = segments[0].end
    for seg in segments[1:]:
        gap = seg.start - prev_end
        if gap > GAP_BLOCK_SECONDS:
            return ValidationResult(False, f"Gap {gap:.1f}s exceeds {GAP_BLOCK_SECONDS}s", {"gap": gap})
        if seg.start < prev_end - 0.01:
            return ValidationResult(False, "Segment order violation")
        prev_end = max(prev_end, seg.end)

    counts: dict[str, int] = {}
    for seg in segments:
        key = normalize_text(seg.text_en)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
        if counts[key] >= DUPLICATE_BLOCK_COUNT:
            return ValidationResult(False, "Abnormal duplicate block detected")

    return ValidationResult(True, "OK", {"coverage": coverage})


def _combined_asr_text(cap: Segment, asr: list[Segment]) -> tuple[str, float]:
    best_text = ""
    best_overlap = 0.0
    for cand in asr:
        overlap = max(0.0, min(cap.end, cand.end) - max(cap.start, cand.start))
        if overlap > best_overlap:
            best_overlap = overlap
            best_text = cand.text_en
    return best_text, best_overlap


def _merged_duration(ranges: list[tuple[float, float]]) -> float:
    if not ranges:
        return 0.0
    sorted_ranges = sorted(ranges, key=lambda item: item[0])
    merged: list[tuple[float, float]] = []
    for start, end in sorted_ranges:
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return sum(end - start for start, end in merged)


def _caption_matches_asr(caption: str, asr_text: str) -> bool:
    cap_norm = normalize_text(caption)
    asr_norm = normalize_text(asr_text)
    if not cap_norm:
        return True
    if cap_norm in asr_norm:
        return True
    cap_words = cap_norm.split()
    asr_words = set(asr_norm.split())
    if cap_words:
        overlap_ratio = sum(1 for word in cap_words if word in asr_words) / len(cap_words)
        if overlap_ratio >= 0.7:
            return True
    return word_divergence(caption, asr_text) <= DIVERGENCE_WORD_THRESHOLD


def cross_validate(caption: list[Segment], asr: list[Segment]) -> tuple[list[Segment], ValidationResult]:
    if not caption:
        return asr, ValidationResult(False, "No caption segments")
    if not asr:
        return caption, ValidationResult(False, "No ASR segments")

    total_duration = max(max(s.end for s in caption), max(s.end for s in asr))
    if total_duration <= 0:
        return caption, ValidationResult(False, "Invalid duration")

    document_divergence = word_divergence(
        " ".join(s.text_en for s in caption),
        " ".join(s.text_en for s in asr),
    )

    divergent_ranges: list[tuple[float, float]] = []
    merged: list[Segment] = []
    asr_by_time = list(asr)

    for cap in caption:
        asr_text, _best_overlap = _combined_asr_text(cap, asr_by_time)
        if asr_text and _caption_matches_asr(cap.text_en, asr_text):
            chosen_text = asr_text
            is_divergent = False
        elif asr_text:
            chosen_text = asr_text
            is_divergent = True
        else:
            chosen_text = cap.text_en
            is_divergent = True
        if is_divergent:
            divergent_ranges.append((cap.start, cap.end))
        merged.append(
            Segment(
                segment_id=cap.segment_id,
                start=cap.start,
                end=cap.end,
                text_en=chosen_text,
                source="verified",
            )
        )

    divergent_duration = _merged_duration(divergent_ranges)
    ratio = divergent_duration / total_duration
    details = {"divergent_ratio": ratio, "document_divergence": document_divergence}
    if document_divergence <= DIVERGENCE_WORD_THRESHOLD:
        return merged, ValidationResult(True, "OK", details)
    if ratio > DIVERGENCE_DURATION_BLOCK:
        return merged, ValidationResult(
            False,
            f"Cross-validate divergence duration {ratio:.1%} exceeds {DIVERGENCE_DURATION_BLOCK:.0%}",
            details,
        )

    return merged, ValidationResult(True, "OK", details)
