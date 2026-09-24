"""Exhaustive (not sampled) coverage of every meaningfully distinct way to
wire Blink's circuit — user request: "test lesson 2 first all possible
ways to connect resistors and see if it runs."

Same "meaningfully distinct, not literal holes" philosophy as
test_exhaustive_wire1_variations.py: column number and row-letter are
already proven irrelevant (test_mini_board_exhaustive.py), so the real
dimensions here are which leg/pin of each component is used, which
Arduino target, and whether the two ends actually share a net.

Blink's topology is genuinely different from analog-read-serial's in one
place: step-2 (led1:A <-> r1:2) is component-to-component, with no
Arduino pin on either side and no landing check at all (see PLAN.md's
Blink notes) — the resistor's two legs are declared symmetric
(swappable, harmless), the LED's two legs are not (real polarity,
reversing it is wrong).
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
    return load_lesson("blink")


def send(lesson, library, state, event):
    return engine.handle_event(lesson, library, state, event)


def _feedback_verdict(actions):
    fb = next((a for a in actions if a["type"] == "feedback"), None)
    return fb["verdict"] if fb else "pass"


# ---------------------------------------------------------------------------
# A) step-1a landing: which resistor leg, landing where
# ---------------------------------------------------------------------------

LEGS = ["1", "2"]
LANDING_DESTS = ["breadboard", "arduino_pin", "nothing"]
LANDING_CASES = [(leg, dest) for leg in LEGS for dest in LANDING_DESTS]


def _expected_landing_verdict(leg, dest):
    if dest != "breadboard":
        return "wrong"
    return "pass" if leg == "1" else "harmless"


@pytest.mark.parametrize("leg,dest", LANDING_CASES)
def test_step1a_landing_variations(lesson, library, leg, dest):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    used_pin = f"r1:{leg}"
    if dest == "breadboard":
        pairs = [[used_pin, "bb1:3b.h"]]
    elif dest == "arduino_pin":
        # A pin that's neither step-1b's target (uno:13) nor a valid
        # substitute for it: straight onto 13 is the (separately tested)
        # breadboard bypass, and straight onto another free DIGITAL pin
        # (e.g. 12) is a bypass plus a pin substitution — both correct
        # (see test_landing_straight_onto_a_substitute_pin_is_accepted).
        # A0 is the analog pool, the wrong kind of pin for a digital
        # output, same choice the other lessons' exhaustive files make.
        pairs = [[used_pin, "uno:A0"]]
    else:
        pairs = []
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    expected = _expected_landing_verdict(leg, dest)
    assert _feedback_verdict(actions) == expected, (leg, dest, actions)
    assert state["step_index"] == (2 if expected != "wrong" else 1)


# ---------------------------------------------------------------------------
# B) step-1b wiring: r1's leg <-> Arduino pin, every target x routing
# ---------------------------------------------------------------------------

ARDUINO_TARGETS = ["13", "12", "11", "GND.1", "5V", "nothing"]
ROUTING = ["direct", "same_strip", "different_strip"]
WIRING_CASES = [(leg, target, routing) for leg in LEGS for target in ARDUINO_TARGETS for routing in ROUTING]


def _expected_wiring_verdict(leg, target, routing):
    if target == "nothing" or routing == "different_strip":
        return "wrong"
    if target not in ("13", "12", "11"):
        return "wrong"  # GND.1/5V aren't digital pins -- no substitution pool to draw from
    # Revised (user request: match real electronics -- see
    # core/engine.py's _try_pin_substitution docstring): pins 12/11 are
    # now accepted via substitution, same as the exact scripted 13 --
    # not just the exact scripted pin, same as analog always was.
    return "pass" if leg == "1" else "harmless"


@pytest.mark.parametrize("leg,target,routing", WIRING_CASES)
def test_step1b_wiring_variations(lesson, library, leg, target, routing):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b

    used_pin = f"r1:{leg}"
    if target == "nothing":
        pairs = []
    elif routing == "direct":
        pairs = [[used_pin, f"uno:{target}"]]
    elif routing == "same_strip":
        pairs = [[used_pin, "bb1:9b.a"], [f"uno:{target}", "bb1:9b.c"]]
    else:
        pairs = [[used_pin, "bb1:9b.a"], [f"uno:{target}", "bb1:10b.a"]]

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    expected = _expected_wiring_verdict(leg, target, routing)
    assert _feedback_verdict(actions) == expected, (leg, target, routing, actions)
    assert state["step_index"] == (3 if expected != "wrong" else 2)


# ---------------------------------------------------------------------------
# C) step-2: led1:A <-> r1:2 — component-to-component, no landing, no wire
# ---------------------------------------------------------------------------

LED_PINS = ["A", "C"]
RESISTOR_LEGS = ["2", "1"]
STEP2_ROUTING = ["direct", "same_strip", "different_strip"]
STEP2_CASES = [(led_pin, r_leg, routing) for led_pin in LED_PINS for r_leg in RESISTOR_LEGS for routing in STEP2_ROUTING]


def _expected_step2_verdict(led_pin, r_leg, routing):
    if routing == "different_strip":
        return "wrong"
    if led_pin != "A":
        return "wrong"  # LED has no symmetric partner -- real polarity
    # step-1b (fast-forwarded "correct") already put r1:1 on pin 13, which
    # locks the resistor's orientation. The LED anode on r1:1 as well sits
    # straight on pin 13 with the resistor bypassed (~86 mA through the LED,
    # see core/physics.py) — a real mistake, not a harmless swap.
    return "pass" if r_leg == "2" else "wrong"


@pytest.mark.parametrize("led_pin,r_leg,routing", STEP2_CASES)
def test_step2_led_to_resistor_variations(lesson, library, led_pin, r_leg, routing):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-2
    assert lesson.step(state["step_index"])["id"] == "step-2"

    led_side = f"led1:{led_pin}"
    r_side = f"r1:{r_leg}"
    if routing == "direct":
        pairs = [[led_side, r_side]]
    elif routing == "same_strip":
        pairs = [[led_side, "bb1:6b.i"], [r_side, "bb1:6b.h"]]
    else:
        pairs = [[led_side, "bb1:6b.i"], [r_side, "bb1:7b.h"]]

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    expected = _expected_step2_verdict(led_pin, r_leg, routing)
    assert _feedback_verdict(actions) == expected, (led_pin, r_leg, routing, actions)
    assert state["step_index"] == (4 if expected != "wrong" else 3)


# ---------------------------------------------------------------------------
# D) step-3: led1:C <-> uno:GND — no landing (rode along with led1:A)
# ---------------------------------------------------------------------------

STEP3_TARGETS = ["GND.1", "GND.2", "GND.3", "13", "5V", "nothing"]
STEP3_ROUTING = ["direct", "same_strip", "different_strip"]
STEP3_CASES = [(led_pin, target, routing) for led_pin in LED_PINS for target in STEP3_TARGETS for routing in STEP3_ROUTING]


def _expected_step3_verdict(led_pin, target, routing):
    if target == "nothing" or routing == "different_strip" or not target.startswith("GND"):
        return "wrong"
    return "pass" if led_pin == "C" else "wrong"  # LED: no symmetric partner


@pytest.mark.parametrize("led_pin,target,routing", STEP3_CASES)
def test_step3_led_to_gnd_variations(lesson, library, led_pin, target, routing):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    for _ in range(2):
        state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
        state, _ = send(lesson, library, state, {"command": "done"})
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-3
    assert lesson.step(state["step_index"])["id"] == "step-3"

    led_side = f"led1:{led_pin}"
    if target == "nothing":
        pairs = []
    elif routing == "direct":
        pairs = [[led_side, f"uno:{target}"]]
    elif routing == "same_strip":
        pairs = [[led_side, "bb1:8b.i"], [f"uno:{target}", "bb1:8b.g"]]
    else:
        pairs = [[led_side, "bb1:8b.i"], [f"uno:{target}", "bb1:9b.a"]]

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    expected = _expected_step3_verdict(led_pin, target, routing)
    assert _feedback_verdict(actions) == expected, (led_pin, target, routing, actions)
    assert state["phase"] == ("upload" if expected != "wrong" else "build")


def test_case_counts_are_what_they_look_like():
    assert len(LANDING_CASES) == 6
    assert len(WIRING_CASES) == 36
    assert len(STEP2_CASES) == 12
    assert len(STEP3_CASES) == 36


def test_step1a_landing_directly_on_the_correct_pin_is_a_bypass_not_wrong(lesson, library):
    """Complements the exhaustive matrix above: unlike an arbitrary wrong
    pin, wiring r1:1 straight to step-1b's own real target (uno:13),
    skipping the breadboard, is the breadboard-bypass feature working
    correctly — a tracked pass, not a failure."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:1", "uno:13"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert any(a["type"] == "breadboard_bypassed" for a in actions)
    assert _feedback_verdict(actions) == "pass"


def test_landing_straight_onto_a_substitute_pin_is_accepted(lesson, library):
    """Leg 1 plugged straight into pin 12 (a free digital pin, valid for
    Blink's pin 13): a breadboard bypass AND a pin substitution. Found by
    the merged flow stress test on a Sonnet-generated Blink."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    state, actions = send(lesson, library, state, {"command": "done", "detected_pairs": [["r1:1", "uno:12"]]})
    assert _feedback_verdict(actions) != "wrong", actions
    assert any(a["type"] == "breadboard_bypassed" for a in actions)
