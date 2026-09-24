"""Tests for the Blink lesson — the first lesson with a genuinely
different topology from analog-read-serial: a component-to-component
connection (led1:A <-> r1:2, no Arduino pin on either side, and no
separate jumper wire — placing the LED in the resistor's column IS the
connection) alongside the usual component-to-Arduino ones. Also the first
lesson exercised under both `difficulty` levels.
"""
import json
from pathlib import Path

import pytest

from core import checker, engine
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


def test_all_parts_used_resolve_in_the_library(lesson, library):
    for part_id in lesson.data["parts_used"]:
        assert library.get(part_id) is not None, f"missing library card: {part_id}"


def test_derived_expected_nets_match_the_handwritten_final_check(lesson):
    """Same cross-check as analog-read-serial's — auto-deriving from the
    real diagram.json must describe the same net groupings as the
    hand-written final_check, catching any hand-transcription mistake."""
    diagram = lesson.diagram()
    derived = checker.derive_expected_nets(diagram)
    alias_map = checker.board_alias_map(diagram["parts"])
    derived_nets = set(checker.build_nets(derived, alias_map))
    handwritten_nets = set(checker.build_nets(lesson.final_check_nets(), alias_map))
    assert derived_nets == handwritten_nets


def _finish_step(lesson, library, state, landing_pairs, wiring_pairs):
    """Drive one build step (landing, if any, then its wiring check) to
    completion with the given detected pairs."""
    step = lesson.step(state["step_index"])
    if "expected_landing" in step:
        state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": landing_pairs})
        state, actions = send(lesson, library, state, {"command": "done"})
        assert not [a for a in actions if a.get("verdict") == "wrong"]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": wiring_pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"], actions
    return state


def test_full_beginner_walkthrough_reaches_completion(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # gather -> step-1a
    assert lesson.step(state["step_index"])["id"] == "step-1a"

    state = _finish_step(lesson, library, state, [["r1:1", "bb1:3b.h"]], [["r1:1", "bb1:3b.h"], ["uno:13", "bb1:3b.g"]])
    assert lesson.step(state["step_index"])["id"] == "step-2"

    # step-2 has no landing at all: placing the LED in the right column IS the connection
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["led1:A", "r1:2"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    assert lesson.step(state["step_index"])["id"] == "step-3"

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["led1:C", "uno:GND.1"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    assert state["phase"] == "upload"

    state, _ = send(lesson, library, state, {"command": "done"})  # -> final_check
    final_pairs = [
        ["r1:1", "bb1:3b.h"], ["uno:13", "bb1:3b.g"],
        ["led1:A", "r1:2"],
        ["led1:C", "uno:GND.1"],
    ]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": final_pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["finished"] is True
    assert any(a["type"] == "complete" for a in actions)


def test_resistor_leg_swap_is_harmless_at_both_landing_and_wiring(lesson, library):
    """The resistor's two legs are declared symmetric (no inherent
    direction) — using leg 2 where the script assumed leg 1 must be
    harmless, not wrong, at both the landing and wiring checks."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:2", "bb1:3b.h"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "harmless"

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:2", "bb1:3b.h"], ["uno:13", "bb1:3b.g"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "harmless"


def test_led_reversed_is_wrong_no_symmetric_partner(lesson, library):
    """Unlike the resistor, the LED has no declared symmetric_pins —
    reversing it (cathode where the anode should connect) is a real
    polarity mistake, not a harmless deviation."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # gather -> step-1a
    state = _finish_step(lesson, library, state, [["r1:1", "bb1:3b.h"]], [["r1:1", "bb1:3b.h"], ["uno:13", "bb1:3b.g"]])

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["led1:C", "r1:2"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    assert state["step_index"] == 3  # blocked, did not advance to step-3


def test_resistors_own_two_legs_shorted_together_is_caught(lesson, library):
    """A genuinely dangerous real mistake: both of the resistor's legs
    landing in the SAME breadboard column defeats its current-limiting
    entirely (the strip just ties them together). Must be caught as
    wrong, with `conflicts` naming exactly the short — r1:1 tied into a
    net that also contains r1:2 and uno:13, not just a generic failure."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:1", "bb1:3b.h"]]})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b

    shorted = [["r1:1", "bb1:3b.h"], ["r1:2", "bb1:3b.i"], ["uno:13", "bb1:3b.g"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": shorted})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    assert feedback["conflicts"]["r1:1"] == ["r1:1", "r1:2", "uno:13"]
    assert state["step_index"] == 2  # blocked


def test_deviating_to_a_different_digital_pin_is_accepted_via_substitution(lesson, library):
    """Revised (user request: match real electronics — see
    core/engine.py's _try_pin_substitution docstring). Wiring to pin 12
    instead of the scripted 13 used to be caught as flatly wrong; now
    it's accepted the same way an analog deviation always was, with the
    shown code rewritten to match (_adjusted_code)."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:1", "bb1:3b.h"]]})
    state, _ = send(lesson, library, state, {"command": "done"})

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:1", "bb1:3b.h"], ["uno:12", "bb1:3b.g"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    sub = next(a for a in actions if a["type"] == "pin_substituted")
    assert "uno:13" in sub["message"] and "uno:12" in sub["message"]


def test_entirely_different_columns_than_the_diagrams_own_still_works(lesson, library):
    """User question: what if the learner uses columns 4/8/9 instead of
    the diagram's own 3/6/8? Since the checker only ever compares which
    components share a net (never which strip realizes it), and the
    lesson's own instructions never name a specific column number, this
    should just work with zero special-casing — verified end to end with
    columns that don't match the authored diagram.json at all."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:1", "bb1:4t.a"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:1", "bb1:4t.a"], ["uno:13", "bb1:4t.c"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]

    # resistor leg2 + LED anode both in column 8, not the diagram's own 6
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:2", "bb1:8t.h"], ["led1:A", "bb1:8t.i"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]

    # LED cathode in column 9, not the diagram's own 8
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["led1:C", "bb1:9t.i"], ["uno:GND.1", "bb1:9t.g"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    assert state["phase"] == "upload"


def test_advanced_difficulty_collapses_step_1a_and_1b_only(lesson, library):
    """step-2 and step-3 already have no landing sub-step (the rigid
    2-terminal parts land both legs at once — see PLAN.md's Blink notes),
    so advanced difficulty only has step-1a to skip; nothing else changes."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "difficulty", "level": "advanced"})
    state, actions = send(lesson, library, state, {"command": "done"})  # gather -> step-1b directly
    assert lesson.step(state["step_index"])["id"] == "step-1b"
    assert actions[0]["text"] == "Connect one end of the resistor to pin 13."   # advanced: just the goal
    state, _ = send(lesson, library, state, {"command": "hint"})
    state, hint = send(lesson, library, state, {"command": "hint"})
    assert "different numbered columns" in hint[0]["text"] and "pin 13" in hint[0]["text"]   # the how, on request

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:1", "bb1:3b.h"], ["uno:13", "bb1:3b.g"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert lesson.step(state["step_index"])["id"] == "step-2"  # unaffected by difficulty, no landing to skip
