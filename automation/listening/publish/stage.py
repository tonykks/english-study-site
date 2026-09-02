from __future__ import annotations

import json
import shutil
from pathlib import Path

from automation.listening.config import COMPARISON_ROOT, STAGING_ROOT
from automation.listening.generate.data_files import validate_format_files, verify_04_en_manifest
from automation.listening.models import Segment


def staging_dir_for(video_id: str) -> Path:
    return STAGING_ROOT / video_id


def comparison_dir_for(video_id: str) -> Path:
    return COMPARISON_ROOT / video_id


def _write_output_dir(
    output_dir: Path,
    files: dict[str, str],
    manifest: list[dict],
    segments: list[Segment] | None = None,
    *,
    html_content: str | None = None,
    html_name: str | None = None,
    reject_placeholders: bool = True,
) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (output_dir / name).write_text(content, encoding="utf-8")
    if html_content and html_name:
        (output_dir / html_name).write_text(html_content, encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ok, reason = validate_format_files(files, segments=segments, reject_placeholders=reject_placeholders)
    if not ok:
        raise ValueError(f"Output validation failed: {reason}")
    if segments and not verify_04_en_manifest(segments, files.get("04_full_script.txt", ""), manifest):
        raise ValueError("Output validation failed: 04 manifest hash mismatch")
    return output_dir


def write_stage(
    video_id: str,
    files: dict[str, str],
    manifest: list[dict],
    segments: list[Segment] | None = None,
    *,
    html_content: str | None = None,
    html_name: str | None = None,
    reject_placeholders: bool = True,
) -> Path:
    return _write_output_dir(
        staging_dir_for(video_id),
        files,
        manifest,
        segments,
        html_content=html_content,
        html_name=html_name,
        reject_placeholders=reject_placeholders,
    )


def write_comparison(
    video_id: str,
    files: dict[str, str],
    manifest: list[dict],
    segments: list[Segment] | None = None,
    *,
    html_content: str | None = None,
    html_name: str | None = None,
    reject_placeholders: bool = True,
) -> Path:
    return _write_output_dir(
        comparison_dir_for(video_id),
        files,
        manifest,
        segments,
        html_content=html_content,
        html_name=html_name,
        reject_placeholders=reject_placeholders,
    )


def clear_staging(video_id: str) -> None:
    stage = staging_dir_for(video_id)
    if stage.exists():
        shutil.rmtree(stage)
