#!/usr/bin/env python3
"""Terminal CLI for testing a lesson end-to-end (PLAN.md Phase 1).

Usage:
    python3 cli.py [lesson_id]        # defaults to analog-read-serial

Commands (exact-match only for now — see COMMANDS.md for what each means
and the natural-language equivalents planned for later):
    start
    done
    previous
    repeat
    hint
    help <item>        # text explanation only
    video <item>       # the item's tutorial_clip, if it has one
    sim <label>        # correct | wrong | swapped
    sim <pin>-<pin> <pin>-<pin> ...   # real hole-level pairs — the actual
                                      # checker determines the verdict.
                                      # The component side of a pin (before
                                      # the ":") also accepts a friendly
                                      # name in place of the raw diagram id
                                      # when it's unambiguous in this
                                      # lesson's diagram — e.g. "resistor"
                                      # or "breadboard" instead of "r1"/
                                      # "bb1" (see component_name_map).
    tools
    quit
"""
import subprocess
import sys
from pathlib import Path

from core import board_translate, engine, eventlog
from core.library import load_library
from core.lesson import load_lesson
from core.profile import load_profile, save_profile

#: Starting assumption for `board`, used only until the learner corrects
#: it (see main()) — the largest variant, so an un-answered board question
#: produces the fewest false "column doesn't fit" warnings (a smaller
#: board wrongly assumed would warn about columns that are actually fine
#: on the learner's real, larger one).
DEFAULT_BREADBOARD_ASSUMPTION = "full"

#: Where a tool's tutorial_clip video actually lives on disk, if it's a
#: local file (see PLAN.md's video-sourcing notes — a `tutorial_clip`
#: value can also be a URL, which this doesn't try to auto-play).
TOOLS_MEDIA_DIR = Path(__file__).resolve().parent / "library" / "tools" / "media"


def play_video_file(ref):
    """Best-effort: actually launch the system's default video player for
    a local tutorial_clip file. Never raises — a missing file or an
    unsupported platform just prints what to do manually instead of
    crashing the CLI session over a video."""
    if ref.startswith("http://") or ref.startswith("https://"):
        print(f"      (hosted externally — open manually: {ref})")
        return
    path = TOOLS_MEDIA_DIR / ref
    if not path.exists():
        print(f"      (video file not found on disk: {path})")
        return
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(path)])
        elif sys.platform == "win32":
            subprocess.Popen(["cmd", "/c", "start", "", str(path)])
        else:
            print(f"      (don't know how to auto-play on this platform — open manually: {path})")
    except OSError as e:
        print(f"      (couldn't launch a video player: {e} — open manually: {path})")


def component_name_map(lesson, library):
    """Friendly-name -> real diagram component id, for the `sim` command
    (user request: the raw diagram id, e.g. 'r1', is cryptic to type —
    a part's own subtype/alias/id word should work too, e.g.
    'resistor'). Built fresh per lesson's diagram, since which ids exist
    (and whether a name is ambiguous) depends on what's actually in it.
    A name that would refer to more than one part in THIS diagram (e.g.
    two resistors) is left out entirely — ambiguous names must still use
    the real id, same as today."""
    name_to_ids = {}

    def add(name, pid):
        if name:
            name_to_ids.setdefault(name.lower(), set()).add(pid)

    for part in lesson.diagram().get("parts", []):
        pid = part.get("id")
        add(pid, pid)
        value = part.get("attrs", {}).get("value")
        for card in library.find_by_wokwi_type(part.get("type"), value):
            add(card.get("id"), pid)
            add(card.get("subtype"), pid)
            for alias in card.get("aliases", []):
                add(alias, pid)
    return {name: next(iter(ids)) for name, ids in name_to_ids.items() if len(ids) == 1}


def _resolve_component_name(pin, name_map):
    if not name_map or ":" not in pin:
        return pin
    comp, leg = pin.split(":", 1)
    resolved = name_map.get(comp.lower())
    return f"{resolved}:{leg}" if resolved else pin


def parse(line, name_map=None):
    parts = line.strip().split(maxsplit=1)
    if not parts:
        return None
    command = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else None
    if command == "help":
        return {"command": "help", "item": rest}
    if command == "video":
        return {"command": "video", "item": rest}
    if command == "board":
        return {"command": "board", "variant": rest}
    if command == "arduino":
        return {"command": "arduino", "board": rest}
    if command == "difficulty":
        return {"command": "difficulty", "level": rest}
    if command == "sim":
        if rest in (None, "correct", "wrong", "swapped"):
            return {"command": "sim", "label": rest}
        # Anything else is real hole-level pairs, space-separated,
        # each written as pinA-pinB (e.g. pot1:GND-bb2:6b.a). Left
        # malformed on purpose if a token has no "-" — the engine's own
        # validation reports it cleanly rather than this parser guessing.
        # The component side of each pin (before the ":") also accepts a
        # friendly name in place of the raw diagram id — e.g.
        # "resistor:2-breadboard:6b" instead of "r1:2-bb1:6b" — resolved
        # via component_name_map; a name not in that map (or none given)
        # passes through unchanged, so a raw id always still works too.
        pairs = []
        for token in rest.split():
            if "-" not in token:
                return {"command": "sim", "detected_pairs": rest}
            a, b = token.split("-", 1)
            pairs.append([_resolve_component_name(a, name_map), _resolve_component_name(b, name_map)])
        return {"command": "sim", "detected_pairs": pairs}
    return {"command": command}


def render(actions):
    for action in actions:
        kind = action["type"]
        if kind == "play_clip":
            print(f"  🎙  [{action['step']}] {action['text']}")
        elif kind == "play_video":
            print(f"  🎬  playing video: {action['ref']}")
            play_video_file(action["ref"])
        elif kind == "show_card":
            card = action["card"]
            if not action.get("in_scope", True):
                print(f"  ℹ️   you don't actually need the {card['display_name']} for this lesson — here it is anyway:")
            print(f"  📇  {card['display_name']} — {card['description']}")
            print(f"      how to use: {card['how_to_use']}")
        elif kind == "list_items":
            print(f"  📦  you'll need: {', '.join(action['items'])}")
        elif kind == "list_ids":
            label = "tools" if action.get("kind") == "tools" else "parts"
            icon = "🧰" if label == "tools" else "📦"
            if action["ids"]:
                print(f"  {icon}  {label} for this lesson: {', '.join(action['ids'])}")
            else:
                print(f"  {icon}  {action.get('message', f'No {label} needed.')}")
        elif kind == "hint":
            print(f"  💡  {action['text']}")
        elif kind == "sim_set":
            if "pairs" in action:
                print(f"  🧪  mock detection set to {len(action['pairs'])} literal hole pair(s)")
            else:
                print(f"  🧪  mock detection set to: {action['label']}")
        elif kind == "board_set":
            print(f"  🍞  breadboard set to: {action['variant']}")
        elif kind == "difficulty_set":
            print(f"  🎚️   difficulty set to: {action['level']}")
        elif kind == "plausibility_warning":
            print(f"  🤔  {action['message']}")
        elif kind == "breadboard_bypassed":
            print(f"  🔀  {action['message']}")
        elif kind == "pin_substituted":
            print(f"  🔁  {action['message']}")
        elif kind == "substitution_refused":
            print(f"  💡  {action['message']}")
        elif kind == "show_code":
            print("  💻  code to upload:")
            for line in action["code"].splitlines():
                print(f"      {line}")
        elif kind == "feedback":
            if action["verdict"] == "wrong":
                print(f"  ❌  not quite — missing: {action['missing']}")
                for pin, actual in (action.get("conflicts") or {}).items():
                    print(f"      ↳ {pin} is currently tied to: {actual}")
            elif action["verdict"] == "harmless":
                print(f"  ⚠️   correct, but flagged: {action.get('note')}")
        elif kind == "complete":
            print("  ✅  lesson complete!")
        elif kind == "error":
            print(f"  ⚠️   {action['message']}")
        else:
            print(f"  ?   {action}")


def try_translate_board(lesson, library, board_name):
    """Attempt to translate `lesson` onto `board_name` (a free-text answer
    like "mega" or "Arduino Mega" — resolved the same alias-aware way
    every other library lookup already works). Returns the lesson to
    actually use (the translated one on success, unchanged on failure) —
    never raises, always prints exactly what happened so a refusal is
    never silent. v1 scope is same-family AVR only (Uno/Nano/Mega) —
    see core/board_translate.py."""
    target = board_translate.resolve_target_board(board_name, library)
    if target is None:
        print(f"  ⚠️   \"{board_name}\" isn't a board this project knows — keeping the lesson as authored.")
        return lesson
    result = board_translate.translate_lesson(lesson, target, library)
    if not result.feasible:
        print("  ⚠️   can't translate this lesson to that board — keeping it as authored:")
        for item in result.infeasible:
            pin = item["pin"] or "(lesson-level)"
            print(f"      ↳ {pin}: {item['reason']}")
        return lesson
    if result.lesson is lesson:
        print("  ✅  that's already this lesson's board — nothing to translate.")
        return lesson
    print(f"  🔁  translated this lesson for the {target.get('spoken_name', target.get('display_name'))}.")
    return result.lesson


def main():
    lesson_id = sys.argv[1] if len(sys.argv) > 1 else "analog-read-serial"
    library = load_library()
    lesson = load_lesson(lesson_id)

    # Asked once, before anything starts — never assumed (same "asked,
    state = engine.initial_state()
    log = eventlog.new_log(lesson_id)

    profile = load_profile()
    if profile.get("name"):
        print(f"Welcome back, {profile['name']}!")
    else:
        try:
            name = input("What's your name? ").strip()
        except EOFError:
            name = ""
        if name:
            profile["name"] = name
            save_profile(profile)

    print(f"--- {lesson.title} ({lesson_id}) --- type 'quit' to exit ---")
    # Same "assumed, not asked, but invited to correct" shape as the
    # breadboard-size message below — printed once, up front, rather than
    # a blocking input() prompt, so a scripted/non-interactive session
    # isn't forced through an extra question it doesn't care about. Only
    # ever actionable before `start` (see the `arduino` command handler
    # below) — state["confirmed_pairs"] has no defined meaning under a
    # different board once real wiring has begun.
    source_card = library.get(lesson.data.get("board"))
    if source_card is not None:
        source_spoken = source_card.get("spoken_name", source_card.get("display_name"))
        print(
            f"  🔧  This lesson was authored for the {source_spoken} — if you have a "
            f"different Arduino (Mega or Nano), say e.g. `arduino mega` before `start`."
        )

    name_map = component_name_map(lesson, library)

    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line.strip().lower() in ("quit", "exit"):
            break
        event = parse(line, name_map)
        if event is None:
            continue
        log.append(event)
        if event["command"] == "arduino":
            # Never routed through engine.handle_event: this swaps which
            # `lesson` object the rest of the session uses, not a `state`
            # transition (see try_translate_board's docstring) — and it's
            # only ever safe before a lesson has actually started.
            if state["started"]:
                print("  ⚠️   already started — the board can only be changed before `start` (see COMMANDS.md).")
            elif not event["board"]:
                print("  ⚠️   usage: arduino <model>, e.g. `arduino mega`")
            else:
                lesson = try_translate_board(lesson, library, event["board"])
                name_map = component_name_map(lesson, library)
            continue
        state, actions = engine.handle_event(lesson, library, state, event)
        render(actions)
        for action in actions:
            if action["type"] == "difficulty_set":
                profile["difficulty"] = action["level"]
                save_profile(profile)
            # board_set is deliberately NOT persisted — which breadboard
            # is on the desk is a fact about *this session*, not the
            # learner, and could easily differ next time. Auto-applying a
            # saved one would quietly reintroduce exactly the "assumed,
            # not asked" behavior `board` was built to avoid in the first
            # place. Always asked fresh — see COMMANDS.md.

        # Right after a manual `start`, quietly apply the remembered
        # difficulty — same effect as typing `difficulty <level>` by
        # hand, just sourced from the saved profile instead of asked
        # fresh every session.
        if event["command"] == "start" and any(a["type"] == "play_clip" for a in actions):
            if profile.get("difficulty"):
                state, _ = engine.handle_event(
                    lesson, library, state, {"command": "difficulty", "level": profile["difficulty"]}
                )
                print(f"  (using your saved difficulty: {profile['difficulty']})")

            # Assume the largest board (fewest false "column doesn't fit"
            # warnings) so plausibility_warning works out of the box for
            # anyone who never thinks to answer `board` explicitly — but
            # say so plainly and invite a correction right here in
            # gather, before any building starts. Never saved to the
            # profile (see above): this is a starting guess for THIS
            # session, not a remembered fact about the learner.
            state, _ = engine.handle_event(lesson, library, state, {"command": "board", "variant": DEFAULT_BREADBOARD_ASSUMPTION})
            print(
                f"  🍞  I'll assume a '{DEFAULT_BREADBOARD_ASSUMPTION}'-size breadboard for now — "
                f"if that's not what you have, say e.g. `board mini` or `board half` before we start building."
            )


if __name__ == "__main__":
    main()
