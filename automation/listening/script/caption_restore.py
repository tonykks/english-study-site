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
        "like",
        "including",
        "unlike",
        "except",
        "plus",
        "versus",
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
        "wars",
        "artists",
        "farmers",
        "doctors",
        "music",
        "share",
        "battles",
        "armies",
        "children",
        "neighbors",
        "technology",
        "culture",
        "religion",
        "knowledge",
        "markets",
        "history",
        "women",
        "men",
    }
)

# Adjective/adverb/noun endings that complete a clause before a new capitalized subject.
TERMINAL_BEFORE_CAPITAL = frozenset(
    {
        "easy",
        "hard",
        "difficult",
        "mixed",
        "more",
        "most",
        "other",
        "forever",
        "deserts",
        "years",
        "celebrations",
        "world",
        "time",
        "region",
        "history",
        "valuable",
        "poor",
        "busy",
        "broken",
        "damaged",
        "united",
        "resilient",
        "together",
        "away",
        "safely",
        "quickly",
        "rapidly",
        "alive",
        "full",
        "century",
        "communities",
        "homes",
        "cities",
        "schools",
        "hospitals",
        "families",
        "people",
        "life",
        "faith",
        "trade",
        "learning",
        "knowledge",
        "culture",
        "conflict",
        "hope",
        "future",
        "past",
        "present",
        "story",
        "stories",
        "generation",
        "generations",
    }
)

_INCOMPLETE_PATTERN = "|".join(re.escape(w) for w in sorted(INCOMPLETE_BEFORE_PERIOD, key=len, reverse=True))
ARTIFICIAL_BREAK_RE = re.compile(
    rf"\b({_INCOMPLETE_PATTERN})\.\s+([A-Za-z][A-Za-z'-]*)",
    re.IGNORECASE,
)
PUNCT_ANOMALY_RE = re.compile(r"[,;:]+\s*\.|\.\s*[,;:]+")


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
            if _is_kept_boundary(before, after):
                return match.group(0)
            return f"{before} {_lower_unless_proper(after)}"

        updated = ARTIFICIAL_BREAK_RE.sub(_repl, result)
        if updated == result:
            break
        result = updated
    return re.sub(r"\s+", " ", result).strip()


def tokenize_words_with_punct(text: str) -> list[tuple[str, str]]:
    """Return (word, trailing punctuation) pairs from ASR or caption text."""
    return [(m.group(1), m.group(2)) for m in re.finditer(r"([A-Za-z0-9']+)([,;:?!]*)", text or "")]


def _internal_punct(punct: str) -> str:
    if "," in (punct or ""):
        return ","
    if ";" in (punct or ""):
        return ";"
    if ":" in (punct or ""):
        return ":"
    return ""


def _end_mark_from_punct(punct: str) -> str:
    if "!" in (punct or ""):
        return "!"
    if "?" in (punct or ""):
        return "?"
    return ""


def _build_asr_word_lists(asr_text: str) -> tuple[list[str], set[int], list[str]]:
    words: list[str] = []
    sentence_ends: set[int] = set()
    puncts: list[str] = []
    for sent in split_sentences(asr_text):
        pairs = tokenize_words_with_punct(sent)
        for i, (tok, punct) in enumerate(pairs):
            words.append(tok)
            puncts.append(punct)
            if i == len(pairs) - 1:
                sentence_ends.add(len(words) - 1)
    return words, sentence_ends, puncts


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


def _should_split_before_next(
    current_norm: str,
    next_word: str,
    next_norm: str,
    *,
    current_raw: str = "",
    prev_norm: str = "",
) -> bool:
    if current_norm in INCOMPLETE_BEFORE_PERIOD:
        # "more/most/other" can end a clause before a new capitalized starter.
        if not (
            current_norm in TERMINAL_BEFORE_CAPITAL
            and (next_norm in SENTENCE_STARTERS or next_word == "I")
        ):
            return False
    if not next_word or not next_word[0].isupper():
        return False
    if current_raw and current_raw[0].isupper() and next_word[0].isupper():
        return False
    if re.match(r"^(Mr|Mrs|Ms|Dr|St)\.?$", current_norm, re.IGNORECASE):
        return False
    if current_norm in PROPER_NOUN_CONTINUATIONS and next_norm in PROPER_NOUN_TOKENS:
        return False
    if next_norm in PROPER_NOUN_TOKENS:
        return False
    # "by/at the time Name..." is a clause opener, not a sentence end.
    if current_norm == "time" and prev_norm == "the":
        return False
    if next_norm in SENTENCE_STARTERS or next_word == "I":
        return True
    if current_norm in TERMINAL_BEFORE_CAPITAL:
        return True
    return False


def _heuristic_sentence_end_indices(words: list[str]) -> set[int]:
    if not words:
        return set()
    ends = {len(words) - 1}
    for i in range(len(words) - 1):
        clean = re.sub(r"[.!?]+$", "", words[i])
        next_word = words[i + 1]
        current_norm = normalize_text(clean)
        next_norm = normalize_text(re.sub(r"[.!?]+$", "", next_word))
        prev_norm = normalize_text(re.sub(r"[.!?]+$", "", words[i - 1])) if i > 0 else ""
        if _should_split_before_next(
            current_norm,
            next_word,
            next_norm,
            current_raw=clean,
            prev_norm=prev_norm,
        ):
            ends.add(i)
    return ends


def _apply_sentence_ends(
    words: list[str],
    end_indices: set[int],
    end_marks: dict[int, str] | None = None,
) -> str:
    """Keep internal ,:; from evidence; attach . ? ! only at sentence ends."""
    marks = end_marks or {}
    output: list[str] = []
    for i, word in enumerate(words):
        if i in end_indices:
            core = re.sub(r"[,;:.!?]+$", "", word)
            mark = marks.get(i, ".")
            if mark not in ".!?":
                mark = "."
            output.append(core + mark)
        else:
            core = re.sub(r"[.!?]+$", "", word)
            output.append(core)
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
    asr_words, asr_ends, asr_puncts = _build_asr_word_lists(asr_text)
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

    # Conservative starter/terminal refinement between existing boundaries, including short spans.
    ordered = sorted(end_indices)
    starts = [0] + [e + 1 for e in ordered[:-1]] if ordered else [0]
    for start, end in zip(starts, ordered or []):
        span_len = end - start + 1
        if span_len < 4:
            continue
        span_words = cap_clean[start : end + 1]
        for local_i in range(len(span_words) - 1):
            abs_i = start + local_i
            if abs_i in end_indices:
                continue
            if _should_split_before_next(
                cap_norm[abs_i],
                span_words[local_i + 1],
                cap_norm[abs_i + 1],
                current_raw=span_words[local_i],
                prev_norm=cap_norm[abs_i - 1] if abs_i > 0 else "",
            ):
                end_indices.add(abs_i)

    end_indices.update(_heuristic_sentence_end_indices(cap_clean))

    safe_ends: set[int] = set()
    for idx in sorted(end_indices):
        if cap_norm[idx] == "time" and idx > 0 and cap_norm[idx - 1] == "the":
            continue
        if cap_norm[idx] in INCOMPLETE_BEFORE_PERIOD and idx != len(cap_clean) - 1:
            next_raw = cap_clean[idx + 1] if idx + 1 < len(cap_clean) else ""
            next_norm = cap_norm[idx + 1] if idx + 1 < len(cap_norm) else ""
            if not _should_split_before_next(
                cap_norm[idx],
                next_raw,
                next_norm,
                current_raw=cap_clean[idx],
                prev_norm=cap_norm[idx - 1] if idx > 0 else "",
            ):
                continue
        safe_ends.add(idx)
    if cap_clean:
        safe_ends.add(len(cap_clean) - 1)

    decorated: list[str] = []
    end_marks: dict[int, str] = {}
    for i, word in enumerate(cap_clean):
        base = re.sub(r"[,;:?!]+$", "", word)
        extra = _internal_punct(word)
        aj = mapping.get(i)
        if aj is not None and aj < len(asr_puncts):
            if not extra:
                extra = _internal_punct(asr_puncts[aj])
            mark = _end_mark_from_punct(asr_puncts[aj])
            if mark:
                end_marks[i] = mark
        decorated.append(base + extra)

    return _apply_sentence_ends(decorated, safe_ends, end_marks)


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
    restored = fix_punctuation_anomalies(restored)
    if not words_unchanged(joined, restored):
        raise RuntimeError("BLOCKED: caption restoration altered word content or order")
    return restored


def _sentence_time_ranges(
    raw_segments: list[Segment],
    sentences: list[str],
) -> list[tuple[float, float]]:
    """Map restored sentences onto caption word order with monotonic timestamps.

    YouTube auto-captions often overlap; raw fragment times can go backwards in
    spoken-word order. Clamp each word so start/end never move earlier than the
    previous word (preserves caption word order; does not sort segments).
    """
    word_times: list[tuple[str, float, float]] = []
    prev_end = float(raw_segments[0].start) if raw_segments else 0.0
    for seg in raw_segments:
        words = normalize_caption_fragment(seg.text_en).split()
        if not words:
            continue
        duration = max(seg.end - seg.start, 0.01)
        step = duration / len(words)
        for i, word in enumerate(words):
            raw_start = seg.start + i * step
            raw_end = seg.start + (i + 1) * step
            start = max(raw_start, prev_end)
            end = max(raw_end, start + 0.001)
            word_times.append((normalize_text(word), start, end))
            prev_end = end

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
        if end_t <= start_t:
            end_t = start_t + 0.01
        ranges.append((start_t, end_t))
        cursor = end_idx
    return ranges


def _enforce_monotonic_segment_times(
    restored: list[Segment],
    *,
    first_start: float,
    last_end: float,
) -> None:
    """Keep caption word order; force non-decreasing start/end times in place."""
    if not restored:
        return
    restored[0].start = first_start
    cursor = first_start
    for i, seg in enumerate(restored):
        start = max(seg.start, cursor)
        end = max(seg.end, start + 0.01)
        if i + 1 < len(restored):
            # Abut neighbors to avoid validate_segments order violations.
            next_raw = restored[i + 1].start
            if next_raw <= start:
                end = start + 0.01
                restored[i + 1].start = end
            elif next_raw < end:
                mid = (start + next_raw) / 2.0 if next_raw > start else start + 0.01
                end = mid
                restored[i + 1].start = mid
        seg.start = start
        seg.end = end
        cursor = end
    restored[-1].end = max(restored[-1].end, last_end)
    if restored[-1].end <= restored[-1].start:
        restored[-1].end = restored[-1].start + 0.01


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
        _enforce_monotonic_segment_times(
            restored,
            first_start=segments[0].start,
            last_end=segments[-1].end,
        )
    return restored


def _is_kept_boundary(before: str, after: str) -> bool:
    return before.lower() in TERMINAL_BEFORE_CAPITAL and after.lower() in SENTENCE_STARTERS


def validate_no_artificial_sentence_breaks(text: str) -> ValidationResult:
    for match in ARTIFICIAL_BREAK_RE.finditer(text or ""):
        if _is_kept_boundary(match.group(1), match.group(2)):
            continue
        return ValidationResult(False, f"Artificial sentence break detected: {match.group(0)}")
    for sent in split_sentences(text):
        for match in ARTIFICIAL_BREAK_RE.finditer(sent):
            if _is_kept_boundary(match.group(1), match.group(2)):
                continue
            return ValidationResult(False, f"Artificial sentence break in sentence: {sent[:80]}")
    return ValidationResult(True, "OK")


def validate_punctuation_anomalies(text: str) -> ValidationResult:
    match = PUNCT_ANOMALY_RE.search(text or "")
    if match:
        return ValidationResult(False, f"Punctuation anomaly detected: {match.group(0)!r}")
    return ValidationResult(True, "OK")


def find_missing_short_boundaries(text: str) -> list[str]:
    """Detect capitalized clause starts that lack a preceding sentence-ending mark."""
    hits: list[str] = []
    words = (text or "").split()
    for i in range(len(words) - 1):
        if re.search(r"[.!?]$", words[i]):
            continue
        clean = re.sub(r"[,:;]+$", "", re.sub(r"[.!?]+$", "", words[i]))
        next_word = words[i + 1]
        next_norm = normalize_text(re.sub(r"[.!?]+$", "", next_word))
        current_norm = normalize_text(clean)
        prev_norm = normalize_text(re.sub(r"[,:;]+$", "", re.sub(r"[.!?]+$", "", words[i - 1]))) if i > 0 else ""
        if _should_split_before_next(
            current_norm,
            next_word,
            next_norm,
            current_raw=clean,
            prev_norm=prev_norm,
        ):
            hits.append(f"{clean} {next_word}")
    return hits


def validate_missing_short_boundaries(text: str) -> ValidationResult:
    hits = find_missing_short_boundaries(text)
    if hits:
        return ValidationResult(False, f"Missing sentence boundary detected: {hits[0]}")
    return ValidationResult(True, "OK")


def fix_punctuation_anomalies(text: str) -> str:
    """Normalize sequences like ',.' without changing word content or order."""
    result = re.sub(r"[,;:]+\s*\.", ".", text or "")
    result = re.sub(r"\.\s*[,;:]+", ".", result)
    return re.sub(r"\s+", " ", result).strip()


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
    punct = validate_punctuation_anomalies(text)
    if not punct.ok:
        return punct
    missing = validate_missing_short_boundaries(text)
    if not missing.ok:
        return missing
    return ValidationResult(True, "OK")


def is_complete_sentence(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    if text[-1] not in ".!?":
        return False
    if ARTIFICIAL_BREAK_RE.search(text):
        for match in ARTIFICIAL_BREAK_RE.finditer(text):
            if not _is_kept_boundary(match.group(1), match.group(2)):
                return False
    words = word_sequence(text)
    return len(words) >= 4
