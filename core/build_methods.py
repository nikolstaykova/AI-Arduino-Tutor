"""Build a lesson WITH or WITHOUT a breadboard.

A lesson's `expected_nets` are already breadboard-free (`r1:2 ↔ led1:A`),
so the breadboard is just one way of making those connections. Without
one, every connection has to be made some other physical way, and which
way depends on the real legs involved (the library card's `leads`):

  wire-lead  — long bendable wire legs (LEDs, resistors): twist together,
               clip or solder them. A lead is thinner than a header pin, so
               pushed into an Arduino socket it sits loose — only the
               "twist" (no extra parts) style does that, and says so.
  pin        — male header pins on a module: a female jumper socket slides
               onto them (that's what those pins are for)
  lug        — a potentiometer's flat solder tabs: solder a wire to each
               tab, or grip it with a clip lead; nothing plugs onto them
  short-leg  — short flat legs (tactile pushbuttons): too short to twist or
               to stay in a header — clip them or solder them

One header socket holds one leg. Joining two legs is done with the chosen
join style — "clips" (alligator-clip leads, solderless, the default),
"twist" (no parts, temporary) or "solder" (permanent, needs tools) — and a
leg that can't do what the style asks falls back to the next thing that
physically works (a pushbutton leg can't be twisted, so it gets a clip).

`plan()` walks the lesson's own build steps in order, deciding each
connection with what's already occupied, so the instructions, the
shopping list (extra parts WITH counts, tools) and the derived lesson all
agree. `derive_lesson()` returns a Lesson-compatible object the unchanged
engine runs: landing steps ("place it on the breadboard") are dropped, each
wiring step is rewritten with the real how-to, the gather step lists the
new parts and tools, and the diagram connects legs directly.
"""
import copy
from collections import Counter

from .board_translate import TranslatedLesson

METHODS = ("breadboard", "no-breadboard")
JOINS = ("clips", "twist", "solder")
SOLDER_TOOLS = ["soldering-iron", "wire-stripper", "flush-cutters"]
SOLDER_PARTS = ["solder", "heat-shrink"]


# ---------------------------------------------------------------------------
# What a leg is, physically
# ---------------------------------------------------------------------------
def _components(lesson, library):
    """component id -> library card, from the lesson's own diagram."""
    out = {}
    for part in lesson.diagram().get("parts", []):
        cards = library.find_by_wokwi_type(part.get("type"), part.get("attrs", {}).get("value"))
        if cards:
            out[part["id"]] = cards[0]
    return out


def _board_id(lesson, library, comps):
    for cid, card in comps.items():
        if card.get("subtype") == "board" or card.get("pin_domains"):
            return cid
    return "uno"


def _leads(card):
    return (card or {}).get("leads", "pin")


def _sock(endpoint):
    """'uno:GND.1' -> 'GND' — the name printed next to the header socket."""
    return endpoint.split(":", 1)[-1].split(".")[0]


def describe(endpoint, comps, board_id):
    """Plain words for an endpoint: 'the LED's anode (the longer leg)'."""
    comp, pin = endpoint.split(":", 1)
    if comp == board_id:
        return f"the Arduino's {_sock(pin)} pin"
    card = comps.get(comp) or {}
    sub, name = card.get("subtype"), card.get("display_name", comp)
    if sub == "led":
        return "the LED's anode (the longer leg)" if pin == "A" else "the LED's cathode (the shorter leg)"
    if sub == "resistor":
        return f"resistor {comp}'s leg {pin}"
    if sub == "pushbutton":
        return f"the pushbutton's contact pair {_sock(pin)} (either of its two legs)"
    if sub == "potentiometer":
        return {"SIG": "the potentiometer's middle pin (the wiper)",
                "GND": "the potentiometer's outer pin on the GND side",
                "VCC": "the potentiometer's other outer pin"}.get(pin, f"the potentiometer's {pin} pin")
    return f"the {name}'s {pin} pin"


# ---------------------------------------------------------------------------
# Deciding each connection
# ---------------------------------------------------------------------------
def _net_index(lesson):
    """endpoint -> net id, from the final circuit (union-find)."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in lesson.final_check_nets():
        parent[find(a)] = find(b)
    return {e: find(e) for e in parent}


class _Planner:
    def __init__(self, lesson, library, join):
        self.lesson, self.library, self.join = lesson, library, join
        self.comps = _components(lesson, library)
        self.board = _board_id(lesson, library, self.comps)
        self.net_of = _net_index(lesson)
        self.socket_holder = {}        # board pin -> the leg pushed into it
        self.done = set()              # endpoints already connected to something
        self.items, self.tools, self.notes = Counter(), set(), []
        self.pairs = []                # the concrete links: [a, b, colour]

    def card(self, endpoint):
        return self.comps.get(endpoint.split(":", 1)[0])

    def is_board(self, endpoint):
        return endpoint.split(":", 1)[0] == self.board

    def d(self, e):
        return describe(e, self.comps, self.board)

    # leg -> header socket. `kind` says what is physically there (the bench draws it):
    #   insert       the bare lead bent straight into the socket (twist style only — loose)
    #   mf-jumper    a male-to-female jumper: female end on a stiff pin, male end in the socket
    #   clip-stub    a jumper in the socket, an alligator lead from its free pin to the bare leg
    #   solder-wire  a jumper wire soldered to the leg (heat-shrink over it), its pin in the socket
    def to_pin(self, leg, pin):
        lead = _leads(self.card(leg))
        holder = self.socket_holder.get(pin)
        if holder and holder != leg:
            # one leg per socket: join to the leg that's already in it
            return self.join_legs(leg, holder, via=f"(it's already in the {_sock(pin)} socket)")
        if lead == "pin":
            self.pairs.append([leg, pin, "orange", "mf-jumper"])
            self.items["jumper-wire-mf"] += 1
            return (f"Slide the socket end of a male-to-female jumper onto {self.d(leg)}, and push its pin end "
                    f"into the {_sock(pin)} socket."), ["jumper-wire-mf"]
        if lead == "wire-lead" and self.join == "twist":
            self.pairs.append([leg, pin, "orange", "insert"])
            self.socket_holder[pin] = leg
            self.notes.append("A component lead is thinner than a header pin, so a lead pushed straight into an "
                              "Arduino socket sits loose. Bend its tip into a small kink before pushing it in, "
                              "and reseat it if a check says the connection is lost.")
            return (f"Bend {self.d(leg)} and push its tip into the {_sock(pin)} socket on the Arduino's header. "
                    f"It's a loose fit (the lead is thinner than a header pin) — a small kink in the tip helps it grip."), []
        why = {"short-leg": "a pushbutton's legs are too short to hold in a socket",
               "lug": "a knob's flat solder tabs won't hold in a socket or take a jumper"}.get(lead, "a bare lead is too thin to grip in a header socket")
        if self.join == "solder":
            self.pairs.append([leg, pin, "orange", "solder-wire"])
            self.items["jumper-wire"] += 1
            self._solder()
            return (f"Solder one end of a jumper wire to {self.d(leg)} ({why}), slide heat-shrink over the joint, "
                    f"and push the wire's pin into the {_sock(pin)} socket."), ["jumper-wire"] + SOLDER_TOOLS
        self.pairs.append([leg, pin, "orange", "clip-stub"])
        self.items["alligator-clip-wire"] += 1
        self.items["jumper-wire"] += 1
        return (f"Push one end of a jumper wire into the {_sock(pin)} socket, then clip an alligator lead "
                f"from {self.d(leg)} to the jumper's free pin ({why})."), ["alligator-clip-wire", "jumper-wire"]

    # leg <-> leg
    def join_legs(self, a, b, via=""):
        la, lb = _leads(self.card(a)), _leads(self.card(b))
        link = [a, b, "green", None]
        self.pairs.append(link)
        extra = f" {via}" if via else ""
        style = self.join
        if style == "twist" and not (la == "wire-lead" and lb == "wire-lead"):
            self.notes.append(f"{self.d(a).capitalize()} and {self.d(b)} can't be twisted together "
                              f"(too short, too stiff or a flat tab), so that joint uses an alligator clip lead.")
            style = "clips"
        link[3] = {"twist": "twist", "solder": "solder"}.get(style, "clip")
        if style == "twist":
            return (f"Twist {self.d(a)} and {self.d(b)}{extra} tightly together — two or three turns. "
                    f"It's temporary: if a check fails later, squeeze this joint first."), []
        if style == "solder":
            self._solder()
            return (f"Solder {self.d(a)} to {self.d(b)}{extra}: hold them side by side, heat the joint, feed in "
                    f"a little solder, and slide heat-shrink over it once it's cool."), list(SOLDER_TOOLS)
        self.items["alligator-clip-wire"] += 1
        return (f"Clip an alligator lead from {self.d(a)} to {self.d(b)}{extra}. Make sure the jaws bite the "
                f"bare metal, and that no other bare leg touches the clip."), ["alligator-clip-wire"]

    def _solder(self):
        self.tools.update(SOLDER_TOOLS)
        for p in SOLDER_PARTS:
            self.items[p] = max(self.items[p], 1)

    def connect(self, a, b):
        if self.is_board(a) and not self.is_board(b):
            a, b = b, a
        if self.is_board(b) and not self.is_board(a):
            text, uses = self.to_pin(a, b)
        elif not self.is_board(a) and not self.is_board(b):
            text, uses = self.join_legs(a, b)
        else:
            self.items["jumper-wire"] += 1
            self.pairs.append([a, b, "gray", "jumper"])
            text, uses = f"Run a jumper wire from {self.d(a)} to {self.d(b)}.", ["jumper-wire"]
        self.done.update([a, b])
        return {"pair": [a, b], "how": text, "uses": sorted(set(uses))}


def _step_pairs(step):
    return [list(p) for p in step.get("expected_nets", [])]


def plan(lesson, library, method="no-breadboard", join="clips"):
    """How to build `lesson` with `method` ("breadboard" / "no-breadboard")
    and, without a breadboard, `join` ("clips" / "twist" / "solder").
    Returns {method, join, steps: [{step, connections: [{pair, how, uses}]}],
    parts: [ids], counts: {id: n}, tools: [ids], changes: {...}, notes}."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    if join not in JOINS:
        raise ValueError(f"join must be one of {JOINS}")
    base_parts = list(dict.fromkeys(lesson.data.get("parts_used", [])))
    base_tools = list(lesson.data.get("tools_used", []))
    if method == "breadboard":
        return {"method": method, "join": None, "steps": [], "parts": base_parts, "counts": {},
                "tools": base_tools, "changes": {"removed": [], "added": [], "tools_added": []}, "notes": []}

    P = _Planner(lesson, library, join)
    steps = []
    for step in lesson.steps:
        if step.get("phase") != "build" or "expected_nets" not in step:
            continue
        steps.append({"step": step["id"], "connections": [P.connect(a, b) for a, b in _step_pairs(step)]})
    # anything in the final circuit no step wired (hand-authored gaps)
    covered = {tuple(sorted(c["pair"])) for s in steps for c in s["connections"]}
    for a, b in lesson.final_check_nets():
        if tuple(sorted((a, b))) not in covered:
            steps.append({"step": "final_check", "connections": [P.connect(a, b)]})

    parts = [p for p in base_parts if p not in ("breadboard", "jumper-wire")]
    parts += [p for p in P.items if p not in parts]
    tools = base_tools + [t for t in sorted(P.tools) if t not in base_tools]
    notes = list(dict.fromkeys(P.notes))
    notes.append("With no breadboard, bare legs can touch and short: spread the parts out and bend legs apart.")
    return {
        "method": method, "join": join, "steps": steps,
        "parts": parts, "counts": dict(P.items), "tools": tools,
        "changes": {"removed": [p for p in base_parts if p not in parts],
                    "added": [p for p in parts if p not in base_parts],
                    "tools_added": [t for t in tools if t not in base_tools]},
        "notes": notes, "pairs": P.pairs, "board": P.board,
    }


def all_plans(lesson, library):
    """Every way to build the lesson — for the lesson card's comparison."""
    out, seen = [plan(lesson, library, "breadboard")], set()
    for j in JOINS:
        p = plan(lesson, library, "no-breadboard", j)
        key = (tuple(p["parts"]), tuple(sorted(p["counts"].items())), tuple(p["tools"]))
        if key not in seen:            # a lesson with no leg-to-leg joins builds the same every style
            seen.add(key)
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# The derived lesson the engine runs
# ---------------------------------------------------------------------------
def _name_list(ids, library, counts=None):
    names = []
    for i in ids:
        card = library.get(i)
        n = (counts or {}).get(i)
        label = card["display_name"] if card else i
        names.append(f"{n}× {label}" if n and n > 1 else label)
    return ", ".join(names[:-1]) + (" and " + names[-1] if len(names) > 1 else names[0] if names else "")


def derive_lesson(lesson, library, method="no-breadboard", join="clips"):
    """A Lesson-compatible copy built `method`/`join`. With a breadboard it's
    the lesson itself."""
    if method == "breadboard":
        return lesson
    p = plan(lesson, library, method, join)
    data = copy.deepcopy(lesson.data)
    how = {s["step"]: s["connections"] for s in p["steps"]}
    style = {"clips": "clip leads", "twist": "twisted legs", "solder": "soldering"}[join]
    new_steps = []
    for step in data["steps"]:
        if step.get("phase") == "gather":
            step["items"] = p["parts"] + p["tools"]
            step["clip"] = (f"No breadboard this time — we'll use {style}. Gather: {_name_list(p['parts'], library, p['counts'])}"
                            + (f". Tools: {_name_list(p['tools'], library)}." if p["tools"] else "."))
        elif step.get("phase") == "build" and "expected_landing" in step and not step.get("expected_nets"):
            continue            # "place it on the breadboard" has no meaning here
        elif step.get("phase") == "build" and step["id"] in how:
            step.pop("expected_landing", None)   # placing it also made a connection: keep that as a joining step
            conns = how[step["id"]]
            step["clip"] = " ".join(c["how"] for c in conns)
            step["hints"] = [f"This step connects {describe(c['pair'][0], _components(lesson, library), p['board'])} "
                             f"and {describe(c['pair'][1], _components(lesson, library), p['board'])} — nothing else."
                             for c in conns] + p["notes"][:1]
        new_steps.append(step)
    data["steps"] = new_steps
    data["parts_used"] = p["parts"]
    data["tools_used"] = p["tools"]
    data["build_method"] = {"method": method, "join": join, "counts": p["counts"], "notes": p["notes"],
                            "links": [{"a": a, "b": b, "kind": k} for a, b, _, k in p["pairs"]]}
    diagram = copy.deepcopy(lesson.diagram())
    bb = {q["id"] for q in diagram["parts"] if "breadboard" in q.get("type", "")}
    diagram["parts"] = [q for q in diagram["parts"] if q["id"] not in bb]
    diagram["connections"] = [[a, b, colour, []] for a, b, colour, _ in p["pairs"]]
    return TranslatedLesson(lesson, data, diagram, lesson.code_text())
