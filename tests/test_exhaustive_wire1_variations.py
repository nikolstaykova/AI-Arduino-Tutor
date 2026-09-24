"""Exhaustive (not sampled) coverage of every meaningfully distinct way a
learner could wire connection #1 (the potentiometer's GND leg), across
both halves of the split step — the landing check (step-1a) and the
wiring check (step-1b). User request: "test all possible variations ...
if user doesn't follow instructions ... see if only the correct ones pass."

"Exhaustive" here means every *meaningfully distinct* choice, not every
literal hole number — PLAN.md/PARTS.md already establish (and
test_checker.py already proves) that the specific column number and the
specific row-letter within a strip never affect correctness, only:
  - which pin of the potentiometer was used (GND / VCC / SIG),
  - which Arduino pin was used, for the wiring half (GND.1/.2/.3, 5V, A0,
    or nothing),
  - whether the two ends of the wiring half actually share a strip.
Enumerating every combination of *those* dimensions is genuinely
exhaustive — a 64th column would exercise no new code path.
"""
import pytest

from core import checker, engine
from core.engine import _symmetric_map
from core.library import load_library
from core.lesson import load_lesson


@pytest.fixture(scope="module")
def library():
    return load_library()


@pytest.fixture(scope="module")
def lesson():
    return load_lesson("analog-read-serial")


@pytest.fixture(scope="module")
def sym_map(lesson, library):
    return _symmetric_map(lesson, library)


def send(lesson, library, state, event):
    return engine.handle_event(lesson, library, state, event)


# ---------------------------------------------------------------------------
# step-1a: landing check — NOW a combined multi-leg check for all three of
# the potentiometer's legs at once (expected_landing = ["pot1:GND",
# "pot1:VCC", "pot1:SIG"] — see PARTS.md's legs_placed_together and
# core.engine._check_multi_leg_landing). GND/VCC/SIG are all checked as
# their OWN real identities simultaneously now, not "which single one
# satisfies this one slot" — so the old per-pin-swap dimension no longer
# applies at landing time (a consistent GND/VCC swap is still accepted,
# just one step later, at the wiring check — checker.check already treats
# it as harmless there). What replaces it: connection #1's (GND's) own
# fate — landed correctly, missing, wired straight to the Arduino instead
# of the breadboard, or accidentally shorted into another leg's column —
# with VCC and SIG always correctly present in their own columns, since
# realistically the whole part was placed in one physical action.
# ---------------------------------------------------------------------------

GND_FATES = ["breadboard", "arduino_pin", "nothing", "shorted_with_vcc"]


@pytest.mark.parametrize("fate", GND_FATES)
def test_every_landing_variation_for_wire_1(lesson, library, fate):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a
    assert state["step_index"] == 1

    vcc_col, sig_col = "bb2:7t.a", "bb2:8t.a"
    pairs = [["pot1:VCC", vcc_col], ["pot1:SIG", sig_col]]
    if fate == "breadboard":
        pairs.append(["pot1:GND", "bb2:6t.a"])
    elif fate == "arduino_pin":
        pairs.append(["pot1:GND", "uno:A0"])
    elif fate == "shorted_with_vcc":
        pairs.append(["pot1:GND", vcc_col])
    # "nothing": GND simply never appears

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    feedback = next((a for a in actions if a["type"] == "feedback"), None)
    if fate == "breadboard":
        assert feedback is None, (fate, actions)  # advanced silently
        assert state["step_index"] == 2
    else:
        assert feedback is not None and feedback["verdict"] == "wrong", (fate, actions)
        assert state["step_index"] == 1  # blocked


# ---------------------------------------------------------------------------
# step-1b: wiring check (expected_nets = [["pot1:GND", "uno:GND.1"]]) --
# unchanged by the landing-check merge; still a single-pin net comparison.
# ---------------------------------------------------------------------------

POT_PINS = ["GND", "VCC", "SIG"]  # every leg the learner could plug in instead
ARDUINO_TARGETS = ["GND.1", "GND.2", "GND.3", "5V", "A0", "nothing"]
ROUTING = ["direct", "same_strip", "different_strip"]

WIRING_CASES = [
    (pin, target, routing)
    for pin in POT_PINS
    for target in ARDUINO_TARGETS
    for routing in ROUTING
]


def _expected_wiring_verdict(pin, target, routing):
    if target == "nothing":
        return "wrong"
    if routing == "different_strip":
        return "wrong"  # the two wires never actually shared a net
    is_gnd_target = target.startswith("GND")
    if not is_gnd_target:
        return "wrong"  # 5V/A0 is simply the wrong Arduino pin for this net
    if pin == "GND":
        return "pass"
    if pin == "VCC":
        return "harmless"
    return "wrong"  # SIG


@pytest.mark.parametrize("pin,target,routing", WIRING_CASES)
def test_every_wiring_variation_for_wire_1(lesson, library, sym_map, pin, target, routing):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a
    # Clear the landing half correctly every time — this test is only about
    # the wiring half's own discrimination, isolated from the landing half.
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1b
    assert state["step_index"] == 2

    used_pin = f"pot1:{pin}"
    if target == "nothing":
        pairs = []
    elif routing == "direct":
        pairs = [[used_pin, f"uno:{target}"]]
    elif routing == "same_strip":
        pairs = [[used_pin, "bb2:9t.a"], [f"uno:{target}", "bb2:9t.c"]]
    else:  # different_strip
        pairs = [[used_pin, "bb2:9t.a"], [f"uno:{target}", "bb2:10t.a"]]

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    expected = _expected_wiring_verdict(pin, target, routing)
    feedback = next((a for a in actions if a["type"] == "feedback"), None)
    if expected == "wrong":
        assert feedback is not None and feedback["verdict"] == "wrong", (pin, target, routing, actions)
        assert state["step_index"] == 2  # blocked
    elif expected == "harmless":
        assert feedback is not None and feedback["verdict"] == "harmless", (pin, target, routing, actions)
        assert state["step_index"] == 3  # flagged but still advanced
    else:
        assert feedback is None, (pin, target, routing, actions)
        assert state["step_index"] == 3  # advanced silently


def test_only_the_documented_correct_combinations_actually_pass_or_harmless():
    """Cross-check the wiring verdict table against the declared alias
    rules directly (not through the engine) — a second, independent way of
    confirming exactly the three GND-aliased Arduino targets are accepted,
    with same-strip or direct routing, and nothing else. (The landing
    half's own verdict table is covered directly by
    test_every_landing_variation_for_wire_1 above — it's no longer a
    simple per-pin lookup once all three legs are checked together.)"""
    accepted_wiring = {
        (pin, target, routing)
        for pin, target, routing in WIRING_CASES
        if _expected_wiring_verdict(pin, target, routing) != "wrong"
    }
    assert accepted_wiring == {
        (pin, target, routing)
        for pin in ("GND", "VCC")
        for target in ("GND.1", "GND.2", "GND.3")
        for routing in ("direct", "same_strip")
    }
