from __future__ import annotations

from automation.listening.generate.data_files import (
    assemble_04_en,
    inject_kr_into_04,
    verify_04_en_manifest,
)
from automation.listening.models import Segment
from automation.listening.script.canonical import segments_from_raw


def _sample_segments() -> list[Segment]:
    raw = [
        {"start": 0.0, "end": 3.0, "text": "First sentence here."},
        {"start": 3.0, "end": 6.0, "text": "Second sentence follows."},
        {"start": 6.0, "end": 9.0, "text": "Third sentence ends part one."},
        {"start": 9.0, "end": 12.0, "text": "Fourth sentence starts part two."},
        {"start": 12.0, "end": 15.0, "text": "Fifth sentence continues."},
        {"start": 15.0, "end": 18.0, "text": "Sixth sentence wraps up."},
    ]
    return segments_from_raw(raw)


def test_04_en_contains_all_segments():
    segments = _sample_segments()
    content_04, manifest = assemble_04_en(segments)
    assert verify_04_en_manifest(segments, content_04)
    assert len(manifest) == len(segments)
    assert "[Paragraph" in content_04
    assert "EN:" in content_04


def test_04_kr_injection_preserves_en():
    segments = _sample_segments()
    content_04_en, _ = assemble_04_en(segments)
    kr = ["첫 번째 문단", "두 번째 문단"]
    merged = inject_kr_into_04(content_04_en, kr)
    assert verify_04_en_manifest(segments, merged)
    assert "KR: 첫 번째 문단" in merged
