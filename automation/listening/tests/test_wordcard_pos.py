from __future__ import annotations

from automation.listening.vertex_client import meaning_matches_pos


def test_verb_meaning_must_be_korean_verb():
    assert meaning_matches_pos("거래하다", "verb")
    assert meaning_matches_pos("영향을 주다", "verb")
    assert meaning_matches_pos("무역하다", "verb")
    assert not meaning_matches_pos("무역", "verb")
    assert not meaning_matches_pos("영향", "verb")


def test_noun_meaning_allows_noun_gloss():
    assert meaning_matches_pos("무역", "noun")
    assert meaning_matches_pos("영향", "noun")


def test_law_code_sense_rejects_cipher():
    from automation.listening.vertex_client import meaning_conflicts_with_context

    assert meaning_conflicts_with_context(
        "code",
        "암호",
        "a written list of laws or rules",
        "King Hammurabi created one of the first written law codes in history.",
    )
    assert meaning_conflicts_with_context(
        "code",
        "법전",
        "a written list of laws or rules",
        "King Hammurabi created one of the first written law codes in history.",
    ) is None


def test_kr_sentence_alignment_detects_mismatch():
    from automation.listening.generate.data_files import validate_04_kr_sentence_alignment

    content = (
        "[Paragraph 1]\n"
        "EN: First sentence. Second sentence.\n"
        "KR: 첫번째만있습니다\n"
    )
    ok, _reason = validate_04_kr_sentence_alignment(content)
    assert not ok


def test_kr_sentence_alignment_ok_when_counts_match():
    from automation.listening.generate.data_files import validate_04_kr_sentence_alignment

    content = (
        "[Paragraph 1]\n"
        "EN: First sentence. Second sentence.\n"
        "KR: 첫번째다. 두번째다.\n"
    )
    ok, reason = validate_04_kr_sentence_alignment(content)
    assert ok, reason
