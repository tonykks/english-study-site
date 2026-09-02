from __future__ import annotations

from automation.listening.generate.cta_filter import segments_for_learning
from automation.listening.models import Segment


def test_cta_tail_removed_from_learning_scope():
    segments = [
        Segment("s1", 0, 10, "Mesopotamia was an early civilization."),
        Segment("s2", 10, 20, "Writing changed human history forever."),
        Segment("s3", 20, 30, "Please subscribe to our channel and hit the like button."),
        Segment("s4", 30, 40, "Thanks for watching and see you in the next video."),
    ]
    learning = segments_for_learning(segments)
    assert len(learning) == 2
    assert all("subscribe" not in s.text_en.lower() for s in learning)


def test_cta_sentence_removed_but_body_kept_in_run_on_segment():
    body = "Trade connected the Middle East to other parts of the world."
    cta = "Thank you for listening. Hit the subscribe button on my channel."
    segments = [
        Segment("s1", 0, 100, f"{body} {cta}"),
    ]
    learning = segments_for_learning(segments)
    assert len(learning) == 1
    assert "Trade connected" in learning[0].text_en
    assert "subscribe" not in learning[0].text_en.lower()
