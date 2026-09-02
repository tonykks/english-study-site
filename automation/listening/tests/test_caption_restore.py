from __future__ import annotations

import re

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


def test_missing_boundary_easy_wars_restored():
    from automation.listening.script.caption_restore import (
        restore_sentence_boundaries,
        validate_missing_short_boundaries,
        words_unchanged,
    )

    text = "It was not always easy Wars invasions and struggles threatened communities"
    restored = restore_sentence_boundaries(text)
    assert words_unchanged(text, restored)
    assert re.search(r"easy\.\s+Wars", restored, re.I)
    assert validate_missing_short_boundaries(restored).ok


def test_missing_boundary_deserts_ships_restored():
    from automation.listening.script.caption_restore import restore_sentence_boundaries, words_unchanged

    text = "Caravans carried goods across deserts Ships sailed on rivers and seas"
    restored = restore_sentence_boundaries(text)
    assert words_unchanged(text, restored)
    assert re.search(r"deserts\.\s+Ships", restored, re.I)


def test_missing_boundary_other_doctors_restored():
    from automation.listening.script.caption_restore import restore_sentence_boundaries, words_unchanged

    text = "Neighbors help each other Doctors care for the sick"
    restored = restore_sentence_boundaries(text)
    assert words_unchanged(text, restored)
    assert re.search(r"other\.\s+Doctors", restored, re.I)


def test_punctuation_anomaly_removed_and_blocked():
    from automation.listening.script.caption_restore import (
        fix_punctuation_anomalies,
        validate_punctuation_anomalies,
        words_unchanged,
    )

    broken = "Life was not easy,. schools, and hospitals were built,."
    fixed = fix_punctuation_anomalies(broken)
    assert ",." not in fixed
    assert validate_punctuation_anomalies(fixed).ok
    assert words_unchanged(broken, fixed)
    assert not validate_punctuation_anomalies("communities,.").ok


def test_asr_internal_commas_preserved():
    from automation.listening.script.caption_restore import restore_sentence_boundaries, words_unchanged

    caption = "Long ago before modern cities and technology people lived very simple lives"
    asr = "Long ago, before modern cities and technology, people lived very simple lives."
    restored = restore_sentence_boundaries(caption, asr)
    assert words_unchanged(caption, restored)
    assert "ago," in restored
    assert "technology," in restored
    assert restored.count(",") >= 2


def test_asr_list_commas_preserved():
    from automation.listening.script.caption_restore import restore_sentence_boundaries, words_unchanged

    caption = "Countries like Britain France and Italy wanted control"
    asr = "Countries like Britain, France, and Italy wanted control."
    restored = restore_sentence_boundaries(caption, asr)
    assert words_unchanged(caption, restored)
    assert "Britain," in restored
    assert "France," in restored


def test_period_only_flattening_rejected():
    from automation.listening.generate.data_files import validate_04_en_punctuation

    sentences = " ".join(f"This is sentence number {i}." for i in range(45))
    content = f"[Paragraph 1]\nEN: {sentences}\nKR: 예시입니다."
    ok, reason = validate_04_en_punctuation(content)
    assert not ok
    assert "flattened" in reason


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
