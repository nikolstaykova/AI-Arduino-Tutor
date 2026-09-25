"""Every part and tool has plain-language text for learners; the technical
card text stays behind the scenes for Claude's brief and the engine."""
import json

import bench_server
from core import lesson_gen
from core.library import load_library


def test_every_card_has_plain_words_for_learners():
    for card in load_library().cards.values():
        if card.get("type") not in ("part", "tool"):
            continue
        plain = card.get("plain") or {}
        assert plain.get("what") and plain.get("how"), card["id"]
        assert len(plain["what"]) <= 200, card["id"]           # short enough to read at a glance


def test_learners_see_the_plain_text_not_the_technical_one():
    items = {i["id"]: i for i in bench_server.api_library({})["items"]}
    lcd = items["lcd1602"]
    assert "two lines of 16" in lcd["description"] and "Wokwi" not in lcd["description"] + lcd["how_to_use"]
    assert "`" not in json.dumps(items)                        # no code-formatting leftovers
    assert items["led"]["pins"]["A"] == "the long leg (+)"


def test_claude_still_gets_the_technical_details():
    brief = lesson_gen.facts_text(load_library())
    assert "anode" in brief and "internal connection" in brief
