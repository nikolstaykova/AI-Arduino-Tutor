"""Pure event handler: handle_event(lesson, library, state, event) -> (state, actions).

No I/O inside. State is a plain, JSON-serializable dict — safe to log and
replay (see eventlog.py). PLAN.md Phase 1's command table, implemented.

Code owns state; nothing here calls an LLM. `sim`/`checker.synthesize_detected`
stand in for the camera until Phase 4 exists.
"""
import contextvars
import copy
import itertools
import re

from . import checker, physics
from .library import load_library

#: The learner's actual breadboard is never assumed — asked, via the
#: `board` command (see COMMANDS.md). Column-count estimates are exactly
#: that: estimates, per PARTS.md's own honesty note (Wokwi's per-variant
#: docs 404'd when checked) — used only for a plausibility warning
#: alongside the real verdict, never folded into pass/harmless/wrong
#: itself, since that logic shouldn't rest on an unverified number.
BREADBOARD_VARIANTS = {
    "full": {"wokwi_type": "wokwi-breadboard", "max_column_estimate": 63},
    "half": {"wokwi_type": "wokwi-breadboard-half", "max_column_estimate": 30},
    "mini": {"wokwi_type": "wokwi-breadboard-mini", "max_column_estimate": 17},
}

#: No per-board or per-part electrical facts live in this module anymore
#: — they live in each board/part's own library JSON card:
#:   - `pin_domains` (analog/digital pin lists) — which legs are
#:     genuinely interchangeable I/O, per board.
#:   - `protocol_pins` ({leg: "I2C"|"SPI"}) — the board's own real,
#:     hardware-fixed bus pins (e.g. an Uno's A4/A5 for I2C; a Mega's
#:     20/21 — genuinely a different DOMAIN per board, so "is this pin
#:     analog" was never the real criterion once a second board's I2C
#:     turned out to live in the digital pool instead).
#:   - `protocol_legs` (a part's OWN bus-signal leg names, e.g. a microSD
#:     card's `["SCK", "DO", "DI"]`) — replacing a single global name
#:     list with each part explicitly declaring its own bus legs, so an
#:     unrelated part's coincidentally-matching leg name (e.g. a
#:     photoresistor's own "DO") is never at risk of a false match.
#: See _board_card/_leg_is_protocol_bus below for how these get resolved,
#: and PARTS.md for the full schema. This is what lets a genuinely large
#: hardware catalog (docs.wokwi.com/getting-started/supported-hardware
#: lists 60+ parts across 10+ microcontroller families) grow without
#: this module's own code ever changing — the algorithms here are
#: generic; only the data describing a specific board/part lives
#: elsewhere. `library` is optional everywhere below and defaults to the
#: real, on-disk library (load_library(), cached) when not given, so
#: existing callers that don't have one handy still resolve against the
#: actual part data instead of breaking.

#: Which experience level the learner is — asked, not assumed (same
#: "asked, not assumed" precedent as `board`). Lessons are authored ONCE,
#: at full granularity (a separate landing check for every leg that lands
#: on the breadboard, even one with no wire of its own — see PLAN.md's
#: Blink notes). "beginner" (the default, so every existing lesson/test
#: behaves exactly as before) stops at every one of those checkpoints.
#: "advanced" silently skips landing steps and merges their instruction
#: into the paired wiring step's — same underlying checks, same safety,
#: just fewer stops for someone who doesn't need the hand-holding.
DIFFICULTIES = {"beginner", "advanced"}


def _board_card(wokwi_type, library=None):
    """The library card for this Wokwi type, if it declares `pin_domains`
    (the signal that it's a board, for substitution purposes) — or None.
    Matching by "declares pin_domains" rather than a hardcoded name
    prefix (e.g. "wokwi-arduino-") means a future non-Arduino board
    (ESP32, STM32, RPi Pico, ...) is recognized automatically the moment
    its own library card declares pin_domains, without this module's
    code ever needing to change."""
    if wokwi_type is None:
        return None
    if library is None:
        library = load_library()
    for card in library.find_by_wokwi_type(wokwi_type):
        if "pin_domains" in card:
            return card
    return None


def _board_component_ids(diagram_parts, library=None):
    """{component_id: wokwi_type} for every diagram part that's an actual
    board (see _board_card) — never a component's own leg. Required
    because a component's own numbered legs use the exact same bare-digit
    strings as a board's digital pins (e.g. every resistor card's
    symmetric_pins is literally [["1", "2"]] — see
    library/parts/resistor-*.json). Without checking which component a
    pin actually belongs to, a resistor's own leg '2' would be wrongly
    treated as substitutable pin 2. Keyed by type (not just a bare id
    set) since which pins are substitutable, and which are the real
    protocol ones, differs per board. Callers that only need "is this id
    a board at all" can still use plain `in` — dict membership checks
    keys."""
    if library is None:
        library = load_library()
    result = {}
    for part in diagram_parts:
        wtype = part.get("type")
        if _board_card(wtype, library) is not None:
            result[part["id"]] = wtype
    return result


def _pin_domain(pin, board_component_ids, library=None):
    """(pool, kind) for this pin: `pool` is the set of pins interchangeable
    with it on ITS board — its own substitution/remap candidates — and
    `kind` is "analog" or "digital" (needed wherever the two domains
    follow different rules, e.g. digital's contention gate). Returns
    (None, None) if this isn't a substitutable numbered I/O pin on a
    known board at all (GND, 5V, a board-alias pin, any pin belonging to
    a non-board component, or a board type with no `pin_domains` card).
    A pin's pool never mixes domains — a digital pin's alternates are
    only other digital pins, same for analog — since an analog-only
    sketch call (analogRead) and a digital-only one (digitalRead/pinMode)
    are never interchangeable with each other."""
    if ":" not in pin:
        return None, None
    comp, leg = pin.split(":", 1)
    card = _board_card(board_component_ids.get(comp), library)
    if card is None:
        return None, None
    domains = card.get("pin_domains", {})
    analog = set(domains.get("analog", []))
    digital = set(domains.get("digital", []))
    if leg in analog:
        return analog, "analog"
    if leg in digital:
        return digital, "digital"
    return None, None


def _pin_pool(pin, board_component_ids, library=None):
    pool, _kind = _pin_domain(pin, board_component_ids, library)
    return pool


# A lesson whose sketch walks its pins in a loop (`for (pin = 2; pin < 8; pin++)`)
# can't follow a learner onto another pin — it sets "fixed_pins": true, and
# while it's being checked no numbered pin is swappable (like 5V or GND).
_FIXED_PINS = contextvars.ContextVar("fixed_pins", default=False)


def _is_substitutable_pin(pin, board_component_ids, library=None):
    if _FIXED_PINS.get():
        return False
    return _pin_pool(pin, board_component_ids, library) is not None


def _is_board_protocol_pin(pin, board_component_ids, library=None):
    """Is this the EXACT, real hardware-fixed protocol pin (I2C or SPI)
    for its board (see its card's `protocol_pins`) — not just "some pin
    in the same domain that protocol happens to use," since that domain
    differs per board (Uno's I2C: analog; Mega's I2C: digital) and per
    protocol (SPI is always digital on both boards)."""
    return _board_protocol_name(pin, board_component_ids, library) is not None


def _board_protocol_name(pin, board_component_ids, library=None):
    """Which real protocol ("I2C"/"SPI") this exact pin is fixed for, or
    None. Used only for phrasing a refusal explanation — the refusal
    logic itself only needs the boolean (_is_board_protocol_pin)."""
    entry = _board_protocol_entry(pin, board_component_ids, library)
    return entry.get("protocol") if entry else None


def _board_protocol_role(pin, board_component_ids, library=None):
    """Which specific role ("SDA"/"SCL"/"MOSI"/"MISO"/"SCK") this exact
    pin plays, or None. Needed (unlike the plain protocol name) for
    cross-board translation: two boards' I2C pins aren't interchangeable
    with each other, only role-for-role (board_translate.py)."""
    entry = _board_protocol_entry(pin, board_component_ids, library)
    return entry.get("role") if entry else None


def _board_protocol_entry(pin, board_component_ids, library=None):
    """The raw {"protocol": ..., "role": ...} dict for this exact pin, or
    None — see each board card's `protocol_pins` field (PARTS.md)."""
    if ":" not in pin:
        return None
    comp, leg = pin.split(":", 1)
    card = _board_card(board_component_ids.get(comp), library)
    if card is None:
        return None
    return card.get("protocol_pins", {}).get(leg)


def _component_types(diagram_parts):
    """{component_id: wokwi_type} for EVERY diagram part, board or not —
    used to look up any component's own library card, e.g. to check its
    declared `protocol_legs`."""
    return {part["id"]: part.get("type") for part in diagram_parts}


def _leg_is_protocol_bus(pin, diagram_parts, library=None):
    """Is this component's OWN leg declared as a real, hardware-fixed
    protocol bus signal on ITS library card (e.g. a microSD card's
    `protocol_legs: ["SCK", "DO", "DI"]`) — replacing a single global
    name list with each part explicitly declaring its own bus legs, so
    an unrelated part's coincidentally-matching leg name (e.g. a
    photoresistor's own "DO") is never at risk of a false match. A part
    that doesn't declare a leg here is never treated as protocol-fixed,
    regardless of what it's called (e.g. the DHT22's "SDA", a one-wire
    protocol unrelated to real I2C — see PARTS.md)."""
    if ":" not in pin:
        return False
    comp, leg = pin.split(":", 1)
    wtype = _component_types(diagram_parts).get(comp)
    if wtype is None:
        return False
    if library is None:
        library = load_library()
    for card in library.find_by_wokwi_type(wtype):
        if leg in card.get("protocol_legs", []):
            return True
    return False


def _pin_change_description(original_pin, actual_pin):
    """Human-readable phrasing for a pin substitution/remap, domain-aware:
    an analog pin's identity in code is always through analogRead(), so
    that's named explicitly; a digital pin's identity in code could be
    pinMode/digitalRead/digitalWrite/a library constructor argument — no
    single call name to point to, so it's phrased generically instead of
    guessing which one the lesson's code actually uses.

    Recognizes an analog leg by shape ("A" + digits) rather than
    membership in a specific board's pin set — this is purely a phrasing
    choice with no correctness weight, and every real board's analog
    pins share this exact naming convention (A0-A5 on an Uno, A0-A15 on
    a Mega, ...), so a shape check stays correct without needing to grow
    a per-board list here too."""
    original_leg = original_pin.split(":", 1)[1]
    actual_leg = actual_pin.split(":", 1)[1]
    if original_leg[:1] == "A" and original_leg[1:].isdigit():
        return f"analogRead({actual_leg}) instead of analogRead({original_leg})"
    return f"pin {actual_leg} instead of pin {original_leg}, wherever the code references it"


def _pin_owner(confirmed_pairs, pin, alias_map, connector_component_ids, for_component=None):
    """Which *other* (non-Arduino, non-connector) component is already
    confirmed wired to this pin, per confirmed_pairs so far — or None if
    it's unclaimed. Used so a substitution never hands out a pin another
    connection already confirmed, which would silently short two
    components onto the same physical Arduino pin instead of flagging a
    real conflict.

    confirmed_pairs is raw, possibly hole-level data (e.g. a breadboard-
    routed confirmation stores `uno:A1` paired with a *hole*, not directly
    with the far-side component) — so this builds real nets first (same
    aliasing checker.check uses) and skips connector-only members when
    picking the "owner," rather than reading the raw pair partner, which
    would misidentify a breadboard hop as the owner instead of tracing
    through to the actual component.

    A net can hold several components at once (the whole board built
    before the first check: pin 2's net holds the pushbutton AND its
    pull-down resistor). If `for_component` is one of them, the pin is
    already its own — returned as the owner, so callers asking "taken by
    someone else?" get no. Otherwise the owner is chosen in sorted order:
    the old "first member of a set" was hash-order dependent, so the same
    wiring could pass or be remapped to a random pin from run to run
    (found by the Sonnet lesson-generation experiment)."""
    connector_component_ids = connector_component_ids or set()
    for net in checker.build_nets(confirmed_pairs, alias_map):
        if pin not in net:
            continue
        comps = sorted({member.split(":", 1)[0] for member in net
                        if member != pin and ":" in member
                        and member.split(":", 1)[0] not in connector_component_ids})
        if not comps:
            continue
        return for_component if for_component in comps else comps[0]
    return None


def _record_confirmed(state, event, detected, board_component_ids, connector_component_ids, library=None):
    """Remember what a passing check confirmed. A whole-board snapshot
    (event "snapshot": true — what the Wiring Bench and a camera send) IS
    the board: it replaces the record outright, so a wire the learner moved
    or removed after an earlier step (changing their mind, pulling out a
    wrong jumper) is never remembered as still there. Partial input (the
    CLI's `sim` of one step's pairs) is merged as before."""
    if isinstance(event, dict) and event.get("snapshot") and _is_valid_pairs(event.get("detected_pairs")):
        state["confirmed_pairs"] = [list(pair) for pair in event["detected_pairs"]]
        return
    _supersede_scarce_leg_pairs(state["confirmed_pairs"], detected, board_component_ids, connector_component_ids, library)


def _supersede_scarce_leg_pairs(confirmed_pairs, detected, board_component_ids, connector_component_ids, library=None):
    """Append `detected` to `confirmed_pairs`, first dropping any EXISTING
    entry whose "scarce" pin (see below) is ALSO in `detected` but paired
    with a DIFFERENT partner there — i.e. only ever evicts a fact that's
    genuinely been superseded, never one simply being re-confirmed
    verbatim (a landing pair re-sent as part of its own wiring check's
    detected data, e.g., stays exactly as many times as before — existing
    tests rely on that exact historical shape).

    A "scarce" pin can only ever be wired to ONE thing at a time: a real
    component's own leg (e.g. 'pot1:SIG'), or a board pin that's a
    substitutable domain pin (e.g. 'uno:13'/'uno:A0'). A board's
    shared-rail pin (GND/5V/3V3/...) or a connector/breadboard hole is
    NOT scarce — those legitimately have many simultaneous, unrelated
    partners (a shared ground rail, a breadboard strip with several
    components in it), so a new fact about one must never evict an
    older, still-true fact about a *different* component that happens to
    share it.

    Fixes a real bug found via a real "land the leg on pin X, then
    genuinely re-wire it to pin Y before the wiring check" scenario (see
    the research log (in git history)): without this, an old, superseded fact (`leg` <-> X)
    and the new one (`leg` <-> Y) both stayed in confirmed_pairs forever,
    so checker.build_nets' union-find — which has no notion of time —
    silently merged them into one net containing BOTH X and Y. That
    broke two independent readers of confirmed_pairs in two different
    ways: `_final_pin_for_component` could return the stale pin for
    generated code (fixed separately, defense-in-depth, by having that
    function walk confirmed_pairs most-recent-first instead of trusting
    a flat net), and `_pin_owner` could mistake the stale partner for a
    still-live rival claim — e.g. seeing the board itself ('uno:X', from
    the superseded pairing) as if it were a competing *component*, and
    wrongly refusing an otherwise perfectly valid substitution onto pin Y
    because "something" appeared to already own it. This is the root-
    cause fix: stale facts about a scarce pin never accumulate in
    confirmed_pairs in the first place, so every reader — present and
    future — sees only current truth."""
    def _is_scarce(pin):
        if ":" not in pin:
            return False
        comp = pin.split(":", 1)[0]
        if comp in connector_component_ids:
            return False
        if comp in board_component_ids:
            return _is_substitutable_pin(pin, board_component_ids, library)
        return True

    new_partners = {}  # scarce pin -> set of partners `detected` gives it
    for pair in detected:
        for i, pin in enumerate(pair):
            if _is_scarce(pin):
                new_partners.setdefault(pin, set()).add(pair[1 - i])

    def _is_board_or_connector(pin):
        if ":" not in pin:
            return False
        comp = pin.split(":", 1)[0]
        return comp in board_component_ids or comp in connector_component_ids

    def _superseded(pair):
        for i, pin in enumerate(pair):
            partners = new_partners.get(pin)
            if partners is None:
                continue
            old_partner = pair[1 - i]
            if old_partner in partners:
                continue
            # A genuine re-wire (this leg's Arduino-side connection moved
            # to a different board pin or breadboard hole — the same
            # physical wire, just re-expressed or actually moved)
            # supersedes the old fact. A NEW partner that's a DIFFERENT
            # component's own leg never does — that's a separate,
            # simultaneously-true edge of a real multi-member net (e.g. a
            # pull-down resistor sharing a pushbutton leg's own strip
            # with the Arduino pin: both facts stay true at once,
            # confirmed in two separate steps — see the research log (in git history)).
            # Requiring BOTH the old and every new partner to be
            # board/connector-side keeps this scoped to an actual rewire
            # of the same wire's endpoint, not a leg's connection to one
            # more, unrelated component arriving alongside an earlier,
            # still-true board-side fact about it.
            if _is_board_or_connector(old_partner) and any(_is_board_or_connector(p) for p in partners):
                return True
        return False

    kept = [pair for pair in confirmed_pairs if not _superseded(pair)]
    confirmed_pairs[:] = kept + list(detected)


def _substitution_text_replacements(state):
    """(original_leg, actual_leg) pairs for every currently-accepted
    learner substitution — used to keep clip/hint text in sync with
    state["pin_substitutions"] the same way _enter_step and the `hint`
    command already keep it in sync with state["pin_remaps"]. Found via a
    real gap (see the research log (in git history)): a later step's own instruction can
    name an EARLIER component's pin directly (e.g. "wire this to the same
    pin as led1") — if led1 was substituted (not remapped), that text
    stayed stale, telling the learner a pin led1 doesn't actually use
    anymore, even though the underlying wiring CHECK itself already
    correctly expected led1's real, current pin (_effective_expected_nets).
    Unlike a remap (looked up per-step, since it's inherently about ONE
    step's own scripted target), a substitution can be referenced by ANY
    later step's text, so every currently-live one applies everywhere,
    not just the step it originated on."""
    return [
        (s["original"].split(":", 1)[1], s["actual"].split(":", 1)[1])
        for s in state["pin_substitutions"]
    ]


def _board_pin_expected_groups(lesson, board_component_ids, alias_map):
    """{canonical_board_pin: group_id} — which board pins (after alias
    folding, e.g. any GND.N canonicalizes to one shared identity) the
    lesson's OWN complete design (every step's expected_nets PLUS
    final_check) ever intends to end up on the same net, vs which it
    keeps genuinely separate. Two board pins in different groups here are
    never supposed to be tied together by anything the learner does.

    Deliberately scoped to BOARD pins only, never component legs.
    Extending this to component legs was attempted and reverted (see
    the research log (in git history)) — it ran into a genuine architectural mismatch, not
    just a bug: a component's symmetric legs (a resistor's two
    interchangeable legs, a pushbutton's contact group, a potentiometer's
    GND/VCC outer legs) get their role LOCKED IN the moment they're
    actually confirmed wired — but this project's own existing test
    methodology exercises a single step's own swap-handling in isolation
    (fast-forwarding earlier steps via plain, unswapped `sim correct`),
    which is fine for THAT purpose but means the accumulated
    confirmed_pairs history isn't always internally physically coherent
    across steps for a symmetric component. A per-net check
    (checker.check's own symmetric_map machinery) can safely try every
    swap variant fresh each time because it only ever looks at ONE net in
    isolation; a cross-step check spanning the WHOLE accumulated history
    can't do the same without first solving "which role did this
    component's legs already commit to," which board pins never need
    (they have no symmetric ambiguity at all) — so board pins remain the
    only currently well-scoped target for this check."""
    net_lists = [step.get("expected_nets", []) for step in lesson.data.get("steps", [])]
    net_lists.append(lesson.data.get("final_check", {}).get("expected_nets", []))
    all_pairs = [pair for nets in net_lists for pair in nets]
    nets = checker.build_nets(all_pairs, alias_map)
    groups = {}
    for i, net in enumerate(nets):
        for pin in net:
            if ":" not in pin:
                continue
            if pin.split(":", 1)[0] in board_component_ids:
                groups[pin] = i
    return groups


def _cross_step_short(lesson, state, alias_map, connector_component_ids, board_component_ids, detected, snapshot=False):
    """None if nothing's wrong, else a human-readable message describing
    a genuine cross-step short: two board pins the lesson's own complete
    design keeps in DIFFERENT nets (_board_pin_expected_groups) have
    ended up merged into ONE actual net, via everything confirmed so far
    PLUS this step's newly-detected data — e.g. two different components
    routed through the same breadboard hole/strip that happens to also
    tie two different board pins together (a real short on real
    hardware). Catches it the moment it happens instead of only at
    final_check (found via a real gap — see the research log (in git history): a learner
    could route a second component's leg through a board pin an earlier,
    ALREADY-CONFIRMED connection already owns, and no per-step check
    before this one ever looked past its own single connection to
    notice).

    Uses _supersede_scarce_leg_pairs (not a raw concatenation) to build
    the "actual so far" picture — required to avoid a real false-positive
    this check hit on its first version: a harmless SWAP of a component's
    own symmetric legs (e.g. a potentiometer's GND/VCC outer legs) means
    the SAME scarce leg (e.g. 'pot1:GND') gets a genuinely NEW partner
    this step, superseding its OLD one from an earlier step — a naive
    concatenation would see both the old and new pairing at once and
    falsely conclude the board pins on either end must be shorted
    together, when really the old fact just needs to be treated as
    superseded, same as everywhere else confirmed_pairs is read."""
    board_groups = _board_pin_expected_groups(lesson, board_component_ids, alias_map)
    if snapshot:
        # The whole board is right here: judge it as it is NOW. A short the
        # learner has since removed may still be in the record (a step passed
        # while it was there), and must not keep failing every check.
        actual_pairs = list(detected)
    else:
        actual_pairs = list(state["confirmed_pairs"])
        _supersede_scarce_leg_pairs(actual_pairs, detected, board_component_ids, connector_component_ids)
    for net in checker.build_nets(actual_pairs, alias_map):
        seen = {}
        for pin in net:
            gid = board_groups.get(pin)
            if gid is not None and gid not in seen:
                seen[gid] = pin
        if len(seen) > 1:
            pins = sorted(seen.values())
            return (
                f"{' and '.join(pins)} ended up connected together, but this lesson keeps them "
                "separate — check for a shared hole/strip that shouldn't be shared."
            )
    return None


def _reserved_pins(lesson, exclude_component, library=None):
    """Every substitutable pin some OTHER step's own expected wiring
    assigns to a component other than `exclude_component` — past or
    future in the lesson's step order, it doesn't matter which. Without
    this, a substitution made at an earlier step could hand out a pin
    that looks free right now (nothing has confirmed it yet) but is
    guaranteed to conflict once a later step correctly wires its own
    component to that same scripted pin — catching the mistake at its
    actual source instead of deferring a confusing 'wrong' to whichever
    step happens second."""
    if lesson is None:
        return set()
    diagram_parts = lesson.diagram().get("parts", [])
    board_component_ids = _board_component_ids(diagram_parts, library)
    reserved = set()
    net_lists = [step.get("expected_nets", []) for step in lesson.data.get("steps", [])]
    net_lists.append(lesson.data.get("final_check", {}).get("expected_nets", []))
    for nets in net_lists:
        for a, b in nets:
            for pin in (a, b):
                if not _is_substitutable_pin(pin, board_component_ids, library):
                    continue
                other = a.split(":", 1)[0] if pin == b else b.split(":", 1)[0]
                if other != exclude_component:
                    reserved.add(pin)
    return reserved


def _protocol_reserved_pins(lesson, library=None):
    """Every Arduino pin this lesson's own script wires to a component's
    real protocol bus leg (_leg_is_protocol_bus) — i.e. an Uno's A4/A5
    the moment this lesson has a real I2C device — hardware-fixed and
    never a valid substitution TARGET for any OTHER, unrelated component
    either, not just off-limits for moving the protocol connection
    itself.

    Found via a real gap: refusing to move the I2C connection (see
    _try_pin_substitution/_compute_pin_remap's own protocol checks) is
    not enough on its own — without this, a plain analogRead() sensor
    could still be silently accepted onto A4 in an EARLIER step, before
    the I2C step is even reached. The I2C step would then have nowhere
    to go (remapping it is refused) and — since two different components
    sharing one Arduino pin isn't inherently a checker error — the
    learner correctly following the (unchanged) instruction would
    silently short the sensor's signal onto the I2C bus, with zero
    warning at all. Reserving A4/A5 up front, lesson-wide, the moment any
    step wires them to a real bus leg, is what actually prevents that."""
    if lesson is None:
        return set()
    diagram_parts = lesson.diagram().get("parts", [])
    board_component_ids = _board_component_ids(diagram_parts, library)
    reserved = set()
    net_lists = [step.get("expected_nets", []) for step in lesson.data.get("steps", [])]
    net_lists.append(lesson.data.get("final_check", {}).get("expected_nets", []))
    for nets in net_lists:
        for a, b in nets:
            for pin in (a, b):
                if not _is_board_protocol_pin(pin, board_component_ids, library):
                    continue
                other_pin = b if pin == a else a
                if _leg_is_protocol_bus(other_pin, diagram_parts, library):
                    reserved.add(pin)
    return reserved


def _describe_pin(pin, board_component_ids):
    """Plain-language phrasing for one pin — "Arduino pin 13" for the
    board side, "led1's A leg" for a component side. Only component:leg
    identities exist at the lesson-script level (no physical breadboard
    hole is ever named by expected_nets — that's real detection's job,
    not the script's), so this is as concrete as a hint can honestly get
    without inventing hole knowledge the lesson doesn't actually have."""
    comp, leg = pin.split(":", 1)
    if comp in board_component_ids:
        return f"Arduino pin {leg}"
    return f"{comp}'s {leg} leg"


def _refusal_hint(result, board_component_ids, lesson, library=None):
    """User request: when a substitution search has already failed and a
    'wrong' verdict is about to stand, say something more useful than a
    bare 'wrong' — always a concrete, plain-language instruction, not
    just the raw missing/conflicts data. Checked against `result` — the
    checker's own `missing`/`conflicts` — so this never re-derives what's
    already computed, just interprets and phrases it.

    Three cases, most specific first:
    1. The learner's actual pin choice happens to land on a pin this
       lesson's own script has already committed to I2C or SPI
       elsewhere (e.g. tried A4, which the LCD's SDA already owns) —
       more specific and actionable than a bare 'wrong', since simply
       trying a different pin would work.
    2. The EXPECTED connection itself is this board's real, hardware-
       fixed protocol pin (e.g. the LCD's own SDA got moved off A4, or
       an SPI device's SCK got moved off its real clock pin) — no
       alternative to suggest, just an explanation of why this one pin
       isn't a free choice the way most pins are. Requires BOTH sides —
       the board pin's real protocol identity AND the component's own
       leg actually being a declared protocol-bus leg on its library
       card (_leg_is_protocol_bus) — not just the board pin alone: an
       ordinary component whose scripted pin merely happens to share a
       number with the board's real SPI/I2C identity (e.g. a plain
       LED scripted onto the Uno's pin 12) has nothing to do with that
       protocol, and a refusal caused by something else entirely (most
       often a genuine pin already taken by another component) must
       never be misattributed to protocol protection it doesn't
       involve — a real bug found via a complex real-world diagram
       stress test, see the research log (in git history).
    3. Anything else: no special reason behind the refusal (the scripted
       pin already IS the only sensible answer) — but still worth saying
       exactly where the connection needs to go, in a plain sentence,
       rather than leaving the learner to parse the raw data structure
       themselves."""
    missing = result.get("missing") or []
    conflicts = result.get("conflicts") or {}
    protocol_reserved = _protocol_reserved_pins(lesson, library) if lesson else set()
    diagram_parts = lesson.diagram().get("parts", []) if lesson is not None else []

    for actual_net in conflicts.values():
        stolen = next((m for m in actual_net if m in protocol_reserved), None)
        if stolen:
            protocol = _board_protocol_name(stolen, board_component_ids, library) or "I2C/SPI"
            return (
                f"{stolen} is already used by this circuit's {protocol} bus — "
                "that pin can't do double duty. Try a different pin instead."
            )

    for enet in missing:
        # Both sides required, matching _try_pin_substitution/
        # _compute_pin_remap's own protocol check: a board pin's real
        # identity (e.g. the Uno's 11/12/13, hardware-fixed for SPI)
        # only makes THIS connection protocol-locked if the OTHER member
        # is a component whose own library card actually declares that
        # leg as a real protocol bus signal. Checking the board pin
        # alone was a real bug -- an ordinary LED whose scripted pin
        # simply happens to BE 12 has nothing to do with SPI, and a
        # refusal caused by something else entirely (e.g. that pin
        # already being another component's, a genuine collision) must
        # never be blamed on protocol protection it doesn't involve
        # (found via a real complex diagram stress test -- see
        # the research log (in git history)).
        protocol_pin = next(
            (m for m in enet if _is_board_protocol_pin(m, board_component_ids, library)
             and _leg_is_protocol_bus(next(o for o in enet if o != m), diagram_parts, library)),
            None,
        )
        if protocol_pin:
            protocol = _board_protocol_name(protocol_pin, board_component_ids, library) or "I2C/SPI"
            return (
                f"{protocol_pin} needs to stay exactly there — {protocol} is wired "
                "directly into the board's dedicated hardware, not a pin the "
                "code can freely choose the way a normal sensor pin can."
            )

    for enet in missing:
        members = sorted(enet)
        described = [_describe_pin(m, board_component_ids) for m in members]
        if len(described) == 2:
            return f"Connect {described[0]} to {described[1]}."
        return "These need to be connected together: " + ", ".join(described) + "."
    return None


def _try_net_superset_match(expected_pairs, detected, alias_map, connector_component_ids, board_component_ids, planned_nets=()):
    """checker.check requires an EXACT net match (same set of pins, after
    alias-folding/connector-dropping) — but a learner can reach the exact
    same real circuit a DIFFERENT way than the lesson's own graph
    describes: e.g. wiring a second component directly to the Arduino pin
    the FIRST component already uses, instead of sharing the first
    component's own leg (a breadboard column, or a direct jumper between
    the two). Electrically identical — both ways put the two components
    on one shared net — but the second way also puts the ACTUAL Arduino
    pin itself into that net, which the lesson's graph (describing just
    "these two connect to each other") never explicitly listed. A strict
    exact-set comparison rejects this as "wrong" even though nothing
    about the circuit is actually incorrect (found via a real question —
    see the research log (in git history)).

    Deliberately NARROW, by design (per direct instruction — stick to the
    tutorial's own intent): if the lesson says "connect X to A2," and by
    design X and Y must share one hole, then the ONLY extra member this
    tolerates is the board's own pin X actually landed on (e.g. A5, if
    that's where X's pin substitution put it) — i.e. Y lands correctly by
    being wired straight to A5 instead of straight to X's own leg. Any
    OTHER extra member (another component's leg — including X's or Y's
    OWN other leg) is refused, not tolerated: that's not "the same hole
    a different way," that's a genuinely different, unintended
    connection (see the resistor-self-short regression this caught:
    r1:1 and r1:2 both landing on the same strip as uno:13 must NOT
    silently pass just because r1:1/uno:13 happen to also be satisfied).

    One more tolerated kind of extra (2026-09-23, "building ahead"): a
    component leg the lesson's OWN finished circuit (`planned_nets`, from
    final_check, in the orientation already locked) puts in this very same
    net. That's a later step done early, correctly — e.g. DigitalReadSerial's
    pull-down resistor already on the pin-2 column when step 2 is checked,
    which a learner who wires the whole board before pressing "check"
    always hits. Anything the finished design doesn't contain (the
    resistor-self-short above) is still refused.

    Returns a synthesized {"verdict": "pass", "missing": []} if EVERY
    expected pair's two pins land in the SAME actual net together AND
    every other member of that net is a board pin or a planned member of
    that same net, else None. Deliberately does NOT relax checker.check's own
    strict semantics everywhere (it's still exactly as strict for every
    other caller); this is only ever tried here, as a last-resort
    fallback."""
    detected_nets = [
        checker._drop_connectors(n, connector_component_ids)
        for n in checker.build_nets(detected, alias_map)
    ]
    for a, b in expected_pairs:
        ca = checker._canonicalize_pin(a, alias_map)
        cb = checker._canonicalize_pin(b, alias_map)
        net = next((n for n in detected_nets if ca in n and cb in n), None)
        if net is None:
            return None
        extras = net - {ca, cb}
        planned = next((p for p in planned_nets if ca in p and cb in p), frozenset())
        if any(pin.split(":", 1)[0] not in board_component_ids and pin not in planned for pin in extras):
            return None
    return {"verdict": "pass", "missing": []}


def _superset_any_orientation(expected_pairs, detected, sym_map, planned_pairs, alias_map,
                               connector_component_ids, board_component_ids):
    """_try_net_superset_match (a later step already built) tried in every
    orientation still open for the symmetric parts, fewest swaps first — a
    part may be turned round AND a later step done early at once. Returns
    pass, harmless (with "swapped"), or None."""
    for variant, swapped_ids in sorted(checker.symmetric_variants_tagged(expected_pairs, sym_map), key=lambda v: len(v[1])):
        variant_planned = planned_pairs
        for comp in swapped_ids:
            variant_planned = [[checker._swap_pin(a, comp, sym_map[comp]), checker._swap_pin(b, comp, sym_map[comp])]
                               for a, b in variant_planned]
        variant_nets = [checker._drop_connectors(n, connector_component_ids)
                        for n in checker.build_nets(variant_planned, alias_map)]
        if _try_net_superset_match(variant, detected, alias_map, connector_component_ids,
                                   board_component_ids, variant_nets):
            if not swapped_ids:
                return {"verdict": "pass", "missing": []}
            return {"verdict": "harmless", "missing": [], "note": "matched via symmetric pin swap",
                    "swapped": sorted(swapped_ids)}
    return None


def _try_pin_substitution(expected_pairs, detected, sym_map, alias_map, connector_component_ids, confirmed_pairs=None, board_component_ids=None, lesson=None, library=None, planned_pairs=None):
    """If a wiring check's expected net targets a specific substitutable
    pin (analog or digital — see _pin_pool) and fails, check whether the
    same net succeeds with a different pin from that *same* pool
    substituted in its place. Returns (result, original_pin, actual_pin)
    for the first substitution that resolves to pass/harmless, or
    (None, None, None) if none does.

    An alternate pin already confirmed as belonging to a *different*
    component (via confirmed_pairs) is never offered — see _pin_owner —
    since that connection has already physically happened and can't be
    silently reinterpreted. A pin some *other*, not-yet-attempted step's
    script also wants is not refused outright, but is deliberately tried
    LAST, after every unreserved candidate — see the two-pass search
    below. Handing it out anyway is still perfectly safe even then: the
    later step is the one that adapts (silently reassigned to a free pin
    instead — see _compute_pin_remap), not this one that gets second-
    guessed or blocked; preferring an unreserved pin first is purely to
    avoid unnecessary remap churn, not a correctness requirement.

    Digital and analog are both unconditionally offered (revised — user
    request: match real electronics, where any digital pin genuinely
    works as well as any other for a plain digitalRead()/digitalWrite()
    connection, same as analog; a learner should be able to deviate
    freely and have the tool figure out a conflict-free assignment,
    the way handling a real breadboard does not stop them either).
    Earlier in this project a digital deviation was only offered when the
    lesson already had genuine multi-component contention for a digital
    pin, specifically so the shown code could never silently drift from
    what's wired without an obvious, explained reason — now that
    _adjusted_code always rewrites the shown code to match whatever's
    actually confirmed (see its own docstring), that justification no
    longer applies, and the two-pass reserved-pin preference plus
    _compute_pin_remap's existing safety net (already domain-agnostic)
    fully cover the conflict-avoidance concern this gate used to handle
    more bluntly, by refusing outright.

    A pin that IS this board's real, fixed protocol identity (see the
    board's own `protocol_pins` card field) and wired to a component's
    own declared bus leg (_leg_is_protocol_bus, e.g. a real I2C device's
    SDA/SCL) is never offered a substitution at all, regardless of
    contention — I2C/SPI is hardware-fixed, not a code-configurable
    choice the way a plain analogRead()/digitalRead() pin is (see
    the research log (in git history)). A component whose leg merely happens to be NAMED
    SDA/SCL/etc. but doesn't declare it as a protocol leg on its own
    library card (e.g. the DHT22's data leg, an unrelated one-wire
    protocol that happens to reuse the name) is NOT affected."""
    confirmed_pairs = confirmed_pairs or []
    board_component_ids = board_component_ids or {}
    diagram_parts = lesson.diagram().get("parts", []) if lesson is not None else []
    for a, b in expected_pairs:
        for pin in (a, b):
            pool, kind = _pin_domain(pin, board_component_ids, library)
            if pool is None:
                continue
            comp, leg = pin.split(":", 1)
            other_pin = b if pin == a else a
            other_comp = other_pin.split(":", 1)[0]
            if _is_board_protocol_pin(pin, board_component_ids, library) and _leg_is_protocol_bus(other_pin, diagram_parts, library):
                continue
            protocol_reserved = _protocol_reserved_pins(lesson, library)
            reserved_legs = {p.split(":", 1)[1] for p in _reserved_pins(lesson, other_comp, library)}
            # Two passes over the same candidate list: first excluding
            # every leg some OTHER, not-yet-reached component's own
            # script still wants, then (only if nothing else works)
            # allowing those too. Preferring the unreserved ones first
            # isn't required for correctness — a reserved pin handed out
            # here is still perfectly safe, since _compute_pin_remap
            # reassigns that other component the moment its own step
            # finds its target already taken — but it minimizes how
            # often that later, unrelated component ends up needing its
            # own remap at all.
            for skip_reserved in (True, False):
                for alt_leg in sorted(pool - {leg}):
                    if skip_reserved and alt_leg in reserved_legs:
                        continue
                    alt_pin = f"{comp}:{alt_leg}"
                    if alt_pin in protocol_reserved:
                        continue  # e.g. A4/A5 already committed to this lesson's I2C bus
                    owner = _pin_owner(confirmed_pairs, alt_pin, alias_map, connector_component_ids, other_comp)
                    if owner is not None and owner != other_comp:
                        continue  # already claimed by a different component
                    trial_pairs = [[alt_pin if p == pin else p for p in pair] for pair in expected_pairs]
                    trial_result = checker.check(trial_pairs, detected, sym_map, alias_map, connector_component_ids)
                    if trial_result["verdict"] == "wrong" and planned_pairs is not None:
                        # Moved pin AND a later step done early (the whole
                        # board built before checking), in any orientation
                        # still open: the lesson's own finished circuit is
                        # moved onto the alternate pin too.
                        trial_planned = [[alt_pin if p == pin else p for p in pair] for pair in planned_pairs]
                        trial_result = _superset_any_orientation(
                            trial_pairs, detected, sym_map, trial_planned, alias_map,
                            connector_component_ids, board_component_ids or set()) or trial_result
                    if trial_result["verdict"] in ("pass", "harmless"):
                        return trial_result, pin, alt_pin
    return None, None, None


def _oriented_leg(lesson, state, pin):
    """The physical leg a scripted component pin refers to, given the
    orientation the learner locked in (state["orientations"]): with the
    pushbutton turned round, the script's 'btn1:2.l' is physically the leg
    'btn1:1.l'. Where a leg is actually wired must be looked up by its
    physical identity, or a turned-round part's pin substitution is missed
    (found by the Sonnet experiment: the shown code kept pin 2 while the
    learner's button was on pin 3)."""
    comp = pin.split(":", 1)[0]
    if state.get("orientations", {}).get(comp) != "swapped":
        return pin
    sym = _symmetric_map(lesson, load_library()).get(comp)
    return checker._swap_pin(pin, comp, sym) if sym else pin


def _adjusted_code(lesson, state):
    """The lesson's code.ino, textually adjusted so every substitutable-pin
    reference matches whichever pin each component is *actually* confirmed
    wired to right now — derived from confirmed_pairs (ground truth), not
    by chaining pin_substitutions/pin_remaps as sequential text replaces.
    Chaining would be wrong whenever one change's target coincides with
    another's source (e.g. sensor remapped A2->A1 while led substituted
    A0->A2 are both live: naive sequential replacement of 'A2'->'A1' would
    also corrupt led's newly-A2 text, which was never meant to become A1).
    A placeholder pass keeps every replacement independent regardless of
    how many are live at once.

    Each replacement matches on a `\\b` word-boundary regex, not a plain
    substring — required now that digital pins are substitutable too:
    a bare digit like '5' is a substring of plenty of unrelated numbers in
    real code (a baud rate, a delay() value, another pin entirely — e.g.
    Blink's own delay(1000) sits right next to pinMode(13, ...)), so a raw
    .replace('5', ...) would corrupt them. 'A2'-style analog names were
    never at real risk of this, but the boundary match costs them nothing
    either, so it's applied uniformly rather than kept as two code paths."""
    code = lesson.code_text()
    diagram_parts = lesson.diagram().get("parts", [])
    alias_map = checker.board_alias_map(diagram_parts)
    connector_component_ids = checker.connector_ids(diagram_parts)
    board_component_ids = _board_component_ids(diagram_parts)

    replacements = []
    net_lists = [step.get("expected_nets", []) for step in lesson.data.get("steps", [])]
    net_lists.append(lesson.data.get("final_check", {}).get("expected_nets", []))
    seen_pins = set()
    for nets in net_lists:
        for a, b in nets:
            for pin in (a, b):
                if not _is_substitutable_pin(pin, board_component_ids):
                    continue
                # The OTHER side of this net — the component's own leg
                # (e.g. 'sensor1:ECHO') — anchors this specific
                # connection. Deduping (and resolving) by this instead of
                # by bare component id matters the moment one component
                # has more than one independent substitutable connection
                # (an HC-SR04's TRIG and ECHO, an LCD's 6 data lines):
                # deduping by component id alone would silently drop
                # every connection after the first one found.
                other_pin = b if pin == a else a
                if other_pin in seen_pins:
                    continue
                seen_pins.add(other_pin)
                original_leg = pin.split(":", 1)[1]
                final_leg = _final_pin_for_component(state, alias_map, connector_component_ids, board_component_ids,
                                                     _oriented_leg(lesson, state, other_pin))
                if final_leg and final_leg != original_leg:
                    replacements.append((original_leg, final_leg))

    # A sketch may name the board's built-in-LED pin by its constant
    # (LED_BUILTIN, 13 on an Uno/Nano/Mega — the board card's `led_builtin`)
    # instead of the number. Moving that connection must rewrite the
    # constant too, or the shown code keeps driving the old pin (found via a
    # Sonnet-generated Blink that kept the official sketch's LED_BUILTIN).
    led_builtin = _board_led_builtin(diagram_parts)
    for original_leg, final_leg in list(replacements):
        if original_leg == led_builtin:
            replacements.append(("LED_BUILTIN", final_leg))

    return rewrite_pins_in_code(code, replacements)


def _board_led_builtin(diagram_parts):
    library = load_library()
    for part in diagram_parts:
        for card in library.find_by_wokwi_type(part.get("type"), part.get("attrs", {}).get("value")):
            if card.get("led_builtin"):
                return card["led_builtin"]
    return None


# Arduino functions whose arguments are pins, and which argument positions.
PIN_FUNCTION_ARGS = {
    "pinMode": (0,), "digitalWrite": (0,), "digitalRead": (0,), "analogRead": (0,), "analogWrite": (0,),
    "tone": (0,), "noTone": (0,), "pulseIn": (0,), "pulseInLong": (0,), "digitalPinToInterrupt": (0,),
    "shiftOut": (0, 1), "shiftIn": (0, 1), "attach": (0,),
}
_CALL_RE = re.compile(r"\b(" + "|".join(PIN_FUNCTION_ARGS) + r")\s*\(([^()]*)\)")
_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_PIN_MENTION_RE = re.compile(r"(\bpins?\s+(?:<b>)?)(A?\d+)\b", re.I)


def _split_replacements(replacements):
    """Pins named by a distinctive token (A0, LED_BUILTIN) can be replaced
    anywhere; bare numbers only where they're provably a pin."""
    named = {old: new for old, new in replacements if not old.isdigit()}
    numeric = {old: new for old, new in replacements if old.isdigit()}
    return named, numeric


def _replace_named(text, named):
    if not named:
        return text
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(named, key=len, reverse=True)) + r")\b")
    return pattern.sub(lambda m: named[m.group(1)], text)


def rewrite_pin_mentions(text, replacements):
    """Prose (a step's clip or hint): change "pin 13" / "pin <b>13</b>" /
    "pins 2" mentions and distinctive pin names (A0, LED_BUILTIN) — never a
    bare number elsewhere ("group-2 contact", "column 13", "2 legs" stay).
    Every replacement is applied in ONE pass, so one change's target can
    never be re-changed by another."""
    named, numeric = _split_replacements(replacements)
    mapping = {**named, **numeric}
    text = _PIN_MENTION_RE.sub(lambda m: m.group(1) + mapping.get(m.group(2), m.group(2)), text)
    return _replace_named(text, named) if named else text


# A pin array — `int ledPins[] = { 2, 7, 4 };` (Arduino's Arrays example): a
# name with "Pin" in it, initialised with pin numbers only. Its elements are
# pins, and `pinMode(ledPins[i], OUTPUT)` uses them.
PIN_ARRAY_RE = re.compile(r"\b((?:const\s+)?(?:unsigned\s+)?(?:int|byte|uint8_t|short)\s+(\w*[Pp]ins?\w*)\s*\[\s*\d*\s*\]\s*=\s*\{)([^{}]*)(\})")


def pin_arrays(code):
    """{name: [pin, ...]} for every pin array in a sketch."""
    out = {}
    for m in PIN_ARRAY_RE.finditer(code or ""):
        items = [x.strip() for x in m.group(3).split(",") if x.strip()]
        if items and all(re.fullmatch(r"A?\d+", x) for x in items):
            out[m.group(2)] = items
    return out


def rewrite_pins_in_code(code, replacements):
    """An Arduino sketch: change a pin number only where it IS a pin —
    an argument of a pin function (pinMode, digitalRead, analogWrite, tone,
    shiftOut's data/clock, servo.attach, ...), the initialiser of a
    constant/variable/#define those functions are called with, and "pin N"
    mentions inside comments. `delay(2)`, `int arr[2]`, `Serial.begin(9600)`
    are never touched (the old whole-word replace turned delay(2) into
    delay(3) on a pin-2 → 3 substitution). Distinctive names (A0,
    LED_BUILTIN) are replaced everywhere. One pass per kind, so replacements
    stay independent."""
    named, numeric = _split_replacements(replacements)
    if numeric:
        pin_names = set()
        for func, args in _CALL_RE.findall(code):
            parts = [a.strip() for a in args.split(",")]
            for i in PIN_FUNCTION_ARGS[func]:
                if i < len(parts) and re.fullmatch(r"[A-Za-z_]\w*", parts[i]):
                    pin_names.add(parts[i])

        def call(m):
            func, args = m.group(1), m.group(2).split(",")
            for i in PIN_FUNCTION_ARGS[func]:
                if i < len(args) and args[i].strip() in numeric:
                    args[i] = args[i].replace(args[i].strip(), numeric[args[i].strip()])
            head = m.group(0)[: m.start(2) - m.start(0)]
            return f"{head}{','.join(args)})"
        code = _CALL_RE.sub(call, code)
        # Arduino convention also names pin constants "...Pin" (ledPin,
        # buttonPin): treat those as pins even before they're used.
        pin_names |= set(re.findall(r"\b(?:const\s+)?(?:unsigned\s+)?(?:int|byte|uint8_t|short|long)\s+(\w*[Pp]in\w*)\s*=", code))
        pin_names |= set(re.findall(r"#define\s+(\w*(?:[Pp]in|PIN)\w*)\s", code))
        if pin_names:
            names = "|".join(re.escape(n) for n in sorted(pin_names))
            code = re.sub(rf"((?:\b(?:const\s+)?(?:unsigned\s+)?(?:int|byte|uint8_t|short|long)\s+(?:{names})\s*=\s*))(\d+)\b",
                          lambda m: m.group(1) + numeric.get(m.group(2), m.group(2)), code)
            code = re.sub(rf"(#define\s+(?:{names})\s+)(\d+)\b",
                          lambda m: m.group(1) + numeric.get(m.group(2), m.group(2)), code)
        # the numbers inside a pin array are pins too
        code = PIN_ARRAY_RE.sub(lambda m: m.group(1) + ",".join(
            re.sub(r"\d+", lambda d: numeric.get(d.group(0), d.group(0)), x) if re.fullmatch(r"\s*\d+\s*", x) else x
            for x in m.group(3).split(",")) + m.group(4) if all(re.fullmatch(r"\s*A?\d+\s*", x) for x in m.group(3).split(",") if x.strip()) else m.group(0), code)
        code = _COMMENT_RE.sub(lambda m: rewrite_pin_mentions(m.group(0), list(numeric.items())), code)
    return _replace_named(code, named)


def apply_word_boundary_replacements(text, replacements):
    """Apply every (original, new) pair in `replacements` to `text`,
    matching each `original` on a `\\b` word-boundary regex rather than a
    plain substring (see _adjusted_code's docstring for why — a bare
    digit like '5' is a substring of plenty of unrelated text). A
    placeholder pass keeps every replacement independent regardless of
    how many are live at once, so one replacement's target never gets
    corrupted by another replacement whose own target happens to equal
    the first replacement's original (see _adjusted_code's docstring for
    the concrete A2/A0 example this avoids). Shared by _adjusted_code and
    board_translate.py — the "replace this literal everywhere, safely"
    technique is identical whether the replacement set comes from a live
    learner deviation or a one-shot board translation."""
    placeholders = {}
    for i, (original, new) in enumerate(replacements):
        token = f"\x00PIN{i}\x00"
        placeholders[token] = new
        text = re.sub(rf"\b{re.escape(original)}\b", token, text)
    for token, new in placeholders.items():
        text = text.replace(token, new)
    return text


def _final_pin_for_component(state, alias_map, connector_component_ids, board_component_ids, original_pin):
    """Which substitutable pin `original_pin` (the exact scripted
    component:leg, e.g. 'sensor1:ECHO' — NOT just a bare component id) is
    actually confirmed wired to right now, per confirmed_pairs — the
    ground truth, regardless of how many substitutions or remaps led
    there.

    Anchored on this SPECIFIC leg, not merely "some net mentioning this
    component" — a component can have more than one independent
    substitutable connection (an HC-SR04's TRIG and ECHO, an LCD's 6 data
    lines), each living in its own separate net. Matching by component id
    alone can't tell those nets apart and would silently report the
    wrong one's pin for the others — a real bug found via a real 2-pin
    sensor (see the research log (in git history)). `original_pin`'s own side of the
    connection never changes across a substitution or remap (only the
    Arduino side does), so it stays a reliable, stable anchor into
    confirmed_pairs regardless of how the Arduino-side pin evolved.

    Returns the leg (e.g. 'A3' or '7'), or None if this exact connection
    hasn't been confirmed with a substitutable-pin net yet.

    Walks confirmed_pairs MOST-RECENT-FIRST, one hop at a time (component
    leg -> breadboard hole -> Arduino pin), rather than building one flat
    net out of the entire session's history the way an earlier version of
    this function did. That flat-net approach had a real bug (found via a
    real "land the leg on pin X, then re-wire it to a genuinely different
    pin Y before the wiring check" scenario — a bypass landing followed by
    a *different* bypass wiring, not a re-confirmation of the same fact):
    since union-find has no notion of time, an old, superseded fact
    (`original_pin` <-> X) and the new one (`original_pin` <-> Y) both
    still mention `original_pin`, so they got silently merged into one
    net containing BOTH X and Y — and which one this function returned
    depended on Python's (unordered) set/frozenset iteration, i.e. it
    could return the STALE pin instead of the real one, non-
    deterministically. Same "most-recent-first, a newer fact about a pin
    supersedes an older one" principle find_confirmed_pin already uses
    (see its own docstring) — generalized here to follow a multi-hop
    chain instead of a single direct pair, and never revisiting a pin
    once resolved so a stale hop can't be walked back into.

    Backtracks rather than committing to a single straight-line walk:
    a scarce leg can have more than one simultaneously-true partner now
    (a real multi-member net junction, e.g. a pull-down resistor sharing
    a pushbutton leg's own strip with the Arduino pin — see
    _supersede_scarce_leg_pairs's docstring), so the most-recent hop at
    a given node isn't always the one that actually leads to a board
    pin. Trying every distinct neighbor (most-recent-first, never
    revisiting a node within one path) and backtracking on a dead end
    still prefers the freshest route while no longer giving up early
    just because THAT particular hop happened to lead nowhere."""
    if _is_substitutable_pin(original_pin, board_component_ids):
        return original_pin.split(":", 1)[1]

    def neighbors_most_recent_first(node):
        canonical_node = checker._canonicalize_pin(node, alias_map)
        seen = set()
        result = []
        for a, b in reversed(state["confirmed_pairs"]):
            ca = checker._canonicalize_pin(a, alias_map)
            cb = checker._canonicalize_pin(b, alias_map)
            if ca == canonical_node and b not in seen:
                seen.add(b)
                result.append(b)
            elif cb == canonical_node and a not in seen:
                seen.add(a)
                result.append(a)
        return result

    def search(node, visited):
        for neighbor in neighbors_most_recent_first(node):
            if neighbor in visited:
                continue
            if _is_substitutable_pin(neighbor, board_component_ids):
                return neighbor.split(":", 1)[1]
            found = search(neighbor, visited | {neighbor})
            if found is not None:
                return found
        return None

    return search(original_pin, {original_pin})


def initial_state():
    return {
        "step_index": -1,  # -1 = lesson not started yet
        "phase": None,
        "hints_used": 0,
        "last_check": None,
        "mock_result": None,
        "started": False,
        "finished": False,
        "last_shown": None,  # {"type": "clip" | "video", "ref": "..."}
        # Running memory of every connection actually confirmed so far
        # (pass or harmless), across all completed steps — not just the
        # most recent check. This is what lets a later step point to
        # wherever the learner *actually* placed something, if they
        # deviated from the script (PLAN.md Phase 6) — pointing at the
        # scripted location would be wrong once reality has diverged.
        "confirmed_pairs": [],
        # Asked, not assumed — which breadboard the learner actually has
        # ("full" | "half" | "mini"), or None until they've answered.
        "breadboard_variant": None,
        # Every landing step where the learner wired a leg directly to its
        # correct final Arduino pin instead of through the breadboard —
        # electrically fine (the breadboard is this lesson's chosen method,
        # not an electrical requirement), but tracked since it's a real
        # deviation from the taught steps. See _run_landing_check.
        "breadboard_bypasses": [],
        # Every wiring check where the learner used a different pin (same
        # domain — analog or digital, never mixed, see engine._pin_pool)
        # than the lesson's own expected_nets — electrically fine, but the
        # sketch's code needs to reference the actual pin used, so it's
        # tracked and reflected in the code shown at upload.
        "pin_substitutions": [],
        # Every step whose OWN scripted pin target got silently
        # reassigned because an earlier connection already took it (see
        # _compute_pin_remap) — {"step", "component", "original", "actual"}
        # each. Unlike pin_substitutions (the learner's own deviation),
        # this is the engine adapting a later step around someone else's
        # deviation, with no accusation shown to the learner — just an
        # adjusted instruction. Tracked here so the code shown later
        # reflects it too.
        "pin_remaps": [],
        # Asked, not assumed — "beginner" (default) or "advanced". See
        # DIFFICULTIES above.
        "difficulty": "beginner",
        # Hints from any landing step(s) silently skipped to reach the
        # current step (advanced difficulty only) — merged into `hint`'s
        # own answer so the skipped step's guidance isn't lost outright.
        "merged_hints": [],
        # advanced difficulty: the hint ladder for the current step (nudge,
        # then the full instruction), or None to use the step's own hints
        "hint_list": None,
    }


def _breadboard_column_number(pin):
    """pin like 'bb2:6t.a' -> 6, or None if not a breadboard-strip pin."""
    if ":" not in pin:
        return None
    _, leg = pin.split(":", 1)
    strip = leg.split(".", 1)[0]
    digits = "".join(ch for ch in strip if ch.isdigit())
    return int(digits) if digits else None


def _reference_landing_hole(lesson, pin):
    """Last-resort, concrete hint fallback (user request — hint 3 should
    say exactly which hole to use): a landing step like "any open hole in
    that column works" is correct — the checker really doesn't care which
    one — but that freedom can leave a stuck learner with no concrete
    next action once every hint is used up. Rather than fabricate a hole,
    look up the lesson's own reference diagram.json (the worked answer
    key, already loaded for board/parts derivation) for a REAL column
    that pin lands on there, and offer that as one example. Returns a
    column number, or None if the reference diagram doesn't wire this pin
    to a breadboard strip."""
    strip = _reference_landing_strip(lesson, pin)
    return _breadboard_column_number(f"x:{strip}") if strip else None


def _reference_landing_strip(lesson, pin):
    """Like _reference_landing_hole, but returns the full strip id (e.g.
    '7t', not just 7) — needed when two different legs of the SAME
    multi-leg component land in the same numbered column but opposite
    halves of the center gap (e.g. the potentiometer's SIG on 7t, VCC on
    7b — electrically unrelated, despite sharing a column NUMBER): a
    hint naming just "column 7" for both would misleadingly read like a
    self-short. Returns None if the reference diagram doesn't wire this
    pin to a breadboard strip."""
    for connection in lesson.diagram().get("connections", []):
        a, b = connection[0], connection[1]
        other = b if a == pin else (a if b == pin else None)
        if other is None or ":" not in other:
            continue
        leg = other.split(":", 1)[1]
        if "." not in leg:
            continue
        return leg.split(".", 1)[0]
    return None


def plausibility_warning(detected_pairs, breadboard_variant):
    """Not a correctness check — a separate, honest signal. If the learner
    has told us which board they have and a detected column number exceeds
    that board's estimated size, that's worth surfacing (probably a
    detection error, or they answered `board` incorrectly) without
    pretending the underlying tie-point counts are verified enough to gate
    pass/harmless/wrong on. Returns a message, or None if nothing's off."""
    if breadboard_variant not in BREADBOARD_VARIANTS:
        return None
    max_col = BREADBOARD_VARIANTS[breadboard_variant]["max_column_estimate"]
    for pair in detected_pairs:
        for pin in pair:
            col = _breadboard_column_number(pin)
            if col is not None and col > max_col:
                return (
                    f"Detected column {col}, but a '{breadboard_variant}' breadboard "
                    f"is only expected to have about {max_col} — worth double-checking "
                    f"(this is an estimate, not a confirmed spec)."
                )
    return None


def _step(lesson, state):
    return lesson.step(state["step_index"])


def _symmetric_map(lesson, library):
    """{component_instance_id: [[pinA, pinB], ...]} for this lesson's diagram,
    resolved by matching each diagram part's Wokwi type (+ value, for
    resistors) against the library's `symmetric_pins` field."""
    sym_map = {}
    for part in lesson.diagram().get("parts", []):
        wtype = part.get("type")
        value = part.get("attrs", {}).get("value")
        for card in library.find_by_wokwi_type(wtype, value):
            pins = card.get("symmetric_pins")
            if pins:
                sym_map[part["id"]] = pins
    return sym_map


def _compute_pin_remap(lesson, state, step):
    """If this step's own scripted substitutable-pin target (analog or
    digital — see _pin_pool) is already confirmed as belonging to a
    DIFFERENT component (an earlier connection took it — possibly itself
    a substitution), silently reassign this step to a genuinely free pin
    from that same pool instead. No accusation, no forced redo of the
    earlier step — the earlier deviation stands, and this step quietly
    adapts around it. Returns {"original", "actual", "component"} — with
    "actual" itself None if every pin in the pool is already taken by
    someone else (the pool is small: 6 analog, 12 digital — a real
    lesson author needing more same-domain connections than that in one
    circuit is a lesson-authoring problem, not a learner mistake, so it's
    surfaced rather than silently resolved into a bare 'no remap needed',
    which would be indistinguishable from the target already being free)
    — or plain None if this step's own target is already fine as
    scripted, with nothing to remap at all.

    A connection wired to a component's own declared protocol bus leg
    (_leg_is_protocol_bus, e.g. a real I2C device's SDA/SCL) on this
    board's real, fixed protocol pin (the board card's `protocol_pins`)
    is never remapped, even if its scripted pin is taken — I2C/SPI is
    hardware-fixed, so there's no free pin that would actually work as
    its replacement; a real conflict there has to surface as an honest
    'wrong' rather than a fabricated remap that can't work in hardware.
    A component whose leg merely happens to be named SDA/SCL/etc. but
    doesn't declare it as a protocol leg (e.g. the DHT22's data leg) is
    unaffected — see _try_pin_substitution."""
    nets = step.get("expected_nets")
    if not nets:
        return None
    diagram_parts = lesson.diagram().get("parts", [])
    alias_map = checker.board_alias_map(diagram_parts)
    connector_component_ids = checker.connector_ids(diagram_parts)
    board_component_ids = _board_component_ids(diagram_parts)
    for a, b in nets:
        for pin in (a, b):
            pool, _kind = _pin_domain(pin, board_component_ids)
            if pool is None:
                continue
            comp, leg = pin.split(":", 1)
            other_pin = b if pin == a else a
            other_comp = other_pin.split(":", 1)[0]
            if _is_board_protocol_pin(pin, board_component_ids) and _leg_is_protocol_bus(other_pin, diagram_parts):
                continue
            owner = _pin_owner(state["confirmed_pairs"], pin, alias_map, connector_component_ids, other_comp)
            if owner is None or owner == other_comp:
                continue  # not taken by anyone else — no remap needed
            reserved = _reserved_pins(lesson, other_comp)
            protocol_reserved = _protocol_reserved_pins(lesson)
            # Pins already promised to a DIFFERENT component by an
            # earlier remap this same session -- not yet in
            # confirmed_pairs (a remap is only a proactive suggestion
            # until the learner actually wires it), but still off
            # limits, or two different not-yet-resolved components can
            # both get silently pointed at the exact same free pin (a
            # real bug found via a real 8-button diagram whose entire
            # digital pool was in mutual contention: every remaining
            # not-yet-reached component saw the same single leftover pin
            # as "the" free choice at once, since confirmed_pairs only
            # reflects physically completed wiring, not other pending
            # promises). Own component's own prior remap doesn't count
            # here — nets never carries a step that already remapped
            # itself twice.
            already_promised = {
                r["actual"] for r in state["pin_remaps"] if r["component"] != other_comp and r["actual"]
            }
            for alt_leg in sorted(pool - {leg}):
                alt_pin = f"{comp}:{alt_leg}"
                if alt_pin in reserved or alt_pin in protocol_reserved or alt_pin in already_promised:
                    continue
                alt_owner = _pin_owner(state["confirmed_pairs"], alt_pin, alias_map, connector_component_ids, other_comp)
                if alt_owner is not None and alt_owner != other_comp:
                    continue
                return {"original": pin, "actual": alt_pin, "component": other_comp}
            return {"original": pin, "actual": None, "component": other_comp}
    return None


def _effective_expected_nets(lesson, state, expected_pairs):
    """The lesson's scripted expected_pairs, adjusted so every
    substitutable-pin side reflects whichever pin its OWN component leg
    is ACTUALLY confirmed wired to right now (confirmed_pairs is ground
    truth) — so a step's own check (and final_check) validates against
    what the learner is actually being told to use, not the lesson's
    original, now-superseded assumption, and so final_check's combined
    comparison already reflects every deviation individually accepted
    during its own wiring step (final_check bundles EVERY connection in
    the lesson into one combined comparison; a fresh, from-scratch
    substitution search there can never resolve more than one brand-new
    deviation at once — _try_pin_substitution only ever tries a single
    substituted pin per call).

    Replaces the two-step _apply_pin_remaps/_apply_pin_substitutions
    pipeline this used to be (see the research log (in git history)), which resolved a pin
    by replacing its OLD VALUE wherever that exact string appeared
    across the WHOLE pair list, one remap/substitution at a time. That
    was unsound the moment two DIFFERENT components' pin values could
    coincide at different points in a chain of deviations — a real bug
    found via a real 8-button diagram: rotating each button onto the
    next one's scripted pin made one button's OWN raw scripted pin equal
    to a DIFFERENT button's already-resolved actual pin, and the blanket
    string-replace then silently merged unrelated buttons into one
    phantom shared net. Resolving each pair by the component LEG's own
    identity via _final_pin_for_component (the same technique
    _adjusted_code already uses, for exactly this reason) sidesteps that
    whole bug class: each pair's board-side pin is looked up
    independently, anchored on WHICH leg it's for, never on what string
    currently happens to sit there.

    A leg with nothing confirmed yet falls back to checking whether its
    own RAW, pristine scripted pin is the "original" of an active remap
    (state["pin_remaps"] — the engine's own proactive "this step's
    scripted target is already someone else's, quietly aim the
    instruction at a free pin instead" mechanism, see
    _compute_pin_remap) or an already-accepted substitution
    (state["pin_substitutions"]) belonging to a DIFFERENT, already-
    resolved component. Matched against the RAW scripted pin, never
    against an already-mutated value, so this carries none of the
    chain-collision risk a sequence of blanket replacements did: this
    only ever fires when two DIFFERENT components were scripted onto
    the exact same literal pin FROM THE START (a real, deliberate lesson
    pattern — e.g. two LEDs meant to share one signal — where following
    one's deviation for the other is exactly correct), never when a
    coincidence only emerges at runtime partway through an unrelated
    chain of deviations (the actual bug case above: each component's OWN
    raw scripted pin was distinct there, so this fallback never
    activates for it). A leg with neither a confirmed fact nor a
    matching remap/substitution resolves to None and the pair is left
    exactly as scripted — the correct fallback, since there's nothing to
    adjust for a connection the learner hasn't reached yet."""
    diagram_parts = lesson.diagram().get("parts", [])
    alias_map = checker.board_alias_map(diagram_parts)
    connector_component_ids = checker.connector_ids(diagram_parts)
    board_component_ids = _board_component_ids(diagram_parts)
    fallback_by_original = {r["original"]: r["actual"] for r in state["pin_remaps"] if r["actual"]}
    fallback_by_original.update({s["original"]: s["actual"] for s in state["pin_substitutions"]})
    result = []
    for pair in expected_pairs:
        new_pair = list(pair)
        for i, pin in enumerate(pair):
            if not _is_substitutable_pin(pin, board_component_ids):
                continue
            other_pin = _oriented_leg(lesson, state, pair[1 - i])
            final_leg = _final_pin_for_component(state, alias_map, connector_component_ids, board_component_ids, other_pin)
            if final_leg:
                new_pair[i] = f"{pin.split(':', 1)[0]}:{final_leg}"
            elif pin in fallback_by_original:
                new_pair[i] = fallback_by_original[pin]
        result.append(new_pair)
    return result


def _enter_step(lesson, state, step):
    """Returns the clip text to actually show — possibly adjusted for a
    pin remap, silently, with no explanation of why (see
    _compute_pin_remap); the instruction itself just reflects the correct
    current target.

    A remap whose pool is exhausted (_compute_pin_remap's "actual": None
    case) is never persisted to state["pin_remaps"] — there's nothing
    resolved to remember, and every other reader of that list
    (_effective_expected_nets, the `hint` command's pin_change descriptions)
    assumes "actual" is always a real pin. Recomputed fresh each time
    this step is (re-)entered instead, and surfaced as an explicit
    warning rather than silently left pointing at a pin another
    component already owns — the one outcome this whole mechanism must
    never produce is a learner correctly following the script into a
    real, unflagged short between two components."""
    state["phase"] = step["phase"] if step else None
    state["hints_used"] = 0
    state["mock_result"] = None
    state["merged_hints"] = []
    state["hint_list"] = None
    if not step:
        return None
    clip = step["clip"]
    # Advanced difficulty shows only the step's short `goal` ("Connect the
    # LED's long leg to the resistor") and lets the learner work it out; the
    # full beginner instruction becomes a hint (see _advanced_hints).
    if state.get("difficulty") == "advanced" and step.get("goal"):
        clip = step["goal"]
        state["hint_list"] = _advanced_hints([step["clip"]], step.get("hints", []))
    remap = next((r for r in state["pin_remaps"] if r["step"] == step["id"]), None)
    if remap is None:
        computed = _compute_pin_remap(lesson, state, step)
        if computed and computed["actual"] is not None:
            remap = {**computed, "step": step["id"]}
            state["pin_remaps"].append(remap)
        elif computed:
            original_leg = computed["original"].split(":", 1)[1]
            clip = (
                f"{clip} (This lesson has run out of free pins to move "
                f"{computed['component']} off of pin {original_leg}, which "
                "another component already uses — this needs the lesson "
                "author's attention, not something you did wrong.)"
            )
    if remap:
        clip = rewrite_pin_mentions(clip, [(remap["original"].split(":", 1)[1], remap["actual"].split(":", 1)[1])])
    clip = rewrite_pin_mentions(clip, _substitution_text_replacements(state))
    state["last_shown"] = {"type": "clip", "text": clip}
    return clip


def _advanced_hints(instructions, hints):
    """Advanced mode's hint ladder: first a nudge (the step's first hint),
    then the full step-by-step beginner instruction, then any other hints."""
    ladder = hints[:1] + ["Step by step: " + " Then: ".join(instructions)] + hints[1:]
    return ladder


def _skip_landing_steps_for_advanced(lesson, state):
    """In 'advanced' difficulty, a landing step is never its own stop —
    it's silently skipped straight to its paired wiring step, since the
    wiring step's own net check already fully covers correctness on its
    own (a landing pass was never a correctness *requirement*, only a
    beginner-mode pinpointing aid — see PLAN.md's Blink notes). Advances
    state['step_index'] past every consecutive landing step starting from
    wherever it currently points, and returns (clips, hints) collected
    from each one skipped, to merge into whatever step is actually shown.
    A no-op (returns ([], [])) in 'beginner' difficulty or when the
    current step isn't a landing step."""
    if state.get("difficulty") != "advanced":
        return [], []
    clips, hints = [], []
    while True:
        current = _step(lesson, state)
        if current is None or "expected_landing" not in current:
            break
        clips.append(current["clip"])
        hints.extend(current.get("hints", []))
        state["step_index"] += 1
    return clips, hints


def _advance_or_finish(lesson, state, actions):
    """Advance to the next real step, or — once the real steps run out —
    enter the (virtual, not present in `steps`) final_check phase before
    actually finishing. `final_check` is a separate top-level field in
    lesson.json, not a step, so it has to be handled as a transition here
    rather than something `_step()` can ever return."""
    state["step_index"] += 1
    skipped_clips, skipped_hints = _skip_landing_steps_for_advanced(lesson, state)
    next_step = _step(lesson, state)
    if next_step is None:
        if state["phase"] != "final_check":
            state["phase"] = "final_check"
            final_check_text = "Let's check the whole circuit is wired correctly."
            state["last_shown"] = {"type": "clip", "text": final_check_text}
            actions.append({"type": "play_clip", "step": "final_check", "text": final_check_text})
            return
        state["finished"] = True
        actions.append({"type": "complete"})
        return
    clip = _enter_step(lesson, state, next_step)
    if skipped_clips and next_step.get("goal"):
        # advanced with a goal: the placing instructions go into the hints, not the screen
        state["hint_list"] = _advanced_hints(skipped_clips + [next_step["clip"]], skipped_hints + next_step.get("hints", []))
    elif skipped_clips:
        clip = " ".join(skipped_clips + [clip])
        state["last_shown"]["text"] = clip
        state["merged_hints"] = skipped_hints
    actions.append({"type": "play_clip", "step": next_step["id"], "text": clip})
    if next_step["phase"] == "upload":
        actions.append({"type": "show_code", "code": _adjusted_code(lesson, state)})


def _describe_pin(pin, board_component_ids):
    comp, leg = pin.split(":", 1)
    return f"Arduino pin {leg}" if comp in board_component_ids else f"{comp}'s {leg} leg"


def _lost_connections(lesson, library, state, detected):
    """Every connection an EARLIER step confirmed that is no longer on the
    board (a wire came loose, a part was pulled out), judged on a whole-
    board snapshot. Legitimate changes don't count as lost: the same leg
    moved to another free pin of the same kind (the learner changed their
    mind — recorded as a substitution later), a part turned round, a leg
    plugged straight onto its Arduino pin, or extra members a later step
    added. Returns [(step, description)]."""
    diagram_parts = lesson.diagram().get("parts", [])
    alias_map = checker.board_alias_map(diagram_parts, library)
    connectors = checker.connector_ids(diagram_parts, library)
    board_ids = _board_component_ids(diagram_parts, library)
    full_sym = _symmetric_map(lesson, library)
    orientations = state.get("orientations", {})
    nets = [checker._drop_connectors(n, connectors) for n in checker.build_nets(detected, alias_map)]
    present = {checker._canonicalize_pin(p, alias_map) for pair in detected for p in pair}
    built = {checker._canonicalize_pin(p, alias_map) for pair in state.get("confirmed_pairs", []) for p in pair}

    def net_of(pin):
        c = checker._canonicalize_pin(pin, alias_map)
        return next((n for n in nets if c in n), frozenset())

    def still_connected(a, b):
        variants = [(a, b)]
        for comp in {a.split(":", 1)[0], b.split(":", 1)[0]} & set(full_sym):
            variants.append((checker._swap_pin(a, comp, full_sym[comp]), checker._swap_pin(b, comp, full_sym[comp])))
        for x, y in variants:
            if checker._canonicalize_pin(y, alias_map) in net_of(x):
                return True
            for board_pin, leg in ((x, y), (y, x)):
                pool, _ = _pin_domain(board_pin, board_ids, library)
                if pool and any(p.split(":", 1)[0] == board_pin.split(":", 1)[0] and p.split(":", 1)[1] in pool
                                for p in net_of(leg)):
                    return True   # moved to another free pin of the same kind
        return False

    lost = []
    for j in range(max(0, state["step_index"])):
        step = lesson.step(j)
        if not step or step.get("phase") != "build":
            continue
        if step.get("expected_nets"):
            pairs, _ = _apply_orientations(_effective_expected_nets(lesson, state, step["expected_nets"]),
                                           full_sym, orientations)
            for a, b in pairs:
                if not still_connected(a, b):
                    lost.append((step, f"The connection from {_describe_pin(a, board_ids)} to "
                                       f"{_describe_pin(b, board_ids)} (from step '{step['id']}') is gone — it may "
                                       "have come loose. Put it back, then check again."))
        else:
            landing = step.get("expected_landing")
            for pin in [landing] if isinstance(landing, str) else list(landing or []):
                comp = pin.split(":", 1)[0]
                options = {pin} | ({checker._swap_pin(pin, comp, full_sym[comp])} if comp in full_sym else set())
                # Judge against what the learner actually built: a leg that was
                # on the last confirmed board and is gone now has come out, even
                # if an interchangeable leg could have satisfied the step.
                was_there = [o for o in options if checker._canonicalize_pin(o, alias_map) in built]
                gone = [o for o in was_there if checker._canonicalize_pin(o, alias_map) not in present]
                if gone or (not was_there and not any(checker._canonicalize_pin(o, alias_map) in present for o in options)):
                    shown = gone[0] if gone else pin
                    lost.append((step, f"{_describe_pin(shown, board_ids)} (placed in step '{step['id']}') is no longer "
                                       "on the board — put it back, then check again."))
    return lost


def _relations(pairs, alias_map, connectors):
    """Which real pins (component legs, board pins) are electrically joined:
    a set of frozenset pairs, breadboard holes/rails folded away, so moving
    a wire to another hole of the same column is no change at all."""
    rel = set()
    for net in checker.build_nets(pairs, alias_map):
        real = sorted(p for p in checker._drop_connectors(net, connectors))
        rel.update(frozenset(pair) for pair in itertools.combinations(real, 2))
    return rel


def _board_changes(lesson, library, state, detected, step):
    """Compare the board now with the last confirmed board and sort what
    changed (whole-board snapshots only):
      moves   — a leg's Arduino pin changed to another free pin of the same
                kind (the learner changed their mind): [(leg, old, new)]
      turned  — an orientation-locked part is now the other way round: [comp]
      strays  — new connections the lesson's finished circuit doesn't have,
                that this step isn't about: [(pin, pin)]
    Losses are _lost_connections' job."""
    changes = {"moves": [], "turned": [], "strays": []}
    if not state.get("confirmed_pairs"):
        return changes
    diagram_parts = lesson.diagram().get("parts", [])
    alias_map = checker.board_alias_map(diagram_parts, library)
    connectors = checker.connector_ids(diagram_parts, library)
    board_ids = _board_component_ids(diagram_parts, library)
    full_sym = _symmetric_map(lesson, library)
    before = _relations(state["confirmed_pairs"], alias_map, connectors)
    now = _relations(detected, alias_map, connectors)
    if before == now:
        return changes
    added, removed = now - before, before - now

    def comp(p):
        return p.split(":", 1)[0]

    def board_partners(rels, leg):
        return {q for r in rels if leg in r for q in r if q != leg and comp(q) in board_ids}

    # parts turned round (only those whose orientation is already locked)
    for c, sym in full_sym.items():
        if state.get("orientations", {}).get(c) not in ("straight", "swapped"):
            continue
        mine_before = {r for r in before if any(comp(p) == c for p in r)}
        mine_now = {r for r in now if any(comp(p) == c for p in r)}
        if mine_before and not mine_before <= mine_now:
            # everything it had before now holds turned round (a later step
            # may have added more to it at the same time)
            swapped = {frozenset(checker._canonicalize_pin(checker._swap_pin(p, c, sym), alias_map) for p in r)
                       for r in mine_before}
            if swapped != mine_before and swapped <= mine_now:
                changes["turned"].append(c)

    # a leg moved to another free pin of the same kind
    legs = {p for r in added | removed for p in r if comp(p) not in board_ids}
    for leg in sorted(legs):
        old, new = board_partners(before, leg) - board_partners(now, leg), board_partners(now, leg) - board_partners(before, leg)
        if len(old) == 1 and len(new) == 1:
            (o,), (n,) = old, new
            pool, _ = _pin_domain(o, board_ids, library)
            owner = _pin_owner(state["confirmed_pairs"], n, alias_map, connectors, comp(leg))
            if pool and n.split(":", 1)[1] in pool and owner in (None, comp(leg)):
                changes["moves"].append((leg, o, n))

    # strays: new relations the finished circuit can't explain
    orientations = dict(state.get("orientations", {}))
    for c in changes["turned"]:
        orientations[c] = "straight" if orientations.get(c) == "swapped" else "swapped"
    planned_pairs, open_sym = _apply_orientations(_effective_expected_nets(lesson, state, lesson.final_check_nets()),
                                                  full_sym, orientations)
    planned = []
    for variant, _ in checker.symmetric_variants_tagged(planned_pairs, open_sym):
        planned += [checker._drop_connectors(n, connectors) for n in checker.build_nets(variant, alias_map)]
    step_pins = {checker._canonicalize_pin(p, alias_map)
                 for pair in (step or {}).get("expected_nets", []) for p in pair}
    landing = (step or {}).get("expected_landing")
    step_pins |= {checker._canonicalize_pin(p, alias_map) for p in ([landing] if isinstance(landing, str) else landing or [])}
    step_comps = {comp(p) for p in step_pins if comp(p) not in board_ids}
    moved_to = {n for _, _, n in changes["moves"]}

    def same_kind(a, b):
        pool, _ = _pin_domain(a, board_ids, library)
        return bool(pool) and comp(a) == comp(b) and b.split(":", 1)[1] in pool

    def explained(x, y):
        if {x, y} & step_pins or {comp(x), comp(y)} & step_comps or {x, y} & moved_to:
            return True
        for net in planned:
            if x in net and y in net:
                return True
            for a, b in ((x, y), (y, x)):
                if a in net and comp(b) in board_ids and any(same_kind(m, b) for m in net if comp(m) in board_ids):
                    return True
        return False
    changes["strays"] = sorted(tuple(sorted(r)) for r in added if not explained(*sorted(r)))
    return changes


def _apply_board_changes(lesson, library, state, event, step, actions):
    """Run the change comparison on a snapshot check. Returns True if a
    stray connection means this check must fail."""
    if not (isinstance(event, dict) and event.get("snapshot") and _is_valid_pairs(event.get("detected_pairs"))):
        return False
    changes = _board_changes(lesson, library, state, event["detected_pairs"], step)
    board_ids = _board_component_ids(lesson.diagram().get("parts", []), library)
    for c in changes["turned"]:
        state["orientations"][c] = "straight" if state["orientations"][c] == "swapped" else "swapped"
        actions.append({"type": "part_turned", "component": c,
                        "message": f"You turned {c} round since the last check — that's fine, it works either way."})
    state.setdefault("pending_moves", [])
    state["pending_moves"] = [(leg, o, n) for leg, o, n in changes["moves"]]
    if changes["strays"]:
        for x, y in changes["strays"]:
            actions.append({"type": "stray_connection",
                            "message": (f"There's a new connection between {_describe_pin(x, board_ids)} and "
                                        f"{_describe_pin(y, board_ids)} that isn't part of this circuit — check for a "
                                        "stray wire, or a leg in the wrong column.")})
        actions.append({"type": "feedback", "verdict": "wrong", "missing": [], "conflicts": {}})
        return True
    return False


def _announce_moves(state, actions):
    """On a passing check: record and announce every pin the learner moved
    since the last check (chained onto any earlier substitution)."""
    for leg, old, new in state.pop("pending_moves", []):
        state["pin_substitutions"].append({"original": old, "actual": new, "step": "moved"})
        actions.append({
            "type": "pin_substituted",
            "message": (f"You moved {leg} from {old} to {new} — that works fine in hardware, and the code "
                        f"will use {_pin_change_description(old, new)} to match."),
        })


def _record_implied_substitutions(state, step, scripted_pairs, effective_pairs, actions):
    """A step whose target already follows a pin the learner chose earlier
    (e.g. the whole board built before the first check, with pin 12 where
    the script says 13) passes against the pin actually used — record and
    announce that the same way a detected substitution is, so the learner
    is told and every consumer of pin_substitutions sees it."""
    # The pin each original is on NOW, following recorded chains (13→7, 7→12).
    current = {}
    for sub in state["pin_substitutions"]:
        root = next((o for o, a in current.items() if a == sub["original"]), sub["original"])
        current[root] = sub["actual"]
    known = set(current.items())
    known |= {(r["original"], r["actual"]) for r in state.get("pin_remaps", [])}
    for scripted, effective in zip(scripted_pairs, effective_pairs):
        for original, actual in zip(scripted, effective):
            if original == actual or (original, actual) in known:
                continue
            known.add((original, actual))
            state["pin_substitutions"].append({"original": original, "actual": actual, "step": step["id"]})
            actions.append({
                "type": "pin_substituted",
                "message": (
                    f"{actual} was used instead of {original} — that works fine in hardware, but the code needs "
                    f"{_pin_change_description(original, actual)} to match. The code shown at upload will reflect this."
                ),
            })


def _physics_behaviour_mismatches(lesson, library, state, event):
    """Compare what the learner's circuit does (their real wiring + the code
    they'll upload) with what the lesson's own circuit does (its diagram +
    its original code): every LED lit/dark the same way and the same input
    readings, for every button state. Only for real hole-level input."""
    detected = event.get("detected_pairs")
    if not _is_valid_pairs(detected):
        mock = state.get("mock_result")
        detected = mock if isinstance(mock, list) and _is_valid_pairs(mock) else None
    if not detected:
        return []
    parts = lesson.diagram().get("parts", [])
    code = _adjusted_code(lesson, state)
    learner = physics.analyze(detected, parts, code, library)
    design = physics.analyze([c[:2] for c in lesson.diagram().get("connections", [])], parts, lesson.code_text(), library)

    def lit(state_name):
        return state_name != "off"

    messages = []
    design_by_label = {s["label"]: s for s in design["scenarios"]}
    for scenario in learner["scenarios"]:
        expected = design_by_label.get(scenario["label"])
        if expected is None:
            continue
        when = "" if scenario["label"] == "steady state" else f" when {scenario['label']}"
        for led, info in expected["leds"].items():
            got = scenario["leds"].get(led)
            if got and lit(got["state"]) != lit(info["state"]):
                driven = ", ".join(sorted(p for p, m in physics.pin_modes_from_code(code).items() if m == "OUTPUT")) or "no pin"
                messages.append(
                    f"With the code you'll upload, {led} would be {'lit' if lit(got['state']) else 'dark'}{when}, "
                    f"but in this lesson's circuit it's {'lit' if lit(info['state']) else 'dark'}. "
                    f"The sketch drives pin {driven} — check that your LED's wire is on that pin.")
        design_readings = sorted(str(p.get("reading")) for p in expected["pins"].values() if "reading" in p)
        got_readings = sorted(str(p.get("reading")) for p in scenario["pins"].values() if "reading" in p)
        if design_readings != got_readings:
            messages.append(f"With the code you'll upload, the input reads {', '.join(got_readings) or 'nothing'}{when}, "
                            f"but in this lesson's circuit it reads {', '.join(design_readings)}.")
    return messages


def _physics_hazards(lesson, library, state, event):
    """Hazard-severity findings from solving the learner's actual circuit
    (core/physics.py), or [] when there's nothing concrete to solve: only
    real hole-level input (explicit detected_pairs, or pairs stashed by
    `sim`) is solved — a label-synthesized circuit is the answer key
    itself, not something the learner built."""
    detected = event.get("detected_pairs")
    if not _is_valid_pairs(detected):
        mock = state.get("mock_result")
        detected = mock if isinstance(mock, list) and _is_valid_pairs(mock) else None
    if not detected:
        return []
    result = physics.analyze(detected, lesson.diagram().get("parts", []), _adjusted_code(lesson, state), library)
    return [f for f in result["findings"] if f["severity"] == "hazard"]


def _is_valid_pairs(value):
    """A well-formed detected_pairs: a list of [str, str] pairs. Anything
    else (found by chaos testing — a stray dict/int/wrong-length item
    reaching build_nets' unpacking) is rejected here rather than crashing
    downstream. Same Phase 6 concern as handle_event's event-shape guard:
    this can eventually be assembled from LLM output."""
    if not isinstance(value, list):
        return False
    return all(
        isinstance(item, (list, tuple)) and len(item) == 2
        and all(isinstance(p, str) for p in item)
        for item in value
    )


def _resolve_detected(event, state, synth_fn):
    """Shared detected-pairs resolution for both net checks and landing
    checks. Precedence: explicit detected_pairs on the event (validated) >
    a raw pairs list stashed by `sim` (real hole-level input, so the actual
    checker — not a canned label — determines the verdict; see COMMANDS.md)
    > a label (from the event or a `sim`-stashed string) synthesized via
    `synth_fn`, defaulting to "wrong". Malformed detected_pairs is ignored
    (with an error action) and falls through to the label path rather than
    aborting the check outright.

    Returns (detected_pairs, error_message_or_None).
    """
    detected = event.get("detected_pairs")
    error = None
    if detected is not None:
        if _is_valid_pairs(detected):
            return detected, None
        error = "Malformed detected_pairs — ignoring."
        detected = None

    mock = state.get("mock_result")
    if isinstance(mock, list) and _is_valid_pairs(mock):
        return mock, error

    label = event.get("label") or (mock if isinstance(mock, str) else None) or "wrong"
    return synth_fn(label), error


def _apply_orientations(expected_pairs, sym_map, orientations):
    """Rewrite expected pairs for every component whose orientation an
    earlier step already fixed: a part confirmed turned round (e.g. 5V on
    the pushbutton's group 1 instead of group 2) stays turned round for
    the rest of the lesson. Returns (pairs, sym_map with locked parts
    removed, so they can't be swapped again)."""
    pairs = expected_pairs
    for comp_id, orientation in orientations.items():
        if orientation == "swapped" and comp_id in sym_map:
            pairs = [[checker._swap_pin(a, comp_id, sym_map[comp_id]), checker._swap_pin(b, comp_id, sym_map[comp_id])]
                     for a, b in pairs]
    return pairs, {c: p for c, p in sym_map.items() if c not in orientations}


def _symmetric_components_in(pairs, sym_map):
    """Components whose declared symmetric legs appear in `pairs`."""
    found = set()
    for pair in pairs:
        for pin in pair:
            comp = pin.split(":", 1)[0]
            if comp in sym_map and checker._swap_pin(pin, comp, sym_map[comp]) != pin:
                found.add(comp)
    return found


def _run_check(lesson, library, state, step, expected_pairs, event, actions, on_pass):
    """Orientation lock (state["orientations"]): a symmetric part (a
    resistor's legs, a potentiometer's outer legs, a pushbutton's two
    contact groups) can go either way round — until a confirmed step fixes
    which way. From then on, later steps expect that orientation, so a
    second connection can't reuse the leg/group the first one already took
    (e.g. pin 2 on the same button group as 5V is a short, not a swap)."""
    orientations = state.setdefault("orientations", {})
    full_sym_map = _symmetric_map(lesson, library)
    turned_round = {c for c, o in orientations.items() if o == "swapped"} & _symmetric_components_in(expected_pairs, full_sym_map)
    expected_pairs, sym_map = _apply_orientations(expected_pairs, full_sym_map, orientations)
    diagram_parts = lesson.diagram().get("parts", [])
    alias_map = checker.board_alias_map(diagram_parts)
    connector_component_ids = checker.connector_ids(diagram_parts)
    board_component_ids = _board_component_ids(diagram_parts)
    detected, error = _resolve_detected(
        event, state, lambda label: checker.synthesize_detected(label, expected_pairs, sym_map)
    )
    if error:
        actions.append({"type": "error", "message": error})
    result = checker.check(expected_pairs, detected, sym_map, alias_map, connector_component_ids)

    if result["verdict"] == "pass" and turned_round:
        # Matches the orientation the learner chose earlier — still a
        # deviation from the script, so flagged the same way the original swap was.
        result = {"verdict": "harmless", "missing": [], "note": "matched via symmetric pin swap",
                  "swapped": sorted(turned_round)}

    substitution = None
    if result["verdict"] == "wrong":
        planned_pairs, _ = _apply_orientations(_effective_expected_nets(lesson, state, lesson.final_check_nets()),
                                               full_sym_map, orientations)
        alt_result, original_pin, actual_pin = _try_pin_substitution(
            expected_pairs, detected, sym_map, alias_map, connector_component_ids, state["confirmed_pairs"],
            board_component_ids=board_component_ids, lesson=lesson, planned_pairs=planned_pairs,
        )
        if alt_result:
            result = alt_result
            substitution = {"original": original_pin, "actual": actual_pin}

    if result["verdict"] == "wrong":
        # Last resort: the learner may have reached the exact same real
        # circuit a different way than the graph literally describes
        # (e.g. wired a second component straight to the Arduino pin the
        # first one uses, instead of sharing the first component's own
        # leg) — electrically identical, just not an exact net-member
        # match. Narrowly scoped: the only tolerated "extra" net member
        # is the board's own pin, never another component leg (see
        # _try_net_superset_match's docstring for why).
        planned_pairs, _ = _apply_orientations(_effective_expected_nets(lesson, state, lesson.final_check_nets()),
                                               full_sym_map, orientations)
        superset_result = _superset_any_orientation(expected_pairs, detected, sym_map, planned_pairs, alias_map,
                                                    connector_component_ids, board_component_ids)
        if superset_result:
            result = superset_result

    short_message = None
    if result["verdict"] in ("pass", "harmless"):
        short_message = _cross_step_short(lesson, state, alias_map, connector_component_ids, board_component_ids, detected,
                                          snapshot=isinstance(event, dict) and bool(event.get("snapshot")))
        if short_message:
            # A cross-step short takes priority over an otherwise-passing
            # verdict (and over announcing a substitution as if it were
            # accepted) — caught here, immediately, rather than only at
            # final_check (see the research log (in git history)).
            result = {"verdict": "wrong", "missing": [], "conflicts": {}}
            substitution = None

    state["last_check"] = result

    warning = plausibility_warning(detected, state.get("breadboard_variant"))
    if warning:
        actions.append({"type": "plausibility_warning", "message": warning})

    if substitution:
        state["pin_substitutions"].append({**substitution, "step": step["id"] if step else "final_check"})
        actions.append({
            "type": "pin_substituted",
            "message": (
                f"{substitution['actual']} was used instead of {substitution['original']} — that works "
                "fine in hardware, but the code needs "
                f"{_pin_change_description(substitution['original'], substitution['actual'])} to match. "
                "The code shown at upload will reflect this."
            ),
        })

    if result["verdict"] == "wrong" and short_message:
        actions.append({"type": "substitution_refused", "message": short_message})
        actions.append({"type": "feedback", "verdict": "wrong", "missing": [], "conflicts": {}})
        return

    if result["verdict"] == "wrong":
        hint = _refusal_hint(result, board_component_ids, lesson, library)
        if hint:
            actions.append({"type": "substitution_refused", "message": hint})
        actions.append({
            "type": "feedback", "verdict": "wrong",
            "missing": result["missing"], "conflicts": result.get("conflicts", {}),
        })
        return
    if result["verdict"] == "harmless":
        actions.append({"type": "feedback", "verdict": "harmless", "note": result.get("note")})
    # Remember what was actually confirmed (pass or harmless) — not what the
    # script assumed — so a later step can point to where a component
    # really ended up if the learner deviated. See find_confirmed_pin below.
    _record_confirmed(state, event, detected, board_component_ids, connector_component_ids, library)
    swapped = set(result.get("swapped", []))
    for comp in _symmetric_components_in(expected_pairs, sym_map):
        orientations[comp] = "swapped" if comp in swapped else "straight"
    on_pass()


def _check_multi_leg_landing(pins, detected, connector_component_ids, alias_map):
    """The list-valued analogue of checker.check_landed, for a part whose
    physical placement seats several legs at once (PARTS.md's
    `legs_placed_together` — a potentiometer's three legs, a pushbutton's
    two contact groups). Every leg must land in some breadboard hole, AND
    no two of them may share the same column — a self-short between two
    of the SAME component's own legs (e.g. a potentiometer's GND and VCC
    both landing in one column), found via a real gap: a single-pin
    landing check for just one of these legs never looked at where the
    OTHERS ended up, so this kind of mistake wasn't caught until a much
    later wiring step, not at the moment it actually happened.

    Deliberately does NOT try checker.check_landed's per-pin symmetric-pin
    tolerance here (e.g. the potentiometer's declared GND/VCC swap) —
    checking several legs' worth of that at once risks double-counting
    one real physical leg against two different roles. A symmetric swap
    is still accepted normally, just one step later, at the wiring check
    (checker.check already treats a consistent swap as harmless there)."""
    missing = []
    conflicts = {}
    for pin in pins:
        result = checker.check_landed(pin, detected, connector_component_ids, [], alias_map)
        if result["verdict"] != "pass":
            missing.append(pin)
            conflicts.update(result.get("conflicts", {}))
    nets = [checker._drop_connectors(n, connector_component_ids) for n in checker.build_nets(detected, alias_map)]
    canon = {pin: checker._canonicalize_pin(pin, alias_map) for pin in pins}
    # Legs that fold to the SAME canonical pin (a pushbutton's 1.l and 1.r)
    # are one internal node by construction — sharing a net is not a short,
    # so a landing may list all four button legs, not just one per group.
    shorted = [
        [pin for pin in pins if canon[pin] in net]
        for net in nets
        if len({canon[pin] for pin in pins if canon[pin] in net}) > 1
    ]
    if shorted:
        conflicts["shorted_together"] = shorted
    if not missing and not shorted:
        return {"verdict": "pass", "missing": []}
    return {"verdict": "wrong", "missing": missing, "conflicts": conflicts}


def _multi_leg_bypass(lesson, state, sym_map, alias_map, connector_component_ids, missing_pins, detected):
    """Generalizes the single-pin breadboard-bypass check below to the
    multi-leg landing case (user request: the underlying logic must not
    assume a breadboard is always the tool in use — a learner, or a
    future LLM-authored lesson, might describe a circuit wired directly,
    with no breadboard at all). A leg wired straight to its own correct
    final Arduino pin is electrically fine regardless of which physical
    method made the connection.

    For each leg in missing_pins (never landed on any breadboard hole),
    finds its own actual wire in `detected` and tries it against EVERY
    expected_nets entry in the WHOLE lesson script — not just the one
    literally naming that pin, and not just the literal next step. That
    breadth matters for a symmetric pair under a power swap: e.g. the
    potentiometer's VCC leg bypassed straight to the Arduino pin the
    script calls "GND" is a valid bypass of GND's OWN net (via checker.
    check's ordinary symmetric-swap handling), even though the net that
    literally names "pot1:VCC" is a completely different one (wired to
    5V). Checking only the nets that name the pin by its own literal name
    would miss this. Returns {pin: verdict} for each pin resolved this
    way ("pass" or "harmless" — e.g. a bypass wire that also used a
    declared symmetric-pin swap, same distinction the breadboard-mediated
    check already preserves rather than flattening into a silent pass)."""
    all_nets = [pair for scripted_step in lesson.data.get("steps", []) for pair in (scripted_step.get("expected_nets") or [])]
    resolved = {}
    for pin in missing_pins:
        # Alias-aware match, not a literal string compare: the physical
        # wire in `detected` may name a different, board-pin-alias-folded
        # leg of the same component than the one this lesson happens to
        # script (e.g. the pushbutton's 2.l used where 2.r is scripted —
        # always the same net, not a deviation at all).
        canonical_pin = checker._canonicalize_pin(pin, alias_map)
        partner = None
        for a, b in detected:
            if checker._canonicalize_pin(a, alias_map) == canonical_pin:
                partner = b
                break
            if checker._canonicalize_pin(b, alias_map) == canonical_pin:
                partner = a
                break
        if partner is None:
            continue
        own_wire = [[pin, partner]]
        board_component_ids = _board_component_ids(lesson.diagram().get("parts", []))
        for pair in all_nets:
            net = _effective_expected_nets(lesson, state, [pair])
            direct_result = checker.check(net, own_wire, sym_map, alias_map, connector_component_ids)
            if direct_result["verdict"] not in ("pass", "harmless"):
                # Straight onto a DIFFERENT free pin of the same kind (13 → 11):
                # a valid substitute, same as it would be through the
                # breadboard. The wiring step that follows records it.
                alt_result, _, _ = _try_pin_substitution(
                    net, own_wire, sym_map, alias_map, connector_component_ids, state["confirmed_pairs"],
                    board_component_ids=board_component_ids, lesson=lesson)
                direct_result = alt_result or direct_result
            if direct_result["verdict"] in ("pass", "harmless"):
                resolved[pin] = direct_result["verdict"]
                break
    return resolved


def _run_landing_check(lesson, library, state, step, event, actions, on_pass):
    """The 'is this leg plugged into the breadboard yet' half of a wiring
    step (PLAN.md Phase 5 — real wiring is two physical actions, not one
    net check). `step["expected_landing"]` is usually a single pin, not a
    net — but for a part whose placement seats several legs at once (see
    PARTS.md's `legs_placed_together`), it's a list of pins instead,
    checked together via _check_multi_leg_landing."""
    raw_landing = step["expected_landing"]
    multi = isinstance(raw_landing, list)
    diagram_parts = lesson.diagram().get("parts", [])
    alias_map = checker.board_alias_map(diagram_parts)
    connector_component_ids = checker.connector_ids(diagram_parts)
    board_component_ids = _board_component_ids(diagram_parts, library)
    sym_map = _symmetric_map(lesson, library)

    bypassed_pins = []
    if multi:
        pins = raw_landing
        detected, error = _resolve_detected(
            event, state,
            lambda label: checker.synthesize_landed_multi(label, pins, connector_component_ids),
        )
        if error:
            actions.append({"type": "error", "message": error})
        result = _check_multi_leg_landing(pins, detected, connector_component_ids, alias_map)

        # A leg wired DIRECTLY to its own final Arduino pin, skipping the
        # breadboard entirely, is electrically fine regardless of whether
        # the LESSON teaches breadboard-mediated wiring or not — the
        # circuit doesn't care which tool made the connection (a
        # breadboard, a wire nut, solder, ...), only that the electrical
        # net is right. Generalized from the single-pin bypass below to
        # the multi-leg case: each still-missing leg gets its OWN search,
        # since each one's real wiring step can be a different distance
        # away (not just "the literal next step").
        if result["missing"]:
            resolved = _multi_leg_bypass(lesson, state, sym_map, alias_map, connector_component_ids, result["missing"], detected)
            # Only the "missing" half can be excused this way -- a
            # shorted_together conflict is a real, unrelated mistake that
            # bypassing a DIFFERENT leg's wiring can't fix.
            if set(resolved) == set(result["missing"]) and not result.get("conflicts", {}).get("shorted_together"):
                bypassed_pins = list(resolved)
                # A bypass that ALSO used a declared symmetric-pin swap
                # (e.g. GND/VCC) is harmless, not silently identical to an
                # exact match — same distinction the breadboard-mediated
                # path already preserves, not flattened away just because
                # this route skipped the board.
                if "harmless" in resolved.values():
                    result = {"verdict": "harmless", "missing": [], "note": "matched via symmetric pin swap"}
                else:
                    result = {"verdict": "pass", "missing": []}
    else:
        pin = raw_landing
        comp_id = pin.split(":", 1)[0]
        symmetric_pairs = sym_map.get(comp_id, [])

        detected, error = _resolve_detected(
            event, state,
            lambda label: checker.synthesize_landed(label, pin, connector_component_ids, symmetric_pairs),
        )
        if error:
            actions.append({"type": "error", "message": error})
        result = checker.check_landed(pin, detected, connector_component_ids, symmetric_pairs, alias_map)

        # A leg wired DIRECTLY to its correct final Arduino pin, skipping the
        # breadboard entirely, is electrically fine — the breadboard is this
        # lesson's chosen method, not an electrical requirement. If the plain
        # landing check failed, check whether the *whole* final net (the
        # paired wiring step's own expected_nets) is already satisfied as-is;
        # if so, accept it here too, rather than forcing a pointless second
        # wire into the board. User request: allow it, but explain the
        # deviation, warn about it, and track it (not silent).
        if result["verdict"] == "wrong":
            next_step = lesson.step(state["step_index"] + 1)
            if next_step and "expected_nets" in next_step:
                next_expected = _effective_expected_nets(lesson, state, next_step["expected_nets"])
                direct_result = checker.check(next_expected, detected, sym_map, alias_map, connector_component_ids)
                if direct_result["verdict"] not in ("pass", "harmless"):
                    alt_result, _, _ = _try_pin_substitution(
                        next_expected, detected, sym_map, alias_map, connector_component_ids, state["confirmed_pairs"],
                        board_component_ids=board_component_ids, lesson=lesson)
                    direct_result = alt_result or direct_result
                if direct_result["verdict"] in ("pass", "harmless"):
                    result = direct_result
                    bypassed_pins = [pin]

    short_message = None
    if result["verdict"] in ("pass", "harmless"):
        short_message = _cross_step_short(lesson, state, alias_map, connector_component_ids, board_component_ids, detected,
                                          snapshot=isinstance(event, dict) and bool(event.get("snapshot")))
        if short_message:
            result = {"verdict": "wrong", "missing": [], "conflicts": {}}
            bypassed_pins = []

    state["last_check"] = result

    warning = plausibility_warning(detected, state.get("breadboard_variant"))
    if warning:
        actions.append({"type": "plausibility_warning", "message": warning})

    if result["verdict"] == "wrong" and short_message:
        actions.append({"type": "substitution_refused", "message": short_message})
        actions.append({"type": "feedback", "verdict": "wrong", "missing": [], "conflicts": {}})
        return

    for bp in bypassed_pins:
        state["breadboard_bypasses"].append({"pin": bp, "step": step["id"]})
        actions.append({
            "type": "breadboard_bypassed",
            "message": (
                f"{bp} was wired directly to its final Arduino pin, skipping the "
                "breadboard — that still works electrically (the breadboard is just "
                "this lesson's chosen method, not a requirement), but it's a real "
                "deviation from the taught steps, so it's flagged rather than silent. "
                "A plain jumper wire's pin end has nothing to grip a bare leg with, "
                "so this needs either an alligator clip test lead (solderless) or, "
                "for advanced users, a soldered joint."
            ),
        })

    if result["verdict"] == "wrong":
        actions.append({
            "type": "feedback", "verdict": "wrong",
            "missing": result["missing"], "conflicts": result.get("conflicts", {}),
        })
        return
    if result["verdict"] == "harmless":
        actions.append({"type": "feedback", "verdict": "harmless", "note": result.get("note")})
    _record_confirmed(state, event, detected, board_component_ids, connector_component_ids, library)
    on_pass()


def _occupied_column_note(state, pin):
    """Proactive 'that spot's taken' hint (user request): if another leg of
    this same component already landed on a breadboard column, per
    confirmed_pairs, say which one and where — before the learner makes
    the mistake of reusing it. A component's own legs are never meant to
    share a column (that would tie them together, which is wrong unless
    they're a declared symmetric pair) — this is exactly the kind of
    physical constraint a real learner benefits from hearing in advance,
    even though it's not needed for correctness (an accidental reuse
    already surfaces as a `wrong` verdict with a `conflicts` entry — see
    checker.check's docstring)."""
    comp_id, _, leg = pin.partition(":")
    for a, b in state["confirmed_pairs"]:
        for mine, other in ((a, b), (b, a)):
            if not mine.startswith(f"{comp_id}:") or mine == pin:
                continue
            other_comp, _, other_leg = other.partition(":")
            if "." in other_leg:
                strip = other_leg.split(".", 1)[0]
                mine_leg = mine.split(":", 1)[1]
                return (
                    f"Heads up: {comp_id}'s {mine_leg} leg is already in column "
                    f"{other_comp}:{strip} — use a different column for this leg."
                )
    return None


def find_confirmed_pin(state, component_id, leg):
    """Where did `component_id:leg` actually end up, per everything
    confirmed so far this session — not the lesson's scripted assumption?
    Returns the other end of the connection it was actually confirmed
    plugged into, or None if that pin hasn't been confirmed yet. This is
    what a later step's pointing logic should call instead of trusting the
    script once a learner may have deviated (PLAN.md Phase 6).

    Searches most-recent-first: since a wiring step is now two confirmed
    facts (leg -> breadboard hole from the landing check, then leg's net
    -> Arduino pin from the wiring check), the same pin can appear in more
    than one confirmed_pairs entry. The later one is the more complete,
    freshest truth — e.g. once the wiring half has run, "where did GND end
    up" should answer with the Arduino pin, not the earlier breadboard-only
    landing fact."""
    pin = f"{component_id}:{leg}"
    for a, b in reversed(state["confirmed_pairs"]):
        if a == pin:
            return b
        if b == pin:
            return a
    return None


def handle_event(lesson, library, state, event):
    token = _FIXED_PINS.set(bool(lesson.data.get("fixed_pins")))
    try:
        return _handle_event(lesson, library, state, event)
    finally:
        _FIXED_PINS.reset(token)


def _handle_event(lesson, library, state, event):
    state = copy.deepcopy(state)
    actions = []

    # Events will eventually be assembled from LLM output (PLAN.md Phase 6):
    # "constrained JSON... code validates the action is legal" — that
    # validation has to survive a malformed/misbehaving model response, not
    # just well-formed CLI input. Anything not shaped like {"command": str}
    # is rejected as an error action, never allowed to reach the logic below.
    if not isinstance(event, dict) or not isinstance(event.get("command"), str):
        actions.append({"type": "error", "message": "Malformed event — expected a dict with a string 'command'."})
        return state, actions

    command = event.get("command")

    if command == "start":
        if state["started"]:
            actions.append({"type": "error", "message": "Lesson already started."})
            return state, actions
        state["started"] = True
        state["step_index"] = 0
        step = _step(lesson, state)
        clip = _enter_step(lesson, state, step)
        actions.append({"type": "play_clip", "step": step["id"], "text": clip})
        return state, actions

    if not state["started"]:
        actions.append({"type": "error", "message": "Lesson hasn't started — say 'start' first."})
        return state, actions

    step = _step(lesson, state)
    phase = state["phase"]

    if command == "done":
        # `finished` means the LAST whole-circuit check passed. The bench
        # stays open after a win, so a re-check is judged from scratch and
        # only a pass (which sets it again in _finish) completes it again.
        if state["finished"] and phase == "final_check":
            state["finished"] = False
        if phase == "gather":
            _advance_or_finish(lesson, state, actions)
            return state, actions

        if phase == "build":
            # Before judging this step, make sure everything earlier steps
            # confirmed is still on the board (whole-board snapshots only —
            # partial `sim` input can't show what's missing).
            if event.get("snapshot") and _is_valid_pairs(event.get("detected_pairs")):
                lost = _lost_connections(lesson, library, state, event["detected_pairs"])
                if lost:
                    for lost_step, message in lost:
                        actions.append({"type": "connection_lost", "step": lost_step["id"], "message": message})
                    actions.append({"type": "feedback", "verdict": "wrong", "missing": [], "conflicts": {}})
                    return state, actions
            # What changed since the last confirmed board: moved pins,
            # turned parts, stray new connections.
            if _apply_board_changes(lesson, library, state, event, step, actions):
                return state, actions

            def on_pass():
                _announce_moves(state, actions)
                _advance_or_finish(lesson, state, actions)
            if "expected_landing" in step:
                _run_landing_check(lesson, library, state, step, event, actions, on_pass=on_pass)
            else:
                effective_nets = _effective_expected_nets(lesson, state, step["expected_nets"])

                def on_pass_with_implied():
                    _announce_moves(state, actions)
                    _record_implied_substitutions(state, step, step["expected_nets"], effective_nets, actions)
                    _advance_or_finish(lesson, state, actions)
                _run_check(lesson, library, state, step, effective_nets, event, actions, on_pass=on_pass_with_implied)
            return state, actions

        if phase == "upload":
            _advance_or_finish(lesson, state, actions)
            return state, actions

        if phase == "final_check":
            def _finish():
                # The nets match the lesson — now check what the circuit
                # actually DOES (PLAN.md Phase 4). A wiring that matches
                # the script but would burn out a part or short the supply
                # is still wrong on a real bench.
                hazards = _physics_hazards(lesson, library, state, event)
                if hazards:
                    for finding in hazards:
                        actions.append({"type": "physics_hazard", "component": finding["component"],
                                        "kind": finding["kind"], "message": finding["message"]})
                    actions.append({"type": "feedback", "verdict": "wrong", "missing": [], "conflicts": {}})
                    return
                # Safe isn't enough: with the code the learner will upload,
                # the circuit must DO what the lesson's own circuit does.
                mismatches = _physics_behaviour_mismatches(lesson, library, state, event)
                if mismatches:
                    for message in mismatches:
                        actions.append({"type": "physics_hazard", "component": None, "kind": "behaviour", "message": message})
                    actions.append({"type": "feedback", "verdict": "wrong", "missing": [], "conflicts": {}})
                    return
                state["finished"] = True
                actions.append({"type": "complete"})
            # The final check always re-proves everything from scratch; the
            # change comparison adds what changed since the last check.
            summary_start = len(actions)
            if _apply_board_changes(lesson, library, state, event, None, actions):
                return state, actions
            if len(actions) > summary_start or state.get("pending_moves"):
                actions.insert(summary_start, {"type": "board_changes",
                                               "message": "Since your last check: " + "; ".join(
                                                   [a["message"] for a in actions[summary_start:]] +
                                                   [f"{leg} moved from {o} to {n}" for leg, o, n in state.get("pending_moves", [])])})
            effective_final_nets = _effective_expected_nets(lesson, state, lesson.final_check_nets())

            def _finish_recording_moves():
                # A pin moved again after its own step (the learner changed
                # their mind) is only seen here: record and announce it.
                _announce_moves(state, actions)
                _record_implied_substitutions(state, {"id": "final_check"}, lesson.final_check_nets(),
                                              effective_final_nets, actions)
                _finish()
            _run_check(
                lesson, library, state, step, effective_final_nets, event, actions,
                on_pass=_finish_recording_moves,
            )
            return state, actions

    if command == "previous":
        if state["step_index"] <= 0:
            actions.append({"type": "error", "message": "Already at the first step."})
            return state, actions
        new_index = state["step_index"] - 1
        if state.get("difficulty") == "advanced":
            # Landing steps are never a stop of their own in advanced mode
            # (see _skip_landing_steps_for_advanced) — going back must skip
            # past them the same way going forward does, landing on
            # whatever real stop came before, not an intermediate one.
            while new_index >= 0:
                candidate = lesson.step(new_index)
                if candidate is None or "expected_landing" not in candidate:
                    break
                new_index -= 1
            if new_index < 0:
                actions.append({"type": "error", "message": "Already at the first step."})
                return state, actions
        state["step_index"] = new_index
        state["finished"] = False          # stepping back reopens a completed lesson
        prev_step = _step(lesson, state)
        clip = _enter_step(lesson, state, prev_step)
        actions.append({"type": "play_clip", "step": prev_step["id"], "text": clip})
        return state, actions

    if command == "repeat":
        shown = state.get("last_shown")
        if not shown:
            actions.append({"type": "error", "message": "Nothing to repeat yet."})
        elif shown["type"] == "video":
            actions.append({"type": "play_video", "ref": shown["ref"]})
        else:
            actions.append({"type": "play_clip", "step": phase, "text": shown["text"]})
            if phase == "upload":
                # Recomputed fresh, not cached from when upload was first
                # entered — so it still reflects the current
                # pin_substitutions even if something changed since.
                actions.append({"type": "show_code", "code": _adjusted_code(lesson, state)})
        return state, actions

    if command == "reveal":
        # "Show me exactly what goes where": the current step's connections as
        # the engine will check them right now (the learner's swapped pins and
        # turned parts already applied). The page marks them on the real board.
        # Counts as a hint for scoring.
        step = _step(lesson, state)
        if phase != "build" or not step:
            actions.append({"type": "error", "message": "Nothing to reveal here."})
            return state, actions
        if "expected_landing" in step:
            landing = step["expected_landing"]
            actions.append({"type": "reveal", "step": step["id"], "pairs": [],
                            "landing": landing if isinstance(landing, list) else [landing]})
        else:
            pairs, _ = _apply_orientations(_effective_expected_nets(lesson, state, step["expected_nets"]),
                                           _symmetric_map(lesson, library), state.get("orientations", {}))
            actions.append({"type": "reveal", "step": step["id"], "pairs": pairs, "landing": []})
        state["hints_used"] += 1
        return state, actions

    if command == "hint":
        if phase == "upload":
            all_pin_changes = state["pin_substitutions"] + state["pin_remaps"]
            if all_pin_changes:
                subs_desc = "; ".join(
                    f"use {_pin_change_description(s['original'], s['actual'])}"
                    for s in all_pin_changes
                )
                actions.append({
                    "type": "hint",
                    "text": f"Remember: {subs_desc} — that's the pin actually in use.",
                })
            else:
                actions.append({"type": "error", "message": "No hints available here."})
            return state, actions
        if phase == "final_check":
            actions.append({"type": "error", "message": "No hints available here."})
            return state, actions
        if phase == "gather":
            actions.append({"type": "list_items", "items": step["items"]})
            return state, actions
        hints = state.get("hint_list") or (state.get("merged_hints", []) + step.get("hints", []))
        if state["hints_used"] < len(hints):
            text = hints[state["hints_used"]]
            # A hint on a step whose own scripted pin got silently
            # remapped (see _compute_pin_remap) must reflect the SAME
            # adjustment _enter_step already applied to the main
            # instruction — found via a real gap: a learner deviating
            # onto pin 7 caused the buzzer's own step-2 to be remapped
            # to pin 10 (its play_clip correctly said "pin 10"), but
            # asking for a hint on that step still said "pin 7", the
            # stale pre-remap value, since only _enter_step's clip
            # substitution existed, not this one.
            remap = next((r for r in state["pin_remaps"] if r["step"] == step["id"]), None)
            if remap:
                text = rewrite_pin_mentions(text, [(remap["original"].split(":", 1)[1], remap["actual"].split(":", 1)[1])])
            text = rewrite_pin_mentions(text, _substitution_text_replacements(state))
            # _occupied_column_note is single-pin only -- a multi-leg
            # landing step (a list, see PARTS.md's legs_placed_together)
            # already gets its self-short check as part of the regular
            # check itself (_check_multi_leg_landing), so this proactive
            # warning is skipped there rather than generalized: a known,
            # narrow scope limit.
            if "expected_landing" in step and isinstance(step["expected_landing"], str):
                note = _occupied_column_note(state, step["expected_landing"])
                if note:
                    text = f"{text} {note}"
            actions.append({"type": "hint", "text": text})
            state["hints_used"] += 1
        else:
            text = "No more hints for this step."
            if "expected_landing" in step and isinstance(step["expected_landing"], str):
                col = _reference_landing_hole(lesson, step["expected_landing"])
                if col is not None:
                    text = f"Land it in column {col}."
            elif "expected_landing" in step:
                # Multi-leg case (PARTS.md's legs_placed_together): name a
                # real column per leg, same concrete-example spirit as the
                # single-pin case above, from the lesson's own reference
                # diagram.json — never fabricated. Uses the FULL strip id
                # (top/bottom half), not just the bare column number: two
                # legs can share a column NUMBER but sit on opposite,
                # electrically separate sides of the center gap (e.g. the
                # potentiometer's SIG/VCC both land in column 7 here) --
                # naming just "column 7" for both would misleadingly read
                # like a self-short.
                strips = [
                    (pin, _reference_landing_strip(lesson, pin))
                    for pin in step["expected_landing"]
                ]
                if all(strip is not None for _, strip in strips):
                    def _describe(strip):
                        col = _breadboard_column_number(f"x:{strip}")
                        half = "top" if strip.endswith("t") else "bottom" if strip.endswith("b") else None
                        return f"the {half} of column {col}" if half else f"column {col}"
                    parts = ", ".join(f"{pin.split(':', 1)[1]} in {_describe(strip)}" for pin, strip in strips)
                    text = f"Each leg gets its own column, for example: {parts}."
            elif "expected_nets" in step:
                # Same concrete-fallback idea as the landing case above
                # (user request: restate the step's own action, just with
                # the real column/pin filled in — "plug one wire in the
                # same column, then [next step] that same wire connect to
                # the gnd" — not an abstract "try column X" note). Only
                # call it a "wire" when the far end is actually a board
                # pin; a direct component-to-component step (e.g. Blink's
                # LED sharing the resistor's column) has no separate wire
                # at all, so it's phrased as "place it," matching that
                # step's own clip.
                diagram_parts = lesson.diagram().get("parts", [])
                board_ids = _board_component_ids(diagram_parts, library)
                for pair in step["expected_nets"]:
                    for leg, other in (pair, reversed(pair)):
                        if leg.split(":", 1)[0] in board_ids:
                            continue
                        col = _reference_landing_hole(lesson, leg)
                        if col is None:
                            continue
                        if other.split(":", 1)[0] in board_ids:
                            text = f"Connect that same wire to Arduino pin {other.split(':', 1)[1]}."
                        else:
                            text = f"Place it in column {col}, the same column as {other}."
                        break
                    if text != "No more hints for this step.":
                        break
            actions.append({"type": "hint", "text": text})
        return state, actions

    if command == "help":
        # Text-only, deliberately: `help` and `video` are two separate
        # requests now (user request — a learner should be able to ask
        # for just the explanation, or just the video, not always get
        # both bundled). A one-off text description never becomes the
        # `repeat` target either way — see `video` below for why that
        # rule exists.
        item_id = event.get("item")
        card = library.get(item_id) if item_id else None
        if card is None:
            actions.append({"type": "error", "message": f"Unknown item: {item_id}"})
            return state, actions
        in_scope = card["id"] in lesson.data.get("tools_used", []) or card["id"] in lesson.data.get("parts_used", [])
        actions.append({"type": "show_card", "card": card, "in_scope": in_scope})
        return state, actions

    if command == "video":
        item_id = event.get("item")
        card = library.get(item_id) if item_id else None
        if card is None:
            actions.append({"type": "error", "message": f"Unknown item: {item_id}"})
            return state, actions
        clip = card.get("tutorial_clip")
        if not clip:
            actions.append({"type": "error", "message": f"No video available for {card['display_name']}."})
            return state, actions
        actions.append({"type": "play_video", "ref": clip})
        # Only a played *video* becomes the new `repeat` target — a
        # one-off text description (`help`) shouldn't hijack it. Asking
        # for `help` again is how you'd re-hear a description; `repeat`
        # should still mean "say the current step again" until a video
        # actually plays.
        state["last_shown"] = {"type": "video", "ref": clip}
        return state, actions

    if command == "tools":
        tool_ids = lesson.data.get("tools_used", [])
        if not tool_ids:
            actions.append({"type": "list_ids", "kind": "tools", "ids": [], "message": "This lesson doesn't need any tools."})
        else:
            actions.append({"type": "list_ids", "kind": "tools", "ids": tool_ids})
        return state, actions

    if command == "parts":
        part_ids = lesson.data.get("parts_used", [])
        if not part_ids:
            actions.append({"type": "list_ids", "kind": "parts", "ids": [], "message": "This lesson doesn't need any parts."})
        else:
            actions.append({"type": "list_ids", "kind": "parts", "ids": part_ids})
        return state, actions

    if command == "board":
        variant = event.get("variant")
        if variant not in BREADBOARD_VARIANTS:
            actions.append({
                "type": "error",
                "message": f"Unknown breadboard variant '{variant}' — choose one of: {', '.join(BREADBOARD_VARIANTS)}.",
            })
            return state, actions
        state["breadboard_variant"] = variant
        actions.append({"type": "board_set", "variant": variant})
        return state, actions

    if command == "difficulty":
        level = event.get("level")
        if level not in DIFFICULTIES:
            actions.append({
                "type": "error",
                "message": f"Unknown difficulty '{level}' — choose one of: {', '.join(sorted(DIFFICULTIES))}.",
            })
            return state, actions
        state["difficulty"] = level
        actions.append({"type": "difficulty_set", "level": level})
        return state, actions

    if command == "sim":
        if phase not in ("build", "final_check"):
            actions.append({"type": "error", "message": "sim only applies during build/final_check."})
            return state, actions
        raw_pairs = event.get("detected_pairs")
        if raw_pairs is not None:
            # Real hole-level input (e.g. from the CLI's `sim pin-pin ...`
            # syntax) — stored as-is so the *actual* checker determines
            # pass/harmless/wrong on the next `done`, instead of a canned
            # label picking the verdict in advance.
            if not _is_valid_pairs(raw_pairs):
                actions.append({"type": "error", "message": "Malformed detected_pairs — ignoring."})
                return state, actions
            state["mock_result"] = raw_pairs
            actions.append({"type": "sim_set", "pairs": raw_pairs})
            return state, actions
        state["mock_result"] = event.get("label")
        actions.append({"type": "sim_set", "label": event.get("label")})
        return state, actions

    actions.append({"type": "error", "message": f"Unknown command: {command}"})
    return state, actions
