"""Development golden reference comparison for verified Level 1 videos."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from automation.listening.config import LISTENING_ROOT
from automation.listening.utils import normalize_text, split_sentences

# video_id -> legacy production 04_full_script.txt (EN oracle only; not runtime dependency)
DEVELOPMENT_GOLDEN_REFERENCES: dict[str, Path] = {
    "fXfO5DpL_IM": LISTENING_ROOT
    / "level1"
    / "The_Middle_East's_Greatest_Contributions"
    / "04_full_script.txt",
}


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

    def to_report(self) -> dict:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "legacy_sentence_count": self.legacy_sentence_count,
            "new_sentence_count": self.new_sentence_count,
            "matching_sentence_count": self.matching_sentence_count,
            "missing_sentence_count": len(self.missing_sentences),
            "boundary_divergence_count": len(self.boundary_divergences),
            "omitted_legacy_edit_count": len(self.omitted_legacy_edits),
            "duplicate_sentence_count": len(self.duplicated_sentences),
            "run_on_count": self.run_on_count,
            "fragment_count": self.fragment_count,
            "unusually_long_count": len(self.unusually_long_sentences),
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


def compare_legacy_en_sentences(
    legacy: list[str],
    new: list[str],
    *,
    max_boundary_divergence_ratio: float = 0.10,
    long_sentence_words: int = 80,
    block_run_on_words: int = 150,
    fragment_word_max: int = 3,
) -> GoldenCompareResult:
    new_keys = [_sentence_key(s) for s in new]
    new_key_set = set(new_keys)
    new_full_words = normalize_text(" ".join(new)).split()

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
        if 0 < wc <= fragment_word_max and sent.rstrip()[-1] in ".!?":
            fragments.append(sent)

    comparable = max(len(legacy) - len(omitted_legacy_edits), 1)
    boundary_ratio = len(boundary_divergences) / comparable
    match_ratio = matching / len(legacy) if legacy else 1.0

    ok = True
    reasons: list[str] = []
    if run_on_count > 0:
        ok = False
        reasons.append(f"{run_on_count} run-on sentence(s) >= {block_run_on_words} words")
    if boundary_ratio > max_boundary_divergence_ratio:
        ok = False
        reasons.append(
            f"boundary divergence ratio {boundary_ratio:.1%} exceeds {max_boundary_divergence_ratio:.0%}"
        )
    if match_ratio < 0.75 and len(legacy) > 20:
        reasons.append(f"matching ratio {match_ratio:.1%} (informational)")

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
