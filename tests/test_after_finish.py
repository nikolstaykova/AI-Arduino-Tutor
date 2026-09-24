"""After a lesson is completed the bench stays open. Breaking the circuit
(or stepping back) must be judged honestly — `finished` means the LAST
check passed, not "passed once, ever"."""
from core import engine
from core.lesson import load_lesson
from core.library import load_library
from core.scenarios import Board


def _finish(lesson_id):
    lesson, library = load_lesson(lesson_id), load_library()
    board = Board(lesson, library)
    state, _ = engine.handle_event(lesson, library, engine.initial_state(), {"command": "start"})
    for _ in range(3 * lesson.step_count() + 4):
        if state["finished"]:
            break
        if state["phase"] in ("gather", "upload"):
            state, _ = engine.handle_event(lesson, library, state, {"command": "done"})
            continue
        wanted = board.full() if state["phase"] == "final_check" else board.upto(state["step_index"])
        state, _ = engine.handle_event(lesson, library, state, {"command": "done", "detected_pairs": wanted, "snapshot": True})
    assert state["finished"]
    return lesson, library, board, state


def _check(lesson, library, state, pairs):
    return engine.handle_event(lesson, library, state, {"command": "done", "detected_pairs": pairs, "snapshot": True})


def test_breaking_the_circuit_after_finishing_is_wrong_not_a_celebration():
    lesson, library, board, state = _finish("blink")
    broken = [p for p in board.full() if "uno:13" not in p]
    state, actions = _check(lesson, library, state, broken)
    assert not state["finished"]
    assert not any(a["type"] == "complete" for a in actions)
    assert any(a["type"] in ("feedback", "connection_lost") and a.get("verdict", "wrong") == "wrong" for a in actions)


def test_a_stray_wrong_wire_after_finishing_is_wrong():
    lesson, library, board, state = _finish("blink")
    state, actions = _check(lesson, library, state, board.full() + [["bb1:tp.1", "uno:GND.1"], ["bb1:tp.2", "uno:5V"]])
    assert not state["finished"] and not any(a["type"] == "complete" for a in actions)


def test_putting_it_right_again_completes_again():
    lesson, library, board, state = _finish("blink")
    state, _ = _check(lesson, library, state, [p for p in board.full() if "uno:13" not in p])
    state, actions = _check(lesson, library, state, board.full())
    assert state["finished"] and any(a["type"] == "complete" for a in actions)


def test_stepping_back_after_finishing_reopens_the_lesson():
    lesson, library, board, state = _finish("blink")
    state, _ = engine.handle_event(lesson, library, state, {"command": "previous"})
    assert not state["finished"]                       # back at upload: reopened
    while state["phase"] != "build":
        state, _ = engine.handle_event(lesson, library, state, {"command": "previous"})
    wrong = [p for p in board.upto(state["step_index"]) if "uno:GND" not in "".join(p)][:-1]
    state, actions = _check(lesson, library, state, wrong)
    assert not state["finished"] and not any(a["type"] == "complete" for a in actions)
