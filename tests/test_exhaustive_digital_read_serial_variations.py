"""Exhaustive (not sampled) coverage of every meaningfully distinct way a
learner could wire DigitalReadSerial, across all four build steps —
matching the standard already set for AnalogReadSerial
(test_exhaustive_wire1_variations.py) and Blink
(test_exhaustive_blink_variations.py), the two lessons that already had
this depth of coverage before this file closed the gap for the third.

"Exhaustive" here means every *meaningfully distinct* choice, not every
literal hole number — the specific column/row never affects correctness,
only:
  - which leg of the pushbutton or resistor was used,
  - which Arduino pin was used (including every GND alias),
  - whether the two ends of a wiring step actually share a strip.

Real facts this lesson exercises that the other two don't:
  - within one contact group (1.l/1.r, or 2.l/2.r) the legs are a true
    board-pin-alias FOLD (silent pass using either leg), verified
    against docs.wokwi.com/parts/wokwi-pushbutton.
  - the two contact GROUPS themselves are interchangeable (a momentary
    switch works either way round): a declared group swap, harmless —
    but only while nothing else fixes which group is which (once group 2
    is on 5V, putting pin 2 on group 2 too is a real short, still wrong).
  - the resistor's two legs ARE a declared symmetric swap (harmless),
    the same as every other lesson's resistor.
  - step-3 is a genuine component-to-component connection with no
    separate wire of its own (sharing a breadboard column IS the
    connection) — same shape as Blink's LED-to-resistor step, but the
    first time this project has combined that with an aliased contact
    group as one of the two endpoints.
"""
import pytest

from core import engine
from core.library import load_library
from core.lesson import load_lesson


@pytest.fixture(scope="module")
def library():
    return load_library()


@pytest.fixture(scope="module")
def lesson():
    return load_lesson("digital-read-serial")


def send(lesson, library, state, event):
    return engine.handle_event(lesson, library, state, event)


def _assert_verdict(actions, state, expected, advanced_step_index):
    feedback = next((a for a in actions if a["type"] == "feedback"), None)
    if expected == "wrong":
        assert feedback is not None and feedback["verdict"] == "wrong", actions
        assert state["step_index"] != advanced_step_index  # blocked
    elif expected == "harmless":
        assert feedback is not None and feedback["verdict"] == "harmless", actions
        assert state["step_index"] == advanced_step_index  # flagged but advanced
    else:
        assert feedback is None, actions
        assert state["step_index"] == advanced_step_index  # advanced silently


# ---------------------------------------------------------------------------
# step-1a: landing check (expected_landing = "btn1:2.r")
# ---------------------------------------------------------------------------

BTN_LEGS = ["1.l", "1.r", "2.l", "2.r"]
LANDING_DESTINATIONS = ["breadboard", "arduino_pin", "nothing"]

LANDING_CASES = [(leg, dest) for leg in BTN_LEGS for dest in LANDING_DESTINATIONS]


def _expected_landing_verdict(leg):
    # The pushbutton's contact groups are a true alias fold (verified
    # docs), not a symmetric declaration -- either leg of the CORRECT
    # group (2) is a silent pass; the other group (1) is a real mistake,
    # never "harmless".
    return "pass" if leg in ("2.l", "2.r") else "wrong"


@pytest.mark.parametrize("leg,dest", LANDING_CASES)
def test_every_landing_variation_for_step_1a(lesson, library, leg, dest):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    assert state["step_index"] == 1

    used_pin = f"btn1:{leg}"
    if dest == "breadboard":
        # step-1a is now a combined multi-leg landing check for BOTH
        # contact groups at once (PARTS.md's legs_placed_together) --
        # group 1 lands correctly, isolating this test's own dimension
        # (which alias of group 2 was used) same as before.
        pairs = [[used_pin, "bb1:4b.a"], ["btn1:1.r", "bb1:5b.a"]]
    elif dest == "arduino_pin":
        # Deliberately NOT the paired step-1b's own correct target (5V) --
        # that would trigger the separate breadboard-bypass acceptance
        # path (see test_breadboard_bypass_accepts_the_aliased_leg_too
        # below) rather than isolating this landing-destination
        # dimension on its own, same choice wire1's own exhaustive file
        # already makes (uno:A0, never the wire's real target).
        pairs = [[used_pin, "uno:A0"]]
    else:
        pairs = []

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    expected = _expected_landing_verdict(leg) if dest == "breadboard" else "wrong"
    _assert_verdict(actions, state, expected, advanced_step_index=2)


@pytest.mark.parametrize("leg", ["2.l", "2.r"])
def test_breadboard_bypass_accepts_the_aliased_leg_too(lesson, library, leg):
    """New combination this exhaustive file's own main matrix deliberately
    avoids (see the comment above): a leg wired DIRECTLY to its correct
    final Arduino pin, skipping the breadboard, is accepted as a tracked
    'bypass' rather than 'wrong' — never explicitly confirmed before for
    the pushbutton's ALIASED leg specifically (2.l, not just the
    lesson's own scripted 2.r)."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    # Group 1 lands normally on the breadboard; group 2's aliased leg
    # bypasses straight to its own correct Arduino pin (5V).
    pairs = [[f"btn1:{leg}", "uno:5V"], ["btn1:1.r", "bb1:5b.a"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert any(a["type"] == "breadboard_bypassed" for a in actions), actions
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    assert state["step_index"] == 2  # advanced to step-1b


# ---------------------------------------------------------------------------
# step-1b: wiring check (expected_nets = [["btn1:2.r", "uno:5V"]])
# ---------------------------------------------------------------------------

ARDUINO_TARGETS_1B = ["5V", "GND.1", "GND.2", "GND.3", "A0", "2", "nothing"]
ROUTING = ["direct", "same_strip", "different_strip"]

WIRING_1B_CASES = [
    (leg, target, routing) for leg in BTN_LEGS for target in ARDUINO_TARGETS_1B for routing in ROUTING
]


def _expected_wiring_1b_verdict(leg, target, routing):
    if target == "nothing" or routing == "different_strip":
        return "wrong"
    if target != "5V":
        return "wrong"
    # Nothing is on the button yet, so either contact group can take 5V:
    # a real momentary switch works identically either way round. The
    # scripted group (2) is a silent pass; the other group (1) is the
    # declared group swap (library symmetric_pins [["1","2"]]) — harmless.
    return "pass" if leg in ("2.l", "2.r") else "harmless"


@pytest.mark.parametrize("leg,target,routing", WIRING_1B_CASES)
def test_every_wiring_variation_for_step_1b(lesson, library, leg, target, routing):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b
    assert state["step_index"] == 2

    used_pin = f"btn1:{leg}"
    if target == "nothing":
        pairs = []
    elif routing == "direct":
        pairs = [[used_pin, f"uno:{target}"]]
    elif routing == "same_strip":
        pairs = [[used_pin, "bb1:9b.a"], [f"uno:{target}", "bb1:9b.c"]]
    else:  # different_strip
        pairs = [[used_pin, "bb1:9b.a"], [f"uno:{target}", "bb1:10b.a"]]

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    expected = _expected_wiring_1b_verdict(leg, target, routing)
    _assert_verdict(actions, state, expected, advanced_step_index=3)


# ---------------------------------------------------------------------------
# step-2: wiring only, no landing (expected_nets = [["btn1:1.r", "uno:2"]])
# ---------------------------------------------------------------------------

ARDUINO_TARGETS_2 = ["2", "5V", "GND.1", "A0", "nothing"]

WIRING_2_CASES = [
    (leg, target, routing) for leg in BTN_LEGS for target in ARDUINO_TARGETS_2 for routing in ROUTING
]


def _expected_wiring_2_verdict(leg, target, routing):
    if target == "nothing" or routing == "different_strip":
        return "wrong"
    if target != "2":
        return "wrong"
    return "pass" if leg in ("1.l", "1.r") else "wrong"


@pytest.mark.parametrize("leg,target,routing", WIRING_2_CASES)
def test_every_wiring_variation_for_step_2(lesson, library, leg, target, routing):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-2
    assert state["step_index"] == 3

    used_pin = f"btn1:{leg}"
    if target == "nothing":
        pairs = []
    elif routing == "direct":
        pairs = [[used_pin, f"uno:{target}"]]
    elif routing == "same_strip":
        pairs = [[used_pin, "bb1:6b.f"], [f"uno:{target}", "bb1:6b.c"]]
    else:
        pairs = [[used_pin, "bb1:6b.f"], [f"uno:{target}", "bb1:7b.c"]]

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    expected = _expected_wiring_2_verdict(leg, target, routing)
    _assert_verdict(actions, state, expected, advanced_step_index=4)


# ---------------------------------------------------------------------------
# step-3: component-to-component, sharing a column IS the connection
# (expected_nets = [["r1:1", "btn1:1.r"]])
# ---------------------------------------------------------------------------

RESISTOR_LEGS = ["1", "2"]
BTN_TARGETS_3 = ["1.l", "1.r", "2.l", "2.r", "nothing"]
COMPONENT_ROUTING = ["same_strip", "different_strip"]

WIRING_3_CASES = [
    (r_leg, btn_target, routing)
    for r_leg in RESISTOR_LEGS
    for btn_target in BTN_TARGETS_3
    for routing in COMPONENT_ROUTING
]


def _expected_wiring_3_verdict(r_leg, btn_target, routing):
    if btn_target == "nothing" or routing == "different_strip":
        return "wrong"
    if btn_target not in ("1.l", "1.r"):
        return "wrong"
    return "pass" if r_leg == "1" else "harmless"


@pytest.mark.parametrize("r_leg,btn_target,routing", WIRING_3_CASES)
def test_every_wiring_variation_for_step_3(lesson, library, r_leg, btn_target, routing):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    for _ in range(3):
        state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
        state, _ = send(lesson, library, state, {"command": "done"})
    assert state["step_index"] == 4  # -> step-3

    if btn_target == "nothing":
        pairs = []
    elif routing == "same_strip":
        pairs = [[f"r1:{r_leg}", "bb1:6b.h"], [f"btn1:{btn_target}", "bb1:6b.f"]]
    else:
        pairs = [[f"r1:{r_leg}", "bb1:6b.h"], [f"btn1:{btn_target}", "bb1:7b.f"]]

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    expected = _expected_wiring_3_verdict(r_leg, btn_target, routing)
    _assert_verdict(actions, state, expected, advanced_step_index=5)


# ---------------------------------------------------------------------------
# step-4: wiring check (expected_nets = [["r1:2", "uno:GND.2"]])
# ---------------------------------------------------------------------------

ARDUINO_TARGETS_4 = ["GND.1", "GND.2", "GND.3", "5V", "A0", "2", "nothing"]

WIRING_4_CASES = [
    (leg, target, routing) for leg in RESISTOR_LEGS for target in ARDUINO_TARGETS_4 for routing in ROUTING
]


def _expected_wiring_4_verdict(leg, target, routing):
    if target == "nothing" or routing == "different_strip":
        return "wrong"
    if not target.startswith("GND"):
        return "wrong"
    # Not a free symmetric swap here, unlike every other lesson's
    # resistor: by this point step-3 has ALREADY confirmed r1:1 (the
    # literal scripted leg, via this test's own "correct"-label
    # preamble) wired to btn1:1.r. Reusing r1:1 for GND here too would
    # genuinely short that pushbutton net (and the Arduino pin it's on)
    # to ground -- a real mistake, correctly caught once
    # _supersede_scarce_leg_pairs/_final_pin_for_component stopped
    # letting a same-leg, different-component fact (r1:1<->btn1:1.r)
    # get silently evicted by a later, unrelated r1:1<->GND fact (see
    # the research log (in git history)). Only the actually-free leg, r1:2, is harmless.
    return "pass" if leg == "2" else "wrong"


@pytest.mark.parametrize("leg,target,routing", WIRING_4_CASES)
def test_every_wiring_variation_for_step_4(lesson, library, leg, target, routing):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    for _ in range(4):
        state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
        state, _ = send(lesson, library, state, {"command": "done"})
    assert state["step_index"] == 5  # -> step-4

    used_pin = f"r1:{leg}"
    if target == "nothing":
        pairs = []
    elif routing == "direct":
        pairs = [[used_pin, f"uno:{target}"]]
    elif routing == "same_strip":
        pairs = [[used_pin, "bb1:10b.g"], [f"uno:{target}", "bb1:10b.h"]]
    else:
        pairs = [[used_pin, "bb1:10b.g"], [f"uno:{target}", "bb1:11b.h"]]

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    expected = _expected_wiring_4_verdict(leg, target, routing)
    _assert_verdict(actions, state, expected, advanced_step_index=6)


# ---------------------------------------------------------------------------
# Cross-checks: confirm the accepted sets match what the lesson/library
# actually declare, independent of the engine run above.
# ---------------------------------------------------------------------------

def test_only_the_documented_correct_combinations_actually_pass_or_harmless():
    accepted_landing = {leg for leg in BTN_LEGS if _expected_landing_verdict(leg) != "wrong"}
    assert accepted_landing == {"2.l", "2.r"}

    accepted_1b = {
        (leg, target, routing) for leg, target, routing in WIRING_1B_CASES
        if _expected_wiring_1b_verdict(leg, target, routing) != "wrong"
    }
    assert accepted_1b == {
        (leg, "5V", routing) for leg in BTN_LEGS for routing in ("direct", "same_strip")
    }

    accepted_2 = {
        (leg, target, routing) for leg, target, routing in WIRING_2_CASES
        if _expected_wiring_2_verdict(leg, target, routing) != "wrong"
    }
    assert accepted_2 == {
        (leg, "2", routing) for leg in ("1.l", "1.r") for routing in ("direct", "same_strip")
    }

    accepted_3 = {
        (r_leg, btn_target, routing) for r_leg, btn_target, routing in WIRING_3_CASES
        if _expected_wiring_3_verdict(r_leg, btn_target, routing) != "wrong"
    }
    assert accepted_3 == {
        (r_leg, btn_target, "same_strip") for r_leg in ("1", "2") for btn_target in ("1.l", "1.r")
    }

    accepted_4 = {
        (leg, target, routing) for leg, target, routing in WIRING_4_CASES
        if _expected_wiring_4_verdict(leg, target, routing) != "wrong"
    }
    assert accepted_4 == {
        (leg, target, routing)
        for leg in ("2",)  # r1:1 is already spoken for by step-3 -- see _expected_wiring_4_verdict
        for target in ("GND.1", "GND.2", "GND.3")
        for routing in ("direct", "same_strip")
    }


# ---------------------------------------------------------------------------
# Whole-lesson runs with the button turned round (the bug the
# llm-lesson-gen experiment found: 5V on contact group 1 instead of 2 used
# to be rejected, so a learner wiring a real button that way couldn't finish).
# ---------------------------------------------------------------------------

def _board_by_step(turned_round):
    """Cumulative real wiring, one physical action per build step, from the
    lesson's own reference diagram. `turned_round` rotates the button so
    group 1 sits where group 2 was (and vice versa)."""
    g = (lambda leg: {"1": "2", "2": "1"}[leg[0]] + leg[1:]) if turned_round else (lambda leg: leg)
    button = [[f"btn1:{g('2.r')}", "bb1:4b.f"], [f"btn1:{g('2.l')}", "bb1:4t.d"],
              [f"btn1:{g('1.l')}", "bb1:6t.d"], [f"btn1:{g('1.r')}", "bb1:6b.f"]]
    five_volt = [["uno:5V", "bb1:bp.1"], ["bb1:bp.3", "bb1:4b.h"]]
    pin2 = [["bb1:6t.c", "uno:2"]]
    resistor = [["r1:1", "bb1:6b.h"], ["r1:2", "bb1:10b.g"]]
    ground = [["bb1:10b.h", "bb1:bn.8"], ["bb1:bn.1", "uno:GND.2"]]
    steps = [button, five_volt, pin2, resistor, ground]
    return [sum(steps[:i + 1], []) for i in range(len(steps))]


@pytest.mark.parametrize("turned_round", [False, True])
def test_whole_lesson_completes_with_the_button_either_way_round(lesson, library, turned_round):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # gather
    verdicts = []
    for board in _board_by_step(turned_round):
        state, actions = send(lesson, library, state, {"command": "done", "detected_pairs": board})
        fb = next((a for a in actions if a["type"] == "feedback"), None)
        verdicts.append(fb["verdict"] if fb else "pass")
        assert "wrong" not in verdicts, (turned_round, verdicts, actions)
    state, _ = send(lesson, library, state, {"command": "done"})  # upload
    state, actions = send(lesson, library, state, {"command": "done", "detected_pairs": _board_by_step(turned_round)[-1]})
    assert state["finished"], actions
    if turned_round:
        assert state["orientations"]["btn1"] == "swapped"
        assert "harmless" in verdicts   # the swap is flagged, never silently identical
    else:
        assert set(verdicts) == {"pass"}


def test_after_turning_the_button_round_pin_2_on_the_5v_group_is_still_a_short(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    boards = _board_by_step(turned_round=True)
    for board in boards[:2]:   # button placed, 5V on group 1
        state, _ = send(lesson, library, state, {"command": "done", "detected_pairs": board})
    # Pin 2 onto column 4 — the group that already has 5V.
    wrong_board = boards[1] + [["bb1:4t.c", "uno:2"]]
    state, actions = send(lesson, library, state, {"command": "done", "detected_pairs": wrong_board})
    assert any(a["type"] == "feedback" and a["verdict"] == "wrong" for a in actions), actions
