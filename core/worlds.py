"""The Learn map: one world per group of the official Arduino built-in
examples (lessons/worlds.json), every example a level numbered like a game
(1-1, 1-2, 2-1 ...). A level whose lesson doesn't exist yet stays on the map
as a named "coming soon" stop, so numbers never shift as lessons are added.
Levels are never locked — `requires` only becomes a tip on the map (see
progress.unlocked)."""
import json
from pathlib import Path

WORLDS_FILE = Path(__file__).resolve().parent.parent / "lessons" / "worlds.json"


def load_worlds(path=WORLDS_FILE):
    return json.loads(Path(path).read_text())


def build_map(lessons, config=None):
    """lessons: [{"id", "generated", ...}] -> [{world..., "number", "levels":
    [lesson + {"level": "2-1"} | {"soon": True, "title", "level"}]}].
    Real lessons not in any world go to the Workshop, generated ones to the
    AI Lab (always shown, so there's a place to create). A world with no
    real lesson yet is `coming_soon`."""
    config = config or load_worlds()
    by_id = {l["id"]: l for l in lessons}
    placed, out = set(), []
    for world in config["worlds"]:
        levels = []
        for entry in world["levels"]:
            lesson = by_id.get(entry.get("lesson"))
            if lesson:
                placed.add(lesson["id"])
                levels.append({**lesson, "example": entry["title"]})
            else:
                levels.append({"soon": True, "title": entry["title"]})
        out.append({**{k: v for k, v in world.items() if k != "levels"}, "levels": levels,
                    "coming_soon": not any(not lv.get("soon") for lv in levels)})
    extra = [l for l in lessons if l["id"] not in placed and not l.get("generated")]
    if extra:
        out.append({**config["workshop"], "levels": extra, "coming_soon": False})
    out.append({**config["ai_lab"], "levels": [l for l in lessons if l.get("generated")], "coming_soon": False})
    for n, world in enumerate(out, 1):
        world["number"] = n
        world["levels"] = [{**l, "level": f"{n}-{i}"} for i, l in enumerate(world["levels"], 1)]
    return out
