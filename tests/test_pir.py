"""The PIR motion sensor (HC-SR501): powered from VCC/GND, it drives OUT high
(~3.3 V) while it sees motion and low when still; unpowered it floats."""
from core import flow_explorer, physics
from core.lesson import load_lesson

PARTS = [{"id": "uno", "type": "wokwi-arduino-uno"}, {"id": "pir1", "type": "wokwi-pir-motion-sensor"},
         {"id": "r1", "type": "wokwi-resistor", "attrs": {"value": "220"}}, {"id": "led1", "type": "wokwi-led"}]
CODE = "void setup(){ pinMode(2, INPUT); } void loop(){}"
POWERED = [("pir1:VCC", "uno:5V"), ("pir1:GND", "uno:GND.1"), ("pir1:OUT", "uno:2")]


def readings(pairs, code=CODE):
    r = physics.analyze(pairs, PARTS, code)
    return {s["label"]: s["pins"]["uno:2"]["reading"] for s in r["scenarios"]}, {f["kind"] for f in r["findings"]}


def test_motion_reads_high_and_stillness_low_with_no_resistor_needed():
    reads, findings = readings(POWERED)
    assert reads == {"pir1 sees no motion": "LOW", "pir1 sees motion": "HIGH"}
    assert findings == set()                     # no floating-input warning: OUT is actively driven


def test_without_power_it_senses_nothing_and_says_why():
    reads, findings = readings([("pir1:OUT", "uno:2")])
    assert set(reads.values()) == {"floating"} and "pir_unpowered" in findings


def test_power_the_wrong_way_round_is_caught():
    reads, findings = readings([("pir1:VCC", "uno:GND.1"), ("pir1:GND", "uno:5V"), ("pir1:OUT", "uno:2")])
    assert set(reads.values()) == {"floating"} and "pir_reversed" in findings


def test_out_can_light_an_led_dimly_like_the_real_module():
    r = physics.analyze([("pir1:VCC", "uno:5V"), ("pir1:GND", "uno:GND.1"), ("pir1:OUT", "r1:1"), ("r1:2", "led1:A"), ("led1:C", "uno:GND.2")], PARTS, "")
    states = {s["label"]: s["leds"]["led1"]["state"] for s in r["scenarios"]}
    assert states["pir1 sees no motion"] == "off" and states["pir1 sees motion"] in ("dim", "on")


def test_the_motion_alarm_lesson_holds_in_every_learner_flow():
    result = flow_explorer.explore(load_lesson("motion-alarm"), mode="smart")
    assert result["flows"] >= 30 and result["failures"] == []


def test_two_signals_never_share_a_pin_in_the_full_explorer():
    for f in flow_explorer.enumerate_flows(load_lesson("motion-alarm")):
        assert len(set(f["pins"].values())) == len(f["pins"])
