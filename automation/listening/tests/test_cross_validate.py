from __future__ import annotations

from automation.listening.models import Segment
from automation.listening.script.validate import cross_validate


def test_cross_validate_pass():
    caption = [Segment("c1", 0, 5, "hello world today")]
    asr = [Segment("a1", 0, 5, "hello world today")]
    merged, result = cross_validate(caption, asr)
    assert result.ok
    assert merged[0].text_en == "hello world today"


def test_cross_validate_prefers_asr_on_divergence():
    caption = []
    asr = []
    for i in range(20):
        cap_text = "caption text segment here"
        asr_text = "completely different words only" if i == 0 else cap_text
        caption.append(Segment(f"c{i}", i * 5, i * 5 + 5, cap_text))
        asr.append(Segment(f"a{i}", i * 5, i * 5 + 5, asr_text))
    merged, result = cross_validate(caption, asr)
    assert result.ok
    assert merged[0].text_en == "completely different words only"
