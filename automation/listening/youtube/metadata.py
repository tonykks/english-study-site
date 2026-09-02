from __future__ import annotations

import json
import urllib.request

from automation.listening.config import extract_video_id
from automation.listening.models import VideoMeta


def fetch_metadata(url_or_id: str) -> VideoMeta:
    video_id = extract_video_id(url_or_id)
    video_url = f"https://youtu.be/{video_id}"
    title = video_id
    channel = ""
    duration = 0.0

    try:
        oembed_url = f"https://www.youtube.com/oembed?url={video_url}&format=json"
        with urllib.request.urlopen(oembed_url, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            title = data.get("title") or title
            channel = data.get("author_name") or channel
    except Exception:
        pass

    return VideoMeta(
        video_id=video_id,
        title=title,
        channel=channel,
        duration=duration,
        video_url=video_url,
    )
