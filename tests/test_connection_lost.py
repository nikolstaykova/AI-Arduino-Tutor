"""On every whole-board check the engine confirms that everything earlier
steps confirmed is still there. A wire that came loose or a part that was
pulled out is named straight away, not only at final_check."""
from core import engine
from core.lesson import load_lesson
from core.library import load_library
from core.scenarios import Board


def _play(lesson_id, board_at):
    """board_at(step_id, board_for_step) -> the board the learner shows."""
    lesson, library = load_lesson(lesson_id), load_library()
    board = Board(lesson, library)
    state = engine.initial_state()
    state, _ = engine.handle_event(lesson, library, state, {"command": "start"})
    log = []
    for _ in range(3 * lesson.step_count() + 4):
        if state["finished"]:
            break
        if state["phase"] in ("gather", "upload"):
            state, _ = engine.handle_event(lesson, library, state, {"command": "done"})
            continue
        step = lesson.step(state["step_index"])
        sid = step["id"] if step else "final_check"
        wanted = board.full() if state["phase"] == "final_check" else board.upto(state["step_index"])
        shown = board_at(sid, wanted)
        state, actions = engine.handle_event(lesson, library, state,
                                             {"command": "done", "detected_pairs": shown, "snapshot": True})
        log.append((sid, actions))
    return state, log


def test_a_wire_that_comes_loose_is_named_at_the_next_check_and_the_lesson_continues():
    loose = {"on": True}
    wire = ["bb1:3b.g", "uno:13"]

    def board_at(sid, board):
        if sid == "step-2" and loose["on"]:
            loose["on"] = False            # shown once without the wire, then put back
            return [c for c in board if c != wire]
        return board
    state, log = _play("blink", board_at)
    lost = [a for sid, acts in log for a in acts if a["type"] == "connection_lost"]
    assert len(lost) == 1 and lost[0]["step"] == "step-1b"
    assert "r1's 1 leg" in lost[0]["message"] and "Arduino pin 13" in lost[0]["message"]
    assert state["finished"]


def test_one_resistor_leg_popping_out_is_named_even_though_the_other_leg_could_count():
    shown_once = {"done": False}

    def board_at(sid, board):
        if sid == "step-1b" and not shown_once["done"]:
            shown_once["done"] = True
            return [c for c in board if c[0] != "r1:1"]
        return board
    state, log = _play("blink", board_at)
    first = log[1][1]   # step-1b's first check
    assert any(a["type"] == "connection_lost" and "r1's 1 leg" in a["message"] for a in first), first
    assert state["finished"]


def test_moving_a_wire_to_another_free_pin_is_not_a_lost_connection():
    """A change of mind (pin 13 → 12 after its step) is a substitution, not
    a loose wire: no connection_lost, the lesson finishes on pin 12."""
    def board_at(sid, board):
        if sid in ("step-2", "step-3", "final_check"):
            return [["uno:12" if p == "uno:13" else p for p in c] for c in board]
        return board
    state, log = _play("blink", board_at)
    assert not [a for _, acts in log for a in acts if a["type"] == "connection_lost"]
    assert state["finished"]
    assert "pinMode(12, OUTPUT)" in engine._adjusted_code(load_lesson("blink"), state)


def test_partial_sim_input_is_unaffected():
    """The CLI's `sim` sends only one step's pairs, so the engine can't tell
    what's missing — no loss check there, as before."""
    lesson, library = load_lesson("blink"), load_library()
    state = engine.initial_state()
    for event in ({"command": "start"}, {"command": "done"},
                  {"command": "done", "label": "correct"}, {"command": "done", "label": "correct"}):
        state, actions = engine.handle_event(lesson, library, state, event)
    assert not any(a["type"] == "connection_lost" for a in actions)
