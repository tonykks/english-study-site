import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


MODEL = "gpt-3.5-turbo"
SOURCE_FILE = Path(
    "pages/listening/level2/KFC_Success_Story/KFC Success Story - Level 2.txt"
)
OUTPUT_FILE = Path("pages/listening/level2/KFC_Success_Story/04_full_script.txt")
MAX_CHARS_PER_PARAGRAPH = 900


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def build_paragraphs(script: str) -> list[str]:
    lines = script.splitlines()
    part_blocks: list[str] = []
    current: list[str] = []
    in_part = False

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^Part\s+\d+:", line):
            if current:
                part_blocks.append(" ".join(current).strip())
                current = []
            in_part = True
            continue
        if in_part:
            current.append(line)

    if current:
        part_blocks.append(" ".join(current).strip())

    paragraphs: list[str] = []
    for part_text in part_blocks:
        sentences = split_sentences(part_text)
        if not sentences:
            continue
        buf: list[str] = []
        buf_len = 0
        for s in sentences:
            extra = len(s) + (1 if buf else 0)
            if buf and (buf_len + extra > MAX_CHARS_PER_PARAGRAPH):
                paragraphs.append(" ".join(buf))
                buf = [s]
                buf_len = len(s)
            else:
                buf.append(s)
                buf_len += extra
        if buf:
            paragraphs.append(" ".join(buf))

    return paragraphs


def translate_paragraph(paragraph: str, api_key: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a precise translator. Translate English to Korean in a literal, "
                    "faithful style. Keep every detail. Do not summarize or omit anything."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Translate the following English paragraph into Korean. "
                    "Return only Korean translation text.\n\n"
                    f"{paragraph}"
                ),
            },
        ],
    }

    for attempt in range(5):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("Translation failed after retries")


def main() -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found")

    source_text = SOURCE_FILE.read_text(encoding="utf-8")
    paragraphs = build_paragraphs(source_text)
    if not paragraphs:
        raise RuntimeError("No paragraphs found from source")

    output_lines: list[str] = []
    total = len(paragraphs)
    for i, en in enumerate(paragraphs, start=1):
        print(f"[{i}/{total}] translating...")
        kr = translate_paragraph(en, api_key)
        output_lines.append(f"[Paragraph {i}]")
        output_lines.append(f"EN: {en}")
        output_lines.append(f"KR: {kr}")
        output_lines.append("")

    OUTPUT_FILE.write_text("\n".join(output_lines).strip() + "\n", encoding="utf-8")
    print(f"Done: {OUTPUT_FILE}")
    print(f"Paragraphs: {len(paragraphs)}")
    print(f"Output chars: {len(OUTPUT_FILE.read_text(encoding='utf-8'))}")


if __name__ == "__main__":
    main()
