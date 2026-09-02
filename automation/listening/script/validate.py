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
    overlapping: list[tuple[float, str, float]] = []
    for cand in asr:
        overlap = max(0.0, min(cap.end, cand.end) - max(cap.start, cand.start))
        if overlap > 0.0:
            overlapping.append((cand.start, cand.text_en, overlap))
    if not overlapping:
        return "", 0.0
    overlapping.sort(key=lambda item: item[0])
    combined = " ".join(item[1] for item in overlapping)
    return combined, max(item[2] for item in overlapping)


def cross_validate(caption: list[Segment], asr: list[Segment]) -> tuple[list[Segment], ValidationResult]:
    if not caption:
        return asr, ValidationResult(False, "No caption segments")
    if not asr:
        return caption, ValidationResult(False, "No ASR segments")

    total_duration = max(max(s.end for s in caption), max(s.end for s in asr))
    if total_duration <= 0:
        return caption, ValidationResult(False, "Invalid duration")

    divergent_duration = 0.0
    merged: list[Segment] = []
    asr_by_time = list(asr)

    for cap in caption:
        asr_text, best_overlap = _combined_asr_text(cap, asr_by_time)
        if asr_text:
            best_div = word_divergence(cap.text_en, asr_text)
            chosen_text = asr_text
        else:
            best_div = 1.0
            chosen_text = cap.text_en
        if best_div > DIVERGENCE_WORD_THRESHOLD:
            divergent_duration += cap.duration()
        merged.append(
            Segment(
                segment_id=cap.segment_id,
                start=cap.start,
                end=cap.end,
                text_en=chosen_text,
                source="verified",
            )
        )

    ratio = divergent_duration / total_duration
    if ratio > DIVERGENCE_DURATION_BLOCK:
        return merged, ValidationResult(
            False,
            f"Cross-validate divergence duration {ratio:.1%} exceeds {DIVERGENCE_DURATION_BLOCK:.0%}",
            {"divergent_ratio": ratio},
        )

    return merged, ValidationResult(True, "OK", {"divergent_ratio": ratio})
