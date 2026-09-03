from __future__ import annotations

import json

from automation.listening.script.vertex_transcribe import parse_asr_response


def test_parse_asr_response_valid_array():
    raw = '[{"start":0.0,"end":1.2,"text":"Hello"},{"start":1.2,"end":2.0,"text":"world"}]'
    items = parse_asr_response(raw)
    assert len(items) == 2
    assert items[0]["text"] == "Hello"


def test_parse_asr_response_repairs_truncated_array():
    # Missing closing brace/bracket mid-stream — first objects still recoverable.
    blob = (
        '[{"start":0.0,"end":1.0,"text":"One"},'
        '{"start":1.0,"end":2.0,"text":"Two"},'
        '{"start":2.0,"end":3.0,"text":"Broken'
    )
    items = parse_asr_response(blob)
    assert len(items) >= 2
    assert items[0]["start"] == 0.0
    assert items[1]["text"] == "Two"


def test_parse_asr_response_rejects_empty():
    try:
        parse_asr_response("not json at all")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "invalid" in str(exc).lower() or "empty" in str(exc).lower()
