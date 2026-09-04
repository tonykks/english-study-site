from __future__ import annotations

import json
import logging
import subprocess

logger = logging.getLogger(__name__)


def fetch_youtube_chapters(video_id: str) -> list[dict[str, float | str]]:
    """Return YouTube chapters when explicitly present: [{title, start, end}, ...]."""
    url = f"https://youtu.be/{video_id}"
    try:
        proc = subprocess.run(
            ["yt-dlp", "--dump-json", "--skip-download", url],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("yt-dlp not found; skipping chapter fetch")
        return []
    except subprocess.TimeoutExpired:
        logger.warning("yt-dlp chapter fetch timed out for %s", video_id)
        return []

    if proc.returncode != 0 or not proc.stdout.strip():
        return []

    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []

    raw = info.get("chapters") or []
    if not raw:
        return []

    duration = float(info.get("duration") or 0.0)
    chapters: list[dict[str, float | str]] = []
    for i, ch in enumerate(raw):
        start = float(ch.get("start_time", 0.0))
        if i + 1 < len(raw):
            end = float(raw[i + 1].get("start_time", start))
        elif duration > start:
            end = duration
        else:
            end = start + 60.0
        title = str(ch.get("title") or f"Section {i + 1}").strip()
        chapters.append({"title": title, "start": start, "end": end})
    return chapters
