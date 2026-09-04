from __future__ import annotations

import re
from pathlib import Path

from automation.listening.generate.update_index import append_listening_card, bracket_balance_ok


def test_idempotent_append(tmp_path: Path):
    index = tmp_path / "index.html"
    index.write_text(
        """<script>
      const listeningCards = [
        {
          level: "level1",
          title: "Existing",
          introEn: "Intro",
          tags: ["Level 1"],
          href: "./level1/Existing/Existing.html"
        }
      ];
    </script>""",
        encoding="utf-8",
    )
    card = {
        "level": "level2",
        "title": "New Story",
        "introEn": "A new intro",
        "tags": ["Level 2"],
        "href": "./level2/New_Story/New_Story.html",
    }
    msg = append_listening_card(index, card, dry_run=False)
    assert msg == "appended"
    content = index.read_text(encoding="utf-8")
    assert "New Story" in content
    assert bracket_balance_ok(content)


def test_duplicate_href_idempotent(tmp_path: Path):
    index = tmp_path / "index.html"
    href = "./level2/Dup/Dup.html"
    index.write_text(
        f"""<script>
      const listeningCards = [
        {{ level: "level2", title: "Dup", introEn: "x", tags: [], href: "{href}" }}
      ];
    </script>""",
        encoding="utf-8",
    )
    card = {"level": "level2", "title": "Dup", "introEn": "x", "tags": [], "href": href}
    msg = append_listening_card(index, card)
    assert "idempotent" in msg
