from __future__ import annotations

import json
import logging
from pathlib import Path

from automation.listening.config import (
    FIXTURES_DIR,
    LISTENING_ROOT,
    LEVEL_LABEL,
    LEVEL_MAP,
    level_folder,
    load_config,
    sanitize_folder_name,
)
from automation.listening.vertex_client import vertex_configured
from automation.listening.generate.data_files import (
    assemble_04_en,
    build_sections_for_transcript,
    generate_core_from_sections,
    generate_intro_from_transcript,
    generate_meta,
    generate_summary_from_sections,
    generate_wordcards_from_transcript,
    inject_kr_into_04,
    validate_format_files,
    verify_04_en_manifest,
)
from automation.listening.generate.page_html import render_lesson_page
from automation.listening.generate.translate import translate_paragraphs_kr
from automation.listening.generate.update_index import check_duplicate
from automation.listening.models import PipelineResult, Segment, VideoMeta
from automation.listening.publish.publish import publish_to_repo
from automation.listening.publish.stage import write_comparison, write_stage
from automation.listening.script.canonical import consolidate_caption_segments, group_paragraphs, merge_overlapping_segments, segments_from_raw
from automation.listening.script.caption_restore import (
    is_complete_sentence,
    restore_caption_segments,
    validate_no_artificial_sentence_breaks,
    words_unchanged,
    join_caption_fragments,
)
from automation.listening.generate.cta_filter import segments_for_learning
from automation.listening.script.validate import (
    cross_validate,
    validate_04_en_fidelity,
    validate_segments,
    validate_transcript_fidelity,
)
from automation.listening.script.vertex_transcribe import chunk_segments, transcribe_with_vertex
from automation.listening.youtube.duration import fetch_youtube_duration
from automation.listening.youtube.metadata import fetch_metadata
from automation.listening.youtube.transcript import fetch_caption_segments

logger = logging.getLogger(__name__)


def load_fixture_segments(name: str = "sample_segments.json") -> tuple[list[Segment], VideoMeta, list[dict] | None]:
    path = FIXTURES_DIR / name
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = segments_from_raw(data["segments"], source="fixture")
    meta = VideoMeta(
        video_id=data["video_id"],
        title=data["title"],
        channel=data.get("channel", "Fixture Channel"),
        duration=float(data.get("duration", max(s.end for s in segments))),
        video_url=f"https://youtu.be/{data['video_id']}",
    )
    chapters = data.get("chapters")
    return segments, meta, chapters


def run_pipeline(
    url: str,
    level: int,
    *,
    dry_run: bool = False,
    fixture: str | None = None,
    comparison: bool = False,
    asr_override: list[Segment] | None = None,
) -> PipelineResult:
    load_config()

    if level not in LEVEL_MAP:
        return PipelineResult("BLOCKED", "Level must be 1, 2, or 3")

    fixture_chapters: list[dict] | None = None
    if fixture:
        segments, meta, fixture_chapters = load_fixture_segments(fixture)
        verified = segments
        val = validate_segments(verified, meta.duration)
        if not val.ok:
            return PipelineResult("BLOCKED", val.reason, video_id=meta.video_id)
        logger.info("Fixture mode: %s segments loaded", len(verified))
    else:
        meta = fetch_metadata(url)
        content_id = sanitize_folder_name(meta.title)
        href = f"./{level_folder(level)}/{content_id}/{content_id}.html"
        if not comparison:
            dup = check_duplicate(meta.video_id, content_id, href)
            if dup:
                return PipelineResult("PASS", f"idempotent: {dup}", video_id=meta.video_id)

        caption_segments: list[Segment] = []
        cap_duration = 0.0
        try:
            caption_segments, is_auto, cap_duration = fetch_caption_segments(meta.video_id)
        except Exception as exc:
            logger.warning("Caption fetch failed: %s", exc)

        if not caption_segments:
            return PipelineResult(
                "BLOCKED",
                "No English captions available; ASR-only path not supported in V1 without cross-validation",
                video_id=meta.video_id,
            )

        video_duration = fetch_youtube_duration(meta.video_id)
        if video_duration > 0:
            meta.duration = video_duration
        elif cap_duration > 0:
            meta.duration = cap_duration

        if not vertex_configured():
            return PipelineResult(
                "BLOCKED",
                "GOOGLE_CLOUD_PROJECT required for Vertex AI (ADC)",
                video_id=meta.video_id,
            )

        try:
            if asr_override is not None:
                asr_segments = asr_override
            else:
                asr_segments = transcribe_with_vertex(meta.video_id, meta.duration or cap_duration)
        except Exception as exc:
            return PipelineResult("BLOCKED", str(exc), video_id=meta.video_id)

        try:
            restored_caption = restore_caption_segments(caption_segments, asr_segments)
        except RuntimeError as exc:
            return PipelineResult("BLOCKED", str(exc), video_id=meta.video_id)

        restored_full = " ".join(s.text_en for s in restored_caption)
        break_check = validate_no_artificial_sentence_breaks(restored_full)
        if not break_check.ok:
            return PipelineResult("BLOCKED", break_check.reason, video_id=meta.video_id)

        if not words_unchanged(join_caption_fragments(caption_segments), restored_full):
            return PipelineResult(
                "BLOCKED",
                "Caption restoration altered word content or order",
                video_id=meta.video_id,
            )

        if caption_segments:
            caps_for_cv = consolidate_caption_segments(restored_caption)
            if meta.duration > 15 * 60:
                cap_chunks = chunk_segments(caps_for_cv, meta.duration)
                asr_chunks = chunk_segments(asr_segments, meta.duration)
                merged_caps = merge_overlapping_segments(cap_chunks)
                merged_asr = merge_overlapping_segments(asr_chunks)
                verified, cv = cross_validate(merged_caps, merged_asr)
            else:
                verified, cv = cross_validate(caps_for_cv, asr_segments)

            if not cv.ok:
                return PipelineResult("BLOCKED", cv.reason, video_id=meta.video_id)

            fidelity = validate_transcript_fidelity(caps_for_cv, verified)
            if not fidelity.ok:
                return PipelineResult("BLOCKED", fidelity.reason, video_id=meta.video_id)

        val = validate_segments(verified, meta.duration or cap_duration)
        if not val.ok:
            return PipelineResult("BLOCKED", val.reason, video_id=meta.video_id)

    content_id = sanitize_folder_name(meta.title)
    href = f"./{level_folder(level)}/{content_id}/{content_id}.html"
    if not fixture and not comparison:
        dup = check_duplicate(meta.video_id, content_id, href)
        if dup:
            return PipelineResult("PASS", f"idempotent: {dup}", video_id=meta.video_id, folder=content_id)

    content_04_en, manifest = assemble_04_en(verified)
    if not verify_04_en_manifest(verified, content_04_en, manifest):
        return PipelineResult("BLOCKED", "04 EN manifest verification failed", video_id=meta.video_id)
    fidelity_04 = validate_04_en_fidelity(verified, content_04_en)
    if not fidelity_04.ok:
        return PipelineResult("BLOCKED", fidelity_04.reason, video_id=meta.video_id)

    allow_placeholder = bool(fixture)
    try:
        paragraphs = group_paragraphs(verified)
        kr_paragraphs = translate_paragraphs_kr(paragraphs, allow_placeholder=allow_placeholder)
        content_04 = inject_kr_into_04(content_04_en, kr_paragraphs)
        sections = build_sections_for_transcript(
            segments_for_learning(verified),
            meta.video_id,
            level,
            allow_placeholder=allow_placeholder,
            chapters=fixture_chapters,
        )
        core_text = generate_core_from_sections(sections, allow_placeholder=allow_placeholder)
        files = {
            "00_meta.txt": generate_meta(meta, level),
            "01_intro.txt": generate_intro_from_transcript(
                verified, level, allow_placeholder=allow_placeholder
            ),
            "02_core.txt": core_text,
            "03_summary.txt": generate_summary_from_sections(sections, allow_placeholder=allow_placeholder),
            "04_full_script.txt": content_04,
            "05_wordcard.txt": generate_wordcards_from_transcript(
                verified, core_text, level, allow_placeholder=allow_placeholder
            ),
        }
    except RuntimeError as exc:
        return PipelineResult("BLOCKED", str(exc), video_id=meta.video_id)

    ok, reason = validate_format_files(files, segments=verified, reject_placeholders=not allow_placeholder)
    if not ok:
        return PipelineResult("BLOCKED", f"Format validation failed: {reason}", video_id=meta.video_id)

    html_content = render_lesson_page(content_id, level, meta.title)
    html_name = f"{content_id}.html"

    if comparison:
        comp_dir = write_comparison(
            meta.video_id,
            files,
            manifest,
            verified,
            html_content=html_content,
            html_name=html_name,
            reject_placeholders=not allow_placeholder,
        )
        return PipelineResult(
            "COMPARISON",
            f"comparison output written to {comp_dir} (repo unchanged)",
            folder=content_id,
            video_id=meta.video_id,
            staging_dir=str(comp_dir),
        )

    stage_dir = write_stage(
        meta.video_id,
        files,
        manifest,
        verified,
        html_content=html_content,
        html_name=html_name,
        reject_placeholders=not allow_placeholder,
    )

    href = f"./{level_folder(level)}/{content_id}/{content_id}.html"
    intro_match = files["01_intro.txt"]
    intro_en = ""
    for line in intro_match.splitlines():
        if line.startswith("EN:"):
            intro_en = line[3:].strip()
            break

    card = {
        "level": level_folder(level),
        "title": meta.title,
        "introEn": intro_en or meta.title,
        "tags": [LEVEL_LABEL[level], "자동생성" if fixture else "신규"],
        "href": href,
        "video_id": meta.video_id,
    }

    if dry_run or fixture:
        msg = publish_to_repo(stage_dir, level, content_id, card, dry_run=True)
        return PipelineResult(
            "DRY_RUN" if dry_run else "PASS",
            msg,
            folder=content_id,
            video_id=meta.video_id,
            staging_dir=str(stage_dir),
        )

    try:
        msg = publish_to_repo(stage_dir, level, content_id, card, dry_run=False)
        return PipelineResult("PASS", msg, folder=content_id, video_id=meta.video_id)
    except Exception as exc:
        return PipelineResult("BLOCKED", f"Publish failed: {exc}", video_id=meta.video_id)
