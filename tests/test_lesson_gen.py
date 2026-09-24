"""core/lesson_gen.py — the generate → validate → repair loop, with a fake
model standing in for Claude. The fake "model" answers with real lesson
files (the hand-authored ones), deliberately broken where a test needs it."""
import copy
import json

import pytest

from core import lesson_gen
from core.lesson import load_lesson


def _files(lesson_id):
    lesson = load_lesson(lesson_id)
    return copy.deepcopy(lesson.data), copy.deepcopy(lesson.diagram()), lesson.code_text()


def _output(data, diagram, code):
    out = {"lesson_json": json.dumps(data), "diagram_json": json.dumps(diagram), "code": code}
    return out, json.dumps(out)


class FakeModel:
    """Returns the queued outputs in order and records every request."""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    def __call__(self, system, messages):
        self.calls.append(copy.deepcopy(messages))
        return self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]


def _errors(data, diagram, code):
    return lesson_gen.validate(data, diagram, code)


# --- the validator on its own -----------------------------------------------

@pytest.mark.parametrize("lesson_id", ["blink", "analog-read-serial", "digital-read-serial"])
def test_every_hand_authored_lesson_passes_the_validator(lesson_id):
    assert _errors(*_files(lesson_id)) == []


def test_missing_series_resistor_is_caught_by_physics():
    data, diagram, code = _files("blink")
    diagram["connections"] = [c for c in diagram["connections"] if c[0] not in ("r1:1", "r1:2")]
    diagram["connections"].append(["bb1:3b.j", "bb1:6b.j", "green", []])
    errors = _errors(data, diagram, code)
    assert any("final_check" in e for e in errors) or any("Circuit physics" in e for e in errors)


def test_sketch_pin_not_wired_is_caught():
    data, diagram, code = _files("blink")
    errors = _errors(data, diagram, code.replace("13", "12"))
    assert any("pin 12" in e for e in errors)


def test_breadboard_hole_in_expected_nets_is_caught():
    data, diagram, code = _files("blink")
    data["steps"][2]["expected_nets"] = [["r1:1", "bb1:3b"]]
    assert any("breadboard hole" in e for e in _errors(data, diagram, code))


def test_unknown_library_id_and_pin_are_caught():
    data, diagram, code = _files("blink")
    data["parts_used"].append("flux-capacitor")
    data["steps"][2]["expected_nets"] = [["r1:3", "uno:13"]]
    errors = _errors(data, diagram, code)
    assert any("'flux-capacitor' is not a library id" in e for e in errors)
    assert any("'3' isn't a pin of wokwi-resistor" in e for e in errors)


def test_final_check_that_disagrees_with_the_diagram_is_caught():
    data, diagram, code = _files("blink")
    data["final_check"]["expected_nets"] = data["final_check"]["expected_nets"][:-1]
    assert any("union of the build steps" in e for e in _errors(data, diagram, code))


def test_floating_input_is_caught_by_physics():
    data, diagram, code = _files("digital-read-serial")
    diagram["connections"] = [c for c in diagram["connections"] if "r1:" not in c[0] + c[1]]
    errors = _errors(data, diagram, code)
    assert errors   # the diagram no longer matches the lesson, and pin 2 floats


def test_four_leg_pushbutton_landing_is_physically_correct_and_accepted():
    """The llm-lesson-gen experiment's one end-to-end failure: listing all
    four pushbutton legs as a landing. Four legs in four columns is exactly
    how a real button straddling the gap sits, so the engine now accepts it
    (legs of one internal contact group are one node, never a short)."""
    data, diagram, code = _files("digital-read-serial")
    for step in data["steps"]:
        if step.get("expected_landing") and any(p.startswith("btn1:") for p in step["expected_landing"]):
            step["expected_landing"] = ["btn1:1.l", "btn1:1.r", "btn1:2.l", "btn1:2.r"]
    assert _errors(data, diagram, code) == []


# --- the loop -----------------------------------------------------------------

def test_valid_output_is_accepted_first_try_and_marked_generated(tmp_path, monkeypatch):
    monkeypatch.setattr(lesson_gen, "LESSONS_ROOT", tmp_path)
    model = FakeModel(_output(*_files("blink")))
    result = lesson_gen.generate_lesson("blink an LED", generate_fn=model)
    assert result["ok"] and len(result["attempts"]) == 1
    assert result["lesson_id"] == "gen-blink"
    saved = json.loads((tmp_path / "gen-blink" / "lesson.json").read_text())
    assert saved["generated"] is True and saved["requires"] == []
    assert (tmp_path / "gen-blink" / "diagram.json").exists() and (tmp_path / "gen-blink" / "code.ino").exists()


def test_errors_are_sent_back_and_a_fixed_second_attempt_is_accepted():
    data, diagram, code = _files("blink")
    model = FakeModel(_output(data, diagram, code.replace("13", "12")), _output(data, diagram, code))
    result = lesson_gen.generate_lesson("blink an LED", generate_fn=model, save=False)
    assert result["ok"] and len(result["attempts"]) == 2
    assert result["attempts"][0]["errors"]
    repair_request = model.calls[1][-1]["content"]
    assert "failed validation" in repair_request and "pin 12" in repair_request


def test_gives_up_after_max_attempts_with_the_last_errors():
    data, diagram, code = _files("blink")
    model = FakeModel(_output(data, diagram, code.replace("13", "12")))
    result = lesson_gen.generate_lesson("blink", generate_fn=model, save=False, max_attempts=3)
    assert not result["ok"] and len(result["attempts"]) == 3 and len(model.calls) == 3
    assert any("pin 12" in e for e in result["errors"])


def test_unparseable_output_is_repaired_not_crashed():
    model = FakeModel(({"lesson_json": "{not json", "diagram_json": "{}", "code": ""}, "raw"), _output(*_files("blink")))
    result = lesson_gen.generate_lesson("blink", generate_fn=model, save=False)
    assert result["ok"] and "couldn't be parsed" in result["attempts"][0]["errors"][0]


def test_inventory_restriction_is_enforced():
    model = FakeModel(_output(*_files("blink")))
    result = lesson_gen.generate_lesson(
        "blink", inventory=["arduino-uno", "breadboard", "led", "jumper-wire"], generate_fn=model, save=False, max_attempts=1,
    )
    assert not result["ok"] and "doesn't own" in result["errors"][0]


def test_suggest_ideas_drops_ideas_needing_unowned_parts():
    ideas = {"ideas": [
        {"title": "Blink", "description": "...", "concept": "digital out", "parts": ["led", "resistor-220"]},
        {"title": "Servo sweep", "description": "...", "concept": "PWM", "parts": ["servo"]},
    ]}
    result = lesson_gen.suggest_ideas(["arduino-uno", "led", "resistor-220"], generate_fn=lambda s, m: (ideas, ""))
    assert [i["title"] for i in result] == ["Blink"]


# --- real parts as physical objects -------------------------------------------

def test_brief_describes_parts_from_the_library():
    facts = lesson_gen.part_facts()
    button = facts["wokwi-pushbutton"]
    assert button["groups"] == [["1.l", "1.r"], ["2.l", "2.r"]]
    assert button["interchangeable"] == [["1", "2"]] and button["placed_together"] and button["straddles_gap"]
    assert facts["wokwi-led"]["polarized"] and not facts["wokwi-resistor"]["polarized"]
    text = lesson_gen._system_prompt(lesson_gen.load_library())
    assert "{part_facts}" not in text
    assert "1.l, 1.r are ONE internal connection" in text
    assert "A single physical object" in text and "straddle the breadboard's centre gap" in text


def test_part_placed_as_one_object_split_across_two_landings_is_caught():
    data, diagram, code = _files("analog-read-serial")
    landing = next(s for s in data["steps"] if isinstance(s.get("expected_landing"), list))
    first = dict(landing, id="step-1a-part1", expected_landing=landing["expected_landing"][:1])
    landing["expected_landing"] = landing["expected_landing"][1:]
    data["steps"].insert(data["steps"].index(landing), first)
    assert any("needs exactly one landing step" in e for e in _errors(data, diagram, code))


def test_landing_that_leaves_out_an_internal_connection_is_caught():
    data, diagram, code = _files("digital-read-serial")
    landing = next(s for s in data["steps"] if isinstance(s.get("expected_landing"), list))
    landing["expected_landing"] = ["btn1:2.r"]   # group 1 isn't mentioned at all
    assert any("doesn't list any of 1.l, 1.r" in e for e in _errors(data, diagram, code))


def test_wiring_a_leg_before_its_part_is_placed_is_caught():
    data, diagram, code = _files("analog-read-serial")
    steps = data["steps"]
    landing_i = next(i for i, s in enumerate(steps) if isinstance(s.get("expected_landing"), list))
    wiring_i = next(i for i, s in enumerate(steps) if s.get("expected_nets"))
    steps.insert(landing_i, steps.pop(wiring_i))
    assert any("before step" in e and "has placed pot1" in e for e in _errors(data, diagram, code))


def test_button_groups_sharing_a_column_half_are_caught_in_the_diagram():
    data, diagram, code = _files("digital-read-serial")
    for c in diagram["connections"]:
        if c[0] == "btn1:1.l":
            c[1] = "bb1:4t.c"   # group 1 now shares column 4t with group 2
    errors = _errors(data, diagram, code)
    assert any("share breadboard column-half 4t" in e for e in errors)


def test_button_that_doesnt_straddle_the_gap_is_caught():
    data, diagram, code = _files("digital-read-serial")
    moved = {"btn1:2.r": "bb1:4t.a", "btn1:1.r": "bb1:6t.a"}   # every leg now in the top half
    for c in diagram["connections"]:
        for i in (0, 1):
            if c[i] in moved:
                c[1 - i] = moved[c[i]]
    assert any("must straddle the centre gap" in e for e in _errors(data, diagram, code))


def test_part_whose_legs_are_not_connected_to_holes_is_named_directly():
    """Sonnet's first AnalogReadSerial draft placed the pot by position only,
    with no leg-to-hole connections — the error must say so plainly."""
    data, diagram, code = _files("analog-read-serial")
    diagram["connections"] = [c for c in diagram["connections"] if not c[0].startswith("pot1:") and not c[1].startswith("pot1:")]
    errors = _errors(data, diagram, code)
    assert any("pot1:SIG isn't in any connection" in e for e in errors)
