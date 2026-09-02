from __future__ import annotations

import pytest

from automation.listening.vertex_client import validate_chunk_translation


def test_chunk_translation_valid():
    en = "The Middle East became a center of learning and exchange."
    row = {
        "id": "s1",
        "kr": "중동은 하나의 중심지가 되었다 학습과 교류의.",
        "chunks": [
            {"en": "The Middle East", "kr": "중동은"},
            {"en": "became a center", "kr": "하나의 중심지가 되었다"},
            {"en": "of learning and exchange", "kr": "학습과 교류의"},
        ],
    }
    kr = validate_chunk_translation("s1", en, row)
    assert "중동은" in kr


def test_chunk_translation_word_by_word_rejected():
    en = "People believed that many gods controlled nature and daily life."
    row = {
        "id": "s2",
        "kr": "사람들은 믿었다 많은 신들이 통제한다고 자연과 일상생활을.",
        "chunks": [{"en": w, "kr": w} for w in en.replace(".", "").split()],
    }
    with pytest.raises(RuntimeError, match="word-by-word"):
        validate_chunk_translation("s2", en, row)


def test_chunk_translation_missing_words_rejected():
    en = "People believed that many gods controlled nature."
    row = {
        "id": "s3",
        "kr": "사람들은 믿었다.",
        "chunks": [
            {"en": "People believed", "kr": "사람들은 믿었다"},
        ],
    }
    with pytest.raises(RuntimeError, match="too few|do not cover"):
        validate_chunk_translation("s3", en, row)


def test_chunk_regression_became_a_center():
    en = "The Middle East became a center of learning and exchange."
    row = {
        "id": "r1",
        "kr": "중동은 하나의 중심지가 되었다 학습과 교류의.",
        "chunks": [
            {"en": "The Middle East", "kr": "중동은"},
            {"en": "became a center", "kr": "하나의 중심지가 되었다"},
            {"en": "of learning and exchange", "kr": "학습과 교류의"},
        ],
    }
    kr = validate_chunk_translation("r1", en, row)
    assert "중동은" in kr


def test_owner_verb_complement_split_allowed():
    en = "King Hammurabi created one of the first written law codes in history."
    row = {
        "id": "r3",
        "kr": "함무라비 왕은 만들었다 최초의 성문법전들 중 하나를 역사상",
        "chunks": [
            {"en": "King Hammurabi", "kr": "함무라비 왕은"},
            {"en": "created", "kr": "만들었다"},
            {"en": "one of the first written law codes", "kr": "최초의 성문법전들 중 하나를"},
            {"en": "in history", "kr": "역사상"},
        ],
    }
    kr = validate_chunk_translation("r3", en, row)
    assert "만들었다" in kr


def test_chunk_rejects_single_word_fragments():
    en = "Because of the rivers, people could stay in one place instead of moving all the time."
    row = {
        "id": "r2",
        "kr": "강들 덕분에 사람들은 머물 수 있었다 한 장소에.",
        "chunks": [{"en": w.strip(",."), "kr": w} for w in en.replace(".", "").split()],
    }
    with pytest.raises(RuntimeError):
        validate_chunk_translation("r2", en, row)
