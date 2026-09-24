"""Every lesson can be built with or without a breadboard; without one,
the real legs decide how each connection is made and what extra parts
and tools that takes — and the derived lesson runs on the unchanged engine."""
import pytest

from core import engine
from core.build_methods import JOINS, all_plans, derive_lesson, plan
from core.lesson import load_lesson
from core.lesson_finder import all_lesson_ids, find_lessons
from core.library import load_library

LIB = load_library()


def _play(lesson):
    """Build step by step with exactly each step's own connections (whole-board snapshots)."""
    state, _ = engine.handle_event(lesson, LIB, engine.initial_state(), {"command": "start"})
    board = []
    for _ in range(40):
        if state["finished"]:
            break
        if state["phase"] in ("gather", "upload"):
            state, _ = engine.handle_event(lesson, LIB, state, {"command": "done"})
            continue
        step = lesson.step(state["step_index"])
        board += [list(p) for p in (step or {}).get("expected_nets", [])]
        state, actions = engine.handle_event(lesson, LIB, state, {"command": "done", "detected_pairs": list(board), "snapshot": True})
    return state


@pytest.mark.parametrize("lesson_id", all_lesson_ids())
@pytest.mark.parametrize("join", JOINS)
def test_every_lesson_completes_without_a_breadboard(lesson_id, join):
    derived = derive_lesson(load_lesson(lesson_id), LIB, "no-breadboard", join)
    assert "breadboard" not in derived.data["parts_used"]
    assert not any("expected_landing" in s for s in derived.steps)
    assert not any("breadboard" in p.get("type", "") for p in derived.diagram()["parts"])
    assert not any("column" in s.get("clip", "") for s in derived.steps if s["phase"] == "build")
    assert _play(derived)["finished"]


@pytest.mark.parametrize("lesson_id", all_lesson_ids())
def test_breadboard_way_is_the_lesson_unchanged(lesson_id):
    lesson = load_lesson(lesson_id)
    assert derive_lesson(lesson, LIB, "breadboard") is lesson
    assert plan(lesson, LIB, "breadboard")["parts"] == list(dict.fromkeys(lesson.data["parts_used"]))


def test_with_clip_leads_a_lead_never_goes_bare_into_a_socket():
    p = plan(load_lesson("blink"), LIB, "no-breadboard", "clips")
    assert p["counts"] == {"alligator-clip-wire": 3, "jumper-wire": 2} and p["tools"] == []
    assert p["changes"]["removed"] == ["breadboard"]
    assert [k for *_, k in p["pairs"]] == ["clip-stub", "clip", "clip-stub"]
    hows = [c["how"] for s in p["steps"] for c in s["connections"]]
    assert "jumper wire into the 13 socket" in hows[0] and "too thin to grip" in hows[0]


def test_only_the_twist_style_pushes_a_bare_lead_into_a_socket_and_it_says_its_loose():
    p = plan(load_lesson("blink"), LIB, "no-breadboard", "twist")
    assert [k for *_, k in p["pairs"]] == ["insert", "twist", "insert"]
    assert any("sits loose" in n for n in p["notes"])


def test_soldering_puts_a_wire_on_each_lead_that_meets_a_socket():
    p = plan(load_lesson("blink"), LIB, "no-breadboard", "solder")
    assert [k for *_, k in p["pairs"]] == ["solder-wire", "solder", "solder-wire"]
    assert p["counts"]["jumper-wire"] == 2


def test_twisting_needs_nothing_extra_for_wire_leads():
    p = plan(load_lesson("blink"), LIB, "no-breadboard", "twist")
    assert p["counts"] == {} and p["tools"] == []


def test_pushbutton_legs_cant_twist_or_sit_in_a_socket():
    p = plan(load_lesson("digital-read-serial"), LIB, "no-breadboard", "twist")
    assert p["counts"]["alligator-clip-wire"] >= 2 and p["counts"]["jumper-wire"] == 2
    assert [k for *_, k in p["pairs"]][:2] == ["clip-stub", "clip-stub"]
    assert any("can't be twisted" in n for n in p["notes"])


def test_soldering_needs_the_tools_and_consumables():
    p = plan(load_lesson("digital-read-serial"), LIB, "no-breadboard", "solder")
    assert {"soldering-iron", "wire-stripper", "flush-cutters"} <= set(p["tools"])
    assert {"solder", "heat-shrink"} <= set(p["parts"])
    assert "alligator-clip-wire" not in p["parts"]


def test_a_knobs_solder_tabs_get_soldered_wires_or_clips_never_jumpers():
    ways = all_plans(load_lesson("analog-read-serial"), LIB)
    assert [(w["method"], w["join"]) for w in ways] == [("breadboard", None), ("no-breadboard", "clips"), ("no-breadboard", "solder")]
    clips, solder = ways[1], ways[2]
    assert [k for *_, k in clips["pairs"]] == ["clip-stub"] * 3 and clips["counts"] == {"alligator-clip-wire": 3, "jumper-wire": 3}
    assert [k for *_, k in solder["pairs"]] == ["solder-wire"] * 3 and "soldering-iron" in solder["tools"]
    assert all("jumper-wire-mf" not in w["parts"] for w in ways)


def test_one_header_socket_holds_one_leg():
    p = plan(load_lesson("blink"), LIB, "no-breadboard", "twist")
    sockets = [pair[1] for pair in p["pairs"] if pair[1].startswith("uno:") and pair[3] == "insert"]
    assert len(sockets) == len(set(sockets))


def test_finder_offers_a_no_breadboard_build_when_you_have_no_breadboard():
    results = {r["id"]: r for r in find_lessons(["arduino-uno", "usb-cable", "led", "resistor-1k", "alligator-clip-wire"])}
    blink = results["blink"]
    assert blink["status"] == "ready" and blink["build"]["method"] == "no-breadboard"
    assert any(w["method"] == "breadboard" and "breadboard" in w["missing"] for w in blink["ways"])


def test_finder_combines_a_stand_in_part_with_no_breadboard():
    blink = {r["id"]: r for r in find_lessons(["arduino-uno", "usb-cable", "led", "resistor-220"])}["blink"]
    assert blink["status"] == "substitute" and blink["build"] == {"method": "no-breadboard", "join": "twist"}
    assert blink["substitutes"][0]["use"] == "resistor-220"
