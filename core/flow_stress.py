"""The merged stress test: every kind of learner run-flow the engine's own
hand-written tests cover, generated generically for ANY lesson —
hand-made or AI-generated (PLAN.md Phase 5b).

core/flow_explorer.py enumerates pins × orientation × timing × one mistake.
This module adds the dimensions the engine's own exhaustive tests exercise
by hand, and mixes them all:

  board        Uno, or the lesson translated to a Mega / Nano
  pins         every free same-kind pin for each signal pin
  mind         the learner moves a signal pin AGAIN at a later step
  turned       each interchangeable part straight or turned round
  ahead        built step by step, or everything before the first check
  gnd          every ground wire on GND.1 / GND.2 / GND.3
  sibling      a wire landing on the other leg of an internal group
  rows         wire ends in a different hole of the same column-half
  shift        the whole layout moved along the breadboard
  rails        5V/GND through the power rails or direct (where rails exist)
  bypass       a leg wired straight to its Arduino pin, no breadboard
  mistakes     several per flow: forgot a step, wire on the wrong kind of
               pin, a wire one column off, an accidental short jumper, a
               one-object part with two legs in one column-half, an LED in
               backwards, a wire an EARLIER step confirmed coming loose. A
               mistake stays on the board until the engine says "wrong",
               then the learner fixes it; a loose wire must be named as
               lost at the very next check.
  session      ask every hint; go back a step and re-check

A full product is millions of flows, so `plan_flows` builds a pairwise
covering set (every pair of values of every two dimensions appears in at
least one flow) plus a fixed-seed random sample of full combinations.
Each flow is checked against the invariants in `check_flow`.
"""
import copy
import itertools
import random
import re

from . import board_translate, checker, engine, physics
from .flow_explorer import _nets, _non_pin_fingerprint, pin_choices
from .library import load_library
from .scenarios import Board, Session, _is_wrong, loose_removal

BB_COLUMNS = {"wokwi-breadboard": 63, "wokwi-breadboard-half": 30, "wokwi-breadboard-mini": 17}
MISTAKE_KINDS = ("forgot", "wrong_kind", "off_by_one", "short_jumper", "leg_self_short", "reversed", "loose")
# Everything except "forgot" stays on the board until the engine catches it:
# a step only checks its own connection (e.g. a resistor landing is
# satisfied by the OTHER, interchangeable leg), so a mistake elsewhere may
# rightly be caught a step later — but always before the lesson finishes.
PERSISTENT = {"wrong_kind", "off_by_one", "short_jumper", "leg_self_short", "reversed"}


# ---------------------------------------------------------------------------
# Dimensions and the plan of flows
# ---------------------------------------------------------------------------

def _variants_for(lesson, library, board_name):
    b = Board(lesson, library)
    parts_types = {p["id"]: p.get("type") for p in b.parts}
    bb_type = next((t for t in parts_types.values() if "breadboard" in (t or "")), None)
    choices = pin_choices(b)
    sym = engine._symmetric_map(lesson, library)
    sym_parts = sorted(c for c in sym if any(p.split(":", 1)[0] == c for conn in b.connections for p in conn))
    gnd_wires = [i for i, c in enumerate(b.connections) for p in c
                 if p.split(":", 1)[0] in b.board_ids and p.split(":", 1)[1].startswith("GND")]
    has_rails = bb_type in ("wokwi-breadboard", "wokwi-breadboard-half")
    groups = [c for c, f in _groups_of(b, library).items() if f]
    leds = [p for p, t in parts_types.items() if t == "wokwi-led"]
    one_object = [p for p, t in parts_types.items() if _placed_together(t, library)]
    dims = {
        "board": ["uno", "arduino mega", "arduino nano"],
        "pins": [dict(zip(choices, combo)) for combo in _pin_samples(choices)],
        "mind": [False, True] if choices else [False],
        "turned": [list(c) for n in range(len(sym_parts) + 1) for c in itertools.combinations(sym_parts, n)],
        "ahead": [False, True],
        "gnd": ["GND.1", "GND.2", "GND.3"] if gnd_wires else ["keep"],
        "sibling": [False, True] if groups else [False],
        "rows": [False, True],
        "shift": [0, _max_shift(b, bb_type)] if _max_shift(b, bb_type) else [0],
        "rails": [False, True] if has_rails else [False],
        "bypass": [False, True],
        "hints": [False, True],
        "back": [False, True],
    }
    steps = b.build_steps
    kinds = [k for k in MISTAKE_KINDS if (k != "reversed" or leds) and (k != "leg_self_short" or one_object)]
    dims["mistakes"] = [()] + [((s, k),) for s in steps for k in kinds] + \
        [((s1, k1), (s2, k2)) for (s1, s2) in itertools.combinations(steps, 2) for k1 in kinds for k2 in kinds][:40]
    return dims


def _pin_samples(choices):
    """Every free pin for each signal pin (others kept), plus the diagonal
    where every pin moves at once."""
    base = {k: k for k in choices}
    combos = [tuple(base.values())]
    for pin, options in choices.items():
        for o in options[1:]:
            combos.append(tuple(o if k == pin else v for k, v in base.items()))
    if len(choices) > 1:
        combos.append(tuple(opts[1] for opts in choices.values() if len(opts) > 1))
    return list(dict.fromkeys(combos)) if choices else [()]


def _groups_of(board, library):
    facts = {}
    for part in board.parts:
        cards = library.find_by_wokwi_type(part.get("type"), part.get("attrs", {}).get("value"))
        rule = (cards[0].get("pin_aliases") or {}) if cards else {}
        facts[part["id"]] = rule.get("mode") == "prefix" and part["id"] not in board.board_ids
    return facts


def _placed_together(wtype, library):
    cards = library.find_by_wokwi_type(wtype) if wtype else []
    return bool(cards and cards[0].get("legs_placed_together"))


def _max_shift(board, bb_type):
    cols = [int(m.group(1)) for c in board.connections for p in c
            for m in [re.match(r"\w+:(\d+)[tb]\.", p)] if m]
    if not cols or bb_type not in BB_COLUMNS:
        return 0
    room = BB_COLUMNS[bb_type] - max(cols)
    return min(room, 4) if room > 0 else -min(min(cols) - 1, 4)


def plan_flows(dims, sample=150, seed=7):
    """Pairwise covering set over all dimensions + a random sample."""
    names = list(dims)
    uncovered = {(a, i, b, j) for ai, a in enumerate(names) for b in names[ai + 1:]
                 for i in range(len(dims[a])) for j in range(len(dims[b]))}
    rng = random.Random(seed)
    flows = []
    while uncovered:
        pick = {}
        a, i, b, j = next(iter(sorted(uncovered)))
        pick[a], pick[b] = i, j
        for name in names:
            if name in pick:
                continue
            best = max(range(len(dims[name])), key=lambda v: (
                sum((min(x, name, key=names.index), ) and
                    ((x, pick[x], name, v) in uncovered if names.index(x) < names.index(name)
                     else (name, v, x, pick[x]) in uncovered) for x in pick), rng.random()))
            pick[name] = best
        for x, y in itertools.combinations(names, 2):
            uncovered.discard((x, pick[x], y, pick[y]))
        flows.append({n: dims[n][pick[n]] for n in names})
    for _ in range(sample):
        flows.append({n: rng.choice(dims[n]) for n in names})
    return flows


# ---------------------------------------------------------------------------
# Building the learner's physical board for one flow
# ---------------------------------------------------------------------------

def _hole(pin):
    m = re.match(r"(\w+):(\d+)([tb])\.([a-j])$", pin)
    return m.groups() if m else None


class Physical:
    """The flow's board as groups: one group of physical connections per
    lesson-diagram connection, so each group keeps that connection's step."""

    def __init__(self, board, lesson, library, flow):
        self.board = board
        sym = engine._symmetric_map(lesson, library)
        conns = [list(c) for c in board.connections]
        board_ids = board.board_ids

        def move_pin(p, mapping):
            comp, leg = p.split(":", 1)
            return f"{comp}:{mapping.get(leg, leg)}" if comp in board_ids else p

        # pins, orientation
        conns = [[move_pin(p, flow["pins"]) for p in c] for c in conns]
        conns = [[checker._swap_pin(p, p.split(":", 1)[0], sym[p.split(":", 1)[0]]) if p.split(":", 1)[0] in flow["turned"] else p
                  for p in c] for c in conns]
        # ground pin choice
        if flow["gnd"] != "keep":
            conns = [[f"{p.split(':', 1)[0]}:{flow['gnd']}" if p.split(":", 1)[0] in board_ids
                      and p.split(":", 1)[1].startswith("GND") else p for p in c] for c in conns]
        # shift the layout
        if flow["shift"]:
            def shift(p):
                h = _hole(p)
                return f"{h[0]}:{int(h[1]) + flow['shift']}{h[2]}.{h[3]}" if h else p
            conns = [[shift(p) for p in c] for c in conns]
        # a wire lands on the other leg of an internal group
        if flow["sibling"]:
            conns = self._to_sibling(conns, library)
        # wire ends in another hole of the same column-half (a wire is a
        # connection with no component leg in it; legs stay where they are)
        if flow["rows"]:
            other = {**dict(zip("abcde", "bcdea")), **dict(zip("fghij", "ghijf"))}   # every row moves

            def is_leg(p):
                comp = p.split(":", 1)[0]
                return comp not in board.connectors and comp not in board_ids
            conns = [c if any(is_leg(p) for p in c) else
                     [f"{_hole(p)[0]}:{_hole(p)[1]}{_hole(p)[2]}.{other[_hole(p)[3]]}" if _hole(p) else p for p in c]
                     for c in conns]
        self.groups = [[c] for c in conns]
        if flow["rails"]:
            self._rails_or_direct(board_ids)
        if flow["bypass"]:
            self._bypass(board_ids)
        self.final = [c for g in self.groups for c in g]

    def _to_sibling(self, conns, library):
        leg_strip = {}
        for c in conns:
            for p, q in ((c[0], c[1]), (c[1], c[0])):
                if _hole(q) and p.split(":", 1)[0] not in self.board.connectors and p.split(":", 1)[0] not in self.board.board_ids:
                    leg_strip[p] = q
        out = []
        for c in conns:
            new = list(c)
            for i, p in enumerate(c):
                h = _hole(p)
                other = c[1 - i]
                if not h or not (other.split(":", 1)[0] in self.board.board_ids or _hole(other)):
                    continue
                strip = f"{h[1]}{h[2]}"
                owner = next((leg for leg, hole in leg_strip.items() if _hole(hole)[1:3] == (h[1], h[2])), None)
                if owner and "." in owner.split(":", 1)[1]:
                    comp, leg = owner.split(":", 1)
                    sib = next((l for l, hole in leg_strip.items() if l.startswith(f"{comp}:{leg.split('.')[0]}.")
                                and l != owner), None)
                    if sib:
                        sh = _hole(leg_strip[sib])
                        new[i] = f"{sh[0]}:{sh[1]}{sh[2]}.{h[3] if h[3] in ('abcde' if sh[2] == 't' else 'fghij') else sh[3]}"
                        break
            out.append(new)
        return out

    def _rails_or_direct(self, board_ids):
        uses_rails = any(re.match(r"\w+:[tb][pn]\.", p) for g in self.groups for c in g for p in c)
        bb = next((p.split(":")[0] for g in self.groups for c in g for p in c if _hole(p)), None)
        if not bb:
            return
        if not uses_rails:
            for gi, g in enumerate(self.groups):
                c = g[0]
                for i, p in enumerate(c):
                    other = c[1 - i]
                    if p.split(":", 1)[0] in board_ids and _hole(other) and (p.endswith(":5V") or ":GND" in p):
                        rail = "bp" if p.endswith(":5V") else "bn"
                        self.groups[gi] = [[p, f"{bb}:{rail}.{gi + 1}"], [f"{bb}:{rail}.{gi + 10}", other]]
        else:
            rail_board = {}
            for g in self.groups:
                for c in g:
                    for i, p in enumerate(c):
                        m = re.match(r"\w+:([tb][pn])\.", p)
                        if m and c[1 - i].split(":", 1)[0] in board_ids:
                            rail_board[m.group(1)] = c[1 - i]
            for gi, g in enumerate(self.groups):
                new = []
                for c in g:
                    rails = [re.match(r"\w+:([tb][pn])\.", p) for p in c]
                    if any(rails) and not any(p.split(":", 1)[0] in board_ids for p in c):
                        r = next(m.group(1) for m in rails if m)
                        hole = next(p for p in c if not re.match(r"\w+:[tb][pn]\.", p))
                        new.append([rail_board.get(r, hole), hole])
                    elif any(rails):
                        continue
                    else:
                        new.append(c)
                self.groups[gi] = new

    def _bypass(self, board_ids):
        """A net that is exactly one component leg + one board pin: the leg
        goes straight onto the board pin."""
        flat = [c for g in self.groups for c in g]
        nets = checker.build_nets(flat, self.board.alias)
        for net in nets:
            real = [p for p in net if p.split(":", 1)[0] not in self.board.connectors]
            legs = [p for p in real if p.split(":", 1)[0] not in board_ids]
            pins = [p for p in real if p.split(":", 1)[0] in board_ids]
            if len(legs) != 1 or len(pins) != 1:
                continue
            leg_pin = legs[0]
            for gi, g in enumerate(self.groups):
                new = []
                for c in g:
                    canon = [checker._canonicalize_pin(p, self.board.alias) for p in c]
                    if any(x in net for x in canon) and any(p.split(":", 1)[0] in self.board.connectors for p in c):
                        if any(checker._canonicalize_pin(p, self.board.alias) == leg_pin for p in c):
                            real_leg = next(p for p in c if checker._canonicalize_pin(p, self.board.alias) == leg_pin)
                            board_pin = next(p for fc in flat for p in fc if checker._canonicalize_pin(p, self.board.alias) == pins[0])
                            new.append([real_leg, board_pin])
                        continue
                    new.append(c)
                self.groups[gi] = new
            return   # one bypass per flow

    def upto(self, step_index):
        return [c for g, s in zip(self.groups, self.board.step_of) if s <= step_index for c in g]


# ---------------------------------------------------------------------------
# Mistakes
# ---------------------------------------------------------------------------

def _mistake(board, phys, step_index, kind, ahead=False):
    """The board with this mistake made at this step, or None if the step
    offers no place for it."""
    current = phys.upto(step_index)
    if kind == "loose":
        # a connection an earlier step put in falls out (prefer a wire)
        earlier_conns = [c for g, st in zip(phys.groups, board.step_of) if st < step_index for c in g]
        gone = loose_removal(board, earlier_conns)
        if not gone:
            return None
        base = phys.final if ahead else current
        return [c for c in base if c not in gone]
    earlier = [j for j in board.build_steps if j < step_index]
    before = phys.upto(earlier[-1]) if earlier else []
    new = [c for c in current if c not in before]
    board_ids = board.board_ids
    if kind == "forgot":
        return before if new else None
    if kind == "wrong_kind":
        for c in new:
            for i, p in enumerate(c):
                if p.split(":", 1)[0] in board_ids:
                    wrong = "GND.1" if not p.split(":", 1)[1].startswith("GND") else "5V"
                    bad = copy.deepcopy(current)
                    bad[current.index(c)][i] = f"{p.split(':', 1)[0]}:{wrong}"
                    return bad
        return None
    if kind == "off_by_one":
        used = {(h[1], h[2]) for c in current for p in c for h in [_hole(p)] if h}
        for c in new:
            if not any(p.split(":", 1)[0] in board_ids for p in c):
                continue
            for i, p in enumerate(c):
                h = _hole(p)
                if h:
                    for d in (1, -1, 2, -2):
                        col = int(h[1]) + d
                        if col >= 1 and (str(col), h[2]) not in used:
                            bad = copy.deepcopy(current)
                            bad[current.index(c)][i] = f"{h[0]}:{col}{h[2]}.{h[3]}"
                            return bad
        return None
    if kind == "short_jumper":
        nets = [n for n in checker.build_nets(current, board.alias)]
        strips = []
        for n in nets:
            hole = next((p for p in n if re.match(r"\w+:\d+[tb]$", p)), None)
            real = [p for p in n if p.split(":", 1)[0] not in board.connectors]
            if hole and real:
                strips.append(hole)
        if len(strips) >= 2:
            a, b = strips[0], strips[1]
            return current + [[f"{a}.a", f"{b}.a"]]
        return None
    if kind == "leg_self_short":
        facts = _groups_of(board, load_library())
        placed = {}
        for c in current:
            for p, q in ((c[0], c[1]), (c[1], c[0])):
                comp = p.split(":", 1)[0]
                if _hole(q) and comp not in board.connectors and comp not in board_ids and \
                        _placed_together(next((x.get("type") for x in board.parts if x["id"] == comp), None), load_library()):
                    placed.setdefault(comp, []).append((p, q))
        for comp, legs in placed.items():
            units = {}
            for p, q in legs:
                unit = p.split(":", 1)[1].split(".")[0] if facts.get(comp) else p
                units.setdefault(unit, (p, q))
            if len(units) >= 2:
                (p1, q1), (p2, q2) = list(units.values())[:2]
                bad = copy.deepcopy(current)
                for c in bad:
                    if p2 in c and q2 in c:
                        h1 = _hole(q1)
                        c[c.index(q2)] = f"{h1[0]}:{h1[1]}{h1[2]}.{'e' if h1[2] == 't' else 'j'}"
                        return bad
        return None
    if kind == "reversed":
        leds = {p["id"] for p in board.parts if p.get("type") == "wokwi-led"}
        swap = {"A": "C", "C": "A"}
        if not any(p.split(":", 1)[0] in leds for c in new for p in c):
            return None
        return [[f"{p.split(':', 1)[0]}:{swap[p.split(':', 1)[1]]}" if p.split(":", 1)[0] in leds
                 and p.split(":", 1)[1] in swap else p for p in c] for c in current]
    return None


# ---------------------------------------------------------------------------
# Playing one flow and checking it
# ---------------------------------------------------------------------------

def _lesson_for(lesson, library, board_name):
    if board_name == "uno":
        return lesson
    result = board_translate.translate_lesson(lesson, board_translate.resolve_target_board(board_name, library), library)
    return result.lesson if result.feasible else None


def run(lesson, library, flow):
    """Play one flow; returns [] or the list of violated invariants."""
    lesson = _lesson_for(lesson, library, flow["board"])
    if lesson is None:
        return []   # the lesson can't be translated to this board: nothing to play
    board = Board(lesson, library)
    if flow["pins"] and not set(flow["pins"]) <= set(pin_choices(board)):
        return []
    phys = Physical(board, lesson, library, flow)
    mistakes = dict(flow["mistakes"])
    pending = {}           # persistent mistake boards not yet caught
    problems = []
    s = Session(lesson, library)
    mind_done = {"moved": None}
    moved_back = {"done": False}

    def mind_adjust(conns):
        if not mind_done["moved"]:
            return conns
        old, new = mind_done["moved"]
        return [[f"{p.split(':', 1)[0]}:{new}" if p.split(":", 1)[0] in board.board_ids and p.split(":", 1)[1] == old else p
                 for p in c] for c in conns]

    def present_board(i):
        return mind_adjust(phys.final if (flow["ahead"] or i is None) else phys.upto(i))

    for _ in range(6 * len(lesson.steps) + 8):
        s.advance_non_build()
        if s.state["finished"]:
            break
        i, phase = s.index, s.phase
        step = lesson.step(i)
        if phase == "build":
            if flow["hints"]:
                for _h in step.get("hints", []):
                    if not any(a["type"] == "hint" for a in s.send({"command": "hint"})):
                        problems.append(f"session: no hint at '{step['id']}'")
            if flow["back"] and not moved_back["done"] and i > min(board.build_steps):
                moved_back["done"] = True
                s.send({"command": "previous"})
                acts = s.send({"command": "done", "detected_pairs": present_board(s.index)})
                if _is_wrong(acts) or s.index != i:
                    problems.append(f"session: going back from '{step['id']}' and re-checking failed")
                    return problems
            if i in mistakes:
                kind = mistakes.pop(i)
                bad = _mistake(board, phys, i, kind, flow["ahead"]) if not flow["ahead"] or kind not in ("forgot", "wrong_kind") else None
                if bad is not None and kind in PERSISTENT:
                    pending[kind] = (i, bad)
                elif bad is not None:
                    acts = s.send({"command": "done", "detected_pairs": mind_adjust(bad)})
                    if not _is_wrong(acts) or s.index != i:
                        problems.append(f"mistakes: '{step['id']}' accepted '{kind}'")
                        return problems
                    if kind == "loose" and not any(a["type"] == "connection_lost" for a in acts):
                        problems.append(f"mistakes: the loose connection at '{step['id']}' wasn't named as lost")
                        return problems
        if pending:
            kind, (at, bad) = next(iter(pending.items()))
            board_now = present_board(i) if phase != "final_check" else present_board(None)
            extra = mind_adjust([c for c in bad if c not in phys.final])
            gone = mind_adjust([c for c in phys.upto(at) if c not in bad])
            shown = [c for c in board_now if c not in gone] + extra
            acts = s.send({"command": "done", "detected_pairs": shown})
            if _is_wrong(acts):
                pending.pop(kind)
                continue   # caught: the learner fixes it and presses check again
            if s.state["finished"]:
                problems.append(f"mistakes: finished with '{kind}' (made at '{lesson.step(at)['id']}') never caught")
                return problems
            continue
        if phase == "final_check":
            acts = s.send({"command": "done", "detected_pairs": present_board(i)})
        else:
            acts = s.send({"command": "done", "detected_pairs": present_board(i)})
            if flow["mind"] and not mind_done["moved"] and not _is_wrong(acts) and flow["pins"] is not None:
                used = [k for k in pin_choices(board)]
                if used:
                    old = flow["pins"].get(used[0], used[0])
                    free = [x for x in pin_choices(board)[used[0]] if x not in (used[0], old)]
                    if free:
                        mind_done["moved"] = (old, free[-1])
        if _is_wrong(acts):
            detail = next((a.get("message") for a in acts if a["type"] in ("substitution_refused", "physics_hazard")), "")
            where = step["id"] if phase != "final_check" else "final_check"
            problems.append(f"finishes: '{where}' said wrong on correct wiring. {detail}".strip())
            return problems
    if not s.state["finished"]:
        return problems + ["finishes: never completed"]
    return problems + check_flow(lesson, library, board, s, present_board(None), flow, mind_done["moved"])


def lesson_pins(lesson, library, board):
    """The signal pins the lesson's own circuit uses."""
    return set(pin_choices(board))


def check_flow(lesson, library, board, s, physical, flow, mind_move):
    problems = []
    state = s.state
    final_pins = dict(flow["pins"])
    if mind_move:
        old, new = mind_move
        orig = next((k for k, v in final_pins.items() if v == old), old)
        final_pins[orig] = new
    final_pins = {k: v for k, v in final_pins.items() if k != v}

    # replay the records in order from each of the lesson's own pins
    current = {p: p for p in lesson_pins(lesson, library, board)}
    for sub in state["pin_substitutions"]:
        o, a = sub["original"].split(":", 1)[1], sub["actual"].split(":", 1)[1]
        for root, now in current.items():
            if now == o or (root == o and now != a):
                current[root] = a
                break
    recorded = current
    recorded = {k: v for k, v in recorded.items() if k != v}
    if recorded != final_pins:
        problems.append(f"substitutions: tracked {recorded}, the learner's pins are {final_pins}")
    told = [a for _, acts in s.log for a in acts if a["type"] == "pin_substituted"]
    if final_pins and not told:
        problems.append("substitutions: the learner was never told about the moved pin")
    if mind_move and not any(mind_move[1] in a["message"] for a in told):
        problems.append(f"substitutions: moving to pin {mind_move[1]} was never announced")

    for comp in sorted(set(engine._symmetric_map(lesson, library)) & set(state.get("orientations", {}))):
        want = "swapped" if comp in flow["turned"] else "straight"
        if state["orientations"][comp] != want:
            problems.append(f"orientation: {comp} tracked {state['orientations'][comp]}, physically {want}")

    if _nets(state["confirmed_pairs"], board) != _nets(physical, board):
        problems.append("tracking: confirmed nets differ from the physical board")

    original, shown = lesson.code_text(), engine._adjusted_code(lesson, state)
    if _non_pin_fingerprint(shown) != _non_pin_fingerprint(original):
        problems.append("code: something that isn't a pin changed")
    before, after = physics.pin_modes_from_code(original), physics.pin_modes_from_code(shown)
    want = {final_pins.get(k, k): v for k, v in before.items()}
    if after != want:
        problems.append(f"code: drives {after}, the learner's circuit needs {want}")

    design = physics.analyze(board.connections, board.parts, original, library)
    learner = physics.analyze(physical, board.parts, shown, library)
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


def stress(lesson, library=None, sample=150, seed=7, stop_after=None):
    """Plan and play every flow. Returns {"flows", "failures": [(flow, problems)]}."""
    library = library or load_library()
    dims = _variants_for(lesson, library, "uno")
    failures, played = [], 0
    for flow in plan_flows(dims, sample=sample, seed=seed):
        played += 1
        try:
            problems = run(lesson, library, flow)
        except Exception as exc:   # a crash is a failure, not a stop
            problems = [f"crash: {type(exc).__name__}: {exc}"]
        if problems:
            failures.append((flow, problems))
            if stop_after and len(failures) >= stop_after:
                break
    return {"flows": played, "dims": {k: len(v) for k, v in dims.items()}, "failures": failures}
