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
