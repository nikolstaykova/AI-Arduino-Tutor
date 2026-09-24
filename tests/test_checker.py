from core import checker


def test_pass_exact_match():
    expected = [["pot1:SIG", "uno:A0"]]
    detected = [["pot1:SIG", "uno:A0"]]
    assert checker.check(expected, detected) == {"verdict": "pass", "missing": []}


def test_wrong_when_nothing_detected():
    expected = [["pot1:SIG", "uno:A0"]]
    result = checker.check(expected, [])
    assert result["verdict"] == "wrong"
    assert result["missing"] == [["pot1:SIG", "uno:A0"]]


def test_strip_agnostic_via_shared_component_pins():
    """Two different physical strips realizing the same component-pin net
    must compare equal — the checker never sees strip identity at all,
    since expected/detected are already expressed as component-pin pairs
    (PLAN.md Phase 5's strip-agnostic reduction happens upstream)."""
    expected = [["led1:A", "uno:13"]]
    # detected via a totally different (but still correct) breadboard strip —
    # doesn't matter, the checker only ever sees the component-pin pair.
    detected = [["led1:A", "uno:13"]]
    assert checker.check(expected, detected)["verdict"] == "pass"


def test_symmetric_pin_swap_is_harmless_not_wrong_and_not_silent_pass():
    expected = [["pot1:GND", "uno:GND.1"], ["pot1:VCC", "uno:5V"]]
    swapped = [["pot1:VCC", "uno:GND.1"], ["pot1:GND", "uno:5V"]]
    sym_map = {"pot1": [["GND", "VCC"]]}

    result = checker.check(expected, swapped, sym_map)
    assert result["verdict"] == "harmless"

    # without the symmetric_map, the same swapped input must be wrong —
    # proves the harmless verdict really is conditional on the part
    # declaring that pair symmetric, not a blanket leniency.
    result_no_map = checker.check(expected, swapped)
    assert result_no_map["verdict"] == "wrong"


def test_led_polarity_is_not_symmetric_and_a_reversed_led_is_wrong():
    expected = [["led1:A", "bb1:18t"], ["led1:C", "bb1:18b"]]
    reversed_led = [["led1:C", "bb1:18t"], ["led1:A", "bb1:18b"]]
    result = checker.check(expected, reversed_led)  # no symmetric_map for led1
    assert result["verdict"] == "wrong"


def test_synthesize_detected_correct_matches_expected_exactly():
    expected = [["pot1:SIG", "uno:A0"]]
    assert checker.synthesize_detected("correct", expected) == expected


def test_synthesize_detected_wrong_is_empty():
    assert checker.synthesize_detected("wrong", [["a:1", "b:2"]]) == []


def test_synthesize_detected_swapped_uses_symmetric_map():
    expected = [["pot1:GND", "uno:GND.1"]]
    sym_map = {"pot1": [["GND", "VCC"]]}
    swapped = checker.synthesize_detected("swapped", expected, sym_map)
    assert swapped == [["pot1:VCC", "uno:GND.1"]]


def test_board_pin_alias_any_gnd_pin_is_the_same_net():
    """Regression test: expected_nets hand-authored against uno:GND.1 must
    still pass when a learner (correctly) used uno:GND.3 instead — any GND
    pin on the Uno is the same net by hardware design, which is literally
    what lesson content already tells the learner ('Any GND pin on the
    Arduino works')."""
    expected = [["pot1:GND", "uno:GND.1"]]
    detected = [["pot1:GND", "uno:GND.3"]]
    alias_map = checker.board_alias_map([{"type": "wokwi-arduino-uno", "id": "uno"}])

    assert checker.check(expected, detected)["verdict"] == "wrong"  # without the fix
    assert checker.check(expected, detected, alias_map=alias_map)["verdict"] == "pass"


def test_board_alias_map_built_from_real_diagram_parts():
    parts = [
        {"type": "wokwi-arduino-uno", "id": "uno", "attrs": {}},
        {"type": "wokwi-potentiometer", "id": "pot1", "attrs": {}},
    ]
    alias_map = checker.board_alias_map(parts)
    assert alias_map == {"uno": {"mode": "prefix", "prefixes": ["GND", "A4", "A5"]}}


def test_a4_a5_secondary_i2c_header_folds_to_the_plain_analog_pin():
    """Real bug, found via two independent real diagrams both wiring an
    I2C device's SDA/SCL to 'A4.2'/'A5.2' rather than plain 'A4'/'A5' --
    the Uno's real secondary I2C breakout header near AREF, the same
    electrical nodes as A4/A5 (same shape as GND.1/GND.2/GND.3, just
    undocumented on docs.wokwi.com/parts/wokwi-arduino-uno's basic pin
    table). Counter-evidence ruled out ".N" being a per-wire connection
    counter: a real diagram wired three separate connections all to the
    literal same 'GND.1', no increment at all. A lesson scripted for
    plain A4/A5 must recognize a diagram's or learner's '.2' variant as
    the identical net, not a real deviation."""
    alias_map = checker.board_alias_map([{"type": "wokwi-arduino-uno", "id": "uno"}])
    expected = [["lcd1:SDA", "uno:A4"], ["lcd1:SCL", "uno:A5"]]
    detected = [["lcd1:SDA", "uno:A4.2"], ["lcd1:SCL", "uno:A5.2"]]
    result = checker.check(expected, detected, {}, alias_map, set())
    assert result["verdict"] == "pass"

    # A0-A3 must NOT be swept up by the same prefix fold -- only A4/A5
    # (and GND) have a real, verified second physical location.
    assert checker._canonicalize_pin("uno:A0", alias_map) == "uno:A0"
    assert checker._canonicalize_pin("uno:A3", alias_map) == "uno:A3"


def test_mega_gnd_and_5v_pins_fold_together_same_as_the_unos():
    """Real gap found via a real Mega diagram: the Mega has FIVE ground
    pins and a secondary 5V header (verified: docs.wokwi.com/parts/
    wokwi-arduino-mega — "GND.1 (next to pin 13), GND.2/GND.3 (next to
    Vin), and GND.4/GND.5 (at the bottom of the header)"; "two
    additional power supply pins, 5V.1/5V.2, at the top of the dual-row
    header"), the same "N physical legs, one net" shape as the Uno's
    three GND pins -- but BOARD_PIN_ALIAS_RULES had no entry for the
    Mega at all, so none of them folded together."""
    alias_map = checker.board_alias_map([{"type": "wokwi-arduino-mega", "id": "mega"}])
    assert alias_map == {"mega": {"mode": "prefix", "prefixes": ["GND", "5V"]}}

    expected = [["led1:C", "mega:GND.1"]]
    detected = [["led1:C", "mega:GND.4"]]
    assert checker.check(expected, detected, {}, alias_map, set())["verdict"] == "pass"

    expected = [["sensor1:VCC", "mega:5V"]]
    detected = [["sensor1:VCC", "mega:5V.2"]]
    assert checker.check(expected, detected, {}, alias_map, set())["verdict"] == "pass"


def test_nano_gnd_pins_fold_together():
    """Real gap found via a real Nano diagram: the user-pasted
    docs.wokwi.com/parts/wokwi-arduino-nano pinout lists 'GND' twice
    (once near D13/RST, once near VIN/RESET), the same "N physical legs,
    one net" shape as the Uno/Mega -- confirmed directly by the diagram
    itself, which wires two different components to GND.1 and GND.2."""
    alias_map = checker.board_alias_map([{"type": "wokwi-arduino-nano", "id": "nano"}])
    assert alias_map == {"nano": {"mode": "prefix", "prefixes": ["GND"]}}
    expected = [["btn1:2", "nano:GND.1"]]
    detected = [["btn1:2", "nano:GND.2"]]
    assert checker.check(expected, detected, {}, alias_map, set())["verdict"] == "pass"


def test_breadboard_hole_folds_to_its_strip_regardless_of_row_letter():
    """Two different physical holes on the same strip (same column, same
    side of the center gap) must compare as the same net — the row letter
    (a/c/e/f/h/...) only picks which of the five identical holes, it's
    never meaningful on its own."""
    alias_map = checker.board_alias_map([{"type": "wokwi-breadboard-mini", "id": "bb2"}])
    expected = [["pot1:GND", "bb2:6b.f"]]
    detected = [["pot1:GND", "bb2:6b.h"]]  # different hole, same strip
    assert checker.check(expected, detected, alias_map=alias_map)["verdict"] == "pass"


def test_different_row_on_the_breadboard_actually_breaks_the_connection():
    """The strip-agnostic reduction must not become blanket leniency: any
    hole within the same column-half strip (6b.f … 6b.j) is genuinely the
    same electrical point (pass), but a different column entirely is a
    genuinely different, disconnected strip — the connection never actually formed, and that
    must be caught as wrong, not waved through."""
    expected = [["pot1:GND", "uno:GND.1"]]
    alias_map = checker.board_alias_map([
        {"type": "wokwi-arduino-uno", "id": "uno"},
        {"type": "wokwi-breadboard-mini", "id": "bb2"},
    ])
    connector_component_ids = checker.connector_ids([{"type": "wokwi-breadboard-mini", "id": "bb2"}])

    same_row = [["pot1:GND", "bb2:4t.a"], ["uno:GND.3", "bb2:4t.c"]]
    result = checker.check(expected, same_row, alias_map=alias_map, connector_component_ids=connector_component_ids)
    assert result["verdict"] == "pass"

    different_row = [["pot1:GND", "bb2:5t.a"], ["uno:GND.3", "bb2:4t.c"]]
    result = checker.check(expected, different_row, alias_map=alias_map, connector_component_ids=connector_component_ids)
    assert result["verdict"] == "wrong"
    assert result["missing"] == [["pot1:GND", "uno:GND"]]


def test_breadboard_routed_detection_passes_not_wrong():
    """Regression test for a real bug: union-find correctly merges
    {pot1:GND, bb2:6b, uno:GND} into one net when the connection is routed
    through a breadboard strip, but comparing that 3-member net directly
    against the 2-member expected {pot1:GND, uno:GND} always failed, since
    frozensets of different sizes are never equal. Every breadboard-routed
    connection looked 'wrong' even when exactly right, until check() also
    dropped the connector-only pins from both sides before comparing."""
    expected = [["pot1:GND", "uno:GND.1"]]
    detected = [["pot1:GND", "bb2:6b.f"], ["uno:GND.3", "bb2:6b.h"]]
    alias_map = checker.board_alias_map([
        {"type": "wokwi-arduino-uno", "id": "uno"},
        {"type": "wokwi-breadboard-mini", "id": "bb2"},
    ])
    connector_component_ids = checker.connector_ids([{"type": "wokwi-breadboard-mini", "id": "bb2"}])

    result = checker.check(expected, detected, alias_map=alias_map)
    assert result["verdict"] == "wrong", "sanity check: without connector filtering, this must still fail"

    result = checker.check(expected, detected, alias_map=alias_map, connector_component_ids=connector_component_ids)
    assert result["verdict"] == "pass"


def test_derive_expected_nets_matches_the_real_analog_read_serial_diagram():
    """End-to-end validation against the actual authored lesson data, not
    a synthetic example: auto-deriving expected_nets from the real
    diagram.json (breadboard hop through bb2 and all) must describe the
    exact same net groupings as what was hand-written in lesson.json."""
    import json
    from pathlib import Path

    lesson_dir = Path(__file__).resolve().parent.parent / "lessons" / "analog-read-serial"
    diagram = json.loads((lesson_dir / "diagram.json").read_text())
    lesson_data = json.loads((lesson_dir / "lesson.json").read_text())

    derived = checker.derive_expected_nets(diagram)
    alias_map = checker.board_alias_map(diagram["parts"])

    derived_nets = set(checker.build_nets(derived, alias_map))
    handwritten_nets = set(checker.build_nets(lesson_data["final_check"]["expected_nets"], alias_map))
    assert derived_nets == handwritten_nets


def test_wrong_missing_reports_only_the_genuine_mistake_not_unrelated_harmless_swaps():
    """Regression test: with several independently-symmetric components,
    a real mistake on ONE of them must not make an already-fine harmless
    swap on a DIFFERENT one show up in `missing` too. Before the fix,
    `check()` always fell back to the plain unswapped comparison for its
    `missing` report once no single variant fully matched, which listed
    every swapped component as if it were also broken."""
    expected = [
        ["btn_a:1.r", "uno:5"], ["btn_a:2.r", "uno:GND.1"],
        ["btn_b:1.r", "uno:6"], ["btn_b:2.r", "uno:GND.1"],
        ["btn_c:1.r", "uno:7"], ["btn_c:2.r", "uno:GND.1"],
    ]
    sym_map = {
        "btn_a": [["1.r", "2.r"]],
        "btn_b": [["1.r", "2.r"]],
        "btn_c": [["1.r", "2.r"]],
    }
    detected = [
        # btn_a: legs swapped -- harmless on its own
        ["btn_a:2.r", "uno:5"], ["btn_a:1.r", "uno:GND.1"],
        # btn_b: legs swapped too -- also harmless on its own
        ["btn_b:2.r", "uno:6"], ["btn_b:1.r", "uno:GND.1"],
        # btn_c: wired to the wrong pin entirely -- a real mistake
        ["btn_c:1.r", "uno:3"], ["btn_c:2.r", "uno:GND.1"],
    ]
    result = checker.check(expected, detected, sym_map)
    assert result["verdict"] == "wrong"
    assert result["missing"] == [["btn_c:1.r", "uno:7"]]


def test_check_reports_conflict_when_a_leg_ended_up_tied_to_the_wrong_thing():
    """A hole/pin can only hold one wire — if the detected data ties
    pot1:GND to something other than uno:GND (e.g. accidentally sharing a
    hole with a different component), 'wrong' should say what it's
    actually tied to, not just that the expected net is missing."""
    expected = [["pot1:GND", "uno:GND.1"]]
    # pot1:GND ended up on the same strip as led1:C instead of uno:GND
    detected = [["pot1:GND", "bb2:6t.a"], ["led1:C", "bb2:6t.c"]]
    connector_ids = {"bb2"}
    alias_map = checker.board_alias_map([{"type": "wokwi-breadboard-mini", "id": "bb2"}])
    result = checker.check(expected, detected, alias_map=alias_map, connector_component_ids=connector_ids)
    assert result["verdict"] == "wrong"
    assert result["conflicts"] == {"pot1:GND": ["led1:C", "pot1:GND"]}


def test_check_reports_no_conflict_when_simply_not_connected_yet():
    expected = [["pot1:GND", "uno:GND.1"]]
    result = checker.check(expected, [])
    assert result["verdict"] == "wrong"
    assert result["conflicts"] == {}


def test_check_landed_passes_once_the_pin_touches_any_hole_on_the_board():
    """The landing half of a wiring step (PLAN.md Phase 5) doesn't care
    which hole, or what the far end eventually becomes — only that the leg
    is actually plugged into the breadboard at all."""
    connector_ids = {"bb2"}
    detected = [["pot1:GND", "bb2:6b.a"]]
    assert checker.check_landed("pot1:GND", detected, connector_ids) == {"verdict": "pass", "missing": []}


def test_check_landed_wrong_when_never_plugged_in():
    """Never plugged in at all is not a conflict — nothing to report."""
    connector_ids = {"bb2"}
    result = checker.check_landed("pot1:GND", [], connector_ids)
    assert result["verdict"] == "wrong"
    assert result["missing"] == ["pot1:GND"]
    assert result["conflicts"] == {}


def test_check_landed_wrong_when_wired_directly_to_arduino_not_the_board():
    """Touching *something*, but not a connector-only component, is not a
    landing — a direct pin-to-pin wire isn't 'plugged into the breadboard'."""
    connector_ids = {"bb2"}
    detected = [["pot1:GND", "uno:GND.1"]]
    assert checker.check_landed("pot1:GND", detected, connector_ids)["verdict"] == "wrong"


def test_check_landed_harmless_when_the_symmetric_pin_landed_instead():
    connector_ids = {"bb2"}
    sym_pairs = [["GND", "VCC"]]
    detected = [["pot1:VCC", "bb2:6b.a"]]  # learner plugged in the interchangeable leg
    result = checker.check_landed("pot1:GND", detected, connector_ids, sym_pairs)
    assert result["verdict"] == "harmless"

    # without the declared symmetric pair, the same input is just wrong
    result_no_sym = checker.check_landed("pot1:GND", detected, connector_ids)
    assert result_no_sym["verdict"] == "wrong"


def test_check_landed_reports_conflict_when_wired_to_something_else():
    connector_ids = {"bb2"}
    detected = [["pot1:GND", "uno:A0"]]  # wired, but not to the board
    result = checker.check_landed("pot1:GND", detected, connector_ids)
    assert result["verdict"] == "wrong"
    assert result["conflicts"] == {"pot1:GND": "uno:A0"}


def test_synthesize_landed_correct_lands_on_a_connector_hole():
    pairs = checker.synthesize_landed("correct", "pot1:GND", {"bb2"})
    assert len(pairs) == 1
    assert pairs[0][0] == "pot1:GND"
    assert pairs[0][1].startswith("bb2:")


def test_synthesize_landed_wrong_is_empty():
    assert checker.synthesize_landed("wrong", "pot1:GND", {"bb2"}) == []


def test_synthesize_landed_swapped_uses_symmetric_pin():
    pairs = checker.synthesize_landed("swapped", "pot1:GND", {"bb2"}, [["GND", "VCC"]])
    assert pairs[0][0] == "pot1:VCC"


def test_check_landed_respects_a_components_own_pin_alias_rule():
    """Regression test: check_landed originally had no alias_map at all —
    only symmetric_pairs — so a component with its OWN board-pin-alias
    rule (like the pushbutton's 1/2 contact groups) was wrongly rejected
    when a learner used the other, equally-valid aliased leg than the one
    named in the landing step. Found starting the DigitalReadSerial lesson."""
    connector_ids = {"bb1"}
    alias_map = checker.board_alias_map([{"type": "wokwi-pushbutton", "id": "btn1"}])
    detected = [["btn1:2.l", "bb1:4b.a"]]  # lesson names 2.r, learner used 2.l
    result = checker.check_landed("btn1:2.r", detected, connector_ids, alias_map=alias_map)
    assert result == {"verdict": "pass", "missing": []}


def test_pushbutton_same_contact_group_legs_fold_to_one_net_silently():
    """Verified against docs.wokwi.com/parts/wokwi-pushbutton: 1.l and 1.r
    are permanently connected to each other (one contact group), and
    separately 2.l/2.r are permanently connected (the other group) —
    always, not just when pressed. Using the other leg of the SAME group
    than the script expected must be a silent pass, not harmless — it's
    not a wiring choice or deviation, it's literally the same node."""
    alias_map = checker.board_alias_map([{"type": "wokwi-pushbutton", "id": "btn1"}])
    expected = [["btn1:1.r", "uno:2"]]
    detected = [["btn1:1.l", "uno:2"]]  # other leg of the SAME contact group
    result = checker.check(expected, detected, alias_map=alias_map)
    assert result == {"verdict": "pass", "missing": []}


def test_pushbutton_different_contact_groups_are_not_the_same_net():
    """1.l/1.r (group 1) and 2.l/2.r (group 2) are genuinely different
    nodes — only bridged when the button is physically pressed, which
    this checker never models (it verifies wiring, not button state)."""
    alias_map = checker.board_alias_map([{"type": "wokwi-pushbutton", "id": "btn1"}])
    expected = [["btn1:1.r", "uno:2"]]
    detected = [["btn1:2.r", "uno:2"]]  # wrong contact group entirely
    result = checker.check(expected, detected, alias_map=alias_map)
    assert result["verdict"] == "wrong"


def test_derive_expected_nets_drops_the_breadboard_itself_from_the_result():
    diagram = {
        "parts": [
            {"type": "wokwi-arduino-uno", "id": "uno"},
            {"type": "wokwi-breadboard-mini", "id": "bb2"},
            {"type": "wokwi-potentiometer", "id": "pot1"},
        ],
        "connections": [
            ["pot1:SIG", "bb2:7t.e", "gray", []],
            ["uno:A0", "bb2:7t.e", "gold", []],
        ],
    }
    derived = checker.derive_expected_nets(diagram)
    assert derived == [["pot1:SIG", "uno:A0"]]
    for pair in derived:
        assert not any(pin.startswith("bb2:") for pin in pair)
