from __future__ import annotations

import json
import logging
import subprocess

logger = logging.getLogger(__name__)


def fetch_youtube_duration(video_id: str) -> float:
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = ["yt-dlp", "-j", "--no-playlist", url]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        data = json.loads(result.stdout)
        return float(data.get("duration") or 0.0)
    except Exception as exc:
        logger.warning("Could not fetch duration for %s: %s", video_id, exc)
        return 0.0
