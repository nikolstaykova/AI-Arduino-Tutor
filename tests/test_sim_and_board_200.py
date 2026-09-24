"""200 scenarios exercising the `sim` raw-hole-pairs feature together with
the `board <variant>` command, end to end through the real engine — not the
checker directly. Every case: pick a breadboard variant (or none), fast-
forward to one of the four build sub-steps (one combined multi-leg landing
check for all three of the potentiometer's legs at once — see PARTS.md's
`legs_placed_together` — plus three wiring/net checks), then feed `sim`
literal hole-level pairs (not a canned label) and confirm both:

  1. the *actual* checker — not a picked label — produces the right
     pass/harmless/wrong verdict from that raw data, and
  2. the plausibility_warning fires exactly when it should: only once a
     board variant has been stated, and only when a detected column number
     couldn't plausibly fit it (PLAN.md Phase 5 / COMMANDS.md `board`).
"""
import random

import pytest

from core import engine
from core.engine import BREADBOARD_VARIANTS, _symmetric_map
from core.library import load_library
from core.lesson import load_lesson


@pytest.fixture(scope="module")
def library():
    return load_library()


@pytest.fixture(scope="module")
def lesson():
    return load_lesson("analog-read-serial")


@pytest.fixture(scope="module")
def sym_map(lesson, library):
    return _symmetric_map(lesson, library)


def send(lesson, library, state, event):
    return engine.handle_event(lesson, library, state, event)


def _swap_if_symmetric(pin, sym_map):
    """Returns (possibly-swapped pin, whether a swap was possible)."""
    comp, leg = pin.split(":", 1)
    for a, b in sym_map.get(comp, []):
        if leg == a:
            return f"{comp}:{b}", True
        if leg == b:
            return f"{comp}:{a}", True
    return pin, False


def _in_range_column(variant, rng):
    if variant is None:
        return rng.randint(1, 20)
    return rng.randint(1, BREADBOARD_VARIANTS[variant]["max_column_estimate"])


def _out_of_range_column(variant, rng):
    if variant is None:
        return rng.randint(50, 200)
    return BREADBOARD_VARIANTS[variant]["max_column_estimate"] + rng.randint(1, 50)


def _advance_to(lesson, library, state, target_index):
    """Fast-forward from wherever `state` is (already started, in gather or
    an earlier build step) up to `target_index` using the well-tested
    'sim correct' + 'done' path — proven elsewhere to pass at every step
    kind, landing or wiring."""
    while state["step_index"] < target_index:
        if state["phase"] == "gather":
            state, _ = send(lesson, library, state, {"command": "done"})
        else:
            state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
            state, _ = send(lesson, library, state, {"command": "done"})
    return state


def _build_pairs_and_expected(lesson, sym_map, step_idx, mode, variant, rng):
    """Returns (pairs, expected_verdict, col_used_or_None)."""
    step = lesson.step(step_idx)
    is_landing = "expected_landing" in step

    if mode == "wrong_empty":
        return [], "wrong", None

    col = _in_range_column(variant, rng) if mode != "correct_out_of_range" else _out_of_range_column(variant, rng)
    strip = f"{col}t"

    if is_landing and isinstance(step["expected_landing"], list):
        # The combined multi-leg landing check (all three of the
        # potentiometer's legs placed at once — PARTS.md's
        # legs_placed_together): each real leg genuinely present, each in
        # its OWN distinct column. "harmless_swap" isn't meaningful here
        # the way it is for a single-pin landing check — with all three
        # real leg identities checked directly and simultaneously, there's
        # no single named slot left ambiguous for a symmetric alternate to
        # stand in for — so it's just treated as another "pass" case,
        # still exercising this exact parameter combination.
        pins = step["expected_landing"]
        pick = _in_range_column if mode != "correct_out_of_range" else _out_of_range_column
        cols = [col]
        for _ in pins[1:]:
            c = pick(variant, rng)
            while c in cols:  # each leg needs its OWN column -- no accidental self-short
                c = pick(variant, rng)
            cols.append(c)
        pairs = [[pin, f"bb2:{c}t.a"] for pin, c in zip(pins, cols)]
        return pairs, "pass", col

    if is_landing:
        pin = step["expected_landing"]
        if mode == "harmless_swap":
            used_pin, swapped = _swap_if_symmetric(pin, sym_map)
            verdict = "harmless" if swapped else "pass"
        else:
            used_pin, verdict = pin, "pass"
        pairs = [[used_pin, f"bb2:{strip}.a"]]
        return pairs, verdict, col

    pin_a, pin_b = step["expected_nets"][0]
    if mode == "harmless_swap":
        used_a, swapped = _swap_if_symmetric(pin_a, sym_map)
        verdict = "harmless" if swapped else "pass"
        # A swap is only free until an earlier step fixes the part's
        # orientation. From step-2b on, the fast-forwarded step-1b has
        # already put pot1:GND on GND, so wiring that same leg to 5V shorts
        # 5V to GND through it — wrong (engine orientation lock).
        if swapped and step_idx > 2:
            verdict = "wrong"
    else:
        used_a, verdict = pin_a, "pass"
    pairs = [[used_a, f"bb2:{strip}.a"], [pin_b, f"bb2:{strip}.c"]]
    return pairs, verdict, col


STEP_INDICES = [1, 2, 3, 4]  # step-1a (multi-leg landing), step-1b, step-2b, step-3b
MODES = ["correct_in_range", "correct_out_of_range", "wrong_empty", "harmless_swap"]
VARIANTS = ["full", "half", "mini", None]

CASES = [
    (seed, STEP_INDICES[seed % 4], MODES[(seed // 4) % 4], VARIANTS[(seed // 16) % 4])
    for seed in range(200)
]


@pytest.mark.parametrize("seed,step_idx,mode,variant", CASES)
def test_sim_raw_pairs_with_a_chosen_board(lesson, library, sym_map, seed, step_idx, mode, variant):
    rng = random.Random(seed)
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    if variant is not None:
        state, board_actions = send(lesson, library, state, {"command": "board", "variant": variant})
        assert board_actions[0] == {"type": "board_set", "variant": variant}
    state = _advance_to(lesson, library, state, step_idx)
    assert state["step_index"] == step_idx

    pairs, expected_verdict, col = _build_pairs_and_expected(lesson, sym_map, step_idx, mode, variant, rng)

    state, sim_actions = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    if pairs:
        assert sim_actions[0] == {"type": "sim_set", "pairs": pairs}
    state, actions = send(lesson, library, state, {"command": "done"})

    feedback = next((a for a in actions if a["type"] == "feedback"), None)
    warnings = [a for a in actions if a["type"] == "plausibility_warning"]

    if expected_verdict == "wrong":
        assert feedback is not None and feedback["verdict"] == "wrong", (seed, step_idx, mode, variant, actions)
        assert state["step_index"] == step_idx  # did not advance
    elif expected_verdict == "harmless":
        assert feedback is not None and feedback["verdict"] == "harmless", (seed, step_idx, mode, variant, actions)
        assert state["step_index"] == step_idx + 1  # flagged but still advanced
    else:  # pass
        assert feedback is None, (seed, step_idx, mode, variant, actions)
        assert state["step_index"] == step_idx + 1  # advanced silently

    should_warn = variant is not None and mode == "correct_out_of_range"
    if should_warn:
        assert warnings, f"expected a plausibility warning: seed={seed} step={step_idx} variant={variant} col={col}"
        assert str(col) in warnings[0]["message"]
        assert variant in warnings[0]["message"]
    else:
        assert not warnings, (seed, step_idx, mode, variant, col, warnings)


def test_200_cases_cover_every_step_mode_variant_combination():
    """Sanity check on the test matrix itself, same style as the 100-case
    realistic-detection suite: 200 cases cycling through 4 steps x 4 modes
    x 4 variants (64 combinations) must hit every one at least once."""
    from collections import Counter

    counts = Counter((step_idx, mode, variant) for _, step_idx, mode, variant in CASES)
    assert len(counts) == 64
    assert min(counts.values()) >= 2
