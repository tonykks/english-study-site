from __future__ import annotations

import logging
import re

from automation.listening.models import Segment, StorySection
from automation.listening.utils import normalize_text, split_sentences
from automation.listening.vertex_client import generate_json, vertex_configured
from automation.listening.youtube.chapters import fetch_youtube_chapters

logger = logging.getLogger(__name__)


def _segments_in_range(segments: list[Segment], start: float, end: float) -> list[Segment]:
    return [s for s in segments if s.end > start and s.start < end]


def _section_text(segs: list[Segment]) -> str:
    return " ".join(s.text_en for s in segs).strip()


def _sections_from_chapters(segments: list[Segment], chapters: list[dict]) -> list[StorySection]:
    sections: list[StorySection] = []
    for i, ch in enumerate(chapters, start=1):
        segs = _segments_in_range(segments, float(ch["start"]), float(ch["end"]))
        text = _section_text(segs)
        if not text:
            continue
        sections.append(
            StorySection(
                index=len(sections) + 1,
                title=str(ch.get("title") or f"Section {i}"),
                text_en=text,
                start=float(ch["start"]),
                end=float(ch["end"]),
            )
        )
    return sections


def _infer_sections_vertex(segments: list[Segment]) -> list[StorySection]:
    if len(segments) > 500:
        logger.warning(
            "Transcript has %d segments; using heuristic sections instead of Vertex inference",
            len(segments),
        )
        return _heuristic_sections(segments)

    lines = [f"{i + 1}. [{s.start:.1f}-{s.end:.1f}] {s.text_en}" for i, s in enumerate(segments)]
    transcript = "\n".join(lines)
    data = generate_json(
        f"""Divide this English listening transcript into natural story sections.
Rules:
- Use YouTube-like section boundaries based on plot events, topic shifts, or logical transitions
- Do NOT merge or split sections to hit a target count
- Each section needs a short title and start/end timestamps in seconds
- Cover the full transcript without gaps or overlaps

Return JSON:
{{"sections": [{{"title": "...", "start": 0.0, "end": 30.0}}, ...]}}

Transcript ({len(segments)} caption segments):
{transcript}
"""
    )
    raw_sections = data.get("sections") or []
    if not raw_sections:
        raise RuntimeError("BLOCKED: Vertex section inference returned no sections")

    sections: list[StorySection] = []
    for i, item in enumerate(raw_sections, start=1):
        start = float(item.get("start", 0.0))
        end = float(item.get("end", start + 1.0))
        segs = _segments_in_range(segments, start, end)
        text = _section_text(segs)
        if not text:
            continue
        sections.append(
            StorySection(
                index=len(sections) + 1,
                title=str(item.get("title") or f"Section {i}"),
                text_en=text,
                start=start,
                end=end,
            )
        )
    if not sections:
        raise RuntimeError("BLOCKED: Vertex section inference produced empty sections")
    return sections


def _heuristic_sections(segments: list[Segment]) -> list[StorySection]:
    """Placeholder sections for fixture/dry-run without Vertex."""
    if not segments:
        return []

    from automation.listening.script.canonical import group_paragraphs

    paragraphs = group_paragraphs(segments, min_sentences=2, max_sentences=4)
    if len(paragraphs) == 1 and len(segments) >= 6:
        mid = len(segments) // 2
        halves = [segments[:mid], segments[mid:]]
        paragraphs = [_section_text(h) for h in halves if _section_text(h)]

    sections: list[StorySection] = []
    seg_idx = 0
    for i, para in enumerate(paragraphs, start=1):
        word_count = len(normalize_text(para).split())
        consumed = max(1, min(len(segments) - seg_idx, word_count // 3 or 1))
        chunk = segments[seg_idx : seg_idx + consumed]
        seg_idx = min(len(segments), seg_idx + consumed)
        start = chunk[0].start if chunk else 0.0
        end = chunk[-1].end if chunk else start
        sections.append(
            StorySection(
                index=i,
                title=f"Section {i}",
                text_en=para,
                start=start,
                end=end,
            )
        )
    if seg_idx < len(segments) and sections:
        tail = segments[seg_idx:]
        sections[-1].text_en = (sections[-1].text_en + " " + _section_text(tail)).strip()
        sections[-1].end = tail[-1].end
    return sections


def build_story_sections(
    segments: list[Segment],
    video_id: str,
    *,
    allow_placeholder: bool = False,
    chapters: list[dict] | None = None,
) -> list[StorySection]:
    if not segments:
        raise RuntimeError("BLOCKED: no segments for section building")

    if chapters:
        from_chapters = _sections_from_chapters(segments, chapters)
        if from_chapters:
            return from_chapters

    if not allow_placeholder:
        explicit = fetch_youtube_chapters(video_id)
        if explicit:
            from_chapters = _sections_from_chapters(segments, explicit)
            if from_chapters:
                logger.info("Using %d YouTube chapters as sections", len(from_chapters))
                return from_chapters

    if vertex_configured() and not allow_placeholder:
        return _infer_sections_vertex(segments)

    sections = _heuristic_sections(segments)
    if not sections:
        raise RuntimeError("BLOCKED: could not build story sections")
    return sections


def _sentence_in_text(sentence: str, text: str) -> bool:
    norm_sent = normalize_text(sentence)
    norm_text = normalize_text(text)
    if not norm_sent:
        return False
    return norm_sent in norm_text


def _pick_core_sentence(section: StorySection, verified_text: str, *, allow_placeholder: bool) -> str:
    if vertex_configured() and not allow_placeholder:
        data = generate_json(
            f"""Pick ONE representative English sentence for this section.
Rules:
- Copy ONE complete sentence verbatim from the section text below
- Do NOT rewrite, summarize, or create a new sentence
- Choose the sentence that best helps a learner recall the whole section

Return JSON: {{"sentence": "..."}}

Section ({section.title}):
{section.text_en[:6000]}
"""
        )
        picked = str(data.get("sentence", "")).strip()
        if not _sentence_in_text(picked, section.text_en):
            raise RuntimeError(
                f"BLOCKED: Core sentence for section {section.index} is not verbatim in section text"
            )
        if not _sentence_in_text(picked, verified_text):
            raise RuntimeError(
                f"BLOCKED: Core sentence for section {section.index} is not in verified full script"
            )
        return picked

    sents = split_sentences(section.text_en)
    if not sents:
        raise RuntimeError(f"BLOCKED: section {section.index} has no sentences for core pick")
    picked = sents[len(sents) // 2]
    if not _sentence_in_text(picked, verified_text):
        raise RuntimeError(f"BLOCKED: heuristic core sentence not in verified script for section {section.index}")
    return picked


def _pick_summary_en(section: StorySection, *, allow_placeholder: bool) -> str:
    if vertex_configured() and not allow_placeholder:
        data = generate_json(
            f"""Write one short, clear English summary sentence for this section.
Rules:
- One sentence only; concise but complete
- Summarize the section content; do not quote verbatim

Return JSON: {{"summary_en": "..."}}

Section ({section.title}):
{section.text_en[:6000]}
"""
        )
        summary = str(data.get("summary_en", "")).strip()
        if not summary:
            raise RuntimeError(f"BLOCKED: empty summary for section {section.index}")
        return summary

    sents = split_sentences(section.text_en)
    return sents[0] if sents else section.text_en[:150]


def fill_section_content(
    sections: list[StorySection],
    segments: list[Segment],
    *,
    allow_placeholder: bool = False,
) -> None:
    verified_text = " ".join(s.text_en for s in segments)
    for section in sections:
        section.core_sentence_en = _pick_core_sentence(section, verified_text, allow_placeholder=allow_placeholder)
        section.summary_en = _pick_summary_en(section, allow_placeholder=allow_placeholder)


def render_core_file(
    sections: list[StorySection],
    translate_fn,
    *,
    allow_placeholder: bool = False,
) -> str:
    lines: list[str] = []
    for section in sections:
        kr = translate_fn(section.core_sentence_en, allow_placeholder=allow_placeholder)
        lines.append(f"[Sentence {section.index}]")
        lines.append(f"EN: {section.core_sentence_en}")
        lines.append(f"KR: {kr}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_summary_file(
    sections: list[StorySection],
    translate_fn,
    *,
    allow_placeholder: bool = False,
) -> str:
    lines: list[str] = []
    for section in sections:
        kr = translate_fn(section.summary_en, allow_placeholder=allow_placeholder)
        lines.append(f"[Part {section.index}]")
        lines.append(f"EN: {section.summary_en}")
        lines.append(f"KR: {kr}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def extract_core_sentences(content: str) -> list[str]:
    sentences: list[str] = []
    for line in content.splitlines():
        if line.strip().startswith("EN:"):
            sentences.append(line.split(":", 1)[1].strip())
    return sentences


def extract_summary_parts(content: str) -> list[str]:
    parts: list[str] = []
    for line in content.splitlines():
        if line.strip().startswith("EN:") and "[Part" in content:
            # Only within Part blocks — EN lines in summary file
            parts.append(line.split(":", 1)[1].strip())
    # Re-parse by blocks for accuracy
    blocks = re.split(r"\[Part\s+\d+\]", content)
    parts = []
    for block in blocks:
        for line in block.splitlines():
            if line.strip().startswith("EN:"):
                parts.append(line.split(":", 1)[1].strip())
                break
    return parts
