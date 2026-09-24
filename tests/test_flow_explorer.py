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


# ---- the smart (covering) sample the hosted app uses --------------------------------

@pytest.mark.parametrize("lesson_id", ["blink", "analog-read-serial", "digital-read-serial"])
def test_smart_sample_is_small_and_every_hand_made_lesson_passes(lesson_id):
    lesson = load_lesson(lesson_id)
    full = sum(1 for _ in flow_explorer.enumerate_flows(lesson))
    result = flow_explorer.explore(lesson, mode="smart")
    assert 10 <= result["flows"] < full / 4
    assert result["failures"] == []


def test_smart_sample_covers_each_choice_on_its_own():
    lesson = load_lesson("blink")
    board = flow_explorer.Board(lesson, flow_explorer.load_library())
    flows = list(flow_explorer.enumerate_flows(lesson, mode="smart"))
    moved = {f["pins"]["13"] for f in flows if list(f["pins"]) == ["13"]}
    assert moved == set(flow_explorer.pin_choices(board)["13"][1:])          # every free pin
    assert any(f["ahead"] for f in flows)                                     # built ahead
    assert {(s, k) for f in flows for s, k in f["mistakes"].items()} == {(s, k) for s in board.build_steps for k in flow_explorer.MISTAKES}


def test_smart_sample_never_puts_two_signals_on_one_pin():
    for lesson_id in ["digital-read-serial", "blink"]:
        for f in flow_explorer.enumerate_flows(load_lesson(lesson_id), mode="smart"):
            assert len(set(f["pins"].values())) == len(f["pins"])


def test_smart_sample_still_catches_a_broken_lesson(monkeypatch):
    # the same two defects the full explorer is tested against above
    data, diagram = copy.deepcopy(load_lesson("blink").data), copy.deepcopy(load_lesson("blink").diagram())
    for step in data["steps"]:
        if step.get("expected_nets") == [["led1:C", "uno:GND.1"]]:
            step["expected_nets"] = [["led1:A", "r1:2"]]
    assert flow_explorer.explore(GeneratedLesson(data, diagram, load_lesson("blink").code_text()), stop_after=1, mode="smart")["failures"]
    base = load_lesson("digital-read-serial")
    lesson = GeneratedLesson(copy.deepcopy(base.data), copy.deepcopy(base.diagram()), base.code_text().replace("delay(1);", "delay(2);"))
    monkeypatch.setattr(engine, "rewrite_pins_in_code", engine.apply_word_boundary_replacements)
    assert flow_explorer.explore(lesson, stop_after=1, mode="smart")["failures"]


def test_generation_uses_the_full_check_unless_hosted(monkeypatch):
    from core import lesson_gen
    monkeypatch.delenv("CQ_FLOW_CHECK", raising=False)
    assert lesson_gen.flow_check_mode() == "full"
    monkeypatch.setenv("CQ_FLOW_CHECK", "smart")
    assert lesson_gen.flow_check_mode() == "smart"
    seen = {}
    monkeypatch.setattr(flow_explorer, "explore", lambda *a, **k: seen.update(k) or {"flows": 0, "failures": []})
    lesson = load_lesson("blink")
    lesson_gen._check_flows(lesson.data, lesson.diagram(), lesson.code_text(), flow_explorer.load_library(), [])
    assert seen["mode"] == "smart"
