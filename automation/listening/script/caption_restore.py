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

# Phrase-final particles that can end a sentence before a clause starter
# (e.g. "knock on. He", "go through. But") even when listed as incomplete.
# Keep this narrow: "yet" is accepted only before a strong starter such as
# "Every", while the context guard below still rejects "And yet, he".
PHRASE_FINAL_BEFORE_STARTER = frozenset(
    {
        "on",
        "through",
        "yet",
    }
)

# Apposition / honorific heads — not new-sentence starters after nouns like "people".
TITLE_OR_ROLE_TOKENS = frozenset(
    {
        "colonel",
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "sir",
        "madam",
        "captain",
        "general",
        "president",
        "professor",
        "king",
        "queen",
        "prince",
        "princess",
    }
)

# Starters strong enough to end a phrase-final particle ("knock on. He").
# Keep narrower than SENTENCE_STARTERS to avoid "on this journey" false splits.
CLAUSE_STARTERS_AFTER_PARTICLE = frozenset(
    {
        "he",
        "she",
        "they",
        "we",
        "i",
        "but",
        "however",
        "instead",
        "then",
        "later",
        "still",
        "suddenly",
        "eventually",
        "finally",
        "meanwhile",
        "nevertheless",
        "every",
    }
)

# A caption-native period before a personal-pronoun subject is strong boundary
# evidence on its own.  Keep this separate from heuristic starter lists: ASR
# may omit or misalign the same words, and grammatical cleanup must not erase
# source punctuation such as "looks like. He was not lucky."
CAPTION_NATIVE_PRONOUN_STARTERS = frozenset({"he", "she", "they", "we", "i"})

# Words that can legitimately finish a clause through pronoun use, ellipsis,
# or preposition/particle stranding.  This is for validation only: restoration
# still requires caption/ASR agreement or one of the narrower guards above.
CONTEXTUAL_SENTENCE_ENDS = frozenset(
    {
        "this",
        "that",
        "these",
        "those",
        "one",
        "all",
        "half",
        "more",
        "most",
        "other",
        "not",
        "no",
        "also",
        "just",
        "only",
        "even",
        "still",
        "already",
        "yet",
        "on",
        "at",
        "by",
        "with",
        "from",
        "into",
        "onto",
        "upon",
        "about",
        "for",
        "in",
        "through",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "over",
        "within",
        "against",
        "among",
        "toward",
        "towards",
        "since",
        "like",
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
        "all",
        "every",
        "keep",
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

# Explicit sentence punctuation plus one of these capitalized starters is
# enough validation evidence for a stranded "to" (for example, "used to.
# For example").  Keep this narrower than accepting every capitalized word.
DISCOURSE_SENTENCE_STARTERS = SENTENCE_STARTERS | {"for"}

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
    """Join caption fragments without discarding source-native punctuation."""
    parts: list[str] = []
    for seg in segments:
        text = normalize_caption_fragment(seg.text_en)
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


def fix_artificial_period_breaks(
    text: str,
    *,
    keep_end_indices: set[int] | None = None,
) -> str:
    """Merge caption fragments split by artificial mid-phrase periods."""
    result = text
    protected = keep_end_indices or set()
    while True:
        def _repl(match: re.Match[str]) -> str:
            before = match.group(1)
            after = match.group(2)
            # keep_end_indices uses the whitespace-token positions consumed by
            # the restoration path.  Do not use normalize_text here: it splits
            # hyphenated tokens and makes later protected positions drift.
            before_idx = len(result[: match.end(1)].split()) - 1
            if before_idx in protected:
                return match.group(0)
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
    return [(m.group(1), m.group(2)) for m in re.finditer(r"([A-Za-z0-9']+)([,;:.?!]*)", text or "")]


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
    if "." in (punct or ""):
        return "."
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


def _agreed_caption_end_indices(caption_text: str, asr_text: str) -> set[int]:
    """Return positions where aligned caption and ASR tokens have explicit ends."""
    cap_words = caption_text.split()
    asr_words, _, asr_puncts = _build_asr_word_lists(asr_text)
    cap_norm = [normalize_text(re.sub(r"[.!?]+$", "", word)) for word in cap_words]
    asr_norm = [normalize_text(word) for word in asr_words]
    mapping = _map_caption_to_asr(cap_norm, asr_norm)
    return {
        ci
        for ci, aj in mapping.items()
        if re.search(r"[.!?]$", cap_words[ci])
        and aj < len(asr_puncts)
        and bool(_end_mark_from_punct(asr_puncts[aj]))
    }


def _agreed_text_end_indices(text: str, caption_text: str, asr_text: str) -> set[int]:
    """Return text positions whose boundary span is explicit in caption and ASR."""
    text_words = text.split()
    cap_words = caption_text.split()
    asr_words, _, asr_puncts = _build_asr_word_lists(asr_text)
    text_norm = [normalize_text(re.sub(r"[.!?]+$", "", word)) for word in text_words]
    cap_norm = [normalize_text(re.sub(r"[.!?]+$", "", word)) for word in cap_words]
    asr_norm = [normalize_text(word) for word in asr_words]
    text_to_cap = _map_caption_to_asr(text_norm, cap_norm)
    cap_to_asr = _map_caption_to_asr(cap_norm, asr_norm)
    agreed: set[int] = set()
    for text_idx in range(len(text_words) - 1):
        cap_idx = text_to_cap.get(text_idx)
        if cap_idx is None or text_to_cap.get(text_idx + 1) != cap_idx + 1:
            continue
        asr_idx = cap_to_asr.get(cap_idx)
        if asr_idx is None or cap_to_asr.get(cap_idx + 1) != asr_idx + 1:
            continue
        if (
            re.search(r"[.!?]$", cap_words[cap_idx])
            and asr_idx < len(asr_puncts)
            and _end_mark_from_punct(asr_puncts[asr_idx])
        ):
            agreed.add(text_idx)
    return agreed


def _should_split_before_next(
    current_norm: str,
    next_word: str,
    next_norm: str,
    *,
    current_raw: str = "",
    prev_norm: str = "",
    prev2_norm: str = "",
) -> bool:
    next_is_starter = next_norm in SENTENCE_STARTERS or next_word in {"I", "i"}
    next_is_particle_starter = next_norm in CLAUSE_STARTERS_AFTER_PARTICLE or next_word in {"I", "i"}
    if current_norm in INCOMPLETE_BEFORE_PERIOD:
        allow_phrase_final = (
            current_norm in PHRASE_FINAL_BEFORE_STARTER and next_is_particle_starter
        )
        allow_terminal_starter = current_norm in TERMINAL_BEFORE_CAPITAL and next_is_starter
        if not (allow_phrase_final or allow_terminal_starter):
            return False
    if not next_word:
        return False
    if current_raw and current_raw[0].isupper() and next_word[0].isupper():
        return False
    if re.match(r"^(Mr|Mrs|Ms|Dr|St)\.?$", current_norm, re.IGNORECASE):
        return False
    if next_norm in TITLE_OR_ROLE_TOKENS:
        return False
    if current_norm in PROPER_NOUN_CONTINUATIONS and next_norm in PROPER_NOUN_TOKENS:
        return False
    if next_norm in PROPER_NOUN_TOKENS:
        return False
    # "Over the years, Name..." — discourse span, not "years. Name"
    if current_norm == "years" and prev_norm == "the":
        return False
    # "by/at the time Name/he..." is a clause opener; allow true sentence starts
    # such as "at the time. All he knew".
    if current_norm == "time" and prev_norm == "the":
        if next_norm in {"all", "everyone", "everything", "nobody", "nothing"}:
            return True
        if next_word[0].isupper() and next_is_starter and next_norm not in {
            "he",
            "she",
            "they",
            "we",
            "it",
            "his",
            "her",
            "their",
            "this",
            "that",
            "these",
            "those",
        }:
            return True
        return False
    # Discourse adverbials kept with following clause ("Once again, he").
    if current_norm == "again" and prev_norm == "once":
        return False
    if current_norm == "yet" and prev_norm == "and":
        return False
    if current_norm == "down" and prev_norm == "deep":
        return False
    if current_norm == "again" and prev_norm == "once" and prev2_norm == "so":
        return False

    if next_word[0].isupper():
        if next_is_starter or next_word == "I":
            return True
        if current_norm in TERMINAL_BEFORE_CAPITAL:
            # Mid-clause contractions keep the prior noun ("story It's not...").
            if "'" in next_word:
                return False
            return True
        return False

    # Lowercase caption starters only after phrase-final particles
    # ("knock on he", "go through but") — not after every TERMINAL word
    # (avoids "learning and exchange" / "on this journey" false splits).
    if next_is_particle_starter and current_norm in PHRASE_FINAL_BEFORE_STARTER:
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
        prev2_norm = normalize_text(re.sub(r"[.!?]+$", "", words[i - 2])) if i > 1 else ""
        if _should_split_before_next(
            current_norm,
            next_word,
            next_norm,
            current_raw=clean,
            prev_norm=prev_norm,
            prev2_norm=prev2_norm,
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
    # Capitalize clause starters after restored sentence ends.
    for i in range(len(output) - 1):
        if not re.search(r"[.!?]$", output[i]):
            continue
        nxt = output[i + 1]
        if not nxt or not nxt[0].islower():
            continue
        nxt_norm = normalize_text(re.sub(r"[,;:.!?]+$", "", nxt))
        if nxt_norm in SENTENCE_STARTERS:
            output[i + 1] = nxt[0].upper() + nxt[1:]
    # After ASR/caption commas, lower false-capitalized clause words
    # ("lifetime, But" → "lifetime, but") unless proper/title.
    for i in range(len(output) - 1):
        if not re.search(r"[,;]$", output[i]):
            continue
        nxt = output[i + 1]
        if not nxt or not nxt[0].isupper():
            continue
        core = re.sub(r"[,;:.!?]+$", "", nxt)
        nxt_norm = normalize_text(core)
        if nxt_norm in PROPER_NOUN_TOKENS or nxt_norm in TITLE_OR_ROLE_TOKENS:
            continue
        if nxt_norm in SENTENCE_STARTERS or nxt_norm in CLAUSE_STARTERS_AFTER_PARTICLE:
            output[i + 1] = nxt[0].lower() + nxt[1:]
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
    # Caption-native sentence ends (auto-captions sometimes already punctuate).
    caption_ends = {
        i for i, w in enumerate(cap_words) if re.search(r"[.!?]$", w or "")
    }

    mapping = _map_caption_to_asr(cap_norm, asr_norm)

    def _asr_blocks_heuristic_end(cap_idx: int) -> bool:
        """ASR comma/semicolon continuation wins over local split heuristics.

        Never block a caption-native period — misaligned ASR commas must not
        erase an existing caption sentence end.
        """
        if cap_idx in caption_ends:
            return False
        aj = mapping.get(cap_idx)
        if aj is None or aj >= len(asr_puncts):
            return False
        if aj in asr_ends:
            return False
        return bool(_internal_punct(asr_puncts[aj]))

    end_indices: set[int] = set()
    for ci, aj in mapping.items():
        if aj in asr_ends:
            end_indices.add(ci)
    end_indices.update(caption_ends)
    if cap_clean:
        end_indices.add(len(cap_clean) - 1)

    # Local heuristic recovery only inside run-on spans.
    end_indices = _split_long_sentences(" ".join(cap_clean), end_indices, max_words=RUN_ON_WARN_WORDS)
    end_indices = {
        i
        for i in end_indices
        if not _asr_blocks_heuristic_end(i)
        or i in caption_ends
        or i in {ci for ci, aj in mapping.items() if aj in asr_ends}
        or i == len(cap_clean) - 1
    }

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
            if _asr_blocks_heuristic_end(abs_i):
                continue
            if _should_split_before_next(
                cap_norm[abs_i],
                span_words[local_i + 1],
                cap_norm[abs_i + 1],
                current_raw=span_words[local_i],
                prev_norm=cap_norm[abs_i - 1] if abs_i > 0 else "",
                prev2_norm=cap_norm[abs_i - 2] if abs_i > 1 else "",
            ):
                end_indices.add(abs_i)

    for hi in _heuristic_sentence_end_indices(cap_clean):
        if hi == len(cap_clean) - 1 or not _asr_blocks_heuristic_end(hi):
            aj = mapping.get(hi)
            if aj in asr_ends or hi in caption_ends or not _asr_blocks_heuristic_end(hi):
                end_indices.add(hi)

    asr_mapped_ends = {ci for ci, aj in mapping.items() if aj in asr_ends}
    safe_ends: set[int] = set()
    for idx in sorted(end_indices):
        next_raw = cap_clean[idx + 1] if idx + 1 < len(cap_clean) else ""
        next_norm = cap_norm[idx + 1] if idx + 1 < len(cap_norm) else ""
        prev_norm = cap_norm[idx - 1] if idx > 0 else ""
        prev2_norm = cap_norm[idx - 2] if idx > 1 else ""
        if idx == len(cap_clean) - 1:
            safe_ends.add(idx)
            continue
        if idx in caption_ends:
            safe_ends.add(idx)
            continue
        if idx not in asr_mapped_ends:
            if not _should_split_before_next(
                cap_norm[idx],
                next_raw,
                next_norm,
                current_raw=cap_clean[idx],
                prev_norm=prev_norm,
                prev2_norm=prev2_norm,
            ):
                continue
            if _asr_blocks_heuristic_end(idx):
                continue
        else:
            # Drop ASR ends that our guards reject (e.g. "the time Jordan").
            if cap_norm[idx] == "time" and prev_norm == "the":
                if not _should_split_before_next(
                    cap_norm[idx],
                    next_raw,
                    next_norm,
                    current_raw=cap_clean[idx],
                    prev_norm=prev_norm,
                    prev2_norm=prev2_norm,
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
        orig = cap_words[i] if i < len(cap_words) else word
        caption_end_mark = ""
        if re.search(r"!$", orig or ""):
            caption_end_mark = "!"
        elif re.search(r"\?$", orig or ""):
            caption_end_mark = "?"
        elif re.search(r"\.$", orig or ""):
            caption_end_mark = "."
        aj = mapping.get(i)
        if aj is not None and aj < len(asr_puncts):
            # Caption sentence ends beat misaligned ASR commas.
            if not caption_end_mark:
                if not extra:
                    extra = _internal_punct(asr_puncts[aj])
            mark = _end_mark_from_punct(asr_puncts[aj])
            if mark:
                end_marks[i] = mark
        if caption_end_mark:
            end_marks[i] = caption_end_mark
            extra = ""
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
    asr_text = " ".join(s.text_en for s in asr_segments) if asr_segments else None
    agreed_ends = _agreed_caption_end_indices(joined, asr_text) if asr_text else set()
    fixed = fix_artificial_period_breaks(joined, keep_end_indices=agreed_ends)
    restored = restore_sentence_boundaries(fixed, asr_text)
    restored = fix_artificial_period_breaks(restored, keep_end_indices=agreed_ends)
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
    b = before.lower()
    a = after.lower()
    if a in CAPTION_NATIVE_PRONOUN_STARTERS:
        return True
    if b in TERMINAL_BEFORE_CAPITAL and a in SENTENCE_STARTERS:
        return True
    if b in PHRASE_FINAL_BEFORE_STARTER and a in CLAUSE_STARTERS_AFTER_PARTICLE:
        return True
    return False


def _is_valid_sentence_boundary(before: str, after: str) -> bool:
    """Accept plausible boundaries without weakening restoration decisions."""
    if _is_kept_boundary(before, after):
        return True
    if (
        before.lower() == "to"
        and bool(after)
        and after[0].isupper()
        and after.lower() in DISCOURSE_SENTENCE_STARTERS
    ):
        return True
    return (
        before.lower() in CONTEXTUAL_SENTENCE_ENDS
        and bool(after)
        and after[0].isupper()
    )


def validate_no_artificial_sentence_breaks(
    text: str,
    *,
    caption_text: str | None = None,
    asr_text: str | None = None,
) -> ValidationResult:
    agreed_end_indices = (
        _agreed_text_end_indices(text, caption_text, asr_text)
        if caption_text is not None and asr_text is not None
        else set()
    )
    for match in ARTIFICIAL_BREAK_RE.finditer(text or ""):
        before_idx = len(text[: match.end(1)].split()) - 1
        if before_idx in agreed_end_indices:
            continue
        if _is_valid_sentence_boundary(match.group(1), match.group(2)):
            continue
        return ValidationResult(False, f"Artificial sentence break detected: {match.group(0)}")
    for sent in split_sentences(text):
        for match in ARTIFICIAL_BREAK_RE.finditer(sent):
            if _is_valid_sentence_boundary(match.group(1), match.group(2)):
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
        # Any source clause punctuation is boundary evidence. In particular,
        # do not strip a real comma and reinterpret its continuation as a
        # missing period ("Yet, they" / "at the same time, European...").
        if re.search(r"[,;:.!?]$", words[i]):
            continue
        clean = re.sub(r"[,:;]+$", "", re.sub(r"[.!?]+$", "", words[i]))
        next_word = words[i + 1]
        next_norm = normalize_text(re.sub(r"[.!?]+$", "", next_word))
        current_norm = normalize_text(clean)
        prev_norm = normalize_text(re.sub(r"[,:;]+$", "", re.sub(r"[.!?]+$", "", words[i - 1]))) if i > 0 else ""
        prev2_norm = normalize_text(re.sub(r"[,:;]+$", "", re.sub(r"[.!?]+$", "", words[i - 2]))) if i > 1 else ""
        if _should_split_before_next(
            current_norm,
            next_word,
            next_norm,
            current_raw=clean,
            prev_norm=prev_norm,
            prev2_norm=prev2_norm,
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


def validate_sentence_boundaries(
    text: str,
    *,
    caption_text: str | None = None,
    asr_text: str | None = None,
) -> ValidationResult:
    artificial = validate_no_artificial_sentence_breaks(
        text,
        caption_text=caption_text,
        asr_text=asr_text,
    )
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
            if not _is_valid_sentence_boundary(match.group(1), match.group(2)):
                return False
    words = word_sequence(text)
    return len(words) >= 4
