from __future__ import annotations

from pathlib import Path

from automation.listening.config import LEVEL_LABEL, TEMPLATE_PATH


def render_lesson_page(content_id: str, level: int, title: str) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace('data-content-id="KFC_Success_Story"', f'data-content-id="{content_id}"')
    html = html.replace(
        'id="breadcrumb-title" class="font-medium text-gray-800">KFC Success Story<',
        f'id="breadcrumb-title" class="font-medium text-gray-800">{title}<',
    )
    html = html.replace(
        'id="breadcrumb-level" class="text-gray-500">Level 2<',
        f'id="breadcrumb-level" class="text-gray-500">{LEVEL_LABEL[level]}<',
    )
    return html


def write_lesson_page(staging_dir: Path, content_id: str, level: int, title: str) -> Path:
    html = render_lesson_page(content_id, level, title)
    out = staging_dir / f"{content_id}.html"
    out.write_text(html, encoding="utf-8")
    return out
