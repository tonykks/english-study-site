from __future__ import annotations

from automation.listening.config import CORE_SENTENCE_COUNT, SUMMARY_PART_COUNT, WORDCARD_COUNT
from automation.listening.publish.stage import write_stage


def _valid_files() -> dict[str, str]:
    return {
        "00_meta.txt": "title: t\nlevel: Level 1\n",
        "01_intro.txt": "EN: hi\nKR: 안녕\n",
        "02_core.txt": "".join(
            f"[Sentence {i}]\nEN: s{i}\nKR: k{i}\n\n" for i in range(1, CORE_SENTENCE_COUNT + 1)
        ),
        "03_summary.txt": "".join(
            f"[Part {i}]\nEN: p{i}\nKR: k{i}\n\n" for i in range(1, SUMMARY_PART_COUNT + 1)
        ),
        "04_full_script.txt": "[Paragraph 1]\nEN: Hello world.\nKR: 안녕\n",
        "05_wordcard.txt": "".join(
            f"[Card {i}]\nheadword: w{i}\n" for i in range(1, WORDCARD_COUNT + 1)
        ),
    }


def test_write_stage_includes_html(tmp_path, monkeypatch):
    monkeypatch.setattr("automation.listening.publish.stage.STAGING_ROOT", tmp_path)
    stage = write_stage(
        "vid123",
        _valid_files(),
        [],
        None,
        html_content="<html>lesson</html>",
        html_name="Lesson.html",
        reject_placeholders=False,
    )
    assert (stage / "Lesson.html").read_text(encoding="utf-8") == "<html>lesson</html>"
