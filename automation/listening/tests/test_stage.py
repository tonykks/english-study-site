from __future__ import annotations

from automation.listening.models import Segment
from automation.listening.publish.stage import write_stage
from automation.listening.script.canonical import segments_from_raw


def test_write_stage_includes_html(tmp_path, monkeypatch):
    monkeypatch.setattr("automation.listening.publish.stage.STAGING_ROOT", tmp_path)
    segments = segments_from_raw([{"start": 0, "end": 2, "text": "Hello world."}])
    files = {
        "00_meta.txt": "title: t\nlevel: Level 1\n",
        "01_intro.txt": "EN: hi\nKR: 안녕\n",
        "02_core.txt": "[Sentence 1]\nEN: hi\nKR: 안녕\n",
        "03_summary.txt": "[Part 1]\nEN: hi\nKR: 안녕\n",
        "04_full_script.txt": "[Paragraph 1]\nEN: Hello world.\nKR: 안녕\n",
        "05_wordcard.txt": "[Card 1]\nheadword: hello\n",
    }
    stage = write_stage(
        "vid123",
        files,
        [],
        segments,
        html_content="<html>lesson</html>",
        html_name="Lesson.html",
    )
    assert (stage / "Lesson.html").read_text(encoding="utf-8") == "<html>lesson</html>"
