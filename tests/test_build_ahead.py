"""A learner may wire the whole circuit before pressing "check" — a later
step done early, correctly, must not block an earlier step (found by the
Sonnet lesson-generation experiment: the hand-made DigitalReadSerial
rejected step 2 when the pull-down resistor was already in place)."""
import pytest

from core import engine
from core.lesson import load_lesson
from core.library import load_library


@pytest.mark.parametrize("lesson_id", ["blink", "analog-read-serial", "digital-read-serial"])
def test_whole_board_shown_at_every_step_completes_the_lesson(lesson_id):
    lesson, library = load_lesson(lesson_id), load_library()
    board = [c[:2] for c in lesson.diagram()["connections"]]
    state = engine.initial_state()
    state, _ = engine.handle_event(lesson, library, state, {"command": "start"})
    for _ in range(lesson.step_count() + 2):
        if state["finished"]:
            break
        event = {"command": "done"} if state["phase"] in ("gather", "upload") else {"command": "done", "detected_pairs": board}
        state, actions = engine.handle_event(lesson, library, state, event)
        assert not any(a["type"] == "feedback" and a.get("verdict") == "wrong" for a in actions), actions
    assert state["finished"]


def test_an_extra_leg_the_finished_circuit_does_not_have_is_still_refused():
    """Building ahead only covers what the lesson will actually build: the
    resistor's OTHER leg on the pin-2 column is a short, not a later step."""
    lesson, library = load_lesson("digital-read-serial"), load_library()
    board = [c[:2] for c in lesson.diagram()["connections"]]
    board = [["r1:2", "bb1:6b.j"] if p[0] == "r1:2" else p for p in board]   # r1:2 onto the pin-2 column too
    state = engine.initial_state()
    state, _ = engine.handle_event(lesson, library, state, {"command": "start"})
    wrong = False
    for _ in range(lesson.step_count() + 2):
        if state["finished"]:
            break
        event = {"command": "done"} if state["phase"] in ("gather", "upload") else {"command": "done", "detected_pairs": board}
        state, actions = engine.handle_event(lesson, library, state, event)
        if any(a["type"] == "feedback" and a.get("verdict") == "wrong" for a in actions):
            wrong = True
            break
    assert wrong and not state["finished"]


def _play_whole_board(lesson, library, board):
    state = engine.initial_state()
    state, _ = engine.handle_event(lesson, library, state, {"command": "start"})
    actions_seen = []
    for _ in range(lesson.step_count() + 2):
        if state["finished"]:
            break
        event = {"command": "done"} if state["phase"] in ("gather", "upload") else {"command": "done", "detected_pairs": board}
        state, actions = engine.handle_event(lesson, library, state, event)
        actions_seen += actions
    return state, actions_seen


def _blink_on_pin_12(lesson):
    return [["uno:12" if p == "uno:13" else p for p in c[:2]] for c in lesson.diagram()["connections"]]


def test_building_ahead_on_a_different_pin_is_announced_and_the_code_follows():
    lesson, library = load_lesson("blink"), load_library()
    state, actions = _play_whole_board(lesson, library, _blink_on_pin_12(lesson))
    assert state["finished"]
    assert [a for a in actions if a["type"] == "pin_substituted"], "the learner must be told they used pin 12"
    assert state["pin_substitutions"][0]["original"] == "uno:13" and state["pin_substitutions"][0]["actual"] == "uno:12"
    assert "pinMode(12, OUTPUT)" in engine._adjusted_code(lesson, state)


def test_led_builtin_in_the_sketch_is_rewritten_when_the_led_moves():
    """A generated Blink kept the official sketch's LED_BUILTIN (= 13 on an
    Uno): moving the LED to pin 12 must rewrite the constant too."""
    from core.lesson_gen import GeneratedLesson
    base = load_lesson("blink")
    code = "void setup() { pinMode(LED_BUILTIN, OUTPUT); }\nvoid loop() { digitalWrite(LED_BUILTIN, HIGH); delay(1000); digitalWrite(LED_BUILTIN, LOW); delay(1000); }\n"
    lesson = GeneratedLesson(base.data, base.diagram(), code)
    library = load_library()
    state, _ = _play_whole_board(lesson, library, _blink_on_pin_12(base))
    assert state["finished"]
    adjusted = engine._adjusted_code(lesson, state)
    assert "LED_BUILTIN" not in adjusted and "pinMode(12, OUTPUT)" in adjusted


def test_final_check_refuses_a_circuit_the_uploaded_code_would_not_drive(monkeypatch):
    """Safe and correctly wired isn't enough: if the sketch the learner will
    upload can't light their LED, the lesson isn't complete. Simulated by
    hiding the board's LED_BUILTIN pin, so the constant can't be rewritten."""
    from core.lesson_gen import GeneratedLesson
    base = load_lesson("blink")
    code = "void setup() { pinMode(LED_BUILTIN, OUTPUT); }\nvoid loop() { digitalWrite(LED_BUILTIN, HIGH); }\n"
    lesson = GeneratedLesson(base.data, base.diagram(), code)
    monkeypatch.setattr(engine, "_board_led_builtin", lambda parts: None)
    state, actions = _play_whole_board(lesson, load_library(), _blink_on_pin_12(base))
    assert not state["finished"]
    behaviour = [a for a in actions if a["type"] == "physics_hazard" and a["kind"] == "behaviour"]
    assert behaviour and "led1 would be dark" in behaviour[0]["message"]


def test_moved_pin_and_whole_board_built_ahead_together():
    """DigitalReadSerial with the button's signal on pin 3 and the whole
    board built before the first check: the pin swap must be found even
    though the pull-down resistor is already on that column."""
    lesson, library = load_lesson("digital-read-serial"), load_library()
    board = [["uno:3" if p == "uno:2" else p for p in c[:2]] for c in lesson.diagram()["connections"]]
    state, actions = _play_whole_board(lesson, library, board)
    assert state["finished"], [a for a in actions if a["type"] in ("feedback", "substitution_refused", "physics_hazard")]
    code = engine._adjusted_code(lesson, state)
    assert "digitalRead(3)" in code and "digitalRead(2)" not in code


def test_turned_round_button_on_a_moved_pin_gets_the_right_code():
    """Button turned round + pin 3 + built ahead: the code adjustment must
    look the leg up by its physical (turned-round) identity."""
    lesson, library = load_lesson("digital-read-serial"), load_library()
    turn = {"btn1:1.l": "btn1:2.l", "btn1:1.r": "btn1:2.r", "btn1:2.l": "btn1:1.l", "btn1:2.r": "btn1:1.r"}
    board = [[turn.get(p, "uno:3" if p == "uno:2" else p) for p in c[:2]] for c in lesson.diagram()["connections"]]
    state, actions = _play_whole_board(lesson, library, board)
    assert state["finished"], [a for a in actions if a["type"] in ("feedback", "substitution_refused", "physics_hazard")]
    assert state["orientations"]["btn1"] == "swapped"
    code = engine._adjusted_code(lesson, state)
    assert "digitalRead(3)" in code and "digitalRead(2)" not in code


def test_pin_owner_is_deterministic_and_knows_its_own_component():
    """A net holding several components (button + pull-down on pin 2) used
    to return whichever came first in a set — hash-order dependent."""
    pairs = [["uno:2", "bb1:6t.c"], ["btn1:1.l", "bb1:6t.d"], ["r1:1", "bb1:6t.e"]]
    from core import checker
    alias = checker.board_alias_map(load_lesson("digital-read-serial").diagram()["parts"])
    conn = {"bb1"}
    assert engine._pin_owner(pairs, "uno:2", alias, conn, for_component="btn1") == "btn1"
    assert engine._pin_owner(pairs, "uno:2", alias, conn, for_component="r1") == "r1"
    assert engine._pin_owner(pairs, "uno:2", alias, conn) == "btn1"   # sorted, not hash order
