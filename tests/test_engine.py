import tempfile
from pathlib import Path

import pytest

from core import checker, engine
from core.eventlog import EventLog, replay
from core.library import load_library
from core.lesson import Lesson, load_lesson


@pytest.fixture
def library():
    return load_library()


@pytest.fixture
def lesson():
    return load_lesson("analog-read-serial")


def send(lesson, library, state, event):
    return engine.handle_event(lesson, library, state, event)


def test_must_start_before_anything_else(lesson, library):
    state = engine.initial_state()
    state, actions = send(lesson, library, state, {"command": "done"})
    assert actions[0]["type"] == "error"
    assert state["started"] is False


def test_start_enters_gather_and_plays_intro(lesson, library):
    state = engine.initial_state()
    state, actions = send(lesson, library, state, {"command": "start"})
    assert state["phase"] == "gather"
    assert actions[0]["type"] == "play_clip"
    assert actions[0]["step"] == "gather"


def test_gather_done_advances_to_first_build_step_with_no_check(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["phase"] == "build"
    assert state["step_index"] == 1
    assert actions[0]["type"] == "play_clip"


def test_build_step_wrong_blocks_advance_and_lists_missing(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # into step-1
    state, _ = send(lesson, library, state, {"command": "sim", "label": "wrong"})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["step_index"] == 1  # did not advance
    assert actions[-1]["type"] == "feedback"
    assert actions[-1]["verdict"] == "wrong"
    assert actions[-1]["missing"]


def test_build_step_correct_advances(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a (landing)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["step_index"] == 2  # advanced to step-1b (wiring)
    assert actions[-1]["type"] == "play_clip"


def test_build_step_swapped_is_harmless_and_still_advances(lesson, library):
    """"swapped" is exercised at step-1b (a plain wiring/net check), not
    the combined multi-leg landing step-1a: with all three of the
    potentiometer's real leg identities checked directly and
    simultaneously there, a single-slot symmetric swap isn't a meaningful
    scenario any more (see _check_multi_leg_landing's own docstring) — the
    swap still resolves harmlessly, just one step later, same as always."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1b
    state, _ = send(lesson, library, state, {"command": "sim", "label": "swapped"})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["step_index"] == 3  # advanced despite the flag
    kinds = [a["type"] for a in actions]
    assert "feedback" in kinds
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "harmless"
    assert "play_clip" in kinds  # still moved on to the next step


def _finish_all_build_steps(lesson, library, state):
    for _ in range(4):  # step-1a (combined landing), step-1b, step-2b, step-3b
        state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
        state, _ = send(lesson, library, state, {"command": "done"})
    return state


def test_upload_phase_has_no_check_and_advances_on_done(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # into step-1
    state = _finish_all_build_steps(lesson, library, state)
    assert state["phase"] == "upload"
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["phase"] == "final_check"
    assert state["finished"] is False


def test_final_check_wrong_then_correct_completes(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    state = _finish_all_build_steps(lesson, library, state)
    state, _ = send(lesson, library, state, {"command": "done"})  # into final_check
    assert state["phase"] == "final_check"

    state, _ = send(lesson, library, state, {"command": "sim", "label": "wrong"})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["finished"] is False
    assert actions[-1]["verdict"] == "wrong"

    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["finished"] is True
    assert actions[-1]["type"] == "complete"


def test_repeat_replays_last_shown_even_at_final_check(lesson, library):
    """Regression test for the bug caught manually: repeat used to look up
    step['clip'] by re-fetching the current step, which is None at
    final_check since it isn't a real step — it must use the stored text."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    state = _finish_all_build_steps(lesson, library, state)
    state, _ = send(lesson, library, state, {"command": "done"})  # into final_check
    state, actions = send(lesson, library, state, {"command": "repeat"})
    assert actions[0]["type"] == "play_clip"
    assert "circuit" in actions[0]["text"].lower()


def test_help_is_text_only_never_plays_a_video(lesson, library):
    """`help` and `video` are separate requests (user request — a learner
    should be able to ask for just the explanation, or just the video,
    not always get both bundled)."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "help", "item": "wire-stripper"})
    assert actions[0]["type"] == "show_card"
    assert not any(a["type"] == "play_video" for a in actions)


def test_video_command_plays_the_tutorial_clip(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "video", "item": "wire-stripper"})
    assert actions[0]["type"] == "play_video"
    assert actions[0]["ref"] == "wire_stripper.mp4"


def test_video_command_says_so_when_the_item_has_none(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "video", "item": "potentiometer"})
    assert actions[0]["type"] == "error"
    assert "no video" in actions[0]["message"].lower()


def test_video_command_with_an_unknown_item_errors_cleanly(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "video", "item": "nonexistent-item"})
    assert actions[0]["type"] == "error"
    assert "unknown item" in actions[0]["message"].lower()


def test_repeat_replays_video_if_that_was_last_shown(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "video", "item": "wire-stripper"})
    assert any(a["type"] == "play_video" for a in actions)
    state, actions = send(lesson, library, state, {"command": "repeat"})
    assert actions[0]["type"] == "play_video"
    assert actions[0]["ref"] == "wire_stripper.mp4"


def test_help_after_video_does_not_hijack_repeat(lesson, library):
    """A text-only `help` after a video was shown must not overwrite
    `last_shown` — `repeat` should still replay the video."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "video", "item": "wire-stripper"})
    state, _ = send(lesson, library, state, {"command": "help", "item": "wire-stripper"})
    state, actions = send(lesson, library, state, {"command": "repeat"})
    assert actions[0]["type"] == "play_video"


def test_previous_goes_back_a_step(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1b
    state, actions = send(lesson, library, state, {"command": "previous"})
    assert state["step_index"] == 1
    assert actions[0]["step"] == "step-1a"


def test_previous_errors_at_first_step(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "previous"})
    assert actions[0]["type"] == "error"


def test_hint_reveals_one_level_at_a_time(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1
    state, actions = send(lesson, library, state, {"command": "hint"})
    assert state["hints_used"] == 1
    first_hint = actions[0]["text"]
    state, actions = send(lesson, library, state, {"command": "hint"})
    assert state["hints_used"] == 2
    assert actions[0]["text"] != first_hint


def test_exhausted_hint_on_a_landing_step_names_a_concrete_column(lesson, library):
    """User feedback from a real run: step-1a's own hints say "any hole in
    the column works" — true, but not actionable for someone still stuck
    once both hints are used up. The final, out-of-hints fallback should
    name a real column per leg rather than just refuse — taken from the
    lesson's own reference diagram.json (pot1:GND really does land on
    bb2:6b there), never fabricated. Now a combined multi-leg landing step
    (PARTS.md's legs_placed_together) — all three legs get their own
    reference column named, not just GND."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a
    state, _ = send(lesson, library, state, {"command": "hint"})
    state, _ = send(lesson, library, state, {"command": "hint"})
    assert state["hints_used"] == 2
    state, actions = send(lesson, library, state, {"command": "hint"})
    assert state["hints_used"] == 2  # this one didn't consume a scripted hint
    text = actions[0]["text"]
    assert "column 6" in text and "column 7" in text
    assert "GND" in text and "VCC" in text and "SIG" in text
    assert text != "No more hints for this step."


def test_exhausted_hint_on_a_wiring_step_names_the_concrete_far_pin(lesson, library):
    """Same concrete-fallback idea, extended to a wiring step (not just a
    landing step) per direct user follow-up ("also here u should say hole
    to hole"): step-1b's own hint says "any GND pin works" -- true, but
    once hints are exhausted the fallback should restate the step's own
    action concretely ("connect that same wire to ...") with the real far
    pin filled in, taken from the lesson's own reference diagram.json."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1a
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [
        ["pot1:GND", "bb2:6b.f"], ["pot1:VCC", "bb2:7b.f"], ["pot1:SIG", "bb2:8t.a"],
    ]})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b
    scripted = len(lesson.step(state["step_index"])["hints"])
    for _ in range(scripted):
        state, _ = send(lesson, library, state, {"command": "hint"})
    assert state["hints_used"] == scripted
    state, actions = send(lesson, library, state, {"command": "hint"})
    assert state["hints_used"] == scripted  # exhausted, didn't consume another scripted hint
    text = actions[0]["text"]
    assert "GND.1" in text
    assert text != "No more hints for this step."


def test_exhausted_hint_on_a_component_to_component_step_says_place_not_wire(library):
    """Blink's step-2 (LED sharing the resistor's own column) has no
    separate wire at all — its own clip says so explicitly. The concrete
    fallback must reflect that: "place it in column X," never "connect
    that wire," since there isn't one."""
    from core.lesson import load_lesson

    blink = load_lesson("blink")
    state = engine.initial_state()
    state, _ = send(blink, library, state, {"command": "start"})
    state, _ = send(blink, library, state, {"command": "done"})  # -> step-1a
    state, _ = send(blink, library, state, {"command": "sim", "detected_pairs": [["r1:1", "bb1:3b.h"]]})
    state, _ = send(blink, library, state, {"command": "done"})  # -> step-1b
    state, _ = send(blink, library, state, {"command": "sim", "detected_pairs": [["r1:1", "bb1:3b.h"], ["uno:13", "bb1:3b.g"]]})
    state, _ = send(blink, library, state, {"command": "done"})  # -> step-2

    for _ in range(2):
        state, _ = send(blink, library, state, {"command": "hint"})
    state, actions = send(blink, library, state, {"command": "hint"})
    text = actions[0]["text"]
    assert "column 6" in text
    assert "r1:2" in text
    assert "wire" not in text.lower()


def test_help_works_for_both_tools_and_parts(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "help", "item": "potentiometer"})
    assert actions[0]["card"]["id"] == "potentiometer-10k"
    state, actions = send(lesson, library, state, {"command": "help", "item": "stripper"})
    assert actions[0]["card"]["id"] == "wire-stripper"


def test_help_without_a_video_does_not_hijack_repeat(lesson, library):
    """Regression test: `help potentiometer` (a part, no tutorial_clip) used
    to overwrite last_shown with its text description, permanently stealing
    `repeat` away from the current step until a step change. A one-off text
    lookup shouldn't do that — only a played video should."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "help", "item": "potentiometer"})
    state, actions = send(lesson, library, state, {"command": "repeat"})
    assert actions[0]["type"] == "play_clip"
    assert actions[0]["step"] == "gather"


def test_board_command_asks_not_assumes(lesson, library):
    """The learner's actual breadboard is never assumed — asked. Before
    answering, breadboard_variant stays None; a bad answer is rejected
    without crashing; a good answer is recorded."""
    state = engine.initial_state()
    assert state["breadboard_variant"] is None
    state, _ = send(lesson, library, state, {"command": "start"})

    state, actions = send(lesson, library, state, {"command": "board", "variant": "extra-large"})
    assert actions[0]["type"] == "error"
    assert state["breadboard_variant"] is None

    state, actions = send(lesson, library, state, {"command": "board", "variant": "mini"})
    assert actions[0] == {"type": "board_set", "variant": "mini"}
    assert state["breadboard_variant"] == "mini"


def test_plausibility_warning_fires_when_detected_column_exceeds_stated_board(lesson, library):
    """Once the learner has said which board they have, a detected column
    number that couldn't fit on it is worth surfacing — as a separate
    warning, not folded into the pass/harmless/wrong verdict itself, since
    the exact column-count estimates aren't a confirmed spec (PARTS.md)."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "board", "variant": "mini"})
    state, _ = send(lesson, library, state, {"command": "done"})  # into step-1

    # column 40 doesn't fit a "mini" board (~17 columns estimated)
    detected = [
        ["pot1:GND", "bb2:40t.a"], ["uno:GND.3", "bb2:40t.c"],
        ["pot1:VCC", "bb2:2t.a"], ["pot1:SIG", "bb2:3t.a"],
    ]
    state, actions = send(lesson, library, state, {"command": "done", "detected_pairs": detected})
    warnings = [a for a in actions if a["type"] == "plausibility_warning"]
    assert warnings, "expected a plausibility warning for an out-of-range column"
    assert "40" in warnings[0]["message"] and "mini" in warnings[0]["message"]
    # the connection is otherwise correct, so the warning doesn't block a pass —
    # it just rides alongside it (advances to step-2's instructions)
    assert any(a["type"] == "play_clip" for a in actions)


def test_no_plausibility_warning_without_a_stated_board(lesson, library):
    """No board answered yet -> nothing to compare against -> no warning,
    even for a wildly large column number."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    detected = [["pot1:GND", "bb2:999t.a"], ["uno:GND.3", "bb2:999t.c"]]
    state, actions = send(lesson, library, state, {"command": "done", "detected_pairs": detected})
    assert not [a for a in actions if a["type"] == "plausibility_warning"]


def _advance_to_step(lesson, library, state, target_index):
    while state["step_index"] < target_index:
        if state["phase"] == "gather":
            state, _ = send(lesson, library, state, {"command": "done"})
        else:
            state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
            state, _ = send(lesson, library, state, {"command": "done"})
    return state


def test_wiring_to_a_different_analog_pin_is_tracked_as_a_substitution_not_wrong(lesson, library):
    """User request: wiring SIG to a different analog pin (A1) than the
    lesson's A0 works fine in hardware, so it should pass, but tracked —
    the code shown later must be updated to match, not silently identical."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state = _advance_to_step(lesson, library, state, 3)  # step-2b (VCC's wiring)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-3b

    pairs = [["pot1:SIG", "bb2:8t.a"], ["uno:A1", "bb2:8t.c"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    sub = next((a for a in actions if a["type"] == "pin_substituted"), None)
    assert sub is not None
    assert "uno:A0" in sub["message"] and "uno:A1" in sub["message"]
    assert not [a for a in actions if a["type"] == "feedback"]  # a clean pass
    assert state["step_index"] == 5  # advanced into upload
    assert state["pin_substitutions"] == [{"original": "uno:A0", "actual": "uno:A1", "step": "step-3b"}]


def test_upload_code_reflects_the_analog_pin_substitution(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state = _advance_to_step(lesson, library, state, 3)  # step-2b (VCC's wiring)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-3b
    pairs = [["pot1:SIG", "bb2:8t.a"], ["uno:A1", "bb2:8t.c"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    show_code = next(a for a in actions if a["type"] == "show_code")
    assert "analogRead(A1)" in show_code["code"]
    assert "analogRead(A0)" not in show_code["code"]


def test_upload_code_unchanged_without_any_substitution(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state = _advance_to_step(lesson, library, state, 4)  # up to step-3b, all correct
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, actions = send(lesson, library, state, {"command": "done"})  # -> upload
    show_code = next(a for a in actions if a["type"] == "show_code")
    assert "analogRead(A0)" in show_code["code"]


def test_upload_hint_explains_substitution_when_one_happened(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state = _advance_to_step(lesson, library, state, 3)  # step-2b (VCC's wiring)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-3b
    pairs = [["pot1:SIG", "bb2:8t.a"], ["uno:A1", "bb2:8t.c"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, _ = send(lesson, library, state, {"command": "done"})

    state, actions = send(lesson, library, state, {"command": "hint"})
    assert actions[0]["type"] == "hint"
    assert "A1" in actions[0]["text"] and "A0" in actions[0]["text"]


def test_upload_hint_still_unavailable_without_a_substitution(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state = _advance_to_step(lesson, library, state, 4)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> upload
    assert state["phase"] == "upload"
    state, actions = send(lesson, library, state, {"command": "hint"})
    assert actions[0]["type"] == "error"


def test_final_check_also_accepts_the_same_analog_pin_substitution(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state = _advance_to_step(lesson, library, state, 3)  # step-2b (VCC's wiring)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-3b
    pairs = [["pot1:SIG", "bb2:8t.a"], ["uno:A1", "bb2:8t.c"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> upload
    state, _ = send(lesson, library, state, {"command": "done"})  # -> final_check
    assert state["phase"] == "final_check"

    final_pairs = [
        ["pot1:GND", "bb2:6t.a"], ["uno:GND.1", "bb2:6t.c"],
        ["pot1:VCC", "bb2:7t.a"], ["uno:5V", "bb2:7t.c"],
        ["pot1:SIG", "bb2:8t.a"], ["uno:A1", "bb2:8t.c"],
    ]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": final_pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    # No repeated `pin_substituted` reminder here anymore: final_check now
    # pre-applies every already-accepted substitution (_apply_pin_
    # substitutions) before comparing, so an already-substituted pin
    # matches directly — checker.check returns "pass" outright, without
    # needing _try_pin_substitution's fallback (which is what used to
    # produce the reminder message) to run at all. Added so final_check
    # can also handle TWO OR MORE simultaneously-substituted components
    # at once, which a single fresh substitution search never could (see
    # the research log (in git history)) — the functional guarantee that matters is still
    # `complete`/`finished`, both still asserted below.
    assert any(a["type"] == "complete" for a in actions)
    assert state["finished"] is True


def test_repeat_at_upload_also_reshows_the_code_reflecting_a_substitution(lesson, library):
    """Regression test for a real gap: `repeat` at upload only replayed
    the instructional clip text, never the actual code — so a learner
    couldn't re-see it, or confirm it reflects what they actually wired."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state = _advance_to_step(lesson, library, state, 3)  # step-2b (VCC's wiring)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-3b
    pairs = [["pot1:SIG", "bb2:8t.a"], ["uno:A1", "bb2:8t.c"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> upload
    assert state["phase"] == "upload"

    state, actions = send(lesson, library, state, {"command": "repeat"})
    show_code = next((a for a in actions if a["type"] == "show_code"), None)
    assert show_code is not None
    assert "analogRead(A1)" in show_code["code"]
    assert "analogRead(A0)" not in show_code["code"]


def test_repeat_at_upload_shows_unmodified_code_without_a_substitution(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state = _advance_to_step(lesson, library, state, 4)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> upload
    state, actions = send(lesson, library, state, {"command": "repeat"})
    show_code = next(a for a in actions if a["type"] == "show_code")
    assert "analogRead(A0)" in show_code["code"]


def test_show_code_never_appears_outside_the_upload_step(lesson, library):
    """User request: code shall be shown only on the upload step. Checks
    every phase, plus the edge case of backing out of upload with
    `previous` and then asking to `repeat` — must not resurrect show_code."""
    def has_show_code(actions):
        return any(a["type"] == "show_code" for a in actions)

    # gather
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    for event in [{"command": "repeat"}, {"command": "hint"}]:
        _, actions = send(lesson, library, state, event)
        assert not has_show_code(actions)

    # every build sub-step
    state = _advance_to_step(lesson, library, state, 1)
    for target in range(1, 5):
        state = _advance_to_step(lesson, library, state, target)
        for event in [{"command": "repeat"}, {"command": "hint"}]:
            _, actions = send(lesson, library, state, event)
            assert not has_show_code(actions)

    # entering upload: show_code SHOULD appear here
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert has_show_code(actions)
    assert state["phase"] == "upload"

    # back out with previous -> build; repeat must not show code anymore
    state, _ = send(lesson, library, state, {"command": "previous"})
    assert state["phase"] == "build"
    state, actions = send(lesson, library, state, {"command": "repeat"})
    assert not has_show_code(actions)

    # final_check: repeat must not show code
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})  # back to upload
    state, _ = send(lesson, library, state, {"command": "done"})  # -> final_check
    assert state["phase"] == "final_check"
    state, actions = send(lesson, library, state, {"command": "repeat"})
    assert not has_show_code(actions)


def test_analog_pin_substitution_never_offers_a_pin_taken_by_another_component():
    """User-caught gap: a wiring check's own substitution search must not
    hand out an analog pin already confirmed for a DIFFERENT component —
    that would silently short two real components onto the same physical
    Arduino pin instead of flagging a genuine conflict. Uses a synthetic
    two-component scenario (this lesson only has one analog connection)."""
    expected = [["sensor1:OUT", "uno:A2"]]
    detected = [["sensor1:OUT", "uno:A1"]]  # mistakenly wired to A1, not A2

    # led1 already confirmed on A1, via a raw breadboard-hop confirmation
    # (the shape real confirmed_pairs entries actually have)
    confirmed_led1_on_a1 = [["led1:A", "bb2:3t.a"], ["uno:A1", "bb2:3t.c"]]
    alias_map = checker.board_alias_map([{"type": "wokwi-breadboard-mini", "id": "bb2"}])
    connector_ids = checker.connector_ids([{"type": "wokwi-breadboard-mini", "id": "bb2"}])

    alt_result, original, actual = engine._try_pin_substitution(
        expected, detected, {}, alias_map, connector_ids, confirmed_led1_on_a1, board_component_ids={"uno": "wokwi-arduino-uno"}
    )
    assert (alt_result, original, actual) == (None, None, None)


def test_analog_pin_substitution_still_allows_a_components_own_prior_pin():
    """Re-confirming the SAME component's own already-used analog pin is
    not a conflict with itself — only a genuinely different component
    claiming it should block the substitution."""
    expected = [["sensor1:OUT", "uno:A2"]]
    detected = [["sensor1:OUT", "uno:A1"]]
    confirmed_self = [["sensor1:OUT", "bb2:5t.a"], ["uno:A1", "bb2:5t.c"]]
    alias_map = checker.board_alias_map([{"type": "wokwi-breadboard-mini", "id": "bb2"}])
    connector_ids = checker.connector_ids([{"type": "wokwi-breadboard-mini", "id": "bb2"}])

    alt_result, original, actual = engine._try_pin_substitution(
        expected, detected, {}, alias_map, connector_ids, confirmed_self, board_component_ids={"uno": "wokwi-arduino-uno"}
    )
    assert alt_result is not None and alt_result["verdict"] == "pass"
    assert actual == "uno:A1"


def test_net_superset_match_accepts_a_component_wired_straight_to_the_boards_own_pin():
    """User design ('X and Y need to be in the same hole so we only accept
    Y to be in A5'): if the lesson expects two components to share one
    net (e.g. led2 chained onto led1's own leg), and the learner instead
    wires the second component with an independent wire straight to the
    Arduino pin the first one's leg actually landed on, that's the SAME
    real net a different, electrically identical way — checker.check's
    exact-member-set comparison alone would reject it, but the only extra
    net member here is the board's own pin, so the superset fallback
    should accept it."""
    expected = [["led2:A", "led1:A"]]
    # led1:A landed on uno:A5 (already substituted earlier); led2 is wired
    # with an independent jumper straight to uno:A5 instead of to led1's leg.
    detected = [["led1:A", "bb1:2t.a"], ["uno:A5", "bb1:2t.b"], ["led2:A", "bb1:2t.c"]]
    alias_map = checker.board_alias_map([{"type": "wokwi-breadboard-mini", "id": "bb1"}])
    connector_ids = checker.connector_ids([{"type": "wokwi-breadboard-mini", "id": "bb1"}])
    board_ids = {"uno": "wokwi-arduino-uno"}

    result = engine._try_net_superset_match(expected, detected, alias_map, connector_ids, board_ids)
    assert result == {"verdict": "pass", "missing": []}


def test_net_superset_match_refuses_when_the_extra_member_is_a_component_leg():
    """The narrow, safe scoping: the ONLY extra net member this tolerates
    is the board's own pin -- never another component's leg, even the
    SAME component's own other leg. Regression for the exact danger this
    fallback originally introduced and had to be tightened to reject: a
    resistor's own two legs (r1:1, r1:2) landing in the same net as the
    Arduino pin defeats the resistor's whole purpose and must NOT be
    silently accepted just because r1:1 (one of the two expected pins)
    happens to also be present."""
    expected = [["r1:1", "uno:13"]]
    detected = [["r1:1", "bb1:3b.h"], ["r1:2", "bb1:3b.i"], ["uno:13", "bb1:3b.g"]]
    alias_map = checker.board_alias_map([{"type": "wokwi-breadboard-mini", "id": "bb1"}])
    connector_ids = checker.connector_ids([{"type": "wokwi-breadboard-mini", "id": "bb1"}])
    board_ids = {"uno": "wokwi-arduino-uno"}

    result = engine._try_net_superset_match(expected, detected, alias_map, connector_ids, board_ids)
    assert result is None


def test_digital_pin_substitution_accepted_with_no_contention_in_the_lesson():
    """Revised (user request: match real electronics — any digital pin
    genuinely works as well as any other for a plain digitalWrite()
    connection, same as analog; the tool should figure out a conflict-
    free assignment rather than refuse a harmless deviation outright).
    Blink-shaped case — a single LED/resistor, nothing else in the
    lesson ever wants a digital pin — is now accepted, same as it always
    was for analog. _adjusted_code (see its own docstring) is what makes
    this safe: the shown code always rewrites to match whatever's
    actually wired, so accepting this never hides a code/wiring
    mismatch from the learner."""
    fake_lesson = _FakeLesson(
        steps=[{"id": "step-1", "expected_nets": [["r1:2", "uno:13"]]}],
        final_check_nets=[["r1:2", "uno:13"]],
    )
    expected = [["r1:2", "uno:13"]]
    detected = [["r1:2", "uno:12"]]  # different pin, nothing else competes for a digital pin

    alt_result, original, actual = engine._try_pin_substitution(
        expected, detected, {}, None, set(), confirmed_pairs=[],
        board_component_ids={"uno": "wokwi-arduino-uno"}, lesson=fake_lesson,
    )
    assert alt_result is not None and alt_result["verdict"] == "pass"
    assert original == "uno:13" and actual == "uno:12"


def test_digital_pin_substitution_accepted_when_a_later_step_contests_the_pin():
    """Same shape as the analog case that motivated this whole mechanism
    (the research log (in git history)): an LED deviates onto a digital pin that a LATER
    step's own script also wants for a different component (here, an
    LCD's RS line) — that's real contention, so the deviation is
    accepted, tracked, and the later step is the one that adapts (see
    _compute_pin_remap)."""
    fake_lesson = _FakeLesson(
        steps=[
            {"id": "step-1", "expected_nets": [["led1:A", "uno:5"]]},
            {"id": "step-2", "expected_nets": [["lcd1:RS", "uno:7"]]},
        ],
        final_check_nets=[["led1:A", "uno:5"], ["lcd1:RS", "uno:7"]],
    )
    expected_step1 = [["led1:A", "uno:5"]]
    detected_step1 = [["led1:A", "uno:7"]]  # also step-2's own scripted pin

    alt_result, original, actual = engine._try_pin_substitution(
        expected_step1, detected_step1, {}, None, set(), confirmed_pairs=[],
        board_component_ids={"uno": "wokwi-arduino-uno"}, lesson=fake_lesson,
    )
    assert alt_result is not None and alt_result["verdict"] == "pass"
    assert actual == "uno:7"


def test_i2c_sda_scl_never_offered_a_substitution_even_with_contention():
    """Real bug found via a real I2C LCD1602 diagram (the research log (in git history)):
    unlike a plain analogRead() sensor, I2C's SDA/SCL are hardware-fixed
    to A4/A5 on an Uno -- substituting either onto a different analog
    pin doesn't just need a code tweak, it physically stops being I2C.
    The engine was about to accept this and tell the learner
    'analogRead(A2) instead of analogRead(A4)', which is both nonsensical
    (I2C isn't analogRead) and not actually true in hardware. Must be
    refused regardless of contention -- construct a lesson where A2
    WOULD otherwise look like a perfectly good, contested substitute."""
    fake_lesson = _FakeLesson(
        steps=[
            {"id": "step-1", "expected_nets": [["lcd1:SDA", "uno:A4"]]},
            {"id": "step-2", "expected_nets": [["sensor1:OUT", "uno:A2"]]},
        ],
        final_check_nets=[["lcd1:SDA", "uno:A4"], ["sensor1:OUT", "uno:A2"]],
        extra_parts=[{"type": "board-ssd1306", "id": "lcd1"}],
    )
    expected = [["lcd1:SDA", "uno:A4"]]
    detected = [["lcd1:SDA", "uno:A2"]]

    alt_result, original, actual = engine._try_pin_substitution(
        expected, detected, {}, None, set(), confirmed_pairs=[],
        board_component_ids={"uno": "wokwi-arduino-uno"}, lesson=fake_lesson,
    )
    assert (alt_result, original, actual) == (None, None, None)


def test_uno_spi_pins_11_12_13_are_protected_like_i2c():
    """Real, confirmed fact (the research log (in git history)): the user pasted Wokwi's
    own wokwi-microsd-card reference page, which includes a worked Uno
    example with an explicit pinout table -- 'SCK 13, DO 12, DI 11, CS
    10' -- the exact evidence this project requires before narrowing a
    pool. SCK/MISO(DO)/MOSI(DI) on 13/12/11 are a real, shared SPI bus,
    the same class of fact as I2C's A4/A5; CS (pin 10) is deliberately
    NOT included -- per-device, freely assignable, same as the Mega."""
    fake_lesson = _FakeLesson(
        steps=[
            {"id": "step-1", "expected_nets": [["sd1:SCK", "uno:13"]]},
            {"id": "step-2", "expected_nets": [["bz1:2", "uno:9"]]},
        ],
        final_check_nets=[["sd1:SCK", "uno:13"], ["bz1:2", "uno:9"]],
        extra_parts=[{"type": "wokwi-microsd-card", "id": "sd1"}],
    )
    alt_result, *_ = engine._try_pin_substitution(
        [["sd1:SCK", "uno:13"]], [["sd1:SCK", "uno:9"]], {}, None, set(),
        confirmed_pairs=[], board_component_ids={"uno": "wokwi-arduino-uno"}, lesson=fake_lesson,
    )
    assert alt_result is None

    # CS (pin 10) stays freely assignable -- real contention still substitutes normally.
    fake_lesson2 = _FakeLesson(
        steps=[
            {"id": "step-1", "expected_nets": [["sd1:CS", "uno:10"]]},
            {"id": "step-2", "expected_nets": [["led1:A", "uno:9"]]},
        ],
        final_check_nets=[["sd1:CS", "uno:10"], ["led1:A", "uno:9"]],
    )
    alt_result2, original2, actual2 = engine._try_pin_substitution(
        [["sd1:CS", "uno:10"]], [["sd1:CS", "uno:9"]], {}, None, set(),
        confirmed_pairs=[], board_component_ids={"uno": "wokwi-arduino-uno"}, lesson=fake_lesson2,
    )
    assert alt_result2 is not None and alt_result2["verdict"] == "pass"
    assert actual2 == "uno:9"


def test_plain_analog_sensor_on_a4_still_substitutes_normally():
    """The I2C fix must be scoped to the SDA/SCL leg name, not to A4/A5
    as pins -- a plain analogRead() sensor happening to use A4 (nothing
    to do with I2C) must still substitute exactly like any other analog
    pin, unaffected."""
    expected = [["sensor1:OUT", "uno:A4"]]
    detected = [["sensor1:OUT", "uno:A2"]]

    alt_result, original, actual = engine._try_pin_substitution(
        expected, detected, {}, None, set(), confirmed_pairs=[],
        board_component_ids={"uno": "wokwi-arduino-uno"}, lesson=None,
    )
    assert alt_result is not None and alt_result["verdict"] == "pass"
    assert actual == "uno:A2"


def test_i2c_connection_never_remapped_even_when_its_pin_is_taken():
    """Same protection on the remap side: if something else ends up
    confirmed on A4, an I2C SDA connection scripted for A4 must NOT be
    silently 'moved' to a different analog pin -- there is no working
    replacement pin for I2C, so this has to surface as a real conflict,
    not a fabricated remap."""
    fake_lesson = _FakeLesson(
        steps=[{"id": "step-1", "expected_nets": [["lcd1:SDA", "uno:A4"]]}],
        final_check_nets=[["lcd1:SDA", "uno:A4"]],
        extra_parts=[{"type": "board-ssd1306", "id": "lcd1"}],
    )
    state = engine.initial_state()
    state["confirmed_pairs"] = [["sensor1:OUT", "uno:A4"]]  # something else already owns A4

    remap = engine._compute_pin_remap(fake_lesson, state, fake_lesson.data["steps"][0])
    assert remap is None


def test_dht22_style_digital_sda_leg_is_unaffected_by_the_i2c_fix():
    """Refinement caught during investigation: the I2C fix must key off
    the ANALOG domain specifically (A4/A5's real hardware-fixed role),
    not the bare leg name 'SDA' -- the DHT22 (verified earlier this
    session: VCC, SDA, NC, GND) also names its data leg 'SDA', but
    that's Wokwi's own naming coincidence for an unrelated one-wire
    digital protocol with no fixed-pin constraint at all. A DHT22-shaped
    digital 'SDA' connection must substitute exactly like any other
    digital pin, with real contention."""
    expected = [["dht1:SDA", "uno:2"]]
    detected = [["dht1:SDA", "uno:4"]]  # also wanted by another component
    fake_lesson = _FakeLesson(
        steps=[
            {"id": "step-1", "expected_nets": expected},
            {"id": "step-2", "expected_nets": [["led1:A", "uno:4"]]},
        ],
        final_check_nets=[["dht1:SDA", "uno:2"], ["led1:A", "uno:4"]],
    )

    alt_result, original, actual = engine._try_pin_substitution(
        expected, detected, {}, None, set(), confirmed_pairs=[],
        board_component_ids={"uno": "wokwi-arduino-uno"}, lesson=fake_lesson,
    )
    assert alt_result is not None and alt_result["verdict"] == "pass"
    assert actual == "uno:4"


def test_a4_never_offered_as_a_substitute_to_an_unrelated_component_when_i2c_uses_it():
    """Real gap found via a real mixed-domain diagram (the research log (in git history)):
    refusing to move the I2C connection itself (see the tests above) is
    not enough on its own. A plain analogRead() sensor scripted for A0
    could still be silently accepted onto A4 in an EARLIER step, before
    the I2C step is even reached -- and since the I2C connection then
    can never be remapped away from A4, the learner correctly following
    the (unchanged) instruction would silently short the sensor's signal
    onto the I2C bus, with zero warning. A4 must be refused as a
    substitution TARGET for the sensor too, the moment this lesson's own
    script uses it for SDA/SCL anywhere."""
    fake_lesson = _FakeLesson(
        steps=[
            {"id": "step-1", "expected_nets": [["ldr1:AO", "uno:A0"]]},
            {"id": "step-2", "expected_nets": [["lcd1:SDA", "uno:A4"]]},
        ],
        final_check_nets=[["ldr1:AO", "uno:A0"], ["lcd1:SDA", "uno:A4"]],
        extra_parts=[{"type": "board-ssd1306", "id": "lcd1"}],
    )
    expected = [["ldr1:AO", "uno:A0"]]
    detected = [["ldr1:AO", "uno:A4"]]  # LDR deviates onto the LCD's own I2C pin

    alt_result, original, actual = engine._try_pin_substitution(
        expected, detected, {}, None, set(), confirmed_pairs=[],
        board_component_ids={"uno": "wokwi-arduino-uno"}, lesson=fake_lesson,
    )
    assert (alt_result, original, actual) == (None, None, None)


class _FakeMegaLesson:
    """Minimal Lesson stand-in for a Mega-board diagram — parallel to
    _FakeLesson, but board_component_ids need to see a real
    'wokwi-arduino-mega' part, not the Uno _FakeLesson always hands
    back. `extra_parts` lets a test declare the REAL wokwi_type for any
    other component its steps reference (e.g. a real I2C/SPI device),
    needed since protocol-leg protection is now resolved by looking up
    each component's own library card — a real diagram always lists
    every part it uses, so a test fixture needs to as well."""

    def __init__(self, steps, extra_parts=None):
        self.data = {"steps": steps, "final_check": {"expected_nets": []}}
        self._extra_parts = extra_parts or []

    def diagram(self):
        return {"parts": [{"type": "wokwi-arduino-mega", "id": "mega"}] + self._extra_parts}


MEGA_BOARD_IDS = {"mega": "wokwi-arduino-mega"}


def test_mega_analog_pool_extends_past_the_unos_a0_a5_shape():
    """Generalization (the research log (in git history)): the Mega has 16 analog pins
    (A0-A15), not the Uno's 6 -- a diagram using A10 must be recognized
    as a real, substitutable analog pin, not silently treated as
    unsubstitutable just because it's outside the Uno's own shape."""
    pool, kind = engine._pin_domain("mega:A10", MEGA_BOARD_IDS)
    assert kind == "analog"
    assert "A10" in pool


def test_nano_analog_pool_includes_the_two_extra_analog_only_pins():
    """Real fact, pasted directly by the user from docs.wokwi.com/parts/
    wokwi-arduino-nano: 'The Arduino Nano includes two extra analog
    pins: A6 and A7. These pins can only be used for Analog input. They
    can't be used as digital GPIO pins.' A6/A7 must be recognized as
    real, substitutable analog pins -- and the analog-only restriction
    needs no special-casing, since they're simply never members of the
    digital set either."""
    board_ids = {"nano": "wokwi-arduino-nano"}
    pool, kind = engine._pin_domain("nano:A7", board_ids)
    assert kind == "analog" and "A7" in pool
    # Confirm A6/A7 are NOT also digital -- the analog-only restriction
    # holds automatically, without a separate exclusion list.
    _, digital_kind = engine._pin_domain("nano:A7", board_ids)
    assert digital_kind != "digital"


def test_nano_i2c_on_a4_a5_protected_like_the_unos():
    """Real fact confirmed by an actual diagram: an SSD1306 OLED's
    SDA/SCL wired straight to nano:A4/A5, identical to the Uno's own
    I2C pins (the Nano's own docs page, pasted by the user, describes
    it as carrying "the same ATmega328p chip" and defers to the Uno
    reference for anything not called out as a difference)."""
    board_ids = {"nano": "wokwi-arduino-nano"}

    class FakeLesson:
        def __init__(self):
            self.data = {"steps": [{"id": "s1", "expected_nets": [["oled1:SDA", "nano:A4"]]}], "final_check": {"expected_nets": []}}
        def diagram(self):
            return {"parts": [{"type": "wokwi-arduino-nano", "id": "nano"}, {"type": "board-ssd1306", "id": "oled1"}]}

    alt_result, *_ = engine._try_pin_substitution(
        [["oled1:SDA", "nano:A4"]], [["oled1:SDA", "nano:A2"]], {}, None, set(),
        confirmed_pairs=[], board_component_ids=board_ids, lesson=FakeLesson(),
    )
    assert alt_result is None


def test_mega_digital_pool_extends_past_pin_13_but_excludes_the_primary_serial_port():
    """The Mega's digital range is 0-53, not the Uno's 0-13 -- pin 30
    must be recognized as substitutable. Pins 0/1 (the primary hardware
    serial port, also used by the USB bootloader during upload
    regardless of whether any lesson's code calls Serial.begin()) stay
    excluded, same as the Uno.

    The Mega's three OTHER hardware serial ports (14/15, 16/17, 18/19)
    are deliberately NOT excluded here, despite being real, documented
    UARTs (docs.wokwi.com/parts/wokwi-arduino-mega) -- unlike 0/1, no
    Mega lesson exists to verify any of them are actually needed for
    communication, and a real diagram directly contradicted excluding
    them by wiring a button straight to pin 19 and a buzzer to pin 1's
    Serial1 counterpart -- repurposing spare UARTs as plain GPIO when
    they're not needed for communication is normal Mega practice.
    Deferred like PWM/interrupt/SPI, not guessed at."""
    pool, kind = engine._pin_domain("mega:30", MEGA_BOARD_IDS)
    assert kind == "digital" and "30" in pool
    for leg in ["0", "1"]:
        pool, kind = engine._pin_domain(f"mega:{leg}", MEGA_BOARD_IDS)
        assert kind is None, f"mega:{leg} should not be substitutable"
    for leg in ["14", "15", "16", "17", "18", "19"]:
        pool, kind = engine._pin_domain(f"mega:{leg}", MEGA_BOARD_IDS)
        assert kind == "digital", f"mega:{leg} should be substitutable (spare UART, not verified in use)"


def test_mega_i2c_lives_on_digital_pins_unlike_the_unos_analog_i2c():
    """Real, board-specific fact (the research log (in git history)): the Mega's I2C is on
    pins 20/21 -- plain DIGITAL pins, unlike the Uno where I2C happens to
    sit on the analog-labeled A4/A5. A deviation on the Mega's SDA (pin
    20) must be refused a substitution exactly like the Uno's A4 case,
    even though it lives in a completely different domain."""
    fake_lesson = _FakeMegaLesson(
        steps=[
            {"id": "s1", "expected_nets": [["sensor1:SDA", "mega:20"]]},
            {"id": "s2", "expected_nets": [["led1:A", "mega:2"]]},
        ],
        extra_parts=[{"type": "board-ssd1306", "id": "sensor1"}],
    )
    expected = [["sensor1:SDA", "mega:20"]]
    detected = [["sensor1:SDA", "mega:2"]]
    alt_result, original, actual = engine._try_pin_substitution(
        expected, detected, {}, None, set(), confirmed_pairs=[],
        board_component_ids=MEGA_BOARD_IDS, lesson=fake_lesson,
    )
    assert (alt_result, original, actual) == (None, None, None)


def test_mega_i2c_pin_cannot_be_stolen_by_an_unrelated_component_either():
    """Same two-sided protection as the Uno's A4 case: an unrelated
    component must not be allowed to substitute ONTO the Mega's real I2C
    pin (20) either, even though — unlike the Uno — that pin sits in the
    DIGITAL domain here."""
    fake_lesson = _FakeMegaLesson(
        steps=[
            {"id": "s1", "expected_nets": [["sensor2:OUT", "mega:5"]]},
            {"id": "s2", "expected_nets": [["oled1:SDA", "mega:20"]]},
        ],
        extra_parts=[{"type": "board-ssd1306", "id": "oled1"}],
    )
    expected = [["sensor2:OUT", "mega:5"]]
    detected = [["sensor2:OUT", "mega:20"]]  # tries to steal the I2C pin
    alt_result, original, actual = engine._try_pin_substitution(
        expected, detected, {}, None, set(), confirmed_pairs=[],
        board_component_ids=MEGA_BOARD_IDS, lesson=fake_lesson,
    )
    assert (alt_result, original, actual) == (None, None, None)


def test_mega_dht22_style_digital_sda_away_from_pin_20_still_substitutes():
    """Scoping check: the Mega's I2C protection must be keyed on the
    EXACT pin (20/21), not "any digital pin named SDA" -- a DHT22-style
    digital SDA leg on a different pin (6) must still substitute
    normally with real contention, exactly like the Uno case."""
    fake_lesson = _FakeMegaLesson(steps=[
        {"id": "s1", "expected_nets": [["dht1:SDA", "mega:6"]]},
        {"id": "s2", "expected_nets": [["led1:A", "mega:8"]]},
    ])
    expected = [["dht1:SDA", "mega:6"]]
    detected = [["dht1:SDA", "mega:8"]]
    alt_result, original, actual = engine._try_pin_substitution(
        expected, detected, {}, None, set(), confirmed_pairs=[],
        board_component_ids=MEGA_BOARD_IDS, lesson=fake_lesson,
    )
    assert alt_result is not None and alt_result["verdict"] == "pass"
    assert actual == "mega:8"


def test_mega_spi_bus_pins_are_protected_like_i2c(library):
    """Real bug found via a real diagram (an ILI9341 touch LCD + microSD
    card sharing one SPI bus on a Mega): MISO/MOSI/SCK are the same
    class of fact as I2C's SDA/SCL -- a real, shared hardware bus, not a
    per-device free choice. The engine was about to accept a deviation
    on the SD card's SCK and silently desync it from the LCD's own,
    still-mega:52-wired SCK line -- same failure shape as the original
    I2C bug, just for a bus of two devices instead of one pair."""
    fake_lesson = _FakeMegaLesson(
        steps=[
            {"id": "s1", "expected_nets": [["sd1:SCK", "mega:52"]]},
            {"id": "s2", "expected_nets": [["bz1:2", "mega:9"]]},
        ],
        extra_parts=[{"type": "wokwi-microsd-card", "id": "sd1"}],
    )
    alt_result, *_ = engine._try_pin_substitution(
        [["sd1:SCK", "mega:52"]], [["sd1:SCK", "mega:9"]], {}, None, set(),
        confirmed_pairs=[], board_component_ids=MEGA_BOARD_IDS, lesson=fake_lesson,
    )
    assert alt_result is None


def test_mega_spi_data_lines_protected_even_under_a_different_leg_name(library):
    """The microSD card names its SPI data lines 'DO'/'DI' (verified:
    docs.wokwi.com/parts/wokwi-microsd-card — "DO (SPI data
    output/MISO)", "DI (SPI data input/MOSI)"), not 'MISO'/'MOSI' like
    the LCD's own connection to the SAME physical bus. Both names must
    be protected on the real SPI pins (mega:50/51) -- matching by name
    alone would miss this device, matching by pin alone would (like the
    old I2C bug) risk false positives on an unrelated component's own
    'DO'/'DI'-named pin landing on an ordinary digital pin."""
    fake_lesson = _FakeMegaLesson(
        steps=[{"id": "s1", "expected_nets": [["sd1:DI", "mega:51"]]}],
        extra_parts=[{"type": "wokwi-microsd-card", "id": "sd1"}],
    )
    alt_result, *_ = engine._try_pin_substitution(
        [["sd1:DI", "mega:51"]], [["sd1:DI", "mega:9"]], {}, None, set(),
        confirmed_pairs=[], board_component_ids=MEGA_BOARD_IDS, lesson=fake_lesson,
    )
    assert alt_result is None


def test_a_do_named_pin_away_from_the_real_spi_bus_still_substitutes_normally(library):
    """Scoping check, mirroring the DHT22/I2C precedent: a component
    that happens to name its own leg 'DO' (e.g. a photoresistor sensor,
    verified earlier this session: VCC/GND/DO/AO) but ISN'T wired to the
    Mega's real SPI bus pins must still substitute normally -- matching
    requires the exact protocol pin identity together with the leg
    name, never the leg name alone."""
    fake_lesson = _FakeMegaLesson(steps=[
        {"id": "s1", "expected_nets": [["ldr1:DO", "mega:6"]]},
        {"id": "s2", "expected_nets": [["led1:A", "mega:8"]]},
    ])
    alt_result, original, actual = engine._try_pin_substitution(
        [["ldr1:DO", "mega:6"]], [["ldr1:DO", "mega:8"]], {}, None, set(),
        confirmed_pairs=[], board_component_ids=MEGA_BOARD_IDS, lesson=fake_lesson,
    )
    assert alt_result is not None and alt_result["verdict"] == "pass"
    assert actual == "mega:8"


def test_mega_spi_cs_pins_stay_freely_assignable_unlike_the_shared_bus_lines(library):
    """CS/SS is deliberately NOT protected, unlike MISO/MOSI/SCK -- each
    SPI device gets its own chip-select line, confirmed by the real
    diagram itself using two different CS pins (mega:10 for the LCD,
    mega:4 for the SD card) for the two devices sharing one bus. A CS
    deviation with real contention must still substitute normally."""
    fake_lesson = _FakeMegaLesson(steps=[
        {"id": "s1", "expected_nets": [["lcd1:CS", "mega:10"]]},
        {"id": "s2", "expected_nets": [["sd1:CS", "mega:4"]]},
    ])
    alt_result, original, actual = engine._try_pin_substitution(
        [["lcd1:CS", "mega:10"]], [["lcd1:CS", "mega:4"]], {}, None, set(),
        confirmed_pairs=[], board_component_ids=MEGA_BOARD_IDS, lesson=fake_lesson,
    )
    assert alt_result is not None and alt_result["verdict"] == "pass"
    assert actual == "mega:4"


def _run_check_with_wrong_detection(lesson, library, steps_before, detected_pairs):
    """Advance `steps_before` build steps correctly, then trigger a
    check with `detected_pairs` on whichever step comes next."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> first build step
    for _ in range(steps_before):
        state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
        state, _ = send(lesson, library, state, {"command": "done"})
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": detected_pairs})
    return send(lesson, library, state, {"command": "done"})


def test_refusal_hint_explains_a_stolen_i2c_pin(library, tmp_path):
    """User request: when a substitution is refused, explain why and,
    where possible, what to do instead. Case 1 -- a plain sensor's
    deviation happens to land on a pin this lesson's own I2C device
    already owns -- gets an actionable explanation, not just 'wrong'."""
    (tmp_path / "diagram.json").write_text(
        '{"parts": [{"type": "wokwi-arduino-uno", "id": "uno"}, {"type": "board-ssd1306", "id": "oled1"}], "connections": []}'
    )
    (tmp_path / "code.ino").write_text("void setup(){Wire.begin();}\nvoid loop(){}\n")
    data = {
        "id": "hint-i2c-stolen", "title": "t", "code": "code.ino", "wokwi_diagram": "diagram.json",
        "steps": [
            {"id": "gather", "phase": "gather", "clip": "g", "items": []},
            {"id": "step-1", "phase": "build", "clip": "Wire LDR to A0.", "expected_nets": [["ldr1:AO", "uno:A0"]], "hints": []},
            {"id": "step-2", "phase": "build", "clip": "Wire SDA to A4.", "expected_nets": [["oled1:SDA", "uno:A4"]], "hints": []},
            {"id": "upload-code", "phase": "upload", "clip": "u", "code": "code.ino"},
        ],
        "final_check": {"expected_nets": [["ldr1:AO", "uno:A0"], ["oled1:SDA", "uno:A4"]]},
    }
    lesson = Lesson(data, tmp_path)
    state, actions = _run_check_with_wrong_detection(lesson, library, 0, [["ldr1:AO", "uno:A4"]])
    hint = next(a for a in actions if a["type"] == "substitution_refused")
    assert "uno:A4" in hint["message"]
    assert "I2C" in hint["message"]


def test_refusal_hint_explains_a_hardware_fixed_i2c_pin(library, tmp_path):
    """Case 2 -- the I2C connection itself got moved off its real,
    fixed pin -- explains WHY, since there's no alternative to offer."""
    (tmp_path / "diagram.json").write_text(
        '{"parts": [{"type": "wokwi-arduino-uno", "id": "uno"}, {"type": "board-ssd1306", "id": "oled1"}], "connections": []}'
    )
    (tmp_path / "code.ino").write_text("void setup(){Wire.begin();}\nvoid loop(){}\n")
    data = {
        "id": "hint-i2c-fixed", "title": "t", "code": "code.ino", "wokwi_diagram": "diagram.json",
        "steps": [
            {"id": "gather", "phase": "gather", "clip": "g", "items": []},
            {"id": "step-1", "phase": "build", "clip": "Wire LDR to A0.", "expected_nets": [["ldr1:AO", "uno:A0"]], "hints": []},
            {"id": "step-2", "phase": "build", "clip": "Wire SDA to A4.", "expected_nets": [["oled1:SDA", "uno:A4"]], "hints": []},
            {"id": "upload-code", "phase": "upload", "clip": "u", "code": "code.ino"},
        ],
        "final_check": {"expected_nets": [["ldr1:AO", "uno:A0"], ["oled1:SDA", "uno:A4"]]},
    }
    lesson = Lesson(data, tmp_path)
    state, actions = _run_check_with_wrong_detection(lesson, library, 1, [["oled1:SDA", "uno:A2"]])
    hint = next(a for a in actions if a["type"] == "substitution_refused")
    assert "uno:A4" in hint["message"]
    assert "hardware" in hint["message"]
    assert "I2C" in hint["message"]


def test_refusal_hint_names_spi_not_i2c_for_a_real_spi_pin(library, tmp_path):
    """Regression: BOARD_PROTOCOL_PINS covers both I2C and SPI pins, but
    the refusal message used to hardcode 'I2C' regardless -- caught by
    the test suite itself the moment Uno's SPI pins (11/12/13) were
    added, since an existing 'plain digital, no special reason' test
    happened to use pin 13 and started getting an I2C-worded message
    for what is actually SPI. The message must name the real protocol
    for the specific pin involved."""
    (tmp_path / "diagram.json").write_text(
        '{"parts": [{"type": "wokwi-arduino-uno", "id": "uno"}, {"type": "wokwi-microsd-card", "id": "sd1"}], "connections": []}'
    )
    (tmp_path / "code.ino").write_text("void setup(){}\nvoid loop(){}\n")
    data = {
        "id": "spi-hint-demo", "title": "t", "code": "code.ino", "wokwi_diagram": "diagram.json",
        "steps": [
            {"id": "gather", "phase": "gather", "clip": "g", "items": []},
            {"id": "step-1", "phase": "build", "clip": "Wire SD SCK to pin 13.", "expected_nets": [["sd1:SCK", "uno:13"]], "hints": []},
            {"id": "upload-code", "phase": "upload", "clip": "u", "code": "code.ino"},
        ],
        "final_check": {"expected_nets": [["sd1:SCK", "uno:13"]]},
    }
    lesson = Lesson(data, tmp_path)
    state, actions = _run_check_with_wrong_detection(lesson, library, 0, [["sd1:SCK", "uno:9"]])
    hint = next(a for a in actions if a["type"] == "substitution_refused")
    assert "SPI" in hint["message"]
    assert "I2C" not in hint["message"]


def test_refusal_hint_never_blames_protocol_for_an_ordinary_pin_collision(library, tmp_path):
    """Regression, found via a real, complex user-supplied diagram (a
    Simon-says game: 4 buttons, 4 LEDs, a buzzer, two 74HC595 shift
    registers): an ordinary LED scripted onto the Uno's pin 12 just
    because that's where the diagram put it has NOTHING to do with SPI
    -- pin 12 merely happens to also be the Uno's real MISO identity.
    When this LED collides with a genuinely different problem (another
    component already owns the pin it deviated to), the refusal must
    blame THAT, not misattribute it to protocol protection this
    connection was never part of -- the old check only looked at the
    board pin's identity, never whether the component's own leg is
    actually a declared protocol-bus leg (_leg_is_protocol_bus)."""
    (tmp_path / "diagram.json").write_text(
        '{"parts": ['
        '{"type": "wokwi-arduino-uno", "id": "uno"}, '
        '{"type": "wokwi-led", "id": "led1"}, '
        '{"type": "wokwi-led", "id": "led2"}'
        '], "connections": []}'
    )
    (tmp_path / "code.ino").write_text("void setup(){}\nvoid loop(){}\n")
    data = {
        "id": "spi-false-positive-demo", "title": "t", "code": "code.ino", "wokwi_diagram": "diagram.json",
        "steps": [
            {"id": "gather", "phase": "gather", "clip": "g", "items": []},
            {"id": "step-1", "phase": "build", "clip": "Wire led1 to pin 7.", "expected_nets": [["led1:A", "uno:7"]], "hints": []},
            {"id": "step-2", "phase": "build", "clip": "Wire led2 to pin 12.", "expected_nets": [["led2:A", "uno:12"]], "hints": []},
            {"id": "upload-code", "phase": "upload", "clip": "u", "code": "code.ino"},
        ],
        "final_check": {"expected_nets": [["led1:A", "uno:7"], ["led2:A", "uno:12"]]},
    }
    lesson = Lesson(data, tmp_path)
    # led1 deviates from its scripted pin 7 onto pin 8 (accepted, no
    # contention) -- _run_check_with_wrong_detection's own "sim -> done"
    # check IS the deviation and advances past step-1.
    state, _ = _run_check_with_wrong_detection(lesson, library, 0, [["led1:A", "uno:8"]])
    # led2 (scripted for the Uno's real SPI-identity pin 12, but NOT an
    # SPI device) collides with led1's now-confirmed pin 8 -- a genuine
    # ownership conflict, unrelated to protocol protection.
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["led2:A", "uno:8"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    hint = next(a for a in actions if a["type"] == "substitution_refused")
    assert "SPI" not in hint["message"] and "I2C" not in hint["message"]
    assert "led2" in hint["message"] and "12" in hint["message"]


def test_plain_digital_deviation_with_no_special_reason_is_now_accepted(library, tmp_path):
    """Revised (user request: match real electronics -- see
    _try_pin_substitution's docstring). This used to be "case 3": a
    plain digital refusal with no special reason behind it (the
    scripted pin already IS the only sensible answer, since nothing
    else in the lesson contends for a digital pin) got a concrete
    refusal instruction rather than being accepted. That justification
    no longer applies now that _adjusted_code always rewrites the shown
    code to match whatever's actually wired -- so this plain, harmless
    deviation is accepted via substitution instead, same as it always
    was for analog."""
    (tmp_path / "diagram.json").write_text('{"parts": [{"type": "wokwi-arduino-uno", "id": "uno"}], "connections": []}')
    (tmp_path / "code.ino").write_text("void setup(){}\nvoid loop(){}\n")
    data = {
        "id": "hint-plain", "title": "t", "code": "code.ino", "wokwi_diagram": "diagram.json",
        "steps": [
            {"id": "gather", "phase": "gather", "clip": "g", "items": []},
            # Pin 9, not 13 -- 11/12/13 are the Uno's real, protocol-fixed
            # SPI pins (BOARD_PROTOCOL_PINS), so this test must use an
            # ordinary pin to stay testing the "no special reason" case.
            {"id": "step-1", "phase": "build", "clip": "Wire LED to 9.", "expected_nets": [["led1:A", "uno:9"]], "hints": []},
            {"id": "upload-code", "phase": "upload", "clip": "u", "code": "code.ino"},
        ],
        "final_check": {"expected_nets": [["led1:A", "uno:9"]]},
    }
    lesson = Lesson(data, tmp_path)
    state, actions = _run_check_with_wrong_detection(lesson, library, 0, [["led1:A", "uno:12"]])
    sub = next(a for a in actions if a["type"] == "pin_substituted")
    assert "uno:9" in sub["message"] and "uno:12" in sub["message"]


class _FakeLesson:
    """Minimal stand-in for core.lesson.Lesson — only what
    _reserved_pins/_compute_pin_remap read (lesson.data,
    lesson.diagram()). Used to test a synthetic two-analog-pin-connection
    scenario, since analog-read-serial itself only has one (SIG->A0).
    `extra_parts` lets a test declare the REAL wokwi_type for any other
    component its steps reference (e.g. a real I2C/SPI device), needed
    since protocol-leg protection is now resolved by looking up each
    component's own library card — a real diagram always lists every
    part it uses, so a test fixture needs to as well."""

    def __init__(self, steps, final_check_nets, extra_parts=None):
        self.data = {"steps": steps, "final_check": {"expected_nets": final_check_nets}}
        self._extra_parts = extra_parts or []

    def diagram(self):
        return {"parts": [{"type": "wokwi-arduino-uno", "id": "uno"}] + self._extra_parts}


def test_analog_pin_substitution_accepts_a_pin_a_future_step_also_wants():
    """Design decision (superseding an earlier, stricter attempt): step-1's
    own substitution search does NOT refuse a pin just because step-2's
    script also wants it for a different component. Accepting step-1's
    actual choice is correct — the *later* step is the one that silently
    adapts around it (see _compute_pin_remap below), not this one that
    gets second-guessed or blocked."""
    expected_step1 = [["led1:A", "uno:A0"]]
    detected_step1 = [["led1:A", "uno:A2"]]  # also step-2's own scripted pin

    alt_result, original, actual = engine._try_pin_substitution(
        expected_step1, detected_step1, {}, None, set(), confirmed_pairs=[], board_component_ids={"uno": "wokwi-arduino-uno"}
    )
    assert alt_result is not None and alt_result["verdict"] == "pass"
    assert actual == "uno:A2"


def test_compute_pin_remap_reassigns_a_later_step_away_from_a_taken_pin(lesson, library):
    """User request: if step-1 ends up on the pin step-2's script wants,
    step-2 should silently reassign itself to a genuinely free pin —
    not force step-1 to be redone, and not just fail with a confusing
    'wrong' once the learner correctly tries to use their own scripted pin."""
    fake_lesson = _FakeLesson(
        steps=[
            {"id": "step-1", "expected_nets": [["led1:A", "uno:A0"]]},
            {"id": "step-2", "expected_nets": [["sensor1:OUT", "uno:A2"]]},
        ],
        final_check_nets=[["led1:A", "uno:A0"], ["sensor1:OUT", "uno:A2"]],
    )
    state = engine.initial_state()
    # led1 already confirmed directly on A2 (step-1's own accepted deviation)
    state["confirmed_pairs"] = [["led1:A", "uno:A2"]]

    remap = engine._compute_pin_remap(fake_lesson, state, fake_lesson.data["steps"][1])
    assert remap is not None
    assert remap["original"] == "uno:A2"
    assert remap["component"] == "sensor1"
    assert remap["actual"] != "uno:A2"
    assert remap["actual"] != "uno:A0"  # not led1's pin either


def test_compute_pin_remap_does_nothing_when_the_scripted_pin_is_still_free(lesson, library):
    fake_lesson = _FakeLesson(
        steps=[
            {"id": "step-1", "expected_nets": [["led1:A", "uno:A0"]]},
            {"id": "step-2", "expected_nets": [["sensor1:OUT", "uno:A2"]]},
        ],
        final_check_nets=[["led1:A", "uno:A0"], ["sensor1:OUT", "uno:A2"]],
    )
    state = engine.initial_state()
    state["confirmed_pairs"] = [["led1:A", "uno:A0"]]  # led1 wired exactly as scripted
    remap = engine._compute_pin_remap(fake_lesson, state, fake_lesson.data["steps"][1])
    assert remap is None


def test_digital_pin_substitution_accepts_a_pin_a_future_step_also_wants():
    """Digital counterpart of test_analog_pin_substitution_accepts_a_pin_
    a_future_step_also_wants above, now that digital deviation is
    unconditionally offered too (see _try_pin_substitution's docstring):
    step-1's own substitution search still doesn't refuse a pin just
    because step-2's script also wants it for a different component --
    _compute_pin_remap (see the reservation-avoidance test below) is
    what keeps step-2 safe when its own turn comes, not a refusal here."""
    expected_step1 = [["led1:A", "uno:5"]]
    detected_step1 = [["led1:A", "uno:8"]]  # also step-2's own scripted pin
    fake_lesson = _FakeLesson(
        steps=[
            {"id": "step-1", "expected_nets": expected_step1},
            {"id": "step-2", "expected_nets": [["led2:A", "uno:8"]]},
        ],
        final_check_nets=[["led1:A", "uno:5"], ["led2:A", "uno:8"]],
    )

    alt_result, original, actual = engine._try_pin_substitution(
        expected_step1, detected_step1, {}, None, set(), confirmed_pairs=[],
        board_component_ids={"uno": "wokwi-arduino-uno"}, lesson=fake_lesson,
    )
    assert alt_result is not None and alt_result["verdict"] == "pass"
    assert actual == "uno:8"


def test_compute_pin_remap_avoids_a_pin_a_third_components_future_step_wants(lesson, library):
    """User's exact safety scenario, now that digital deviation is
    unconditionally offered (_try_pin_substitution's docstring): 'if led
    wants 12 we give 13 and another led gets 12 that's no conflict, but
    if X can only get 8 and we give it to someone then we're screwed'.
    Three components' worth of digital pins: led1 already deviated onto
    sensor1's scripted pin (forcing a remap search), AND led2's own
    still-unreached step wants a specific, different pin. The remap
    must not hand sensor1 that reserved pin, even though it's genuinely
    free right now -- it must pick one nothing else has ANY claim on,
    leaving led2 able to get its own scripted pin later without needing
    its own remap in turn."""
    fake_lesson = _FakeLesson(
        steps=[
            {"id": "step-1", "expected_nets": [["led1:A", "uno:5"]]},
            {"id": "step-2", "expected_nets": [["led2:A", "uno:8"]]},
            {"id": "step-3", "expected_nets": [["sensor1:OUT", "uno:9"]]},
        ],
        final_check_nets=[["led1:A", "uno:5"], ["led2:A", "uno:8"], ["sensor1:OUT", "uno:9"]],
    )
    state = engine.initial_state()
    # led1 already deviated off its own script (5) straight onto
    # sensor1's scripted pin (9) -- forcing sensor1's step-3 to remap.
    state["confirmed_pairs"] = [["led1:A", "uno:9"]]

    remap = engine._compute_pin_remap(fake_lesson, state, fake_lesson.data["steps"][2])
    assert remap is not None
    assert remap["original"] == "uno:9"
    assert remap["actual"] not in ("uno:8", "uno:9")  # never the pin led2's own script still needs


def test_compute_pin_remap_reports_exhaustion_instead_of_a_bare_none(library):
    """User-raised edge case: if EVERY pin in the domain is already taken
    by someone else, there's no free pin left to silently remap to. That
    must be distinguishable from 'nothing to remap' (both used to return
    a bare None) — conflating them would leave a step's instruction
    pointing at a pin another component already owns, with the learner
    never told, and correctly following it would physically short two
    components onto one Arduino pin."""
    fake_lesson = _FakeLesson(
        steps=[{"id": "step-1", "expected_nets": [["sensor1:OUT", "uno:7"]]}],
        final_check_nets=[["sensor1:OUT", "uno:7"]],
    )
    state = engine.initial_state()
    # Every digital pin except 7 is already claimed by other components,
    # and 7 itself (this step's own target) is ALSO already someone
    # else's -- zero free alternatives remain anywhere in the pool.
    state["confirmed_pairs"] = [[f"decoy{n}:X", f"uno:{n}"] for n in range(2, 14) if n != 7]
    state["confirmed_pairs"].append(["other1:Y", "uno:7"])

    remap = engine._compute_pin_remap(fake_lesson, state, fake_lesson.data["steps"][0])
    assert remap == {"original": "uno:7", "actual": None, "component": "sensor1"}


def test_exhausted_remap_warns_instead_of_silently_pointing_at_a_taken_pin(library):
    """End-to-end: entering a step whose target is exhausted must not
    persist a broken remap (nothing downstream — _apply_pin_remaps, the
    `hint` command — expects "actual" to ever be None) and must warn in
    the clip rather than silently repeat the already-taken pin number."""
    fake_lesson = _FakeLesson(
        steps=[{"id": "step-1", "phase": "build", "expected_nets": [["sensor1:OUT", "uno:7"]], "clip": "Wire the sensor to pin 7.", "hints": []}],
        final_check_nets=[["sensor1:OUT", "uno:7"]],
    )
    state = engine.initial_state()
    state["confirmed_pairs"] = [[f"decoy{n}:X", f"uno:{n}"] for n in range(2, 14) if n != 7]
    state["confirmed_pairs"].append(["other1:Y", "uno:7"])

    clip = engine._enter_step(fake_lesson, state, fake_lesson.data["steps"][0])
    assert "author's attention" in clip
    assert state["pin_remaps"] == []  # nothing resolved -- nothing persisted


def _write_synthetic_two_analog_lesson(folder):
    """A real on-disk lesson (not the FakeLesson stand-in) with two
    separate analog-pin connections, so the full engine flow — including
    _adjusted_code, which needs a real code_path() — can be exercised
    end to end. analog-read-serial itself only has one such connection."""
    (folder / "diagram.json").write_text('{"parts": [{"type": "wokwi-arduino-uno", "id": "uno"}], "connections": []}')
    (folder / "code.ino").write_text(
        "void loop() {\n"
        "  int ledReading = analogRead(A0);\n"
        "  int sensorReading = analogRead(A2);\n"
        "}\n"
    )
    data = {
        "id": "synthetic-two-analog", "title": "test", "code": "code.ino", "wokwi_diagram": "diagram.json",
        "steps": [
            {"id": "gather", "phase": "gather", "clip": "Gather your parts.", "items": []},
            {"id": "step-1", "phase": "build", "clip": "Wire the LED's signal leg to the Arduino's A0 pin.",
             "expected_nets": [["led1:A", "uno:A0"]], "hints": []},
            {"id": "step-2", "phase": "build", "clip": "Wire the sensor's output to the Arduino's A2 pin.",
             "expected_nets": [["sensor1:OUT", "uno:A2"]], "hints": []},
            {"id": "upload-code", "phase": "upload", "clip": "Copy this code and upload it.", "code": "code.ino"},
        ],
        "final_check": {"expected_nets": [["led1:A", "uno:A0"], ["sensor1:OUT", "uno:A2"]]},
    }
    return Lesson(data, folder)


def test_step_silently_remaps_around_an_earlier_deviation_no_accusation(library, tmp_path):
    """User request: if an earlier connection ends up on the pin a later
    step's own script wants, that later step should silently reassign
    itself to a free pin instead — no forced redo of the earlier step, no
    telling the learner they did something wrong, just an instruction
    that already reflects the correct current target. The code shown
    later must reflect both changes with zero cross-contamination."""
    lesson = _write_synthetic_two_analog_lesson(tmp_path)
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1

    # Step 1: LED wired to A2 instead of its own scripted A0 -- which
    # happens to be exactly what step-2's own script wants for the sensor.
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["led1:A", "uno:A2"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert any(a["type"] == "pin_substituted" for a in actions)
    step2_clip = next(a for a in actions if a["type"] == "play_clip")
    assert "A2" not in step2_clip["text"]  # silently NOT still telling the learner to use A2
    assert "A1" in step2_clip["text"]  # reassigned to the next free pin
    assert not any(a["type"].startswith("error") for a in actions)  # no accusation of any kind

    # Step 2: learner follows the (correctly adjusted) instruction exactly.
    state, actions = send(lesson, library, state, {"command": "sim", "detected_pairs": [["sensor1:OUT", "uno:A1"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not any(a["type"] == "feedback" for a in actions)  # a clean pass, matches the remap exactly
    assert state["phase"] == "upload"

    show_code = next(a for a in actions if a["type"] == "show_code")
    assert "analogRead(A2)" in show_code["code"]  # LED's actual pin
    assert "analogRead(A1)" in show_code["code"]  # sensor's reassigned pin
    assert "analogRead(A0)" not in show_code["code"]  # LED's original scripted pin, superseded
    assert show_code["code"].count("analogRead(A2)") == 1  # not accidentally duplicated/cross-contaminated
    assert show_code["code"].count("analogRead(A1)") == 1

    assert state["pin_substitutions"] == [{"original": "uno:A0", "actual": "uno:A2", "step": "step-1"}]
    assert state["pin_remaps"] == [{"original": "uno:A2", "actual": "uno:A1", "component": "sensor1", "step": "step-2"}]


def _write_synthetic_two_pin_sensor_lesson(folder):
    """A real on-disk lesson where ONE component (sensor1) has TWO
    independent substitutable digital connections (TRIG and ECHO) --
    mirroring a real HC-SR04, the first part this project hit with more
    than one substitutable pin per component. Regression coverage for a
    real bug: _adjusted_code used to dedup by bare component id, so a
    remap on the SECOND of a component's pins was silently dropped from
    the generated code (see the research log (in git history))."""
    (folder / "diagram.json").write_text('{"parts": [{"type": "wokwi-arduino-uno", "id": "uno"}], "connections": []}')
    (folder / "code.ino").write_text(
        "void setup() {\n"
        "  pinMode(9, OUTPUT);\n"
        "  pinMode(7, OUTPUT);\n"
        "  pinMode(6, INPUT);\n"
        "}\n"
    )
    data = {
        "id": "synthetic-two-pin-sensor", "title": "test", "code": "code.ino", "wokwi_diagram": "diagram.json",
        "steps": [
            {"id": "gather", "phase": "gather", "clip": "Gather your parts.", "items": []},
            {"id": "step-1", "phase": "build", "clip": "Wire the LED to pin 9.",
             "expected_nets": [["led1:A", "uno:9"]], "hints": []},
            {"id": "step-2", "phase": "build", "clip": "Wire the sensor's TRIG pin to pin 7.",
             "expected_nets": [["sensor1:TRIG", "uno:7"]], "hints": []},
            {"id": "step-3", "phase": "build", "clip": "Wire the sensor's ECHO pin to pin 6.",
             "expected_nets": [["sensor1:ECHO", "uno:6"]], "hints": []},
            {"id": "upload-code", "phase": "upload", "clip": "Copy this code and upload it.", "code": "code.ino"},
        ],
        "final_check": {"expected_nets": [
            ["led1:A", "uno:9"], ["sensor1:TRIG", "uno:7"], ["sensor1:ECHO", "uno:6"],
        ]},
    }
    return Lesson(data, folder)


def test_adjusted_code_updates_both_of_a_components_independent_pins(library, tmp_path):
    """Regression test for a real bug: a component with two independent
    substitutable connections (an HC-SR04's TRIG and ECHO) used to have
    only the FIRST one's remap/substitution reflected in the generated
    code — the second was silently skipped because the old dedup keyed
    on bare component id, and _final_pin_for_component couldn't tell the
    two pins' nets apart even if asked twice. Deviate LED onto ECHO's
    scripted pin, forcing ECHO (the SECOND of sensor1's two pins) to be
    the one that gets remapped, and confirm the generated code reflects
    it correctly, not silently left stale."""
    lesson = _write_synthetic_two_pin_sensor_lesson(tmp_path)
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1

    # LED wired to pin 6 instead of its own scripted 9 -- which is
    # exactly step-3's own scripted target for the sensor's ECHO pin.
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["led1:A", "uno:6"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert any(a["type"] == "pin_substituted" for a in actions)

    # step-2 (TRIG): follow exactly as scripted -- untouched by any of this.
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["sensor1:TRIG", "uno:7"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    step3_clip = next(a for a in actions if a["type"] == "play_clip")
    assert "pin 6" not in step3_clip["text"]  # ECHO's own step silently reassigned away from 6

    # step-3 (ECHO): follow the (correctly adjusted) instruction.
    remap = state["pin_remaps"][0]
    actual_echo_leg = remap["actual"].split(":", 1)[1]
    state, actions = send(lesson, library, state, {"command": "sim", "detected_pairs": [["sensor1:ECHO", f"uno:{actual_echo_leg}"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["phase"] == "upload"

    show_code = next(a for a in actions if a["type"] == "show_code")
    assert "pinMode(6, OUTPUT)" in show_code["code"]  # LED's actual pin
    assert "pinMode(7, OUTPUT)" in show_code["code"]  # TRIG, untouched
    assert f"pinMode({actual_echo_leg}, INPUT)" in show_code["code"]  # ECHO's reassigned pin -- the fix
    assert "pinMode(9, OUTPUT)" not in show_code["code"]  # LED's original scripted pin, superseded
    assert "pinMode(6, INPUT)" not in show_code["code"]  # ECHO's stale original -- must NOT survive


def test_hint_on_a_remapped_step_reflects_the_new_pin_not_the_stale_original(library, tmp_path):
    """Real gap found by direct testing: _enter_step already substitutes
    a remapped pin into the step's main instruction (play_clip), but the
    `hint` command's own text never went through the same substitution
    — asking for a hint on a step whose target got silently remapped
    away (see _compute_pin_remap) showed the stale, pre-remap pin
    number, contradicting the instruction the learner was just given."""
    (tmp_path / "diagram.json").write_text('{"parts": [{"type": "wokwi-arduino-uno", "id": "uno"}], "connections": []}')
    (tmp_path / "code.ino").write_text("void setup(){pinMode(5,OUTPUT);pinMode(7,OUTPUT);}\nvoid loop(){}\n")
    data = {
        "id": "hint-remap-demo", "title": "t", "code": "code.ino", "wokwi_diagram": "diagram.json",
        "steps": [
            {"id": "gather", "phase": "gather", "clip": "g", "items": []},
            {"id": "step-1", "phase": "build", "clip": "Wire LED to pin 5.",
             "expected_nets": [["led1:A", "uno:5"]], "hints": ["Look for the leg near pin 5."]},
            {"id": "step-2", "phase": "build", "clip": "Wire the buzzer to pin 7.",
             "expected_nets": [["bz1:2", "uno:7"]],
             "hints": ["Either orientation works — just make sure it lands on pin 7."]},
            {"id": "upload-code", "phase": "upload", "clip": "u", "code": "code.ino"},
        ],
        "final_check": {"expected_nets": [["led1:A", "uno:5"], ["bz1:2", "uno:7"]]},
    }
    lesson = Lesson(data, tmp_path)
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1

    # LED deviates onto pin 7 -- buzzer's own future scripted pin.
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["led1:A", "uno:7"]]})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-2, remapped
    remap = state["pin_remaps"][0]
    assert remap["original"] == "uno:7" and remap["actual"] != "uno:7"
    actual_leg = remap["actual"].split(":", 1)[1]

    state, actions = send(lesson, library, state, {"command": "hint"})
    hint = next(a for a in actions if a["type"] == "hint")
    assert f"pin {actual_leg}" in hint["text"]
    assert "pin 7" not in hint["text"]


def test_remap_reaches_any_later_step_not_just_the_immediate_next_one(library, tmp_path):
    """User request: the remap must reach ANY step later in the lesson
    that references the now-taken pin, not just the step immediately
    after the deviation. An unrelated step (a digital pin, no analog
    involvement at all) sits in between to prove the remap survives
    intervening steps rather than being a one-shot fix for 'the next
    step' specifically."""
    (tmp_path / "diagram.json").write_text('{"parts": [{"type": "wokwi-arduino-uno", "id": "uno"}], "connections": []}')
    (tmp_path / "code.ino").write_text("void loop() { analogRead(A0); analogRead(A2); }\n")
    data = {
        "id": "synthetic-remap-reach", "title": "test", "code": "code.ino", "wokwi_diagram": "diagram.json",
        "steps": [
            {"id": "gather", "phase": "gather", "clip": "Gather your parts.", "items": []},
            {"id": "step-1", "phase": "build", "clip": "Wire LED1 to the Arduino's A0 pin.",
             "expected_nets": [["led1:A", "uno:A0"]], "hints": []},
            {"id": "step-2", "phase": "build", "clip": "Wire the button to the Arduino's digital pin 2.",
             "expected_nets": [["button1:1", "uno:2"]], "hints": []},
            {"id": "step-5", "phase": "build", "clip": "Much later: wire the sensor's output to the Arduino's A2 pin.",
             "expected_nets": [["sensor1:OUT", "uno:A2"]], "hints": ["By default this wants A2."]},
            {"id": "upload-code", "phase": "upload", "clip": "Copy this code and upload it.", "code": "code.ino"},
        ],
        "final_check": {"expected_nets": [["led1:A", "uno:A0"], ["button1:1", "uno:2"], ["sensor1:OUT", "uno:A2"]]},
    }
    lesson = Lesson(data, tmp_path)

    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["led1:A", "uno:A2"]]})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-2 (LED now on A2)

    # step-2 has no analog pin at all -- must pass through completely unaffected
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["button1:1", "uno:2"]]})
    state, actions = send(lesson, library, state, {"command": "done"})  # -> step-5
    step5_clip = next(a for a in actions if a["type"] == "play_clip")
    assert "A2" not in step5_clip["text"]
    assert "A1" in step5_clip["text"]
    assert state["pin_remaps"] == [{"original": "uno:A2", "actual": "uno:A1", "component": "sensor1", "step": "step-5"}]

    # the `hint` command on that same step must reflect the same update,
    # not just the main instruction clip (user question: does the hint
    # update too, when a much-earlier step took the pin it defaults to?)
    state, actions = send(lesson, library, state, {"command": "hint"})
    hint = next(a for a in actions if a["type"] == "hint")
    assert "A1" in hint["text"]
    assert "A2" not in hint["text"]


def test_difficulty_command_asks_not_assumes_and_defaults_to_beginner(lesson, library):
    state = engine.initial_state()
    assert state["difficulty"] == "beginner"
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "difficulty", "level": "expert"})
    assert actions[0]["type"] == "error"
    assert state["difficulty"] == "beginner"
    state, actions = send(lesson, library, state, {"command": "difficulty", "level": "advanced"})
    assert actions[0] == {"type": "difficulty_set", "level": "advanced"}
    assert state["difficulty"] == "advanced"


def test_advanced_difficulty_shows_only_the_goal_and_hides_the_how_in_the_hints(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "difficulty", "level": "advanced"})
    state, actions = send(lesson, library, state, {"command": "done"})  # gather -> step-1b directly
    assert state["step_index"] == 2  # step-1a (index 1) was skipped
    assert actions[0]["text"] == lesson.step(2)["goal"]            # just the goal: "Connect one outer leg ... to GND."
    state, first = send(lesson, library, state, {"command": "hint"})
    state, second = send(lesson, library, state, {"command": "hint"})
    assert first[0]["text"] == lesson.step(1)["hints"][0]           # a nudge first
    assert second[0]["text"].startswith("Step by step:")            # then the full beginner instructions
    assert lesson.step(1)["clip"] in second[0]["text"] and lesson.step(2)["clip"] in second[0]["text"]


def test_a_lesson_without_goals_keeps_the_merged_advanced_clip(lesson, library):
    import copy
    bare = copy.copy(lesson)
    bare.steps = [{k: v for k, v in s.items() if k != "goal"} for s in lesson.steps]
    bare.step = lambda i: bare.steps[i] if 0 <= i < len(bare.steps) else None
    state = engine.initial_state()
    state, _ = send(bare, library, state, {"command": "start"})
    state, _ = send(bare, library, state, {"command": "difficulty", "level": "advanced"})
    state, actions = send(bare, library, state, {"command": "done"})
    assert actions[0]["text"] == bare.step(1)["clip"] + " " + bare.step(2)["clip"]


def test_advanced_difficulty_wiring_check_alone_is_still_fully_correct(lesson, library):
    """Skipping the landing checkpoint doesn't skip any actual
    verification — the wiring step's own net check still catches a wrong
    connection just as reliably as in beginner mode."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "difficulty", "level": "advanced"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": []})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    assert state["step_index"] == 2  # blocked, did not advance

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["pot1:GND", "bb2:6t.a"], ["uno:GND.1", "bb2:6t.c"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert not [a for a in actions if a["type"] == "feedback"]
    assert state["step_index"] == 3  # advanced to step-2b (no separate landing step left to skip)


def test_advanced_difficulty_hint_merges_the_skipped_landing_steps_hints(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "difficulty", "level": "advanced"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b (skipped step-1a)
    state, actions = send(lesson, library, state, {"command": "hint"})
    # step-1a's own first hint (the nudge), since it was merged in ahead of step-1b's own hints
    assert actions[0]["text"] == lesson.step(1)["hints"][0]


def test_advanced_difficulty_previous_skips_backward_over_landing_steps(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "difficulty", "level": "advanced"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b (index 2)
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["pot1:GND", "bb2:6t.a"], ["uno:GND.1", "bb2:6t.c"]]})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-2b (index 3)
    assert state["step_index"] == 3

    state, actions = send(lesson, library, state, {"command": "previous"})
    assert state["step_index"] == 2  # back to step-1b, not step-1a (1)
    assert actions[0]["step"] == "step-1b"


def test_advanced_difficulty_direct_wire_still_passes_cleanly(lesson, library):
    """The breadboard-bypass feature becomes moot (not needed) in advanced
    mode: with no landing checkpoint to reject a direct wire in the first
    place, a direct-to-Arduino connection just passes via the plain net
    check — no bypass action, no noise."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "difficulty", "level": "advanced"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["pot1:GND", "uno:GND.1"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert [a["type"] for a in actions] == ["play_clip"]
    assert state["step_index"] == 3


def test_advanced_difficulty_full_session_reaches_completion(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "difficulty", "level": "advanced"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["pot1:GND", "bb2:6t.a"], ["uno:GND.1", "bb2:6t.c"]]})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-2b
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["pot1:VCC", "bb2:7t.a"], ["uno:5V", "bb2:7t.c"]]})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-3b
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["pot1:SIG", "bb2:8t.a"], ["uno:A0", "bb2:8t.c"]]})
    state, actions = send(lesson, library, state, {"command": "done"})  # -> upload
    assert state["phase"] == "upload"
    state, _ = send(lesson, library, state, {"command": "done"})  # -> final_check
    final_pairs = [
        ["pot1:GND", "bb2:6t.a"], ["uno:GND.1", "bb2:6t.c"],
        ["pot1:VCC", "bb2:7t.a"], ["uno:5V", "bb2:7t.c"],
        ["pot1:SIG", "bb2:8t.a"], ["uno:A0", "bb2:8t.c"],
    ]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": final_pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["finished"] is True


def test_advanced_mode_final_check_still_catches_a_break_in_a_skipped_connection(lesson, library):
    """User request: verify that skipping a landing checkpoint (advanced
    difficulty) never means skipping VERIFICATION of that connection —
    final_check re-checks the whole circuit fresh regardless of which
    steps had a separate landing stop along the way."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "difficulty", "level": "advanced"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b (step-1a skipped)
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["pot1:GND", "bb2:6t.a"], ["uno:GND.1", "bb2:6t.c"]]})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-2b
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["pot1:VCC", "bb2:7t.a"], ["uno:5V", "bb2:7t.c"]]})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-3b
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["pot1:SIG", "bb2:8t.a"], ["uno:A0", "bb2:8t.c"]]})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> upload
    state, _ = send(lesson, library, state, {"command": "done"})  # -> final_check

    # GND (the connection whose landing was skipped) is secretly missing
    # from the final snapshot — everything else exactly as wired.
    broken_final = [
        ["pot1:VCC", "bb2:7t.a"], ["uno:5V", "bb2:7t.c"],
        ["pot1:SIG", "bb2:8t.a"], ["uno:A0", "bb2:8t.c"],
    ]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": broken_final})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    assert feedback["missing"] == [["pot1:GND", "uno:GND"]]
    assert state["finished"] is False


def test_advanced_mode_each_combined_step_still_classifies_and_tracks_immediately(lesson, library):
    """User request: confirm each substep (even the combined
    landing+wiring one, in advanced mode) still gets its own immediate
    pass/harmless/wrong classification and tracking — not a silent
    pass-through that only gets checked at the very end."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "difficulty", "level": "advanced"})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-1b

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": []})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    assert state["step_index"] == 2  # blocked, not silently advanced
    assert state["confirmed_pairs"] == []  # a wrong attempt tracks nothing

    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": [["pot1:VCC", "uno:GND.1"]]})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "harmless"
    assert state["step_index"] == 3  # advanced to step-2b
    assert state["confirmed_pairs"] == [["pot1:VCC", "uno:GND.1"]]


def _single_leg_landing_lesson(tmp_path):
    """A synthetic single-leg lesson for exercising the single-pin
    bypass path directly (see _run_landing_check's non-multi branch) --
    the multi-leg generalization (_multi_leg_bypass) has its own separate
    coverage below, using analog-read-serial's real combined landing
    step."""
    (tmp_path / "diagram.json").write_text(
        '{"parts": [{"type": "wokwi-arduino-uno", "id": "uno"}, {"type": "wokwi-potentiometer", "id": "pot1"}], "connections": []}'
    )
    (tmp_path / "code.ino").write_text("void setup(){}\nvoid loop(){}\n")
    data = {
        "id": "bypass-demo", "title": "t", "code": "code.ino", "wokwi_diagram": "diagram.json",
        "steps": [
            {"id": "gather", "phase": "gather", "clip": "g", "items": []},
            {"id": "step-1a", "phase": "build", "clip": "Land it.", "expected_landing": "pot1:GND", "hints": []},
            {"id": "step-1b", "phase": "build", "clip": "Wire it.", "expected_nets": [["pot1:GND", "uno:GND.1"]], "hints": []},
            {"id": "upload-code", "phase": "upload", "clip": "u", "code": "code.ino"},
        ],
        "final_check": {"expected_nets": [["pot1:GND", "uno:GND.1"]]},
    }
    return Lesson(data, tmp_path)


def test_landing_check_accepts_a_direct_wire_to_the_correct_pin_as_a_bypass(library, tmp_path):
    """User request: skipping the breadboard and wiring a leg straight to
    its correct final Arduino pin works electrically, so it should pass —
    but explained, warned about, and tracked, not silently identical to
    the taught (breadboard-routed) method."""
    lesson = _single_leg_landing_lesson(tmp_path)
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a
    pairs = [["pot1:GND", "uno:GND.1"]]  # correct final pin, no breadboard at all
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    bypass = next((a for a in actions if a["type"] == "breadboard_bypassed"), None)
    assert bypass is not None
    assert "pot1:GND" in bypass["message"]
    assert not [a for a in actions if a["type"] == "feedback"]  # a clean pass, not flagged wrong
    assert state["step_index"] == 2  # advanced
    assert state["breadboard_bypasses"] == [{"pin": "pot1:GND", "step": "step-1a"}]


def test_landing_check_bypass_still_applies_symmetric_swap_harmlessly(library, tmp_path):
    lesson = _single_leg_landing_lesson(tmp_path)
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a
    pairs = [["pot1:VCC", "uno:GND.1"]]  # swapped leg, still direct, no breadboard
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    assert any(a["type"] == "breadboard_bypassed" for a in actions)
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "harmless"
    assert state["step_index"] == 2


def test_multi_leg_landing_bypass_accepts_all_three_legs_wired_direct_no_breadboard(lesson, library):
    """User point: the underlying logic must not assume a breadboard is
    always the tool in use — a learner (or a future LLM-authored lesson)
    might wire a circuit directly, with no breadboard at all.
    _multi_leg_bypass generalizes the single-pin bypass above to the
    combined multi-leg landing step: each leg wired straight to its own
    correct final Arduino pin is accepted, tracked as a bypass, same as
    the single-pin case — not forced through the breadboard just because
    this component has several legs."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a (combined landing)
    pairs = [["pot1:GND", "uno:GND.1"], ["pot1:VCC", "uno:5V"], ["pot1:SIG", "uno:A0"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    bypasses = [a for a in actions if a["type"] == "breadboard_bypassed"]
    assert {a["message"].split(" ")[0] for a in bypasses} == {"pot1:GND", "pot1:VCC", "pot1:SIG"}
    assert not [a for a in actions if a["type"] == "feedback"]  # a clean pass
    assert state["step_index"] == 2  # advanced to step-1b
    assert state["breadboard_bypasses"] == [
        {"pin": "pot1:GND", "step": "step-1a"},
        {"pin": "pot1:VCC", "step": "step-1a"},
        {"pin": "pot1:SIG", "step": "step-1a"},
    ]


def test_multi_leg_landing_bypass_requires_every_leg_resolved_not_just_some(lesson, library):
    """A partial bypass isn't accepted: if only SOME legs are wired direct
    and the rest are genuinely missing, the whole check still fails —
    same all-or-nothing principle as any other landing requirement."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a
    pairs = [["pot1:GND", "uno:GND.1"], ["pot1:VCC", "uno:5V"]]  # SIG missing entirely
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    # All three still count as missing (not just SIG): a partial bypass
    # resolves nothing at all, same all-or-nothing principle as the rest
    # of this check.
    assert set(feedback["missing"]) == {"pot1:GND", "pot1:VCC", "pot1:SIG"}
    assert not [a for a in actions if a["type"] == "breadboard_bypassed"]
    assert state["step_index"] == 1  # blocked


def test_landing_check_direct_wire_to_the_wrong_pin_is_still_wrong_not_a_bypass(lesson, library):
    """A direct wire that doesn't even reach the right final net isn't a
    valid bypass — it's just wrong, same as it always was."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a
    pairs = [["pot1:GND", "uno:A0"]]  # wrong pin entirely, no breadboard
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    assert not [a for a in actions if a["type"] == "breadboard_bypassed"]
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    assert state["step_index"] == 1  # blocked
    assert state["breadboard_bypasses"] == []


def test_normal_breadboard_routed_landing_is_not_flagged_as_a_bypass(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a
    pairs = [["pot1:GND", "bb2:6t.a"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})

    assert not [a for a in actions if a["type"] == "breadboard_bypassed"]
    assert state["breadboard_bypasses"] == []


def test_wrong_feedback_includes_conflicts_when_a_leg_is_tied_to_something_else(lesson, library):
    """User request: a 'wrong' verdict should say *why* when a hole/pin
    conflict is the cause, not just list what's missing."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a landing
    # pot1:GND wired straight to A0 instead of the breadboard — not a
    # landing. VCC/SIG land correctly, isolating GND's own conflict.
    pairs = [
        ["pot1:GND", "uno:A0"],
        ["pot1:VCC", "bb2:7t.a"],
        ["pot1:SIG", "bb2:8t.a"],
    ]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    assert feedback["conflicts"] == {"pot1:GND": "uno:A0"}


def test_wrong_feedback_has_no_conflicts_when_simply_unconnected(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    state, _ = send(lesson, library, state, {"command": "sim", "label": "wrong"})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    assert feedback["conflicts"] == {}


def test_hint_warns_about_a_column_already_taken_by_a_sibling_leg(library, tmp_path):
    """User request: proactive 'that spot's taken' hint. Once pot1:GND has
    landed on a breadboard column, asking for a hint on a LATER, separate
    landing step for a sibling leg (VCC) should mention it, before the
    learner reuses that same column.

    Uses a synthetic lesson rather than analog-read-serial: with all
    three of the potentiometer's legs now checked together in one
    combined landing step (PARTS.md's legs_placed_together), this exact
    scenario — a SEPARATE, later landing step for a sibling leg of the
    SAME component — no longer occurs in any of this project's real
    lessons (a same-component self-short is now caught immediately, as
    part of that one combined check, instead). _occupied_column_note
    itself is still real, general-purpose code, so this keeps it
    covered against a lesson shape that could still produce it."""
    (tmp_path / "diagram.json").write_text(
        '{"parts": ['
        '{"type": "wokwi-arduino-uno", "id": "uno"}, '
        '{"type": "wokwi-potentiometer", "id": "pot1"}, '
        '{"type": "wokwi-breadboard-mini", "id": "bb2"}'
        '], "connections": []}'
    )
    (tmp_path / "code.ino").write_text("void setup(){}\nvoid loop(){}\n")
    data = {
        "id": "sibling-leg-demo", "title": "t", "code": "code.ino", "wokwi_diagram": "diagram.json",
        "steps": [
            {"id": "gather", "phase": "gather", "clip": "g", "items": []},
            {"id": "step-1a", "phase": "build", "clip": "Land GND.", "expected_landing": "pot1:GND", "hints": []},
            {"id": "step-1b", "phase": "build", "clip": "Wire GND.", "expected_nets": [["pot1:GND", "uno:GND.1"]], "hints": []},
            {"id": "step-2a", "phase": "build", "clip": "Land VCC.", "expected_landing": "pot1:VCC", "hints": ["h"]},
            {"id": "upload-code", "phase": "upload", "clip": "u", "code": "code.ino"},
        ],
        "final_check": {"expected_nets": [["pot1:GND", "uno:GND.1"], ["pot1:VCC", "uno:5V"]]},
    }
    lesson = Lesson(data, tmp_path)

    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a (GND landing)
    pairs = [["pot1:GND", "bb2:6t.a"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1b (GND wiring)
    pairs = [["pot1:GND", "bb2:6t.a"], ["uno:GND.1", "bb2:6t.c"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, _ = send(lesson, library, state, {"command": "done"})  # -> step-2a (VCC landing)
    assert state["step_index"] == 3

    state, actions = send(lesson, library, state, {"command": "hint"})
    assert "bb2:6t" in actions[0]["text"]
    assert "GND" in actions[0]["text"]


def test_hint_has_no_taken_column_note_when_nothing_confirmed_yet(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a, nothing confirmed yet
    state, actions = send(lesson, library, state, {"command": "hint"})
    assert "Heads up" not in actions[0]["text"]


def test_sim_with_real_hole_pairs_lets_the_actual_checker_decide(lesson, library):
    """`sim` can now be given literal hole-level pairs instead of a canned
    label (COMMANDS.md) — the real checker determines pass/harmless/wrong
    from them, exactly as it would for genuine detected_pairs on `done`."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # step-1a (GND landing)

    # Genuinely correct: all three legs actually land on breadboard holes.
    pairs = [["pot1:GND", "bb2:6b.a"], ["pot1:VCC", "bb2:7b.a"], ["pot1:SIG", "bb2:8t.a"]]
    state, actions = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    assert actions[0] == {"type": "sim_set", "pairs": pairs}
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["step_index"] == 2  # advanced to step-1b — no canned label was ever picked
    assert not [a for a in actions if a.get("verdict") == "wrong"]

    # step-1b: wire the same strip to the wrong Arduino pin (A0, not GND) —
    # the real net check must catch this even though nothing here said "wrong".
    pairs = [["pot1:GND", "bb2:6b.a"], ["uno:A0", "bb2:6b.c"]]
    state, _ = send(lesson, library, state, {"command": "sim", "detected_pairs": pairs})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert state["step_index"] == 2  # did not advance
    assert actions[-1]["type"] == "feedback"
    assert actions[-1]["verdict"] == "wrong"


def test_sim_with_malformed_raw_pairs_errors_without_crashing(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    state, actions = send(lesson, library, state, {"command": "sim", "detected_pairs": "not a list"})
    assert actions[0]["type"] == "error"
    assert state["mock_result"] is None  # unchanged, not silently accepted


def test_sim_rejected_outside_build_and_final_check(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})  # gather phase
    state, actions = send(lesson, library, state, {"command": "sim", "label": "correct"})
    assert actions[0]["type"] == "error"


def test_tools_lists_only_this_lessons_tools_not_the_whole_library(lesson, library):
    """Regression test: `tools` used to dump the entire global library
    (parts and tools both), rather than the current lesson's tools_used.
    analog-read-serial genuinely needs none, so it should say so, not list
    unrelated items like potentiometer-10k (a part) or every tool ever
    authored."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "tools"})
    assert actions[0]["ids"] == []
    assert actions[0]["kind"] == "tools"
    assert "message" in actions[0]


def test_parts_lists_only_this_lessons_parts(lesson, library):
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "parts"})
    assert actions[0]["kind"] == "parts"
    assert set(actions[0]["ids"]) == {"arduino-uno", "usb-cable", "breadboard", "potentiometer-10k", "jumper-wire"}
    assert "led" not in actions[0]["ids"]  # not used by this lesson, must not leak in


@pytest.mark.parametrize("bad_event", [None, "just a string", 42, [], {}, ["a", "list"]])
def test_handle_event_rejects_non_dict_or_commandless_events_without_crashing(lesson, library, bad_event):
    """Found by a 100-session chaos test with deliberately malformed input.
    Matters beyond robustness-for-its-own-sake: PLAN.md Phase 6 will
    eventually assemble events from LLM output, and a misbehaving model
    could return anything — this must degrade to an error action, never
    an exception."""
    state = engine.initial_state()
    state, actions = send(lesson, library, state, bad_event)
    assert actions[0]["type"] == "error"


@pytest.mark.parametrize("bad_detected", [
    {"nested": "dict"}, 42, "not a list", ["a", "list", "of", "strings"],
    [{"a": 1}], [["only-one-element"]], [[1, 2]], [["a", "b", "c"]],
])
def test_malformed_detected_pairs_does_not_crash_the_checker(lesson, library, bad_detected):
    """Found by chaos testing: build_nets unpacked detected_pairs items
    with `for a, b in pairs` and crashed on anything not shaped like a
    list of 2-string pairs — e.g. iterating a dict yields its keys, and a
    multi-character key unpacks into 'too many values'. Same Phase 6
    concern as the top-level event-shape guard: this can eventually come
    from LLM output, which could send anything."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # into step-1
    state, actions = send(lesson, library, state, {"command": "done", "detected_pairs": bad_detected})
    assert any(a["type"] == "error" for a in actions)


@pytest.mark.parametrize("bad_item", [{"nested": "dict"}, 123, ["a", "list"], 3.14])
def test_help_with_a_non_string_item_does_not_crash(lesson, library, bad_item):
    """Found by the same chaos test — library.get() assumed its argument
    was always a string and crashed calling .lower() on anything else."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "help", "item": bad_item})
    assert actions[0]["type"] == "error"


def test_help_flags_an_item_not_used_by_this_lesson(lesson, library):
    """analog-read-serial's tools_used is empty, so any tool is out of
    scope — help should still work, but note it isn't actually needed."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, actions = send(lesson, library, state, {"command": "help", "item": "stripper"})
    assert actions[0]["in_scope"] is False

    state, actions = send(lesson, library, state, {"command": "help", "item": "potentiometer"})
    assert actions[0]["in_scope"] is True  # this lesson's actual part


def test_many_consistent_swaps_still_resolve_harmless_end_to_end(lesson, library):
    """A learner who swaps the potentiometer's power pins on every relevant
    step (a consistent, whole-circuit reversal) should read as harmless
    throughout, including at final_check — not wrong, and not silently
    identical to an exact match either."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    # step-1a (combined landing): "swapped" isn't meaningful for the
    # multi-leg case (see _check_multi_leg_landing) -- all three real
    # legs land normally here; the swap is exercised at each wiring step.
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, _ = send(lesson, library, state, {"command": "done"})
    for _ in range(3):  # step-1b, step-2b, step-3b
        state, _ = send(lesson, library, state, {"command": "sim", "label": "swapped"})
        state, _ = send(lesson, library, state, {"command": "done"})
    state, _ = send(lesson, library, state, {"command": "done"})  # upload -> final_check
    assert state["phase"] == "final_check"

    state, _ = send(lesson, library, state, {"command": "sim", "label": "swapped"})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "harmless"
    assert state["finished"] is True


def test_final_check_never_trusts_earlier_confirmations_always_rechecks_fresh(lesson, library):
    """Safety property: every build step passing 'correct' must not let
    final_check skip its own verification. Physical wiring can be bumped
    loose between steps — trusting history instead of rechecking would be
    a real gap, not just an implementation detail."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})
    for _ in range(4):  # step-1a (combined landing), step-1b, step-2b, step-3b
        state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
        state, actions = send(lesson, library, state, {"command": "done"})
        assert not [a for a in actions if a.get("verdict") == "wrong"]
    state, _ = send(lesson, library, state, {"command": "done"})  # upload -> final_check

    # simulate something coming loose after every step already confirmed correct
    state, _ = send(lesson, library, state, {"command": "sim", "label": "wrong"})
    state, actions = send(lesson, library, state, {"command": "done"})
    feedback = next(a for a in actions if a["type"] == "feedback")
    assert feedback["verdict"] == "wrong"
    assert state["finished"] is False


def test_confirmed_pairs_track_what_actually_happened_not_the_script(lesson, library):
    """PLAN.md Phase 6: if a learner deviates (here, the potentiometer's
    power pins swapped — a harmless deviation), a later step needs to point
    at where things *actually* ended up, not the scripted assumption.
    confirmed_pairs/find_confirmed_pin is what makes that possible — now
    across two confirmed facts per net (the landing half, then the wiring
    half), with the most recent one winning once both exist.

    "swapped" isn't meaningful for the combined multi-leg landing step
    itself (see _check_multi_leg_landing) — all three real legs land
    normally there; the swap this test cares about happens at the wiring
    half (step-1b), same underlying confirmed_pairs mechanism."""
    state = engine.initial_state()
    state, _ = send(lesson, library, state, {"command": "start"})
    state, _ = send(lesson, library, state, {"command": "done"})  # into step-1a (combined landing)
    state, _ = send(lesson, library, state, {"command": "sim", "label": "correct"})
    state, actions = send(lesson, library, state, {"command": "done"})  # -> step-1b
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    assert state["confirmed_pairs"] == [
        ["pot1:GND", "bb2:1t.a"], ["pot1:VCC", "bb2:2t.a"], ["pot1:SIG", "bb2:3t.a"],
    ]

    # The script assumed pot1:GND wires to uno:GND.1, but the swapped pair
    # pot1:VCC -> uno:GND.1 (its declared symmetric counterpart) is what's
    # actually confirmed.
    state, _ = send(lesson, library, state, {"command": "sim", "label": "swapped"})
    state, actions = send(lesson, library, state, {"command": "done"})
    assert actions[0]["verdict"] == "harmless"

    # Most-recent-wins: VCC's landing fact is now superseded by its own
    # wiring fact; GND's landing fact is untouched, since the swap never
    # actually confirmed anything about GND.
    assert engine.find_confirmed_pin(state, "pot1", "VCC") == "uno:GND.1"
    assert engine.find_confirmed_pin(state, "pot1", "GND") == "bb2:1t.a"
    assert engine.find_confirmed_pin(state, "pot1", "SIG") == "bb2:3t.a"


def test_replay_reproduces_the_same_final_state(lesson, library):
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "session.jsonl"
        log = EventLog(log_path)
        events = [
            {"command": "start"},
            {"command": "done"},  # gather -> step-1a
            {"command": "sim", "label": "correct"}, {"command": "done"},  # step-1a -> step-1b
            {"command": "sim", "label": "swapped"}, {"command": "done"},  # step-1b -> step-2a
            {"command": "sim", "label": "correct"}, {"command": "done"},  # step-2a -> step-2b
            {"command": "sim", "label": "correct"}, {"command": "done"},  # step-2b -> step-3a
            {"command": "sim", "label": "swapped"}, {"command": "done"},  # step-3a -> step-3b
            {"command": "sim", "label": "correct"}, {"command": "done"},  # step-3b -> upload
            {"command": "done"},  # upload -> final_check
            {"command": "sim", "label": "correct"}, {"command": "done"},  # final_check -> finished
        ]
        state = engine.initial_state()
        for event in events:
            log.append(event)
            state, _ = engine.handle_event(lesson, library, state, event)

        replayed_state = replay(lesson, library, log_path)
        assert replayed_state == state
        assert replayed_state["finished"] is True


def test_fuzz_random_walk_never_crashes(lesson, library):
    """No (phase, command) combination should ever raise — the primary
    property PLAN.md's fuzz test asks for. Uses every command, including
    ones that are illegal in a given phase (e.g. `sim` during gather),
    specifically to confirm those are handled as an `error` action, not
    an exception."""
    import random

    commands = ["start", "done", "previous", "repeat", "hint", "tools",
                "help potentiometer", "help nonexistent-item",
                "sim correct", "sim wrong", "sim swapped", "sim"]
    rng = random.Random(42)
    for _ in range(50):
        state = engine.initial_state()
        for _ in range(80):
            raw = rng.choice(commands)
            parts = raw.split(maxsplit=1)
            event = {"command": parts[0]}
            if parts[0] == "help" and len(parts) > 1:
                event["item"] = parts[1]
            elif parts[0] == "sim" and len(parts) > 1:
                event["label"] = parts[1]
            state, actions = engine.handle_event(lesson, library, state, event)  # must not raise
            assert isinstance(actions, list) and actions


def test_done_heavy_walk_can_reach_completion(lesson, library):
    """Separate from the crash fuzz test: a walk weighted toward the
    sequence a cooperative learner would actually produce (mostly `sim
    correct` + `done`, occasionally a distraction command) should reach
    `finished` — proving there's no permanent dead end, not just that nothing
    crashes."""
    import random

    commands = (["done", "sim correct"] * 5) + ["previous", "repeat", "hint", "tools"]
    rng = random.Random(7)
    for _ in range(10):
        state = engine.initial_state()
        state, _ = engine.handle_event(lesson, library, state, {"command": "start"})
        for _ in range(60):
            raw = rng.choice(commands)
            event = {"command": raw.split()[0]}
            if raw.startswith("sim"):
                event["label"] = raw.split()[1]
            state, _ = engine.handle_event(lesson, library, state, event)
            if state["finished"]:
                return  # reached completion at least once — test passes
    assert False, "a cooperative random walk should reach completion within budget"
