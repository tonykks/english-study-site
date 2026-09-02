"""Restore complete sentences from fragmented YouTube auto-captions."""

from __future__ import annotations

import re

from automation.listening.models import Segment, ValidationResult
from automation.listening.utils import capitalize_first, normalize_text, split_sentences

# Words that cannot grammatically end a sentence before a continuing phrase.
INCOMPLETE_BEFORE_PERIOD = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "for",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "into",
        "onto",
        "upon",
        "about",
        "and",
        "or",
        "but",
        "so",
        "yet",
        "nor",
        "as",
        "if",
        "than",
        "that",
        "which",
        "who",
        "whom",
        "whose",
        "where",
        "when",
        "while",
        "because",
        "although",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "my",
        "your",
        "his",
        "her",
        "its",
        "our",
        "their",
        "this",
        "these",
        "those",
        "one",
        "first",
        "second",
        "third",
        "became",
        "called",
        "named",
        "become",
        "becomes",
        "very",
        "more",
        "most",
        "not",
        "no",
        "also",
        "just",
        "only",
        "even",
        "still",
        "already",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "over",
        "without",
        "within",
        "against",
        "among",
        "toward",
        "towards",
        "until",
        "unless",
        "since",
        "though",
        "although",
        "whether",
        "how",
        "what",
        "when",
        "where",
        "why",
        "all",
        "half",
    }
)

# Keep capitalization when the next token is likely a proper noun / acronym.
PROPER_NOUN_TOKENS = frozenset(
    {
        "i",
        "english",
        "mesopotamia",
        "sumerians",
        "sumerian",
        "babylon",
        "babylonian",
        "hammurabi",
        "egypt",
        "egyptian",
        "persian",
        "islam",
        "islamic",
        "muslim",
        "christianity",
        "judaism",
        "middle",
        "east",
        "tigris",
        "euphrates",
        "cuneiform",
        "ziggurats",
        "youtube",
        "europe",
        "africa",
        "asia",
        "arab",
        "arabic",
        "turkey",
        "iran",
        "iraq",
        "syria",
        "israel",
        "koran",
        "quran",
        "prophet",
        "muhammad",
        "christian",
        "jewish",
        "pharaohs",
        "pharaoh",
    }
)

_INCOMPLETE_PATTERN = "|".join(re.escape(w) for w in sorted(INCOMPLETE_BEFORE_PERIOD, key=len, reverse=True))
ARTIFICIAL_BREAK_RE = re.compile(
    rf"\b({_INCOMPLETE_PATTERN})\.\s+([A-Za-z][A-Za-z'-]*)",
    re.IGNORECASE,
)


def normalize_caption_fragment(text: str) -> str:
    """Whitespace normalization only — never append sentence-ending punctuation."""
    return re.sub(r"\s+", " ", (text or "").strip())


def word_sequence(text: str) -> list[str]:
    return normalize_text(text).split()


def words_unchanged(before: str, after: str) -> bool:
    return word_sequence(before) == word_sequence(after)


def join_caption_fragments(segments: list[Segment]) -> str:
    parts: list[str] = []
    for seg in segments:
        text = normalize_caption_fragment(seg.text_en)
        text = re.sub(r"[.!?]+$", "", text).strip()
        if text:
            parts.append(text)
    return " ".join(parts)


def _lower_unless_proper(word: str) -> str:
    if not word:
        return word
    if word.isupper() and len(word) <= 4:
        return word
    lower = word.lower()
    if lower in PROPER_NOUN_TOKENS:
        return word[0].upper() + word[1:] if word[0].islower() else word
    if word[0].isupper() and lower in PROPER_NOUN_TOKENS:
        return word
    return lower


def fix_artificial_period_breaks(text: str) -> str:
    """Merge caption fragments split by artificial mid-phrase periods."""
    result = text
    while True:
        def _repl(match: re.Match[str]) -> str:
            before = match.group(1)
            after = match.group(2)
            return f"{before} {_lower_unless_proper(after)}"

        updated = ARTIFICIAL_BREAK_RE.sub(_repl, result)
        if updated == result:
            break
        result = updated
    return re.sub(r"\s+", " ", result).strip()


def _asr_sentence_end_indices(asr_text: str) -> list[int]:
    """Return ASR word indices (0-based) where a sentence ends."""
    ends: list[int] = []
    idx = 0
    for sent in split_sentences(asr_text):
        words = re.findall(r"[A-Za-z0-9']+", sent)
        if not words:
            continue
        idx += len(words)
        ends.append(idx - 1)
    return ends


def _restore_boundaries_with_asr(cap_words: list[str], asr_text: str) -> str:
    asr_words: list[str] = []
    asr_ends: set[int] = set()
    for sent in split_sentences(asr_text):
        tokens = re.findall(r"[A-Za-z0-9']+", sent)
        for i, tok in enumerate(tokens):
            asr_words.append(tok)
            if i == len(tokens) - 1:
                asr_ends.add(len(asr_words) - 1)

    asr_norm = [normalize_text(w) for w in asr_words]
    output: list[str] = []
    ai = 0
    for cw in cap_words:
        cnorm = normalize_text(re.sub(r"[.!?]+$", "", cw))
        while ai < len(asr_norm) and asr_norm[ai] != cnorm:
            ai += 1
        ends_sentence = ai in asr_ends if ai < len(asr_words) else False
        clean = re.sub(r"[.!?]+$", "", cw)
        if ai < len(asr_norm):
            ai += 1
        output.append(clean + ("." if ends_sentence else ""))
    return " ".join(output)


def _restore_boundaries_heuristic(text: str) -> str:
    words = text.split()
    if not words:
        return text
    output: list[str] = []
    for i, word in enumerate(words):
        clean = re.sub(r"[.!?]+$", "", word)
        is_last = i == len(words) - 1
        next_word = words[i + 1] if not is_last else ""
        ends = is_last
        if not is_last:
            norm = normalize_text(clean)
            next_norm = normalize_text(next_word)
            if norm in INCOMPLETE_BEFORE_PERIOD:
                ends = False
            elif next_norm in PROPER_NOUN_TOKENS and norm in {"called", "named", "the"}:
                ends = False
            elif re.match(r"^(Mr|Mrs|Ms|Dr|St)\.?$", clean):
                ends = False
        output.append(clean + ("." if ends else ""))
    return " ".join(output)


def restore_sentence_boundaries(text: str, asr_text: str | None = None) -> str:
    cap_words = text.split()
    if not cap_words:
        return text
    if asr_text and normalize_text(asr_text):
        try:
            return _restore_boundaries_with_asr(cap_words, asr_text)
        except Exception:
            pass
    return _restore_boundaries_heuristic(text)


def restore_caption_text(segments: list[Segment], asr_segments: list[Segment] | None = None) -> str:
    joined = join_caption_fragments(segments)
    fixed = fix_artificial_period_breaks(joined)
    asr_text = " ".join(s.text_en for s in asr_segments) if asr_segments else None
    restored = restore_sentence_boundaries(fixed, asr_text)
    restored = fix_artificial_period_breaks(restored)
    if not words_unchanged(joined, restored):
        raise RuntimeError("BLOCKED: caption restoration altered word content or order")
    return restored


def _sentence_time_ranges(
    raw_segments: list[Segment],
    sentences: list[str],
) -> list[tuple[float, float]]:
    word_times: list[tuple[str, float, float]] = []
    for seg in raw_segments:
        words = normalize_caption_fragment(seg.text_en).split()
        if not words:
            continue
        duration = max(seg.end - seg.start, 0.01)
        step = duration / len(words)
        for i, word in enumerate(words):
            word_times.append((normalize_text(word), seg.start + i * step, seg.start + (i + 1) * step))

    ranges: list[tuple[float, float]] = []
    cursor = 0
    for sentence in sentences:
        sent_words = word_sequence(sentence)
        if not sent_words:
            continue
        start_idx = cursor
        end_idx = min(len(word_times), cursor + len(sent_words))
        if start_idx >= len(word_times):
            ranges.append((raw_segments[-1].start, raw_segments[-1].end))
            cursor = end_idx
            continue
        start_t = word_times[start_idx][1]
        end_t = word_times[end_idx - 1][2] if end_idx > start_idx else word_times[start_idx][2]
        ranges.append((start_t, end_t))
        cursor = end_idx
    return ranges


def restore_caption_segments(
    segments: list[Segment],
    asr_segments: list[Segment] | None = None,
) -> list[Segment]:
    if not segments:
        return segments

    restored_text = restore_caption_text(segments, asr_segments)
    sentences = [capitalize_first(s.strip()) for s in split_sentences(restored_text) if s.strip()]
    if not sentences:
        return segments

    times = _sentence_time_ranges(segments, sentences)
    restored: list[Segment] = []
    for i, (sentence, (start, end)) in enumerate(zip(sentences, times), start=1):
        restored.append(
            Segment(
                segment_id=f"cap_{i:05d}",
                start=start,
                end=max(end, start + 0.01),
                text_en=sentence,
                source="caption_restored",
            )
        )
    if len(times) < len(sentences):
        for j, sentence in enumerate(sentences[len(times) :], start=len(times) + 1):
            prev_end = restored[-1].end if restored else segments[-1].end
            restored.append(
                Segment(
                    segment_id=f"cap_{j:05d}",
                    start=prev_end,
                    end=prev_end + 0.01,
                    text_en=sentence,
                    source="caption_restored",
                )
            )
    if restored:
        restored[0].start = segments[0].start
        restored[-1].end = segments[-1].end
        for i in range(len(restored) - 1):
            boundary = (restored[i].end + restored[i + 1].start) / 2.0
            restored[i].end = boundary
            restored[i + 1].start = boundary
    return restored


def validate_no_artificial_sentence_breaks(text: str) -> ValidationResult:
    matches = list(ARTIFICIAL_BREAK_RE.finditer(text))
    if matches:
        sample = matches[0].group(0)
        return ValidationResult(False, f"Artificial sentence break detected: {sample}")
    for sent in split_sentences(text):
        if ARTIFICIAL_BREAK_RE.search(sent):
            return ValidationResult(False, f"Artificial sentence break in sentence: {sent[:80]}")
    return ValidationResult(True, "OK")


def is_complete_sentence(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    if text[-1] not in ".!?":
        return False
    if ARTIFICIAL_BREAK_RE.search(text):
        return False
    words = word_sequence(text)
    return len(words) >= 4
