from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from automation.listening.utils import normalize_text

logger = logging.getLogger(__name__)

DEFAULT_VERTEX_MODEL = "gemini-3.1-flash-lite"

CHUNK_KR_INSTRUCTION = """Translate to Korean using Meaning-Chunk Literal Translation (의미 덩어리 직역).

Purpose: Korean learners must feel English word order through meaningful Korean chunks.

Rules:
- Split the English sentence mentally into meaningful grammatical chunks (subject, verb phrase, object, clause, etc.)
- Translate each chunk into understandable Korean that preserves the chunk's meaning
- Preserve the original English chunk order in Korean output
- Do NOT rearrange chunks into natural Korean sentence order
- Do NOT translate word-by-word (one English word per chunk)
- Do NOT summarize, paraphrase, omit, or add meaning
- Each English chunk must map clearly to one Korean chunk
- Chunk-internal Korean grammar should be understandable (e.g. "became a center" → "하나의 중심지가 되었다")
- You do not need to output "/" in the final kr text; join chunks with spaces

Examples:
English: The Middle East became a center of learning and exchange.
Chunks:
- The Middle East → 중동은
- became a center → 하나의 중심지가 되었다
- of learning and exchange → 학습과 교류의
Final kr: 중동은 하나의 중심지가 되었다 학습과 교류의.

English: People believed that many gods controlled nature and daily life.
Chunks:
- People believed → 사람들은 믿었다
- that many gods controlled → 많은 신들이 통제한다고
- nature and daily life → 자연과 일상생활을
Final kr: 사람들은 믿었다 많은 신들이 통제한다고 자연과 일상생활을."""

LITERAL_KR_INSTRUCTION = CHUNK_KR_INSTRUCTION


def vertex_configured() -> bool:
    return bool(os.getenv("GOOGLE_CLOUD_PROJECT"))


def vertex_model() -> str:
    return os.getenv("VERTEX_GEMINI_MODEL") or os.getenv("GEMINI_MODEL") or DEFAULT_VERTEX_MODEL


def vertex_location() -> str:
    return os.getenv("GOOGLE_CLOUD_LOCATION", "global")


def _client():
    if not vertex_configured():
        raise RuntimeError("BLOCKED: GOOGLE_CLOUD_PROJECT required for Vertex AI (ADC)")
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("BLOCKED: google-genai package required") from exc

    return genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=vertex_location(),
    )


def generate_text(prompt: str, *, timeout_sec: int = 120) -> str:
    _ = timeout_sec
    client = _client()
    response = client.models.generate_content(
        model=vertex_model(),
        contents=prompt,
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("BLOCKED: Vertex AI returned empty response")
    return text


def generate_json(prompt: str, *, timeout_sec: int = 180) -> Any:
    text = generate_text(prompt + "\n\nReturn valid JSON only.", timeout_sec=timeout_sec)
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if not match:
        raise RuntimeError("BLOCKED: Vertex AI returned non-JSON response")
    return json.loads(match.group(1))


def transcribe_audio_bytes(audio_bytes: bytes, mime_type: str = "audio/mp4") -> str:
    from google import genai
    from google.genai import types

    client = _client()
    prompt = (
        "Transcribe this English audio accurately. Return JSON array only: "
        '[{"start":0.0,"end":1.2,"text":"..."}] with timestamps in seconds.'
    )
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                types.Part.from_text(text=prompt),
            ],
        )
    ]
    response = client.models.generate_content(model=vertex_model(), contents=contents)
    return (response.text or "").strip()


def _chunk_en_words(chunks: list[dict[str, Any]]) -> list[str]:
    words: list[str] = []
    for chunk in chunks:
        words.extend(normalize_text(str(chunk.get("en", ""))).split())
    return words


def validate_chunk_translation(item_id: str, en_text: str, row: dict[str, Any]) -> str:
    """Validate meaning-chunk translation; return final kr string."""
    kr = str(row.get("kr", "")).strip()
    chunks = row.get("chunks")
    if not kr:
        raise RuntimeError(f"BLOCKED: empty KR for id {item_id}")

    en_words = normalize_text(en_text).split()
    if not en_words:
        return kr

    if not isinstance(chunks, list) or not chunks:
        if len(en_words) >= 6:
            raise RuntimeError(f"BLOCKED: missing chunk structure for id {item_id}")
        return kr

    if len(chunks) < 2 and len(en_words) >= 6:
        raise RuntimeError(f"BLOCKED: too few meaning chunks for id {item_id}")

    chunk_en_words = _chunk_en_words(chunks)
    if chunk_en_words != en_words:
        raise RuntimeError(f"BLOCKED: chunk EN words do not cover source for id {item_id}")

    if len(chunks) >= max(3, int(len(en_words) * 0.75)):
        raise RuntimeError(f"BLOCKED: word-by-word chunk translation detected for id {item_id}")

    joined_kr = " ".join(str(c.get("kr", "")).strip() for c in chunks if str(c.get("kr", "")).strip())
    if normalize_text(joined_kr) != normalize_text(kr):
        raise RuntimeError(f"BLOCKED: chunk KR join mismatch for id {item_id}")

    for chunk in chunks:
        en_part = normalize_text(str(chunk.get("en", ""))).split()
        kr_part = normalize_text(str(chunk.get("kr", ""))).split()
        if len(en_part) >= 6 and len(kr_part) <= 1:
            raise RuntimeError(f"BLOCKED: chunk KR too fragmented for id {item_id}")

    return kr


def validate_batch_kr_result(items: list[dict[str, str]], raw: Any) -> dict[str, str]:
    if not isinstance(raw, list):
        raise RuntimeError("BLOCKED: batch KR translation returned non-array JSON")
    if len(raw) != len(items):
        raise RuntimeError(
            f"BLOCKED: batch KR translation count mismatch (expected {len(items)}, got {len(raw)})"
        )
    expected_ids = [item["id"] for item in items]
    out: dict[str, str] = {}
    for idx, (expected, row) in enumerate(zip(expected_ids, raw)):
        if not isinstance(row, dict):
            raise RuntimeError(f"BLOCKED: batch KR item {idx} is not an object")
        row_id = str(row.get("id", "")).strip()
        if row_id != expected:
            raise RuntimeError(f"BLOCKED: batch KR id mismatch at index {idx} (expected {expected}, got {row_id})")
        en_text = items[idx]["text"]
        out[row_id] = validate_chunk_translation(row_id, en_text, row)
    return out


BATCH_KR_SUFFIX = """
You will receive a JSON array of objects with "id" and "text" fields.
Translate each English "text" using Meaning-Chunk Literal Translation.
Return JSON array only with the same ids in the same order:
[{"id": "...", "kr": "joined korean text", "chunks": [{"en": "...", "kr": "..."}, ...]}]
Rules:
- Output count must equal input count
- Each output id must match the corresponding input id
- "kr" must equal all chunk "kr" values joined in order (space-separated)
- Chunk EN words must cover the full source sentence in order with no omissions
- Use meaningful chunks, not word-by-word translation
- Do not merge, split, omit, or reorder input items
"""


def translate_literal_kr(en_text: str) -> str:
    payload = [{"id": "single", "text": en_text}]
    result = translate_literal_kr_batch([("single", en_text)])
    return result["single"]


def translate_literal_kr_batch(items: list[tuple[str, str]], *, timeout_sec: int = 180) -> dict[str, str]:
    """Translate multiple EN strings in one Vertex call. items: [(id, en_text), ...]"""
    if not items:
        return {}
    if len(items) == 1:
        item_id, text = items[0]
        prompt = (
            f"{CHUNK_KR_INSTRUCTION}\n\n"
            f'Translate this English sentence. Return JSON only:\n'
            f'{{"id": "{item_id}", "kr": "...", "chunks": [{{"en": "...", "kr": "..."}}]}}\n\n'
            f"English:\n{text}"
        )
        raw = generate_json(prompt, timeout_sec=timeout_sec)
        if isinstance(raw, list):
            row = raw[0]
        else:
            row = raw
        kr = validate_chunk_translation(item_id, text, row if isinstance(row, dict) else {})
        return {item_id: kr}

    payload = [{"id": item_id, "text": text} for item_id, text in items]
    prompt = (
        f"{CHUNK_KR_INSTRUCTION}\n{BATCH_KR_SUFFIX}\n\nInput JSON:\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    raw = generate_json(prompt, timeout_sec=timeout_sec)
    structured = [{"id": item_id, "text": text} for item_id, text in items]
    return validate_batch_kr_result(structured, raw)
