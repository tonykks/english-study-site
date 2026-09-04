from __future__ import annotations

from automation.listening.generate.data_files import _lemma_level1_headword, _translate_batch
from automation.listening.vertex_client import validate_batch_kr_result


def test_lemma_level1_farming_to_farm():
    assert _lemma_level1_headword("farming", "noun") == "farm"


def test_lemma_level1_writing_to_write():
    assert _lemma_level1_headword("writing", "verb") == "write"


def test_lemma_level1_non_ing_unchanged():
    assert _lemma_level1_headword("conflict", "noun") == "conflict"


def test_batch_kr_validator_count_mismatch():
    items = [{"id": "a", "text": "hello"}, {"id": "b", "text": "world"}]
    try:
        validate_batch_kr_result(items, [{"id": "a", "kr": "안녕"}])
        assert False, "expected mismatch error"
    except RuntimeError as exc:
        assert "count mismatch" in str(exc).lower()


def test_batch_kr_validator_id_mismatch():
    items = [{"id": "a", "text": "hello"}]
    try:
        validate_batch_kr_result(items, [{"id": "b", "kr": "안녕"}])
        assert False, "expected id mismatch error"
    except RuntimeError as exc:
        assert "id mismatch" in str(exc).lower()


def test_translate_batch_placeholder():
    result = _translate_batch([("x1", "Hello world.")], allow_placeholder=True)
    assert result["x1"].startswith("[KR translation pending:")
