"""Cross-board lesson translation, SAME-FAMILY ONLY (PLAN.md). A lesson is
authored once, against exactly one board — this module runs ONCE, before
a session starts, to produce an equivalent `Lesson` against a *different*
board in the same MCU family, so every existing mechanism downstream
(checker net-folding, engine's pin substitution/remap search,
`_adjusted_code`) keeps working completely unmodified: they already
re-derive everything fresh from `lesson.diagram()`/`lesson.data` on every
call, so once those return board-B data instead of board-A data, nothing
else needs to know translation ever happened.

Family is an explicit board-card field (`mcu_family`: "avr" for
Uno/Nano/Mega, "esp32" for the ESP32 variants) — CROSS-family translation
(e.g. Uno -> any ESP32) is refused outright (see translate_lesson's first
check), never silently attempted: a different family means a different
toolchain/generated-code shape entirely (different `#include`s, different
`Serial`/Wi-Fi boilerplate), not just different pin numbers, and this
module only ever touches pin literals and prose text. Within the AVR
family, translation also does role-aware I2C/SPI pin mapping (see
`_translate_leg`) since those boards have real, hardware-fixed bus pins.
None of the ESP32 cards declare `protocol_pins` at all (confirmed via
each card's own `how_to_use`: the ESP32 GPIO matrix means no bus pin is
hardware-fixed there), so ESP32-family translation is pure plain-GPIO
domain-membership matching — simpler, and doesn't need that mechanism.

KNOWN, FLAGGED GAP (not fixed, no real lesson exercises it yet): each
ESP32 variant's own default UART0 (serial-monitor) pins aren't uniformly
named — the DevKit V1 calls them `RX0`/`TX0`, while the S3/C3/S2/C6 cards
all use bare `RX`/`TX`. These pins are deliberately excluded from
`pin_domains` (same reasoning as the Uno's pins 0/1), so a connection to
one currently falls through to the "keep the literal name as-is" fallback
in `_translate_leg` — correct within a family that shares the same UART0
naming, but WRONG translating to/from the DevKit V1 specifically (it'd
produce a reference to a `RX0`/`TX0` leg that doesn't exist on the
target, or vice versa). No current lesson wires `$serialMonitor` in its
`expected_nets`, so this hasn't caused an actual wrong translation yet —
flagged here rather than guessed at, same as the Nucleo Morpho-header and
DS18B20 1-Wire gaps found earlier this project.

Deliberately NOT wired into `engine.handle_event` — translating a lesson
swaps *which* `lesson` object a session uses, not a `state` transition,
and only ever happens before a lesson starts (see cli.py's `arduino`
command). Mid-lesson board switching is out of scope: `state`'s
`confirmed_pairs` would reference the old board's literal pins with no
defined way to reinterpret already-completed history under a different
board.
"""
import copy
from dataclasses import dataclass, field

from . import checker
from .engine import (
    _board_card,
    _board_component_ids,
    _leg_is_protocol_bus,
    rewrite_pin_mentions,
    rewrite_pins_in_code,
)
from .library import load_library

#: The only alias/leg-name prefixes ever treated as a non-scarce power or
#: ground rail (kept same-literal across every AVR board in this family —
#: confirmed identical naming on Uno/Nano/Mega's own library cards). A
#: board's OWN pin_domains/protocol_pins are always checked first (see
#: _translate_leg) — this is only the fallback for a leg that's neither.
POWER_LEG_PREFIXES = {"GND", "5V", "3V3", "VIN"}


def resolve_target_board(name_or_alias, library=None):
    """The board card for this name/alias (any of its library `aliases`,
    same case-insensitive lookup every other command already uses), or
    None if unrecognized or not actually a board (must declare
    `pin_domains` — see engine._board_card)."""
    if library is None:
        library = load_library()
    card = library.get(name_or_alias)
    if card is None or "pin_domains" not in card:
        return None
    return card


@dataclass
class TranslationResult:
    feasible: bool
    lesson: object = None  # a TranslatedLesson, only when feasible
    infeasible: list = field(default_factory=list)  # [{"pin", "reason"}, ...]
    notes: list = field(default_factory=list)


class TranslatedLesson:
    """Same interface as core.lesson.Lesson (duck-typed — nothing
    downstream cares that this isn't literally that class), wrapping a
    deep-translated copy of the original lesson's `.data`, diagram, and
    code. `folder`/`code_path` are kept pointing at the ORIGINAL lesson's
    files (upload-step video lookups etc. still resolve normally) — only
    `code_text()` is overridden, since that's the one place board-specific
    pin literals actually live in a file on disk."""

    def __init__(self, original, data, diagram, code_text):
        self.data = data
        self.folder = original.folder
        self.id = data["id"]
        self.title = data["title"]
        self.steps = data["steps"]
        self._diagram = diagram
        self._code_text = code_text
        self._original_code_path = original.code_path()

    def step(self, index):
        if 0 <= index < len(self.steps):
            return self.steps[index]
        return None

    def step_count(self):
        return len(self.steps)

    def code_path(self):
        return self._original_code_path

    def diagram_path(self):
        return self.folder / self.data["wokwi_diagram"]

    def diagram(self):
        return self._diagram

    def final_check_nets(self):
        return self.data["final_check"]["expected_nets"]

    def code_text(self):
        return self._code_text


def _leg_kind(leg, card):
    """"analog"/"digital"/None for this bare leg on this board card,
    checked against its own pin_domains — same membership test as
    engine._pin_domain, just against a card directly instead of resolving
    one from a diagram."""
    domains = card.get("pin_domains", {})
    if leg in domains.get("analog", []):
        return "analog"
    if leg in domains.get("digital", []):
        return "digital"
    return None


def _translate_leg(leg, is_real_protocol_connection, source_card, target_card, used_target_legs):
    """One board leg -> (translated_leg, reason_if_infeasible). Checked in
    this order, each one a genuinely different kind of fact:

    1. A real protocol connection (this board's own protocol_pins entry,
       AND confirmed — by the caller, via engine._leg_is_protocol_bus —
       that the far end is a component's own declared bus leg, not just a
       same-named coincidence) translates by ROLE (SDA/SCL/MOSI/MISO/SCK),
       never by literal pin number: two boards' I2C/SPI pins are only
       equivalent role-for-role, never position-for-position (confirmed
       via real docs this session: the Mega's MISO/MOSI at 50/51 are the
       *reverse* relative order of the Uno's MOSI/MISO at 11/12).
    2. An ordinary domain pin (pin_domains membership) prefers keeping the
       exact same literal pin on the target — true for the common case
       within the Uno's own pin range, since Nano/Mega both start their
       numbering identically. A target pin being SPI/I2C-*capable* is not
       by itself a reason to avoid it (the Uno's own digital pool already
       includes its SPI pins 11-13 — capability and current use are
       different facts); the only thing actually avoided is `used_target_
       legs`, i.e. a pin THIS lesson has already assigned on the target
       (whether from an earlier connection, or from a real protocol-role
       translation elsewhere in this same lesson — callers process
       protocol connections first for exactly this reason). Falls back to
       a free pin in the same domain (analog stays analog, digital stays
       digital — an analogRead()-only sketch call is never interchangeable
       with a digitalRead/digitalWrite one) only if the literal pin either
       doesn't exist on the target or is already spoken for.
    3. Anything else (GND/5V/3V3/VIN, or an unrecognized leg) is treated
       as a non-scarce, identically-named rail across this whole board
       family — kept as-is.
    """
    source_protocol = source_card.get("protocol_pins", {}).get(leg)
    if is_real_protocol_connection and source_protocol:
        target_role_to_leg = {
            entry["role"]: pin for pin, entry in target_card.get("protocol_pins", {}).items()
        }
        target_leg = target_role_to_leg.get(source_protocol["role"])
        if target_leg is None:
            return None, (
                f"the target board has no real {source_protocol['protocol']} "
                f"{source_protocol['role']} pin"
            )
        return target_leg, None

    kind = _leg_kind(leg, source_card)
    if kind is not None:
        pool = set(target_card.get("pin_domains", {}).get(kind, []))
        if leg in pool and leg not in used_target_legs:
            return leg, None
        # Numeric-aware sort ("10" before "2" as plain strings would be
        # wrong) so the lowest-numbered free pin is always preferred,
        # for predictable, reproducible translation output.
        candidates = sorted(pool - used_target_legs, key=lambda p: int(p.lstrip("A") or 0))
        if candidates:
            return candidates[0], None
        return None, f"the target board has no free {kind} pin left for this connection"

    bare = leg.split(".", 1)[0]
    if bare in POWER_LEG_PREFIXES:
        return bare, None
    # Unrecognized leg (neither a domain pin, a protocol pin, nor a known
    # power rail) — never guessed at, left exactly as authored, since a
    # board-generic name is the safest default and this project's rule is
    # to never invent a board fact.
    return leg, None


def translate_lesson(lesson, target_card, library=None):
    """See module docstring. Returns a TranslationResult — never a
    partial translation: either every board-leg reference in the lesson
    resolves, or nothing is returned but the infeasible list explaining
    why."""
    if library is None:
        library = load_library()

    source_card = library.get(lesson.data.get("board"))
    if source_card is None or "pin_domains" not in source_card:
        return TranslationResult(
            feasible=False,
            infeasible=[{"pin": None, "reason": "this lesson's own board isn't a recognized board card"}],
        )

    if target_card.get("wokwi_type") == source_card.get("wokwi_type"):
        return TranslationResult(feasible=True, lesson=lesson, notes=["already the target board — no translation needed"])

    source_family = source_card.get("mcu_family")
    target_family = target_card.get("mcu_family")
    if not source_family or not target_family or source_family != target_family:
        return TranslationResult(
            feasible=False,
            infeasible=[{
                "pin": None,
                "reason": (
                    f"cross-family translation isn't supported ({source_card.get('spoken_name', source_card.get('id'))} "
                    f"is '{source_family or 'unknown'}', {target_card.get('spoken_name', target_card.get('id'))} is "
                    f"'{target_family or 'unknown'}') — a different family means different generated code and "
                    "toolchain, not just different pins"
                ),
            }],
        )

    diagram = lesson.diagram()
    diagram_parts = diagram.get("parts", [])
    board_component_ids = _board_component_ids(diagram_parts, library)
    board_ids = [cid for cid, wtype in board_component_ids.items() if wtype == source_card["wokwi_type"]]
    if not board_ids:
        return TranslationResult(
            feasible=False,
            infeasible=[{"pin": None, "reason": "this lesson's diagram has no part matching its own declared board"}],
        )
    board_id = board_ids[0]

    net_lists = [step.get("expected_nets", []) for step in lesson.data.get("steps", [])]
    net_lists.append(lesson.data.get("final_check", {}).get("expected_nets", []))

    # Every distinct board leg referenced, paired with whether its far end
    # is a real protocol-bus connection — collected once up front so
    # protocol-role translations can run BEFORE plain-GPIO ones (below).
    # Order matters: a plain-GPIO leg's "keep the same literal, else find
    # a free one" search must already see any target pin a real I2C/SPI
    # role-translation elsewhere in this same lesson has claimed, or it
    # could silently hand out that exact pin to something else.
    board_legs = {}  # leg -> is_real_protocol_connection
    for nets in net_lists:
        for a, b in nets:
            for pin, other in ((a, b), (b, a)):
                if ":" not in pin:
                    continue
                comp, leg = pin.split(":", 1)
                if comp != board_id or leg in board_legs:
                    continue
                board_legs[leg] = _leg_is_protocol_bus(other, diagram_parts, library)

    leg_map = {}
    used_target_legs = set()
    infeasible = []
    for leg in sorted(board_legs, key=lambda l: not board_legs[l]):  # protocol legs first
        target_leg, reason = _translate_leg(leg, board_legs[leg], source_card, target_card, used_target_legs)
        if target_leg is None:
            infeasible.append({"pin": f"{board_id}:{leg}", "reason": reason})
            continue
        leg_map[leg] = target_leg
        used_target_legs.add(target_leg)

    if infeasible:
        return TranslationResult(feasible=False, infeasible=infeasible)

    text_replacements = [(old, new) for old, new in leg_map.items() if old != new]
    source_spoken = source_card.get("spoken_name") or source_card.get("display_name") or source_card.get("id")
    target_spoken = target_card.get("spoken_name") or target_card.get("display_name") or target_card.get("id")
    if source_spoken and target_spoken and source_spoken != target_spoken:
        text_replacements.append((source_spoken, target_spoken))

    data = copy.deepcopy(lesson.data)
    data["board"] = target_card["id"]
    if source_card["id"] in data.get("parts_used", []):
        data["parts_used"] = [target_card["id"] if p == source_card["id"] else p for p in data["parts_used"]]

    def _translate_nets(nets):
        return [
            [
                f"{board_id}:{leg_map[pin.split(':', 1)[1]]}" if pin.split(":", 1)[0] == board_id and pin.split(":", 1)[1] in leg_map else pin
                for pin in pair
            ]
            for pair in nets
        ]

    for step in data.get("steps", []):
        if "expected_nets" in step:
            step["expected_nets"] = _translate_nets(step["expected_nets"])
        if "clip" in step:
            step["clip"] = rewrite_pin_mentions(step["clip"], text_replacements)
        if "hints" in step:
            step["hints"] = [rewrite_pin_mentions(h, text_replacements) for h in step["hints"]]
        if step.get("phase") == "gather" and source_card["id"] in step.get("items", []):
            step["items"] = [target_card["id"] if i == source_card["id"] else i for i in step["items"]]
    if "final_check" in data:
        data["final_check"]["expected_nets"] = _translate_nets(data["final_check"]["expected_nets"])

    def _translate_pin(pin):
        if ":" not in pin:
            return pin
        comp, leg = pin.split(":", 1)
        if comp == board_id and leg in leg_map:
            return f"{comp}:{leg_map[leg]}"
        return pin

    translated_diagram = copy.deepcopy(diagram)
    for part in translated_diagram.get("parts", []):
        if part.get("id") == board_id:
            part["type"] = target_card["wokwi_type"]
    # A diagram connection is [pinA, pinB, color, routing] — only the two
    # endpoint strings ever need translating, unlike expected_nets (which
    # are always plain [pinA, pinB] pairs, handled by _translate_nets
    # above); reusing that helper here would wrongly try to .split(':')
    # the color string and the routing list.
    translated_diagram["connections"] = [
        [_translate_pin(conn[0]), _translate_pin(conn[1]), *conn[2:]]
        for conn in translated_diagram.get("connections", [])
    ]

    code_text = rewrite_pins_in_code(lesson.code_text(), text_replacements)

    translated = TranslatedLesson(lesson, data, translated_diagram, code_text)
    return TranslationResult(feasible=True, lesson=translated, notes=[f"translated {len(leg_map)} board pin(s)"])
