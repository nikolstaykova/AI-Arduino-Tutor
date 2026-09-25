"""Every lesson in lessons/ — hand-made, from the lesson kit, or generated —
passes the same validator Claude's lessons must pass (smart build-way sample,
so the whole set runs in about a minute), and every map level that names a
lesson points at one that exists."""
import json
import os
from pathlib import Path

import pytest

from core import lesson_gen

LESSONS = Path(__file__).resolve().parent.parent / "lessons"
IDS = sorted(p.parent.name for p in LESSONS.glob("*/lesson.json"))


def _steps(lesson_id):
    return len(json.loads((LESSONS / lesson_id / "lesson.json").read_text()).get("steps", []))


# The replay scenarios and build-way checks grow with a lesson's length (and
# with every button or resistor that can sit either way round), so lessons
# over LONG steps — the 5-button USB lessons, the 8x8 matrix, Analog Write
# Mega: several minutes each — run only with CQ_SLOW_TESTS=1. The lesson kit
# (tools/lesson_kit.py) validates every lesson in full whenever it writes them.
LONG = 26


@pytest.mark.parametrize("lesson_id", IDS)
def test_lesson_passes_every_check(lesson_id, monkeypatch):
    if _steps(lesson_id) > LONG and not os.environ.get("CQ_SLOW_TESTS"):
        pytest.skip(f"{lesson_id} has {_steps(lesson_id)} steps — run with CQ_SLOW_TESTS=1")
    monkeypatch.setenv("CQ_FLOW_CHECK", "smart")
    folder = LESSONS / lesson_id
    errors = lesson_gen.validate(json.loads((folder / "lesson.json").read_text()), json.loads((folder / "diagram.json").read_text()),
                                 (folder / "code.ino").read_text())
    assert errors == []


def test_every_map_level_with_a_lesson_exists():
    worlds = json.loads((LESSONS / "worlds.json").read_text())
    for world in worlds["worlds"]:
        for level in world["levels"]:
            if level.get("lesson"):
                assert (LESSONS / level["lesson"] / "lesson.json").exists(), level
