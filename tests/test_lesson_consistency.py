"""A lesson's circuit and its parts list must describe the same real parts:
the diagram's resistor value is the resistor the learner gathers (Digital
Read Serial once asked for a 10 kΩ resistor while its diagram said 1 kΩ)."""
import pytest

from core.lesson import load_lesson
from core.lesson_finder import all_lesson_ids
from core.library import load_library

LIB = load_library()


@pytest.mark.parametrize("lesson_id", all_lesson_ids())
def test_every_diagram_part_is_in_the_parts_list(lesson_id):
    lesson = load_lesson(lesson_id)
    used = set(lesson.data.get("parts_used", []))
    for part in lesson.diagram()["parts"]:
        cards = LIB.find_by_wokwi_type(part["type"], part.get("attrs", {}).get("value"))
        if not cards:
            continue
        assert any(c["id"] in used for c in cards), (
            f"{lesson_id}: diagram part {part['id']} ({part['type']} {part.get('attrs', {})}) "
            f"is none of {sorted(c['id'] for c in cards)}, but parts_used is {sorted(used)}")
