from __future__ import annotations

from automation.listening.generate.data_files import build_04_en_manifest, verify_04_en_manifest
from automation.listening.models import Segment


def test_manifest_hash_verification():
    segments = [
        Segment("s1", 0, 3, "Alpha sentence."),
        Segment("s2", 3, 6, "Beta sentence."),
    ]
    manifest = build_04_en_manifest(segments)
    good = (
        "[Paragraph 1]\n"
        "EN: Alpha sentence. Beta sentence.\n"
        "KR: test\n"
    )
    assert verify_04_en_manifest(segments, good, manifest)

    bad = (
        "[Paragraph 1]\n"
        "EN: Alpha sentence.\n"
        "KR: test\n"
    )
    assert not verify_04_en_manifest(segments, bad, manifest)
