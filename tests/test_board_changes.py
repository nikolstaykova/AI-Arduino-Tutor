"""Every whole-board check compares the board with the last confirmed one
and handles what changed — a moved pin is announced right away, a stray new
connection is flagged when it appears, a part turned round after it was
locked is followed — then runs the full check as before."""
from core import engine
from core.lesson import load_lesson
from core.library import load_library
from core.scenarios import Board


def _play(lesson_id, board_at):
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
        state, actions = engine.handle_event(lesson, library, state,
                                             {"command": "done", "detected_pairs": board_at(sid, wanted), "snapshot": True})
        log.append((sid, actions))
    return state, log


def _types(log, sid):
    return [a["type"] for s, acts in log if s == sid for a in acts]


def test_a_pin_moved_after_its_step_is_announced_at_the_next_check():
    def board_at(sid, board):
        if sid in ("step-2", "step-3", "final_check"):
            return [["uno:12" if p == "uno:13" else p for p in c] for c in board]
        return board
    state, log = _play("blink", board_at)
    assert state["finished"]
    assert "pin_substituted" in _types(log, "step-2")          # told straight away, not at the end
    assert "pin_substituted" not in _types(log, "final_check")  # and not again
    assert "pinMode(12, OUTPUT)" in engine._adjusted_code(load_lesson("blink"), state)


def test_a_stray_wire_is_flagged_when_it_appears_and_cleared_when_removed():
    stray = ["bb1:6b.j", "uno:5V"]    # the LED anode's column straight to 5V: not part of Blink
    shown = {"once": False}

    def board_at(sid, board):
        if sid == "step-3" and not shown["once"]:
            shown["once"] = True
            return board + [stray]
        return board
    state, log = _play("blink", board_at)
    first_step3 = next(acts for s, acts in log if s == "step-3")
    assert any(a["type"] == "stray_connection" and "Arduino pin 5V" in a["message"] for a in first_step3)
    assert any(a["type"] == "feedback" and a["verdict"] == "wrong" for a in first_step3)
    assert state["finished"]


def test_a_locked_part_turned_round_later_is_followed():
    """The resistor is locked 'straight' at step-1b; the learner then turns
    it round. The engine notices, flips the lock, and the lesson finishes."""
    turn = {"r1:1": "r1:2", "r1:2": "r1:1"}

    def board_at(sid, board):
        if sid in ("step-2", "step-3", "final_check"):
            return [[turn.get(p, p) for p in c] for c in board]
        return board
    state, log = _play("blink", board_at)
    assert "part_turned" in _types(log, "step-2")
    assert state["orientations"]["r1"] == "swapped"
    assert state["finished"]


def test_final_check_summarises_what_changed_since_the_last_check():
    def board_at(sid, board):
        if sid == "final_check":
            return [["uno:12" if p == "uno:13" else p for p in c] for c in board]
        return board
    state, log = _play("blink", board_at)
    summary = [a for s, acts in log if s == "final_check" for a in acts if a["type"] == "board_changes"]
    assert summary and "uno:13" in summary[0]["message"] and "uno:12" in summary[0]["message"]
    assert state["finished"]
