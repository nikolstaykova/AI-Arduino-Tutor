"""Deterministic net comparison — no AI (PLAN.md Phase 5).

Expected/detected nets are lists of [pinA, pinB] component-pin pairs
(e.g. ["pot1:GND", "uno:GND.1"]) — independent of which physical hole/strip
realized the connection. `derive_expected_nets` performs that reduction
programmatically from a raw Wokwi diagram (breadboard hops and all), so a
lesson's expected_nets can be generated from — or cross-checked against —
the actual authored diagram.json, instead of a human doing the reduction
by hand (which is exactly how the GND.1 vs. GND.3 mismatch happened; see
the research log (in git history)). The same board/breadboard pin-canonicalization rules
are also applied at check() time, so this isn't only an authoring-time
convenience — it's the same equivalence the checker itself relies on for
every comparison.

This module carries NO per-board or per-part electrical facts of its own
— those live in each part's library JSON card (`pin_aliases`,
`connector_only`; see PARTS.md), looked up here by Wokwi type/value the
same way engine._symmetric_map already looks up `symmetric_pins`. Keeping
this data in JSON instead of a hardcoded Python table (the original
design, kept as BOARD_PIN_ALIAS_RULES/CONNECTOR_ONLY_TYPES through this
project's first ~60 fixes) means a genuinely huge hardware catalog
(docs.wokwi.com/getting-started/supported-hardware lists 60+ parts across
10+ microcontroller families) can grow without this module's own code
ever changing — the algorithms here are generic; only the data describing
a specific board/part lives elsewhere.

This module adds one more kind of equivalence on top of alias-folding:
symmetric pin pairs on a single component (e.g. a potentiometer's GND/VCC
outer legs, or a resistor's two non-polarized legs — genuinely
interchangeable, but a genuine per-instance CHOICE unlike a board's fixed
pin-alias fact). A symmetric swap is classified as "harmless", not
silently identical to an exact match and not "wrong" — see PLAN.md
Phase 5/6. (Also library-JSON-driven already, via `symmetric_pins` —
see engine._symmetric_map.)
"""
from .library import load_library


def _canonicalize_pin(pin, alias_map):
    """alias_map: {component_instance_id: rule_dict}. Folds e.g.
    'uno:GND.3' -> 'uno:GND', or 'bb2:6b.f' -> 'bb2:6b', so pins that are
    the same net by hardware/breadboard-geometry design compare equal
    without needing to be explicitly connected together in the pairs list.
    Applied identically to expected and detected pairs."""
    if not alias_map or ":" not in pin:
        return pin
    comp, leg = pin.split(":", 1)
    rule = alias_map.get(comp)
    if not rule:
        return pin
    if rule["mode"] == "prefix":
        for prefix in rule["prefixes"]:
            if leg.startswith(prefix):
                return f"{comp}:{prefix}"
        return pin
    if rule["mode"] == "strip":
        strip_id = leg.split(".", 1)[0]
        return f"{comp}:{strip_id}"
    return pin


def board_alias_map(diagram_parts, library=None):
    """Build {instance_id: rule_dict} from a Wokwi diagram's `parts` array,
    looking up each part's `pin_aliases` field from its library card (found
    by wokwi_type/value, the same matching engine._symmetric_map already
    uses for `symmetric_pins`) — not a hardcoded per-type table, so this
    module carries no per-board/per-part electrical facts of its own.
    `library` defaults to the real, on-disk library when not given, so
    every existing caller that doesn't have one handy still resolves
    against the actual part data. One dict, reusable for both expected
    and detected pairs in a given lesson."""
    if library is None:
        library = load_library()
    alias_map = {}
    for part in diagram_parts:
        wtype = part.get("type")
        value = part.get("attrs", {}).get("value")
        for card in library.find_by_wokwi_type(wtype, value):
            rule = card.get("pin_aliases")
            if rule:
                alias_map[part["id"]] = rule
                break
    return alias_map


def derive_expected_nets(diagram, library=None):
    """Turn a raw Wokwi diagram (parts + connections, breadboard hops and
    all) into component-pin-only expected_nets — the same reduction a
    lesson author currently has to do by hand when writing lesson.json.
    Doing it here instead means expected_nets can be generated from (or
    cross-checked against) the actual authored/validated diagram.json,
    rather than being an independently hand-maintained parallel structure
    that can silently drift out of sync with it.
    """
    if library is None:
        library = load_library()
    parts = diagram.get("parts", [])
    connections = diagram.get("connections", [])
    alias_map = board_alias_map(parts, library)
    connector_component_ids = connector_ids(parts, library)

    raw_pairs = [[c[0], c[1]] for c in connections]
    nets = [_drop_connectors(n, connector_component_ids) for n in build_nets(raw_pairs, alias_map)]

    expected_nets = []
    for net in nets:
        real_pins = sorted(net)
        if len(real_pins) < 2:
            continue  # a net with 0-1 real endpoints connects nothing observable
        # a simple chain is enough to reconstruct this exact grouping via
        # union-find later; which specific pairing is used doesn't matter.
        for a, b in zip(real_pins, real_pins[1:]):
            expected_nets.append([a, b])
    return expected_nets


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def groups(self):
        result = {}
        for node in list(self.parent):
            root = self.find(node)
            result.setdefault(root, set()).add(node)
        return list(result.values())


def build_nets(pairs, alias_map=None):
    """pairs: list of [pinA, pinB]. Returns list of frozensets (nets), with
    any board pin-aliases (e.g. every GND pin on the Uno) already folded
    together — see each part's own `pin_aliases` library field."""
    uf = UnionFind()
    for a, b in pairs:
        uf.union(_canonicalize_pin(a, alias_map), _canonicalize_pin(b, alias_map))
    return [frozenset(g) for g in uf.groups()]


def connector_ids(diagram_parts, library=None):
    """Instance ids whose library card declares `connector_only: true` — a
    breadboard's own pins are never a real endpoint, only ever a
    pass-through. Used to strip them back out of a net after union-find,
    so a connection realized through a breadboard (or a *different*
    breadboard, or no breadboard at all) compares equal to the same
    connection realized any other way. Without this, union-find correctly
    merges e.g. {pot1:GND, bb2:6b, uno:GND} into one net, but that net can
    then never exactly equal the expected {pot1:GND, uno:GND} — the leftover
    breadboard node makes every breadboard-routed connection look "wrong"
    even when it's exactly right (caught via a realistic hole-level mimic
    detection test; see the research log (in git history)). `library` defaults to the real,
    on-disk library, same as board_alias_map."""
    if library is None:
        library = load_library()
    ids = set()
    for part in diagram_parts:
        wtype = part.get("type")
        value = part.get("attrs", {}).get("value")
        for card in library.find_by_wokwi_type(wtype, value):
            if card.get("connector_only"):
                ids.add(part["id"])
                break
    return ids


def _drop_connectors(net, connector_component_ids):
    if not connector_component_ids:
        return net
    return frozenset(pin for pin in net if pin.split(":", 1)[0] not in connector_component_ids)


def _swap_pin(pin, component_id, symmetric_pairs):
    """pin like 'pot1:GND'. Swap the leg name if it's part of a symmetric pair
    on this specific component instance. A symmetric pair can also name a
    whole internally-connected contact GROUP: the pushbutton's
    [["1", "2"]] swaps group 1 with group 2, so a physical leg like
    'btn1:1.r' becomes 'btn1:2.r' (same side, other group) — a real
    momentary switch works identically either way round."""
    if ":" not in pin:
        return pin
    comp, leg = pin.split(":", 1)
    if comp != component_id:
        return pin
    for a, b in symmetric_pairs:
        if leg == a:
            return f"{comp}:{b}"
        if leg == b:
            return f"{comp}:{a}"
        if leg.startswith(a + "."):
            return f"{comp}:{b}{leg[len(a):]}"
        if leg.startswith(b + "."):
            return f"{comp}:{a}{leg[len(b):]}"
    return pin


def symmetric_variants_tagged(pairs, symmetric_map):
    """Like symmetric_variants, but each variant comes with the set of
    component ids whose symmetric pins it swapped: [(pairs, frozenset)]."""
    variants = [(pairs, frozenset())]
    for comp_id, sym_pairs in symmetric_map.items():
        new_variants = []
        for variant, swapped_ids in variants:
            swapped = [
                [_swap_pin(a, comp_id, sym_pairs), _swap_pin(b, comp_id, sym_pairs)]
                for a, b in variant
            ]
            new_variants.append((swapped, swapped_ids | {comp_id}))
        variants += new_variants
    return variants


def symmetric_variants(pairs, symmetric_map):
    """symmetric_map: {component_instance_id: [[pinA, pinB], ...]}.
    Returns a list of variants of `pairs`: the original, plus one variant
    per component with its symmetric pins swapped (pins on different
    components are swapped independently, so with N symmetric components
    this yields 2^N variants — fine for the small number of symmetric
    parts expected in practice)."""
    return [variant for variant, _ in symmetric_variants_tagged(pairs, symmetric_map)]


def _missing_nets(expected_pairs, detected_nets, alias_map, connector_component_ids):
    expected_nets = [
        _drop_connectors(n, connector_component_ids)
        for n in build_nets(expected_pairs, alias_map)
    ]
    return [sorted(enet) for enet in expected_nets if enet not in detected_nets]


def _actual_net_for_pin(pin, detected_nets):
    """Which detected net (post connector-dropping) `pin` is actually
    sitting in right now, if any — used to explain *why* a net is missing,
    not just that it is. sorted() for a stable, comparable/printable
    result."""
    for net in detected_nets:
        if pin in net:
            return sorted(net)
    return None


def _conflicts_for_missing(missing_nets, detected_nets):
    """{pin: actual_net} for every pin belonging to a missing expected net
    that's nevertheless wired to *something* right now — just not the
    right thing. A hole/pin can only ever hold one wire, so this is almost
    always the story behind an accidental cross-connection (two different
    legs ending up tied together via a shared hole/pin) rather than a
    generic 'not wired yet'. A pin absent here genuinely has no connection
    at all — that's the plain missing-connection case, not a conflict.
    """
    conflicts = {}
    for enet in missing_nets:
        for pin in enet:
            actual = _actual_net_for_pin(pin, detected_nets)
            if actual is not None and actual != enet:
                conflicts[pin] = actual
    return conflicts


def check(expected_pairs, detected_pairs, symmetric_map=None, alias_map=None, connector_component_ids=None):
    """Returns {"verdict": "pass" | "harmless" | "wrong", "missing": [...]}.

    - pass: detected nets match expected nets exactly (after board pin
      aliases, e.g. any GND pin, are folded together, and any connector-only
      component — a breadboard — is dropped from the result).
    - harmless: detected nets match once a symmetric-pin swap is applied —
      still fully correct electrically, just flagged rather than silent.
    - wrong: detected nets don't match under any symmetric variant; `missing`
      lists the expected nets (as sorted, alias-folded pin lists) that
      weren't found — from whichever variant (swapped or not) comes
      closest, so a genuine mistake on one component doesn't make an
      unrelated, already-fine harmless swap on a different component look
      broken too (see the docstring on the closest-variant selection below).

    `connector_component_ids` (from `connector_ids(diagram_parts)`) matters
    whenever `detected_pairs` includes a breadboard hop — pass `alias_map`
    and `connector_component_ids` together, both derived from the same
    diagram, or a breadboard-routed connection will never compare equal to
    the expected component-pin-only fact (see connector_ids' docstring).
    """
    symmetric_map = symmetric_map or {}
    connector_component_ids = connector_component_ids or set()
    detected_nets = [
        _drop_connectors(n, connector_component_ids)
        for n in build_nets(detected_pairs, alias_map)
    ]

    # tagged[0] is always the plain, unswapped expected_pairs.
    tagged = symmetric_variants_tagged(expected_pairs, symmetric_map)
    missing_per_variant = [
        _missing_nets(variant, detected_nets, alias_map, connector_component_ids)
        for variant, _ in tagged
    ]

    if not missing_per_variant[0]:
        return {"verdict": "pass", "missing": []}

    # Of the matching swapped variants, report the one that swaps the
    # fewest components — `swapped` says which parts the learner turned
    # round, so the engine can lock that orientation for later steps.
    matching = [swapped_ids for (_, swapped_ids), missing in zip(tagged, missing_per_variant) if not missing]
    if matching:
        return {"verdict": "harmless", "missing": [], "note": "matched via symmetric pin swap",
                "swapped": sorted(min(matching, key=len))}

    # No single variant fully matches — a real mistake exists. Report
    # against whichever variant gets closest (fewest missing nets), not
    # always the plain unswapped one: with several components each
    # independently swappable, one might already be correctly wired via
    # its own harmless swap while a *different* component has a genuine
    # error — always falling back to the unswapped comparison would then
    # wrongly list the already-fine swapped component as missing too.
    best_missing = min(missing_per_variant, key=len)
    return {
        "verdict": "wrong",
        "missing": best_missing,
        "conflicts": _conflicts_for_missing(best_missing, detected_nets),
    }


def check_landed(pin, detected_pairs, connector_component_ids, symmetric_pairs=None, alias_map=None):
    """Verdict for 'is this leg plugged into the board at all yet' — half
    of what used to be one net check, now that a single component-to-Arduino
    connection is actually two separate physical actions (leg -> breadboard
    hole, then that same strip -> Arduino pin; see the research log (in git history)). Unlike
    check(), this is not a net-equality comparison against a specific far
    end: it only asks whether `pin` (or, harmlessly, its declared symmetric
    counterpart on the same component) is directly wired to any hole
    belonging to a connector-only component. Which specific hole doesn't
    matter yet — the follow-up step's ordinary check() call verifies the far
    end against the whole current snapshot, and will fail on its own if the
    two wires ended up on different strips.

    `alias_map` matters whenever the pin itself has a board-pin-alias rule
    of its own (e.g. a pushbutton's `2.l`/`2.r`, always the same net) — not
    just Arduino GND or a breadboard strip. Without it, a learner using the
    *other* aliased leg than the one named in `pin` would be wrongly
    rejected as `wrong`, even though it's the identical net (found via a
    real pushbutton lesson — see the research log (in git history)).

    Returns {"verdict": "pass" | "harmless" | "wrong", "missing": [...]},
    same shape as check(), so callers don't need to branch on which kind of
    check produced a result.
    """
    symmetric_pairs = symmetric_pairs or []
    connector_component_ids = connector_component_ids or set()
    canonical_pin = _canonicalize_pin(pin, alias_map)

    def _lands(target):
        canonical_target = _canonicalize_pin(target, alias_map)
        for a, b in detected_pairs:
            if _canonicalize_pin(a, alias_map) == canonical_target and b.split(":", 1)[0] in connector_component_ids:
                return True
            if _canonicalize_pin(b, alias_map) == canonical_target and a.split(":", 1)[0] in connector_component_ids:
                return True
        return False

    if _lands(pin):
        return {"verdict": "pass", "missing": []}

    comp, leg = pin.split(":", 1)
    for a, b in symmetric_pairs:
        alt = None
        if leg == a:
            alt = f"{comp}:{b}"
        elif leg == b:
            alt = f"{comp}:{a}"
        if alt and _lands(alt):
            return {"verdict": "harmless", "missing": [], "note": "matched via symmetric pin swap"}

    conflicts = {}
    for a, b in detected_pairs:
        if _canonicalize_pin(a, alias_map) == canonical_pin:
            conflicts[pin] = b
            break
        if _canonicalize_pin(b, alias_map) == canonical_pin:
            conflicts[pin] = a
            break
    return {"verdict": "wrong", "missing": [pin], "conflicts": conflicts}


def synthesize_landed(label, pin, connector_component_ids, symmetric_pairs=None):
    """Dev/test only (the `sim` command) — the landing-check analogue of
    synthesize_detected. Fabricates a plausible detected pair using a
    stand-in hole on whichever connector component the diagram has, since
    there's no real camera/vision yet (PLAN.md Phase 4)."""
    symmetric_pairs = symmetric_pairs or []
    if not connector_component_ids:
        return []
    board_id = sorted(connector_component_ids)[0]
    hole = f"{board_id}:1t.a"
    if label == "correct":
        return [[pin, hole]]
    if label == "swapped":
        comp, leg = pin.split(":", 1)
        for a, b in symmetric_pairs:
            if leg == a:
                return [[f"{comp}:{b}", hole]]
            if leg == b:
                return [[f"{comp}:{a}", hole]]
        return [[pin, hole]]
    return []  # "wrong" or unrecognized label — nothing detected


def synthesize_landed_multi(label, pins, connector_component_ids):
    """Dev/test only (the `sim` command) — like synthesize_landed, but for
    a multi-leg component's several legs, all placed in one physical
    action at once (see engine._run_landing_check's list case, and
    PARTS.md's `legs_placed_together`). "correct" gives each leg its OWN
    distinct stand-in column — landing them all in the SAME one would
    itself synthesize a self-short, defeating the point of the check this
    exists to test."""
    if not connector_component_ids or label != "correct":
        return []
    board_id = sorted(connector_component_ids)[0]
    return [[pin, f"{board_id}:{i + 1}t.a"] for i, pin in enumerate(pins)]


def synthesize_detected(label, expected_pairs, symmetric_map=None):
    """Dev/test only (the `sim` command — PLAN.md/COMMANDS.md). Stands in for
    the camera/vision pipeline before it exists, by deriving a plausible
    detected-pairs list from the *current step's own* expected pairs — so
    `sim` never needs hand-written mock data per lesson.

    Labels: "correct" (exact match), "wrong" (nothing detected), "swapped"
    (first available symmetric-pin swap applied, if any).
    """
    symmetric_map = symmetric_map or {}
    if label == "correct":
        return list(expected_pairs)
    if label == "swapped":
        variants = symmetric_variants(expected_pairs, symmetric_map)
        return variants[1] if len(variants) > 1 else list(expected_pairs)
    return []  # "wrong" or unrecognized label — nothing detected
