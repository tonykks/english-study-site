from __future__ import annotations

from automation.listening.generate.data_files import validate_format_files
from automation.listening.generate.sections import (
    build_story_sections,
    fill_section_content,
    render_core_file,
    render_summary_file,
)
from automation.listening.script.canonical import segments_from_raw


def _fixture_segments():
    raw = [
        {"start": 0.0, "end": 5.0, "text": "Hello everyone, welcome to this English lesson today."},
        {"start": 5.0, "end": 12.0, "text": "We will learn useful expressions through a short story."},
        {"start": 12.0, "end": 20.0, "text": "Listen carefully and repeat each sentence for better pronunciation."},
        {"start": 20.0, "end": 30.0, "text": "The main character faced many challenges but never gave up hope."},
        {"start": 30.0, "end": 42.0, "text": "She worked hard every day and practiced speaking with confidence."},
        {"start": 42.0, "end": 55.0, "text": "Eventually her effort paid off and she achieved her dream goal."},
        {"start": 55.0, "end": 70.0, "text": "This story teaches us that persistence and courage matter most."},
        {"start": 70.0, "end": 85.0, "text": "Remember to review the vocabulary cards after finishing the script."},
        {"start": 85.0, "end": 100.0, "text": "Thank you for studying with us and see you in the next lesson."},
    ]
    return segments_from_raw(raw, source="fixture")


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


def test_section_alignment_pass():
    segments = _fixture_segments()
    sections = build_story_sections(segments, "fixture000001", allow_placeholder=True)
    fill_section_content(sections, segments, allow_placeholder=True)

    def fake_translate(en: str, *, allow_placeholder: bool = False) -> str:
        return f"KR:{en[:20]}"

    core = render_core_file(sections, fake_translate, allow_placeholder=True)
    summary = render_summary_file(sections, fake_translate, allow_placeholder=True)
    n = len(sections)

    files = {
        "00_meta.txt": "title: t\nlevel: Level 1\n",
        "01_intro.txt": "EN: hi\nKR: 안녕\n",
        "02_core.txt": core,
        "03_summary.txt": summary,
        "04_full_script.txt": "[Paragraph 1]\nEN: " + " ".join(s.text_en for s in segments) + "\nKR: kr\n",
        "05_wordcard.txt": "".join(_wordcard_block(i) for i in range(1, 3)),
    }
    ok, reason = validate_format_files(files, segments=segments, reject_placeholders=False)
    assert ok, reason
    assert n >= 1


def test_section_alignment_fail_mismatch():
    files = {
        "00_meta.txt": "title: t\nlevel: Level 1\n",
        "01_intro.txt": "EN: hi\nKR: 안녕\n",
        "02_core.txt": "[Sentence 1]\nEN: Hello everyone, welcome to this English lesson today.\nKR: k\n\n"
        "[Sentence 2]\nEN: We will learn useful expressions through a short story.\nKR: k\n\n",
        "03_summary.txt": "[Part 1]\nEN: p\nKR: k\n\n",
        "04_full_script.txt": "[Paragraph 1]\nEN: Hello everyone.\nKR: kr\n",
        "05_wordcard.txt": _wordcard_block(1),
    }
    ok, reason = validate_format_files(files, reject_placeholders=False)
    assert not ok
    assert "section mismatch" in reason.lower() or "sentences but" in reason


def test_core_sentence_must_exist_in_script():
    files = {
        "00_meta.txt": "title: t\nlevel: Level 1\n",
        "01_intro.txt": "EN: hi\nKR: 안녕\n",
        "02_core.txt": "[Sentence 1]\nEN: This sentence is not in the script.\nKR: k\n\n",
        "03_summary.txt": "[Part 1]\nEN: p\nKR: k\n\n",
        "04_full_script.txt": "[Paragraph 1]\nEN: Hello world.\nKR: kr\n",
        "05_wordcard.txt": _wordcard_block(1),
    }
    ok, reason = validate_format_files(files, reject_placeholders=False)
    assert not ok
    assert "not found in verified full script" in reason
