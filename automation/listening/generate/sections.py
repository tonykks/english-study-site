from __future__ import annotations

import json
import logging
import re

from automation.listening.config import (
    LEVEL_GENERATION_GUIDANCE,
    SECTION_CHUNK_MAX_SEGMENTS,
    SECTION_CHUNK_OVERLAP_SEGMENTS,
    SECTION_CROSS_CHUNK_BOUNDARY_EPS_SEC,
    SECTION_CROSS_CHUNK_OVERLAP_MIN,
)
from automation.listening.models import Segment, StorySection
from automation.listening.script.caption_restore import is_complete_sentence
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


def chunk_segments_for_inference(
    segments: list[Segment],
    *,
    max_segments: int = SECTION_CHUNK_MAX_SEGMENTS,
    overlap: int = SECTION_CHUNK_OVERLAP_SEGMENTS,
) -> list[list[Segment]]:
    if not segments:
        return []
    if len(segments) <= max_segments:
        return [segments]

    chunks: list[list[Segment]] = []
    start_idx = 0
    while start_idx < len(segments):
        end_idx = min(start_idx + max_segments, len(segments))
        chunks.append(segments[start_idx:end_idx])
        if end_idx >= len(segments):
            break
        start_idx = max(0, end_idx - overlap)
    return chunks


def _candidate_span(cand: dict) -> tuple[float, float]:
    start = float(cand.get("start", 0.0))
    end = float(cand.get("end", start))
    if end <= start:
        end = start + 1.0
    return start, end


def _overlap_ratio(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    overlap = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    if overlap <= 0.0:
        return 0.0
    min_span = min(a_end - a_start, b_end - b_start)
    return overlap / min_span if min_span > 0.0 else 0.0


def _normalize_candidate(cand: dict) -> dict:
    start, end = _candidate_span(cand)
    normalized = {
        "title": str(cand.get("title") or "Section").strip(),
        "start": start,
        "end": end,
    }
    if "source_chunk" in cand:
        normalized["source_chunk"] = cand["source_chunk"]
    return normalized


def _should_merge_cross_chunk(existing: dict, cand: dict) -> bool:
    """Merge only when different chunks produced overlapping duplicate section candidates."""
    chunk_a = existing.get("source_chunk")
    chunk_b = cand.get("source_chunk")
    if chunk_a is None or chunk_b is None:
        return False
    if chunk_a == chunk_b:
        return False

    a_start, a_end = _candidate_span(existing)
    b_start, b_end = _candidate_span(cand)
    if _overlap_ratio(a_start, a_end, b_start, b_end) >= SECTION_CROSS_CHUNK_OVERLAP_MIN:
        return True

    return (
        abs(a_start - b_start) <= SECTION_CROSS_CHUNK_BOUNDARY_EPS_SEC
        and abs(a_end - b_end) <= SECTION_CROSS_CHUNK_BOUNDARY_EPS_SEC
    )


def merge_section_candidates(candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []

    normalized = [_normalize_candidate(c) for c in candidates]
    sorted_cands = sorted(normalized, key=lambda c: (c["start"], c["end"]))
    merged: list[dict] = []

    for cand in sorted_cands:
        merge_idx: int | None = None
        best_ratio = 0.0
        for i, existing in enumerate(merged):
            if not _should_merge_cross_chunk(existing, cand):
                continue
            a_start, a_end = _candidate_span(existing)
            b_start, b_end = _candidate_span(cand)
            ratio = _overlap_ratio(a_start, a_end, b_start, b_end)
            if ratio > best_ratio:
                best_ratio = ratio
                merge_idx = i

        if merge_idx is None:
            merged.append(dict(cand))
            continue

        target = merged[merge_idx]
        cand_start, cand_end = _candidate_span(cand)
        target["start"] = min(float(target["start"]), cand_start)
        target["end"] = max(float(target["end"]), cand_end)
        if len(cand["title"]) > len(target["title"]):
            target["title"] = cand["title"]

    merged.sort(key=lambda c: (c["start"], c["end"]))
    return merged


def _candidates_to_sections(candidates: list[dict], segments: list[Segment]) -> list[StorySection]:
    sections: list[StorySection] = []
    for i, cand in enumerate(candidates, start=1):
        start = float(cand.get("start", 0.0))
        end = float(cand.get("end", start + 1.0))
        segs = _segments_in_range(segments, start, end)
        text = _section_text(segs)
        if not text:
            continue
        sections.append(
            StorySection(
                index=len(sections) + 1,
                title=str(cand.get("title") or f"Section {i}"),
                text_en=text,
                start=start,
                end=end,
            )
        )
    if not sections:
        raise RuntimeError("BLOCKED: section candidates produced no usable sections")
    return sections


def _infer_sections_vertex_single(segments: list[Segment]) -> list[StorySection]:
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
    return _candidates_to_sections(raw_sections, segments)


def _infer_chunk_section_candidates(
    chunk_segments: list[Segment],
    chunk_index: int,
    total_chunks: int,
) -> list[dict]:
    chunk_start = chunk_segments[0].start
    chunk_end = chunk_segments[-1].end
    lines = [f"[{s.start:.1f}-{s.end:.1f}] {s.text_en}" for s in chunk_segments]
    data = generate_json(
        f"""This is part {chunk_index + 1} of {total_chunks} from a longer English listening video.
Time range: {chunk_start:.1f}s to {chunk_end:.1f}s (absolute timestamps).

Identify natural story/topic section boundaries within this excerpt.
Rules:
- Use absolute timestamps in seconds from the video start
- Base boundaries on plot events, topic shifts, or logical transitions
- Do NOT merge or split sections to hit a target count
- At chunk edges, add a boundary only when there is a clear transition (avoid artificial edge splits)

Return JSON:
{{"sections": [{{"title": "...", "start": 0.0, "end": 30.0}}, ...]}}

Transcript excerpt ({len(chunk_segments)} segments):
{chr(10).join(lines)}
"""
    )
    raw = data.get("sections") or []
    if not raw:
        raise RuntimeError(f"BLOCKED: Vertex chunk {chunk_index + 1}/{total_chunks} returned no sections")
    return raw


def _consolidate_section_boundaries_vertex(segments: list[Segment], candidates: list[dict]) -> list[dict]:
    if len(candidates) <= 1:
        return candidates

    total_end = segments[-1].end
    summary = "\n".join(
        f"- {c['title']}: {float(c['start']):.1f}s – {float(c['end']):.1f}s" for c in candidates
    )
    data = generate_json(
        f"""These section boundary candidates were produced by processing a {total_end:.0f}s video in chunks.
Merge ONLY boundaries that incorrectly split one natural section across chunk edges.
Do NOT merge distinct story sections to reduce count.
Do NOT split sections to hit a target count.
Return finalized sections covering 0 to {total_end:.1f}s without gaps.

Candidates:
{summary}

Return JSON:
{{"sections": [{{"title": "...", "start": 0.0, "end": 30.0}}, ...]}}
"""
    )
    finalized = data.get("sections") or []
    if not finalized:
        logger.warning("Vertex consolidation returned empty; using merged chunk candidates")
        return candidates
    return finalized


def _infer_sections_vertex_chunked(segments: list[Segment]) -> list[StorySection]:
    chunks = chunk_segments_for_inference(segments)
    logger.info("Section inference: processing %d segments in %d Vertex chunks", len(segments), len(chunks))

    all_candidates: list[dict] = []
    for i, chunk in enumerate(chunks):
        raw_candidates = _infer_chunk_section_candidates(chunk, i, len(chunks))
        for cand in raw_candidates:
            tagged = dict(cand)
            tagged["source_chunk"] = i
            all_candidates.append(tagged)
        logger.info("Chunk %d/%d yielded %d section candidates", i + 1, len(chunks), len(raw_candidates))

    merged = merge_section_candidates(all_candidates)
    if len(chunks) > 1:
        finalized = _consolidate_section_boundaries_vertex(segments, merged)
    else:
        finalized = merged

    return _candidates_to_sections(finalized, segments)


def _infer_sections_vertex(segments: list[Segment]) -> list[StorySection]:
    if len(segments) <= SECTION_CHUNK_MAX_SEGMENTS:
        return _infer_sections_vertex_single(segments)
    return _infer_sections_vertex_chunked(segments)


def _heuristic_sections(segments: list[Segment]) -> list[StorySection]:
    """Placeholder sections for fixture/offline tests only."""
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

        if not vertex_configured():
            raise RuntimeError("BLOCKED: Vertex AI (ADC) required for section inference")
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


def _level_guidance(level: int) -> str:
    return LEVEL_GENERATION_GUIDANCE.get(level, LEVEL_GENERATION_GUIDANCE[2])


def _pick_core_sentences_batch(
    sections: list[StorySection],
    verified_text: str,
    *,
    allow_placeholder: bool,
) -> dict[int, str]:
    if not (vertex_configured() and not allow_placeholder):
        picked: dict[int, str] = {}
        for section in sections:
            picked[section.index] = _pick_core_sentence(section, verified_text, allow_placeholder=allow_placeholder)
        return picked

    payload = [
        {
            "index": section.index,
            "title": section.title,
            "text": section.text_en[:4000],
        }
        for section in sections
    ]
    data = generate_json(
        f"""Pick ONE representative English sentence per section.
Rules:
- For each section, copy ONE complete sentence verbatim from that section's text
- Do NOT rewrite, summarize, or create a new sentence
- Choose the sentence that best helps a learner recall the whole section

Return JSON:
{{"sections": [{{"index": 1, "sentence": "..."}}, ...]}}

Sections:
{json.dumps(payload, ensure_ascii=False)}
"""
    )
    rows = data.get("sections") or []
    if len(rows) != len(sections):
        raise RuntimeError(
            f"BLOCKED: Core batch returned {len(rows)} sentences, expected {len(sections)}"
        )
    by_index: dict[int, str] = {}
    for row in rows:
        idx = int(row.get("index", 0))
        picked = str(row.get("sentence", "")).strip()
        section = next((s for s in sections if s.index == idx), None)
        if section is None:
            raise RuntimeError(f"BLOCKED: Core batch returned unknown section index {idx}")
        if not _sentence_in_text(picked, section.text_en):
            raise RuntimeError(f"BLOCKED: Core sentence for section {idx} is not verbatim in section text")
        if not _sentence_in_text(picked, verified_text):
            raise RuntimeError(f"BLOCKED: Core sentence for section {idx} is not in verified full script")
        if not is_complete_sentence(picked):
            raise RuntimeError(f"BLOCKED: Core sentence for section {idx} is not a complete sentence")
        by_index[idx] = picked
    if len(by_index) != len(sections):
        raise RuntimeError("BLOCKED: Core batch missing section indices")
    return by_index


def _pick_summaries_batch(
    sections: list[StorySection],
    level: int,
    *,
    allow_placeholder: bool,
) -> dict[int, str]:
    if not (vertex_configured() and not allow_placeholder):
        return {
            section.index: _pick_summary_en(section, level, allow_placeholder=allow_placeholder)
            for section in sections
        }

    level_hint = _level_guidance(level)
    payload = [
        {"index": section.index, "title": section.title, "text": section.text_en[:4000]}
        for section in sections
    ]
    data = generate_json(
        f"""Write one short, clear English summary sentence per section for Level {level} learners.
{level_hint}
Rules:
- One sentence per section; concise but complete
- Summarize the section content; do not quote verbatim

Return JSON:
{{"sections": [{{"index": 1, "summary_en": "..."}}, ...]}}

Sections:
{json.dumps(payload, ensure_ascii=False)}
"""
    )
    rows = data.get("sections") or []
    if len(rows) != len(sections):
        raise RuntimeError(
            f"BLOCKED: Summary batch returned {len(rows)} items, expected {len(sections)}"
        )
    by_index: dict[int, str] = {}
    for row in rows:
        idx = int(row.get("index", 0))
        summary = str(row.get("summary_en", "")).strip()
        if not summary:
            raise RuntimeError(f"BLOCKED: empty summary for section {idx}")
        if idx not in {s.index for s in sections}:
            raise RuntimeError(f"BLOCKED: Summary batch returned unknown section index {idx}")
        by_index[idx] = summary
    if len(by_index) != len(sections):
        raise RuntimeError("BLOCKED: Summary batch missing section indices")
    return by_index


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
        if not is_complete_sentence(picked):
            raise RuntimeError(
                f"BLOCKED: Core sentence for section {section.index} is not a complete sentence"
            )
        return picked

    sents = split_sentences(section.text_en)
    if not sents:
        raise RuntimeError(f"BLOCKED: section {section.index} has no sentences for core pick")
    picked = sents[len(sents) // 2]
    if not _sentence_in_text(picked, verified_text):
        raise RuntimeError(f"BLOCKED: heuristic core sentence not in verified script for section {section.index}")
    return picked


def _pick_summary_en(section: StorySection, level: int, *, allow_placeholder: bool) -> str:
    level_hint = _level_guidance(level)
    if vertex_configured() and not allow_placeholder:
        data = generate_json(
            f"""Write one short, clear English summary sentence for Level {level} learners.
{level_hint}
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
    level: int = 1,
    allow_placeholder: bool = False,
) -> None:
    verified_text = " ".join(s.text_en for s in segments)
    core_by_index = _pick_core_sentences_batch(sections, verified_text, allow_placeholder=allow_placeholder)
    summary_by_index = _pick_summaries_batch(sections, level, allow_placeholder=allow_placeholder)
    for section in sections:
        section.core_sentence_en = core_by_index[section.index]
        section.summary_en = summary_by_index[section.index]


def render_core_file(
    sections: list[StorySection],
    translate_batch_fn,
    *,
    allow_placeholder: bool = False,
) -> str:
    items = [(f"s{section.index}", section.core_sentence_en) for section in sections]
    kr_map = translate_batch_fn(items, allow_placeholder=allow_placeholder)
    lines: list[str] = []
    for section in sections:
        lines.append(f"[Sentence {section.index}]")
        lines.append(f"EN: {section.core_sentence_en}")
        lines.append(f"KR: {kr_map[f's{section.index}']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_summary_file(
    sections: list[StorySection],
    translate_batch_fn,
    *,
    allow_placeholder: bool = False,
) -> str:
    items = [(f"p{section.index}", section.summary_en) for section in sections]
    kr_map = translate_batch_fn(items, allow_placeholder=allow_placeholder)
    lines: list[str] = []
    for section in sections:
        lines.append(f"[Part {section.index}]")
        lines.append(f"EN: {section.summary_en}")
        lines.append(f"KR: {kr_map[f'p{section.index}']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def extract_core_sentences(content: str) -> list[str]:
    sentences: list[str] = []
    for line in content.splitlines():
        if line.strip().startswith("EN:"):
            sentences.append(line.split(":", 1)[1].strip())
    return sentences


def extract_summary_parts(content: str) -> list[str]:
    blocks = re.split(r"\[Part\s+\d+\]", content)
    parts: list[str] = []
    for block in blocks:
        for line in block.splitlines():
            if line.strip().startswith("EN:"):
                parts.append(line.split(":", 1)[1].strip())
                break
    return parts
