"""User request: with a `mini` breadboard specifically stated (COMMANDS.md
`board` command), exhaustively test that pass/harmless/wrong still comes
out right across every valid column, the t/b gap boundary, and the
plausibility-warning column cutoff — not just the abstracted
same_strip/different_strip categories used in test_exhaustive_wire1_variations.py,
but real literal mini-board holes across mini's actual ~17-column range
(core.engine.BREADBOARD_VARIANTS).
"""
import pytest

from core import engine
from core.engine import BREADBOARD_VARIANTS
from core.library import load_library
from core.lesson import load_lesson

MINI_MAX_COLUMN = BREADBOARD_VARIANTS["mini"]["max_column_estimate"]  # 17
T_LETTERS = "abcde"
B_LETTERS = "fghij"
ALL_MINI_HOLES = [
    f"{col}{side}.{letter}"
    for col in range(1, MINI_MAX_COLUMN + 1)
    for side, letters in (("t", T_LETTERS), ("b", B_LETTERS))
    for letter in letters
]  # every physical hole on a mini board: 17 columns x 2 sides x 5 letters = 170


@pytest.fixture(scope="module")
def library():
    return load_library()


@pytest.fixture(scope="module")
def lesson():
    return load_lesson("analog-read-serial")


def send(lesson, library, state, event):
    return engine.handle_event(lesson, library, state, event)


def _fresh_mini_state(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, board_actions = send(lesson, library, state, {"command": "board", "variant": "mini"})
    assert board_actions[0] == {"type": "board_set", "variant": "mini"}
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    return state


def _feedback_and_warning(actions):
    feedback = next((a for a in actions if a["type"] == "feedback"), None)
    warnings = [a for a in actions if a["type"] == "plausibility_warning"]
    return feedback, warnings


def _safe_columns(*taken):
    """Two columns guaranteed distinct from each other and from every
    column in `taken` -- for VCC/SIG landing columns in a test that's
    sweeping GND's own column across the whole mini range and must never
    accidentally self-short by reusing it."""
    taken = set(taken)
    picked = []
    candidate = 1
    while len(picked) < 2:
        if candidate not in taken and candidate not in picked:
            picked.append(candidate)
        candidate += 1
    return picked


# ---------------------------------------------------------------------------
# A) Every valid mini-board column (1..17) must land pot1:GND correctly,
#    with no plausibility warning — no per-column bug, no boundary bug.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("col", range(1, MINI_MAX_COLUMN + 1))
def test_every_valid_mini_column_lands_correctly_no_warning(lesson, library, col):
    """step-1a is a combined multi-leg landing check (PARTS.md's
    legs_placed_together) — VCC/SIG stay at fixed, safe columns (not
    under test here) while GND's own column varies across mini's range."""
    state = _fresh_mini_state(lesson, library)
    vcc_col, sig_col = _safe_columns(col)
    pairs = [["pot1:GND", f"bb2:{col}t.a"], ["pot1:VCC", f"bb2:{vcc_col}t.a"], ["pot1:SIG", f"bb2:{sig_col}t.a"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback, warnings = _feedback_and_warning(actions)
    assert feedback is None  # pass, no feedback action at all
    assert not warnings, f"column {col} is within mini's own range, must not warn"
    assert state["step_index"] == 2


# ---------------------------------------------------------------------------
# A2) Every single physical hole on the mini board (all 170 of them, both
#     sides, every letter) must land pot1:GND correctly — not just one
#     representative letter per column.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hole", ALL_MINI_HOLES)
def test_every_physical_hole_on_the_mini_board_lands_correctly(lesson, library, hole):
    state = _fresh_mini_state(lesson, library)
    col = int("".join(ch for ch in hole.split(".", 1)[0] if ch.isdigit()))
    vcc_col, sig_col = _safe_columns(col)
    pairs = [["pot1:GND", f"bb2:{hole}"], ["pot1:VCC", f"bb2:{vcc_col}t.a"], ["pot1:SIG", f"bb2:{sig_col}t.a"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback, warnings = _feedback_and_warning(actions)
    assert feedback is None, f"hole {hole} should land pot1:GND cleanly"
    assert not warnings
    assert state["step_index"] == 2


# ---------------------------------------------------------------------------
# B) Every valid mini-board column, used for BOTH ends of the wiring step,
#    must pass — same strip is same strip regardless of which column.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("col", range(1, MINI_MAX_COLUMN + 1))
def test_every_valid_mini_column_wires_correctly_no_warning(lesson, library, col):
    state = _fresh_mini_state(lesson, library)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b
    pairs = [["pot1:GND", f"bb2:{col}t.a"], ["uno:GND.1", f"bb2:{col}t.c"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback, warnings = _feedback_and_warning(actions)
    assert feedback is None
    assert not warnings
    assert state["step_index"] == 3


# ---------------------------------------------------------------------------
# B2) Every pair of distinct holes within the SAME strip (any letter on
#     one end, any letter on the other, across every column and side) must
#     wire correctly — the five holes in a strip are supposed to be
#     electrically identical, and this checks all of them, not a sample.
# ---------------------------------------------------------------------------

SAME_STRIP_HOLE_PAIRS = [
    (col, side, l1, l2)
    for col in range(1, MINI_MAX_COLUMN + 1)
    for side, letters in (("t", T_LETTERS), ("b", B_LETTERS))
    for l1 in letters
    for l2 in letters
]  # 17 columns x 2 sides x 5 x 5 = 850 letter-pairs, every strip fully covered


@pytest.mark.parametrize("col,side,l1,l2", SAME_STRIP_HOLE_PAIRS)
def test_every_hole_pair_within_a_mini_strip_wires_correctly(lesson, library, col, side, l1, l2):
    state = _fresh_mini_state(lesson, library)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b
    pairs = [["pot1:GND", f"bb2:{col}{side}.{l1}"], ["uno:GND.1", f"bb2:{col}{side}.{l2}"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback, warnings = _feedback_and_warning(actions)
    assert feedback is None, f"strip {col}{side} (holes .{l1}/.{l2}) should wire cleanly"
    assert not warnings
    assert state["step_index"] == 3


# ---------------------------------------------------------------------------
# C) Same column NUMBER, opposite sides of the center gap (Nt vs Nb), is
#    the classic "looks connected but isn't" mistake — must be wrong, at
#    every valid mini column, not just one hand-picked example.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("col", range(1, MINI_MAX_COLUMN + 1))
def test_same_column_number_opposite_side_of_gap_is_wrong_on_mini(lesson, library, col):
    state = _fresh_mini_state(lesson, library)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b
    pairs = [["pot1:GND", f"bb2:{col}t.a"], ["uno:GND.1", f"bb2:{col}b.f"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback, _ = _feedback_and_warning(actions)
    assert feedback is not None and feedback["verdict"] == "wrong"
    assert state["step_index"] == 2  # blocked


# ---------------------------------------------------------------------------
# D) Past mini's estimated max column: correctness is unaffected (strip-
#    agnostic design doesn't care), but the plausibility warning MUST fire,
#    naming the actual column and "mini".
# ---------------------------------------------------------------------------

OUT_OF_RANGE_MINI_COLUMNS = [MINI_MAX_COLUMN + 1, MINI_MAX_COLUMN + 3, 25, 30, 63]


@pytest.mark.parametrize("col", OUT_OF_RANGE_MINI_COLUMNS)
def test_column_past_minis_range_still_passes_but_warns(lesson, library, col):
    state = _fresh_mini_state(lesson, library)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b
    pairs = [["pot1:GND", f"bb2:{col}t.a"], ["uno:GND.1", f"bb2:{col}t.c"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback, warnings = _feedback_and_warning(actions)
    assert feedback is None  # still a pass — the verdict never depends on this estimate
    assert warnings, f"column {col} exceeds mini's ~{MINI_MAX_COLUMN}-column estimate, should warn"
    assert str(col) in warnings[0]["message"]
    assert "mini" in warnings[0]["message"]
    assert state["step_index"] == 3


def test_column_exactly_at_minis_max_does_not_warn(lesson, library):
    """Boundary check: the max estimate itself is still in-range, not
    out-of-range — no off-by-one at the edge."""
    state = _fresh_mini_state(lesson, library)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})
    pairs = [["pot1:GND", f"bb2:{MINI_MAX_COLUMN}t.a"], ["uno:GND.1", f"bb2:{MINI_MAX_COLUMN}t.c"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    _, warnings = _feedback_and_warning(actions)
    assert not warnings


# ---------------------------------------------------------------------------
# E) Pot-pin discrimination (correct / symmetric-harmless / wrong) must
#    hold on a mini board exactly as it does anywhere else — spot-checked
#    at both ends of the valid column range.
# ---------------------------------------------------------------------------

POT_PINS_AND_VERDICTS = [("GND", "pass"), ("VCC", "harmless"), ("SIG", "wrong")]


@pytest.mark.parametrize("col", [1, MINI_MAX_COLUMN])
def test_self_short_between_two_legs_is_still_caught_at_boundary_columns(lesson, library, col):
    """step-1a is a combined multi-leg landing check now (PARTS.md's
    legs_placed_together), checking all three of the potentiometer's real
    leg identities at once rather than discriminating "which identity
    fills this one slot" — so the old per-pin-slot discrimination this
    test used to exhaust doesn't apply at landing time any more (it's
    still fully exercised at the WIRING level, see
    test_pot_pin_discrimination_holds_on_mini_wiring below). What DOES
    still matter at landing time, and is worth exhausting at both column
    boundaries: a genuine self-short between two of the SAME component's
    own legs (here, GND and VCC sharing a column) must still be caught."""
    state = _fresh_mini_state(lesson, library)
    sig_col = _safe_columns(col)[0]
    pairs = [["pot1:GND", f"bb2:{col}t.a"], ["pot1:VCC", f"bb2:{col}t.a"], ["pot1:SIG", f"bb2:{sig_col}t.a"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback, warnings = _feedback_and_warning(actions)
    assert not warnings  # col is 1 or MINI_MAX_COLUMN, both in-range
    assert feedback is not None and feedback["verdict"] == "wrong"
    assert state["step_index"] == 1  # blocked


@pytest.mark.parametrize("col", [1, MINI_MAX_COLUMN])
@pytest.mark.parametrize("pin,expected", POT_PINS_AND_VERDICTS)
def test_pot_pin_discrimination_holds_on_mini_wiring(lesson, library, col, pin, expected):
    state = _fresh_mini_state(lesson, library)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b
    pairs = [[f"pot1:{pin}", f"bb2:{col}t.a"], ["uno:GND.1", f"bb2:{col}t.c"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback, warnings = _feedback_and_warning(actions)
    assert not warnings

    if expected == "pass":
        assert feedback is None
        assert state["step_index"] == 3
    elif expected == "harmless":
        assert feedback is not None and feedback["verdict"] == "harmless"
        assert state["step_index"] == 3
    else:
        assert feedback is not None and feedback["verdict"] == "wrong"
        assert state["step_index"] == 2
