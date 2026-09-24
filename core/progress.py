"""Gamification — XP, levels, streaks, badges, unlocks (PLAN.md Phase 5).

Pure functions. A session's score is computed by REPLAYING its logged
events through the real engine (the same replay eventlog.replay does), so
XP can never reward anything the engine didn't actually confirm: a step
only earns XP once the engine advanced past it, and a lesson only earns
its completion bonus once final_check passed (physics included).

Kept out of core/engine.py on purpose, like core/profile.py: engine state
is one lesson session; progress is the learner across many sessions.
"""
from datetime import date, timedelta

from . import engine

XP_STEP = 10            # a build step passed
XP_FIRST_TRY = 5        # ...with no wrong attempt on it
XP_NO_HINT = 5          # ...with no hint used on it
XP_COMPLETE = 50        # final_check passed
XP_CLEAN_RUN = 25       # whole lesson: no wrong attempts and no hints

BADGES = {
    "first-circuit": "First circuit — completed your first lesson.",
    "no-hints": "Unassisted — completed a lesson without a single hint.",
    "perfectionist": "Perfectionist — every step right on the first try.",
    "pin-swapper": "Pin swapper — used a different pin than the script, correctly.",
    "inventor": "Inventor — completed an AI-generated lesson.",
    "explorer": "Explorer — completed three different lessons.",
    "streak-3": "On a roll — a three-day streak.",
}


def empty_progress():
    return {"xp": 0, "completed": {}, "streak": {"days": 0, "last": None}, "badges": []}


def level_for(xp):
    """Level n+1 starts at 50·n·(n+1) XP: 100, 300, 600, 1000, ...
    Returns (level, xp_into_level, xp_needed_for_next)."""
    n = 0
    while 50 * (n + 1) * (n + 2) <= xp:
        n += 1
    start, nxt = 50 * n * (n + 1), 50 * (n + 1) * (n + 2)
    return n + 1, xp - start, nxt - start


def score_session(lesson, library, events):
    """Replay `events` (a session's logged event dicts) through the engine
    and score them. Returns {"xp", "breakdown": [(reason, xp)], "finished",
    "steps": {step_id: {"attempts", "wrong", "hints", "passed"}},
    "hints", "wrong", "substitutions", "perfect"}."""
    state = engine.initial_state()
    steps = {}
    substitutions = 0
    for event in events:
        step_before = lesson.step(state["step_index"]) if state["step_index"] >= 0 else None
        phase_before = state["phase"]
        index_before = state["step_index"]
        state, actions = engine.handle_event(lesson, library, state, event)
        if phase_before != "build" or step_before is None:
            continue
        record = steps.setdefault(step_before["id"], {"attempts": 0, "wrong": 0, "hints": 0, "passed": False})
        command = event.get("command") if isinstance(event, dict) else None
        if command in ("hint", "reveal") and any(a["type"] in ("hint", "reveal") for a in actions):
            record["hints"] += 1
        elif command == "done":
            record["attempts"] += 1
            if any(a["type"] == "feedback" and a.get("verdict") == "wrong" for a in actions):
                record["wrong"] += 1
            elif state["step_index"] != index_before or state["phase"] != phase_before:
                record["passed"] = True
            substitutions += sum(1 for a in actions if a["type"] == "pin_substituted")

    breakdown = []
    for step_id, record in steps.items():
        if not record["passed"]:
            continue
        breakdown.append((f"{step_id} passed", XP_STEP))
        if record["wrong"] == 0:
            breakdown.append((f"{step_id} first try", XP_FIRST_TRY))
        if record["hints"] == 0:
            breakdown.append((f"{step_id} no hints", XP_NO_HINT))
    hints = sum(r["hints"] for r in steps.values())
    wrong = sum(r["wrong"] for r in steps.values())
    perfect = bool(steps) and state["finished"] and hints == 0 and wrong == 0
    if state["finished"]:
        breakdown.append(("lesson complete", XP_COMPLETE))
        if perfect:
            breakdown.append(("clean run: no hints, no mistakes", XP_CLEAN_RUN))
    return {
        "xp": sum(xp for _, xp in breakdown),
        "breakdown": breakdown,
        "finished": state["finished"],
        "steps": steps,
        "hints": hints,
        "wrong": wrong,
        "substitutions": substitutions,
        "perfect": perfect,
    }


def stars_for(score):
    """0-3 stars for a scored session: one for finishing, one for using no
    hints, one for never getting a step wrong."""
    if not score.get("finished"):
        return 0
    return 1 + (score.get("hints", 1) == 0) + (score.get("wrong", 1) == 0)


def apply_session(progress, lesson_id, score, today=None, generated=False):
    """Fold one scored session into the learner's progress. Replaying a
    lesson only earns the improvement over its best previous score, so XP
    can't be farmed by repeating the easiest lesson. Returns
    (new_progress, {"xp_gained", "new_badges", "level_up"})."""
    today = today or date.today()
    progress = {**empty_progress(), **progress}
    progress["completed"] = dict(progress["completed"])
    progress["badges"] = list(progress["badges"])
    progress["streak"] = dict(progress["streak"])
    level_before = level_for(progress["xp"])[0]

    best_before = progress["completed"].get(lesson_id, {}).get("best_xp", 0)
    xp_gained = max(0, score["xp"] - best_before)
    progress["xp"] += xp_gained
    new_badges = []

    if score["finished"]:
        progress["completed"][lesson_id] = {
            "best_xp": max(best_before, score["xp"]),
            "stars": max(stars_for(score), progress["completed"].get(lesson_id, {}).get("stars", 0)),
            "generated": generated or progress["completed"].get(lesson_id, {}).get("generated", False),
        }
        last = progress["streak"]["last"]
        if last != today.isoformat():
            yesterday = (today - timedelta(days=1)).isoformat()
            progress["streak"]["days"] = progress["streak"]["days"] + 1 if last == yesterday else 1
            progress["streak"]["last"] = today.isoformat()

        earned = {"first-circuit"}
        if score["hints"] == 0:
            earned.add("no-hints")
        if score["perfect"]:
            earned.add("perfectionist")
        if score["substitutions"]:
            earned.add("pin-swapper")
        if generated:
            earned.add("inventor")
        if len(progress["completed"]) >= 3:
            earned.add("explorer")
        if progress["streak"]["days"] >= 3:
            earned.add("streak-3")
        for badge in sorted(earned):
            if badge not in progress["badges"]:
                progress["badges"].append(badge)
                new_badges.append(badge)

    return progress, {
        "xp_gained": xp_gained,
        "new_badges": new_badges,
        "level_up": level_for(progress["xp"])[0] > level_before,
    }


def unlocked(lesson_data, progress):
    """True once every lesson in its `requires` list has been completed.
    This is a SUGGESTION, not a lock: any level can be played (and marked
    completed) in any order; the map just tips the learner off when a level
    builds on one they haven't done yet. Generated lessons have no
    `requires`."""
    done = set(progress.get("completed", {}))
    return all(req in done for req in lesson_data.get("requires", []))
