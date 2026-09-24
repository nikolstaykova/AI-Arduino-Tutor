"""CircuitQuest Wiring Bench — local server that runs the REAL engine behind the browser UI.

    python3 bench_server.py            # then open http://localhost:8765

The page (bench/index.html) is only the breadboard UI: drag-and-drop
placement and wire drawing. Every check, hint, substitution, remap and
code adjustment comes from core/engine.py, called exactly the way cli.py
calls it — handle_event(lesson, library, state, event) — against the real
lessons/ and library/ folders. No JS mirror of the engine logic exists
anywhere, so the bench can't drift from what the test suite covers.

Engine modules are reloaded at the start of every lesson, so an edit to
core/*.py or a lesson.json shows up on the next "Start lesson" without
restarting the server. Every event is appended to logs/<lesson>/ just like
a CLI session, so a bench session is replayable with eventlog.replay.

Also serves the game layer: physics results after every check
(core/physics.py), XP/levels/badges on completion (core/progress.py, saved
in profile.json), "what can I build with my parts?" (core/lesson_finder.py)
and lessons generated on the spot by Claude (core/lesson_gen.py; needs
`pip install anthropic` and an API key).
"""
import importlib
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "bench" / "index.html"
PORT = 8765
DEFAULT_BREADBOARD = "full"  # same assumption cli.py makes

sys.path.insert(0, str(ROOT))
import core.checker
import core.library
import core.lesson
import core.physics
import core.engine
import core.eventlog
import core.progress
import core.lesson_finder
import core.lesson_gen
import core.profile
import core.worlds
import core.build_methods

# Dependency order: engine imports checker/lesson/library/physics at module
# level, so those must be reloaded first for engine to pick up new versions.
_RELOAD_ORDER = [core.checker, core.library, core.lesson, core.physics, core.engine, core.eventlog,
                 core.progress, core.build_methods, core.lesson_finder, core.lesson_gen]

# Wokwi part type → the bench page's leg template.
_TEMPLATES = {"wokwi-resistor": "resistor", "wokwi-led": "led", "wokwi-potentiometer": "pot",
              "wokwi-slide-potentiometer": "pot", "wokwi-pushbutton": "button", "wokwi-pushbutton-6mm": "button"}

sessions = {}  # session id -> {"lesson", "library", "state", "log"}


def _reload_engine():
    for module in _RELOAD_ORDER:
        importlib.reload(module)


def _tray_parts(lesson, library):
    """The parts the learner drags onto the board, straight from the
    lesson's own diagram.json + library cards — so a generated lesson
    needs no page changes."""
    parts = []
    for part in lesson.diagram().get("parts", []):
        template = _TEMPLATES.get(part.get("type"))
        if not template:
            continue
        attrs = part.get("attrs", {})
        cards = library.find_by_wokwi_type(part["type"], attrs.get("value"))
        label = cards[0]["display_name"] if cards else part["type"].replace("wokwi-", "")
        if template == "led" and attrs.get("color"):
            label = f"LED ({attrs['color']})"
        parts.append({"id": part["id"], "type": template, "label": label, "sub": cards[0]["id"] if cards else part["type"],
                      "wokwi_type": part["type"], "attrs": attrs, "card_id": cards[0]["id"] if cards else None,
                      "leads": cards[0].get("leads", "pin") if cards else "pin"})
    return parts


def _layout(lesson):
    """Which board and breadboard the page draws (real Wokwi types)."""
    parts = lesson.diagram().get("parts", [])
    board = next((p for p in parts if "arduino" in p.get("type", "")), None)
    bb = next((p for p in parts if "breadboard" in p.get("type", "")), None)
    return {"board": {"id": board["id"], "type": board["type"]} if board else None,
            "breadboard": {"id": bb["id"], "type": bb["type"]} if bb else None}


def _progress_summary(progress):
    level, into, span = core.progress.level_for(progress.get("xp", 0))
    return {**progress, "level": level, "level_xp": into, "level_span": span,
            "badge_names": {b: core.progress.BADGES.get(b, b) for b in progress.get("badges", [])}}


def _load_progress():
    return {**core.progress.empty_progress(), **core.profile.load_profile().get("progress", {})}


def _save_progress(progress):
    profile = core.profile.load_profile()
    profile["progress"] = progress
    core.profile.save_profile(profile)


def _view(session):
    """Everything the page renders, read straight from the engine's state."""
    lesson, state = session["lesson"], session["state"]
    engine = core.engine
    step = lesson.step(state["step_index"]) if state["step_index"] >= 0 else None
    code = engine._adjusted_code(lesson, state) if step and step.get("phase") == "upload" else None
    breadboard_id = board_id = None
    for part in lesson.diagram().get("parts", []):
        part_type = part.get("type", "")
        if "breadboard" in part_type:
            breadboard_id = part["id"]
        if "arduino" in part_type:
            board_id = part["id"]
    return {
        "phase": state["phase"],
        "step_index": state["step_index"],
        "step_count": lesson.step_count(),
        "step": step,
        "finished": state["finished"],
        "confirmed_pairs": state["confirmed_pairs"],
        "pin_substitutions": state["pin_substitutions"],
        "pin_remaps": state["pin_remaps"],
        "hints_used": state["hints_used"],
        "code": code,
        "breadboard_id": breadboard_id,
        "board_id": board_id,
    }


def _handle(session, event):
    session["log"].append(event)
    session["state"], actions = core.engine.handle_event(
        session["lesson"], session["library"], session["state"], event
    )
    return actions


def _physics(session, pairs):
    """Solve what the learner has on the board right now (core/physics.py)."""
    lesson = session["lesson"]
    code = core.engine._adjusted_code(lesson, session["state"])
    return core.physics.analyze(pairs, lesson.diagram().get("parts", []), code, session["library"])


def _award(session):
    """Score the finished session by replaying its log through the engine,
    then fold it into the learner's saved progress."""
    lesson = session["lesson"]
    score = core.progress.score_session(lesson, session["library"], session["log"].read_events())
    progress, award = core.progress.apply_session(
        _load_progress(), lesson.id, score, generated=bool(lesson.data.get("generated")))
    _save_progress(progress)
    return {**award, "score": score, "progress": _progress_summary(progress)}


def api_lessons(_body):
    progress = _load_progress()
    lessons = []
    for path in sorted((ROOT / "lessons").glob("*/lesson.json")):
        data = json.loads(path.read_text())
        lessons.append({"id": data["id"], "title": data.get("title", data["id"]),
                        "description": data.get("description", ""),
                        "generated": bool(data.get("generated")),
                        "requires": data.get("requires", []),
                        "unlocked": True,     # every level is playable in any order
                        "prereqs_done": core.progress.unlocked(data, progress),
                        "completed": data["id"] in progress["completed"],
                        "stars": progress["completed"].get(data["id"], {}).get("stars", 1 if data["id"] in progress["completed"] else 0),
                        "difficulty": data.get("difficulty", "beginner"),
                        "parts_used": data.get("parts_used", [])})
    return {"lessons": lessons, "worlds": core.worlds.build_map(lessons), "progress": _progress_summary(progress)}


def api_find(body):
    """'I have these parts — what can I build?'"""
    ids, unknown = core.lesson_finder.resolve_inventory(body.get("parts", []))
    results = core.lesson_finder.find_lessons(ids, progress=_load_progress())
    return {"inventory": ids, "unknown": unknown, "lessons": results}


def _ai_unavailable(exc):
    """Missing SDK or credentials: a clear 503, not a traceback."""
    name = type(exc).__name__
    if isinstance(exc, core.lesson_gen.AIUnavailable):
        return {"error": f"AI unavailable: {exc}"}, 503
    if isinstance(exc, RuntimeError):          # Claude answered, but not usefully (timeout, refusal, ...)
        return {"error": str(exc)}, 502
    if isinstance(exc, ImportError) or "Authentication" in name or "api_key" in str(exc).lower() or "auth" in str(exc).lower():
        return {"error": "AI unavailable: install the Anthropic SDK (pip install anthropic) and set ANTHROPIC_API_KEY."}, 503
    raise exc


def api_ai_status(_body):
    """How this bench reaches Claude: "api", "claude-code" or null."""
    return {"backend": core.lesson_gen.backend()}


def api_ideas(body):
    """LLM lesson ideas from the learner's parts (needs the Anthropic SDK + a key)."""
    ids, unknown = core.lesson_finder.resolve_inventory(body.get("parts", []))
    try:
        ideas = core.lesson_gen.suggest_ideas(ids)
    except Exception as exc:
        return _ai_unavailable(exc)
    return {"inventory": ids, "unknown": unknown, "ideas": ideas}


def api_generate(body):
    """Generate → validate → repair a lesson on the spot, then save it."""
    inventory = None
    if body.get("parts"):
        inventory, _ = core.lesson_finder.resolve_inventory(body["parts"])
    try:
        return core.lesson_gen.generate_lesson(body["request"], inventory=inventory)
    except Exception as exc:
        return _ai_unavailable(exc)


def api_start(body):
    _reload_engine()
    lesson_id = body["lesson_id"]
    session_id = "bench-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(2)
    library = core.library.load_library()
    build = body.get("build") or {}
    method, join = build.get("method", "breadboard"), build.get("join") or "clips"
    if method not in core.build_methods.METHODS or join not in core.build_methods.JOINS:
        return {"error": f"Unknown build method {method}/{join}."}, 400
    session = {
        # without a breadboard the session runs a derived lesson: same
        # circuit and code, steps rewritten for how the legs really connect
        "lesson": core.build_methods.derive_lesson(core.lesson.load_lesson(lesson_id), library, method, join),
        "library": library,
        "state": core.engine.initial_state(),
        "log": core.eventlog.new_log(lesson_id, session_id),
    }
    progress = _load_progress()
    sessions[session_id] = session
    actions = []
    # Same opening sequence as a CLI session: start, apply the chosen
    # difficulty and the default breadboard assumption, then confirm the
    # gather step (the bench has no physical parts to gather).
    for event in (
        {"command": "start"},
        {"command": "difficulty", "level": body.get("difficulty", "beginner")},
        {"command": "board", "variant": DEFAULT_BREADBOARD},
        {"command": "done"},
    ):
        actions += _handle(session, event)
    return {"session": session_id, "actions": actions, "view": _view(session),
            "parts": _tray_parts(session["lesson"], session["library"]),
            "layout": _layout(session["lesson"]),
            # the lesson's own finished circuit (leg -> hole, hole -> pin), so
            # "reveal step" can show where a part that isn't placed yet goes
            "reference": [c[:2] for c in session["lesson"].diagram().get("connections", [])],
            "build": {"method": method, "join": join if method != "breadboard" else None,
                      **session["lesson"].data.get("build_method", {})},
            "progress": _progress_summary(progress)}


def api_plan(body):
    """Every way to build a lesson — with a breadboard, or without one
    (clip leads / twisted legs / solder) — with the parts (and counts),
    tools, what changes and the how-to for each connection."""
    library = core.library.load_library()
    lesson = core.lesson.load_lesson(body["lesson_id"])
    name = lambda i: (library.get(i) or {"display_name": i})["display_name"]
    ways = []
    for p in core.build_methods.all_plans(lesson, library):
        ways.append({"method": p["method"], "join": p["join"],
                     "parts": [{"id": i, "name": name(i), "count": p["counts"].get(i, 1)} for i in p["parts"]],
                     "tools": [{"id": i, "name": name(i)} for i in p["tools"]],
                     "changes": {k: [{"id": i, "name": name(i)} for i in v] for k, v in p["changes"].items()},
                     "steps": p["steps"], "notes": p["notes"]})
    return {"lesson_id": lesson.id, "ways": ways}


def api_event(body):
    session = sessions.get(body.get("session"))
    if session is None:
        return {"error": "Unknown session — start the lesson again."}, 404
    event = body.get("event")
    was_finished = session["state"]["finished"]
    actions = _handle(session, event)
    result = {"actions": actions, "view": _view(session)}
    if isinstance(event, dict) and isinstance(event.get("detected_pairs"), list):
        result["physics"] = _physics(session, event["detected_pairs"])
    if session["state"]["finished"] and not was_finished:
        result["award"] = _award(session)
    return result


def api_part(body):
    """Everything the part inspector shows: the library card, the physical
    facts the engine and AI brief use, and what each pin is."""
    library = core.library.load_library()
    cards = library.find_by_wokwi_type(body.get("wokwi_type"), (body.get("attrs") or {}).get("value"))
    card = cards[0] if cards else (library.get(body.get("card_id")) if body.get("card_id") else None)
    if card is None:
        return {"error": "unknown part"}, 404
    facts = core.lesson_gen.part_facts(library).get(body.get("wokwi_type"), {})
    return {"card": {k: card.get(k) for k in ("id", "display_name", "description", "how_to_use", "pins", "polarized",
                                               "legs_placed_together", "straddles_center_gap", "symmetric_pins",
                                               "pin_domains", "protocol_pins", "led_builtin")},
            "groups": facts.get("groups", []), "interchangeable": facts.get("interchangeable", card.get("symmetric_pins", []))}


# The parts the Learn picker offers first — the ones lessons are built from.
PICKER_FIRST = ["arduino-uno", "usb-cable", "breadboard", "jumper-wire", "led", "resistor-220", "resistor-1k",
                "resistor-10k", "pushbutton", "potentiometer-10k", "alligator-clip-wire", "jumper-wire-mf", "soldering-iron"]


def api_parts_catalog(_body):
    """Every library part the Learn picker can show, with the real Wokwi
    element (and attrs) to draw it with where one exists."""
    library = core.library.load_library()
    out = []
    for card in library.cards.values():
        if card.get("type") not in ("part", "tool"):
            continue
        wt = card.get("wokwi_type")
        wt = wt[0] if isinstance(wt, list) else wt
        attrs = {"value": card["wokwi_value"]} if card.get("wokwi_value") else {}
        out.append({"id": card["id"], "name": card["display_name"], "subtype": card.get("subtype") or card["type"],
                    "wokwi_type": wt, "attrs": attrs, "popular": card["id"] in PICKER_FIRST,
                    "description": card.get("description", "")})
    out.sort(key=lambda c: (not c["popular"], PICKER_FIRST.index(c["id"]) if c["popular"] else 0, c["name"]))
    return {"parts": out}


def api_profile(body):
    """GET-style (no body) returns the learner; {"name": ...} saves it."""
    profile = core.profile.load_profile()
    if body.get("name"):
        profile["name"] = str(body["name"]).strip()[:40]
        core.profile.save_profile(profile)
    return {"name": profile.get("name"), "difficulty": profile.get("difficulty", "beginner"),
            "progress": _progress_summary(_load_progress())}


ROUTES = {"/api/lessons": api_lessons, "/api/start": api_start, "/api/event": api_event,
          "/api/find": api_find, "/api/ideas": api_ideas, "/api/generate": api_generate, "/api/part": api_part,
          "/api/parts_catalog": api_parts_catalog, "/api/plan": api_plan, "/api/ai_status": api_ai_status, "/api/profile": api_profile}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _dispatch(self, body):
        route = ROUTES.get(self.path.split("?")[0])
        if route is None:
            return self._send(404, {"error": "not found"})
        try:
            result = route(body)
        except Exception as exc:  # surface engine errors in the page, not just the terminal
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
        status = 200
        if isinstance(result, tuple):
            result, status = result
        self._send(status, result)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        name = self.path.split("?")[0].lstrip("/")
        static = (PAGE.parent / name[len("bench/"):]) if name.startswith("bench/") else None
        if static and static.suffix in (".js", ".css") and PAGE.parent.resolve() in static.resolve().parents and static.exists():
            kind = "text/javascript" if static.suffix == ".js" else "text/css"
            return self._send(200, static.read_bytes(), f"{kind}; charset=utf-8")
        self._dispatch({})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "invalid JSON"})
        self._dispatch(body)

    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet; errors are still printed above


def load_env(path=None):
    """Read KEY=VALUE lines from a local .env (git-ignored) into the
    environment — e.g. CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`, or
    ANTHROPIC_API_KEY. Values already set in the real environment win.
    Returns the names loaded (never the values)."""
    path = Path(path) if path else ROOT / ".env"
    if not path.is_file():
        return []
    loaded = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip().removeprefix("export ").strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def main():
    loaded = load_env()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    route = core.lesson_gen.backend()
    how = {"claude-code": "your Claude Code login" + (" (token from .env)" if "CLAUDE_CODE_OAUTH_TOKEN" in loaded else ""),
           "api": "the Anthropic API key" + (" (from .env)" if "ANTHROPIC_API_KEY" in loaded else ""), None: "off"}[route]
    print(f"AI lessons: {how}")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"CircuitQuest Wiring Bench running on the real engine → http://localhost:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
