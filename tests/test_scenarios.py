"""core/scenarios.py — every lesson must survive a real learner: step by
step, building ahead, a different pin, parts turned round, a forgotten
step, a wrong pin, a reversed LED, a short, hints and going back."""
import copy

import pytest

from core import scenarios
from core.lesson import load_lesson
from core.lesson_gen import GeneratedLesson, validate


@pytest.mark.parametrize("lesson_id", ["blink", "analog-read-serial", "digital-read-serial"])
def test_every_hand_made_lesson_survives_every_scenario(lesson_id):
    results = scenarios.run_scenarios(load_lesson(lesson_id))
    assert [r for r in results if not r["ok"]] == []
    assert {r["name"] for r in results} >= {"normal", "build_ahead", "moved_pins", "turned_round", "forgot_step",
                                            "wrong_pin", "short_at_final", "hints_and_back"}


def test_board_is_built_the_way_a_person_places_parts():
    """Blink: the resistor goes in with BOTH legs at its first step, even
    though the lesson only checks leg 1 there."""
    board = scenarios.Board(load_lesson("blink"), scenarios.load_library())
    first = board.upto(board.build_steps[0])
    assert {c[0] for c in first if c[0].startswith("r1:")} == {"r1:1", "r1:2"}
    assert board.upto(board.build_steps[-1]) == board.full()


def _generated(lesson_id):
    lesson = load_lesson(lesson_id)
    return copy.deepcopy(lesson.data), copy.deepcopy(lesson.diagram()), lesson.code_text()


def test_a_lesson_whose_steps_skip_a_connection_fails_forgot_step():
    """A step that asks for nothing new lets a learner pass without doing
    anything — the scenario gate must catch it."""
    data, diagram, code = _generated("blink")
    step = next(s for s in data["steps"] if s.get("expected_nets") == [["r1:1", "uno:13"]])
    step["expected_nets"] = [["r1:1", "r1:1"]]
    lesson = GeneratedLesson(data, diagram, code)
    failed = {r["name"] for r in scenarios.run_scenarios(lesson) if not r["ok"]}
    assert failed


def test_validator_runs_the_scenarios_as_a_gate():
    data, diagram, code = _generated("digital-read-serial")
    for step in data["steps"]:
        step.pop("hints", None) if step.get("phase") == "build" and step["id"] == "step-4" else None
    errors = validate(data, diagram, code)
    assert errors   # a build step without hints is caught (structure or hints_and_back)
