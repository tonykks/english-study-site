from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
LISTENING_ROOT = REPO_ROOT / "pages" / "listening"
STAGING_ROOT = REPO_ROOT / "automation" / ".staging"
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "lesson_page.html"
FIXTURES_DIR = Path(__file__).resolve().parent / "tests" / "fixtures"

CHUNK_SECONDS = 15 * 60
OVERLAP_SECONDS = 30
GAP_BLOCK_SECONDS = 10
COVERAGE_MIN = 0.95
DIVERGENCE_WORD_THRESHOLD = 0.15
DIVERGENCE_DURATION_BLOCK = 0.05
DUPLICATE_BLOCK_COUNT = 3

LEVEL_MAP = {1: "level1", 2: "level2", 3: "level3"}
LEVEL_LABEL = {1: "Level 1", 2: "Level 2", 3: "Level 3"}


def load_config() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)


def extract_video_id(url: str) -> str:
    text = (url or "").strip()
    patterns = [
        r"(?:youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/|youtube\.com/live/|v=)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", text):
        return text
    raise ValueError(f"Invalid YouTube URL or video_id: {url}")


def sanitize_folder_name(title: str) -> str:
    cleaned = re.sub(r"[^\w\s'-]", "", title or "content")
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = cleaned.strip("_") or "content"
    return cleaned[:80]


def level_folder(level: int) -> str:
    if level not in LEVEL_MAP:
        raise ValueError("Level must be 1, 2, or 3")
    return LEVEL_MAP[level]


def gemini_configured() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY"))


def openai_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))
