"""Score an LLM-generated lesson against the hand-made one for the same tutorial.

    python3 experiments/sonnet-lesson-gen/evaluate.py <run_dir> <reference_lesson_id>

Checks, in order:
1. validate   — core.lesson_gen.validate: every check a playable lesson must
                pass (structure, library ids, pin names, physical part
                placement, step/final/diagram consistency, sketch pins,
                physics, a full engine dry run).
2. equivalent — the same circuit as the reference: some mapping of instance
                ids (same Wokwi type), plus each part either way round where
                its card says that's interchangeable, makes the two
                diagrams' nets identical. Board pins compare by kind
                (digital / analog / 5V / 3.3V / GND), so pin 12 vs 13 or
                GND.1 vs GND.2 don't count as differences.
3. behaves    — both circuits solved by core.physics: same LED states and
                currents (±0.05 mA) and the same input readings, per
                button state.
4. cross-play — the reference's real physical wiring (renamed into the
                generated lesson's ids), shown at every build step and at
                final_check, must complete the generated lesson: a learner
                who built the real circuit passes.
5. adapts     — the same, with every Arduino signal pin moved to a different
                free pin of the same kind (13 → 12, A0 → A1, 2 → 3). Since
                final_check compares the circuit's behaviour with the code
                the learner will upload, finishing means the lesson's sketch
                really follows the learner's pin choice.
"""
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import checker, engine, physics  # noqa: E402
from core.lesson import load_lesson  # noqa: E402
from core.lesson_gen import GeneratedLesson, part_facts, validate  # noqa: E402
from core.library import load_library  # noqa: E402

LIBRARY = load_library()
BOARD_TYPES = {"wokwi-arduino-uno"}


def _parts(diagram):
    return {p["id"]: p.get("type") for p in diagram["parts"]
            if p.get("type") not in BOARD_TYPES and "breadboard" not in p.get("type", "")}


def _pin_kind(pin, board_ids):
    comp, leg = pin.split(":", 1)
    if comp not in board_ids:
        return pin
    if leg.startswith("GND"):
        return "board:GND"
    if leg in ("5V", "3.3V", "VIN"):
        return f"board:{leg}"
    return "board:analog" if leg.startswith("A") else "board:digital"


def _nets(diagram):
    parts = diagram["parts"]
    alias = checker.board_alias_map(parts, LIBRARY)
    conn = checker.connector_ids(parts, LIBRARY)
    board_ids = {p["id"] for p in parts if p.get("type") in BOARD_TYPES}
    nets = [checker._drop_connectors(n, conn) for n in checker.build_nets([c[:2] for c in diagram["connections"]], alias)]
    return [frozenset(_pin_kind(p, board_ids) for p in n) for n in nets if len(n) > 1]


def _rename(pin, mapping, swaps, facts, types):
    comp, leg = pin.split(":", 1)
    if comp not in mapping:
        return pin
    if comp in swaps:
        leg = checker._swap_pin(pin, comp, facts[types[comp]]["interchangeable"]).split(":", 1)[1]
    return f"{mapping[comp]}:{leg}"


def equivalence(gen_diagram, ref_diagram):
    """Returns the {gen_id: ref_id} mapping that makes the circuits
    identical, or None."""
    facts = part_facts(LIBRARY)
    gen_types, ref_types = _parts(gen_diagram), _parts(ref_diagram)
    if sorted(gen_types.values()) != sorted(ref_types.values()):
        return None
    ref_nets = set(_nets(ref_diagram))
    gen_nets = _nets(gen_diagram)
    gen_ids = sorted(gen_types)
    swappable = [c for c in gen_ids if facts.get(gen_types[c], {}).get("interchangeable")]
    for perm in itertools.permutations(sorted(ref_types)):
        mapping = dict(zip(gen_ids, perm))
        if any(gen_types[g] != ref_types[r] for g, r in mapping.items()):
            continue
        for k in range(len(swappable) + 1):
            for swaps in itertools.combinations(swappable, k):
                renamed = {frozenset(_rename(p, mapping, swaps, facts, gen_types) for p in n) for n in gen_nets}
                if renamed == ref_nets:
                    return mapping
    return None


def _physics_summary(diagram, code, id_map=None):
    result = physics.analyze([c[:2] for c in diagram["connections"]], diagram["parts"], code, LIBRARY)
    id_map = id_map or {}
    out = {}
    for s in result["scenarios"]:
        label = s["label"]
        for gid, rid in id_map.items():
            label = label.replace(gid, rid)
        for led, info in s["leds"].items():
            out[(label, id_map.get(led, led))] = (info["state"], info["current_ma"])
        for pin, info in s["pins"].items():
            if "reading" in info:
                out[(label, "input")] = info["reading"]
    return out, result


def behaves_the_same(gen_diagram, gen_code, ref_diagram, ref_code, mapping):
    gen, _ = _physics_summary(gen_diagram, gen_code, mapping)
    ref, _ = _physics_summary(ref_diagram, ref_code)
    diffs = []
    for key in sorted(set(gen) | set(ref), key=str):
        a, b = gen.get(key), ref.get(key)
        if isinstance(a, tuple) and isinstance(b, tuple):
            if a[0] != b[0] or abs(a[1] - b[1]) > 0.05:
                diffs.append(f"{key}: generated {a} vs reference {b}")
        elif a != b:
            diffs.append(f"{key}: generated {a} vs reference {b}")
    return diffs


MOVE_PIN = {"13": "12", "2": "3", "A0": "A1"}


def cross_play(gen_data, gen_diagram, gen_code, ref_diagram, mapping, move_pins=False):
    """The reference's physical wiring, renamed into the generated ids,
    shown at every check of the generated lesson. With move_pins, every
    signal pin in MOVE_PIN is moved to its neighbour first."""
    inverse = {r: g for g, r in mapping.items()}
    gen_bb = next((p["id"] for p in gen_diagram["parts"] if "breadboard" in p["type"]), None)
    ref_bb = next((p["id"] for p in ref_diagram["parts"] if "breadboard" in p["type"]), None)
    if ref_bb:
        inverse[ref_bb] = gen_bb or ref_bb
    # A half/mini breadboard reference fits any generated breadboard as-is.
    def leg(p):
        comp, name = p.split(":", 1)
        if move_pins and comp == "uno":
            name = MOVE_PIN.get(name, name)
        return f"{inverse.get(comp, comp)}:{name}"
    wiring = [[leg(p) for p in c[:2]] for c in ref_diagram["connections"]]
    lesson = GeneratedLesson(gen_data, gen_diagram, gen_code)
    state = engine.initial_state()
    state, _ = engine.handle_event(lesson, LIBRARY, state, {"command": "start"})
    notes = []
    for _ in range(len(lesson.steps) + 2):
        if state["finished"]:
            break
        # The learner's real, finished board is shown at every check (not
        # the lesson's own "correct" label), so the history is physically
        # coherent: a part turned round relative to the generated lesson
        # stays turned round from its first step to final_check.
        event = ({"command": "done"} if state["phase"] in ("gather", "upload")
                 else {"command": "done", "detected_pairs": wiring})
        state, actions = engine.handle_event(lesson, LIBRARY, state, event)
        for a in actions:
            if a["type"] in ("pin_substituted", "physics_hazard", "substitution_refused"):
                notes.append(a["message"])
        if any(a["type"] == "feedback" and a.get("verdict") == "wrong" for a in actions):
            return False, notes or ["final_check rejected the reference wiring"]
    return state["finished"], notes


def evaluate(run_dir, ref_id):
    run_dir = Path(run_dir)
    data = json.loads((run_dir / "lesson.json").read_text())
    diagram = json.loads((run_dir / "diagram.json").read_text())
    code = (run_dir / "code.ino").read_text()
    ref = load_lesson(ref_id)
    report = {"run": run_dir.name, "reference": ref_id}
    report["validate_errors"] = validate(data, diagram, code, LIBRARY)
    mapping = equivalence(diagram, ref.diagram())
    report["equivalent"] = mapping is not None
    report["mapping"] = mapping
    if mapping:
        report["behaviour_diffs"] = behaves_the_same(diagram, code, ref.diagram(), ref.code_text(), mapping)
        ok, notes = cross_play(data, diagram, code, ref.diagram(), mapping)
        report["cross_play"] = ok
        report["cross_play_notes"] = notes
        ok, notes = cross_play(data, diagram, code, ref.diagram(), mapping, move_pins=True)
        report["adapts"] = ok
        report["adapts_notes"] = notes
    parts = {p["id"]: (p["type"], p.get("attrs", {})) for p in diagram["parts"]}
    report["parts"] = {k: f"{t.replace('wokwi-', '')} {a.get('value', a.get('color', ''))}".strip() for k, (t, a) in parts.items()}
    report["steps"] = [f"{s['id']}: " + (f"land {s['expected_landing']}" if "expected_landing" in s else
                                          f"wire {s['expected_nets']}" if "expected_nets" in s else s["phase"])
                       for s in data["steps"]]
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate(sys.argv[1], sys.argv[2]), indent=2, ensure_ascii=False))
