"""Stand-in for the Phase 4 vision pipeline (PLAN.md) — not a test helper
bolted on the side, but the actual interface boundary Phase 4 will
eventually implement for real.

`mimic_detection()` produces data in the *exact* shape a real detection
system has to produce: a flat list of [pin, pin] pairs, hole-level,
routed through whichever breadboard strip a wire actually occupies —
never pre-reduced to "component connects to component" the way `sim`'s
shortcut is. Everything downstream (checker.check, engine._run_check)
already consumes exactly this shape. When Phase 4 exists, it becomes a
second implementation of the same contract — nothing that calls this
module today has to change, only what gets called does.
"""
import random


def mimic_detection(expected_pairs, mode, symmetric_map=None, breadboard_id="bb2", rng=None):
    """Turn component-pin expected_pairs into a realistic hole-level
    detected_pairs list, as if a real vision system read actual breadboard
    connections.

    mode:
      - "correct"  — realizes expected_pairs exactly, each net routed
        through a freshly, randomly chosen breadboard strip/hole (proving
        strip choice never matters, not just for one hand-picked example).
      - "harmless" — realizes a symmetric-pin-swapped variant instead (if
        the component has one declared; otherwise identical to "correct",
        since there's nothing to swap).
      - "wrong"    — deliberately breaks every net: each pair's two ends
        land on two different, disjoint strips, so the expected connection
        never actually forms.
    """
    rng = rng or random.Random()
    symmetric_map = symmetric_map or {}

    if mode == "harmless":
        variants = _symmetric_variants(expected_pairs, symmetric_map)
        pairs = variants[1] if len(variants) > 1 else expected_pairs
    else:
        pairs = expected_pairs

    used_strips = set()

    def fresh_strip():
        while True:
            strip = f"{rng.randint(1, 30)}{rng.choice('tb')}"
            if strip not in used_strips:
                used_strips.add(strip)
                return strip

    def hole(strip):
        # Real breadboards split each row at the center gap into two
        # disconnected halves — confirmed from the user's own Wokwi
        # exports: the "t" side only ever uses letters a-e, the "b" side
        # only f-j. This doesn't affect correctness (the checker only ever
        # folds on the first ".", never looks at which letter it is — see
        # test_different_row_on_the_breadboard_actually_breaks_the_connection),
        # but generating a letter from the wrong half would be data this
        # module could never actually see from a real board. The exact
        # letter range is itself a board-model detail (may differ for
        # other breadboard variants), not a universal constant.
        letters = "abcde" if strip.endswith("t") else "fghij"
        return f"{strip}.{rng.choice(letters)}"

    detected = []
    for a, b in pairs:
        if mode == "wrong":
            strip_a, strip_b = fresh_strip(), fresh_strip()  # disjoint on purpose
        else:
            strip_a = strip_b = fresh_strip()  # same strip == same net
        detected.append([a, f"{breadboard_id}:{hole(strip_a)}"])
        detected.append([b, f"{breadboard_id}:{hole(strip_b)}"])
    return detected


def _symmetric_variants(pairs, symmetric_map):
    """Local copy of checker.symmetric_variants' first-level swap — kept
    tiny and dependency-free here since this module models the *input*
    side (what a sensor would see), not the comparison logic itself."""
    from . import checker
    return checker.symmetric_variants(pairs, symmetric_map)
