from __future__ import annotations

from automation.listening.script.golden_reference import (
    compare_legacy_en_sentences,
    extract_en_sentences_from_04,
)


def test_extract_en_sentences_from_04():
    content = "[Paragraph 1]\nEN: Hello world. Second sentence.\nKR: hi"
    sents = extract_en_sentences_from_04(content)
    assert len(sents) == 2
    assert sents[0].startswith("Hello")


def test_golden_compare_detects_run_on():
    legacy = ["The Persians ruled a huge area.", "They were known for fairness."]
    new = [
        "The Persians ruled a huge area They were known for fairness "
        + " ".join(f"word{i}" for i in range(160))
    ]
    result = compare_legacy_en_sentences(legacy, new)
    assert not result.ok
    assert result.run_on_count >= 1


def test_golden_compare_boundary_divergence():
    legacy = ["They were known for fairness.", "Merchants could travel safely."]
    new = ["They were known for fairness Merchants could travel safely."]
    result = compare_legacy_en_sentences(legacy, new)
    assert not result.ok
    assert len(result.boundary_divergences) >= 1


def test_golden_compare_matching_sentences():
    legacy = ["Alpha one.", "Beta two.", "Gamma three."]
    new = ["Alpha one.", "Beta two.", "Gamma three."]
    result = compare_legacy_en_sentences(legacy, new)
    assert result.ok
    assert result.matching_sentence_count == 3
