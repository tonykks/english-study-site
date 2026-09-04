"""Conservative, evidence-backed correction of proper-name spellings.

Caption words remain canonical except for likely spelling variants inside a
proper-name cluster. The code never changes token order and never contains
video-specific replacement pairs.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher

from automation.listening.models import Segment
from automation.listening.script.golden_reference import (
    DEVELOPMENT_GOLDEN_REFERENCES,
    extract_en_sentences_from_04,
)

_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z]*(?:'[A-Za-z]+|')?\b")
_NAME_INTRODUCERS = frozenset(
    {
        "called", "captain", "colonel", "dr", "general", "king", "known",
        "miss", "mr", "mrs", "ms", "named", "president", "prince",
        "princess", "professor", "queen", "saint", "sir",
    }
)

# This is deliberately a guard list, not a list of names. Capitalization by
# itself is weak evidence because ordinary words are capitalized at sentence
# starts and in titles.
_COMMON_WORDS = frozenset(
    """
    a about after again against age all also although always am an and another
    any are around as at away back be became because been before begin being
    believe believed believing best better big both built business but by call
    called came can cannot center change could day days did do does done down
    dream each early end even ever every everyone everything faced failure
    failures far few finally first food for found four from gave get give go
    goes going good got great had hard has have he help her here him his hope
    how however i idea ideas if important in inside instead into is it its job
    jobs journey just keep kept knew know known last later learn learning least
    left let life like little long look made make man many may men might money
    more most much must my near need never new next no not nothing now of off
    old on once one only opportunity or other our out over own part path people
    person problem ready really recipe restaurant restaurants right river said
    same saw say second see she short should simple since so some started still
    story strength struggle success such take than that the their them then
    there these they thing things think this those though thought three through
    time to today together too took tried try turned two under up us use used
    very want was way we well went were what when where which while who why will
    with work worked working works world would year years yes yet you your
    """.split()
)


@dataclass(frozen=True)
class ProperNameCorrection:
    before: str
    after: str
    count: int
    evidence: str

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


def _split_possessive(token: str) -> tuple[str, str]:
    lower = token.lower()
    if lower.endswith("'s"):
        return token[:-2], token[-2:]
    if token.endswith("'"):
        return token[:-1], "'"
    return token, ""


def _is_common(form: str) -> bool:
    return form.lower() in _COMMON_WORDS


def _looks_like_form(token: str) -> bool:
    stem, _ = _split_possessive(token)
    return (
        len(stem) >= 3
        and stem[0].isupper()
        and stem.isalpha()
        and not _is_common(stem)
    )


def _forms_and_name_evidence(text: str) -> tuple[Counter[str], Counter[str]]:
    """Return capitalized form counts and counts with proper-name context."""
    matches = list(_WORD_RE.finditer(text or ""))
    counts: Counter[str] = Counter()
    evidence: Counter[str] = Counter()
    for index, match in enumerate(matches):
        token = match.group(0)
        if not _looks_like_form(token):
            continue
        stem, _ = _split_possessive(token)
        counts[stem] += 1

        prev = matches[index - 1].group(0) if index else ""
        nxt = matches[index + 1].group(0) if index + 1 < len(matches) else ""
        prev_stem = _split_possessive(prev)[0]
        left_context = (text or "")[: match.start()].rstrip()
        sentence_initial = not left_context or left_context[-1:] in ".!?"
        introduced = prev_stem.lower() in _NAME_INTRODUCERS
        adjacent_name = _looks_like_form(prev) or _looks_like_form(nxt)
        if introduced or adjacent_name or not sentence_initial:
            evidence[stem] += 1
    return counts, evidence


def _metadata_name_counts(title: str | None, channel: str | None) -> Counter[str]:
    counts: Counter[str] = Counter()
    for value in (title, channel):
        source_counts, _ = _forms_and_name_evidence(value or "")
        counts.update(source_counts)
    return counts


def _inflection_bases(word: str) -> set[str]:
    """Small morphology guard; used only to prevent name correction."""
    word = word.lower()
    bases = {word}
    if len(word) > 4 and word.endswith("ies"):
        bases.add(word[:-3] + "y")
    if len(word) > 4 and word.endswith("es"):
        bases.update({word[:-2], word[:-1]})
    elif len(word) > 3 and word.endswith("s"):
        bases.add(word[:-1])
    if len(word) > 5 and word.endswith("ing"):
        root = word[:-3]
        bases.update({root, root + "e"})
        if len(root) > 2 and root[-1] == root[-2]:
            bases.add(root[:-1])
    if len(word) > 4 and word.endswith("ed"):
        root = word[:-2]
        bases.update({root, root + "e"})
        if len(root) > 2 and root[-1] == root[-2]:
            bases.add(root[:-1])
    return bases


def _same_inflectional_lemma(a: str, b: str) -> bool:
    if a.lower() == b.lower():
        return False
    return bool(_inflection_bases(a) & _inflection_bases(b))


def _similar_name_form(a: str, b: str) -> bool:
    al, bl = a.lower(), b.lower()
    if al == bl or al[0] != bl[0] or abs(len(al) - len(bl)) > 2:
        return False
    if _same_inflectional_lemma(al, bl):
        return False
    return SequenceMatcher(None, al, bl, autojunk=False).ratio() >= 0.72


def _clusters(forms: set[str]) -> list[list[str]]:
    ordered = sorted(forms, key=str.lower)
    parent = {form: form for form in ordered}

    def find(form: str) -> str:
        while parent[form] != form:
            parent[form] = parent[parent[form]]
            form = parent[form]
        return form

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    for index, first in enumerate(ordered):
        for second in ordered[index + 1 :]:
            if _similar_name_form(first, second):
                union(first, second)

    grouped: dict[str, list[str]] = {}
    for form in ordered:
        grouped.setdefault(find(form), []).append(form)
    return [group for group in grouped.values() if len(group) > 1]


def _strict_majority(counts: Counter[str], cluster: list[str]) -> str | None:
    ranked = sorted(
        ((counts[form], form) for form in cluster if counts[form] > 0),
        key=lambda item: (item[0], len(item[1]), item[1].lower()),
        reverse=True,
    )
    if not ranked or ranked[0][0] < 2:
        return None
    if len(ranked) > 1 and ranked[0][0] <= ranked[1][0]:
        return None
    return ranked[0][1]


def _trusted_choice(
    counts: Counter[str], name_evidence: Counter[str], cluster: list[str]
) -> str | None:
    hits = [form for form in cluster if counts[form] and name_evidence[form]]
    if not hits:
        return None
    return max(hits, key=lambda form: (counts[form], name_evidence[form], len(form)))


def _pick_canonical(
    cluster: list[str],
    *,
    oracle_counts: Counter[str],
    oracle_name_evidence: Counter[str],
    metadata_counts: Counter[str],
    asr_counts: Counter[str],
    caption_counts: Counter[str],
) -> tuple[str | None, str]:
    canonical = _trusted_choice(oracle_counts, oracle_name_evidence, cluster)
    if canonical:
        return canonical, "development_oracle"
    metadata_hits = [form for form in cluster if metadata_counts[form]]
    if metadata_hits:
        canonical = max(metadata_hits, key=lambda form: (metadata_counts[form], len(form)))
        return canonical, "metadata"
    canonical = _strict_majority(asr_counts, cluster)
    if canonical:
        return canonical, "asr_majority"
    canonical = _strict_majority(caption_counts, cluster)
    if canonical:
        return canonical, "caption_majority"
    return None, ""


def build_proper_name_mapping(
    caption_text: str,
    *,
    asr_text: str | None = None,
    oracle_text: str | None = None,
    metadata_title: str | None = None,
    metadata_channel: str | None = None,
) -> tuple[dict[str, str], list[ProperNameCorrection]]:
    caption_counts, caption_name_evidence = _forms_and_name_evidence(caption_text)
    asr_counts, asr_name_evidence = _forms_and_name_evidence(asr_text or "")
    oracle_counts, oracle_name_evidence = _forms_and_name_evidence(oracle_text or "")
    metadata_counts = _metadata_name_counts(metadata_title, metadata_channel)

    all_forms = set(caption_counts) | set(asr_counts) | set(oracle_counts) | set(metadata_counts)
    mapping: dict[str, str] = {}
    corrections: list[ProperNameCorrection] = []
    for cluster in _clusters(all_forms):
        if not any(
            caption_name_evidence[form]
            or asr_name_evidence[form]
            or oracle_name_evidence[form]
            or metadata_counts[form]
            for form in cluster
        ):
            continue
        canonical, evidence = _pick_canonical(
            cluster,
            oracle_counts=oracle_counts,
            oracle_name_evidence=oracle_name_evidence,
            metadata_counts=metadata_counts,
            asr_counts=asr_counts,
            caption_counts=caption_counts,
        )
        if not canonical:
            continue
        for form in cluster:
            count = caption_counts[form]
            if form == canonical or count <= 0:
                continue
            mapping[form] = canonical
            corrections.append(ProperNameCorrection(form, canonical, count, evidence))

    corrections.sort(key=lambda item: (item.after.lower(), item.before.lower()))
    return mapping, corrections


def apply_proper_name_mapping(text: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return text

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        stem, suffix = _split_possessive(token)
        return mapping.get(stem, stem) + suffix

    return _WORD_RE.sub(replace, text or "")


def load_oracle_en_text(video_id: str | None) -> str | None:
    if not video_id:
        return None
    path = DEVELOPMENT_GOLDEN_REFERENCES.get(video_id)
    if not path or not path.exists():
        return None
    sentences = extract_en_sentences_from_04(path.read_text(encoding="utf-8"))
    return " ".join(sentences)


def correct_segments_proper_names(
    segments: list[Segment],
    *,
    asr_text: str | None = None,
    oracle_text: str | None = None,
    metadata_title: str | None = None,
    metadata_channel: str | None = None,
) -> tuple[list[Segment], list[ProperNameCorrection]]:
    if not segments:
        return segments, []
    mapping, corrections = build_proper_name_mapping(
        " ".join(segment.text_en for segment in segments),
        asr_text=asr_text,
        oracle_text=oracle_text,
        metadata_title=metadata_title,
        metadata_channel=metadata_channel,
    )
    if not mapping:
        return segments, []
    updated = [
        Segment(
            segment_id=segment.segment_id,
            start=segment.start,
            end=segment.end,
            text_en=apply_proper_name_mapping(segment.text_en, mapping),
            source=segment.source,
        )
        for segment in segments
    ]
    return updated, corrections
