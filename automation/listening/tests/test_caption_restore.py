from __future__ import annotations

from automation.listening.models import Segment
from automation.listening.script.caption_restore import (
    fix_artificial_period_breaks,
    join_caption_fragments,
    restore_caption_segments,
    restore_caption_text,
    validate_no_artificial_sentence_breaks,
    words_unchanged,
)
from automation.listening.script.canonical import segments_from_raw


def _sample_fragments() -> list[Segment]:
    raw = [
        {"start": 0.0, "duration": 2.0, "text": "The Middle East became a center of"},
        {"start": 2.0, "duration": 2.0, "text": "learning and exchange"},
        {"start": 4.0, "duration": 2.0, "text": "His faith became the"},
        {"start": 6.0, "duration": 2.0, "text": "foundation of Judaism"},
    ]
    return segments_from_raw(raw, source="caption")


def _asr_for_samples() -> list[Segment]:
    raw = [
        {
            "start": 0.0,
            "duration": 4.0,
            "text": "The Middle East became a center of learning and exchange.",
        },
        {"start": 4.0, "duration": 4.0, "text": "His faith became the foundation of Judaism."},
    ]
    return segments_from_raw(raw, source="asr")


def test_join_preserves_word_sequence():
    segments = _sample_fragments()
    joined = join_caption_fragments(segments)
    assert "center of learning" in joined.lower()
    assert "foundation of judaism" in joined.lower()


def test_fix_artificial_period_breaks():
    broken = "The Middle East became a center of. Learning and exchange."
    fixed = fix_artificial_period_breaks(broken)
    assert fixed.rstrip(".") == "The Middle East became a center of learning and exchange"
    assert validate_no_artificial_sentence_breaks(fixed.rstrip(".")).ok


def test_restore_two_fragments_one_sentence():
    segments = _sample_fragments()[:2]
    asr = _asr_for_samples()[:1]
    restored = restore_caption_text(segments, asr)
    assert words_unchanged(join_caption_fragments(segments), restored)
    assert "center of learning and exchange" in restored.lower()
    assert validate_no_artificial_sentence_breaks(restored).ok


def test_restore_multiple_fragments_word_sequence_unchanged():
    segments = _sample_fragments()
    asr = _asr_for_samples()
    before = join_caption_fragments(segments)
    restored = restore_caption_text(segments, asr)
    assert words_unchanged(before, restored)


def test_artificial_break_detection_blocks():
    bad = "one of the first. Writing systems in history."
    result = validate_no_artificial_sentence_breaks(bad)
    assert not result.ok


def test_restore_caption_segments_complete_sentences():
    segments = _sample_fragments()
    asr = _asr_for_samples()
    restored_segs = restore_caption_segments(segments, asr)
    assert len(restored_segs) == 2
    assert restored_segs[0].text_en.endswith(".")
    assert "learning and exchange" in restored_segs[0].text_en


def test_real_sentence_end_preserved():
    text = "Water made the land good for farming. Because of the rivers, people stayed."
    assert validate_no_artificial_sentence_breaks(text).ok


def test_run_on_split_after_alignment_gap():
    from automation.listening.script.caption_restore import restore_sentence_boundaries, validate_run_on_sentences

    joined = (
        "The Persians ruled a huge area including modern day Iran Iraq and parts of Turkey "
        "They were known for fairness good roads and trade "
        "Merchants could travel safely and sell goods like spices silk and gold"
    )
    asr = (
        "The Persians ruled a huge area including modern-day Iran, Iraq, and parts of Turkey. "
        "They were known for fairness, good roads, and trade. "
        "Merchants could travel safely and sell goods like spices, silk, and gold."
    )
    restored = restore_sentence_boundaries(joined, asr)
    assert "Turkey." in restored or "turkey." in restored.lower()
    assert validate_run_on_sentences(restored).ok
