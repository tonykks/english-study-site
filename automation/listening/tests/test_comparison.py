from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from automation.listening.config import LISTENING_ROOT
from automation.listening.pipeline import run_pipeline


def test_comparison_mode_writes_output_without_touching_repo(tmp_path, monkeypatch):
    comparison_root = tmp_path / "comparison"
    monkeypatch.setattr("automation.listening.config.COMPARISON_ROOT", comparison_root)
    monkeypatch.setattr("automation.listening.publish.stage.COMPARISON_ROOT", comparison_root)

    index_path = LISTENING_ROOT / "index.html"
    index_before = index_path.read_text(encoding="utf-8")

    result = run_pipeline(
        "fixture://local",
        2,
        fixture="sample_segments.json",
        comparison=True,
    )

    assert result.status == "COMPARISON"
    assert "repo unchanged" in result.message
    comp_dir = comparison_root / "fixture000001"
    assert comp_dir.is_dir()
    assert (comp_dir / "02_core.txt").is_file()
    assert (comp_dir / "04_full_script.txt").is_file()
    assert (comp_dir / "manifest.json").is_file()
    assert index_path.read_text(encoding="utf-8") == index_before


def test_comparison_skips_duplicate_guard():
    with patch("automation.listening.pipeline.load_fixture_segments") as load_fix, patch(
        "automation.listening.pipeline.check_duplicate",
        return_value="video_id exists",
    ) as dup_check, patch(
        "automation.listening.pipeline.write_comparison",
        return_value=Path("automation/.comparison/vid123"),
    ) as write_comp:
        from automation.listening.models import Segment, VideoMeta

        segments = [
            Segment("seg_00001", 0.0, 5.0, "Hello world.", "fixture"),
        ]
        meta = VideoMeta("vid123", "Title", "Ch", 5.0, "https://youtu.be/vid123")
        load_fix.return_value = (segments, meta, None)

        with patch("automation.listening.pipeline.validate_segments") as val_seg, patch(
            "automation.listening.pipeline.assemble_04_en",
            return_value=("[Paragraph 1]\nEN: Hello world.\nKR: \n", []),
        ), patch("automation.listening.pipeline.verify_04_en_manifest", return_value=True), patch(
            "automation.listening.pipeline.group_paragraphs",
            return_value=["Hello world."],
        ), patch(
            "automation.listening.pipeline.translate_paragraphs_kr",
            return_value=["KR"],
        ), patch(
            "automation.listening.pipeline.build_sections_for_transcript"
        ) as build_sec, patch(
            "automation.listening.pipeline.generate_core_from_sections",
            return_value="[Sentence 1]\nEN: Hello world.\nKR: k\n",
        ), patch(
            "automation.listening.pipeline.generate_intro_from_transcript",
            return_value="EN: hi\nKR: k\n",
        ), patch(
            "automation.listening.pipeline.generate_summary_from_sections",
            return_value="[Part 1]\nEN: p\nKR: k\n",
        ), patch(
            "automation.listening.pipeline.generate_wordcards_from_transcript",
            return_value="[Card 1]\nheadword: w\n",
        ), patch(
            "automation.listening.pipeline.validate_format_files",
            return_value=(True, "OK"),
        ), patch(
            "automation.listening.pipeline.render_lesson_page",
            return_value="<html></html>",
        ):
            from automation.listening.models import StorySection

            build_sec.return_value = [
                StorySection(1, "S1", "Hello world.", 0.0, 5.0, "Hello world.", "Summary.")
            ]
            val_seg.return_value = type("V", (), {"ok": True, "reason": ""})()

            result = run_pipeline("fixture://", 2, fixture="sample_segments.json", comparison=True)

    dup_check.assert_not_called()
    write_comp.assert_called_once()
    assert result.status == "COMPARISON"


def test_production_still_blocks_duplicate():
    with patch("automation.listening.pipeline.fetch_metadata") as fetch_meta, patch(
        "automation.listening.pipeline.check_duplicate",
        return_value="video_id abc already exists",
    ):
        from automation.listening.models import VideoMeta

        fetch_meta.return_value = VideoMeta("abc12345678", "Dup", "Ch", 60.0, "https://youtu.be/abc12345678")
        result = run_pipeline("https://youtu.be/abc12345678", 2, comparison=False)

    assert result.status == "PASS"
    assert "idempotent" in result.message
