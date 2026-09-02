from __future__ import annotations

from automation.listening.models import Segment
from automation.listening.script.validate import (
    cross_validate,
    validate_04_en_fidelity,
    validate_no_transcript_anomalies,
    validate_transcript_fidelity,
    word_sequence_from_segments,
)
from automation.listening.generate.data_files import assemble_04_en
from automation.listening.utils import normalize_text


def test_cross_validate_pass_keeps_caption():
    caption = [Segment("c1", 0, 5, "hello world today")]
    asr = [Segment("a1", 0, 5, "hello world today")]
    merged, result = cross_validate(caption, asr)
    assert result.ok
    assert merged[0].text_en == "hello world today"
    assert merged[0].source == "verified"


def test_cross_validate_keeps_caption_on_asr_mismatch():
    caption = [Segment("c1", 0, 5, "caption text segment here")]
    asr = [Segment("a1", 0, 5, "completely different words only")]
    merged, result = cross_validate(caption, asr)
    assert merged[0].text_en == "caption text segment here"


def test_cross_validate_blocked_on_high_divergence():
    caption = []
    asr = []
    for i in range(20):
        cap_text = "caption text segment here"
        asr_text = "completely different words only" if i < 10 else cap_text
        caption.append(Segment(f"c{i}", i * 5, i * 5 + 5, cap_text))
        asr.append(Segment(f"a{i}", i * 5, i * 5 + 5, asr_text))
    merged, result = cross_validate(caption, asr)
    assert not result.ok
    assert merged[0].text_en == "caption text segment here"


def test_one_asr_segment_two_caption_buckets_no_duplication():
    caption = [
        Segment("c1", 0, 6, "First sentence here today."),
        Segment("c2", 6, 12, "Second sentence follows now."),
    ]
    asr = [
        Segment(
            "a1",
            0,
            12,
            "First sentence here today. Second sentence follows now.",
        )
    ]
    merged, result = cross_validate(caption, asr)
    assert result.ok
    words = word_sequence_from_segments(merged)
    assert words.count("first") == 1
    assert words.count("second") == 1
    assert len(merged) == 2
    fidelity = validate_transcript_fidelity(caption, merged)
    assert fidelity.ok


def test_multiple_captions_one_asr_segment_no_omission():
    caption = [
        Segment("c1", 0, 4, "Alpha beta gamma."),
        Segment("c2", 4, 8, "Delta epsilon zeta."),
        Segment("c3", 8, 12, "Eta theta iota."),
    ]
    asr = [Segment("a1", 0, 12, "Alpha beta gamma. Delta epsilon zeta. Eta theta iota.")]
    merged, result = cross_validate(caption, asr)
    assert result.ok
    assert word_sequence_from_segments(caption) == word_sequence_from_segments(merged)


def test_caption_word_order_preserved_to_04():
    caption = [
        Segment("c1", 0, 5, "One two three."),
        Segment("c2", 5, 10, "Four five six."),
    ]
    asr = [Segment("a1", 0, 10, "One two three. Four five six.")]
    verified, cv = cross_validate(caption, asr)
    assert cv.ok
    assert validate_transcript_fidelity(caption, verified).ok

    content_04, _manifest = assemble_04_en(verified)
    assert validate_04_en_fidelity(verified, content_04).ok


def test_consecutive_duplicate_sentence_fails_anomaly_check():
    segments = [
        Segment("c1", 0, 5, "This is a repeated sentence here."),
        Segment("c2", 5, 10, "This is a repeated sentence here."),
    ]
    result = validate_no_transcript_anomalies(segments)
    assert not result.ok
    assert "duplicate" in result.reason.lower()


def test_non_consecutive_repeat_allowed():
    segments = [
        Segment("c1", 0, 5, "Middle East and beyond."),
        Segment("c2", 5, 10, "Other content here today."),
        Segment("c3", 10, 15, "Middle East and beyond."),
    ]
    result = validate_no_transcript_anomalies(segments)
    assert result.ok


def test_duplicate_sentence_fails_anomaly_check():
    segments = [
        Segment("c1", 0, 5, "This is a repeated sentence here."),
        Segment("c2", 5, 10, "This is a repeated sentence here."),
    ]
    result = validate_no_transcript_anomalies(segments)
    assert not result.ok
    assert "duplicate" in result.reason.lower()


def test_cross_validate_pass():
    caption = [Segment("c1", 0, 5, "hello world today")]
    asr = [Segment("a1", 0, 5, "hello world today")]
    merged, result = cross_validate(caption, asr)
    assert result.ok
    assert merged[0].text_en == "hello world today"
