"""Lessons from a real tutorial follow it exactly: every part with its real
quantity and value, substituted ONLY when the library doesn't have it, and a
generated circuit that doesn't match the guide goes back to Claude."""
import io
import json

import pytest

from core import guide_import
from core.library import load_library

LIB = load_library()

# what Claude extracts from build-electronic-circuits.com/usb-flashlight
FLASHLIGHT = {
    "title": "USB Flashlight", "summary": "Five LEDs, each with its own resistor, in parallel on USB 5V.",
    "behaviour": "The LEDs light when it's switched on.", "uses_microcontroller": False, "board": "",
    "switch_behaviour": "unspecified",
    "parts": [
        {"name": "LED", "quantity": 5, "value": "", "color": "white", "optional": False},
        {"name": "Resistor", "quantity": 5, "value": "100 Ω", "color": "", "optional": False},
        {"name": "USB breakout board", "quantity": 1, "value": "", "color": "", "optional": False},
        {"name": "Prototyping board", "quantity": 1, "value": "", "color": "", "optional": False},
        {"name": "Switch", "quantity": 1, "value": "", "color": "", "optional": True},
        {"name": "Soldering iron", "quantity": 1, "value": "", "color": "", "optional": False},
    ],
    "circuit": ["each LED in series with its own 100 Ω resistor", "the five LED+resistor pairs in parallel between USB 5V and GND"],
    "code": "",
}


def test_html_to_text_keeps_the_content_and_drops_scripts():
    title, text = guide_import.html_to_text("<html><head><title>USB Flashlight</title><script>x=1</script></head>"
                                             "<body><nav>menu</nav><h1>Parts</h1><ul><li>5x LEDs</li><li>5x 100 ohm</li></ul></body></html>")
    assert title == "USB Flashlight" and "5x LEDs" in text and "5x 100 ohm" in text
    assert "x=1" not in text and "menu" not in text


def test_fetch_rejects_non_web_links_and_reads_pages():
    with pytest.raises(ValueError):
        guide_import.fetch_text("file:///etc/passwd")

    class Resp(io.BytesIO):
        headers = None
        def __enter__(self): return self
        def __exit__(self, *a): return False
    page = b"<title>T</title><p>hello</p>" + b"<p>" + b"A real guide paragraph with parts and steps. " * 20 + b"</p>"
    title, text = guide_import.fetch_text("https://example.com/g", opener=lambda req, timeout: Resp(page))
    assert title == "T" and "hello" in text
    with pytest.raises(ValueError, match="JavaScript"):          # a page with (almost) nothing readable
        guide_import.fetch_text("https://example.com/js", opener=lambda req, timeout: Resp(b"<title>T</title><div id=app></div>"))


def test_parts_are_kept_exactly_and_substituted_only_when_missing():
    plan = guide_import.map_parts(FLASHLIGHT, LIB)
    by = {r["name"]: r for r in plan["parts"]}
    assert by["LED"]["card"] == "led" and by["LED"]["status"] == "exact" and by["LED"]["quantity"] == 5
    assert by["Resistor"]["card"] == "resistor-100" and by["Resistor"]["status"] == "exact"      # we have 100 Ω
    assert by["USB breakout board"]["card"] == "arduino-uno" and by["USB breakout board"]["status"] == "substitute"
    assert by["Prototyping board"]["card"] == "breadboard" and "Solder" in by["Prototyping board"]["note"]
    assert by["Switch"]["card"] == "slide-switch"                                               # on/off, stays on
    assert by["Soldering iron"]["status"] == "tool"
    assert plan["ok"] and guide_import.required_counts(plan) == {"led": 5, "resistor-100": 5, "slide-switch": 1}


def test_a_value_we_dont_stock_is_the_nearest_one_and_says_so():
    row = guide_import.map_part({"name": "Resistor", "value": "120 ohm", "quantity": 1}, "none", LIB)
    assert row["status"] == "substitute" and row["card"] == "resistor-100" and "nearest" in row["note"]


def test_a_momentary_guide_switch_stays_a_pushbutton():
    row = guide_import.map_part({"name": "Switch", "value": "", "quantity": 1}, "momentary", LIB)
    assert row["card"] == "pushbutton"


def test_parts_we_cant_simulate_block_the_lesson_honestly():
    plan = guide_import.map_parts({**FLASHLIGHT, "parts": FLASHLIGHT["parts"] + [{"name": "Servo Motor", "quantity": 1, "value": "", "color": "", "optional": False}]}, LIB)
    assert not plan["ok"] and plan["blocked"][0]["name"] == "Servo Motor"
    result = guide_import.generate(plan, library=LIB, generate_fn=lambda *a: pytest.fail("must not call Claude"), save=False)
    assert not result["ok"] and "Servo Motor" in result["errors"][0]


def test_the_requirements_pin_down_parts_values_switch_and_circuit():
    text = guide_import.requirements_text({**guide_import.map_parts(FLASHLIGHT, LIB), "url": "https://x"}, LIB)
    assert "5 × `led`" in text and "5 × `resistor-100`" in text and 'attrs.value "100"' in text and "colour: white" in text
    assert "1 × `slide-switch`" in text and "parallel" in text and "empty sketch" in text
    assert "USB breakout board → `arduino-uno`" in text


def test_a_circuit_that_simplifies_the_guide_is_sent_back():
    check = guide_import.check_against_plan(guide_import.map_parts(FLASHLIGHT, LIB), LIB)
    one_led = {"parts": [{"type": "wokwi-arduino-uno", "id": "uno"}, {"type": "wokwi-led", "id": "led1"},
                         {"type": "wokwi-resistor", "id": "r1", "attrs": {"value": "220"}}, {"type": "wokwi-pushbutton", "id": "btn1"}]}
    errors = check({}, one_led)
    assert any("5 × LED" in e and "has 1" in e for e in errors)
    assert any("220Ω" in e for e in errors) and any("Pushbutton" in e for e in errors)
    faithful = {"parts": [{"type": "wokwi-arduino-uno", "id": "uno"}, {"type": "wokwi-slide-switch", "id": "sw1"}]
                + [{"type": "wokwi-led", "id": f"led{i}"} for i in range(1, 6)]
                + [{"type": "wokwi-resistor", "id": f"r{i}", "attrs": {"value": "100"}} for i in range(1, 6)]}
    assert check({}, faithful) == []


def test_generation_uses_the_check_and_records_the_source():
    plan = {**guide_import.map_parts(FLASHLIGHT, LIB), "url": "https://guide"}
    seen = []

    def fake_model(system, messages):
        seen.append(messages[-1]["content"])
        return {"lesson_json": "{}", "diagram_json": "{}", "code": ""}, "{}"
    result = guide_import.generate(plan, library=LIB, generate_fn=fake_model, save=False)
    assert not result["ok"]                           # the fake lesson is empty — fine; what matters is the request
    assert "follows this tutorial EXACTLY" in seen[0]


MEMORY_GAME = [{"name": "Arduino Uno", "quantity": 1, "value": "", "color": "", "optional": False},
               {"name": "LEDs", "quantity": 4, "value": "", "color": "red, yellow, green, blue", "optional": False},
               {"name": "Push buttons", "quantity": 5, "value": "", "color": "", "optional": False},
               {"name": "Piezo Buzzer", "quantity": 1, "value": "", "color": "", "optional": False},
               {"name": "Resistors", "quantity": 4, "value": "220Ω", "color": "", "optional": False},
               {"name": "Resistors", "quantity": 5, "value": "10kΩ", "color": "", "optional": False}]


def test_parts_we_have_are_exact_whatever_the_guide_calls_them():
    plan = guide_import.map_parts({**FLASHLIGHT, "uses_microcontroller": True, "board": "Arduino Uno", "switch_behaviour": "momentary", "parts": MEMORY_GAME}, LIB)
    assert all(r["status"] == "exact" for r in plan["parts"]), [(r["guide"], r["status"]) for r in plan["parts"]]
    assert guide_import.required_counts(plan) == {"led": 4, "pushbutton": 5, "buzzer": 1, "resistor-220": 4, "resistor-10k": 5}
