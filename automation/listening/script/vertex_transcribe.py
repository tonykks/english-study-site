from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from automation.listening.config import CHUNK_SECONDS, OVERLAP_SECONDS
from automation.listening.models import Segment
from automation.listening.script.canonical import segments_from_raw
from automation.listening.utils import cleanup_caption_text
from automation.listening.vertex_client import transcribe_audio_bytes, vertex_configured

logger = logging.getLogger(__name__)


def transcribe_with_vertex(video_id: str, duration: float) -> list[Segment]:
    """Vertex AI ASR via google-genai + ADC."""
    if not vertex_configured():
        raise RuntimeError("BLOCKED: GOOGLE_CLOUD_PROJECT required for Vertex AI ASR (ADC)")

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
    import subprocess
    import tempfile

    chunks: list[tuple[str, float]] = []
    start = 0.0
    idx = 0
    while start < duration:
        end = min(duration, start + CHUNK_SECONDS)
        chunk_len = end - start
        out = tempfile.NamedTemporaryFile(suffix=f"_chunk{idx}.m4a", delete=False)
        out.close()
        cmd = [
            "ffmpeg", "-y", "-ss", str(start), "-t", str(chunk_len),
            "-i", audio_path, "-c", "copy", out.name,
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
            segs = _transcribe_audio_vertex(audio_path)
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
    import subprocess
    import tempfile

    tmp_dir = tempfile.mkdtemp()
    out_path = str(Path(tmp_dir) / f"{video_id}.m4a")
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = [
        "yt-dlp", "-f", "bestaudio[ext=m4a]/bestaudio", "-o", out_path,
        "--no-playlist", "--no-continue", "--force-overwrites", url,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except FileNotFoundError as exc:
        raise RuntimeError("BLOCKED: yt-dlp required for audio download") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"BLOCKED: audio download failed: {exc.stderr.decode(errors='ignore')[:200]}") from exc
    return out_path


def parse_asr_response(text: str) -> list[dict]:
    """Parse Vertex ASR JSON; repair truncated/malformed arrays when possible."""
    blob = (text or "").strip()
    if not blob:
        raise RuntimeError("BLOCKED: ASR returned empty response")
    match = re.search(r"\[.*\]", blob, re.DOTALL)
    candidate = match.group(0) if match else blob
    try:
        raw = json.loads(candidate)
        if isinstance(raw, list):
            return raw
    except json.JSONDecodeError:
        pass

    # Fallback: extract individual segment objects even if the array is truncated.
    objects: list[dict] = []
    for m in re.finditer(
        r'\{\s*"start"\s*:\s*([0-9.]+)\s*,\s*"end"\s*:\s*([0-9.]+)\s*,\s*"text"\s*:\s*"((?:\\.|[^"\\])*)"\s*\}',
        candidate,
    ):
        objects.append(
            {
                "start": float(m.group(1)),
                "end": float(m.group(2)),
                "text": _unescape_json_string(m.group(3)),
            }
        )
    if not objects:
        # Looser fallback for broken wrappers around valid fields.
        for m in re.finditer(
            r'"start"\s*:\s*([0-9.]+).*?"end"\s*:\s*([0-9.]+).*?"text"\s*:\s*"((?:\\.|[^"\\])*)"',
            candidate,
            re.DOTALL,
        ):
            objects.append(
                {
                    "start": float(m.group(1)),
                    "end": float(m.group(2)),
                    "text": _unescape_json_string(m.group(3)),
                }
            )
    if not objects:
        raise RuntimeError("BLOCKED: ASR returned invalid format")
    return objects


def _unescape_json_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except Exception:
        return (
            value.replace(r"\"", '"')
            .replace(r"\n", "\n")
            .replace(r"\\", "\\")
        )


def _transcribe_audio_vertex(audio_path: str) -> list[Segment]:
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    text = transcribe_audio_bytes(audio_bytes, mime_type="audio/mp4")
    raw = parse_asr_response(text)
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        start = float(item.get("start", 0.0))
        cleaned.append(
            {
                "start": start,
                "end": float(item.get("end", start + 1.0)),
                "text": cleanup_caption_text(str(item.get("text", ""))),
            }
        )
    if not cleaned:
        raise RuntimeError("BLOCKED: ASR returned no usable segments")
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
