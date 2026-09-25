"""Lessons generated on the spot by an LLM (PLAN.md Phase 5b).

Flow: request ("a traffic light", or an idea from `suggest_ideas`) →
Claude writes lesson.json + diagram.json + code.ino → `validate` runs
every check the hand-authored lessons already pass (structure, library
ids, pin names, step/final/diagram consistency, sketch pins, the physics
solver, and a real engine dry run) → any errors go back to the model to
fix → only a lesson that passes everything is saved and playable.

The model never decides correctness at play time: a generated lesson is
run by the same engine, checker and physics as a hand-authored one. The
generation brief and the validation checks are adapted from the
`llm-lesson-gen` experiment (a separate copy of this project), which
found Sonnet produced electrically equivalent lessons for all three
Arduino Basics tutorials in one attempt.

Real parts are described to the model as physical objects, generated
from the library cards (part_facts / facts_text): pins and what each
leg is, which legs are one internal connection, which are
interchangeable, polarity, whether the part goes in as one object (all
legs at once, one landing step) and whether it must straddle the gap.
The validator checks the returned steps and diagram against the SAME
facts (_check_physical_steps, _check_diagram_placement), so the brief
and the checks can't drift apart.

Two ways to reach Claude (`backend()` picks; CQ_AI_BACKEND forces one, or
"none" to switch AI off — test servers do, so tests never spend usage):
  "api"          — the Anthropic SDK with ANTHROPIC_API_KEY (imported
                   lazily, so the rest of the project stays standard-library);
  "claude-code"  — the learner's own Claude Code login on this machine:
                   `claude -p` in print mode with --json-schema structured
                   output, no tools, no saved session. No key needed — for
                   running the bench locally on your own account.
Tests inject `generate_fn` instead.
"""
import contextlib
import contextvars
import json
import os
import re
import shutil
import subprocess
import tempfile

from . import checker, engine, flow_explorer, physics, scenarios
from .lesson import LESSONS_ROOT, Lesson
from .library import load_library

MODEL = "claude-opus-5"
MAX_ATTEMPTS = 3

# Part types the engine AND the physics solver fully model. Their physical
# facts (pins, internal connections, interchangeable legs, polarity, how
# they're placed) are read from the library cards — see part_facts().
MODELLED_TYPES = ["wokwi-led", "wokwi-resistor", "wokwi-potentiometer", "wokwi-pushbutton", "wokwi-slide-switch", "wokwi-buzzer", "wokwi-pir-motion-sensor",
                   "cq-photoresistor", "cq-fsr", "cq-ping", "cq-adxl335", "cq-memsic2125", "wokwi-rgb-led"]
UNO_PINS = ({str(n) for n in range(14)} | {f"A{n}" for n in range(6)}
            | {"5V", "3.3V", "VIN", "GND.1", "GND.2", "GND.3", "AREF", "IOREF", "RESET"})
BREADBOARD_TYPES = {"wokwi-breadboard", "wokwi-breadboard-half", "wokwi-breadboard-mini"}


def part_facts(library=None):
    """{wokwi_type: facts} for every modelled part, straight from its
    library card: what a real one physically is. Used twice, so the model
    and the validator can never disagree: to write the brief's "real
    parts" section, and to check the steps and diagram the model returns.

    facts = {"pins": {pin: meaning}, "groups": [[pins internally connected]],
             "interchangeable": [[group_or_pin, group_or_pin]], "polarized",
             "placed_together", "straddles_gap", "display_name", "how_to_use"}"""
    library = library or load_library()
    facts = {}
    for wtype in MODELLED_TYPES:
        cards = [c for c in library.cards.values()
                 if wtype in (c.get("wokwi_type") if isinstance(c.get("wokwi_type"), list) else [c.get("wokwi_type")])]
        if not cards:
            continue
        card = cards[0]
        pins = card.get("pins", {})
        prefixes = (card.get("pin_aliases") or {}).get("prefixes", []) if (card.get("pin_aliases") or {}).get("mode") == "prefix" else []
        groups = [[p for p in pins if p.split(".")[0] == prefix] for prefix in prefixes]
        facts[wtype] = {
            "pins": pins,
            "groups": [g for g in groups if len(g) > 1],
            "interchangeable": card.get("symmetric_pins", []),
            "polarized": bool(card.get("polarized")),
            "placed_together": bool(card.get("legs_placed_together")),
            "straddles_gap": bool(card.get("straddles_center_gap")),
            "display_name": card["display_name"].split(" (")[0] if card.get("subtype") != "resistor" else "Resistor",
            # Value-specific cards (220 Ω / 1 kΩ / 10 kΩ resistors) each describe
            # one particular use; the shared description fits the part itself.
            "how_to_use": card.get("description", "") if len(cards) > 1 else card.get("how_to_use", ""),
        }
    return facts


def part_pins(library=None):
    pins = {"wokwi-arduino-uno": UNO_PINS}
    pins.update({wtype: set(f["pins"]) for wtype, f in part_facts(library).items()})
    return pins


def facts_text(library=None):
    """The brief's "real parts" section, generated from the library."""
    lines = []
    for wtype, f in part_facts(library).items():
        lines.append(f"### {f['display_name']} — `{wtype}`")
        lines.append("Pins: " + "; ".join(f"`{p}` = {meaning}" for p, meaning in f["pins"].items()) + ".")
        for group in f["groups"]:
            lines.append(f"- {', '.join(group)} are ONE internal connection (the same metal): any of them works, "
                         "and they can never be separated.")
        for a, b in f["interchangeable"]:
            lines.append(f"- `{a}` and `{b}` are interchangeable: the part works identically either way round.")
        if f["polarized"]:
            lines.append("- Polarized: it only works one way round.")
        if f["placed_together"]:
            lines.append("- A single physical object: placing it seats ALL its legs at once. Give it exactly ONE "
                         "landing step (`expected_landing` = a list with at least one leg of each internal "
                         "connection), before any step that wires one of its legs.")
        else:
            lines.append("- Its legs can be placed one at a time; a leg's first wiring step can place it.")
        if f["straddles_gap"]:
            lines.append("- Must straddle the breadboard's centre gap: legs split between the top (a-e) and bottom "
                         "(f-j) halves. Legs of DIFFERENT internal connections must never share a column-half "
                         "(that shorts them together permanently).")
        else:
            lines.append("- Each leg in its own column-half: two legs of it in one column-half are shorted together.")
        lines.append(f"- How it's used: {f['how_to_use']}")
        lines.append("")
    return "\n".join(lines)

BRIEF = """You write lessons for CircuitQuest, a gamified tutor that walks a beginner
through building a real Arduino circuit step by step and checks their wiring
against your answer key. The app trusts your output as ground truth and
validates it automatically: the circuit, the steps, the code and the physics
must all agree, and the lesson must work for a real learner who builds step
by step, builds ahead, uses a different free pin, puts a part in the other
way round, or makes and fixes a mistake.

Return three things: `lesson_json`, `diagram_json` (both as JSON text) and
`code` (the Arduino sketch).

## 1. The Wokwi diagram (`diagram_json`)
The diagram is a Wokwi `diagram.json` describing the FINISHED circuit as it
physically sits on the desk:

{"version": 1, "author": "generated", "editor": "wokwi",
 "parts": [ {"type": "<wokwi type>", "id": "<instance id>", "top": 0, "left": 0,
             "rotate": 0, "attrs": {...}}, ... ],
 "connections": [ ["<pin A>", "<pin B>", "<wire colour>", []], ... ],
 "dependencies": {}}

- `top`/`left` (pixels) and `rotate` (degrees, optional) only position the
  drawing. They connect NOTHING. Electrical connections exist only as
  entries in `connections`.
- A connection is one physical contact: a component leg pushed into a
  breadboard hole (`["r1:1", "bb1:3b.h", "green", []]`), or a jumper wire
  between two holes or a hole and a board pin (`["bb1:3b.g", "uno:13", "red", []]`).
  Every leg that sits in the breadboard needs its own connection to the
  hole it's in, including parts that go in as one object.
- The 4th element is Wokwi's wire routing hints; always write `[]`.
- Wire colour is a plain colour name ("red", "black", "green", "blue",
  "yellow", "orange", "purple", "gray", "white"). Convention: red = 5V,
  black = GND, any other colour = signal. Colour has no electrical meaning.
- One hole holds one leg or one wire end. Use a fresh hole in the same
  column-half to add another connection to that column.

### The board: Arduino Uno — type `wokwi-arduino-uno`, id `uno`, library id `arduino-uno`
Pin names: `0`-`13` (digital; avoid `0` and `1`, they're the USB serial
port), `A0`-`A5` (analog inputs, also usable as digital), `5V`, `3.3V`,
`VIN`, `GND.1` (top header, next to pin 13), `GND.2` and `GND.3` (power
header). All GND pins are the same connection. The Uno sits beside the
breadboard; its pins are only ever reached by jumper wires. Parts are
never plugged into it.

### The breadboard — type `wokwi-breadboard-half`, id `bb1`, library id `breadboard`
- Holes are `bb1:<column><half>.<row>`: column `1`-`30`, half `t` (top,
  rows `a`-`e`) or `b` (bottom, rows `f`-`j`), e.g. `bb1:12t.c`,
  `bb1:12b.h`.
- The five holes of one column-half are ONE connection. The centre gap
  separates the halves: `12t` and `12b` are NOT connected.
- Power rails: `bb1:tp.<n>` / `bb1:tn.<n>` (top plus / minus) and
  `bb1:bp.<n>` / `bb1:bn.<n>` (bottom), numbered from 1. Every hole of one
  rail is one connection. A rail is optional: a direct wire from a column
  to the board pin is equally correct.

## 2. Real parts (from the parts library — treat them as physical objects)
Build the steps the way a person handles the real objects: pick a part up,
push its legs into the breadboard (one landing step for a part whose legs
all go in at once), then run wires. Each step is one physical action.
Only these part types exist. Resistors take `attrs.value` in ohms as a
string (e.g. "220"); LEDs take `attrs.color` ("red", "green", "yellow",
"blue", "white"). Instance ids: `led1`, `led2`…, `r1`…, `pot1`…, `btn1`…

{part_facts}

## 3. Real electronics (checked by a circuit solver)
- Every LED needs a series resistor: keep LED current 5-20 mA,
  (5 V − ~2 V) / R. 220 Ω is standard.
- Never connect 5V or an OUTPUT pin straight to GND.
- Every digital input needs a defined level: a pull-down resistor to GND
  (10 kΩ) or pinMode(pin, INPUT_PULLUP) with the button wired to GND.

## 4. The sketch (`code`) — written so the app can follow the learner's pin
If the learner wires a part to a different free pin (12 instead of 13, A1
instead of A0), the app rewrites the sketch to match. It does that
reliably only if you follow these rules:
- Declare each board pin ONCE, as a named constant whose name contains
  "Pin", and use that name everywhere:
  `const int ledPin = 13;` … `pinMode(ledPin, OUTPUT); digitalWrite(ledPin, HIGH);`
  (Writing the number directly inside pinMode/digitalWrite/digitalRead/
  analogRead/analogWrite also works, but a named constant is clearest.)
- Never compute a pin (`ledPin + 1`), store pins in an array, or pass a pin
  through your own helper function. The app can't follow those.
- For an EXTERNAL LED use its own constant (`const int ledPin = 13;`), not
  `LED_BUILTIN`. `LED_BUILTIN` means the Uno's on-board LED.
- Use only the pins the circuit uses, with a pinMode for every digital pin
  the sketch drives or reads (analogRead needs none).
- In comments, mention a pin as "pin 13".
- Keep the official tutorial's sketch when there is one, changing only what
  these rules require.

## 5. The lesson (`lesson_json`)
{"id": "<kebab-case>", "title": "...", "description": "...", "difficulty": "beginner",
 "board": "arduino-uno", "code": "code.ino", "wokwi_diagram": "diagram.json",
 "tools_used": [], "parts_used": [<library ids>], "steps": [...],
 "final_check": {"expected_nets": [...]}}
Steps, in order:
1. One gather step: {"id": "gather", "phase": "gather", "clip": "...", "items": [<library ids>]}.
2. Build steps, in physical order (place a part, then wire it). Every build
   step must ask for something new that the learner physically does in that
   step:
   - Landing (placing legs, no wire yet): {"id": "step-1a", "phase": "build", "clip": "...",
     "expected_landing": "r1:1" or a list of pins, "strict": false, "goal": "...", "hints": ["...", "..."]}.
     For a part that goes in as one object, list its legs in ONE landing step (see "Real parts").
   - Wiring: {"id": "step-1b", "phase": "build", "clip": "...",
     "expected_nets": [["r1:1", "uno:13"]], "strict": false, "goal": "...", "hints": [...]}.
     Nets name component or board pins only, never breadboard holes. Two legs sharing a
     column is still a wiring step: [["led1:A", "r1:2"]].
3. One upload step: {"id": "upload-code", "phase": "upload", "clip": "...", "code": "code.ino"}.
final_check.expected_nets = the union of every build step's expected_nets, and must
describe exactly the connections in diagram_json.
Step ids are unique.
Write for a complete beginner. Every build step has three texts:
- `clip` (beginner mode): one or two short, plain sentences saying exactly
  what to do with which part, which leg and where — "Put the LED's long leg
  in the same column as the resistor's other leg, and the short leg in an
  empty column." Name legs by what a beginner can see (long / short leg,
  middle leg, "either leg"), never by internal names ("group 1", "anode" alone,
  "contact pair"). Say breadboard places as numbered columns and the middle
  gap; never say "row" for a connection.
- `goal` (advanced mode, shown INSTEAD of the clip): only what to achieve,
  no how — "Connect the LED's long leg (+) to the free end of the resistor."
- `hints`: 1-2 short nudges. In advanced mode the app shows the first hint,
  then the full `clip` as the next hint, then the rest.
When a clip or hint names a board pin, write it as "pin 13" / "pin A0"
(optionally "pin <b>13</b>"). The app rewrites exactly that form if the
learner uses a different pin, so never refer to a pin any other way
("D13", "the 13 socket", or a bare "13").
Only use library ids from this list: {library_ids}

## 6. Before you answer, check
- Every part's every leg has a connection to its hole; every wire's ends are real pins/holes.
- No two legs of one part share a column-half unless the part card says they're one connection.
- final_check.expected_nets == union of build steps == the connections in diagram_json.
- Every pin the sketch uses is wired, declared once as a "...Pin" constant, and mentioned in prose as "pin N"."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "lesson_json": {"type": "string"},
        "diagram_json": {"type": "string"},
        "code": {"type": "string"},
    },
    "required": ["lesson_json", "diagram_json", "code"],
    "additionalProperties": False,
}

IDEAS_SCHEMA = {
    "type": "object",
    "properties": {
        "ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "concept": {"type": "string"},
                    "parts": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "description", "concept", "parts"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["ideas"],
    "additionalProperties": False,
}


class GeneratedLesson(Lesson):
    """A lesson held in memory (not yet on disk) so it can be validated
    through the real engine before being saved."""

    def __init__(self, data, diagram, code):
        super().__init__(data, LESSONS_ROOT / data.get("id", "generated"))
        self._diagram = diagram
        self._code = code

    def code_text(self):
        return self._code


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _net_set(pairs, alias_map, connectors):
    nets = [checker._drop_connectors(n, connectors) for n in checker.build_nets(pairs, alias_map)]
    return {frozenset(n) for n in nets if len(n) > 1}


def _check_structure(data, errors):
    for field in ("id", "title", "description", "steps", "final_check", "parts_used"):
        if field not in data:
            errors.append(f"lesson_json is missing required field '{field}'.")
    steps = data.get("steps") or []
    if not steps:
        return
    if steps[0].get("phase") != "gather":
        errors.append("The first step must be the gather step.")
    if steps[-1].get("phase") != "upload":
        errors.append("The last step must be the upload step.")
    ids = [s.get("id") for s in steps]
    if len(ids) != len(set(ids)):
        errors.append("Step ids must be unique.")
    # every expected connection is exactly two pins — a net of three or more is written as pairs
    nets = [(s.get("id"), n) for s in steps for n in (s.get("expected_nets") or [])]
    nets += [("final_check", n) for n in ((data.get("final_check") or {}).get("expected_nets") or [])]
    for where, net in nets:
        if not (isinstance(net, list) and len(net) == 2 and all(isinstance(x, str) and ":" in x for x in net)):
            errors.append(f"In '{where}', {json.dumps(net)} isn't a pair of two pins. Every expected_nets entry is exactly "
                          f"[\"part:pin\", \"part:pin\"]; to join three or more pins, write it as several pairs "
                          f"(e.g. [[\"a:1\", \"b:1\"], [\"b:1\", \"uno:2\"]]).")
    for step in steps:
        if step.get("phase") == "build":
            if not step.get("expected_nets") and not step.get("expected_landing"):
                errors.append(f"Build step '{step.get('id')}' has neither expected_nets nor expected_landing.")
            if not step.get("hints"):
                errors.append(f"Build step '{step.get('id')}' has no hints.")
        elif step.get("phase") not in ("gather", "upload"):
            errors.append(f"Step '{step.get('id')}' has unknown phase '{step.get('phase')}'.")


def _check_library(data, library, errors):
    ids = list(data.get("parts_used", [])) + list(data.get("tools_used", []))
    for step in data.get("steps", []):
        ids += step.get("items", [])
    for item in dict.fromkeys(ids):
        if library.get(item) is None or library.get(item)["id"] != item:
            errors.append(f"'{item}' is not a library id.")


def _check_pins(data, diagram, library, errors):
    types = {p["id"]: p.get("type") for p in diagram.get("parts", [])}
    PART_PINS = part_pins(library)

    def check(pin, where, allow_breadboard):
        if ":" not in pin:
            errors.append(f"{where}: '{pin}' isn't a component:pin name.")
            return
        comp, leg = pin.split(":", 1)
        if comp not in types:
            errors.append(f"{where}: '{comp}' isn't a part in diagram_json.")
        elif types[comp] in BREADBOARD_TYPES:
            if not allow_breadboard:
                errors.append(f"{where}: '{pin}' is a breadboard hole — nets name component or board pins only.")
        elif types[comp] in PART_PINS and leg not in PART_PINS[types[comp]]:
            errors.append(f"{where}: '{leg}' isn't a pin of {types[comp]} (valid: {sorted(PART_PINS[types[comp]])}).")
        elif types[comp] not in PART_PINS:
            errors.append(f"{where}: part type {types[comp]} isn't supported; use LEDs, resistors, potentiometers and pushbuttons.")

    for connection in diagram.get("connections", []):
        for pin in connection[:2]:
            check(pin, "diagram_json connection", True)
    for step in data.get("steps", []):
        for pair in step.get("expected_nets", []):
            for pin in pair:
                check(pin, f"step '{step.get('id')}'", False)
        landing = step.get("expected_landing")
        for pin in ([landing] if isinstance(landing, str) else landing or []):
            check(pin, f"step '{step.get('id')}' expected_landing", False)


def _landing_pins(step):
    landing = step.get("expected_landing")
    return [landing] if isinstance(landing, str) else list(landing or [])


def _check_physical_steps(data, diagram, library, errors):
    """Steps must follow how the real objects are handled: a part whose
    legs all go in at once gets exactly one landing step, covering every
    internal connection, before any step wires one of its legs."""
    facts = part_facts(library)
    types = {p["id"]: p.get("type") for p in diagram.get("parts", [])}
    for comp, wtype in types.items():
        f = facts.get(wtype)
        if not f or not f["placed_together"]:
            continue
        landings = [(i, s) for i, s in enumerate(data.get("steps", []))
                    if any(p.split(":", 1)[0] == comp for p in _landing_pins(s))]
        if len(landings) != 1:
            errors.append(f"{comp} ({f['display_name']}) goes into the breadboard as one object: it needs exactly one "
                          f"landing step listing its legs, not {len(landings)}.")
            continue
        index, step = landings[0]
        legs = {p.split(":", 1)[1] for p in _landing_pins(step) if p.split(":", 1)[0] == comp}
        units = f["groups"] + [[p] for p in f["pins"] if not any(p in g for g in f["groups"])]
        for unit in units:
            if not legs & set(unit):
                errors.append(f"Step '{step['id']}' places {comp} but doesn't list any of {', '.join(unit)} — "
                              "placing the part seats every leg, so the landing must cover each internal connection.")
        for earlier in data["steps"][:index]:
            used = [p for pair in earlier.get("expected_nets", []) for p in pair if p.split(":", 1)[0] == comp]
            if used:
                errors.append(f"Step '{earlier['id']}' wires {used[0]} before step '{step['id']}' has placed {comp}.")


def _check_diagram_placement(diagram, library, errors):
    """Where the diagram puts each leg must be physically possible: legs of
    different internal connections never share a column-half, and a
    gap-straddling part really spans the gap."""
    facts = part_facts(library)
    types = {p["id"]: p.get("type") for p in diagram.get("parts", [])}
    strip_of = {}
    for connection in diagram.get("connections", []):
        a, b = connection[0], connection[1]
        for pin, other in ((a, b), (b, a)):
            comp = pin.split(":", 1)[0]
            other_comp = other.split(":", 1)[0]
            if types.get(comp) in facts and types.get(other_comp) in BREADBOARD_TYPES:
                strip = other.split(":", 1)[1].split(".", 1)[0]
                strip_of.setdefault(comp, {})[pin.split(":", 1)[1]] = strip
    for comp, wtype in types.items():
        f = facts.get(wtype)
        if not f:
            continue
        connected = {pin.split(":", 1)[1] for c in diagram.get("connections", []) for pin in c[:2]
                     if pin.split(":", 1)[0] == comp}
        group_of = {p: i for i, g in enumerate(f["groups"]) for p in g}
        units = f["groups"] + [[p] for p in f["pins"] if p not in group_of]
        for unit in units:
            if not connected & set(unit):
                errors.append(f"In diagram_json, {comp}:{unit[0]} isn't in any connection — every leg in the "
                              f"breadboard needs a connection to its hole (e.g. [\"{comp}:{unit[0]}\", \"bb1:15t.c\", "
                              "\"black\", []]). A part's top/left position connects nothing.")
    for comp, legs in strip_of.items():
        f = facts[types[comp]]
        group_of = {p: i for i, g in enumerate(f["groups"]) for p in g}
        by_strip = {}
        for leg, strip in legs.items():
            by_strip.setdefault(strip, set()).add(group_of.get(leg, leg))
        for strip, units in by_strip.items():
            if len(units) > 1:
                errors.append(f"In diagram_json, {comp}'s legs {', '.join(sorted(l for l, s in legs.items() if s == strip))} "
                              f"share breadboard column-half {strip} — that shorts them together.")
        if f["straddles_gap"] and len(legs) > 1:
            halves = {strip[-1] for strip in legs.values() if strip[-1] in "tb"}
            if halves and halves != {"t", "b"}:
                errors.append(f"In diagram_json, {comp} must straddle the centre gap (legs in both the top and bottom halves).")


def _check_consistency(data, diagram, library, errors):
    alias_map = checker.board_alias_map(diagram.get("parts", []), library)
    connectors = checker.connector_ids(diagram.get("parts", []), library)
    step_pairs = [pair for s in data.get("steps", []) for pair in s.get("expected_nets", [])]
    final_pairs = data.get("final_check", {}).get("expected_nets", [])
    derived = _net_set(checker.derive_expected_nets(diagram, library), alias_map, connectors)
    if _net_set(step_pairs, alias_map, connectors) != _net_set(final_pairs, alias_map, connectors):
        errors.append("final_check.expected_nets isn't the union of the build steps' expected_nets.")
    if _net_set(final_pairs, alias_map, connectors) != derived:
        errors.append(
            "final_check.expected_nets doesn't match the connections in diagram_json. "
            f"The diagram's nets are: {sorted(sorted(n) for n in derived)}."
        )


def _check_code_followable(code, errors):
    """Every pin passed to a pin function must be something the app can
    rewrite when the learner uses a different pin: a number, A0-A5,
    LED_BUILTIN, or a constant declared with a literal."""
    constants = set(re.findall(r"(?:const\s+)?(?:unsigned\s+)?(?:int|byte|uint8_t|short|long)\s+(\w+)\s*=\s*A?\d+\s*;", code))
    constants |= set(re.findall(r"#define\s+(\w+)\s+A?\d+", code))
    arrays = engine.pin_arrays(code)
    for func, args in engine._CALL_RE.findall(code):
        parts = [a.strip() for a in args.split(",")]
        for i in engine.PIN_FUNCTION_ARGS[func]:
            if i >= len(parts) or not parts[i]:
                continue
            arg = parts[i]
            if re.fullmatch(r"A?\d+|LED_BUILTIN", arg) or arg in constants:
                continue
            if re.fullmatch(r"(\w+)\s*\[.*\]", arg) and re.match(r"\w+", arg).group(0) in arrays:
                continue                      # an element of a pin array: the app rewrites the array itself
            errors.append(f"The sketch passes `{arg}` as a pin to {func}(). Declare each pin once as a constant "
                          "(e.g. `const int ledPin = 13;`) and pass that name, so the app can follow a learner "
                          "who uses a different pin.")


def _check_code(diagram, code, errors):
    used = set(physics.pin_modes_from_code(code))
    used |= set(re.findall(r"digital(?:Read|Write)\s*\(\s*(A?\d+)", code))
    wired = {pin.split(":", 1)[1] for c in diagram.get("connections", []) for pin in c[:2] if pin.startswith("uno:")}
    for pin in sorted(used - wired):
        errors.append(f"The sketch uses pin {pin}, but nothing in diagram_json is wired to uno:{pin}.")
    if "void setup" not in code or "void loop" not in code:
        errors.append("The sketch must define setup() and loop().")
    _check_code_followable(code, errors)


def _check_physics(diagram, code, library, errors):
    result = physics.analyze([c[:2] for c in diagram.get("connections", [])], diagram.get("parts", []), code, library)
    for finding in result["findings"]:
        if finding["severity"] in ("hazard", "warning"):
            errors.append(f"Circuit physics: {finding['message']}")
    return result


def _check_engine(data, diagram, code, library, errors):
    """Run the lesson start to finish in the real engine: each build step
    passed with the engine's own 'correct' label, then the complete
    diagram wiring shown at final_check (which also re-runs physics)."""
    lesson = GeneratedLesson(data, diagram, code)
    state = engine.initial_state()
    pairs = [c[:2] for c in diagram.get("connections", [])]
    try:
        state, _ = engine.handle_event(lesson, library, state, {"command": "start"})
        for _ in range(len(lesson.steps) + 2):
            if state["finished"]:
                break
            event = {"command": "done", "detected_pairs": pairs} if state["phase"] == "final_check" else {"command": "done", "label": "correct"}
            step = lesson.step(state["step_index"])
            state, actions = engine.handle_event(lesson, library, state, event)
            wrong = [a for a in actions if a["type"] == "feedback" and a.get("verdict") == "wrong"]
            if wrong:
                detail = next((a["message"] for a in actions if a["type"] in ("substitution_refused", "physics_hazard")), "")
                errors.append(f"The engine rejects step '{step['id'] if step else 'final_check'}' even when built exactly as specified. {detail}".strip())
                return
    except Exception as exc:  # a malformed lesson must never crash generation
        errors.append(f"The engine couldn't run the lesson: {type(exc).__name__}: {exc}")
        return
    if not state["finished"]:
        errors.append("The engine didn't reach the end of the lesson.")


SCENARIO_HINTS = {
    "normal": "a learner following the steps exactly got stuck — check each step only asks for what's physically on the board by then, in the order a person would place parts and run wires",
    "build_ahead": "a learner who wires everything before the first check got stuck",
    "moved_pins": "a learner using a different free pin wasn't handled — declare each pin once (e.g. `const int ledPin = 13;`) and use that name everywhere, and write 'pin 13' when a clip mentions a pin",
    "turned_round": "a part that works either way round was rejected when turned round",
    "forgot_step": "a step passed even though the learner hadn't done it — each build step must ask for the new connection it adds",
    "wrong_pin": "a step accepted a wire on the wrong kind of pin",
    "reversed_part": "the lesson finished with an LED in backwards",
    "short_at_final": "a 5V-to-GND short at the end wasn't refused",
    "hints_and_back": "asking for hints or going back a step broke the lesson — every build step needs hints",
    "wire_comes_loose": "a connection an earlier step confirmed came loose and the lesson didn't notice, or couldn't continue once it was put back",
}


def _check_scenarios(data, diagram, code, library, errors):
    """The whole flow must work for a real learner exactly as it does in the
    hand-made lessons: step by step, building ahead, on a different pin,
    with parts turned round, after mistakes (core/scenarios.py)."""
    lesson = GeneratedLesson(data, diagram, code)
    try:
        for result in scenarios.run_scenarios(lesson, library):
            if not result["ok"]:
                errors.append(f"Learner scenario '{result['name']}' fails: {SCENARIO_HINTS.get(result['name'], '')}. "
                              f"Detail: {result['detail']}")
    except Exception as exc:  # never crash generation on a malformed lesson
        errors.append(f"The learner scenarios couldn't run: {type(exc).__name__}: {exc}")


def flow_check_mode():
    """"full" (every combination — the default, on your own machine) or
    "smart" (the covering sample — the hosted app sets CQ_FLOW_CHECK=smart,
    because a small shared CPU would take many minutes over the full set)."""
    return "smart" if os.environ.get("CQ_FLOW_CHECK", "").lower() == "smart" else "full"


def _check_flows(data, diagram, code, library, errors, max_reported=3):
    """Every learner run-flow (core/flow_explorer.py): every free pin, every
    orientation, built step by step or ahead, with a mistake at any step.
    Tracking, the shown code and the physics must hold in all of them."""
    lesson = GeneratedLesson(data, diagram, code)
    try:
        result = flow_explorer.explore(lesson, library, stop_after=max_reported, mode=flow_check_mode())
    except Exception as exc:
        errors.append(f"The run-flow check couldn't run: {type(exc).__name__}: {exc}")
        return
    for flow, problems in result["failures"]:
        errors.append(f"Run-flow {flow} breaks: {'; '.join(problems)}")


def validate(data, diagram, code, library=None):
    """Every check a playable lesson must pass. Returns a list of plain
    error strings, written to be sent straight back to the model. A check
    that crashes on unexpected input becomes one of those errors too — the
    model gets to fix its lesson instead of the whole generation failing."""
    try:
        return _validate(data, diagram, code, library)
    except Exception as exc:          # malformed output a check didn't anticipate
        return [f"The lesson made a check fail with {type(exc).__name__}: {exc}. Re-check its structure against the "
                f"schema: steps, expected_nets as pairs of \"part:pin\" strings, diagram parts and connections."]


def _validate(data, diagram, code, library=None):
    library = library or load_library()
    errors = []
    _check_structure(data, errors)
    if errors:
        return errors
    _check_library(data, library, errors)
    _check_pins(data, diagram, library, errors)
    if errors:
        return errors   # later checks assume known parts and pins
    _check_consistency(data, diagram, library, errors)
    _check_physical_steps(data, diagram, library, errors)
    _check_diagram_placement(diagram, library, errors)
    _check_code(diagram, code, errors)
    _check_physics(diagram, code, library, errors)
    if errors:
        return errors
    _check_engine(data, diagram, code, library, errors)
    if errors:
        return errors
    _check_scenarios(data, diagram, code, library, errors)
    if errors:
        return errors
    _check_flows(data, diagram, code, library, errors)
    return errors


# ---------------------------------------------------------------------------
# Calling the model
# ---------------------------------------------------------------------------

class AIUnavailable(RuntimeError):
    """No way to reach Claude from this machine (or the login failed)."""


CLAUDE_CODE_MODEL = "opus"          # the CLI's alias for its latest Opus
CLAUDE_CODE_TIMEOUT = 900           # seconds: a full lesson with thinking takes a while


def _api_ready():
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def backend():
    """"api", "claude-code" or None — how this machine can reach Claude."""
    forced = os.environ.get("CQ_AI_BACKEND")
    if forced == "none":            # test servers: never spend anyone's Claude usage
        return None
    if forced in ("api", "claude-code"):
        return forced
    if _api_ready():
        return "api"
    if shutil.which("claude"):
        return "claude-code"
    return None


def _flatten(messages):
    """The CLI takes one prompt: fold the repair conversation into it."""
    if len(messages) == 1:
        return messages[0]["content"]
    parts = [messages[0]["content"]]
    for m in messages[1:]:
        if m["role"] == "assistant":
            parts.append("Your previous answer was:\n" + m["content"])
        else:
            parts.append(m["content"])
    return "\n\n---\n\n".join(parts)


def _call_claude_code(system, messages, schema, run=subprocess.run):
    """One structured-output request through the local `claude` CLI (the
    user's own Claude Code login). Returns (parsed JSON dict, raw text)."""
    exe = shutil.which("claude")
    if not exe:
        raise AIUnavailable("Claude Code isn't installed on this machine.")
    cmd = [exe, "-p", "--output-format", "json", "--json-schema", json.dumps(schema),
           "--system-prompt", system, "--tools", "", "--no-session-persistence",
           "--model", os.environ.get("CQ_CLAUDE_MODEL", CLAUDE_CODE_MODEL)]
    try:
        # run outside the project so no project settings/CLAUDE.md leak into the brief
        proc = run(cmd, input=_flatten(messages), capture_output=True, text=True,
                   timeout=CLAUDE_CODE_TIMEOUT, cwd=tempfile.gettempdir())
    except subprocess.TimeoutExpired:
        raise RuntimeError("Claude took too long to answer — try again.")
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        detail = (proc.stderr or proc.stdout or "").strip()[:300]
        if "login" in detail.lower() or "auth" in detail.lower():
            raise AIUnavailable(f"Claude Code isn't logged in: {detail}")
        raise RuntimeError(f"Claude Code returned something unreadable: {detail}")
    if out.get("is_error") or "structured_output" not in out:
        detail = str(out.get("result") or out.get("subtype") or "unknown error")[:300]
        if any(w in detail.lower() for w in ("login", "api key", "auth", "credit", "usage limit", "rate limit")):
            raise AIUnavailable(f"Claude Code couldn't answer: {detail}")
        raise RuntimeError(f"Claude Code couldn't answer: {detail}")
    data = out["structured_output"]
    return data, json.dumps(data)


# A learner's own Anthropic API key for this request (hosted app, accounts
# on): when set, every Claude call in this request uses it and nothing else.
_user_key = contextvars.ContextVar("claude_user_key", default=None)


@contextlib.contextmanager
def using_key(api_key):
    token = _user_key.set(api_key)
    try:
        yield
    finally:
        _user_key.reset(token)


def _call_model(system, messages, schema):
    """The learner's own key if they connected one, else whichever backend this machine has."""
    if _user_key.get():
        import anthropic
        return _call_claude(system, messages, schema, client=anthropic.Anthropic(api_key=_user_key.get()))
    which = backend()
    if which == "api":
        return _call_claude(system, messages, schema)
    if which == "claude-code":
        return _call_claude_code(system, messages, schema)
    raise AIUnavailable("No way to reach Claude: log in to Claude Code (run `claude` once) "
                        "or install the Anthropic SDK and set ANTHROPIC_API_KEY.")


def _client():
    import anthropic   # lazy: only generation needs the SDK
    return anthropic.Anthropic()


def _call_claude(system, messages, schema, client=None):
    """One structured-output request. Returns (parsed JSON dict, raw text)."""
    import anthropic
    client = client or _client()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": schema}},
        system=system,
        messages=messages,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("The model declined to generate this lesson.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("The lesson was too long to generate in one response.")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text), text


def _system_prompt(library):
    ids = ", ".join(c for c in library.all_ids() if library.cards[c].get("type") in ("part", "tool"))
    return BRIEF.replace("{library_ids}", ids).replace("{part_facts}", facts_text(library))


def _request_text(request, inventory):
    text = f"Write a lesson for: {request}"
    if inventory:
        text += "\n\nThe learner owns only these parts (library ids); use nothing else: " + ", ".join(inventory)
    return text


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "lesson"


def generate_lesson(request, inventory=None, library=None, generate_fn=None, max_attempts=MAX_ATTEMPTS, save=True,
                    extra_check=None, extra_data=None):
    """Generate → validate → repair, up to `max_attempts` model calls.

    `generate_fn(system, messages) -> (dict, raw_text)` defaults to a real
    Claude call; tests pass a fake. Returns {"ok", "lesson_id", "attempts":
    [{"errors": [...]}], "errors"} and, when ok and `save`, writes
    lessons/<lesson_id>/{lesson.json, diagram.json, code.ino}.

    `extra_check(data, diagram) -> [errors]` adds a caller's own rule (e.g.
    guide_import: exactly the guide's parts); `extra_data` is merged into the
    saved lesson.json (e.g. where the lesson came from)."""
    library = library or load_library()
    generate_fn = generate_fn or (lambda system, messages: _call_model(system, messages, OUTPUT_SCHEMA))
    system = _system_prompt(library)
    messages = [{"role": "user", "content": _request_text(request, inventory)}]
    attempts = []
    for _ in range(max_attempts):
        output, raw = generate_fn(system, messages)
        try:
            data = json.loads(output["lesson_json"])
            diagram = json.loads(output["diagram_json"])
            code = output["code"]
            errors = validate(data, diagram, code, library)
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
            errors = [f"The output couldn't be parsed: {type(exc).__name__}: {exc}"]
        if not errors and extra_check:
            errors = extra_check(data, diagram)
        if not errors and inventory:
            extra = [p for p in data.get("parts_used", []) if p not in inventory]
            if extra:
                errors = [f"The lesson uses parts the learner doesn't own: {', '.join(extra)}."]
        attempts.append({"errors": errors})
        if not errors:
            lesson_id = _free_id("gen-" + _slug(data.get("id") or data.get("title", "lesson")))
            data = {**data, "id": lesson_id, "generated": True, "requires": [],
                    "code": "code.ino", "wokwi_diagram": "diagram.json", **(extra_data or {})}
            if save:
                _save(lesson_id, data, diagram, code)
            return {"ok": True, "lesson_id": lesson_id, "attempts": attempts, "errors": []}
        messages += [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "The lesson failed validation. Fix every problem and return the full corrected output:\n- " + "\n- ".join(errors)},
        ]
    return {"ok": False, "lesson_id": None, "attempts": attempts, "errors": attempts[-1]["errors"]}


def _free_id(base):
    """Never overwrite someone's lesson: gen-traffic-light, then -2, -3 …"""
    lesson_id, n = base, 2
    while (LESSONS_ROOT / lesson_id).exists():
        lesson_id, n = f"{base}-{n}", n + 1
    return lesson_id


def _save(lesson_id, data, diagram, code):
    folder = LESSONS_ROOT / lesson_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "lesson.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    (folder / "diagram.json").write_text(json.dumps(diagram, indent=2) + "\n")
    (folder / "code.ino").write_text(code if code.endswith("\n") else code + "\n")


def suggest_ideas(inventory, library=None, generate_fn=None, count=5):
    """Ask the model for lesson ideas buildable from the learner's parts.
    Ideas naming parts outside the inventory are dropped. Pick one and
    pass its description to generate_lesson."""
    library = library or load_library()
    generate_fn = generate_fn or (lambda system, messages: _call_model(system, messages, IDEAS_SCHEMA))
    names = [f"{i} ({library.get(i)['display_name']})" for i in inventory if library.get(i)]
    system = ("You suggest beginner Arduino Uno projects for CircuitQuest, a gamified electronics tutor. "
              "Each idea must be buildable with ONLY the listed parts (library ids), teach one clear "
              "concept, and use only LEDs, resistors, potentiometers and pushbuttons besides the board, "
              "breadboard, wires and USB cable.")
    messages = [{"role": "user", "content": f"Parts I have: {', '.join(names)}. Suggest {count} different projects, simplest first."}]
    output, _ = generate_fn(system, messages)
    owned = set(inventory)
    return [idea for idea in output.get("ideas", []) if set(idea.get("parts", [])) <= owned]
