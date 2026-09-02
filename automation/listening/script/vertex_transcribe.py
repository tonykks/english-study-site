from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from automation.listening.config import CHUNK_SECONDS, OVERLAP_SECONDS, gemini_configured
from automation.listening.models import Segment
from automation.listening.script.canonical import segments_from_raw
from automation.listening.utils import cleanup_caption_text

logger = logging.getLogger(__name__)


def transcribe_with_vertex(video_id: str, duration: float) -> list[Segment]:
    """Vertex/Gemini ASR with retry and long-video chunking."""
    if not gemini_configured():
        raise RuntimeError(
            "BLOCKED: GOOGLE_API_KEY required for ASR cross-validation"
        )

    audio_path = _download_audio(video_id)
    try:
        if duration > CHUNK_SECONDS:
            return _transcribe_long_audio(audio_path, duration)
        return _transcribe_chunk_with_retry(audio_path, offset=0.0)
    finally:
        try:
            Path(audio_path).unlink(missing_ok=True)
        except OSError:
            pass


def _transcribe_long_audio(audio_path: str, duration: float) -> list[Segment]:
    chunks = _split_audio_chunks(audio_path, duration)
    merged: list[Segment] = []
    try:
        for chunk_path, offset in chunks:
            part = _transcribe_chunk_with_retry(chunk_path, offset=offset)
            merged.extend(part)
        from automation.listening.script.canonical import merge_overlapping_segments

        return merge_overlapping_segments([merged])
    finally:
        for chunk_path, _ in chunks:
            try:
                Path(chunk_path).unlink(missing_ok=True)
            except OSError:
                pass


def _split_audio_chunks(audio_path: str, duration: float) -> list[tuple[str, float]]:
    """Split audio into 15min chunks with 30s overlap using ffmpeg."""
    chunks: list[tuple[str, float]] = []
    start = 0.0
    idx = 0
    while start < duration:
        end = min(duration, start + CHUNK_SECONDS)
        chunk_len = end - start
        out = tempfile.NamedTemporaryFile(suffix=f"_chunk{idx}.m4a", delete=False)
        out.close()
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-t",
            str(chunk_len),
            "-i",
            audio_path,
            "-c",
            "copy",
            out.name,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise RuntimeError("BLOCKED: ffmpeg required for long-video ASR chunking") from exc
        chunks.append((out.name, start))
        if end >= duration:
            break
        start = end - OVERLAP_SECONDS
        idx += 1
    return chunks


def _transcribe_chunk_with_retry(audio_path: str, offset: float = 0.0) -> list[Segment]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            segs = _transcribe_audio_gemini(audio_path)
            if offset:
                for seg in segs:
                    seg.start += offset
                    seg.end += offset
            return segs
        except Exception as exc:
            last_error = exc
            logger.warning("ASR attempt %s failed: %s", attempt + 1, exc)
    raise RuntimeError(f"BLOCKED: ASR failed after retries: {last_error}")


def _download_audio(video_id: str) -> str:
    tmp_dir = tempfile.mkdtemp()
    out_path = str(Path(tmp_dir) / f"{video_id}.m4a")
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = [
        "yt-dlp",
        "-f",
        "bestaudio[ext=m4a]/bestaudio",
        "-o",
        out_path,
        "--no-playlist",
        "--no-continue",
        "--force-overwrites",
        url,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except FileNotFoundError as exc:
        raise RuntimeError("BLOCKED: yt-dlp required for audio download") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"BLOCKED: audio download failed: {exc.stderr.decode(errors='ignore')[:200]}") from exc
    return out_path


def _transcribe_audio_gemini(audio_path: str) -> list[Segment]:
    import os

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("BLOCKED: GOOGLE_API_KEY not set")

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise RuntimeError("BLOCKED: google-generativeai package required") from exc

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    model = genai.GenerativeModel(model_name)

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    prompt = (
        "Transcribe this English audio accurately. Return JSON array only: "
        '[{"start":0.0,"end":1.2,"text":"..."}] with timestamps in seconds.'
    )

    response = model.generate_content(
        [{"mime_type": "audio/mp4", "data": audio_bytes}, prompt],
        request_options={"timeout": 120},
    )
    text = (response.text or "").strip()
    import json
    import re

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise RuntimeError("BLOCKED: ASR returned invalid format")
    raw = json.loads(match.group(0))
    cleaned = []
    for item in raw:
        cleaned.append(
            {
                "start": float(item["start"]),
                "end": float(item.get("end", float(item["start"]) + 1.0)),
                "text": cleanup_caption_text(str(item.get("text", ""))),
            }
        )
    return segments_from_raw(cleaned, source="asr")


def chunk_segments(segments: list[Segment], duration: float) -> list[list[Segment]]:
    if duration <= CHUNK_SECONDS:
        return [segments]
    chunks: list[list[Segment]] = []
    start = 0.0
    while start < duration:
        end = min(duration, start + CHUNK_SECONDS)
        chunk = [s for s in segments if s.start >= start - 0.5 and s.end <= end + 0.5]
        if chunk:
            chunks.append(chunk)
        if end >= duration:
            break
        start = end - 30
    return chunks or [segments]
