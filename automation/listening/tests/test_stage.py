from __future__ import annotations

from automation.listening.publish.stage import write_stage


def _wordcard_block(i: int) -> str:
    return (
        f"[Card {i}]\n"
        f"headword: word{i}\n"
        f"part_of_speech: noun\n"
        f"meaning_kr: 단어{i}\n"
        f"definition_en: definition of word{i}\n"
        f"definition_kr_literal: word{i}의 정의\n"
        f"example_en: This story mentions word{i}.\n"
        f"example_kr_literal: 이 이야기는 word{i}를 언급합니다.\n\n"
    )


def _valid_files() -> dict[str, str]:
    core_sent = "Hello everyone, welcome to this English lesson today."
    return {
        "00_meta.txt": "title: t\nlevel: Level 1\n",
        "01_intro.txt": "EN: hi\nKR: 안녕\n",
        "02_core.txt": f"[Sentence 1]\nEN: {core_sent}\nKR: k1\n\n",
        "03_summary.txt": "[Part 1]\nEN: A welcome lesson intro.\nKR: k1\n\n",
        "04_full_script.txt": f"[Paragraph 1]\nEN: {core_sent}\nKR: 안녕\n",
        "05_wordcard.txt": "".join(_wordcard_block(i) for i in range(1, 3)),
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
