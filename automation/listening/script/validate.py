from __future__ import annotations

from automation.listening.config import (
    COVERAGE_MIN,
    DIVERGENCE_DURATION_BLOCK,
    DIVERGENCE_WORD_THRESHOLD,
    DUPLICATE_BLOCK_COUNT,
    GAP_BLOCK_SECONDS,
)
from automation.listening.models import Segment, ValidationResult
from automation.listening.utils import normalize_text, split_sentences, word_divergence


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


def word_sequence_from_segments(segments: list[Segment]) -> list[str]:
    return normalize_text(" ".join(s.text_en for s in segments)).split()


def _combined_asr_text(cap: Segment, asr: list[Segment]) -> tuple[str, float]:
    """Combine overlapping ASR evidence for validation matching only (not canonical text)."""
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
    """Use caption text as canonical; ASR is independent verification evidence only."""
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
    verified: list[Segment] = []
    asr_by_time = list(asr)

    for cap in caption:
        asr_text, _best_overlap = _combined_asr_text(cap, asr_by_time)
        if asr_text and not _caption_matches_asr(cap.text_en, asr_text):
            divergent_ranges.append((cap.start, cap.end))
        verified.append(
            Segment(
                segment_id=cap.segment_id,
                start=cap.start,
                end=cap.end,
                text_en=cap.text_en,
                source="verified",
            )
        )

    divergent_duration = _merged_duration(divergent_ranges)
    ratio = divergent_duration / total_duration
    details = {"divergent_ratio": ratio, "document_divergence": document_divergence}

    if document_divergence <= DIVERGENCE_WORD_THRESHOLD:
        return verified, ValidationResult(True, "OK", details)
    if ratio > DIVERGENCE_DURATION_BLOCK:
        return verified, ValidationResult(
            False,
            f"Cross-validate divergence duration {ratio:.1%} exceeds {DIVERGENCE_DURATION_BLOCK:.0%}",
            details,
        )
    if document_divergence > DIVERGENCE_WORD_THRESHOLD:
        return verified, ValidationResult(
            False,
            f"Document divergence {document_divergence:.1%} exceeds {DIVERGENCE_WORD_THRESHOLD:.0%}",
            details,
        )

    return verified, ValidationResult(True, "OK", details)


def validate_transcript_fidelity(source: list[Segment], verified: list[Segment]) -> ValidationResult:
    """Caption word content and order must survive unchanged into verified transcript."""
    src_words = word_sequence_from_segments(source)
    ver_words = word_sequence_from_segments(verified)
    if src_words != ver_words:
        return ValidationResult(
            False,
            "Verified transcript altered caption word content or order",
            {"source_word_count": len(src_words), "verified_word_count": len(ver_words)},
        )
    return validate_no_transcript_anomalies(verified)


def validate_no_transcript_anomalies(segments: list[Segment]) -> ValidationResult:
    """Reject fragments and abnormal duplication in canonical transcript."""
    if not segments:
        return ValidationResult(False, "Empty transcript")

    for seg in segments:
        words = normalize_text(seg.text_en).split()
        if 0 < len(words) < 3 and seg.duration() >= 2.0:
            return ValidationResult(False, f"Fragment segment detected: {seg.text_en[:80]}")

    full = " ".join(s.text_en for s in segments)
    prev_sent_key = ""
    for sent in split_sentences(full):
        key = normalize_text(sent)
        if len(key.split()) < 4:
            prev_sent_key = key
            continue
        if key and key == prev_sent_key:
            return ValidationResult(False, f"Consecutive duplicate sentence in transcript: {sent[:80]}")
        prev_sent_key = key

    prev_key = ""
    for seg in segments:
        key = normalize_text(seg.text_en)
        if key and key == prev_key:
            return ValidationResult(False, "Consecutive duplicate segment in transcript")
        prev_key = key

    return ValidationResult(True, "OK")


def validate_04_en_fidelity(verified: list[Segment], content_04: str) -> ValidationResult:
    """04 EN paragraphs must preserve verified transcript words in order."""
    en_lines = [
        line.split(":", 1)[1].strip()
        for line in content_04.splitlines()
        if line.strip().upper().startswith("EN:")
    ]
    para_words = normalize_text(" ".join(en_lines)).split()
    ver_words = word_sequence_from_segments(verified)
    if para_words != ver_words:
        return ValidationResult(
            False,
            "04_full_script EN altered verified transcript word content or order",
            {"verified_word_count": len(ver_words), "paragraph_word_count": len(para_words)},
        )
    return ValidationResult(True, "OK")
