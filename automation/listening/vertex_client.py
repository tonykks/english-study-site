from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_VERTEX_MODEL = "gemini-3.1-flash-lite"

LITERAL_KR_INSTRUCTION = """Translate to Korean using literal translation (직역).
Rules:
- Preserve English word order and sentence structure as much as Korean allows
- Do NOT summarize, paraphrase, restructure, or omit content
- Do NOT add meaning that is not in the English source
- Learners must map each English phrase to Korean one-to-one
- Output Korean text only, no labels or explanation"""


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


def translate_literal_kr(en_text: str) -> str:
    prompt = f"{LITERAL_KR_INSTRUCTION}\n\nEnglish:\n{en_text}"
    return generate_text(prompt)


BATCH_KR_SUFFIX = """
You will receive a JSON array of objects with "id" and "text" fields.
Translate each "text" to Korean using the literal translation rules above.
Return JSON array only with the same ids in the same order:
[{"id": "...", "kr": "..."}]
Rules:
- Output count must equal input count
- Each output id must match the corresponding input id
- Do not merge, split, omit, or reorder items
"""


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
        kr = str(row.get("kr", "")).strip()
        if not kr:
            raise RuntimeError(f"BLOCKED: batch KR empty for id {row_id}")
        out[row_id] = kr
    return out


def translate_literal_kr_batch(items: list[tuple[str, str]], *, timeout_sec: int = 180) -> dict[str, str]:
    """Translate multiple EN strings in one Vertex call. items: [(id, en_text), ...]"""
    if not items:
        return {}
    if len(items) == 1:
        item_id, text = items[0]
        return {item_id: translate_literal_kr(text)}

    payload = [{"id": item_id, "text": text} for item_id, text in items]
    prompt = (
        f"{LITERAL_KR_INSTRUCTION}\n{BATCH_KR_SUFFIX}\n\nInput JSON:\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    raw = generate_json(prompt, timeout_sec=timeout_sec)
    structured = [{"id": item_id, "text": text} for item_id, text in items]
    return validate_batch_kr_result(structured, raw)
