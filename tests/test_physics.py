"""core/physics.py — every expected number here is a hand calculation
(Ohm's law around the loop), not a value copied back from the solver.

Model constants the hand calculations use: I/O pin output resistance
25 ohm, LED series resistance 10 ohm, red LED Vf 2.0 V (see physics.py's
module docstring for where each comes from)."""
import copy
from pathlib import Path

import pytest

from core import physics
from core.lesson import load_lesson

LESSONS_ROOT = Path(__file__).resolve().parent.parent / "lessons"


def _lesson_circuit(lesson_id):
    lesson = load_lesson(lesson_id)
    diagram = lesson.diagram()
    pairs = [c[:2] for c in diagram["connections"]]
    parts = copy.deepcopy(diagram["parts"])
    code = (LESSONS_ROOT / lesson_id / lesson.data["code"]).read_text()
    return pairs, parts, code


def _set_value(parts, part_id, value):
    for part in parts:
        if part["id"] == part_id:
            part.setdefault("attrs", {})["value"] = value


def _kinds(result):
    return {(f["severity"], f["kind"], f["component"]) for f in result["findings"]}


def _only(result):
    assert len(result["scenarios"]) == 1
    return result["scenarios"][0]


# --- parsing ---------------------------------------------------------------

@pytest.mark.parametrize("text, ohms", [
    ("220", 220), ("1000", 1000), ("4.7k", 4700), ("10k", 10000), ("1M", 1e6), ("10kΩ", 10000), (None, 1000), ("junk", 1000),
])
def test_parse_resistance(text, ohms):
    assert physics.parse_resistance(text) == pytest.approx(ohms)


def test_pin_modes_from_code_resolves_literals_constants_and_analog_pins():
    code = """
    const int buttonPin = 2;
    #define LED 9
    void setup() {
      pinMode(LED_BUILTIN, OUTPUT);
      pinMode(buttonPin, INPUT_PULLUP);
      pinMode(LED, OUTPUT);
    }
    void loop() { analogRead(A0); analogWrite(6, 128); }
    """
    assert physics.pin_modes_from_code(code) == {
        "13": "OUTPUT", "2": "INPUT_PULLUP", "9": "OUTPUT", "A0": "ANALOG_IN", "6": "OUTPUT",
    }


# --- Blink: resistor value decides the LED current --------------------------

@pytest.mark.parametrize("value, expected_ma, state", [
    ("1000", 3.0 / 1035 * 1000, "on"),      # the lesson's own reference diagram
    ("220", 3.0 / 255 * 1000, "on"),
    ("10000", 3.0 / 10035 * 1000, "dim"),
])
def test_blink_led_current_follows_ohms_law(value, expected_ma, state):
    pairs, parts, code = _lesson_circuit("blink")
    _set_value(parts, "r1", value)
    led = _only(physics.analyze(pairs, parts, code))["leds"]["led1"]
    assert led["current_ma"] == pytest.approx(expected_ma, abs=0.01)
    assert led["state"] == state


def test_blink_reference_circuit_is_hazard_free():
    pairs, parts, code = _lesson_circuit("blink")
    result = physics.analyze(pairs, parts, code)
    assert not result["hazard"]
    assert result["findings"] == []
    assert result["unmodeled"] == []


def test_led_without_series_resistor_burns_out_and_overloads_the_pin():
    pairs, parts, code = _lesson_circuit("blink")
    # Remove the resistor; bridge pin 13's strip straight to the LED anode's strip.
    pairs = [p for p in pairs if p[0] not in ("r1:1", "r1:2")] + [["bb1:3b.j", "bb1:6b.j"]]
    result = physics.analyze(pairs, parts, code)
    led = _only(result)["leds"]["led1"]
    assert led["current_ma"] == pytest.approx(3.0 / 35 * 1000, abs=0.01)   # ~86 mA
    assert ("hazard", "led_overcurrent", "led1") in _kinds(result)
    assert ("hazard", "pin_overcurrent", "uno:13") in _kinds(result)
    assert result["hazard"]


def test_led_between_rated_and_absolute_max_is_a_warning_not_a_hazard():
    pairs, parts, code = _lesson_circuit("blink")
    _set_value(parts, "r1", "100")   # 3 V / 135 ohm ≈ 22 mA
    result = physics.analyze(pairs, parts, code)
    assert ("warning", "led_overcurrent", "led1") in _kinds(result)
    assert ("warning", "pin_overcurrent", "uno:13") in _kinds(result)
    assert not result["hazard"]


def test_reversed_led_stays_dark_and_says_why():
    pairs, parts, code = _lesson_circuit("blink")
    swapped = {"led1:A": "led1:C", "led1:C": "led1:A"}
    pairs = [[swapped.get(a, a), b] for a, b in pairs]
    result = physics.analyze(pairs, parts, code)
    assert _only(result)["leds"]["led1"]["state"] == "off"
    assert ("warning", "led_reversed", "led1") in _kinds(result)
    assert not result["hazard"]


def test_blue_led_uses_its_higher_forward_voltage():
    pairs, parts, code = _lesson_circuit("blink")
    for part in parts:
        if part["id"] == "led1":
            part["attrs"]["color"] = "blue"
    led = _only(physics.analyze(pairs, parts, code))["leds"]["led1"]
    assert led["current_ma"] == pytest.approx((5.0 - 3.1) / 1035 * 1000, abs=0.01)


def test_led_with_nothing_driving_it_is_off_without_findings():
    pairs, parts, _ = _lesson_circuit("blink")
    result = physics.analyze(pairs, parts, code="void setup() {} void loop() {}")
    assert _only(result)["leds"]["led1"]["state"] == "off"
    assert result["findings"] == []


# --- shorts ----------------------------------------------------------------

def test_5v_wired_straight_to_gnd_is_a_short_circuit_hazard():
    pairs, parts, code = _lesson_circuit("blink")
    result = physics.analyze(pairs + [["uno:5V", "uno:GND.2"]], parts, code)
    assert ("hazard", "short_circuit", "uno:5V") in _kinds(result)


def test_output_pin_wired_straight_to_gnd_overloads_the_pin():
    pairs, parts, code = _lesson_circuit("blink")
    result = physics.analyze(pairs + [["uno:13", "uno:GND.1"]], parts, code)
    assert ("hazard", "pin_overcurrent", "uno:13") in _kinds(result)   # 5 V / 25 ohm = 200 mA


def test_unused_5v_pin_adds_no_supply():
    pairs, parts, code = _lesson_circuit("blink")
    assert "uno:5V" not in _only(physics.analyze(pairs, parts, code))["pins"]


# --- DigitalReadSerial: pushbutton + pull-down ------------------------------

def test_button_with_pull_down_reads_low_released_and_high_pressed():
    pairs, parts, code = _lesson_circuit("digital-read-serial")
    result = physics.analyze(pairs, parts, code)
    by_state = {s["pressed"]["btn1"]: s for s in result["scenarios"]}
    assert by_state[False]["pins"]["uno:2"]["reading"] == "LOW"
    assert by_state[True]["pins"]["uno:2"]["reading"] == "HIGH"
    # pressed: 5 V across the 10 kohm pull-down (the lesson's reference value, as in Arduino's example)
    assert by_state[True]["pins"]["uno:5V"]["current_ma"] == pytest.approx(0.5, abs=0.05)
    assert result["findings"] == []


def test_button_without_pull_down_floats_when_released():
    pairs, parts, code = _lesson_circuit("digital-read-serial")
    pairs = [p for p in pairs if "r1:" not in p[0] + p[1]]
    result = physics.analyze(pairs, parts, code)
    by_state = {s["pressed"]["btn1"]: s for s in result["scenarios"]}
    assert by_state[False]["pins"]["uno:2"]["reading"] == "floating"
    assert by_state[True]["pins"]["uno:2"]["reading"] == "HIGH"
    assert ("warning", "floating_input", "uno:2") in _kinds(result)


def test_input_pullup_needs_no_external_resistor():
    pairs, parts, _ = _lesson_circuit("digital-read-serial")
    pairs = [p for p in pairs if "r1:" not in p[0] + p[1]]
    code = "void setup() { pinMode(2, INPUT_PULLUP); } void loop() { digitalRead(2); }"
    result = physics.analyze(pairs, parts, code)
    assert all(s["pins"]["uno:2"]["reading"] != "floating" for s in result["scenarios"])
    assert ("warning", "floating_input", "uno:2") not in _kinds(result)


# --- AnalogReadSerial: potentiometer divider ---------------------------------

def test_potentiometer_at_mid_travel_reads_half_scale():
    pairs, parts, code = _lesson_circuit("analog-read-serial")
    result = physics.analyze(pairs, parts, code)
    a0 = _only(result)["pins"]["uno:A0"]
    assert a0["voltage"] == pytest.approx(2.5, abs=0.01)
    assert a0["reading"] == 512 or a0["reading"] == 511
    assert result["findings"] == []


# --- every shipped lesson solves cleanly -------------------------------------

@pytest.mark.parametrize("lesson_id", ["blink", "analog-read-serial", "digital-read-serial"])
def test_every_lesson_reference_diagram_is_hazard_free_and_fully_modelled(lesson_id):
    pairs, parts, code = _lesson_circuit(lesson_id)
    result = physics.analyze(pairs, parts, code)
    assert not result["hazard"]
    assert result["unmodeled"] == []


# --- engine integration: final_check -----------------------------------------

def _walk_to_final_check(lesson_id):
    from core import engine
    from core.library import load_library
    lesson, library = load_lesson(lesson_id), load_library()
    state = engine.initial_state()
    state, _ = engine.handle_event(lesson, library, state, {"command": "start"})
    pairs = [c[:2] for c in lesson.diagram()["connections"]]
    # Steps are passed with the engine's own "correct" label; only the
    # final check gets the real, complete board. (Handing the finished
    # board to an early step is "building ahead", which the step checks
    # deliberately don't accept — a separate question from physics.)
    while state["phase"] != "final_check":
        state, actions = engine.handle_event(lesson, library, state, {"command": "done", "label": "correct"})
        assert not any(a["type"] == "feedback" and a["verdict"] == "wrong" for a in actions), actions
    return engine, lesson, library, state, pairs


@pytest.mark.parametrize("lesson_id", ["blink", "analog-read-serial", "digital-read-serial"])
def test_final_check_completes_on_a_physically_sound_circuit(lesson_id):
    engine, lesson, library, state, pairs = _walk_to_final_check(lesson_id)
    state, actions = engine.handle_event(lesson, library, state, {"command": "done", "detected_pairs": pairs})
    assert state["finished"]
    assert not any(a["type"] == "physics_hazard" for a in actions)


def test_final_check_refuses_a_matching_circuit_that_shorts_the_supply():
    engine, lesson, library, state, pairs = _walk_to_final_check("blink")
    shorted = pairs + [["uno:5V", "uno:GND.2"]]
    state, actions = engine.handle_event(lesson, library, state, {"command": "done", "detected_pairs": shorted})
    assert not state["finished"]
    hazards = [a for a in actions if a["type"] == "physics_hazard"]
    assert [h["kind"] for h in hazards] == ["short_circuit"]
    assert any(a["type"] == "feedback" and a["verdict"] == "wrong" for a in actions)
    # Fixing it completes the lesson.
    state, actions = engine.handle_event(lesson, library, state, {"command": "done", "detected_pairs": pairs})
    assert state["finished"]


def test_final_check_physics_uses_the_substituted_pin_from_the_adjusted_code():
    """Blink wired to pin 12 instead of 13: the adjusted sketch drives pin
    12, so pin 12 is the one solved as a HIGH output and the LED lights."""
    from core import engine
    from core.library import load_library
    lesson, library = load_lesson("blink"), load_library()
    pairs = [["uno:12", p[1]] if p[0] == "uno:13" else ([p[0], "uno:12"] if p[1] == "uno:13" else p)
             for p in (c[:2] for c in lesson.diagram()["connections"])]
    state = engine.initial_state()
    state, _ = engine.handle_event(lesson, library, state, {"command": "start"})
    while state["phase"] != "final_check":
        state, _ = engine.handle_event(lesson, library, state, {"command": "done", "detected_pairs": pairs})
    assert "pinMode(12, OUTPUT)" in engine._adjusted_code(lesson, state)
    result = physics.analyze(pairs, lesson.diagram()["parts"], engine._adjusted_code(lesson, state), library)
    assert result["scenarios"][0]["leds"]["led1"]["state"] == "on"
    state, _ = engine.handle_event(lesson, library, state, {"command": "done", "detected_pairs": pairs})
    assert state["finished"]


def test_button_with_both_groups_on_one_connection_is_a_bypassed_switch():
    pairs, parts, code = _lesson_circuit("digital-read-serial")
    pairs = pairs + [["btn1:1.l", "btn1:2.l"]]
    result = physics.analyze(pairs, parts, code)
    assert ("warning", "switch_bypassed", "btn1") in _kinds(result)
    assert {s["pins"]["uno:2"]["reading"] for s in result["scenarios"]} == {"HIGH"}
