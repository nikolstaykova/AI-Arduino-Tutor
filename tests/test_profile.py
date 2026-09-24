"""Tests for core/profile.py — the local learner profile (name,
difficulty) remembered between CLI sessions. Deliberately excludes the
breadboard variant — see the module's own docstring: which board is on
the desk is a per-session fact, not a learner trait, so `board` is always
asked fresh, never persisted or auto-applied. Always uses an explicit
`path` pointing into pytest's tmp_path, never the real project-root
profile.json, so tests never pollute (or race on) the learner's actual
saved profile.
"""
from core.profile import load_profile, save_profile


def test_load_profile_returns_empty_dict_when_no_file_exists(tmp_path):
    assert load_profile(tmp_path / "no_such_profile.json") == {}


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "profile.json"
    save_profile({"name": "Nikol", "difficulty": "advanced"}, path)
    assert load_profile(path) == {"name": "Nikol", "difficulty": "advanced"}


def test_save_overwrites_a_previous_profile(tmp_path):
    path = tmp_path / "profile.json"
    save_profile({"name": "Nikol", "difficulty": "beginner"}, path)
    save_profile({"name": "Nikol", "difficulty": "advanced"}, path)
    assert load_profile(path) == {"name": "Nikol", "difficulty": "advanced"}


def test_partial_profile_only_has_the_fields_that_were_saved(tmp_path):
    path = tmp_path / "profile.json"
    save_profile({"name": "Nikol"}, path)
    profile = load_profile(path)
    assert profile.get("difficulty") is None
