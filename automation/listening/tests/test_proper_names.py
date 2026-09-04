from __future__ import annotations

from automation.listening.script.proper_names import (
    apply_proper_name_mapping,
    build_proper_name_mapping,
)


def test_proper_name_correction_uses_asr_and_oracle_evidence():
    caption = (
        "Colonel Harlon Sanders was born poor. Later Harlon built KFC. "
        "A boy named Haron David Sanders worked hard. Harland kept going."
    )
    asr = (
        "Colonel Harland Sanders was born poor. Later Harland built KFC. "
        "A boy named Harland David Sanders worked hard. Harland kept going."
    )
    oracle = (
        "Colonel Harland Sanders was born poor. Later Harland built KFC. "
        "A boy named Harland David Sanders worked hard."
    )
    mapping, corrections = build_proper_name_mapping(
        caption, asr_text=asr, oracle_text=oracle
    )
    assert mapping.get("Harlon") == "Harland"
    assert mapping.get("Haron") == "Harland"
    fixed = apply_proper_name_mapping(caption, mapping)
    assert "Harlon" not in fixed
    assert "Haron" not in fixed
    assert fixed.count("Harland") >= 4
    assert all(c.after == "Harland" for c in corrections)
    # Possessive suffix preserved when present
    assert "Harland's" in apply_proper_name_mapping("Harlon's recipe", mapping)


def test_proper_name_does_not_invent_without_evidence():
    caption = "Alice met Bob near the river."
    mapping, corrections = build_proper_name_mapping(caption, asr_text=caption)
    assert mapping == {}
    assert corrections == []


def test_common_verb_inflections_are_never_name_variants():
    caption = "Believe in yourself. Believing takes patient daily practice."
    oracle = "Believing can help. Believe what the evidence supports."
    mapping, corrections = build_proper_name_mapping(
        caption,
        asr_text=oracle,
        oracle_text=oracle,
    )
    assert mapping == {}
    assert corrections == []


def test_metadata_can_supply_canonical_name_form():
    caption = "Jon Smyth spoke first. Later Jon Smyth answered questions."
    mapping, corrections = build_proper_name_mapping(
        caption,
        asr_text=caption,
        metadata_title="An Interview with John Smith",
        metadata_channel="John Smith Official",
    )
    assert mapping["Jon"] == "John"
    assert mapping["Smyth"] == "Smith"
    assert {item.evidence for item in corrections} == {"metadata"}


def test_capitalized_common_nouns_do_not_pollute_clusters():
    caption = "Desert winds can be strong. Dessert tastes sweet."
    oracle = "Dessert can be shared. Desert weather can change quickly."
    mapping, corrections = build_proper_name_mapping(
        caption,
        asr_text=oracle,
        oracle_text=oracle,
    )
    assert mapping == {}
    assert corrections == []


def test_correction_records_count_and_evidence():
    mapping, corrections = build_proper_name_mapping(
        "Colonel Harlon spoke. Harlon's recipe became popular.",
        asr_text="Colonel Harland spoke. Harland's recipe became popular.",
        oracle_text="Colonel Harland spoke. Harland's recipe became popular.",
    )
    assert mapping["Harlon"] == "Harland"
    assert [item.to_dict() for item in corrections] == [
        {
            "before": "Harlon",
            "after": "Harland",
            "count": 2,
            "evidence": "development_oracle",
        }
    ]


def test_asr_majority_selects_existing_name_spelling():
    mapping, corrections = build_proper_name_mapping(
        "Professor Maren Lee spoke. Maren returned later.",
        asr_text="Professor Marin Lee spoke. Marin returned later. Marin agreed.",
    )
    assert mapping == {"Maren": "Marin"}
    assert corrections[0].evidence == "asr_majority"


def test_caption_majority_only_rewrites_the_minority_variant():
    caption = "Professor Marin Lee spoke. Marin returned. Maren answered."
    mapping, corrections = build_proper_name_mapping(caption)
    assert mapping == {"Maren": "Marin"}
    assert corrections[0].count == 1
    assert corrections[0].evidence == "caption_majority"
