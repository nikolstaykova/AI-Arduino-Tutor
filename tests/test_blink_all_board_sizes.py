"""Exhaustive coverage of Blink's three connections (r1:1<->uno:13,
led1:A<->r1:2, led1:C<->uno:GND) across all three breadboard sizes
(full/half/mini) — user request: confirm the checking algorithm works
with any breadboard size without breaking, and cover every possible
correct/harmless/wrong combo for the LED and resistor.

Column number never affects correctness (only the separate
plausibility_warning cares about board size) — already proven generally
in test_mini_board_exhaustive.py for analog-read-serial. This file proves
it specifically for Blink's own topology, including its one genuinely
different connection (component-to-component, no Arduino pin on either
side), across every board size, not just mini.
"""
import pytest

from core import engine
from core.engine import BREADBOARD_VARIANTS
from core.library import load_library
from core.lesson import load_lesson

BOARD_SIZES = ["full", "half", "mini"]
MAX_COLUMN = {size: BREADBOARD_VARIANTS[size]["max_column_estimate"] for size in BOARD_SIZES}


@pytest.fixture(scope="module")
def library():
    return load_library()


@pytest.fixture(scope="module")
def lesson():
    return load_lesson("blink")


def send(lesson, library, state, event):
    return engine.handle_event(lesson, library, state, event)


def _feedback_and_warning(actions):
    fb = next((a for a in actions if a["type"] == "feedback"), None)
    warn = [a for a in actions if a["type"] == "plausibility_warning"]
    return (fb["verdict"] if fb else "pass"), warn


def _fresh(lesson, library, board_size):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "board", "variant": board_size})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    return state


# ---------------------------------------------------------------------------
# A) r1:1 <-> uno:13, every valid column, on every board size
# ---------------------------------------------------------------------------

STEP1_CASES = [(size, col) for size in BOARD_SIZES for col in range(1, MAX_COLUMN[size] + 1)]


@pytest.mark.parametrize("board_size,col", STEP1_CASES)
def test_resistor_to_pin13_every_valid_column_every_board_size(lesson, library, board_size, col):
    state = _fresh(lesson, library, board_size)
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:1", f"bb1:{col}t.a"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    verdict, warnings = _feedback_and_warning(actions)
    assert verdict == "pass", (board_size, col, actions)
    assert not warnings

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:1", f"bb1:{col}t.a"], ["uno:13", f"bb1:{col}t.c"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    verdict, warnings = _feedback_and_warning(actions)
    assert verdict == "pass", (board_size, col, actions)
    assert not warnings
    assert lesson.step(state["step_index"])["id"] == "step-2"


# ---------------------------------------------------------------------------
# B) led1:A <-> r1:2 (component-to-component, no landing), every column,
#    every board size — the one genuinely novel connection in this lesson
# ---------------------------------------------------------------------------

STEP2_CASES = [(size, col) for size in BOARD_SIZES for col in range(1, MAX_COLUMN[size] + 1)]


@pytest.mark.parametrize("board_size,col", STEP2_CASES)
def test_led_to_resistor_every_valid_column_every_board_size(lesson, library, board_size, col):
    state = _fresh(lesson, library, board_size)
    for _ in range(2):  # step-1a, step-1b -> lands at step-2
        state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
        state, _ = send(lesson, library, state, {"command": "done"})

    pairs = [["led1:A", f"bb1:{col}t.i"], ["r1:2", f"bb1:{col}t.h"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    verdict, warnings = _feedback_and_warning(actions)
    assert verdict == "pass", (board_size, col, actions)
    assert not warnings
    assert lesson.step(state["step_index"])["id"] == "step-3"


# ---------------------------------------------------------------------------
# C) led1:C <-> uno:GND (no landing), every column, every board size
# ---------------------------------------------------------------------------

STEP3_CASES = [(size, col) for size in BOARD_SIZES for col in range(1, MAX_COLUMN[size] + 1)]


@pytest.mark.parametrize("board_size,col", STEP3_CASES)
def test_led_to_gnd_every_valid_column_every_board_size(lesson, library, board_size, col):
    state = _fresh(lesson, library, board_size)
    for _ in range(3):  # step-1a, step-1b, step-2 -> lands at step-3
        state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
        state, _ = send(lesson, library, state, {"command": "done"})
    assert lesson.step(state["step_index"])["id"] == "step-3"

    pairs = [["led1:C", f"bb1:{col}t.i"], ["uno:GND.1", f"bb1:{col}t.g"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    verdict, warnings = _feedback_and_warning(actions)
    assert verdict == "pass", (board_size, col, actions)
    assert not warnings
    assert state["phase"] == "upload"


# ---------------------------------------------------------------------------
# D) The classic same-column-opposite-side-of-gap mistake, every board size
# ---------------------------------------------------------------------------

SPOT_COLUMNS = {"full": [1, 30, 63], "half": [1, 15, 30], "mini": [1, 9, 17]}
GAP_MISTAKE_CASES = [(size, col) for size in BOARD_SIZES for col in SPOT_COLUMNS[size]]


@pytest.mark.parametrize("board_size,col", GAP_MISTAKE_CASES)
def test_same_column_opposite_side_of_gap_is_wrong_every_board_size(lesson, library, board_size, col):
    state = _fresh(lesson, library, board_size)
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:1", f"bb1:{col}t.a"]]})
    state, _ = send(lesson, library, state, {"command": "done"})

    pairs = [["r1:1", f"bb1:{col}t.a"], ["uno:13", f"bb1:{col}b.f"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    verdict, _ = _feedback_and_warning(actions)
    assert verdict == "wrong", (board_size, col, actions)


# ---------------------------------------------------------------------------
# E) Past-the-max column: verdict unaffected, but the warning is specific
#    to the DECLARED board's own estimate, not some other size's
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("board_size", BOARD_SIZES)
def test_column_past_this_boards_own_max_warns_specifically(lesson, library, board_size):
    over_col = MAX_COLUMN[board_size] + 5
    state = _fresh(lesson, library, board_size)
    pairs = [["r1:1", f"bb1:{over_col}t.a"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    verdict, warnings = _feedback_and_warning(actions)
    assert verdict == "pass"  # correctness never depends on this estimate
    assert warnings, (board_size, over_col)
    assert str(over_col) in warnings[0]["message"]
    assert board_size in warnings[0]["message"]


@pytest.mark.parametrize("declared_size,detected_size", [("mini", "full"), ("half", "full"), ("mini", "half")])
def test_a_column_valid_on_a_bigger_board_warns_only_when_a_smaller_one_is_declared(lesson, library, declared_size, detected_size):
    """The exact cross-board-size scenario from the user's own earlier
    question: a column fine on a bigger board can still be flagged if a
    SMALLER board was declared, since it wouldn't fit that one."""
    col = MAX_COLUMN[detected_size]  # valid for detected_size, likely too big for declared_size
    assert col > MAX_COLUMN[declared_size], "test setup: pick sizes where this is actually out of range"
    state = _fresh(lesson, library, declared_size)
    pairs = [["r1:1", f"bb1:{col}t.a"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    verdict, warnings = _feedback_and_warning(actions)
    assert verdict == "pass"
    assert warnings


def test_case_counts():
    assert len(STEP1_CASES) == 63 + 30 + 17
    assert len(STEP2_CASES) == 63 + 30 + 17
    assert len(STEP3_CASES) == 63 + 30 + 17
