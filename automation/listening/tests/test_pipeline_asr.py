from __future__ import annotations

from unittest.mock import patch

from automation.listening.models import VideoMeta
from automation.listening.pipeline import run_pipeline


def test_asr_only_blocked_without_captions():
    meta = VideoMeta(
        video_id="testvid1234",
        title="Test Video",
        channel="Ch",
        duration=120.0,
        video_url="https://youtu.be/testvid1234",
    )

    with patch("automation.listening.pipeline.fetch_metadata", return_value=meta), patch(
        "automation.listening.pipeline.check_duplicate", return_value=None
    ), patch(
        "automation.listening.pipeline.fetch_caption_segments",
        side_effect=RuntimeError("no captions"),
    ), patch("automation.listening.pipeline.fetch_youtube_duration", return_value=120.0):
        result = run_pipeline("https://youtu.be/testvid1234", 2)

    assert result.status == "BLOCKED"
    assert "ASR-only" in result.message or "captions" in result.message.lower()
