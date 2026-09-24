"""Pin substitution must rewrite only pins — in sketches and in the tutor's
own words — never unrelated numbers (delay(2), array sizes, "group-2
contact", "column 13")."""
from core import engine
from core.lesson import load_lesson
from core.library import load_library

SKETCH = """const int buttonPin = 2;  // the button is on pin 2
#define LED_PIN 13
void setup() { Serial.begin(9600); pinMode(buttonPin, INPUT); pinMode(LED_BUILTIN, OUTPUT); }
void loop() { int v = digitalRead(2); delay(2); int arr[2] = {0, 2}; tone(2, 440); shiftOut(2, 13, MSBFIRST, 2); analogRead(A0); }"""


def test_code_rewrite_touches_only_pins():
    out = engine.rewrite_pins_in_code(SKETCH, [("2", "3"), ("13", "12"), ("LED_BUILTIN", "12"), ("A0", "A1")])
    assert "const int buttonPin = 3;" in out and "on pin 3" in out
    assert "#define LED_PIN 12" in out
    assert "pinMode(12, OUTPUT)" in out and "digitalRead(3)" in out and "analogRead(A1)" in out
    assert "tone(3, 440)" in out and "shiftOut(3, 12, MSBFIRST, 2)" in out
    assert "delay(2)" in out and "int arr[2] = {0, 2}" in out and "Serial.begin(9600)" in out


def test_code_rewrite_is_one_pass_not_a_chain():
    """2→3 and 3→4 at once: pin 2 must become 3, not 4."""
    out = engine.rewrite_pins_in_code("pinMode(2, OUTPUT); pinMode(3, INPUT);", [("2", "3"), ("3", "4")])
    assert out == "pinMode(3, OUTPUT); pinMode(4, INPUT);"


def test_prose_rewrite_touches_only_pin_mentions():
    text = "Wire the group-2 contact (column 13, 2 legs) to the Arduino's digital pin <b>2</b>, then pin 13 and A0."
    out = engine.rewrite_pin_mentions(text, [("2", "3"), ("13", "12"), ("A0", "A1")])
    assert out == "Wire the group-2 contact (column 13, 2 legs) to the Arduino's digital pin <b>3</b>, then pin 12 and A1."


def test_digital_read_serial_instructions_keep_group_names_when_pin_2_moves():
    """The hand-made lesson's own clips say "group-2 contact": moving the
    button's signal to pin 3 used to turn that into "group-3 contact"."""
    lesson, library = load_lesson("digital-read-serial"), load_library()
    board = [["uno:3" if p == "uno:2" else p for p in c[:2]] for c in lesson.diagram()["connections"]]
    state = engine.initial_state()
    state, _ = engine.handle_event(lesson, library, state, {"command": "start"})
    clips = []
    for _ in range(lesson.step_count() + 2):
        if state["finished"]:
            break
        event = {"command": "done"} if state["phase"] in ("gather", "upload") else {"command": "done", "detected_pairs": board}
        state, actions = engine.handle_event(lesson, library, state, event)
        clips += [a["text"] for a in actions if a["type"] == "play_clip"]
    assert state["finished"]
    assert not any("group-3" in c for c in clips), [c for c in clips if "group-3" in c]
    assert any("pin <b>3</b>" in c or "pin 3" in c for c in clips)
