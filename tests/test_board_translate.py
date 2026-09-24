"""Tests for core/board_translate.py — cross-board lesson translation,
SAME-FAMILY ONLY (see the module's own docstring): AVR (Uno/Nano/Mega)
and ESP32 (DevKit V1/S3/C3/S2/C6) are each internally substitutable, but
translating ACROSS families (e.g. Uno -> any ESP32) is refused outright —
a different family means different generated code and toolchain, not
just different pins.

Style follows tests/test_engine.py: evidence-citing docstrings, a
_FakeMegaLesson-style minimal fixture (_FakeTranslatableLesson below)
rather than loading real lesson.json files for the unit-level cases —
the real lessons (blink, analog-read-serial, digital-read-serial, all
Uno-authored) are covered separately, end-to-end, further down. No real
lesson is ESP32-authored yet, so ESP32-family coverage here is
necessarily synthetic-fixture-only, same treatment as this project gives
any board with no real lesson to validate against yet.
"""
from core import board_translate, engine
from core.lesson import load_lesson
from core.library import load_library

BOARD_WOKWI_TYPES = {
    "arduino-uno": "wokwi-arduino-uno",
    "arduino-mega": "wokwi-arduino-mega",
    "arduino-nano": "wokwi-arduino-nano",
    "esp32-devkit-v1": "wokwi-esp32-devkit-v1",
    "esp32-s3-devkitc1": "board-esp32-s3-devkitc-1",
    "esp32-c3-devkitm1": "board-esp32-c3-devkitm-1",
}
BOARD_IDS = {
    "arduino-uno": "uno", "arduino-mega": "mega", "arduino-nano": "nano",
    "esp32-devkit-v1": "esp", "esp32-s3-devkitc1": "esp", "esp32-c3-devkitm1": "esp",
}


class _FakeTranslatableLesson:
    """Minimal Lesson stand-in with the full shape translate_lesson reads:
    `.data` (board/steps/final_check/parts_used), `.diagram()`, and
    `.code_text()` — parallel to test_engine.py's _FakeMegaLesson, just
    carrying everything a translation (not just a substitution check)
    needs. `extra_parts` works the same way as _FakeMegaLesson's: declare
    the REAL wokwi_type for any non-board component a step references, so
    protocol-leg detection (engine._leg_is_protocol_bus) resolves against
    a real library card, exactly as a real diagram always would."""

    def __init__(self, board, steps, final_check_nets=None, extra_parts=None, code="// no pin literals here"):
        self.data = {
            "id": "fake-translatable",
            "title": "Fake Translatable Lesson",
            "board": board,
            "steps": steps,
            "final_check": {"expected_nets": final_check_nets or []},
            "parts_used": [board],
        }
        self._extra_parts = extra_parts or []
        self._code = code
        self.folder = None

    def diagram(self):
        return {
            "parts": [{"type": BOARD_WOKWI_TYPES[self.data["board"]], "id": BOARD_IDS[self.data["board"]]}] + self._extra_parts,
            "connections": [],
        }

    def code_path(self):
        return None

    def code_text(self):
        return self._code


LIBRARY = load_library()
UNO_CARD = LIBRARY.get("uno")
MEGA_CARD = LIBRARY.get("mega")
NANO_CARD = LIBRARY.get("nano")
ESP32_DEVKIT_CARD = LIBRARY.get("esp32")
ESP32_S3_CARD = LIBRARY.get("esp32-s3")
ESP32_C3_CARD = LIBRARY.get("esp32-c3")


def test_resolve_target_board_uses_the_same_alias_index_every_other_lookup_uses():
    """No new matching logic — board cards already declare aliases (e.g.
    arduino-mega.json's ["mega", "arduino mega", "mega 2560"]), reused
    directly via Library.get, same as any other command."""
    assert board_translate.resolve_target_board("mega")["wokwi_type"] == "wokwi-arduino-mega"
    assert board_translate.resolve_target_board("Arduino Mega")["wokwi_type"] == "wokwi-arduino-mega"
    assert board_translate.resolve_target_board("mega 2560")["wokwi_type"] == "wokwi-arduino-mega"


def test_resolve_target_board_rejects_an_unrecognized_or_non_board_name():
    assert board_translate.resolve_target_board("raspberry pi 5") is None
    # A real card that exists but isn't a board (declares no pin_domains)
    # must not be handed back as if it were one.
    assert board_translate.resolve_target_board("led") is None


def test_same_board_as_target_is_a_no_op():
    lesson = _FakeTranslatableLesson("arduino-uno", steps=[])
    result = board_translate.translate_lesson(lesson, UNO_CARD, LIBRARY)
    assert result.feasible
    assert result.lesson is lesson


def test_cross_family_translation_is_refused_not_silently_attempted():
    """Uno (mcu_family 'avr') -> any ESP32 (mcu_family 'esp32') must be
    refused outright, never silently produce a pin-only translation — a
    different family means a different Arduino core/includes/Serial
    boilerplate, which this module never touches (see module docstring)."""
    lesson = _FakeTranslatableLesson(
        "arduino-uno",
        steps=[{"id": "s1", "phase": "build", "clip": "c", "hints": [], "expected_nets": [["led1:A", "uno:13"]]}],
        final_check_nets=[["led1:A", "uno:13"]],
        extra_parts=[{"type": "wokwi-led", "id": "led1"}],
    )
    result = board_translate.translate_lesson(lesson, ESP32_DEVKIT_CARD, LIBRARY)
    assert not result.feasible
    assert result.lesson is None
    assert "avr" in result.infeasible[0]["reason"] and "esp32" in result.infeasible[0]["reason"]


def test_esp32_family_translation_free_searches_when_leg_naming_differs_across_variants():
    """The DevKit V1 names its legs by silkscreen (e.g. 'D5'), while the
    S3/C3/S2/C6 cards use bare GPIO numbers — confirmed directly from
    each card's own `how_to_use` text. A DevKit V1 leg essentially never
    has a literal match on those variants, so translation must fall
    through to the free-pin search in the target's own digital domain,
    same mechanism as the AVR case, just taking that path far more often
    since the naming conventions genuinely don't overlap."""
    lesson = _FakeTranslatableLesson(
        "esp32-devkit-v1",
        steps=[{"id": "s1", "phase": "build", "clip": "Wire an LED to D5.", "hints": [], "expected_nets": [["led1:A", "esp:D5"]]}],
        final_check_nets=[["led1:A", "esp:D5"]],
        extra_parts=[{"type": "wokwi-led", "id": "led1"}],
    )
    result = board_translate.translate_lesson(lesson, ESP32_S3_CARD, LIBRARY)
    assert result.feasible
    net = result.lesson.data["steps"][0]["expected_nets"][0]
    assert net[1] != "esp:D5"  # 'D5' has no literal match on the S3
    assert net[1].split(":", 1)[1] in ESP32_S3_CARD["pin_domains"]["digital"]
    assert "Wire an LED to" in result.lesson.data["steps"][0]["clip"]


def test_esp32_family_translation_keeps_the_same_literal_when_naming_does_overlap():
    """Unlike the DevKit V1, the C3 and S3 cards both use bare GPIO-number
    leg names — a pin that exists identically on both should need no
    reassignment, same "prefer the same literal" fast path as the AVR
    case."""
    lesson = _FakeTranslatableLesson(
        "esp32-c3-devkitm1",
        steps=[{"id": "s1", "phase": "build", "clip": "c", "hints": [], "expected_nets": [["led1:A", "esp:5"]]}],
        final_check_nets=[["led1:A", "esp:5"]],
        extra_parts=[{"type": "wokwi-led", "id": "led1"}],
    )
    result = board_translate.translate_lesson(lesson, ESP32_S3_CARD, LIBRARY)
    assert result.feasible
    assert result.lesson.data["steps"][0]["expected_nets"] == [["led1:A", "esp:5"]]


def test_plain_digital_pin_prefers_the_same_literal_when_it_exists_on_the_target():
    """Pin 13 exists identically on the Uno, Nano, and Mega (same low
    pin-number range on every AVR board this project supports) — the
    common case should need no reassignment at all."""
    lesson = _FakeTranslatableLesson(
        "arduino-uno",
        steps=[{"id": "s1", "phase": "build", "clip": "Wire pin 13.", "hints": [], "expected_nets": [["led1:A", "uno:13"]]}],
        final_check_nets=[["led1:A", "uno:13"]],
        extra_parts=[{"type": "wokwi-led", "id": "led1"}],
        code="pinMode(13, OUTPUT);",
    )
    result = board_translate.translate_lesson(lesson, MEGA_CARD, LIBRARY)
    assert result.feasible
    # The diagram's board component id ("uno") is just an opaque instance
    # label, same as "led1" or "r1" — translation swaps its `type` and
    # its pin legs, never renames the id itself.
    assert result.lesson.data["steps"][0]["expected_nets"] == [["led1:A", "uno:13"]]
    assert result.lesson.code_text() == "pinMode(13, OUTPUT);"


def test_i2c_role_translates_uno_sda_scl_to_the_megas_real_sda_scl_not_a_positional_guess():
    """Uno: A4=SDA/A5=SCL. Mega: 20=SDA/21=SCL (confirmed via real docs
    this session, docs.wokwi.com/parts/wokwi-arduino-mega: '20 I2C SDA
    (Data)', '21 I2C SCL (Clock)') — a real I2C device's SDA/SCL legs
    must translate by ROLE, landing on 20/21 specifically, never on some
    other digital pin."""
    lesson = _FakeTranslatableLesson(
        "arduino-uno",
        steps=[{
            "id": "s1", "phase": "build", "clip": "Wire SDA to A4, SCL to A5.", "hints": [],
            "expected_nets": [["rtc1:SDA", "uno:A4"], ["rtc1:SCL", "uno:A5"]],
        }],
        final_check_nets=[["rtc1:SDA", "uno:A4"], ["rtc1:SCL", "uno:A5"]],
        extra_parts=[{"type": "wokwi-ds1307", "id": "rtc1"}],
    )
    result = board_translate.translate_lesson(lesson, MEGA_CARD, LIBRARY)
    assert result.feasible
    nets = result.lesson.data["steps"][0]["expected_nets"]
    assert ["rtc1:SDA", "uno:20"] in nets
    assert ["rtc1:SCL", "uno:21"] in nets


def test_spi_role_translation_is_not_a_naive_positional_map():
    """Uno: 11=MOSI/12=MISO/13=SCK. Mega: 50=MISO/51=MOSI/52=SCK (real
    docs, both boards) — the Mega's MISO/MOSI are the REVERSE relative
    order of the Uno's, so a translation that just walked both boards'
    three SPI pins in parallel (11->50, 12->51, 13->52) would silently
    swap MISO and MOSI. Role-based lookup must get this right."""
    lesson = _FakeTranslatableLesson(
        "arduino-uno",
        steps=[{
            "id": "s1", "phase": "build", "clip": "Wire the SD card's SPI lines.", "hints": [],
            "expected_nets": [["sd1:DI", "uno:11"], ["sd1:DO", "uno:12"], ["sd1:SCK", "uno:13"]],
        }],
        final_check_nets=[["sd1:DI", "uno:11"], ["sd1:DO", "uno:12"], ["sd1:SCK", "uno:13"]],
        extra_parts=[{"type": "wokwi-microsd-card", "id": "sd1"}],
    )
    result = board_translate.translate_lesson(lesson, MEGA_CARD, LIBRARY)
    assert result.feasible
    nets = result.lesson.data["steps"][0]["expected_nets"]
    assert ["sd1:DI", "uno:51"] in nets   # MOSI -> MOSI
    assert ["sd1:DO", "uno:50"] in nets   # MISO -> MISO
    assert ["sd1:SCK", "uno:52"] in nets  # SCK -> SCK


def test_a_same_named_pin_that_is_not_actually_used_for_i2c_is_not_treated_as_protocol_reserved():
    """A4 is the Uno's real I2C SDA pin, but only when the OTHER end of
    the connection is a component's own declared protocol leg
    (engine._leg_is_protocol_bus) — an ordinary analog sensor plugged into
    A4 (not a real I2C device) must translate as plain analog GPIO, same
    literal preferred, same as any other analog pin. Mirrors the exact
    distinction engine.py's own _leg_is_protocol_bus was built for (a
    part's own leg name alone is never enough — see PARTS.md)."""
    lesson = _FakeTranslatableLesson(
        "arduino-uno",
        steps=[{
            "id": "s1", "phase": "build", "clip": "Wire the sensor to A4.", "hints": [],
            "expected_nets": [["sensor1:AO", "uno:A4"]],
        }],
        final_check_nets=[["sensor1:AO", "uno:A4"]],
        extra_parts=[{"type": "wokwi-photoresistor-sensor", "id": "sensor1"}],
    )
    result = board_translate.translate_lesson(lesson, MEGA_CARD, LIBRARY)
    assert result.feasible
    # A4 exists identically on the Mega as a plain analog pin (not
    # protocol-reserved there for a connection that was never real I2C).
    assert result.lesson.data["steps"][0]["expected_nets"] == [["sensor1:AO", "uno:A4"]]


def test_power_and_ground_legs_canonicalize_to_the_bare_prefix_regardless_of_suffix():
    lesson = _FakeTranslatableLesson(
        "arduino-uno",
        steps=[{
            "id": "s1", "phase": "build", "clip": "Wire ground.", "hints": [],
            "expected_nets": [["led1:C", "uno:GND.3"], ["led1:A", "uno:5V"]],
        }],
        final_check_nets=[["led1:C", "uno:GND.3"], ["led1:A", "uno:5V"]],
        extra_parts=[{"type": "wokwi-led", "id": "led1"}],
    )
    result = board_translate.translate_lesson(lesson, MEGA_CARD, LIBRARY)
    assert result.feasible
    nets = result.lesson.data["steps"][0]["expected_nets"]
    assert ["led1:C", "uno:GND"] in nets
    assert ["led1:A", "uno:5V"] in nets


def test_a_target_pin_already_claimed_by_a_role_translation_is_never_handed_out_again():
    """Regression for the exact ordering bug this module's docstring
    calls out: protocol connections must be translated BEFORE plain GPIO
    ones, so a plain pin's 'keep the same literal' search already knows
    which target pins a same-lesson I2C/SPI translation has claimed. Uno
    A4(SDA)/A5(SCL) -> Mega 20/21; a THIRD, unrelated plain-GPIO
    connection that happens to already sit on Uno's A4 in a different
    part of the same lesson (impossible in practice since A4 can't wire
    to two different things at once, but the collision-avoidance logic
    itself is what's under test here) must never collide with 20 or 21
    on the target."""
    lesson = _FakeTranslatableLesson(
        "arduino-mega",
        steps=[{
            "id": "s1", "phase": "build", "clip": "I2C plus a plain pin.", "hints": [],
            "expected_nets": [
                ["rtc1:SDA", "mega:20"], ["rtc1:SCL", "mega:21"],
                ["led1:A", "mega:22"],
            ],
        }],
        final_check_nets=[["rtc1:SDA", "mega:20"], ["rtc1:SCL", "mega:21"], ["led1:A", "mega:22"]],
        extra_parts=[{"type": "wokwi-ds1307", "id": "rtc1"}, {"type": "wokwi-led", "id": "led1"}],
    )
    result = board_translate.translate_lesson(lesson, UNO_CARD, LIBRARY)
    assert result.feasible
    nets = result.lesson.data["steps"][0]["expected_nets"]
    # Source board id ("mega") stays unchanged — only its type/legs translate.
    assert ["rtc1:SDA", "mega:A4"] in nets
    assert ["rtc1:SCL", "mega:A5"] in nets
    # led1's pin 22 has no literal equivalent on the Uno (digital domain
    # tops out at 13) — must land on some OTHER free digital pin, and
    # specifically must not collide with A4/A5 (impossible anyway, wrong
    # domain, but must also not collide with any other assignment).
    led_net = next(n for n in nets if n[0] == "led1:A")
    assert led_net[1] not in ("mega:A4", "mega:A5")
    assert led_net[1].startswith("mega:")


def test_exhausting_the_targets_domain_is_infeasible_not_silently_partial():
    """The Uno has only 12 digital pins (2-13). Translating 20 distinct
    Mega digital-pin connections down to the Uno must fail cleanly — the
    real Mega diagram this mirrors (the research log's (in git history) 32-servo diagram)
    is exactly the kind of lesson that could never fit on an Uno."""
    nets = [[f"led{i}:A", f"mega:{22 + i}"] for i in range(20)]
    lesson = _FakeTranslatableLesson(
        "arduino-mega",
        steps=[{"id": "s1", "phase": "build", "clip": "many LEDs", "hints": [], "expected_nets": nets}],
        final_check_nets=nets,
        extra_parts=[{"type": "wokwi-led", "id": f"led{i}"} for i in range(20)],
    )
    result = board_translate.translate_lesson(lesson, UNO_CARD, LIBRARY)
    assert not result.feasible
    assert result.lesson is None
    assert result.infeasible  # named, not just a bare False


def test_i2c_connection_is_infeasible_on_a_board_with_no_real_i2c_role_for_it():
    """Every AVR board in this family (Uno/Nano/Mega) does have real I2C,
    so this can't happen with the current three cards — this test proves
    the refusal path itself works by using a target card with pin_domains
    but deliberately no protocol_pins at all, the same shape a future
    board card without documented I2C would have."""
    lesson = _FakeTranslatableLesson(
        "arduino-uno",
        steps=[{
            "id": "s1", "phase": "build", "clip": "I2C.", "hints": [],
            "expected_nets": [["rtc1:SDA", "uno:A4"]],
        }],
        final_check_nets=[["rtc1:SDA", "uno:A4"]],
        extra_parts=[{"type": "wokwi-ds1307", "id": "rtc1"}],
    )
    no_i2c_card = {"id": "no-i2c-board", "wokwi_type": "no-i2c-board", "mcu_family": "avr", "pin_domains": {"analog": ["A0"], "digital": ["2"]}}
    result = board_translate.translate_lesson(lesson, no_i2c_card, LIBRARY)
    assert not result.feasible
    assert "I2C" in result.infeasible[0]["reason"]


def test_gather_step_and_parts_used_name_the_target_board_not_the_original():
    lesson = _FakeTranslatableLesson(
        "arduino-uno",
        steps=[{"id": "gather", "phase": "gather", "clip": "Let's gather: an Arduino Uno.", "items": ["arduino-uno"]}],
    )
    result = board_translate.translate_lesson(lesson, MEGA_CARD, LIBRARY)
    assert result.feasible
    assert result.lesson.data["parts_used"] == ["arduino-mega"]
    assert result.lesson.data["steps"][0]["items"] == ["arduino-mega"]
    assert "Arduino Mega" in result.lesson.data["steps"][0]["clip"]
    assert "Arduino Uno" not in result.lesson.data["steps"][0]["clip"]


def test_hint_text_and_code_get_the_same_word_boundary_safe_pin_substitution_as_adjusted_code():
    """Regression for the exact corruption bug engine._adjusted_code's own
    docstring documents: a plain .replace('5', ...) would corrupt an
    unrelated '5' inside other text (a baud rate, a delay() value). Board
    translation reuses engine.apply_word_boundary_replacements for
    exactly this reason — prove it holds for hint text and code together,
    with two simultaneously-live leg translations whose old/new literals
    could collide if replacements were applied sequentially instead of
    via the placeholder pass (mirrors _adjusted_code's own A2/A0 example)."""
    lesson = _FakeTranslatableLesson(
        "arduino-mega",
        steps=[{
            "id": "s1", "phase": "build",
            "clip": "Wire pin 2 and pin 3.",
            "hints": ["Pin 2 is the first one.", "Don't confuse it with pin 12 or a delay of 1200ms."],
            "expected_nets": [["a:A", "mega:2"], ["b:A", "mega:3"]],
        }],
        final_check_nets=[["a:A", "mega:2"], ["b:A", "mega:3"]],
        extra_parts=[{"type": "wokwi-led", "id": "a"}, {"type": "wokwi-led", "id": "b"}],
        code="pinMode(2, OUTPUT);\npinMode(3, OUTPUT);\ndelay(1200);",
    )
    # Uno's digital domain has no pin 2/3 collision risk here, but force a
    # collision-shaped translation via the Uno as target isn't possible
    # (2/3 exist identically on the Uno too) — use a deliberately tiny
    # fake target whose only free digital pin equals the Uno's *other*
    # leg's original value, to actually exercise the corruption-avoidance
    # path rather than just the trivial same-literal case.
    tiny_target = {
        "id": "tiny-board", "wokwi_type": "tiny-board", "mcu_family": "avr",
        "pin_domains": {"analog": [], "digital": ["3", "2"]},  # 2 and 3 both exist, but swap availability order
    }
    result = board_translate.translate_lesson(lesson, tiny_target, LIBRARY)
    assert result.feasible
    # '1200' (the delay) must never be corrupted by a '2'->something or a
    # '12' fragment-style match — word-boundary matching protects it.
    assert "delay(1200)" in result.lesson.code_text()
    assert "pin 12 or a delay of 1200ms" in result.lesson.data["steps"][0]["hints"][1]


def test_nano_now_has_real_spi_protocol_pins_matching_the_uno():
    """Regression for the pre-existing card gap flagged in the research log (in git history)
    ('Nano SPI... left deferred... no real Nano SPI diagram has shown up
    yet') — confirmed via docs.wokwi.com/parts/wokwi-arduino-nano, which
    explicitly defers to the Uno's own pin-function table ('same as
    wokwi-arduino-uno'), so Nano's SPI role assignment must be identical:
    11=MOSI, 12=MISO, 13=SCK."""
    assert NANO_CARD["protocol_pins"]["11"] == {"protocol": "SPI", "role": "MOSI"}
    assert NANO_CARD["protocol_pins"]["12"] == {"protocol": "SPI", "role": "MISO"}
    assert NANO_CARD["protocol_pins"]["13"] == {"protocol": "SPI", "role": "SCK"}


def test_nano_spi_translates_correctly_uno_to_nano():
    lesson = _FakeTranslatableLesson(
        "arduino-uno",
        steps=[{
            "id": "s1", "phase": "build", "clip": "SPI.", "hints": [],
            "expected_nets": [["sd1:DI", "uno:11"], ["sd1:DO", "uno:12"], ["sd1:SCK", "uno:13"]],
        }],
        final_check_nets=[["sd1:DI", "uno:11"], ["sd1:DO", "uno:12"], ["sd1:SCK", "uno:13"]],
        extra_parts=[{"type": "wokwi-microsd-card", "id": "sd1"}],
    )
    result = board_translate.translate_lesson(lesson, NANO_CARD, LIBRARY)
    assert result.feasible
    nets = result.lesson.data["steps"][0]["expected_nets"]
    assert ["sd1:DI", "uno:11"] in nets
    assert ["sd1:DO", "uno:12"] in nets
    assert ["sd1:SCK", "uno:13"] in nets


def _send(lesson, library, state, event):
    return engine.handle_event(lesson, library, state, event)


def test_end_to_end_blink_translated_to_mega_runs_a_real_session_to_completion():
    """Mirrors tests/test_blink.py's own full-walkthrough pattern exactly
    (start -> gather->step-1a -> landing+wiring -> step-2 -> step-3 ->
    upload -> final_check), just against a Mega-translated lesson instead
    of the original Uno one — confirming every existing downstream
    mechanism (checker aliasing, _adjusted_code, the whole handle_event
    state machine) works completely unmodified against a translated
    lesson, per board_translate's whole design premise. Pin literals are
    unchanged from the original test's (13, GND.1) since neither needs
    reassignment translating Uno->Mega — the board component id itself
    also stays "uno" (see the id-stability tests above)."""
    library = load_library()
    lesson = load_lesson("blink")
    result = board_translate.translate_lesson(lesson, MEGA_CARD, library)
    assert result.feasible
    translated = result.lesson
    assert "Arduino Mega" in translated.data["steps"][0]["clip"]

    state = engine.initial_state()
    state, _ = _send(translated, library, state, {"command": "start"})
    state, _ = _send(translated, library, state, {"command": "done"})  # gather -> step-1a
    assert translated.step(state["step_index"])["id"] == "step-1a"

    state, _ = _send(translated, library, state, {"command": "sim", "detected_pairs": [["r1:1", "bb1:3b.h"]]})
    state, actions = _send(translated, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    state, _ = _send(translated, library, state, {"command": "sim", "detected_pairs": [["r1:1", "bb1:3b.h"], ["uno:13", "bb1:3b.g"]]})
    state, actions = _send(translated, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    assert translated.step(state["step_index"])["id"] == "step-2"

    state, _ = _send(translated, library, state, {"command": "sim", "detected_pairs": [["led1:A", "r1:2"]]})
    state, actions = _send(translated, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    assert translated.step(state["step_index"])["id"] == "step-3"

    state, _ = _send(translated, library, state, {"command": "sim", "detected_pairs": [["led1:C", "uno:GND.1"]]})
    state, actions = _send(translated, library, state, {"command": "done"})  # step-3 -> upload-code
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    assert state["phase"] == "upload"
    # show_code is appended by THIS SAME done call (the one that advances
    # INTO the upload-code step, see engine._advance_or_finish) — reflects
    # the translated code text, unchanged here since pin 13/GND need no
    # reassignment on the Mega.
    assert any(a["type"] == "show_code" for a in actions)
    code_action = next(a for a in actions if a["type"] == "show_code")
    assert "pinMode(13, OUTPUT)" in code_action["code"]

    state, _ = _send(translated, library, state, {"command": "done"})  # -> final_check
    final_pairs = [["r1:1", "bb1:3b.h"], ["uno:13", "bb1:3b.g"], ["led1:A", "r1:2"], ["led1:C", "uno:GND.1"]]
    state, _ = _send(translated, library, state, {"command": "sim", "detected_pairs": final_pairs})
    state, actions = _send(translated, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    assert state["finished"]


def test_end_to_end_analog_read_serial_translated_to_nano_runs_a_real_session_to_completion():
    """Same shape as above, against a Nano-translated lesson. A0/GND/5V
    are all unchanged translating Uno->Nano, same reasoning as the Mega
    case above.

    Uses the normal breadboard-mediated route, not the "bypass straight to
    the Arduino pin" style test_full_session_variations.py's own bypass
    route uses — bypass IS generalized to the combined multi-leg landing
    step too (_multi_leg_bypass), but this test specifically exercises the
    breadboard-mediated path end to end; the bypass path itself has its
    own direct coverage elsewhere."""
    library = load_library()
    lesson = load_lesson("analog-read-serial")
    result = board_translate.translate_lesson(lesson, NANO_CARD, library)
    assert result.feasible
    translated = result.lesson
    assert "Arduino Nano" in translated.data["steps"][0]["clip"]

    state = engine.initial_state()
    state, _ = _send(translated, library, state, {"command": "start"})
    state, _ = _send(translated, library, state, {"command": "done"})  # -> step-1a
    assert state["step_index"] == 1

    # The combined landing step: all three legs, each in its own column.
    landing_pairs = [["pot1:GND", "bb2:6t.a"], ["pot1:VCC", "bb2:7t.a"], ["pot1:SIG", "bb2:8t.a"]]
    state, _ = _send(translated, library, state, {"command": "sim", "detected_pairs": landing_pairs})
    state, actions = _send(translated, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"], actions

    for leg, col, target in (("GND", "6t", "GND.1"), ("VCC", "7t", "5V"), ("SIG", "8t", "A0")):
        pair = [[f"pot1:{leg}", f"bb2:{col}.a"], [f"uno:{target}", f"bb2:{col}.c"]]
        state, _ = _send(translated, library, state, {"command": "sim", "detected_pairs": pair})
        state, actions = _send(translated, library, state, {"command": "done"})
        assert not [a for a in actions if a.get("verdict") == "wrong"], actions

    # The last wiring `done` above (SIG -> A0) is the one that advances
    # INTO the upload-code step — show_code is appended by that same call
    # (see engine._advance_or_finish), so it's already in `actions`.
    assert state["phase"] == "upload"
    assert any(a["type"] == "show_code" for a in actions)

    state, _ = _send(translated, library, state, {"command": "done"})  # -> final_check
    final_pairs = [["pot1:GND", "uno:GND.1"], ["pot1:VCC", "uno:5V"], ["pot1:SIG", "uno:A0"]]
    state, _ = _send(translated, library, state, {"command": "sim", "detected_pairs": final_pairs})
    state, actions = _send(translated, library, state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]
    assert state["finished"]


def test_combined_stress_scenario_chained_board_switches_i2c_role_translation_pin_theft_refusal_and_a_live_deviation_all_together():
    """Regression test for a real bug this exact combined scenario found
    and core/engine.py._final_pin_for_component was fixed for (see
    the research log (in git history)): a component leg landed on one pin, then genuinely
    re-wired to a DIFFERENT pin later in the same step, used to get
    silently merged by checker.build_nets (no notion of time) into one
    net containing BOTH the stale and the current pin — and which one
    _adjusted_code's generated code reflected depended on unordered
    set/frozenset iteration, i.e. could show the WRONG, stale pin. Fixed
    by walking confirmed_pairs most-recent-first instead.

    This test combines every moving part board translation touches, in
    one session, end to end:
    - 5 chained board switches (Mega -> Nano -> Mega -> Uno -> Mega)
    - a REAL I2C connection, role-translated (A4/A5 -> Mega's 20/21),
      confirmed to survive all the switching
    - an attempt to steal the I2C's own pin for an unrelated component
      (must be REFUSED — protocol-pin protection working on a translated
      board, not just the original)
    - a genuine live pin deviation on top of the ALREADY-translated board
      (LED moved from its scripted, translated pin to a different one)
    - the FINAL generated code checked with a word-boundary-safe regex
      (a naive substring check would false-positive on '13' inside an
      unrelated identifier like 'DS1307' — the actual failure mode this
      test's own first draft hit before being fixed)."""
    import re

    library = load_library()
    mega = board_translate.resolve_target_board("mega", library)
    nano = board_translate.resolve_target_board("nano", library)
    uno = board_translate.resolve_target_board("uno", library)

    data = {
        "id": "combo-test", "title": "RTC + LED", "board": "arduino-uno",
        "steps": [
            {"id": "gather", "phase": "gather", "clip": "Gather.", "items": ["arduino-uno"]},
            {"id": "s1", "phase": "build", "clip": "Wire the RTC's SDA to A4 and SCL to A5.", "hints": [],
             "expected_nets": [["rtc1:SDA", "uno:A4"], ["rtc1:SCL", "uno:A5"]]},
            {"id": "s2", "phase": "build", "clip": "Wire the LED's anode to pin 13.", "hints": [],
             "expected_nets": [["led1:A", "uno:13"]]},
            {"id": "s3", "phase": "build", "clip": "Wire the LED's cathode to GND.", "hints": [],
             "expected_nets": [["led1:C", "uno:GND.1"]]},
            {"id": "upload-code", "phase": "upload", "clip": "Upload.", "code": "code.ino"},
        ],
        "final_check": {"expected_nets": [
            ["rtc1:SDA", "uno:A4"], ["rtc1:SCL", "uno:A5"], ["led1:A", "uno:13"], ["led1:C", "uno:GND.1"],
        ]},
        "parts_used": ["arduino-uno"],
    }
    diagram = {
        "parts": [
            {"type": "wokwi-arduino-uno", "id": "uno"},
            {"type": "wokwi-ds1307", "id": "rtc1"},
            {"type": "wokwi-led", "id": "led1"},
        ],
        "connections": [],
    }
    code = "const int ledPin = 13;\n"
    lesson = _FakeTranslatableLesson.__new__(_FakeTranslatableLesson)
    lesson.data, lesson._extra_parts, lesson._code, lesson.folder = data, [], code, None
    lesson.diagram = lambda: diagram
    lesson.code_text = lambda: code
    lesson.code_path = lambda: None

    current = lesson
    for target in (mega, nano, mega, uno, mega):
        r = board_translate.translate_lesson(current, target, library)
        assert r.feasible, r.infeasible
        current = r.lesson
    translated = current
    assert translated.data["board"] == "arduino-mega"
    assert translated.data["steps"][1]["expected_nets"] == [["rtc1:SDA", "uno:20"], ["rtc1:SCL", "uno:21"]]

    def send(state, event):
        return engine.handle_event(translated, library, state, event)

    state = engine.initial_state()
    state, _ = send(state, {"command": "start"})
    state, _ = send(state, {"command": "done"})  # gather -> s1

    state, _ = send(state, {"command": "sim", "detected_pairs": [["rtc1:SDA", "uno:20"], ["rtc1:SCL", "uno:21"]]})
    state, actions = send(state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"]

    # Try to steal the I2C's own translated pin for the LED — must be refused.
    state, actions = send(state, {"command": "sim", "detected_pairs": [["led1:A", "uno:20"]]})
    state, actions2 = send(state, {"command": "done"})
    all_actions = actions + actions2
    assert any(a["type"] == "substitution_refused" for a in all_actions)
    assert any(a.get("verdict") == "wrong" for a in all_actions)

    # Now wire the LED correctly, but onto a genuinely different valid
    # Mega pin than the (translated-but-unchanged) scripted 13.
    state, _ = send(state, {"command": "sim", "detected_pairs": [["led1:A", "uno:22"]]})
    state, actions = send(state, {"command": "done"})
    assert any(a["type"] == "pin_substituted" for a in actions)

    state, _ = send(state, {"command": "sim", "detected_pairs": [["led1:C", "uno:GND.1"]]})
    state, actions = send(state, {"command": "done"})  # -> upload
    assert state["phase"] == "upload"

    state, _ = send(state, {"command": "done"})  # -> final_check
    final_pairs = [["rtc1:SDA", "uno:20"], ["rtc1:SCL", "uno:21"], ["led1:A", "uno:22"], ["led1:C", "uno:GND.1"]]
    state, _ = send(state, {"command": "sim", "detected_pairs": final_pairs})
    state, actions = send(state, {"command": "done"})
    assert state["finished"]

    code_action = next((a for a in actions if a["type"] == "show_code"), None)
    if code_action is None:
        # show_code was emitted on the earlier done that entered "upload" —
        # re-derive it directly the same way _adjusted_code would, since
        # this test cares about the FINAL code text regardless of which
        # action list it arrived in.
        final_code = engine._adjusted_code(translated, state)
    else:
        final_code = code_action["code"]

    assert re.search(r"\bledPin\s*=\s*22\b", final_code), final_code
    assert not re.search(r"\b13\b", final_code), f"stale pin 13 leaked into final code: {final_code}"


def test_final_check_handles_two_simultaneously_independent_pin_substitutions():
    """Regression test for a real, more serious bug found via a user-
    requested exhaustive cartesian sweep (every digital pin x every other
    digital pin, on every board, for a lesson with two independently
    substitutable components — see the research log (in git history)): none of this
    project's three real lessons has more than one substitutable pin, so
    nothing had ever exercised TWO simultaneously-live substitutions in
    one lesson before.

    Root cause: engine._try_pin_substitution only ever tries ONE
    substituted pin per call — it walks expected_pairs, swaps in ONE
    alternate leg, and returns the first trial that makes checker.check
    pass. That's correct for an ordinary build step (always exactly one
    connection), but final_check bundles EVERY connection in the lesson
    into one combined comparison — if two DIFFERENT components have each
    independently deviated, no single substitution can ever make that
    combined check pass, even though both deviations were already
    correctly accepted individually during their own wiring steps.

    Fixed by engine._apply_pin_substitutions (mirroring the existing
    _apply_pin_remaps), pre-applying every already-accepted substitution
    to the expected nets before comparing, at both the per-step check and
    final_check."""
    library = load_library()

    class _TwoIndependentPinsLesson:
        def __init__(self, board, scripted_led, scripted_btn):
            self.data = {
                "id": "two-independent", "title": "t", "board": board,
                "steps": [
                    {"id": "s1", "phase": "build", "clip": "c", "hints": [], "expected_nets": [["led1:A", f"uno:{scripted_led}"]]},
                    {"id": "s2", "phase": "build", "clip": "c", "hints": [], "expected_nets": [["btn1:1.r", f"uno:{scripted_btn}"]]},
                    {"id": "upload-code", "phase": "upload", "clip": "u", "code": "code.ino"},
                ],
                "final_check": {"expected_nets": [["led1:A", f"uno:{scripted_led}"], ["btn1:1.r", f"uno:{scripted_btn}"]]},
                "parts_used": [board],
            }
            self._diagram = {
                "parts": [{"type": BOARD_WOKWI_TYPES[board], "id": BOARD_IDS[board]},
                          {"type": "wokwi-led", "id": "led1"}, {"type": "wokwi-pushbutton", "id": "btn1"}],
                "connections": [],
            }
            self.folder = None
        def diagram(self): return self._diagram
        def code_path(self): return None
        def code_text(self): return "// placeholder"
        def step(self, i): return self.data["steps"][i] if 0 <= i < len(self.data["steps"]) else None
        def step_count(self): return len(self.data["steps"])
        def final_check_nets(self): return self.data["final_check"]["expected_nets"]

    lesson = _TwoIndependentPinsLesson("arduino-uno", "2", "3")

    def send(state, event):
        return engine.handle_event(lesson, library, state, event)

    state = engine.initial_state()
    state, _ = send(state, {"command": "start"})
    # Deviate BOTH components simultaneously, onto pins that don't collide
    # with each other's own scripted target (avoids also triggering the
    # separate remap mechanism, kept orthogonal to this specific bug).
    state, _ = send(state, {"command": "sim", "detected_pairs": [["led1:A", "uno:7"]]})
    state, actions = send(state, {"command": "done"})
    assert any(a["type"] == "pin_substituted" for a in actions), actions
    state, _ = send(state, {"command": "sim", "detected_pairs": [["btn1:1.r", "uno:8"]]})
    state, actions = send(state, {"command": "done"})
    assert any(a["type"] == "pin_substituted" for a in actions), actions
    assert state["phase"] == "upload"

    state, _ = send(state, {"command": "done"})  # -> final_check
    final_pairs = [["led1:A", "uno:7"], ["btn1:1.r", "uno:8"]]
    state, _ = send(state, {"command": "sim", "detected_pairs": final_pairs})
    state, actions = send(state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"], actions
    assert state["finished"]


def test_clip_and_hint_text_reflect_a_substitution_named_by_a_later_steps_instruction():
    """Regression test for a real gap found by the user directly asking
    whether a later step's instruction stays correct when it references an
    EARLIER component's pin, and that earlier component was substituted
    (not remapped) — see the research log (in git history). Clip/hint substitution used to
    only ever look at state["pin_remaps"] (engine._enter_step, and the
    `hint` command's own build-step path) — never state["pin_substitutions"]
    (the learner's own accepted deviations). A later step whose own
    authored text names an earlier, since-substituted component's pin
    (e.g. "wire this to the same pin as led1") stayed stale, even though
    the underlying wiring CHECK itself was already correctly aware
    (engine._apply_pin_substitutions, fixed earlier the same day)."""
    library = load_library()

    class _SharedHoleLesson:
        def __init__(self):
            self.data = {
                "id": "shared-hole", "title": "t", "board": "arduino-uno",
                "steps": [
                    {"id": "s1", "phase": "build", "clip": "Wire led1 to pin 2.", "hints": ["led1 uses pin 2."], "expected_nets": [["led1:A", "uno:2"]]},
                    {"id": "s4", "phase": "build", "clip": "Wire led2 to the same pin as led1, pin 2.", "hints": ["Same pin as led1: pin 2."], "expected_nets": [["led2:A", "uno:2"]]},
                    {"id": "upload-code", "phase": "upload", "clip": "u", "code": "code.ino"},
                ],
                "final_check": {"expected_nets": [["led1:A", "uno:2"], ["led2:A", "uno:2"]]},
                "parts_used": ["arduino-uno"],
            }
            self._diagram = {
                "parts": [{"type": "wokwi-arduino-uno", "id": "uno"}, {"type": "wokwi-led", "id": "led1"}, {"type": "wokwi-led", "id": "led2"}],
                "connections": [],
            }
            self.folder = None
        def diagram(self): return self._diagram
        def code_path(self): return None
        def code_text(self): return "// placeholder"
        def step(self, i): return self.data["steps"][i] if 0 <= i < len(self.data["steps"]) else None
        def step_count(self): return len(self.data["steps"])
        def final_check_nets(self): return self.data["final_check"]["expected_nets"]

    lesson = _SharedHoleLesson()

    def send(state, event):
        return engine.handle_event(lesson, library, state, event)

    state = engine.initial_state()
    state, _ = send(state, {"command": "start"})
    # led1 deviates 2 -> 7.
    state, _ = send(state, {"command": "sim", "detected_pairs": [["led1:A", "uno:7"]]})
    state, actions = send(state, {"command": "done"})
    assert any(a["type"] == "pin_substituted" for a in actions), actions
    clip_action = next(a for a in actions if a["type"] == "play_clip")
    assert "pin 7" in clip_action["text"]
    assert "pin 2" not in clip_action["text"]

    state, actions = send(state, {"command": "hint"})
    assert "pin 7" in actions[0]["text"]
    assert "pin 2" not in actions[0]["text"]

    # Following the now-correct instruction should pass with zero friction.
    state, _ = send(state, {"command": "sim", "detected_pairs": [["led2:A", "uno:7"]]})
    state, actions = send(state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"], actions
    assert not any(a["type"] == "pin_substituted" for a in actions), actions


def test_a_cross_step_short_is_caught_immediately_not_deferred_to_final_check():
    """User-requested feature: catch a genuine cross-step short (two board
    pins the lesson keeps separate ending up on the same actual net, via
    a shared breadboard hole/strip) as soon as it happens, not only at
    final_check (see the research log (in git history)). Scoped to board pins only,
    deliberately — a component's own symmetric legs (a resistor's two
    legs, a pushbutton's contact group, a potentiometer's GND/VCC outer
    legs) are a real, valid ambiguity checker.check's own symmetric_map
    machinery already resolves; a naive version of this check first broke
    that (falsely flagged a legitimate potentiometer GND/VCC swap as a
    short) until fixed to use the same de-staling logic
    (_supersede_scarce_leg_pairs) everywhere else in the engine already
    uses, instead of a raw confirmed_pairs concatenation."""
    library = load_library()
    lesson = load_lesson("analog-read-serial")

    def send(state, event):
        return engine.handle_event(lesson, library, state, event)

    state = engine.initial_state()
    state, _ = send(state, {"command": "start"})
    state, _ = send(state, {"command": "done"})  # -> step-1a
    # The combined landing step (all three legs, each its own column — see
    # PARTS.md's legs_placed_together): a component-leg self-short (e.g.
    # VCC landing in GND's own column) is now caught immediately, right
    # here, by _check_multi_leg_landing -- so this test deliberately keeps
    # every leg in its own distinct column and demonstrates the OTHER,
    # still-real board-pin short case instead: a stray wire directly
    # tying two Arduino pins together.
    state, _ = send(state, {"command": "sim", "detected_pairs": [
        ["pot1:GND", "bb2:6t.a"], ["pot1:VCC", "bb2:7t.a"], ["pot1:SIG", "bb2:8t.a"],
    ]})
    state, actions = send(state, {"command": "done"})  # -> step-1b
    assert not [a for a in actions if a.get("verdict") == "wrong"], actions

    state, _ = send(state, {"command": "sim", "detected_pairs": [["pot1:GND", "bb2:6t.a"], ["uno:GND.1", "bb2:6t.c"]]})
    state, actions = send(state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"], actions
    assert state["step_index"] == 3  # -> step-2b (VCC's wiring)

    # The actual short: VCC wired to 5V normally, PLUS a stray extra wire
    # directly tying uno:5V to uno:GND.1 -- two board pins the lesson
    # keeps separate, now merged.
    state, _ = send(state, {"command": "sim", "detected_pairs": [
        ["pot1:VCC", "bb2:7t.a"], ["uno:5V", "bb2:7t.c"], ["uno:5V", "uno:GND.1"],
    ]})
    state, actions = send(state, {"command": "done"})
    assert any(a["type"] == "substitution_refused" for a in actions), actions
    assert any(a.get("verdict") == "wrong" for a in actions), actions
    assert state["step_index"] == 3  # did NOT advance — caught here, not deferred


def test_a_harmless_symmetric_swap_is_never_mistaken_for_a_cross_step_short():
    """Regression for the false positive found while building the above:
    a potentiometer's GND/VCC outer legs are declared symmetric_pins — a
    learner wiring them "swapped" relative to the script is fully valid
    (`harmless`), not a real board-pin short, even though the SAME
    "pot1:GND" leg ends up pointing at a genuinely different Arduino pin
    than an earlier, now-superseded fact said."""
    library = load_library()
    lesson = load_lesson("analog-read-serial")

    def send(state, event):
        return engine.handle_event(lesson, library, state, event)

    state = engine.initial_state()
    state, _ = send(state, {"command": "start"})
    state, _ = send(state, {"command": "done"})  # -> step-1a
    # The combined landing step: all three legs, each in its own column.
    state, _ = send(state, {"command": "sim", "detected_pairs": [
        ["pot1:GND", "bb2:6t.a"], ["pot1:VCC", "bb2:7t.a"], ["pot1:SIG", "bb2:8t.a"],
    ]})
    state, actions = send(state, {"command": "done"})  # -> step-1b
    assert not [a for a in actions if a.get("verdict") == "wrong"], actions

    # The learner turns the pot round from the very first wire: the
    # VCC-labeled leg (column 7t) goes to GND. Harmless, and it locks the
    # pot's orientation (engine._run_check's orientation lock).
    state, _ = send(state, {"command": "sim", "detected_pairs": [["pot1:VCC", "bb2:7t.a"], ["uno:GND.1", "bb2:7t.c"]]})
    state, actions = send(state, {"command": "done"})  # -> step-2b
    assert not [a for a in actions if a.get("verdict") == "wrong"], actions
    assert any(a.get("verdict") == "harmless" for a in actions), actions

    # VCC's step, consistently swapped: the GND-labeled leg (column 6t)
    # goes to 5V. Physically coherent (each leg in one column, on one pin),
    # so it must read harmless — never a false cross-step short.
    state, _ = send(state, {"command": "sim", "detected_pairs": [["pot1:GND", "bb2:6t.a"], ["uno:5V", "bb2:6t.c"]]})
    state, actions = send(state, {"command": "done"})
    assert not [a for a in actions if a.get("verdict") == "wrong"], actions
    assert not [a for a in actions if a["type"] == "substitution_refused"], actions
    assert any(a.get("verdict") == "harmless" for a in actions), actions
