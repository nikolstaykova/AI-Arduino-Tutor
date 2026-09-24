"""The Learn map: themed worlds, game-style level numbers, no hard locks."""
import json

import bench_server
from core import progress
from core.worlds import build_map, load_worlds

LESSONS = [{"id": "blink"}, {"id": "digital-read-serial"}, {"id": "analog-read-serial"},
           {"id": "my-extra"}, {"id": "gen-1", "generated": True}]


def test_every_lesson_lands_in_exactly_one_world_with_a_level_number():
    worlds = build_map(LESSONS)
    real = [lv for w in worlds for lv in w["levels"] if not lv.get("soon")]
    assert sorted(lv["id"] for lv in real) == sorted(l["id"] for l in LESSONS)
    numbers = {lv["id"]: lv["level"] for lv in real}
    assert numbers["blink"] == "1-2"                       # Basics: Bare Minimum is 1-1
    assert worlds[-1]["id"] == "ai-lab" and [lv["id"] for lv in worlds[-1]["levels"]] == ["gen-1"]
    assert any(w["id"] == "workshop" and w["levels"][0]["id"] == "my-extra" for w in worlds)


def test_worlds_follow_the_official_arduino_example_groups():
    config = load_worlds()
    assert [w["group"] for w in config["worlds"]] == ["Basics", "Digital", "Analog", "Communication", "Control Structures",
                                                      "Sensors", "Display", "Strings", "USB", "Arduino ISP"]
    assert sum(len(w["levels"]) for w in config["worlds"]) == 68


def test_examples_without_a_lesson_stay_as_named_coming_soon_levels():
    worlds = build_map([{"id": "blink"}])
    basics = worlds[0]
    assert [lv.get("title") for lv in basics["levels"] if lv.get("soon")][:1] == ["Bare Minimum"]
    assert not basics["coming_soon"] and worlds[1]["coming_soon"]
    assert worlds[1]["levels"][2] == {"soon": True, "title": "Debounce", "level": "2-3"}
    assert worlds[-1]["id"] == "ai-lab" and worlds[-1]["levels"] == []


def test_every_real_lesson_is_placed_in_a_themed_world():
    config = load_worlds()
    placed = {lv.get("lesson") for w in config["worlds"] for lv in w["levels"]}
    assert {"blink", "digital-read-serial", "analog-read-serial"} <= placed


def test_stars():
    assert progress.stars_for({"finished": False, "hints": 0, "wrong": 0}) == 0
    assert progress.stars_for({"finished": True, "hints": 2, "wrong": 1}) == 1
    assert progress.stars_for({"finished": True, "hints": 0, "wrong": 1}) == 2
    assert progress.stars_for({"finished": True, "hints": 0, "wrong": 0}) == 3


def test_best_stars_are_kept_on_a_worse_replay():
    good = {"xp": 100, "finished": True, "hints": 0, "wrong": 0, "substitutions": 0, "perfect": True}
    bad = {"xp": 60, "finished": True, "hints": 3, "wrong": 2, "substitutions": 0, "perfect": False}
    state, _ = progress.apply_session(progress.empty_progress(), "blink", good)
    state, _ = progress.apply_session(state, "blink", bad)
    assert state["completed"]["blink"]["stars"] == 3


def test_any_level_can_be_played_first_and_is_marked_completed(tmp_path, monkeypatch):
    saved = {}
    monkeypatch.setattr(bench_server, "_load_progress", lambda: saved.get("p", progress.empty_progress()))
    monkeypatch.setattr(bench_server, "_save_progress", lambda p: saved.__setitem__("p", p))
    monkeypatch.setattr(bench_server, "_reload_engine", lambda: None)
    monkeypatch.setattr(bench_server.core.eventlog, "LOGS_ROOT", tmp_path)
    listing = bench_server.api_lessons({})
    analog = next(l for l in listing["lessons"] if l["id"] == "analog-read-serial")
    assert analog["unlocked"] and not analog["prereqs_done"]      # a tip, not a lock
    started = bench_server.api_start({"lesson_id": "analog-read-serial", "difficulty": "beginner"})
    assert isinstance(started, dict) and "session" in started
    assert "worlds" in listing and listing["worlds"][0]["levels"][1]["level"] == "1-2"
