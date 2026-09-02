"""Restore complete sentences from fragmented YouTube auto-captions."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from automation.listening.models import Segment, ValidationResult
from automation.listening.utils import capitalize_first, normalize_text, split_sentences

RUN_ON_WARN_WORDS = 80
RUN_ON_BLOCK_WORDS = 150

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

# Multi-word proper-noun continuations — do not split before the next token.
PROPER_NOUN_CONTINUATIONS = frozenset(
    {
        "middle",
        "new",
        "world",
        "ten",
        "united",
        "san",
        "los",
        "saint",
        "st",
        "great",
        "ancient",
        "modern",
        "daily",
        "human",
        "north",
        "south",
        "east",
        "west",
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

SENTENCE_STARTERS = frozenset(
    {
        "they",
        "it",
        "this",
        "the",
        "people",
        "he",
        "she",
        "we",
        "you",
        "later",
        "then",
        "however",
        "instead",
        "after",
        "before",
        "when",
        "even",
        "many",
        "one",
        "king",
        "life",
        "faith",
        "writing",
        "trade",
        "merchants",
        "scholars",
        "families",
        "cities",
        "villages",
        "because",
        "although",
        "over",
        "long",
        "hundreds",
        "thousands",
        "suddenly",
        "despite",
        "still",
        "yet",
        "but",
        "and",
        "his",
        "her",
        "their",
        "these",
        "those",
        "everyone",
        "ordinary",
        "without",
        "looking",
        "thank",
        "trade",
        "scholars",
        "oil",
        "suddenly",
        "political",
        "families",
        "neighbors",
        "muhammad",
        "caravans",
        "ships",
        "despite",
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


def _build_asr_word_lists(asr_text: str) -> tuple[list[str], set[int]]:
    words: list[str] = []
    sentence_ends: set[int] = set()
    for sent in split_sentences(asr_text):
        tokens = re.findall(r"[A-Za-z0-9']+", sent)
        for i, tok in enumerate(tokens):
            words.append(tok)
            if i == len(tokens) - 1:
                sentence_ends.add(len(words) - 1)
    return words, sentence_ends


def _map_caption_to_asr(cap_norm: list[str], asr_norm: list[str]) -> dict[int, int]:
    if not cap_norm or not asr_norm:
        return {}
    matcher = SequenceMatcher(None, cap_norm, asr_norm, autojunk=False)
    mapping: dict[int, int] = {}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                mapping[i1 + offset] = j1 + offset
    return mapping


def _should_split_before_next(current_norm: str, next_word: str, next_norm: str) -> bool:
    if current_norm in INCOMPLETE_BEFORE_PERIOD:
        return False
    if not next_word or not next_word[0].isupper():
        return False
    if re.match(r"^(Mr|Mrs|Ms|Dr|St)\.?$", current_norm, re.IGNORECASE):
        return False
    if current_norm in PROPER_NOUN_CONTINUATIONS and next_norm in PROPER_NOUN_TOKENS:
        return False
    if next_norm in PROPER_NOUN_TOKENS and current_norm in {"called", "named", "the"}:
        return False
    if next_norm not in SENTENCE_STARTERS and next_word not in {"I"}:
        return False
    return True


def _heuristic_sentence_end_indices(words: list[str]) -> set[int]:
    if not words:
        return set()
    ends = {len(words) - 1}
    for i in range(len(words) - 1):
        clean = re.sub(r"[.!?]+$", "", words[i])
        next_word = words[i + 1]
        current_norm = normalize_text(clean)
        next_norm = normalize_text(re.sub(r"[.!?]+$", "", next_word))
        if _should_split_before_next(current_norm, next_word, next_norm):
            ends.add(i)
    return ends


def _apply_sentence_ends(words: list[str], end_indices: set[int]) -> str:
    output: list[str] = []
    for i, word in enumerate(words):
        clean = re.sub(r"[.!?]+$", "", word)
        output.append(clean + ("." if i in end_indices else ""))
    return " ".join(output)


def _split_long_sentences(text: str, end_indices: set[int], *, max_words: int = RUN_ON_WARN_WORDS) -> set[int]:
    """Insert additional boundaries inside run-on spans using local heuristics."""
    words = text.split()
    if not words:
        return end_indices

    ordered_ends = sorted(end_indices)
    new_ends = set(end_indices)
    start = 0
    for end_idx in ordered_ends:
        span_len = end_idx - start + 1
        if span_len > max_words:
            span_words = words[start : end_idx + 1]
            local = _heuristic_sentence_end_indices(span_words)
            for local_end in local:
                abs_idx = start + local_end
                if abs_idx < end_idx:
                    new_ends.add(abs_idx)
        start = end_idx + 1
    return new_ends


def _restore_boundaries_with_asr(cap_words: list[str], asr_text: str) -> str:
    asr_words, asr_ends = _build_asr_word_lists(asr_text)
    asr_norm = [normalize_text(w) for w in asr_words]
    cap_clean = [re.sub(r"[.!?]+$", "", w) for w in cap_words]
    cap_norm = [normalize_text(w) for w in cap_clean]

    mapping = _map_caption_to_asr(cap_norm, asr_norm)

    end_indices: set[int] = set()
    for ci, aj in mapping.items():
        if aj in asr_ends:
            end_indices.add(ci)
    if cap_clean:
        end_indices.add(len(cap_clean) - 1)

    # Local heuristic recovery only inside run-on spans.
    end_indices = _split_long_sentences(" ".join(cap_clean), end_indices, max_words=RUN_ON_WARN_WORDS)

    # Conservative starter-based refinement between existing boundaries.
    ordered = sorted(end_indices)
    for start, end in zip([0] + ordered, ordered):
        span_len = end - start
        if span_len >= 20:
            span_words = cap_clean[start : end + 1]
            for local_i in range(len(span_words) - 1):
                abs_i = start + local_i
                if abs_i in end_indices:
                    continue
                if _should_split_before_next(
                    cap_norm[abs_i],
                    span_words[local_i + 1],
                    cap_norm[abs_i + 1],
                ):
                    end_indices.add(abs_i)

    if len(end_indices) <= 1 and cap_clean:
        end_indices.update(_heuristic_sentence_end_indices(cap_clean))

    safe_ends: set[int] = set()
    for idx in sorted(end_indices):
        if cap_norm[idx] in INCOMPLETE_BEFORE_PERIOD and idx != len(cap_clean) - 1:
            continue
        safe_ends.add(idx)
    if cap_clean:
        safe_ends.add(len(cap_clean) - 1)

    return _apply_sentence_ends(cap_clean, safe_ends)


def _restore_boundaries_heuristic(text: str) -> str:
    words = text.split()
    if not words:
        return text
    end_indices = _heuristic_sentence_end_indices(words)
    end_indices = _split_long_sentences(text, end_indices)
    return _apply_sentence_ends(words, end_indices)


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


def validate_run_on_sentences(text: str, *, block_words: int = RUN_ON_BLOCK_WORDS) -> ValidationResult:
    run_ons: list[str] = []
    for sent in split_sentences(text):
        wc = len(word_sequence(sent))
        if wc >= block_words:
            run_ons.append(f"{wc} words: {sent[:100]}...")
    if run_ons:
        return ValidationResult(False, f"Run-on sentence detected ({run_ons[0]})")
    return ValidationResult(True, "OK")


def validate_sentence_boundaries(text: str) -> ValidationResult:
    artificial = validate_no_artificial_sentence_breaks(text)
    if not artificial.ok:
        return artificial
    run_on = validate_run_on_sentences(text)
    if not run_on.ok:
        return run_on
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
