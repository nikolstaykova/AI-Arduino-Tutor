"""The merged stress test (core/flow_stress.py) on the three hand-made
lessons AND every Sonnet-generated version of them: the same crazy flows
the engine's own tests cover — every free pin, changing their mind, parts
turned round, built ahead, every GND, another leg of a group, other rows,
a shifted layout, power rails, legs straight onto the Arduino, Mega/Nano,
several persistent mistakes, hints and going back — pairwise-covered plus
a fixed-seed random sample. Tracking, code and physics must hold in all."""
import json
from pathlib import Path

import pytest

from core import engine, flow_stress
from core.lesson import load_lesson
from core.lesson_gen import GeneratedLesson
from core.library import load_library

RUNS = Path(__file__).resolve().parent.parent / "experiments" / "sonnet-lesson-gen" / "runs"
GENERATED = sorted(p.name for p in RUNS.glob("*-run*") if (p / "lesson.json").exists()) if RUNS.exists() else []


def _generated(run):
    d = RUNS / run
    return GeneratedLesson(json.loads((d / "lesson.json").read_text()), json.loads((d / "diagram.json").read_text()),
                           (d / "code.ino").read_text())


@pytest.mark.parametrize("lesson_id", ["blink", "analog-read-serial", "digital-read-serial"])
def test_hand_made_lesson_survives_every_merged_flow(lesson_id):
    result = flow_stress.stress(load_lesson(lesson_id), load_library())
    assert result["flows"] > 400
    assert result["failures"] == [], result["failures"][:3]


@pytest.mark.parametrize("run", GENERATED)
def test_sonnet_generated_lesson_survives_every_merged_flow(run):
    result = flow_stress.stress(_generated(run), load_library())
    assert result["failures"] == [], result["failures"][:3]


def test_every_dimension_is_really_exercised():
    lesson, library = load_lesson("digital-read-serial"), load_library()
    board = flow_stress.Board(lesson, library)
    plain = {"board": "uno", "pins": {}, "mind": False, "turned": [], "ahead": False, "gnd": "keep", "sibling": False,
             "rows": False, "shift": 0, "rails": False, "bypass": False, "hints": False, "back": False, "mistakes": ()}
    ref = flow_stress.Physical(board, lesson, library, plain).final
    dims = flow_stress._variants_for(lesson, library, "uno")
    for name, value in [("gnd", "GND.1"), ("sibling", True), ("rows", True), ("shift", dims["shift"][-1]),
                        ("rails", True), ("bypass", True)]:
        assert flow_stress.Physical(board, lesson, library, {**plain, name: value}).final != ref, name
    phys = flow_stress.Physical(board, lesson, library, plain)
    for kind in ("forgot", "wrong_kind", "off_by_one", "short_jumper", "leg_self_short"):
        assert any(flow_stress._mistake(board, phys, s, kind) is not None for s in board.build_steps), kind


def test_stress_catches_add_only_tracking(monkeypatch):
    """Before whole-board snapshots, a wire moved after its step stayed in
    the engine's record forever. The stress test must catch that."""
    monkeypatch.setattr(engine, "_record_confirmed",
                        lambda state, event, detected, b, c, lib=None: engine._supersede_scarce_leg_pairs(
                            state["confirmed_pairs"], detected, b, c, lib))
    result = flow_stress.stress(load_lesson("blink"), load_library(), stop_after=1)
    assert result["failures"] and any(p.startswith("tracking") for p in result["failures"][0][1])


def test_stress_catches_a_code_rewrite_that_touches_non_pins(monkeypatch):
    base = load_lesson("digital-read-serial")
    lesson = GeneratedLesson(base.data, base.diagram(), base.code_text().replace("delay(1);", "delay(2);"))
    monkeypatch.setattr(engine, "rewrite_pins_in_code", engine.apply_word_boundary_replacements)
    result = flow_stress.stress(lesson, load_library(), stop_after=1)
    assert result["failures"] and any(p.startswith("code") for p in result["failures"][0][1])


@pytest.mark.skipif("analog-read-serial-run1" not in GENERATED, reason="Sonnet runs not present")
def test_removing_a_caught_short_unblocks_the_learner():
    """Found by the deep run (40k flows): a short jumper made at one step,
    present while a later step passed, then caught and removed. The engine
    kept failing every check on the stale record. Judged on the snapshot now."""
    flow = {"board": "arduino mega", "pins": {}, "mind": False, "turned": ["pot1"], "ahead": False, "gnd": "GND.1",
            "sibling": False, "rows": True, "shift": 0, "rails": True, "bypass": False, "hints": True, "back": False,
            "mistakes": ((3, "short_jumper"),)}
    assert flow_stress.run(_generated("analog-read-serial-run1"), load_library(), flow) == []
