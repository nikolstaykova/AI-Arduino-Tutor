"""core/flow_explorer.py — every learner run-flow of a lesson keeps
tracking, code and behaviour correct."""
import copy

import pytest

from core import engine, flow_explorer
from core.lesson import load_lesson
from core.lesson_gen import GeneratedLesson


@pytest.mark.parametrize("lesson_id, min_flows", [("blink", 200), ("analog-read-serial", 100), ("digital-read-serial", 500)])
def test_every_flow_of_every_hand_made_lesson_holds(lesson_id, min_flows):
    result = flow_explorer.explore(load_lesson(lesson_id))
    assert result["flows"] >= min_flows
    assert result["failures"] == []


def test_every_free_pin_is_tried():
    board = flow_explorer.Board(load_lesson("blink"), flow_explorer.load_library())
    assert flow_explorer.pin_choices(board)["13"] == ["13"] + [str(n) for n in range(2, 13)]


def test_explorer_catches_a_code_rewrite_that_touches_non_pins(monkeypatch):
    """With the old whole-word rewrite, a pin-2 → 3 move also changed
    delay(2). The explorer's independent non-pin check must flag it."""
    base = load_lesson("digital-read-serial")
    lesson = GeneratedLesson(copy.deepcopy(base.data), copy.deepcopy(base.diagram()),
                             base.code_text().replace("delay(1);", "delay(2);"))
    assert flow_explorer.explore(lesson)["failures"] == []
    monkeypatch.setattr(engine, "rewrite_pins_in_code", engine.apply_word_boundary_replacements)
    result = flow_explorer.explore(lesson, stop_after=1)
    assert result["failures"] and any("isn't a pin changed" in p for p in result["failures"][0][1])


def test_explorer_catches_a_lesson_that_accepts_a_forgotten_step():
    data, diagram = copy.deepcopy(load_lesson("blink").data), copy.deepcopy(load_lesson("blink").diagram())
    for step in data["steps"]:
        if step.get("expected_nets") == [["led1:C", "uno:GND.1"]]:
            step["expected_nets"] = [["led1:A", "r1:2"]]   # asks for something already done
    lesson = GeneratedLesson(data, diagram, load_lesson("blink").code_text())
    result = flow_explorer.explore(lesson, stop_after=1)
    assert result["failures"]
