from __future__ import annotations

from automation.listening.generate.sections import (
    _best_complete_core_sentence,
    _exact_sentence_candidates,
    _sentence_exact_in_script,
    _whitespace_key,
)
from automation.listening.models import StorySection


def test_exact_core_rejects_punctuation_drift():
    verified = (
        "Each door that closed made him look for another one to knock on. "
        "He understood something very important: that failure is not the end, "
        "it's just part of the journey."
    )
    drifted = (
        "He understood something very important that failure is not the end, "
        "It's just part of the journey."
    )
    assert _sentence_exact_in_script(drifted, verified) is None
    assert _sentence_exact_in_script(
        "He understood something very important: that failure is not the end, "
        "it's just part of the journey.",
        verified,
    )


def test_exact_candidates_whitespace_only():
    section = (
        "Success isn't about age. It's not about luck. "
        "It's about never giving up."
    )
    verified = section
    cands = _exact_sentence_candidates(section, verified)
    assert any(_whitespace_key(c) == _whitespace_key("Success isn't about age.") for c in cands)


def test_exact_candidate_is_copied_from_verified_script():
    verified = "Maya built a thriving restaurant in Detroit."
    section = "Maya  built a thriving restaurant in Detroit."
    assert _exact_sentence_candidates(section, verified) == [verified]


def test_fallback_prefers_section_specific_event_over_generic_line():
    verified = (
        "The problem wasn't the food. "
        "After years of rejection, Maya built a thriving restaurant in Detroit."
    )
    section = StorySection(
        index=1,
        title="Maya Builds Her Restaurant",
        text_en=verified,
        start=0.0,
        end=20.0,
    )
    assert _best_complete_core_sentence(section, verified) == (
        "After years of rejection, Maya built a thriving restaurant in Detroit."
    )
