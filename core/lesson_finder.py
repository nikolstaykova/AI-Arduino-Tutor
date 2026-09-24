""""I have these parts — what can I build?" (PLAN.md Phase 5b).

Matches a learner's parts inventory against every lesson's `parts_used`.
A missing part doesn't automatically rule a lesson out: if the learner
owns a part of the same kind with a different value (a 220 Ω resistor
where the lesson says 1 kΩ), the lesson's own reference circuit is
re-solved with that value (core/physics.py). The substitute is accepted
only if nothing becomes a hazard or a new warning, and the learner is
told what changes ("led1: 2.9 mA → 11.8 mA, brighter"). Real electronics,
not an exact-match shopping list.

Quantities aren't tracked yet (one card = "I have some"); a lesson that
needs two resistors is satisfied by owning that resistor at all.
"""
import copy

from . import build_methods, physics
from .lesson import LESSONS_ROOT, load_lesson
from .library import load_library

# Kinds of part where a different value of the same kind can stand in.
SUBSTITUTABLE_SUBTYPES = {"resistor"}


def resolve_inventory(names, library=None):
    """Free-text names/aliases/ids → (library ids, unrecognised names)."""
    library = library or load_library()
    ids, unknown = [], []
    for name in names:
        text = str(name).strip()
        # "usb cable" → the "usb-cable" id, when it isn't a listed alias.
        card = library.get(text) or library.get("-".join(text.lower().split()))
        if card is None:
            unknown.append(name)
        elif card["id"] not in ids:
            ids.append(card["id"])
    return ids, unknown


def all_lesson_ids():
    return sorted(p.parent.name for p in LESSONS_ROOT.glob("*/lesson.json"))


def _reference(lesson):
    diagram = lesson.diagram()
    code = (lesson.folder / lesson.data["code"]).read_text()
    return [c[:2] for c in diagram["connections"]], diagram["parts"], code


def _summary(result):
    """Per-component numbers worth comparing before/after a substitution."""
    out = {}
    for scenario in result["scenarios"]:
        for led_id, led in scenario["leds"].items():
            out[(scenario["label"], led_id)] = ("led", led["state"], led["current_ma"])
        for pin, info in scenario["pins"].items():
            if "reading" in info:
                out[(scenario["label"], pin)] = ("reading", info["reading"], None)
            elif info["mode"] == "SUPPLY":
                out[(scenario["label"], pin)] = ("supply", None, info["current_ma"])
    return out


def _try_substitute(lesson, library, need_card, have_card):
    """Re-solve the lesson's reference circuit with `have_card`'s value in
    place of `need_card`'s. Returns a note string if it still works, else
    None."""
    pairs, parts, code = _reference(lesson)
    baseline = physics.analyze(pairs, parts, code, library)
    swapped = copy.deepcopy(parts)
    targets = [p for p in swapped if need_card in library.find_by_wokwi_type(p.get("type"), p.get("attrs", {}).get("value"))]
    if not targets:
        # parts_used and the diagram disagree on the value (it happens in
        # hand-authored lessons) — fall back to every part of that kind.
        wanted_types = need_card["wokwi_type"] if isinstance(need_card["wokwi_type"], list) else [need_card["wokwi_type"]]
        targets = [p for p in swapped if p.get("type") in wanted_types]
    if not targets:
        return None
    for part in targets:
        part.setdefault("attrs", {})["value"] = have_card["wokwi_value"]
    after = physics.analyze(pairs, swapped, code, library)

    if after["hazard"]:
        return None
    old_warnings = {(f["kind"], f["component"]) for f in baseline["findings"] if f["severity"] != "info"}
    if any((f["kind"], f["component"]) not in old_warnings for f in after["findings"] if f["severity"] != "info"):
        return None
    before, now = _summary(baseline), _summary(after)
    if any(before[k][0] == "reading" and now.get(k, (None, None))[1] != before[k][1] for k in before):
        return None   # an input would read differently: the lesson wouldn't behave the same

    changes = []
    for key, (kind, state, ma) in now.items():
        if key not in before or kind not in ("led", "supply"):
            continue
        old_ma = before[key][2]
        if abs(ma - old_ma) < 0.05:
            continue
        scenario = "" if key[0] == "steady state" else f" while {key[0]}"
        if kind == "led":
            trend = "brighter, still safe" if ma > old_ma else ("dimmer, barely visible" if state == "dim" else "dimmer")
            changes.append(f"{key[1]}: {old_ma:.1f} mA → {ma:.1f} mA ({trend})")
        else:
            changes.append(f"{key[1]} supplies {old_ma:.1f} mA → {ma:.1f} mA{scenario}")
    note = f"use your {have_card['display_name']} instead of the {need_card['display_name']}"
    return note + (" — " + "; ".join(changes) if changes else " — the circuit behaves the same")


def _classify(lesson, library, owned, needed):
    """(missing, substitutes) for a parts list against what's owned."""
    missing, substitutes = [], []
    for part_id in needed:
        if part_id in owned:
            continue
        need_card = library.get(part_id)
        note = None
        if need_card and need_card.get("subtype") in SUBSTITUTABLE_SUBTYPES:
            for have_id in sorted(owned):
                have_card = library.get(have_id)
                if have_card and have_card.get("subtype") == need_card["subtype"] and "wokwi_value" in have_card:
                    note = _try_substitute(lesson, library, need_card, have_card)
                    if note:
                        substitutes.append({"need": part_id, "use": have_id, "note": note})
                        break
        if not note:
            missing.append(part_id)
    return missing, substitutes


def find_lessons(inventory_ids, library=None, lesson_ids=None, progress=None):
    """Every lesson, classified against the inventory:
      "ready"      — every part owned;
      "substitute" — buildable by swapping in owned parts (physics-checked);
      "missing"    — still needs the listed parts.
    Each lesson is tried every way it can be built (core/build_methods:
    breadboard, or no breadboard with clip leads / twisted legs / solder)
    and classified by its best way; `build` names that way and `ways`
    lists them all with what each still needs.
    Sorted ready → substitute → fewest missing."""
    library = library or load_library()
    owned = set(inventory_ids)
    results = []
    for lesson_id in lesson_ids or all_lesson_ids():
        lesson = load_lesson(lesson_id)
        # every way to build it: on a breadboard, or without one (clip
        # leads / twisted legs / solder) — each has its own parts + tools
        ways = []
        for p in build_methods.all_plans(lesson, library):
            missing, substitutes = _classify(lesson, library, owned, p["parts"])
            missing += [t for t in p["tools"] if t not in owned]
            ways.append({"method": p["method"], "join": p["join"], "missing": missing,
                         "substitutes": substitutes, "extra": p["changes"]["added"] + p["changes"]["tools_added"]})
        best = min(ways, key=lambda w: (len(w["missing"]), bool(w["substitutes"]), w["method"] != "breadboard"))
        # a breadboard build that's already fine stays the headline
        missing, substitutes = best["missing"], best["substitutes"]
        status = "missing" if missing else ("substitute" if substitutes else "ready")
        entry = {"id": lesson_id, "title": lesson.title, "status": status,
                 "missing": missing, "substitutes": substitutes,
                 "build": {"method": best["method"], "join": best["join"]}, "ways": ways}
        if progress is not None:
            from .progress import unlocked
            entry["unlocked"] = unlocked(lesson.data, progress)
        results.append(entry)
    order = {"ready": 0, "substitute": 1, "missing": 2}
    return sorted(results, key=lambda r: (order[r["status"]], len(r["missing"]), r["id"]))
