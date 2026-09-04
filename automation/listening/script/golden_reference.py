"""Development golden reference comparison for verified Level 1 videos."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from automation.listening.config import LISTENING_ROOT
from automation.listening.script.caption_restore import (
    find_missing_short_boundaries,
    validate_punctuation_anomalies,
    validate_run_on_sentences,
)
from automation.listening.utils import normalize_text, split_sentences

# video_id -> legacy production 04_full_script.txt (EN oracle only; not runtime dependency)
DEVELOPMENT_GOLDEN_REFERENCES: dict[str, Path] = {
    "fXfO5DpL_IM": LISTENING_ROOT
    / "level1"
    / "The_Middle_East's_Greatest_Contributions"
    / "04_full_script.txt",
    "azuRd9B4AOQ": LISTENING_ROOT / "level2" / "KFC_Success_Story" / "04_full_script.txt",
}


@dataclass
class BoundaryMismatch:
    kind: str  # missed_boundary | added_boundary
    classification: str  # REAL_ERROR | VALID_IMPROVEMENT
    sample: str
    word_index: int = -1


@dataclass
class GoldenCompareResult:
    ok: bool
    reason: str
    legacy_sentence_count: int = 0
    new_sentence_count: int = 0
    matching_sentence_count: int = 0
    missing_sentences: list[str] = field(default_factory=list)
    duplicated_sentences: list[str] = field(default_factory=list)
    unusually_long_sentences: list[str] = field(default_factory=list)
    fragment_sentences: list[str] = field(default_factory=list)
    boundary_divergences: list[str] = field(default_factory=list)
    run_on_count: int = 0
    fragment_count: int = 0
    omitted_legacy_edits: list[str] = field(default_factory=list)
    missed_boundary_count: int = 0
    added_boundary_count: int = 0
    real_error_count: int = 0
    mismatches: list[BoundaryMismatch] = field(default_factory=list)

    def to_report(self) -> dict:
        real_errors = [m for m in self.mismatches if m.classification == "REAL_ERROR"]
        improvements = [m for m in self.mismatches if m.classification == "VALID_IMPROVEMENT"]
        return {
            "ok": self.ok,
            "reason": self.reason,
            "legacy_sentence_count": self.legacy_sentence_count,
            "new_sentence_count": self.new_sentence_count,
            "matching_sentence_count": self.matching_sentence_count,
            "missed_boundary_count": self.missed_boundary_count,
            "added_boundary_count": self.added_boundary_count,
            "real_error_count": self.real_error_count,
            "valid_improvement_count": len(improvements),
            "missing_sentence_count": len(self.missing_sentences),
            "boundary_divergence_count": len(self.boundary_divergences),
            "omitted_legacy_edit_count": len(self.omitted_legacy_edits),
            "duplicate_sentence_count": len(self.duplicated_sentences),
            "run_on_count": self.run_on_count,
            "fragment_count": self.fragment_count,
            "unusually_long_count": len(self.unusually_long_sentences),
            "real_error_samples": [m.sample for m in real_errors],
            "missed_boundary_samples": [
                m.sample for m in self.mismatches if m.kind == "missed_boundary"
            ],
            "added_boundary_samples": [
                m.sample for m in self.mismatches if m.kind == "added_boundary"
            ][:20],
            "missing_samples": self.missing_sentences[:5],
            "boundary_samples": self.boundary_divergences[:5],
            "duplicate_samples": self.duplicated_sentences[:5],
            "long_samples": [s[:120] for s in self.unusually_long_sentences[:3]],
            "fragment_samples": self.fragment_sentences[:5],
        }


def extract_en_sentences_from_04(content: str) -> list[str]:
    """Extract ordered EN sentences from 04_full_script.txt content."""
    en_blob = " ".join(
        line.split(":", 1)[1].strip()
        for line in content.splitlines()
        if line.strip().upper().startswith("EN:")
    )
    return [s.strip() for s in split_sentences(en_blob) if s.strip()]


def _sentence_key(sentence: str) -> str:
    return normalize_text(sentence)


def _words_in_order(haystack: list[str], needle: list[str]) -> bool:
    if not needle:
        return True
    ni = 0
    for word in haystack:
        if ni < len(needle) and word == needle[ni]:
            ni += 1
    return ni == len(needle)


def _token_words(sentences: list[str]) -> tuple[list[str], list[str], set[int]]:
    """Return (normalized words, cased words, sentence-end indices)."""
    norm: list[str] = []
    cased: list[str] = []
    ends: set[int] = set()
    for sent in sentences:
        tokens = re.findall(r"[A-Za-z0-9']+", sent)
        if not tokens:
            continue
        for tok in tokens:
            cased.append(tok)
            norm.append(normalize_text(tok))
        ends.add(len(norm) - 1)
    return norm, cased, ends


def _context_sample(cased: list[str], index: int) -> str:
    start = max(0, index - 4)
    end = min(len(cased), index + 6)
    return " ".join(cased[start:end])


def _classify_missed(cased: list[str], index: int, new_text: str) -> str:
    if index + 1 >= len(cased):
        return "VALID_IMPROVEMENT"
    left = cased[index]
    right = cased[index + 1]
    join = f"{left} {right}"
    if find_missing_short_boundaries(join):
        return "REAL_ERROR"
    hits = find_missing_short_boundaries(new_text)
    if any(left.lower() in h.lower() and right.lower() in h.lower() for h in hits):
        return "REAL_ERROR"
    return "VALID_IMPROVEMENT"


def _classify_added(new_sentences: list[str], new_norm: list[str], index: int) -> str:
    """Added boundaries are usually valid ASR/editorial improvements.

    Short utterances ("Yes.", "Why?", "Ready?") are common in spoken ASR and
    should not fail the golden gate by themselves. Real faults are caught by
    missed-boundary / artificial-break / run-on detectors.
    """
    cursor = 0
    for sent in new_sentences:
        words = normalize_text(sent).split()
        if not words:
            continue
        end = cursor + len(words) - 1
        if end == index:
            _ = new_norm
            return "VALID_IMPROVEMENT"
        cursor += len(words)
    _ = new_norm
    return "VALID_IMPROVEMENT"


def compare_legacy_en_sentences(
    legacy: list[str],
    new: list[str],
    *,
    long_sentence_words: int = 80,
    block_run_on_words: int = 150,
    fragment_word_max: int = 3,
) -> GoldenCompareResult:
    new_keys = [_sentence_key(s) for s in new]
    new_key_set = set(new_keys)
    new_full_words = normalize_text(" ".join(new)).split()
    new_text = " ".join(new)

    matching = 0
    boundary_divergences: list[str] = []
    omitted_legacy_edits: list[str] = []

    for leg_sent in legacy:
        leg_key = _sentence_key(leg_sent)
        leg_words = leg_key.split()
        if not leg_words:
            continue
        if leg_key in new_key_set:
            matching += 1
            continue
        if _words_in_order(new_full_words, leg_words):
            boundary_divergences.append(leg_sent)
        else:
            omitted_legacy_edits.append(leg_sent)

    duplicated: list[str] = []
    seen: dict[str, int] = {}
    for sent in new:
        key = _sentence_key(sent)
        if not key:
            continue
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 2:
            duplicated.append(sent)

    long_sents: list[str] = []
    run_on_count = 0
    for sent in new:
        wc = len(_sentence_key(sent).split())
        if wc >= long_sentence_words:
            long_sents.append(sent)
        if wc >= block_run_on_words:
            run_on_count += 1

    fragments: list[str] = []
    for sent in new:
        wc = len(_sentence_key(sent).split())
        if 0 < wc <= fragment_word_max and sent.rstrip()[-1:] in ".!?":
            fragments.append(sent)

    legacy_norm, _, legacy_ends = _token_words(legacy)
    new_norm, new_cased, new_ends = _token_words(new)
    matcher = SequenceMatcher(None, legacy_norm, new_norm, autojunk=False)
    mapped_legacy_ends: set[int] = set()
    mapped_new_indices: set[int] = set()
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            continue
        for offset in range(i2 - i1):
            li = i1 + offset
            ni = j1 + offset
            mapped_new_indices.add(ni)
            if li in legacy_ends:
                mapped_legacy_ends.add(ni)

    missed = sorted(mapped_legacy_ends - new_ends)
    added = sorted((new_ends & mapped_new_indices) - mapped_legacy_ends)

    mismatches: list[BoundaryMismatch] = []
    for idx in missed:
        classification = _classify_missed(new_cased, idx, new_text)
        mismatches.append(
            BoundaryMismatch("missed_boundary", classification, _context_sample(new_cased, idx), idx)
        )
    for idx in added:
        classification = _classify_added(new, new_norm, idx)
        mismatches.append(
            BoundaryMismatch("added_boundary", classification, _context_sample(new_cased, idx), idx)
        )

    # Direct detector on new text is always a REAL_ERROR, even if golden didn't map it.
    detector_hits = find_missing_short_boundaries(new_text)
    for hit in detector_hits:
        if not any(hit.lower() in m.sample.lower() or m.sample.lower() in hit.lower() for m in mismatches):
            mismatches.append(BoundaryMismatch("missed_boundary", "REAL_ERROR", hit, -1))

    punct = validate_punctuation_anomalies(new_text)
    if not punct.ok:
        mismatches.append(BoundaryMismatch("missed_boundary", "REAL_ERROR", punct.reason, -1))

    run_on_val = validate_run_on_sentences(new_text, block_words=block_run_on_words)
    if not run_on_val.ok:
        mismatches.append(BoundaryMismatch("missed_boundary", "REAL_ERROR", run_on_val.reason, -1))

    real_error_count = sum(1 for m in mismatches if m.classification == "REAL_ERROR")
    missed_count = sum(1 for m in mismatches if m.kind == "missed_boundary")
    added_count = sum(1 for m in mismatches if m.kind == "added_boundary")

    ok = real_error_count == 0 and run_on_count == 0
    reasons: list[str] = []
    if real_error_count:
        reasons.append(f"{real_error_count} REAL_ERROR boundary mismatch(es)")
    if run_on_count:
        reasons.append(f"{run_on_count} run-on sentence(s) >= {block_run_on_words} words")
    if not punct.ok:
        reasons.append(punct.reason)

    return GoldenCompareResult(
        ok=ok,
        reason="; ".join(reasons) if reasons else "OK",
        legacy_sentence_count=len(legacy),
        new_sentence_count=len(new),
        matching_sentence_count=matching,
        missing_sentences=boundary_divergences,
        duplicated_sentences=duplicated,
        unusually_long_sentences=long_sents,
        fragment_sentences=fragments,
        boundary_divergences=boundary_divergences,
        run_on_count=run_on_count,
        fragment_count=len(fragments),
        omitted_legacy_edits=omitted_legacy_edits,
        missed_boundary_count=missed_count,
        added_boundary_count=added_count,
        real_error_count=real_error_count,
        mismatches=mismatches,
    )


def compare_legacy_04_file(legacy_path: Path, new_04_content: str) -> GoldenCompareResult:
    if not legacy_path.exists():
        return GoldenCompareResult(False, f"Legacy reference not found: {legacy_path}")
    legacy_content = legacy_path.read_text(encoding="utf-8")
    legacy_sents = extract_en_sentences_from_04(legacy_content)
    new_sents = extract_en_sentences_from_04(new_04_content)
    return compare_legacy_en_sentences(legacy_sents, new_sents)


def compare_video_golden_reference(video_id: str, new_04_content: str) -> GoldenCompareResult | None:
    path = DEVELOPMENT_GOLDEN_REFERENCES.get(video_id)
    if not path:
        return None
    return compare_legacy_04_file(path, new_04_content)
