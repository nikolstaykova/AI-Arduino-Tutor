"""Full end-to-end SESSIONS, each its own test case, from `start` through
every build sub-step to a real `final_check` — not isolated single-step
checks like the other exhaustive files. User request: verify the state
tracking (confirmed_pairs, breadboard_bypasses) holds up across an entire
session, with a final check that re-verifies everything fresh, and report
exactly how many of each verdict category actually occurred.

Two independent choices per connection (GND/VCC/SIG), each varied
per-connection except the power-swap, which must be applied consistently
to GND and VCC *together* — swapping just one physically means the shared
potentiometer leg would have to serve two different Arduino pins at once,
which the checker correctly flags as `wrong` (a short), not a meaningful
"harmless" variation to test:
  - route: "breadboard" (routed through a strip) or "bypass" (wired
    directly to the correct final Arduino pin, skipping the board —
    engine._run_landing_check's breadboard_bypassed feature)
  - swap_power: whether GND/VCC's power legs are swapped (harmless) or not

2^3 routes x 2 swap states = 16 full successful sessions, plus a handful
of deliberately-blocked sessions and final-check-catches-a-late-fault
sessions.
"""
import itertools

import pytest

from core import engine
from core.library import load_library
from core.lesson import load_lesson

CONNECTIONS = [
    {"leg": "GND", "target": "GND.1", "symmetric": True, "col": 6},
    {"leg": "VCC", "target": "5V", "symmetric": True, "col": 7},
    {"leg": "SIG", "target": "A0", "symmetric": False, "col": 8},
]
SWAP_PARTNER = {"GND": "VCC", "VCC": "GND"}


@pytest.fixture(scope="module")
def library():
    return load_library()


@pytest.fixture(scope="module")
def lesson():
    return load_lesson("analog-read-serial")


def send(lesson, library, state, event):
    return engine.handle_event(lesson, library, state, event)


def _leg_for(conn, swap_power):
    if swap_power and conn["symmetric"]:
        return SWAP_PARTNER[conn["leg"]]
    return conn["leg"]


def _pairs_for(conn, route, swap_power):
    leg = _leg_for(conn, swap_power)
    pot_pin = f"pot1:{leg}"
    arduino_pin = f"uno:{conn['target']}"
    if route == "breadboard":
        col = conn["col"]
        landing = [[pot_pin, f"bb2:{col}t.a"]]
        wiring = [[pot_pin, f"bb2:{col}t.a"], [arduino_pin, f"bb2:{col}t.c"]]
        is_bypass = False
    else:
        landing = [[pot_pin, arduino_pin]]
        wiring = list(landing)
        is_bypass = True
    return landing, wiring, is_bypass


ROUTE_COMBOS = list(itertools.product(["breadboard", "bypass"], repeat=3))
FULL_SESSION_CASES = [(routes, swap_power) for routes in ROUTE_COMBOS for swap_power in (False, True)]

# Tallies filled in as tests run, printed at the end — answers "how many
# are classified correctly" directly rather than just reporting pass/fail.
TALLY = {"pass": 0, "harmless": 0, "wrong": 0, "bypass": 0}


@pytest.mark.parametrize("routes,swap_power", FULL_SESSION_CASES)
def test_full_session_reaches_completion_with_correct_tracking(lesson, library, routes, swap_power):
    """step-1a is now ONE combined multi-leg landing check for all three
    of the potentiometer's legs at once (PARTS.md's legs_placed_together)
    — routes[i] still independently picks breadboard vs. bypass PER LEG,
    all landed together in one step, mixing freely (see
    engine._multi_leg_bypass). Landing-time verdict is 'pass' regardless
    of swap_power now: the combined check verifies all three real leg
    IDENTITIES are present, each in its own column — which SPECIFIC
    column each one lands in was never checked at landing time anyway
    (that only matters once a leg is wired to a specific Arduino pin), so
    a mutual GND/VCC position swap isn't a detectable deviation there —
    UNLESS the swap happens via a bypass wire (which names a specific
    Arduino pin), where it correctly still reads as harmless."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    assert state["step_index"] == 1

    landing_pairs = []
    is_bypass_by_leg = {}
    for i, conn in enumerate(CONNECTIONS):
        landing, _, is_bypass = _pairs_for(conn, routes[i], swap_power)
        landing_pairs.extend(landing)
        is_bypass_by_leg[conn["leg"]] = is_bypass

    any_bypass_swap = swap_power and any(is_bypass_by_leg[c["leg"]] for c in CONNECTIONS if c["symmetric"])
    expected_landing_verdict = "harmless" if any_bypass_swap else "pass"

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": landing_pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    fb = next((a for a in actions if a["type"] == "feedback"), None)
    landing_verdict = fb["verdict"] if fb else "pass"
    assert landing_verdict == expected_landing_verdict, (routes, swap_power, actions)
    TALLY[landing_verdict] += 1

    expected_bypasses = []
    bypassed_pins = {a["message"].split(" ")[0] for a in actions if a["type"] == "breadboard_bypassed"}
    for conn in CONNECTIONS:
        leg = _leg_for(conn, swap_power)
        pin = f"pot1:{leg}"
        if is_bypass_by_leg[conn["leg"]]:
            assert pin in bypassed_pins, (routes, swap_power, conn, actions)
            TALLY["bypass"] += 1
            expected_bypasses.append({"pin": pin, "step": "step-1a"})
    assert bypassed_pins == {b["pin"] for b in expected_bypasses}
    expected_confirmed = [landing_pairs]

    final_pairs = []
    for i, conn in enumerate(CONNECTIONS):
        route = routes[i]
        _, wiring, _ = _pairs_for(conn, route, swap_power)
        expected_verdict = "harmless" if (swap_power and conn["symmetric"]) else "pass"

        state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": wiring})
        state, actions = send(lesson, library, state, {"command": "done"})
        fb = next((a for a in actions if a["type"] == "feedback"), None)
        wiring_verdict = fb["verdict"] if fb else "pass"
        assert wiring_verdict == expected_verdict, (i, "wiring", routes, swap_power, actions)
        TALLY[wiring_verdict] += 1
        expected_confirmed.append(wiring)

        final_pairs.extend(wiring)

    # State tracking, checked directly rather than inferred from verdicts:
    flat_expected_confirmed = [pair for group in expected_confirmed for pair in group]
    assert state["confirmed_pairs"] == flat_expected_confirmed
    # Order compared as a set, not a list: _multi_leg_bypass resolves pins
    # in lesson-script order (by pin IDENTITY), not by which CONNECTION
    # role each one fills — under a power swap those differ, even though
    # the same set of pins is bypassed either way.
    assert {(b["pin"], b["step"]) for b in state["breadboard_bypasses"]} == {(b["pin"], b["step"]) for b in expected_bypasses}

    assert state["phase"] == "upload"
    state, _ = send(lesson, library, state, {"command": "done"})  # upload -> final_check
    assert state["phase"] == "final_check"

    # final_check gets one fresh, self-consistent snapshot of the whole
    # board as it actually ended up — not a reuse of confirmed_pairs.
    state, actions = send(lesson, library, state, {"command": "sim", "detected_pairs": final_pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    expected_final = "harmless" if swap_power else "pass"
    if expected_final == "pass":
        assert state["finished"] is True, (routes, swap_power, actions)
        assert not [a for a in actions if a["type"] == "feedback"]
    else:
        fb = next(a for a in actions if a["type"] == "feedback")
        assert fb["verdict"] == "harmless"
        assert state["finished"] is True
    TALLY[expected_final] += 1


def test_tally_report():
    """Not a real assertion beyond sanity — prints how many of each
    verdict category actually occurred across every full-session case
    above, as a direct answer to 'how many are classified correctly'.
    Depends on pytest running this module's tests in file order (the
    default), so the tally is fully populated by the time this runs."""
    print(f"\nFull-session verdict tally across {len(FULL_SESSION_CASES)} sessions:")
    for key, count in TALLY.items():
        print(f"  {key:10s}: {count}")
    assert sum(TALLY.values()) > 0


# ---------------------------------------------------------------------------
# Blocked sessions: one connection is genuinely wrong, must stop the
# session there and leave state reflecting only what was actually confirmed.
# ---------------------------------------------------------------------------

def test_blocked_landing_leaves_nothing_confirmed(lesson, library):
    """step-1a is now ONE combined multi-leg landing check (PARTS.md's
    legs_placed_together) — a genuinely incomplete attempt (SIG never
    connected at all) must block there, with nothing recorded."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a

    bad_pairs = [["pot1:GND", "bb2:6t.a"], ["pot1:VCC", "bb2:7t.a"]]  # SIG missing entirely
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": bad_pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    assert feedback["missing"] == ["pot1:SIG"]
    assert state["step_index"] == 1  # did not advance
    assert state["confirmed_pairs"] == []  # nothing recorded from the failed attempt


WIRING_BLOCKED_CASES = [
    (0, [["pot1:GND", "bb2:6t.a"], ["uno:A0", "bb2:6t.c"]]),  # GND wiring: wrong Arduino target
    (2, [["pot1:SIG", "bb2:8t.a"], ["uno:GND.1", "bb2:9t.c"]]),  # SIG wiring: different strip
]


@pytest.mark.parametrize("conn_idx,bad_pairs", WIRING_BLOCKED_CASES)
def test_blocked_wiring_stops_at_the_right_step_with_correct_state(lesson, library, conn_idx, bad_pairs):
    """The combined landing step always happens first, all three legs at
    once — a per-connection wiring mistake still stops the session at
    exactly that connection's own wiring step, same as before."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a

    landing_pairs = []
    for conn in CONNECTIONS:
        landing, _, _ = _pairs_for(conn, "breadboard", False)
        landing_pairs.extend(landing)
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": landing_pairs})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b
    confirmed_before = [landing_pairs]

    for i in range(conn_idx):
        conn = CONNECTIONS[i]
        _, wiring, _ = _pairs_for(conn, "breadboard", False)
        state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": wiring})
        state, _ = send(lesson, library, state, {"command": "done"})
        confirmed_before.append(wiring)

    step_index_before_failure = state["step_index"]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": bad_pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    assert state["step_index"] == step_index_before_failure  # did not advance

    flat_confirmed_before = [pair for group in confirmed_before for pair in group]
    assert state["confirmed_pairs"] == flat_confirmed_before  # nothing new recorded from the failed attempt


# ---------------------------------------------------------------------------
# final_check catches a late-breaking fault even when every build step
# reported correct — several independent instances of the fault, not just
# the one already covered in test_engine.py.
# ---------------------------------------------------------------------------

LATE_FAULT_CASES = [
    "gnd_disconnected",   # GND leg not actually connected in the final snapshot
    "vcc_wrong_target",   # VCC leg ended up on A0 instead of 5V
    "sig_shorted_to_gnd", # SIG leg accidentally shares a strip with GND
]


@pytest.mark.parametrize("fault", LATE_FAULT_CASES)
def test_final_check_catches_a_late_breaking_fault_after_all_steps_passed(lesson, library, fault):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a

    landing_pairs = []
    for conn in CONNECTIONS:
        landing, _, _ = _pairs_for(conn, "breadboard", False)
        landing_pairs.extend(landing)
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": landing_pairs})
    state, actions = send(lesson, library, state, {"command": "done"})  # -> step-1b
    assert not [a for a in actions if a.get("verdict") == "wrong"]

    for conn in CONNECTIONS:
        _, wiring, _ = _pairs_for(conn, "breadboard", False)
        state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": wiring})
        state, actions = send(lesson, library, state, {"command": "done"})
        assert not [a for a in actions if a.get("verdict") == "wrong"]
    state, _ = send(lesson, library, state, {"command": "done"})  # upload -> final_check
    assert state["phase"] == "final_check"

    final_pairs = [
        ["pot1:GND", "bb2:6t.a"], ["uno:GND.1", "bb2:6t.c"],
        ["pot1:VCC", "bb2:7t.a"], ["uno:5V", "bb2:7t.c"],
        ["pot1:SIG", "bb2:8t.a"], ["uno:A0", "bb2:8t.c"],
    ]
    if fault == "gnd_disconnected":
        final_pairs = [p for p in final_pairs if "GND" not in p[0] and "GND.1" not in p[1]]
    elif fault == "vcc_wrong_target":
        final_pairs = [p if p != ["uno:5V", "bb2:7t.c"] else ["uno:A0", "bb2:7t.c"] for p in final_pairs]
    elif fault == "sig_shorted_to_gnd":
        final_pairs = [p if p != ["pot1:SIG", "bb2:8t.a"] else ["pot1:SIG", "bb2:6t.a"] for p in final_pairs]

    state, actions = send(lesson, library, state, {"command": "sim", "detected_pairs": final_pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong", (fault, actions)
    assert state["finished"] is False
