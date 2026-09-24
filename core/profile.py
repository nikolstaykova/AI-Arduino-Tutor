"""Local learner profile — remembers a couple of settings between CLI
sessions: name and difficulty. Deliberately just a local JSON file: this
is a single-learner prototype, not a hosted multi-user app, so there's no
login/password — see PLAN.md for the "real accounts" scope that would
need if this ever becomes a shared/hosted service instead.

Deliberately does NOT include breadboard_variant, even though `board` is
asked the same "asked, not assumed" way `difficulty` is: which board is
on the desk is a fact about *this session*, not the learner — they could
easily use a different one next time — so persisting and auto-applying it
would quietly reintroduce exactly the assumption `board` exists to avoid.
Difficulty is genuinely a property of the learner (their experience level
doesn't reset every lesson), which is why it, unlike the board, belongs
here.

Kept separate from core/engine.py on purpose: engine.py's own state must
stay a plain, replayable session record with no I/O inside it (see its
module docstring). A learner's identity across *different* sessions is a
different concern from one lesson session's own state.
"""
import json
import os
from pathlib import Path

# CQ_PROFILE points a server at another profile file — test servers use one,
# so a test run can never touch the learner's real progress.
DEFAULT_PROFILE_PATH = Path(os.environ.get("CQ_PROFILE") or Path(__file__).resolve().parent.parent / "profile.json")


def load_profile(path=None):
    """Returns {} if no profile has been saved yet — every field is
    optional, callers should fall back to asking (same "asked, not
    assumed" precedent as `board`/`difficulty` themselves)."""
    path = path or DEFAULT_PROFILE_PATH
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def save_profile(profile, path=None):
    path = path or DEFAULT_PROFILE_PATH
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)
        f.write("\n")
