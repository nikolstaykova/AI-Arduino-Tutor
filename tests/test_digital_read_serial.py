"""Tests for the DigitalReadSerial lesson — the first lesson using the
pushbutton (whose corrected board-pin-alias behavior, see
the research log (in git history), is exercised here for real) and the breadboard's own
power rails (bp/bn), and the first with a genuine 3-way net junction
(btn1:1.r, r1:1, and uno:2 all sharing one strip).
"""
import pytest

from core import checker, engine
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


def test_all_parts_used_resolve_in_the_library(lesson, library):
    for part_id in lesson.data["parts_used"]:
        assert library.get(part_id) is not None, f"missing library card: {part_id}"


def test_derived_expected_nets_match_the_handwritten_final_check(lesson):
    diagram = lesson.diagram()
    derived = checker.derive_expected_nets(diagram)
    alias_map = checker.board_alias_map(diagram["parts"])
    derived_nets = set(checker.build_nets(derived, alias_map))
    handwritten_nets = set(checker.build_nets(lesson.final_check_nets(), alias_map))
    assert derived_nets == handwritten_nets


def _advance_correctly(lesson, library, state, n):
    for _ in range(n):
        state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
        state, actions = send(lesson, library, state, {"command": "done"})
        assert not [a for a in actions if a.get("verdict") == "wrong"], actions
    return state


def test_full_beginner_walkthrough_reaches_completion(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a

    state = _advance_correctly(lesson, library, state, 4)  # step-1a..step-3 -> step-4
    assert lesson.step(state["step_index"])["id"] == "step-4"

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:2", "bb1:10b.g"], ["uno:GND.2", "bb1:10b.h"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    assert state["phase"] == "upload"

    state, _ = send(lesson, library, state, {"command": "done"})  # -> final_check
    final_pairs = [
        ["btn1:2.r", "bb1:4b.f"], ["uno:5V", "bb1:4b.h"],
        ["btn1:1.r", "bb1:6b.f"], ["uno:2", "bb1:6b.c"],
        ["r1:1", "bb1:6b.h"],
        ["r1:2", "bb1:10b.g"], ["uno:GND.2", "bb1:10b.h"],
    ]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": final_pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["finished"] is True
    assert any(a["type"] == "complete" for a in actions)


def test_aliased_contact_group_leg_is_a_silent_pass_not_harmless(lesson, library):
    """The pushbutton's 2.l and 2.r are ALWAYS the same net (verified
    against Wokwi's own docs) — using 2.l where the lesson names 2.r must
    be a silent pass, at both landing and wiring, not flagged harmless."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["btn1:2.l", "bb1:4b.f"], ["btn1:1.r", "bb1:5b.f"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a["type"] == "feedback"]  # silent pass

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["btn1:2.l", "bb1:4b.f"], ["uno:5V", "bb1:4b.h"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a["type"] == "feedback"]  # still silent pass
    assert lesson.step(state["step_index"])["id"] == "step-2"


def test_wrong_contact_group_is_a_real_mistake(lesson, library):
    """1.x and 2.x are genuinely different internal nodes — wiring the
    WRONG contact group to 5V is a real error, not an aliasable variant."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["btn1:1.r", "bb1:4b.f"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    assert state["step_index"] == 1  # blocked


def test_multi_leg_bypass_recognizes_an_aliased_leg_name_not_just_the_literal_one(lesson, library):
    """Regression: _multi_leg_bypass's own search for a still-missing
    leg's real wire in `detected` originally used an exact string match
    against the pin name — so a bypass wire using the pushbutton's
    ALIASED leg (2.l, always the same net as the scripted 2.r) was never
    even found, let alone resolved, even though the single-pin bypass
    path (and every other alias-aware comparison in this codebase)
    already treats 2.l/2.r as identical. Fixed to canonicalize both sides
    via the same alias_map checker.check itself already uses."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    pairs = [["btn1:2.l", "uno:5V"], ["btn1:1.r", "uno:2"]]  # both bypassed, aliased leg for group 2
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    # Bypass messages/tracking name the SCRIPTED leg identity (btn1:2.r),
    # not the physically-used alias (btn1:2.l) -- consistent with how
    # every other confirmed-pairs/tracking mechanism in this codebase
    # refers to a pin, even when the learner used its alias.
    bypasses = {a["message"].split(" ")[0] for a in actions if a["type"] == "breadboard_bypassed"}
    assert bypasses == {"btn1:2.r", "btn1:1.r"}
    assert not [a for a in actions if a["type"] == "feedback"]  # a clean pass
    assert state["step_index"] == 2  # advanced to step-1b


def test_resistor_leg_swap_is_harmless(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    state = _advance_correctly(lesson, library, state, 3)  # -> step-3
    assert lesson.step(state["step_index"])["id"] == "step-3"

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:2", "bb1:6b.h"], ["btn1:1.r", "bb1:6b.f"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "harmless"


def test_nothing_connected_is_wrong(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": []})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"


def test_the_3way_junction_via_a_shared_breadboard_strip_passes(lesson, library):
    """btn1:1.r, r1:1, and uno:2 all sharing one physical breadboard strip
    is the real circuit topology here (not a bug) — a genuine 3-member
    net, correctly recognized as fully connected."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    state = _advance_correctly(lesson, library, state, 2)  # -> step-2
    assert lesson.step(state["step_index"])["id"] == "step-2"

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["btn1:1.r", "bb1:6b.f"], ["uno:2", "bb1:6b.c"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    assert lesson.step(state["step_index"])["id"] == "step-3"

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["r1:1", "bb1:6b.h"], ["btn1:1.r", "bb1:6b.f"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]
