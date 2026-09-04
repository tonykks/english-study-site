from __future__ import annotations

from automation.listening.generate.data_files import validate_format_files
from automation.listening.generate.sections import (
    build_story_sections,
    chunk_segments_for_inference,
    fill_section_content,
    merge_section_candidates,
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
    fill_section_content(sections, segments, level=1, allow_placeholder=True)

    def fake_translate_batch(items, *, allow_placeholder: bool = False):
        return {item_id: f"KR:{text[:20]}" for item_id, text in items}

    core = render_core_file(sections, fake_translate_batch, allow_placeholder=True)
    summary = render_summary_file(sections, fake_translate_batch, allow_placeholder=True)
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
    assert "not an exact Full Script sentence" in reason or "not found in verified full script" in reason


def test_chunk_segments_for_long_transcript():
    segments = _fixture_segments()
    expanded = []
    for i in range(60):
        for seg in segments:
            expanded.append(
                type(seg)(
                    segment_id=f"seg_{len(expanded)+1:05d}",
                    start=seg.start + i * 120,
                    end=seg.end + i * 120,
                    text_en=seg.text_en,
                    source=seg.source,
                )
            )
    chunks = chunk_segments_for_inference(expanded, max_segments=400, overlap=40)
    assert len(chunks) > 1
    assert sum(len(c) for c in chunks) > len(expanded)


def test_merge_preserves_three_adjacent_sections_same_chunk():
    candidates = [
        {"title": "Part A", "start": 0.0, "end": 300.0, "source_chunk": 0},
        {"title": "Part B", "start": 300.0, "end": 600.0, "source_chunk": 0},
        {"title": "Part C", "start": 600.0, "end": 900.0, "source_chunk": 0},
    ]
    merged = merge_section_candidates(candidates)
    assert len(merged) == 3
    assert [m["start"] for m in merged] == [0.0, 300.0, 600.0]
    assert [m["end"] for m in merged] == [300.0, 600.0, 900.0]


def test_merge_deduplicates_cross_chunk_overlap_only():
    candidates = [
        {"title": "Part A", "start": 0.0, "end": 300.0, "source_chunk": 0},
        {"title": "Part B", "start": 300.0, "end": 600.0, "source_chunk": 0},
        {"title": "Part B overlap", "start": 280.0, "end": 600.0, "source_chunk": 1},
        {"title": "Part C", "start": 600.0, "end": 900.0, "source_chunk": 1},
    ]
    merged = merge_section_candidates(candidates)
    assert len(merged) == 3
    assert merged[0]["start"] == 0.0
    assert merged[0]["end"] == 300.0
    assert merged[1]["start"] == 280.0
    assert merged[1]["end"] == 600.0
    assert merged[2]["start"] == 600.0
    assert merged[2]["end"] == 900.0


def test_merge_without_source_chunk_does_not_merge_adjacent():
    candidates = [
        {"title": "Intro", "start": 0.0, "end": 300.0},
        {"title": "Middle", "start": 300.0, "end": 600.0},
        {"title": "End", "start": 600.0, "end": 900.0},
    ]
    merged = merge_section_candidates(candidates)
    assert len(merged) == 3

