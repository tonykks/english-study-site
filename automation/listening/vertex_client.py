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

Purpose: Korean learners first catch the English subject + verb, then attach the remaining information in the same order English presents it (what / where / why / how).

Rules:
- Split the English sentence into meaning chunks, not isolated words
- Put the subject + verb first, then follow English information order
- Remaining chunks follow English order: object, complement, place, reason, manner
- Keep Korean particles and endings intact enough for every chunk to retain its meaning
- Translate each chunk into understandable Korean without collapsing its grammar
- Preserve the original English chunk order in Korean output
- Do NOT rearrange chunks into natural Korean sentence order
- Do NOT make a 1:1 mechanical single-word translation
- Do NOT duplicate, summarize, paraphrase, omit, or add meaning
- Verb and complement MAY be separate chunks. That is intended.
  Example allowed: "became" → "되었다", "a center" → "하나의 중심지가"
- Do NOT force verb+complement into one chunk
- You do not need to output "/" in the final kr text; join chunks with spaces

Examples:
English: The Middle East became a center of learning and exchange.
Chunks:
- The Middle East → 중동은
- became → 되었다
- a center → 하나의 중심지가
- of learning and exchange → 학습과 교류의
Final kr: 중동은 되었다 하나의 중심지가 학습과 교류의

English: King Hammurabi created one of the first written law codes in history.
Chunks:
- King Hammurabi → 함무라비 왕은
- created → 만들었다
- one of the first written law codes → 최초의 성문법전들 중 하나를
- in history → 역사상
Final kr: 함무라비 왕은 만들었다 최초의 성문법전들 중 하나를 역사상

English: Writing helped humans build more organized societies.
Chunks:
- Writing → 글쓰기는
- helped → 도왔다
- humans build → 인간들이 건설하도록
- more organized societies → 더 조직적인 사회를
Final kr: 글쓰기는 도왔다 인간들이 건설하도록 더 조직적인 사회를

English: Because of the rivers, people could stay in one place instead of moving all the time.
Chunks:
- Because of the rivers → 강들 덕분에
- people could stay → 사람들은 머무를 수 있었다
- in one place → 한 장소에
- instead of moving all the time → 계속 이동하는 대신에
Final kr: 강들 덕분에 사람들은 머무를 수 있었다 한 장소에 계속 이동하는 대신에

English: People believed that many gods controlled nature and daily life.
Chunks:
- People believed → 사람들은 믿었다
- that many gods controlled → 많은 신들이 통제한다고
- nature and daily life → 자연과 일상생활을
Final kr: 사람들은 믿었다 많은 신들이 통제한다고 자연과 일상생활을

English: You can fail many times and still win in the end, if you keep going.
Chunks:
- You can fail → 당신은 실패할 수 있다
- many times → 여러 번
- and still win → 그리고도 이길 수 있다
- in the end → 결국에는
- if you keep going → 당신이 계속 나아간다면
Final kr: 당신은 실패할 수 있다 여러 번 그리고도 이길 수 있다 결국에는 당신이 계속 나아간다면

English: They planted the seeds of the man who would one day become Colonel Sanders, the founder of KFC.
Chunks:
- They planted → 그들은 심었다
- the seeds → 씨앗을
- of the man who would one day become Colonel Sanders → 훗날 커널 샌더스가 될 그 사람의
- the founder of KFC → KFC의 창립자가
Final kr: 그들은 심었다 씨앗을 훗날 커널 샌더스가 될 그 사람의 KFC의 창립자가"""

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


def _subsequence_coverage(source: list[str], parts: list[str]) -> float:
    if not source:
        return 1.0
    si = 0
    matched = 0
    for part in parts:
        while si < len(source) and source[si] != part:
            si += 1
        if si < len(source) and source[si] == part:
            matched += 1
            si += 1
    return matched / len(source)


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
        coverage = _subsequence_coverage(en_words, chunk_en_words)
        if coverage < 0.95:
            raise RuntimeError(f"BLOCKED: chunk EN words do not cover source for id {item_id}")

    if len(chunks) >= max(3, int(len(en_words) * 0.75)):
        raise RuntimeError(f"BLOCKED: word-by-word chunk translation detected for id {item_id}")

    tiny_chunks = 0
    for chunk in chunks:
        en_part = normalize_text(str(chunk.get("en", ""))).split()
        kr_part = str(chunk.get("kr", "")).strip()
        if len(en_part) >= 3 and len(kr_part.split()) <= 1:
            tiny_chunks += 1
    if len(en_words) >= 8 and tiny_chunks >= max(2, len(chunks) // 2):
        raise RuntimeError(f"BLOCKED: fragmented one-word chunks for id {item_id}")

    if len(en_words) >= 8:
        avg_en_words = len(chunk_en_words) / len(chunks)
        if avg_en_words < 1.5:
            raise RuntimeError(f"BLOCKED: chunks too small (avg {avg_en_words:.1f} EN words) for id {item_id}")

    joined_kr = " ".join(str(c.get("kr", "")).strip() for c in chunks if str(c.get("kr", "")).strip())
    if not joined_kr:
        return kr

    return joined_kr


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
- Use meaningful chunks following subject+verb first, then remaining English-order information
- Keep Korean particles/endings intact so each meaning chunk remains understandable
- Do not duplicate meaning or use mechanical one-English-word/one-Korean-word chunks
- Do not rearrange chunks into natural full-sentence Korean order
- Verb and complement MAY be separate chunks
- Do not merge, split, omit, or reorder input items
"""


def translate_literal_kr(en_text: str) -> str:
    payload = [{"id": "single", "text": en_text}]
    result = translate_literal_kr_batch([("single", en_text)])
    return result["single"]


def _translate_literal_kr_batch_once(items: list[tuple[str, str]], *, timeout_sec: int = 180) -> dict[str, str]:
    payload = [{"id": item_id, "text": text} for item_id, text in items]
    prompt = (
        f"{CHUNK_KR_INSTRUCTION}\n{BATCH_KR_SUFFIX}\n\nInput JSON:\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    raw = generate_json(prompt, timeout_sec=timeout_sec)
    structured = [{"id": item_id, "text": text} for item_id, text in items]
    return validate_batch_kr_result(structured, raw)


def translate_literal_kr_batch(items: list[tuple[str, str]], *, timeout_sec: int = 180) -> dict[str, str]:
    """Translate multiple EN strings in one Vertex call. items: [(id, en_text), ...]"""
    if not items:
        return {}

    def _translate_single(item_id: str, text: str) -> str:
        prompt = (
            f"{CHUNK_KR_INSTRUCTION}\n\n"
            f'Translate this English sentence. Return JSON only:\n'
            f'{{"id": "{item_id}", "kr": "...", "chunks": [{{"en": "...", "kr": "..."}}]}}\n\n'
            f"English:\n{text}"
        )
        raw = generate_json(prompt, timeout_sec=timeout_sec)
        row = raw[0] if isinstance(raw, list) else raw
        try:
            return validate_chunk_translation(item_id, text, row if isinstance(row, dict) else {})
        except RuntimeError:
            if isinstance(row, dict):
                kr = str(row.get("kr", "")).strip()
                chunks = row.get("chunks")
                if kr and isinstance(chunks, list) and len(chunks) >= 2:
                    return kr
            raise

    if len(items) == 1:
        item_id, text = items[0]
        return {item_id: _translate_single(item_id, text)}

    batch_size = 8
    out: dict[str, str] = {}
    for start in range(0, len(items), batch_size):
        chunk = items[start : start + batch_size]
        try:
            out.update(_translate_literal_kr_batch_once(chunk, timeout_sec=timeout_sec))
        except RuntimeError:
            for item_id, text in chunk:
                out[item_id] = _translate_single(item_id, text)
    return out


WORDCARD_POS_INSTRUCTION = """Translate the English headword into ONE Korean dictionary gloss for THIS card's sense.
Use headword + part_of_speech + definition_en + example_en together.
The gloss MUST match the given part of speech AND the meaning used in the definition/example.
- verb → Korean verb, typically ending in 다 (trade/verb → 거래하다; influence/verb → 영향을 주다)
- noun → Korean noun matching this card's sense
  * law/rules list → 법전 (NOT 암호)
  * secret message → 암호
  * computer program → 코드
- adjective → Korean adjective
- adverb → Korean adverb
Do not give a noun gloss for a verb, or a verb gloss for a noun.
Do not pick an unrelated dictionary sense.
Return JSON array only: [{"id":"...","kr":"..."}]
"""

_VERB_KR_RE = re.compile(r"(다|하다|되다|주다|받다|가다|오다|보다|이다)$")


def meaning_matches_pos(meaning_kr: str, pos: str) -> bool:
    kr = re.sub(r"\s+", "", (meaning_kr or "").strip())
    p = (pos or "").lower()
    if not kr:
        return False
    if p.startswith("verb"):
        return bool(_VERB_KR_RE.search(kr)) or "하다" in kr or "주다" in kr
    return True


def meaning_conflicts_with_context(
    headword: str,
    meaning_kr: str,
    definition_en: str,
    example_en: str,
) -> str | None:
    """Return a reason if meaning_kr contradicts the card's definition/example sense."""
    hw = (headword or "").strip().lower()
    kr = (meaning_kr or "").strip()
    blob = f"{definition_en} {example_en}".lower()
    if hw == "code" and any(token in blob for token in ("law", "laws", "legal", "hammurabi", "rule")):
        if any(bad in kr for bad in ("암호", "코드", "암호문")):
            return "law-code sense expected (법전/법규), not 암호/코드"
        if "법" not in kr:
            return "law-code sense expected (법전/법규)"
    return None


def translate_wordcard_meanings(items: list[dict[str, str]], *, timeout_sec: int = 120) -> dict[str, str]:
    """items: dicts with id, headword, part_of_speech, definition_en, example_en."""
    if not items:
        return {}
    payload = [
        {
            "id": str(item.get("id", "")).strip(),
            "headword": str(item.get("headword", "")).strip(),
            "part_of_speech": str(item.get("part_of_speech", "")).strip(),
            "definition_en": str(item.get("definition_en", "")).strip(),
            "example_en": str(item.get("example_en", "")).strip(),
        }
        for item in items
    ]
    prompt = (
        f"{WORDCARD_POS_INSTRUCTION}\n\nInput JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )
    raw = generate_json(prompt, timeout_sec=timeout_sec)
    if not isinstance(raw, list) or len(raw) != len(items):
        raw = generate_json(
            f"{WORDCARD_POS_INSTRUCTION}\nReturn one object per input id.\n\nInput JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False)}",
            timeout_sec=timeout_sec,
        )
    if not isinstance(raw, list) or len(raw) != len(items):
        raise RuntimeError("BLOCKED: wordcard meaning translation count mismatch")
    out: dict[str, str] = {}
    for expected, row in zip(payload, raw):
        item_id = expected["id"]
        hw = expected["headword"]
        pos = expected["part_of_speech"]
        if not isinstance(row, dict):
            raise RuntimeError(f"BLOCKED: wordcard meaning item {item_id} is not an object")
        if str(row.get("id", "")).strip() != item_id:
            raise RuntimeError(f"BLOCKED: wordcard meaning id mismatch for {item_id}")
        kr = str(row.get("kr", "")).strip()
        if not meaning_matches_pos(kr, pos):
            retry = generate_json(
                f"{WORDCARD_POS_INSTRUCTION}\nHeadword: {hw}\nPart of speech: {pos}\n"
                f"Definition: {expected['definition_en']}\nExample: {expected['example_en']}\n"
                f'Return JSON only: {{"id": "{item_id}", "kr": "..."}}'
            )
            kr = str(retry.get("kr", "")).strip() if isinstance(retry, dict) else ""
            if not meaning_matches_pos(kr, pos):
                raise RuntimeError(
                    f"BLOCKED: wordcard meaning POS mismatch for {hw} ({pos}): {kr}"
                )
        conflict = meaning_conflicts_with_context(
            hw, kr, expected["definition_en"], expected["example_en"]
        )
        if conflict:
            retry = generate_json(
                f"{WORDCARD_POS_INSTRUCTION}\nThe previous gloss was wrong: {kr}\n"
                f"Headword: {hw}\nPart of speech: {pos}\n"
                f"Definition: {expected['definition_en']}\nExample: {expected['example_en']}\n"
                f'Return JSON only: {{"id": "{item_id}", "kr": "..."}}'
            )
            kr = str(retry.get("kr", "")).strip() if isinstance(retry, dict) else kr
            conflict = meaning_conflicts_with_context(
                hw, kr, expected["definition_en"], expected["example_en"]
            )
            if conflict:
                raise RuntimeError(f"BLOCKED: wordcard sense mismatch for {hw}: {conflict}")
        out[item_id] = kr
    return out
