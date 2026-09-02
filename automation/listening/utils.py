from __future__ import annotations

import hashlib
import re


def normalize_text(text: str) -> str:
    lowered = (text or "").lower()
    lowered = re.sub(r"[^\w\s']", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def word_divergence(a: str, b: str) -> float:
    wa = normalize_text(a).split()
    wb = normalize_text(b).split()
    if not wa and not wb:
        return 0.0
    if not wa or not wb:
        return 1.0
    from difflib import SequenceMatcher

    return 1.0 - SequenceMatcher(None, wa, wb).ratio()


def segment_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:16]


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def capitalize_first(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text
    return text[0].upper() + text[1:]


def cleanup_caption_text(text: str) -> str:
    """Punctuation/capitalization only — no word add/remove."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return text
    text = capitalize_first(text)
    if text[-1] not in ".!?":
        text += "."
    return text
