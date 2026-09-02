from __future__ import annotations

from automation.listening.config import CORE_SENTENCE_COUNT, SUMMARY_PART_COUNT, WORDCARD_COUNT
from automation.listening.generate.data_files import validate_format_files


def test_format_counts_pass():
    files = {
        "00_meta.txt": "title: t\nlevel: Level 1\n",
        "01_intro.txt": "EN: hi\nKR: 안녕\n",
        "02_core.txt": "".join(
            f"[Sentence {i}]\nEN: s{i}\nKR: k{i}\n\n" for i in range(1, CORE_SENTENCE_COUNT + 1)
        ),
        "03_summary.txt": "".join(
            f"[Part {i}]\nEN: p{i}\nKR: k{i}\n\n" for i in range(1, SUMMARY_PART_COUNT + 1)
        ),
        "04_full_script.txt": "[Paragraph 1]\nEN: full\nKR: full kr\n",
        "05_wordcard.txt": "".join(
            f"[Card {i}]\nheadword: w{i}\n" for i in range(1, WORDCARD_COUNT + 1)
        ),
    }
    ok, reason = validate_format_files(files, reject_placeholders=False)
    assert ok, reason


def test_format_counts_fail_core():
    files = {
        "00_meta.txt": "title: t\nlevel: Level 1\n",
        "01_intro.txt": "EN: hi\nKR: 안녕\n",
        "02_core.txt": "[Sentence 1]\nEN: only one\nKR: k\n",
        "03_summary.txt": "".join(
            f"[Part {i}]\nEN: p\nKR: k\n\n" for i in range(1, SUMMARY_PART_COUNT + 1)
        ),
        "04_full_script.txt": "[Paragraph 1]\nEN: full\nKR: kr\n",
        "05_wordcard.txt": "".join(f"[Card {i}]\nheadword: w\n" for i in range(1, WORDCARD_COUNT + 1)),
    }
    ok, reason = validate_format_files(files, reject_placeholders=False)
    assert not ok
    assert "02_core" in reason
