"""Loads a lesson.json plus its co-located diagram.json/code.ino (LESSONS.md schema)."""
import json
from pathlib import Path

LESSONS_ROOT = Path(__file__).resolve().parent.parent / "lessons"


class Lesson:
    def __init__(self, data, folder):
        self.data = data
        self.folder = folder
        self.id = data["id"]
        self.title = data["title"]
        self.steps = data["steps"]
        self._diagram = None

    def step(self, index):
        if 0 <= index < len(self.steps):
            return self.steps[index]
        return None

    def step_count(self):
        return len(self.steps)

    def code_path(self):
        return self.folder / self.data["code"]

    def code_text(self):
        """Default: read code.ino from disk. A translated lesson
        (core/board_translate.py) overrides this to return already
        board-adjusted, in-memory code with no disk write."""
        return self.code_path().read_text()

    def diagram_path(self):
        return self.folder / self.data["wokwi_diagram"]

    def diagram(self):
        """Lazily load and cache the lesson's Wokwi diagram.json."""
        if self._diagram is None:
            with open(self.diagram_path()) as f:
                self._diagram = json.load(f)
        return self._diagram

    def final_check_nets(self):
        return self.data["final_check"]["expected_nets"]


def load_lesson(lesson_id):
    folder = LESSONS_ROOT / lesson_id
    with open(folder / "lesson.json") as f:
        data = json.load(f)
    return Lesson(data, folder)
