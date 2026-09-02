from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_VERTEX_MODEL = "gemini-2.0-flash-001"

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
    return os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")


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
