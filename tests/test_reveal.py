"""'Reveal step': the engine hands back exactly what the current step needs
connected — with the learner's own swapped pins applied — and it counts as
a hint (so it costs the no-hints star)."""
from core import engine, progress
from core.lesson import load_lesson
from core.library import load_library

LIB = load_library()


def _to_step(lesson, target_id, board=()):
    state, _ = engine.handle_event(lesson, LIB, engine.initial_state(), {"command": "start"})
    state, _ = engine.handle_event(lesson, LIB, state, {"command": "done"})
    for _ in range(12):
        if lesson.step(state["step_index"])["id"] == target_id:
            return state
        state, _ = engine.handle_event(lesson, LIB, state, {"command": "done", "detected_pairs": list(board), "snapshot": True})
    raise AssertionError("never reached " + target_id)


def test_reveal_on_a_wiring_step_gives_the_exact_connection():
    lesson = load_lesson("blink")
    state = _to_step(lesson, "step-1a")
    state, actions = engine.handle_event(lesson, LIB, state, {"command": "reveal"})
    assert actions == [{"type": "reveal", "step": "step-1a", "pairs": [], "landing": ["r1:1"]}]
    state, _ = engine.handle_event(lesson, LIB, state, {"command": "done", "detected_pairs": [["r1:1", "bb1:3b.h"], ["r1:2", "bb1:7b.h"]], "snapshot": True})
    state, actions = engine.handle_event(lesson, LIB, state, {"command": "reveal"})
    assert actions[0]["pairs"] == [["r1:1", "uno:13"]]
    assert state["hints_used"] == 1          # the hint counter is per step


def test_reveal_follows_a_pin_the_learner_swapped():
    lesson = load_lesson("blink")
    state = _to_step(lesson, "step-1a")
    board = [["r1:1", "bb1:3b.h"], ["r1:2", "bb1:7b.h"]]
    state, _ = engine.handle_event(lesson, LIB, state, {"command": "done", "detected_pairs": board, "snapshot": True})
    board += [["bb1:3b.j", "uno:12"]]                       # pin 12 instead of 13
    state, _ = engine.handle_event(lesson, LIB, state, {"command": "done", "detected_pairs": board, "snapshot": True})
    assert lesson.step(state["step_index"])["id"] == "step-2"
    state, _ = engine.handle_event(lesson, LIB, state, {"command": "previous"})
    state, actions = engine.handle_event(lesson, LIB, state, {"command": "reveal"})
    assert actions[0]["pairs"] == [["r1:1", "uno:12"]]


def test_reveal_counts_as_a_hint_when_scoring():
    lesson = load_lesson("blink")
    events = [{"command": "start"}, {"command": "done"}, {"command": "reveal"}]
    score = progress.score_session(lesson, LIB, events)
    assert score["hints"] == 1


def test_nothing_to_reveal_outside_a_build_step():
    lesson = load_lesson("blink")
    state, _ = engine.handle_event(lesson, LIB, engine.initial_state(), {"command": "start"})
    state, actions = engine.handle_event(lesson, LIB, state, {"command": "reveal"})
    assert actions[0]["type"] == "error"
