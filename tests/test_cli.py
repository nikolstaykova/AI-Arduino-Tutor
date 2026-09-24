"""Unit tests for cli.py's parse() — specifically the `sim` command's two
input modes: a canned label, or real hole-level pairs (COMMANDS.md)."""
import sys

import pytest

import cli
from cli import parse
from core.library import load_library


@pytest.fixture(scope="module")
def library():
    return load_library()


def _run_cli_session(monkeypatch, tmp_path, inputs):
    """Drives cli.main() with scripted stdin and an isolated profile path,
    returning everything printed. Never touches the real project-root
    profile.json."""
    monkeypatch.setattr(cli, "load_profile", lambda: {})
    saved = {}
    monkeypatch.setattr(cli, "save_profile", lambda profile, path=None: saved.update(profile))
    remaining = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(remaining, "quit"))
    monkeypatch.setattr(sys, "argv", ["cli.py"])
    cli.main()
    return saved


def test_sim_with_canned_label():
    assert parse("sim correct") == {"command": "sim", "label": "correct"}
    assert parse("sim wrong") == {"command": "sim", "label": "wrong"}
    assert parse("sim swapped") == {"command": "sim", "label": "swapped"}


def test_sim_with_no_argument():
    assert parse("sim") == {"command": "sim", "label": None}


def test_sim_with_one_hole_pair():
    assert parse("sim pot1:GND-bb2:6b.a") == {
        "command": "sim",
        "detected_pairs": [["pot1:GND", "bb2:6b.a"]],
    }


def test_sim_with_several_hole_pairs():
    line = "sim pot1:GND-bb2:6b.a uno:GND.3-bb2:6b.c pot1:VCC-bb2:7b.a"
    assert parse(line) == {
        "command": "sim",
        "detected_pairs": [
            ["pot1:GND", "bb2:6b.a"],
            ["uno:GND.3", "bb2:6b.c"],
            ["pot1:VCC", "bb2:7b.a"],
        ],
    }


def test_sim_with_a_malformed_token_is_left_for_the_engine_to_reject():
    """A token with no '-' can't be split into a pin pair — passed through
    as a plain string rather than guessed at, so the engine's own
    detected_pairs validation reports it cleanly (see test_engine.py's
    malformed-detected-pairs coverage)."""
    result = parse("sim pot1:GND-bb2:6b.a nodash")
    assert result["command"] == "sim"
    assert isinstance(result["detected_pairs"], str)


def test_other_commands_unaffected():
    assert parse("done") == {"command": "done"}
    assert parse("help potentiometer") == {"command": "help", "item": "potentiometer"}


def test_sim_resolves_a_friendly_component_name(library):
    """User feedback: 'r1:2' is too cryptic to type — a part's own
    subtype/alias word (from its library card) should resolve to the
    real diagram id too, not just the raw id itself."""
    from core.lesson import load_lesson

    lesson = load_lesson("blink")
    name_map = cli.component_name_map(lesson, library)
    assert parse("sim resistor:1-breadboard:3b", name_map) == {
        "command": "sim",
        "detected_pairs": [["r1:1", "bb1:3b"]],
    }
    # case-insensitive, and a raw id still works unresolved either way
    assert parse("sim RESISTOR:1-bb1:3b", name_map) == {
        "command": "sim",
        "detected_pairs": [["r1:1", "bb1:3b"]],
    }
    assert parse("sim r1:1-bb1:3b", name_map) == {
        "command": "sim",
        "detected_pairs": [["r1:1", "bb1:3b"]],
    }


def test_sim_without_a_name_map_falls_back_to_literal_ids():
    """No name_map given (e.g. any existing caller that hasn't been
    updated) behaves exactly as before — no resolution attempted."""
    assert parse("sim resistor:1-bb1:3b") == {
        "command": "sim",
        "detected_pairs": [["resistor:1", "bb1:3b"]],
    }


def test_component_name_map_drops_a_name_ambiguous_in_this_diagram(tmp_path, library):
    """Two resistors in the same diagram both answer to 'resistor' — that
    name must NOT resolve to either one silently (that could wire the
    wrong part); it's left out of the map entirely, so it just passes
    through unresolved and the engine reports an honest unknown-id error
    rather than guessing."""
    from core.lesson import Lesson

    (tmp_path / "diagram.json").write_text(
        '{"parts": ['
        '{"type": "wokwi-arduino-uno", "id": "uno"}, '
        '{"type": "wokwi-resistor", "id": "r1", "attrs": {"value": "1000"}}, '
        '{"type": "wokwi-resistor", "id": "r2", "attrs": {"value": "1000"}}'
        '], "connections": []}'
    )
    (tmp_path / "code.ino").write_text("void setup(){}\nvoid loop(){}\n")
    data = {"id": "two-resistors", "title": "t", "code": "code.ino", "wokwi_diagram": "diagram.json", "steps": []}
    lesson = Lesson(data, tmp_path)

    name_map = cli.component_name_map(lesson, library)
    assert "resistor" not in name_map
    assert name_map["r1"] == "r1"
    assert name_map["r2"] == "r2"


def test_board_command_carries_its_variant():
    """Regression test: parse() never captured board's argument at all —
    `board mini` silently became {"command": "board"} with no variant,
    so the engine always rejected it as 'Unknown breadboard variant
    None'. Found while testing the profile feature's auto-apply path."""
    assert parse("board mini") == {"command": "board", "variant": "mini"}
    assert parse("board") == {"command": "board", "variant": None}


def test_difficulty_command_carries_its_level():
    assert parse("difficulty advanced") == {"command": "difficulty", "level": "advanced"}
    assert parse("difficulty") == {"command": "difficulty", "level": None}


def test_arduino_command_carries_its_board():
    assert parse("arduino mega") == {"command": "arduino", "board": "mega"}
    assert parse("arduino Arduino Mega") == {"command": "arduino", "board": "Arduino Mega"}
    assert parse("arduino") == {"command": "arduino", "board": None}


def test_arduino_command_invites_a_correction_at_the_start_of_a_session(monkeypatch, tmp_path, capsys):
    """Same "assumed, not asked, but invited to correct" shape as the
    breadboard message — printed once, up front, before `start`."""
    _run_cli_session(monkeypatch, tmp_path, ["Nikol", "start", "quit"])
    out = capsys.readouterr().out
    assert "authored for the Arduino Uno" in out
    assert "arduino mega" in out or "`arduino mega`" in out


def test_arduino_command_translates_the_lesson_before_start(monkeypatch, tmp_path, capsys):
    _run_cli_session(monkeypatch, tmp_path, ["Nikol", "arduino mega", "start", "quit"])
    out = capsys.readouterr().out
    assert "translated this lesson for the Arduino Mega" in out
    assert "an Arduino Mega" in out  # the gather clip now names the new board


def test_arduino_command_with_an_unrecognized_board_keeps_the_lesson_as_authored(monkeypatch, tmp_path, capsys):
    _run_cli_session(monkeypatch, tmp_path, ["Nikol", "arduino raspberry pi", "start", "quit"])
    out = capsys.readouterr().out
    assert "isn't a board this project knows" in out
    assert "an Arduino Uno" in out  # unchanged — original lesson still active


def test_arduino_command_refused_once_the_lesson_has_started(monkeypatch, tmp_path, capsys):
    """Explicit limitation, not silently handled: translating a lesson
    mid-session would leave state["confirmed_pairs"] referencing the old
    board's literal pins with no defined reinterpretation."""
    _run_cli_session(monkeypatch, tmp_path, ["Nikol", "start", "arduino mega", "quit"])
    out = capsys.readouterr().out
    assert "already started" in out
    assert "translated this lesson" not in out


def test_arduino_command_can_switch_boards_more_than_once_before_start(monkeypatch, tmp_path, capsys):
    """Chained corrections (learner changes their mind, or is walked
    through several boards) must stay harmless — each `arduino` call
    translates from whatever board is CURRENTLY active, not always from
    the lesson's original author board."""
    _run_cli_session(monkeypatch, tmp_path, ["Nikol", "arduino mega", "arduino nano", "arduino uno", "start", "quit"])
    out = capsys.readouterr().out
    assert out.count("🔁") == 3
    assert "translated this lesson for the Arduino Mega" in out
    assert "translated this lesson for the Arduino Nano" in out
    assert "translated this lesson for the Arduino Uno" in out
    assert "an Arduino Uno" in out  # ended back on the original board


def test_start_assumes_the_default_board_and_invites_a_correction(monkeypatch, tmp_path, capsys):
    """User request: the breadboard should be an assumed-then-correctable
    input for each lesson, asked right at gather — not silently left
    unset unless the learner remembers the `board` command on their own."""
    _run_cli_session(monkeypatch, tmp_path, ["Nikol", "start", "quit"])
    out = capsys.readouterr().out
    assert f"assume a '{cli.DEFAULT_BREADBOARD_ASSUMPTION}'-size breadboard" in out
    assert "board mini" in out or "`board mini`" in out  # tells them how to correct it


def test_default_board_assumption_never_saved_to_the_profile(monkeypatch, tmp_path):
    """The assumption is a starting guess for THIS session, not a
    remembered learner fact — must never be written to profile.json,
    consistent with `board` never being persisted at all."""
    saved = _run_cli_session(monkeypatch, tmp_path, ["Nikol", "start", "quit"])
    assert "breadboard_variant" not in saved


def test_play_video_file_launches_the_system_player_for_a_real_file(monkeypatch, capsys):
    """Doesn't actually spawn a player during tests — monkeypatches
    subprocess.Popen to just record the call — but confirms the real
    wire_stripper.mp4 file resolves and the right platform-specific
    command gets built."""
    calls = []
    monkeypatch.setattr(cli.subprocess, "Popen", lambda cmd: calls.append(cmd))
    cli.play_video_file("wire_stripper.mp4")
    assert calls, "expected a player to be launched for a file that exists"


def test_play_video_file_missing_file_does_not_crash(capsys):
    cli.play_video_file("nonexistent-video.mp4")
    out = capsys.readouterr().out
    assert "not found" in out


def test_play_video_file_url_is_not_auto_launched(monkeypatch, capsys):
    """A tutorial_clip could be a URL (see PLAN.md's video-sourcing
    notes) — never silently shell out to open an arbitrary URL, just
    print it for the learner to open themselves."""
    calls = []
    monkeypatch.setattr(cli.subprocess, "Popen", lambda cmd: calls.append(cmd))
    cli.play_video_file("https://example.com/some-video")
    out = capsys.readouterr().out
    assert "example.com" in out
    assert not calls


def test_correcting_the_board_changes_the_plausibility_warning(monkeypatch, tmp_path, capsys):
    """The exact scenario the user described: column 20 is fine on the
    assumed 'full' board (no warning), but the SAME column correctly
    warns once corrected to 'mini'."""
    _run_cli_session(monkeypatch, tmp_path, [
        "Nikol", "start", "done", "sim pot1:GND-bb2:20t.a", "done", "quit",
    ])
    out_full = capsys.readouterr().out
    assert "worth double-checking" not in out_full

    _run_cli_session(monkeypatch, tmp_path, [
        "Nikol", "start", "board mini", "done", "sim pot1:GND-bb2:20t.a", "done", "quit",
    ])
    out_mini = capsys.readouterr().out
    assert "worth double-checking" in out_mini
    assert "column 20" in out_mini.lower()
