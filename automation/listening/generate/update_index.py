from __future__ import annotations

import json
import re
from pathlib import Path

from automation.listening.config import LISTENING_ROOT, extract_video_id


def find_existing_video_ids() -> set[str]:
    ids: set[str] = set()
    for meta in LISTENING_ROOT.rglob("00_meta.txt"):
        text = meta.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if line.lower().startswith("video_id:"):
                val = line.split(":", 1)[1].strip()
                if val and val.lower() != "none":
                    ids.add(val)
            if line.lower().startswith("video_url:"):
                try:
                    ids.add(extract_video_id(line.split(":", 1)[1].strip()))
                except ValueError:
                    pass
    return ids


def find_existing_folders() -> set[str]:
    folders: set[str] = set()
    for path in LISTENING_ROOT.rglob("*"):
        if path.is_dir() and (path / "00_meta.txt").exists():
            folders.add(path.name)
    return folders


def check_duplicate(video_id: str, folder: str, href: str | None = None) -> str | None:
    if video_id in find_existing_video_ids():
        return f"video_id {video_id} already exists"
    if folder in find_existing_folders():
        return f"folder {folder} already exists"
    if href:
        index_path = LISTENING_ROOT / "index.html"
        if index_path.exists() and href in index_path.read_text(encoding="utf-8", errors="ignore"):
            return f"href {href} already exists"
    return None


def bracket_balance_ok(js_snippet: str) -> bool:
    return js_snippet.count("[") == js_snippet.count("]") and js_snippet.count("{") == js_snippet.count("}")


def append_listening_card(index_path: Path, card: dict, dry_run: bool = False) -> str:
    original = index_path.read_text(encoding="utf-8")
    match = re.search(r"(const\s+listeningCards\s*=\s*\[)([\s\S]*?)(\]\s*;)", original)
    if not match:
        raise ValueError("listeningCards array not found")

    array_body = match.group(2)
    if card["href"] in original:
        return "idempotent: href already present"

    intro_escaped = card["introEn"].replace("\\", "\\\\").replace('"', '\\"')
    title_escaped = card["title"].replace("\\", "\\\\").replace('"', '\\"')
    entry = (
        "\n        {\n"
        f'          level: "{card["level"]}",\n'
        f'          title: "{title_escaped}",\n'
        f'          introEn: "{intro_escaped}",\n'
        f'          tags: {json.dumps(card["tags"], ensure_ascii=False)},\n'
        f'          href: "{card["href"]}"\n'
        "        },"
    )
    trimmed = array_body.rstrip()
    if trimmed and not trimmed.endswith(","):
        trimmed = trimmed + ","
    new_body = trimmed + entry + "\n      "
    new_content = original[: match.start(2)] + new_body + original[match.end(2) :]

    new_match = re.search(r"(const\s+listeningCards\s*=\s*\[)([\s\S]*?)(\]\s*;)", new_content)
    if not new_match or not bracket_balance_ok(new_match.group(0)):
        raise ValueError("Bracket balance check failed after append")

    if dry_run:
        return f"dry-run: would append card href={card['href']}"

    index_path.write_text(new_content, encoding="utf-8")
    return "appended"
