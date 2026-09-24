"""core/progress.py — XP comes only from what the real engine confirmed."""
from datetime import date

import pytest

from core import progress
from core.lesson import load_lesson
from core.library import load_library

LIBRARY = load_library()


def _blink_events(extra_before_step=None):
    """A Blink session driven by real events. `extra_before_step` maps a
    step id to events inserted just before that step's passing `done`."""
    lesson = load_lesson("blink")
    events = [{"command": "start"}, {"command": "done"}]   # gather
    for step in lesson.steps:
        if step["phase"] != "build":
            continue
        events += (extra_before_step or {}).get(step["id"], [])
        events.append({"command": "done", "label": "correct"})
    events.append({"command": "done"})                       # upload
    events.append({"command": "done", "label": "correct"})   # final_check
    return lesson, events


def test_level_thresholds():
    assert progress.level_for(0) == (1, 0, 100)
    assert progress.level_for(99) == (1, 99, 100)
    assert progress.level_for(100) == (2, 0, 200)
    assert progress.level_for(300) == (3, 0, 300)
    assert progress.level_for(650) == (4, 50, 400)


def test_clean_blink_run_earns_every_bonus():
    lesson, events = _blink_events()
    score = progress.score_session(lesson, LIBRARY, events)
    build_steps = [s for s in lesson.steps if s["phase"] == "build"]
    per_step = progress.XP_STEP + progress.XP_FIRST_TRY + progress.XP_NO_HINT
    assert score["finished"] and score["perfect"]
    assert score["xp"] == len(build_steps) * per_step + progress.XP_COMPLETE + progress.XP_CLEAN_RUN


def test_hints_and_wrong_attempts_cost_their_bonuses_only():
    lesson, events = _blink_events({
        "step-1b": [{"command": "hint"}],
        "step-3": [{"command": "done", "label": "wrong"}],
    })
    score = progress.score_session(lesson, LIBRARY, events)
    assert score["finished"] and not score["perfect"]
    assert score["steps"]["step-1b"] == {"attempts": 1, "wrong": 0, "hints": 1, "passed": True}
    assert score["steps"]["step-3"]["wrong"] == 1
    reasons = dict(score["breakdown"])
    assert "step-1b no hints" not in reasons and "step-1b first try" in reasons
    assert "step-3 first try" not in reasons and "step-3 no hints" in reasons
    assert "clean run: no hints, no mistakes" not in reasons


def test_unfinished_session_gets_no_completion_bonus():
    lesson, events = _blink_events()
    score = progress.score_session(lesson, LIBRARY, events[:-3])
    assert not score["finished"]
    assert "lesson complete" not in dict(score["breakdown"])


def test_a_step_that_never_passed_earns_nothing():
    lesson = load_lesson("blink")
    events = [{"command": "start"}, {"command": "done"}, {"command": "done", "label": "wrong"}]
    score = progress.score_session(lesson, LIBRARY, events)
    assert score["xp"] == 0


def test_apply_session_awards_badges_streak_and_only_improvement_on_replay():
    lesson, events = _blink_events()
    score = progress.score_session(lesson, LIBRARY, events)
    day = date(2026, 9, 23)
    state, award = progress.apply_session(progress.empty_progress(), "blink", score, today=day)
    assert award["xp_gained"] == score["xp"]
    assert set(award["new_badges"]) == {"first-circuit", "no-hints", "perfectionist"}
    assert state["streak"] == {"days": 1, "last": "2026-09-23"}

    # Same lesson again, same score: no XP farming, no duplicate badges.
    state, award = progress.apply_session(state, "blink", score, today=day)
    assert award["xp_gained"] == 0 and award["new_badges"] == []

    # Next day keeps the streak going; a gap resets it.
    state, _ = progress.apply_session(state, "blink", score, today=date(2026, 9, 24))
    assert state["streak"]["days"] == 2
    state, _ = progress.apply_session(state, "blink", score, today=date(2026, 9, 27))
    assert state["streak"]["days"] == 1


def test_generated_lesson_and_substitution_badges():
    score = {"xp": 10, "finished": True, "hints": 1, "wrong": 0, "substitutions": 1, "perfect": False}
    state, award = progress.apply_session(progress.empty_progress(), "gen-traffic-light", score, generated=True)
    assert {"inventor", "pin-swapper"} <= set(award["new_badges"])
    assert state["completed"]["gen-traffic-light"]["generated"] is True


def test_explorer_badge_after_three_lessons():
    score = {"xp": 10, "finished": True, "hints": 1, "wrong": 1, "substitutions": 0, "perfect": False}
    state = progress.empty_progress()
    for lesson_id in ("a", "b", "c"):
        state, award = progress.apply_session(state, lesson_id, score)
    assert "explorer" in award["new_badges"]


@pytest.mark.parametrize("lesson_id, locked_until_blink", [
    ("blink", False), ("digital-read-serial", True), ("analog-read-serial", True),
])
def test_unlocks_follow_requires(lesson_id, locked_until_blink):
    data = load_lesson(lesson_id).data
    assert progress.unlocked(data, progress.empty_progress()) is (not locked_until_blink)
    assert progress.unlocked(data, {"completed": {"blink": {"best_xp": 1}}})
