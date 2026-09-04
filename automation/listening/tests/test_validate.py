from __future__ import annotations

from automation.listening.models import Segment
from automation.listening.script.validate import validate_segments


def test_coverage_pass():
    segs = [
        Segment("s1", 0, 10, "hello world"),
        Segment("s2", 10, 20, "second line"),
    ]
    result = validate_segments(segs, 20.0)
    assert result.ok


def test_gap_blocked():
    segs = [
        Segment("s1", 0, 280, "first long segment with enough coverage"),
        Segment("s2", 295, 300, "segment after fifteen second gap"),
    ]
    result = validate_segments(segs, 300.0)
    assert not result.ok
    assert "Gap" in result.reason


def test_duplicate_blocked():
    text = "repeat this block exactly"
    segs = [
        Segment("s1", 0, 5, text),
        Segment("s2", 5, 10, text),
        Segment("s3", 10, 15, text),
    ]
    result = validate_segments(segs, 15.0)
    assert not result.ok
    assert "duplicate" in result.reason.lower()


def test_order_violation():
    segs = [
        Segment("s1", 10, 15, "late start"),
        Segment("s2", 5, 8, "earlier timestamp"),
    ]
    result = validate_segments(segs, 20.0)
    assert not result.ok
