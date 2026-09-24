"""1000 generated scenarios combining EVERY moving part this session's
board-translation feature touches, end to end through the real engine
against the real lessons and their real code.ino files — user request,
after a smaller combined stress test (tests/test_board_translate.py's
own `test_combined_stress_scenario_...`) found and fixed a real bug in
`engine._final_pin_for_component`.

Same generated-parametrize style as tests/test_sim_and_board_200.py: each
of the 1000 seeds becomes its own individually-reported pytest case, not
one big loop, deriving (lesson, target board, behavior mode) from the
seed the same deterministic way.

Every real lesson (blink, analog-read-serial, digital-read-serial) has
exactly ONE substitutable Arduino pin — confirmed by reading each
lesson.json directly — so a single case's "weirdness" comes from
combining: which same-family board it's translated to (including a
same-board no-op), and what the learner does with that one pin:
wire it correctly, deviate to a different valid pin, deviate several
times in a row before finally confirming (only the last should count —
this exact pattern is what the fixed bug involved), or get it wrong
first (refused, must not advance) before finally getting it right.
Independently testing MULTIPLE simultaneously-deviating components (this
project's real lessons don't have more than one substitutable pin each)
is covered separately by the synthetic multi-component case already in
test_board_translate.py.

Every case's final assertion is the one the user asked for by name: is
the code correct at the end, no matter how many mistakes and swaps
happened along the way — checked with word-boundary-safe regex (a naive
substring check would false-positive, e.g. '13' inside 'RTC_DS1307' or
inside a translated pin like '213' — none of these lessons have that
exact collision, but the check is written safely regardless).
"""
import random
import re

import pytest

from core import board_translate, engine
from core.library import load_library
from core.lesson import load_lesson

LESSON_IDS = ["blink", "analog-read-serial", "digital-read-serial"]
TARGET_ALIASES = ["uno", "mega", "nano"]
MODES = ["correct", "deviate", "deviate_multi", "wrong_then_correct", "wrong_then_deviate"]

# Each real lesson's one substitutable connection, plus enough structural
# metadata (step ids, the other steps' pairs verbatim) to drive the whole
# session generically without re-deriving lesson-specific shape from
# scratch in the test body. Confirmed directly from each lessons/*/lesson.json.
LESSON_SHAPES = {
    "blink": {
        "landing_step": "step-1a", "landing_leg": "r1:1",
        "wiring_step": "step-1b", "wiring_component_leg": "r1:1", "wiring_kind": "digital",
        "other_steps": [
            ("step-2", [["led1:A", "r1:2"]]),
            ("step-3", [["led1:C", "uno:GND.1"]]),
        ],
        "final_check_extra": [["led1:A", "r1:2"], ["led1:C", "uno:GND.1"]],
        "code_var_pattern": None,  # bare pin literal, e.g. pinMode(13, ...)
    },
    "analog-read-serial": {
        # step-1a is now ONE combined multi-leg landing check for all
        # three of the potentiometer's legs at once (PARTS.md's
        # legs_placed_together) — not three separate landing steps.
        "landing_step": "step-1a", "landing_legs": ["pot1:GND", "pot1:VCC", "pot1:SIG"],
        "pre_wiring_step": "step-1b", "pre_wiring_pair": ["pot1:GND", "uno:GND.1"],
        "pre_wiring_step_2": "step-2b", "pre_wiring_pair_2": ["pot1:VCC", "uno:5V"],
        "wiring_step": "step-3b", "wiring_component_leg": "pot1:SIG", "wiring_kind": "analog",
        "final_check_extra": [["pot1:GND", "uno:GND.1"], ["pot1:VCC", "uno:5V"]],
        "code_var_pattern": "A",  # analogRead(A0)
    },
    "digital-read-serial": {
        # step-1a is now ONE combined multi-leg landing check for BOTH
        # of the pushbutton's contact groups at once (PARTS.md's
        # legs_placed_together) — not just its own scripted group 2 leg.
        "landing_step": "step-1a", "landing_legs": ["btn1:2.r", "btn1:1.r"],
        "pre_wiring_step": "step-1b", "pre_wiring_pair": ["btn1:2.r", "uno:5V"],
        "wiring_step": "step-2", "wiring_component_leg": "btn1:1.r", "wiring_kind": "digital",
        "other_steps": [
            ("step-3", [["r1:1", "btn1:1.r"]]),
            ("step-4", [["r1:2", "uno:GND.2"]]),
        ],
        "final_check_extra": [["btn1:2.r", "uno:5V"], ["r1:1", "btn1:1.r"], ["r1:2", "uno:GND.2"]],
        "code_var_pattern": None,
    },
}

# The literal pin each lesson's REAL, on-disk code.ino uses for its one
# substitutable connection — confirmed by reading each code.ino directly.
ORIGINAL_CODE_LEG = {"blink": "13", "analog-read-serial": "A0", "digital-read-serial": "2"}


def send(lesson, library, state, event):
    return engine.handle_event(lesson, library, state, event)


def _pick_alternate(target_card, kind, exclude, rng):
    pool = sorted(target_card["pin_domains"].get(kind, []), key=lambda p: int(p.lstrip("A") or 0))
    candidates = [p for p in pool if p not in exclude]
    assert candidates, f"no free {kind} pin left on {target_card['id']} excluding {exclude}"
    return rng.choice(candidates)


def _do_wiring_step(lesson, library, state, step_id, component_leg, scripted_leg, mode, target_card, kind, rng):
    """Drives one wiring step (the lesson's single substitutable
    connection) according to `mode`. Returns the leg actually left
    confirmed for this connection (may differ from `scripted_leg`)."""
    board_pin_prefix = "uno:"  # every translated lesson's board id stays "uno" — see test_board_translate.py

    if mode == "wrong_then_correct" or mode == "wrong_then_deviate":
        state[0], actions = send(lesson, library, state[0], {"command": "sim", "detected_pairs": [[component_leg, "nowhere:9999"]]})
        state[0], actions = send(lesson, library, state[0], {"command": "done"})
        feedback = next((a for a in actions if a["type"] == "feedback"), None)
        assert feedback is not None and feedback["verdict"] == "wrong", actions
        assert lesson.step(state[0]["step_index"])["id"] == step_id, "wrong attempt must not advance"

    if mode in ("correct", "wrong_then_correct"):
        final_leg = scripted_leg
        pair = [component_leg, f"{board_pin_prefix}{final_leg}"]
        state[0], _ = send(lesson, library, state[0], {"command": "sim", "detected_pairs": [pair]})
        state[0], actions = send(lesson, library, state[0], {"command": "done"})
        assert not [a for a in actions if a.get("verdict") == "wrong"], actions
        return final_leg

    # deviate / deviate_multi / wrong_then_deviate
    alt = _pick_alternate(target_card, kind, exclude={scripted_leg}, rng=rng)
    if mode == "deviate_multi":
        # Re-sim a few different (unconfirmed) candidates first — only the
        # LAST one before `done` should ever be reflected anywhere. This
        # is the exact shape the real bug involved.
        decoys = set()
        for _ in range(rng.randint(2, 4)):
            decoy = _pick_alternate(target_card, kind, exclude={scripted_leg, alt} | decoys, rng=rng)
            decoys.add(decoy)
            state[0], _ = send(lesson, library, state[0], {"command": "sim", "detected_pairs": [[component_leg, f"{board_pin_prefix}{decoy}"]]})
    pair = [component_leg, f"{board_pin_prefix}{alt}"]
    state[0], _ = send(lesson, library, state[0], {"command": "sim", "detected_pairs": [pair]})
    state[0], actions = send(lesson, library, state[0], {"command": "done"})

    # Revised (user request, core/engine.py's own _try_pin_substitution
    # docstring — see the research log (in git history)): digital and analog deviations
    # are now both unconditionally offered, matching real electronics —
    # any digital pin genuinely works as well as any other for a plain
    # digitalRead()/digitalWrite() connection. A harmless deviation is
    # accepted via substitution, same as it always was for analog.
    assert any(a["type"] == "pin_substituted" for a in actions), actions
    return alt


def _run_scenario(lesson_id, target_alias, mode, seed):
    rng = random.Random(seed)
    library = load_library()
    lesson = load_lesson(lesson_id)
    target_card = board_translate.resolve_target_board(target_alias, library)
    result = board_translate.translate_lesson(lesson, target_card, library)
    assert result.feasible, result.infeasible
    translated = result.lesson
    shape = LESSON_SHAPES[lesson_id]

    state = [engine.initial_state()]
    state[0], _ = send(translated, library, state[0], {"command": "start"})
    state[0], _ = send(translated, library, state[0], {"command": "done"})  # gather -> first build step

    if lesson_id == "blink":
        # landing (bypass) -> wiring (the one substitutable connection)
        state[0], _ = send(translated, library, state[0], {"command": "sim", "detected_pairs": [[shape["landing_leg"], "uno:GND.1"]]})
        # ^ intentionally NOT the real landing pair (a breadboard column) —
        # blink's landing is a plain "leg lands somewhere" check; reuse the
        # already-proven breadboard-routed pairs from tests/test_blink.py
        # instead, for fidelity with the real, established test pattern.
        pass

    # Use the exact, already-proven pair shapes from each lesson's own
    # dedicated test file (test_blink.py / test_full_session_variations.py)
    # for every step OTHER than the one substitutable connection, which is
    # driven by _do_wiring_step above according to `mode`.
    scripted_leg = None
    kind = shape.get("wiring_kind")

    if lesson_id == "blink":
        # step-1a landing, then step-1b wiring (substitutable pin 13).
        state[0], _ = send(translated, library, state[0], {"command": "sim", "detected_pairs": [["r1:1", "bb1:3b.h"]]})
        state[0], actions = send(translated, library, state[0], {"command": "done"})
        assert not [a for a in actions if a.get("verdict") == "wrong"]
        scripted_leg = translated.data["steps"][2]["expected_nets"][0][1].split(":", 1)[1]
        assert lesson.step(state[0]["step_index"])["id"] == "step-1b"
        # Both landing+wiring pairs re-sent together, same as the real
        # tested pattern — but the wiring itself (the substitutable pin)
        # is driven by _do_wiring_step, which sends its own pairs.
        final_leg = _do_wiring_step(translated, library, state, "step-1b", "r1:1", scripted_leg, mode, target_card, kind, rng)
        state[0], actions = send(translated, library, state[0], {"command": "sim", "detected_pairs": [["led1:A", "r1:2"]]})
        state[0], actions = send(translated, library, state[0], {"command": "done"})
        assert not [a for a in actions if a.get("verdict") == "wrong"]
        state[0], actions = send(translated, library, state[0], {"command": "sim", "detected_pairs": [["led1:C", "uno:GND.1"]]})
        state[0], actions = send(translated, library, state[0], {"command": "done"})
        assert not [a for a in actions if a.get("verdict") == "wrong"]
        final_check_pairs = [["r1:1", f"uno:{final_leg}"], ["led1:A", "r1:2"], ["led1:C", "uno:GND.1"]]

    elif lesson_id == "analog-read-serial":
        # step-1a is now ONE combined multi-leg landing check for all
        # three of the potentiometer's legs at once (PARTS.md's
        # legs_placed_together) — all three bypassed straight to their
        # real Arduino pins here (engine._multi_leg_bypass), same
        # electrically-fine-but-flagged deviation as the single-leg
        # bypass every other lesson already uses in this file.
        scripted_leg = translated.data["steps"][4]["expected_nets"][0][1].split(":", 1)[1]
        landing_pairs = [
            ["pot1:GND", "uno:GND.1"],
            ["pot1:VCC", "uno:5V"],
            ["pot1:SIG", f"uno:{scripted_leg}"],
        ]
        state[0], _ = send(translated, library, state[0], {"command": "sim", "detected_pairs": landing_pairs})
        state[0], actions = send(translated, library, state[0], {"command": "done"})  # -> step-1b
        assert not [a for a in actions if a.get("verdict") == "wrong"], actions

        for leg, target in (("GND", "GND.1"), ("VCC", "5V")):
            pair = [[f"pot1:{leg}", f"uno:{target}"]]
            state[0], _ = send(translated, library, state[0], {"command": "sim", "detected_pairs": pair})
            state[0], actions = send(translated, library, state[0], {"command": "done"})
            assert not [a for a in actions if a.get("verdict") == "wrong"], actions

        final_leg = _do_wiring_step(translated, library, state, "step-3b", "pot1:SIG", scripted_leg, mode, target_card, kind, rng)
        final_check_pairs = [["pot1:GND", "uno:GND.1"], ["pot1:VCC", "uno:5V"], ["pot1:SIG", f"uno:{final_leg}"]]

    else:  # digital-read-serial
        # step-1a is a combined multi-leg landing check for BOTH contact
        # groups at once now (PARTS.md's legs_placed_together) — both
        # bypassed straight to their own correct Arduino pins. Group 1's
        # target must be the TRANSLATED lesson's own scripted pin (the
        # one substitutable connection, may differ from the original
        # board's "2" once translated), not a hardcoded literal.
        scripted_leg = translated.data["steps"][3]["expected_nets"][0][1].split(":", 1)[1]
        state[0], _ = send(translated, library, state[0], {"command": "sim", "detected_pairs": [["btn1:2.r", "uno:5V"], ["btn1:1.r", f"uno:{scripted_leg}"]]})
        state[0], actions = send(translated, library, state[0], {"command": "done"})  # landing (bypass)
        assert not [a for a in actions if a.get("verdict") == "wrong"], actions
        state[0], _ = send(translated, library, state[0], {"command": "sim", "detected_pairs": [["btn1:2.r", "uno:5V"]]})
        state[0], actions = send(translated, library, state[0], {"command": "done"})  # step-1b wiring
        assert not [a for a in actions if a.get("verdict") == "wrong"], actions
        final_leg = _do_wiring_step(translated, library, state, "step-2", "btn1:1.r", scripted_leg, mode, target_card, kind, rng)
        state[0], actions = send(translated, library, state[0], {"command": "sim", "detected_pairs": [["r1:1", "btn1:1.r"]]})
        state[0], actions = send(translated, library, state[0], {"command": "done"})
        assert not [a for a in actions if a.get("verdict") == "wrong"], actions
        state[0], _ = send(translated, library, state[0], {"command": "sim", "detected_pairs": [["r1:2", "uno:GND.2"]]})
        state[0], actions = send(translated, library, state[0], {"command": "done"})
        assert not [a for a in actions if a.get("verdict") == "wrong"], actions
        final_check_pairs = [["btn1:2.r", "uno:5V"], ["btn1:1.r", f"uno:{final_leg}"], ["r1:1", "btn1:1.r"], ["r1:2", "uno:GND.2"]]

    assert state[0]["phase"] == "upload"
    state[0], actions = send(translated, library, state[0], {"command": "done"})  # -> final_check
    state[0], _ = send(translated, library, state[0], {"command": "sim", "detected_pairs": final_check_pairs})
    state[0], actions = send(translated, library, state[0], {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"], (lesson_id, target_alias, mode, seed, actions)
    assert state[0]["finished"], (lesson_id, target_alias, mode, seed)

    final_code = engine._adjusted_code(translated, state[0])
    original_leg = ORIGINAL_CODE_LEG[lesson_id]
    if final_leg != original_leg:
        assert re.search(rf"\b{re.escape(final_leg)}\b", final_code), (lesson_id, target_alias, mode, seed, "final leg missing", final_code)
        assert not re.search(rf"\b{re.escape(original_leg)}\b", final_code), (lesson_id, target_alias, mode, seed, "stale original leg leaked", final_code)
    else:
        assert re.search(rf"\b{re.escape(final_leg)}\b", final_code), (lesson_id, target_alias, mode, seed, final_code)


CASES = [
    (seed, LESSON_IDS[seed % 3], TARGET_ALIASES[(seed // 3) % 3], MODES[(seed // 9) % 5])
    for seed in range(1000)
]


@pytest.mark.parametrize("seed,lesson_id,target_alias,mode", CASES)
def test_1000_board_translation_stress_scenarios(seed, lesson_id, target_alias, mode):
    _run_scenario(lesson_id, target_alias, mode, seed)


def test_1000_cases_cover_every_lesson_target_mode_combination():
    """Sanity check on the test matrix itself, same style as the existing
    200-case suite's own coverage check."""
    seen = {(c[1], c[2], c[3]) for c in CASES}
    expected = {(l, t, m) for l in LESSON_IDS for t in TARGET_ALIASES for m in MODES}
    assert seen == expected, expected - seen
