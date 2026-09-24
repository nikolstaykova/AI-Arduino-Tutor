"""core/lesson_finder.py — "I have these parts, what can I build?"."""
from core.lesson_finder import find_lessons, resolve_inventory

BASICS = ["arduino", "usb cable", "breadboard", "jumper wire"]


def _by_id(inventory):
    ids, _ = resolve_inventory(inventory)
    return {r["id"]: r for r in find_lessons(ids)}


def test_resolve_inventory_accepts_aliases_and_spaced_ids_and_reports_unknowns():
    ids, unknown = resolve_inventory(["Arduino", "usb cable", "220 ohm resistor", "pot", "flux capacitor"])
    assert ids == ["arduino-uno", "usb-cable", "resistor-220", "potentiometer-10k"]
    assert unknown == ["flux capacitor"]


def test_exact_parts_make_a_lesson_ready():
    result = _by_id(BASICS + ["potentiometer"])
    assert result["analog-read-serial"]["status"] == "ready"


def test_a_safe_resistor_substitute_is_offered_with_the_physics_behind_it():
    blink = _by_id(BASICS + ["led", "resistor-220"])["blink"]
    assert blink["status"] == "substitute"
    [sub] = blink["substitutes"]
    assert (sub["need"], sub["use"]) == ("resistor-1k", "resistor-220")
    assert "brighter" in sub["note"] and "11.8 mA" in sub["note"]


def test_a_much_larger_resistor_still_works_but_says_the_led_is_barely_visible():
    blink = _by_id(BASICS + ["led", "resistor-10k"])["blink"]
    assert blink["status"] == "substitute"
    assert "barely visible" in blink["substitutes"][0]["note"]


def test_missing_parts_are_listed_and_sorted_last():
    results = find_lessons(resolve_inventory(BASICS + ["led", "resistor-1k"])[0])
    assert results[0]["id"] == "blink" and results[0]["status"] == "ready"
    analog = next(r for r in results if r["id"] == "analog-read-serial")
    assert analog["status"] == "missing" and analog["missing"] == ["potentiometer-10k"]


def test_unlock_state_is_reported_when_progress_is_given():
    ids, _ = resolve_inventory(BASICS + ["potentiometer"])
    results = {r["id"]: r for r in find_lessons(ids, progress={"completed": {}})}
    assert results["blink"]["unlocked"] and not results["analog-read-serial"]["unlocked"]
