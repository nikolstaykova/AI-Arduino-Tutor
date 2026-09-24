"""Learner scenarios every lesson must survive — hand-made or AI-generated
(PLAN.md Phase 5b).

A generated lesson isn't good enough just because it matches an answer
key: a real learner builds step by step, builds ahead, picks a different
pin, puts a part in the other way round, forgets a step, wires the wrong
pin, reverses an LED, makes a short, asks for hints and goes back. This
module plays each of those against a lesson through the real engine, using
the lesson's OWN diagram as the physical board, and reports any scenario
that doesn't behave the way it does in the hand-made lessons.

How the board is built for step-by-step play: a part goes in with ALL its
legs at the first step that mentions it (a resistor is one object, even
if the lesson checks one leg at a time), and a wire goes in at the first
step that expects a connection inside the electrical net that wire is
part of.
"""
from . import checker, engine, physics
from .library import load_library

SCENARIOS = ["normal", "build_ahead", "moved_pins", "turned_round", "forgot_step",
             "wrong_pin", "reversed_part", "short_at_final", "hints_and_back", "wire_comes_loose"]


# ---------------------------------------------------------------------------
# The physical board, step by step
# ---------------------------------------------------------------------------

def _is_wrong(actions):
    return any(a["type"] == "feedback" and a.get("verdict") == "wrong" for a in actions)


def _pins_of_step(step):
    pins = [p for pair in step.get("expected_nets", []) for p in pair]
    landing = step.get("expected_landing")
    pins += [landing] if isinstance(landing, str) else list(landing or [])
    return pins


class Board:
    """The lesson's diagram as physical actions, with helpers to build the
    board as it stands after each build step."""

    def __init__(self, lesson, library):
        self.lesson = lesson
        self.library = library
        diagram = lesson.diagram()
        self.parts = diagram.get("parts", [])
        self.connections = [list(c[:2]) for c in diagram.get("connections", [])]
        self.alias = checker.board_alias_map(self.parts, library)
        self.connectors = checker.connector_ids(self.parts, library)
        self.board_ids = engine._board_component_ids(self.parts, library)
        self.build_steps = [i for i, s in enumerate(lesson.steps) if s.get("phase") == "build"]
        self._assign()

    def _comp(self, pin):
        return pin.split(":", 1)[0]

    def _is_component_pin(self, pin):
        comp = self._comp(pin)
        return comp not in self.connectors and comp not in self.board_ids

    def _assign(self):
        """step index each connection first belongs to."""
        full_nets = checker.build_nets(self.connections, self.alias)
        net_of = {}
        for net in full_nets:
            for member in net:
                net_of[member] = net
        first_mention = {}
        for i in self.build_steps:
            for pin in _pins_of_step(self.lesson.steps[i]):
                first_mention.setdefault(self._comp(pin), i)
        last = self.build_steps[-1] if self.build_steps else 0
        self.step_of = []
        for a, b in self.connections:
            comps = [self._comp(p) for p in (a, b) if self._is_component_pin(p)]
            if comps:
                # a leg in a hole (or leg to leg): placed with its part
                self.step_of.append(min(first_mention.get(c, last) for c in comps))
                continue
            net = net_of.get(checker._canonicalize_pin(a, self.alias), frozenset())
            when = last
            for i in self.build_steps:
                for x, y in self.lesson.steps[i].get("expected_nets", []):
                    cx, cy = (checker._canonicalize_pin(p, self.alias) for p in (x, y))
                    if cx in net or cy in net:
                        when = min(when, i)
            self.step_of.append(when)

    def upto(self, step_index, connections=None):
        connections = connections if connections is not None else self.connections
        return [c for c, s in zip(connections, self.step_of) if s <= step_index]

    def full(self, connections=None):
        return list(connections if connections is not None else self.connections)

    # --- variants of the physical board ---------------------------------

    def moved_pins(self):
        """Every signal pin (digital/analog) moved to a free pin of the same
        kind: returns (connections, {old: new})."""
        board_type = next((p.get("type") for p in self.parts if p["id"] in self.board_ids), None)
        card = engine._board_card(board_type, self.library) if board_type else None
        domains = (card or {}).get("pin_domains", {"digital": [str(n) for n in range(2, 14)],
                                                      "analog": [f"A{n}" for n in range(6)]})
        used = {p.split(":", 1)[1] for c in self.connections for p in c if self._comp(p) in self.board_ids}
        moves = {}
        for pin in sorted(used):
            pool = next((d for d in domains.values() if pin in d), None)
            if not pool:
                continue
            i = pool.index(pin)
            for candidate in pool[i - 1::-1] + pool[i + 1:] if i > 0 else pool[i + 1:]:
                if candidate not in used and candidate not in moves.values():
                    moves[pin] = candidate
                    break
        moved = [[f"{self._comp(p)}:{moves.get(p.split(':', 1)[1], p.split(':', 1)[1])}"
                  if self._comp(p) in self.board_ids else p for p in c] for c in self.connections]
        return moved, moves

    def turned_round(self):
        """Every part whose card says it's interchangeable, put in the other
        way round. Returns (connections, [part ids])."""
        sym = engine._symmetric_map(self.lesson, self.library)
        comps = sorted(c for c in sym if any(self._comp(p) == c for conn in self.connections for p in conn))
        turned = [[checker._swap_pin(p, self._comp(p), sym[self._comp(p)]) if self._comp(p) in comps else p
                   for p in c] for c in self.connections]
        return turned, comps

    def reversed_polarized(self):
        """Every LED (polarized part) in backwards. Returns (connections, ids)."""
        leds = sorted({p["id"] for p in self.parts if p.get("type") == "wokwi-led"})
        swap = {"A": "C", "C": "A"}
        rev = [[f"{self._comp(p)}:{swap[p.split(':', 1)[1]]}" if self._comp(p) in leds and p.split(":", 1)[1] in swap else p
                for p in c] for c in self.connections]
        return rev, leds


def loose_removal(board, earlier_conns):
    """What physically comes loose: a jumper wire if there is one, else a
    whole part pulled out (every leg of it) — never a single leg of a
    one-object part, which can't come out on its own."""
    def legs(c):
        return [p for p in c if p.split(":", 1)[0] not in board.connectors and p.split(":", 1)[0] not in board.board_ids]
    wires = [c for c in earlier_conns if not legs(c)]
    if wires:
        return [wires[0]]
    parts = [legs(c)[0].split(":", 1)[0] for c in earlier_conns if legs(c)]
    if not parts:
        return []
    comp = parts[0]
    return [c for c in earlier_conns if any(p.split(":", 1)[0] == comp for p in c)]


# ---------------------------------------------------------------------------
# Playing a lesson
# ---------------------------------------------------------------------------

class Session:
    def __init__(self, lesson, library):
        self.lesson, self.library = lesson, library
        self.state = engine.initial_state()
        self.log = []
        self.send({"command": "start"})

    def send(self, event):
        if event.get("detected_pairs") is not None:
            event = {**event, "snapshot": True}   # always the learner's whole board
        self.state, actions = engine.handle_event(self.lesson, self.library, self.state, event)
        self.log.append((event, actions))
        return actions

    @property
    def index(self):
        return self.state["step_index"]

    @property
    def phase(self):
        return self.state["phase"]

    def step_id(self):
        step = self.lesson.step(self.index)
        return step["id"] if step else self.phase

    def advance_non_build(self):
        while self.phase in ("gather", "upload") and not self.state["finished"]:
            self.send({"command": "done"})


def _play(lesson, library, board_for_step, final_board, max_checks=60, on_step=None):
    """Drive the lesson: at every build step present board_for_step(i), at
    final_check present final_board. Returns (session, error or None)."""
    s = Session(lesson, library)
    for _ in range(max_checks):
        s.advance_non_build()
        if s.state["finished"]:
            return s, None
        if on_step:
            err = on_step(s)
            if err:
                return s, err
            s.advance_non_build()
            if s.state["finished"]:
                return s, None
        board = final_board if s.phase == "final_check" else board_for_step(s.index)
        before = (s.index, s.phase)
        actions = s.send({"command": "done", "detected_pairs": board})
        if _is_wrong(actions):
            detail = next((a.get("message") for a in actions if a["type"] in ("substitution_refused", "physics_hazard")), "")
            return s, f"step '{lesson.step(before[0])['id'] if before[1] != 'final_check' else 'final_check'}' said wrong. {detail}".strip()
    return s, "never finished"


def _result(name, ok, detail=""):
    return {"name": name, "ok": ok, "detail": detail}


def run_scenarios(lesson, library=None, only=None):
    """Play every scenario; returns [{"name", "ok", "detail"}]."""
    library = library or load_library()
    board = Board(lesson, library)
    results = []
    wanted = only or SCENARIOS

    if "normal" in wanted:
        s, err = _play(lesson, library, lambda i: board.upto(i), board.full())
        results.append(_result("normal", err is None and s.state["finished"], err or ""))

    if "build_ahead" in wanted:
        s, err = _play(lesson, library, lambda i: board.full(), board.full())
        results.append(_result("build_ahead", err is None, err or ""))

    if "moved_pins" in wanted:
        moved, moves = board.moved_pins()
        if moves:
            s, err = _play(lesson, library, lambda i: board.upto(i, moved), moved)
            told = [a for _, acts in s.log for a in acts if a["type"] == "pin_substituted"]
            code_pins = set(physics.pin_modes_from_code(engine._adjusted_code(lesson, s.state)))
            problems = []
            if err:
                problems.append(err)
            if len(told) < len(moves):
                problems.append(f"the learner was told about {len(told)} of {len(moves)} moved pins")
            stale = [old for old, new in moves.items() if old in code_pins and new not in code_pins]
            if stale:
                problems.append(f"the shown code still uses pin(s) {', '.join(stale)}")
            results.append(_result("moved_pins", not problems, "; ".join(problems) + f" (moved {moves})"))

    if "turned_round" in wanted:
        turned, comps = board.turned_round()
        if comps:
            s, err = _play(lesson, library, lambda i: board.upto(i, turned), turned)
            harmless = any(a.get("verdict") == "harmless" for _, acts in s.log for a in acts)
            ok = err is None and harmless
            results.append(_result("turned_round", ok, err or ("" if harmless else "the swap was never flagged harmless")
                                   + f" (turned {comps})"))

    if "forgot_step" in wanted:
        problems = []

        def forgot(s):
            if s.phase != "build":
                return None
            i = s.index
            earlier = [j for j in board.build_steps if j < i]
            previous_board = board.upto(earlier[-1]) if earlier else []
            if board.upto(i) == previous_board:
                return None   # this step adds nothing physical (a check of what's already there)
            actions = s.send({"command": "done", "detected_pairs": previous_board})
            if not _is_wrong(actions) or s.index != i:
                problems.append(f"'{s.step_id()}' accepted a board where this step wasn't done")
            return None
        s, err = _play(lesson, library, lambda i: board.upto(i), board.full(), on_step=forgot)
        if err:
            problems.append(f"after fixing: {err}")
        results.append(_result("forgot_step", not problems, "; ".join(problems)))

    if "wrong_pin" in wanted:
        problems = []

        def wrong_pin(s):
            if s.phase != "build":
                return None
            step = lesson.step(s.index)
            board_pins = [p for pair in step.get("expected_nets", []) for p in pair
                          if p.split(":", 1)[0] in board.board_ids]
            if not board_pins:
                return None
            target = board_pins[0]
            wrong = "GND.1" if not target.split(":", 1)[1].startswith("GND") else "5V"
            comp = target.split(":", 1)[0]
            bad = [[f"{comp}:{wrong}" if p == target or (p.split(':', 1)[0] == comp and
                   checker._canonicalize_pin(p, board.alias) == checker._canonicalize_pin(target, board.alias)) else p
                    for p in c] for c in board.upto(s.index)]
            actions = s.send({"command": "done", "detected_pairs": bad})
            if not _is_wrong(actions):
                problems.append(f"'{step['id']}' accepted {target} wired to {wrong}")
            return None
        s, err = _play(lesson, library, lambda i: board.upto(i), board.full(), on_step=wrong_pin)
        if err:
            problems.append(f"after fixing: {err}")
        results.append(_result("wrong_pin", not problems, "; ".join(problems)))

    if "reversed_part" in wanted:
        rev, leds = board.reversed_polarized()
        if leds:
            s, err = _play(lesson, library, lambda i: board.upto(i, rev), rev)
            if err is None:
                results.append(_result("reversed_part", False, f"finished with {', '.join(leds)} in backwards"))
            else:
                # the learner flips it round and carries on
                s2, err2 = _play(lesson, library, lambda i: board.upto(i), board.full())
                results.append(_result("reversed_part", err2 is None, err2 or ""))

    if "short_at_final" in wanted:
        board_pin = next(iter(sorted(board.board_ids)), "uno")
        shorted = board.full() + [[f"{board_pin}:5V", f"{board_pin}:GND.2"]]
        s, err = _play(lesson, library, lambda i: board.upto(i), shorted)
        # Refused either way is right: by the wiring check when 5V is
        # already part of the circuit, by the physics solver when it isn't.
        if err is None or "final_check" not in err:
            results.append(_result("short_at_final", False, err or "a 5V–GND short at final_check was accepted"))
        else:
            actions = s.send({"command": "done", "detected_pairs": board.full()})
            results.append(_result("short_at_final", s.state["finished"], "" if s.state["finished"] else "didn't finish after removing the short"))

    if "hints_and_back" in wanted:
        problems = []
        went_back = {"done": False}

        def hints_and_back(s):
            if s.phase != "build":
                return None
            step = lesson.step(s.index)
            for _ in step.get("hints", []):
                actions = s.send({"command": "hint"})
                if not any(a["type"] == "hint" for a in actions):
                    problems.append(f"'{step['id']}' gave no hint")
                    break
            if not went_back["done"] and s.index > min(board.build_steps):
                went_back["done"] = True
                here = s.index
                s.send({"command": "previous"})
                s.send({"command": "done", "detected_pairs": board.upto(s.index)})
                if s.index != here:
                    problems.append(f"going back from '{step['id']}' and re-checking didn't return to it")
            return None
        s, err = _play(lesson, library, lambda i: board.upto(i), board.full(), on_step=hints_and_back)
        if err:
            problems.append(err)
        results.append(_result("hints_and_back", not problems, "; ".join(problems)))

    if "wire_comes_loose" in wanted:
        problems = []

        def loose(s):
            if s.phase != "build":
                return None
            i = s.index
            earlier = [c for c, st in zip(board.connections, board.step_of) if st < i]
            gone = loose_removal(board, earlier)
            if not gone:
                return None
            actions = s.send({"command": "done", "detected_pairs": [c for c in board.upto(i) if c not in gone]})
            if not _is_wrong(actions) or not any(a["type"] == "connection_lost" for a in actions):
                problems.append(f"'{s.step_id()}': {gone} came loose and wasn't reported")
            return None
        s, err = _play(lesson, library, lambda i: board.upto(i), board.full(), on_step=loose)
        if err:
            problems.append(f"after putting it back: {err}")
        results.append(_result("wire_comes_loose", not problems, "; ".join(problems)))

    return results


def failures(lesson, library=None):
    return [r for r in run_scenarios(lesson, library) if not r["ok"]]
