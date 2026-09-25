"""Explore every learner run-flow of a lesson and check that tracking and
code always hold (PLAN.md Phase 5b).

The LLM is called once — it produces the circuit (diagram.json), the
sketch and the steps. Everything after that is algorithm: this module
enumerates the ways a real learner can build that circuit and plays each
one through the real engine:

- pins:        every free pin of the same kind for every signal pin the
               circuit uses (13 → 2..12, A0 → A1..A5), not one sample;
- orientation: every interchangeable part straight or turned round;
- timing:      built step by step, or the whole board built before the
               first check;
- mistakes:    none, or one mistake at any build step (the step not done,
               or its wire on the wrong kind of pin), then fixed.

For every flow it checks the invariants a correct lesson must keep:
  finishes        — the lesson completes; "wrong" appears only where a
                    mistake was injected, and never advances past it;
  substitutions   — every moved pin is recorded (original → actual) and
                    announced once; nothing is recorded when nothing moved;
  orientation     — every turned part is tracked "swapped", every other
                    symmetric part "straight", and a swap is flagged
                    harmless;
  tracking        — the nets the engine confirmed equal the physical board;
  code            — the sketch shown equals the original with ONLY the
                    moved pins rewritten (rewrite_pins_in_code), and drives
                    the learner's pins in the same modes;
  behaviour       — the learner's circuit with that code behaves like the
                    lesson's own circuit (LED states, input readings).
"""
import itertools
import re

from . import checker, engine, physics
from .library import load_library
from .scenarios import Board, Session, _is_wrong

MISTAKES = ("forgot", "wrong_pin")


def _board_domains(board):
    board_type = next((p.get("type") for p in board.parts if p["id"] in board.board_ids), None)
    card = engine._board_card(board_type, board.library) if board_type else None
    return (card or {}).get("pin_domains", {"digital": [str(n) for n in range(2, 14)],
                                             "analog": [f"A{n}" for n in range(6)]})


def pin_choices(board):
    """{used signal pin: [every pin it could move to]} — same kind, not
    used by anything else, never the USB serial pins."""
    domains = _board_domains(board)
    used = sorted({p.split(":", 1)[1] for c in board.connections for p in c
                   if p.split(":", 1)[0] in board.board_ids})
    choices = {}
    for pin in used:
        pool = next((d for d in domains.values() if pin in d), None)
        if pool:
            choices[pin] = [pin] + [c for c in pool if c not in used and c not in ("0", "1")]
    return choices


def enumerate_flows(lesson, library=None, exhaustive_mistakes=False, mode="full"):
    """Yield flow dicts: {"pins": {old: new}, "turned": [ids], "ahead": bool,
    "mistakes": {build_step_index: kind}}. Pin moves are combined across
    pins only as "move each pin anywhere" per pin (the full product for one
    or two signal pins; for more, each pin varies while the others stay).

    mode="smart" plays a covering sample instead of the full product — each
    choice varied on its own, plus everything changed at once — so the count
    grows by adding cases, not multiplying them (tens of flows, not
    thousands). The hosted app uses it; the full product runs locally."""
    library = library or load_library()
    board = Board(lesson, library)
    choices = pin_choices(board)
    sym = engine._symmetric_map(lesson, library)
    sym_parts = sorted(c for c in sym if any(p.split(":", 1)[0] == c for conn in board.connections for p in conn))
    if mode == "smart":
        yield from _smart_flows(choices, sym_parts, board.build_steps)
        return

    if len(choices) <= 2:
        # every combination — except two signals landing on the same pin, which no one can wire
        pin_sets = [dict(zip(choices, combo)) for combo in itertools.product(*choices.values())
                    if len(set(combo)) == len(combo)]
    else:
        pin_sets = [{k: k for k in choices}]
        for pin, options in choices.items():
            pin_sets += [{**{k: k for k in choices}, pin: o} for o in options[1:]]
    orientations = [list(c) for n in range(len(sym_parts) + 1) for c in itertools.combinations(sym_parts, n)]
    steps = board.build_steps
    if exhaustive_mistakes:
        mistake_sets = [dict((s, k) for s, k in zip(steps, combo) if k)
                        for combo in itertools.product((None,) + MISTAKES, repeat=len(steps))]
    else:
        mistake_sets = [{}] + [{s: k} for s in steps for k in MISTAKES]

    for pins, turned, ahead, mistakes in itertools.product(pin_sets, orientations, (False, True), mistake_sets):
        if ahead and mistakes:
            continue   # a mistake on a fully built board is the same as the step-by-step case
        yield {"pins": {k: v for k, v in pins.items() if k != v}, "turned": turned, "ahead": ahead, "mistakes": mistakes}


def _smart_flows(choices, sym_parts, steps):
    """The covering sample: the plain build; every alternative for each pin
    (the others kept); every pin moved at once; each symmetric part turned
    alone, and all of them; the board built ahead (plain, and with every
    change at once); and every mistake at every step."""
    # every pin moved at once — each to its own free pin (two can't share one)
    moved_all, taken = {}, set()
    for pin, options in choices.items():
        free = next((o for o in options[1:] if o not in taken), None)
        if free:
            moved_all[pin] = free; taken.add(free)
    flows = [{"pins": {}, "turned": [], "ahead": False, "mistakes": {}}]
    flows += [{"pins": {pin: o}, "turned": [], "ahead": False, "mistakes": {}} for pin, options in choices.items() for o in options[1:]]
    if len(moved_all) > 1:
        flows.append({"pins": moved_all, "turned": [], "ahead": False, "mistakes": {}})
    flows += [{"pins": {}, "turned": [c], "ahead": False, "mistakes": {}} for c in sym_parts]
    if len(sym_parts) > 1:
        flows.append({"pins": {}, "turned": list(sym_parts), "ahead": False, "mistakes": {}})
    flows.append({"pins": {}, "turned": [], "ahead": True, "mistakes": {}})
    if moved_all or sym_parts:
        flows.append({"pins": moved_all, "turned": list(sym_parts), "ahead": True, "mistakes": {}})
    flows += [{"pins": {}, "turned": [], "ahead": False, "mistakes": {s: k}} for s in steps for k in MISTAKES]
    yield from flows


def _physical(board, lesson, library, flow):
    """The learner's real connections for this flow."""
    sym = engine._symmetric_map(lesson, library)
    out = []
    for conn in board.connections:
        new = []
        for p in conn:
            comp, leg = p.split(":", 1)
            if comp in board.board_ids and leg in flow["pins"]:
                p = f"{comp}:{flow['pins'][leg]}"
            elif comp in flow["turned"]:
                p = checker._swap_pin(p, comp, sym[comp])
            new.append(p)
        out.append(new)
    return out


def _mistake_board(board, physical, step_index, kind):
    earlier = [j for j in board.build_steps if j < step_index]
    if kind == "forgot":
        prev = board.upto(earlier[-1], physical) if earlier else []
        return prev if prev != board.upto(step_index, physical) else None
    step = board.lesson.step(step_index)
    board_pins = {p for pair in step.get("expected_nets", []) for p in pair if p.split(":", 1)[0] in board.board_ids}
    if not board_pins:
        return None
    current = board.upto(step_index, physical)
    new_conns = [c for c in current if c not in (board.upto(earlier[-1], physical) if earlier else [])]
    for conn in new_conns:
        for i, p in enumerate(conn):
            if p.split(":", 1)[0] in board.board_ids:
                wrong = "GND.1" if not p.split(":", 1)[1].startswith("GND") else "5V"
                bad = [list(c) for c in current]
                bad[current.index(conn)][i] = f"{p.split(':', 1)[0]}:{wrong}"
                return bad
    return None


def _nets(pairs, board):
    return {n for n in (frozenset(checker._drop_connectors(n, board.connectors))
                        for n in checker.build_nets(pairs, board.alias)) if len(n) > 1}


def _non_pin_fingerprint(code):
    """Everything in a sketch that is NOT a pin: calls to non-pin functions
    with their arguments (delay, Serial.begin, …), array sizes and brace
    initialisers, comments removed. An independent oracle: a pin rewrite
    must leave this byte-for-byte unchanged, whatever rewriter is used."""
    code = engine._COMMENT_RE.sub("", code)
    calls = [m.group(0) for m in re.finditer(r"\b(\w+(?:\.\w+)?)\s*\(([^()]*)\)", code)
             if m.group(1).split(".")[-1] not in engine.PIN_FUNCTION_ARGS]
    return calls + re.findall(r"\[\s*\d+\s*\]", code) + re.findall(r"=\s*\{[^{}]*\}", code)


def run_flow(lesson, library, board, flow):
    """Play one flow; return a list of violated invariants (empty = holds)."""
    physical = _physical(board, lesson, library, flow)
    problems = []
    s = Session(lesson, library)
    for _ in range(4 * len(lesson.steps) + 4):
        s.advance_non_build()
        if s.state["finished"]:
            break
        i = s.index
        if s.phase == "build" and i in flow["mistakes"]:
            bad = _mistake_board(board, physical, i, flow["mistakes"][i])
            if bad is not None:
                actions = s.send({"command": "done", "detected_pairs": bad})
                if not _is_wrong(actions) or s.index != i:
                    problems.append(f"finishes: step '{lesson.step(i)['id']}' accepted mistake '{flow['mistakes'][i]}'")
                    return problems
        present = physical if (flow["ahead"] or s.phase == "final_check") else board.upto(i, physical)
        actions = s.send({"command": "done", "detected_pairs": present})
        if _is_wrong(actions):
            detail = next((a.get("message") for a in actions if a["type"] in ("substitution_refused", "physics_hazard")), "")
            where = lesson.step(i)["id"] if s.phase != "final_check" else "final_check"
            problems.append(f"finishes: '{where}' said wrong on correct wiring. {detail}".strip())
            return problems
    state = s.state
    if not state["finished"]:
        return ["finishes: never completed"]

    # substitutions
    board_id = next(iter(sorted(board.board_ids)), "uno")
    recorded = {(x["original"].split(":", 1)[1], x["actual"].split(":", 1)[1]) for x in state["pin_substitutions"]}
    expected = set(flow["pins"].items())
    if recorded != expected:
        problems.append(f"substitutions: recorded {sorted(recorded)} but the learner moved {sorted(expected)}")
    told = sum(1 for _, acts in s.log for a in acts if a["type"] == "pin_substituted")
    if told != len(expected):
        problems.append(f"substitutions: announced {told} times for {len(expected)} moved pin(s)")

    # orientation
    sym = engine._symmetric_map(lesson, library)
    for comp in sorted(set(sym) & set(state.get("orientations", {}))):
        want = "swapped" if comp in flow["turned"] else "straight"
        if state["orientations"][comp] != want:
            problems.append(f"orientation: {comp} tracked {state['orientations'][comp]}, physically {want}")
    harmless = any(a.get("verdict") == "harmless" for _, acts in s.log for a in acts)
    if flow["turned"] and not harmless:
        problems.append("orientation: a turned part was never flagged harmless")

    # tracking
    if _nets(state["confirmed_pairs"], board) != _nets(physical, board):
        problems.append("tracking: confirmed nets differ from the physical board")

    # code
    original = lesson.code_text()
    shown = engine._adjusted_code(lesson, state)
    moves = list(flow["pins"].items())
    led_builtin = engine._board_led_builtin(board.parts)
    moves += [("LED_BUILTIN", new) for old, new in flow["pins"].items() if old == led_builtin]
    if shown != engine.rewrite_pins_in_code(original, moves):
        problems.append("code: the shown sketch changed more (or less) than the moved pins")
    if _non_pin_fingerprint(shown) != _non_pin_fingerprint(original):
        problems.append("code: something that isn't a pin changed (a delay, a baud rate, an array size…)")
    before = physics.pin_modes_from_code(original)
    after = physics.pin_modes_from_code(shown)
    want_after = {flow["pins"].get(k, k): v for k, v in before.items()}
    if after != want_after:
        problems.append(f"code: drives {after}, the learner's circuit needs {want_after}")

    # behaviour
    parts = board.parts
    design = physics.analyze(board.connections, parts, original, library)
    learner = physics.analyze(physical, parts, shown, library)
    by_label = {x["label"]: x for x in design["scenarios"]}
    for scen in learner["scenarios"]:
        ref = by_label.get(scen["label"])
        if not ref:
            continue
        for led, info in ref["leds"].items():
            if (scen["leds"].get(led, {}).get("state") == "off") != (info["state"] == "off"):
                problems.append(f"behaviour: {led} {'dark' if info['state'] != 'off' else 'lit'} ({scen['label']})")
        if sorted(str(p.get("reading")) for p in ref["pins"].values() if "reading" in p) != \
                sorted(str(p.get("reading")) for p in scen["pins"].values() if "reading" in p):
            problems.append(f"behaviour: input reading differs ({scen['label']})")
    return problems


def explore(lesson, library=None, exhaustive_mistakes=False, stop_after=None, mode="full"):
    """Play every flow (or the smart sample). Returns {"flows": n, "failures": [(flow, problems)]}."""
    library = library or load_library()
    board = Board(lesson, library)
    failures, n = [], 0
    for flow in enumerate_flows(lesson, library, exhaustive_mistakes, mode=mode):
        n += 1
        problems = run_flow(lesson, library, board, flow)
        if problems:
            failures.append((flow, problems))
            if stop_after and len(failures) >= stop_after:
                break
    return {"flows": n, "failures": failures}
