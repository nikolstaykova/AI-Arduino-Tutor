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


@pytest.mark.parametrize("lesson_id", IDS)
def test_lesson_passes_every_check(lesson_id, monkeypatch):
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
