"""100 realistic hole-level detection scenarios against the real
analog-read-serial lesson, using core.mock_vision — the same module Phase
4's real vision pipeline will eventually stand in for. Unlike the `sim`
shortcut (which operates on already-reduced component-pin pairs), these
scenarios go through actual breadboard strips with a fresh random
strip/hole choice every time, exercising the full board_alias_map +
connector_ids + symmetric_map pipeline end to end — both a genuinely
correct build and a genuinely reversed/wrong one, per step.
"""
import random

import pytest

from core import checker, mock_vision
from core.engine import _symmetric_map
from core.library import load_library
from core.lesson import load_lesson

MODES = ["correct", "harmless", "wrong"]
# Only the wiring half of each pair has an expected_nets — the landing
# half is now step-1a's own combined multi-leg check (all three of the
# potentiometer's legs at once, see PARTS.md's legs_placed_together),
# which doesn't have a single expected_nets to mimic_detection against
# the same way, so it's out of scope for this generator.
BUILD_STEP_INDICES = [2, 3, 4]  # step-1b (GND), step-2b (VCC), step-3b (SIG)


@pytest.fixture(scope="module")
def library():
    return load_library()


@pytest.fixture(scope="module")
def lesson():
    return load_lesson("analog-read-serial")


@pytest.fixture(scope="module")
def sym_map(lesson, library):
    return _symmetric_map(lesson, library)


@pytest.fixture(scope="module")
def alias_map(lesson):
    return checker.board_alias_map(lesson.diagram()["parts"])


@pytest.fixture(scope="module")
def connector_component_ids(lesson):
    return checker.connector_ids(lesson.diagram()["parts"])


def _expected_verdict(step_idx, mode):
    """step-3b (SIG) has no symmetric_pins partner declared — mimic_detection
    falls back to realizing it identically to 'correct' when asked for
    'harmless', since there's nothing to swap. So the expected verdict for
    (step-3b, 'harmless') is 'pass', not 'harmless'. Otherwise the mode name
    maps straight across, modulo "correct" -> the checker's actual verdict
    string "pass" (the mode is what we asked mock_vision to realize; "pass"
    is what checker.check actually returns for it)."""
    if mode == "correct" or (step_idx == 4 and mode == "harmless"):
        return "pass"
    return mode


CASES = [(seed, BUILD_STEP_INDICES[seed % 3], MODES[(seed // 3) % 3]) for seed in range(100)]


@pytest.mark.parametrize("seed,step_idx,mode", CASES)
def test_realistic_breadboard_scenario(lesson, library, sym_map, alias_map, connector_component_ids, seed, step_idx, mode):
    step = lesson.step(step_idx)
    rng = random.Random(seed)
    detected = mock_vision.mimic_detection(step["expected_nets"], mode, sym_map, rng=rng)

    # sanity: this must actually be realistic hole-level data, not a
    # sneaky shortcut back to component-pin pairs.
    assert all(":" in p and "bb2:" in p for pair in detected for p in pair if p.startswith("bb2"))

    result = checker.check(step["expected_nets"], detected, sym_map, alias_map, connector_component_ids)
    assert result["verdict"] == _expected_verdict(step_idx, mode), (
        f"seed={seed} step={step['id']} mode={mode} detected={detected} result={result}"
    )


def test_mock_vision_never_generates_a_letter_from_the_wrong_side_of_the_gap():
    """Real breadboards split each row at the center gap into two
    disconnected halves — confirmed from real Wokwi data: the 't' side
    only uses a-e, the 'b' side only f-j. mock_vision must only ever
    produce hole names a real board could actually have."""
    rng = random.Random(123)
    detected = mock_vision.mimic_detection([["a:1", "b:2"]] * 50, "correct", rng=rng)
    for pair in detected:
        for pin in pair:
            if ":" not in pin or "." not in pin:
                continue
            _, leg = pin.split(":", 1)
            strip, letter = leg.split(".", 1)
            if strip.endswith("t"):
                assert letter in "abcde", f"'t' side must never produce letter {letter!r}"
            elif strip.endswith("b"):
                assert letter in "fghij", f"'b' side must never produce letter {letter!r}"


def test_100_cases_cover_every_step_and_mode_combination():
    """Sanity check on the test matrix itself: with 100 cases cycling
    through 3 steps x 3 modes, every combination must actually be hit
    multiple times, not just nominally present."""
    from collections import Counter
    counts = Counter((step_idx, mode) for _, step_idx, mode in CASES)
    assert len(counts) == 9
    assert min(counts.values()) >= 10
