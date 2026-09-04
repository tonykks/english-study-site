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
    assert result.real_error_count >= 1
    assert result.missed_boundary_count >= 1


def test_owner_style_verb_split_is_valid():
    from automation.listening.vertex_client import validate_chunk_translation

    en = "The Middle East became a center of learning and exchange."
    row = {
        "id": "owner1",
        "kr": "중동은 되었다 하나의 중심지가 학습과 교류의",
        "chunks": [
            {"en": "The Middle East", "kr": "중동은"},
            {"en": "became", "kr": "되었다"},
            {"en": "a center", "kr": "하나의 중심지가"},
            {"en": "of learning and exchange", "kr": "학습과 교류의"},
        ],
    }
    kr = validate_chunk_translation("owner1", en, row)
    assert "되었다" in kr
    assert "하나의 중심지가" in kr


def test_golden_compare_matching_sentences():
    legacy = ["Alpha one.", "Beta two.", "Gamma three."]
    new = ["Alpha one.", "Beta two.", "Gamma three."]
    result = compare_legacy_en_sentences(legacy, new)
    assert result.ok
    assert result.matching_sentence_count == 3
