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
import html
import json
import os
import secrets
import threading
import urllib.error
import urllib.request
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
import core.guide_import
import core.cloud
import core.similar
import core.secretbox

# Dependency order: engine imports checker/lesson/library/physics at module
# level, so those must be reloaded first for engine to pick up new versions.
_RELOAD_ORDER = [core.checker, core.library, core.lesson, core.physics, core.engine, core.eventlog,
                 core.progress, core.build_methods, core.lesson_finder, core.lesson_gen, core.guide_import]

# Wokwi part type → the bench page's leg template.
_TEMPLATES = {"wokwi-resistor": "resistor", "wokwi-led": "led", "wokwi-potentiometer": "pot",
              "wokwi-slide-potentiometer": "pot", "wokwi-pushbutton": "button", "wokwi-pushbutton-6mm": "button",
              "wokwi-slide-switch": "switch", "wokwi-buzzer": "buzzer"}

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


# who this request is from: with accounts on (core/cloud.py), the signed-in
# Google user; otherwise None and everything uses the local profile.json
_request = threading.local()


def _user():
    return getattr(_request, "user", None)


def _guest():
    """A guest's id (typed a name, no Google) — hosted with accounts only."""
    return getattr(_request, "guest", None)


def _profile():
    user = _user()
    if user:
        return core.cloud.load_profile(user)
    if core.cloud.enabled():
        return core.cloud.load_guest(_guest()) if _guest() else {}
    return core.profile.load_profile()


def _store_profile(profile):
    user = _user()
    if user:
        core.cloud.save_profile(user, profile)
    elif core.cloud.enabled():
        if _guest():
            core.cloud.save_guest(_guest(), profile)
    else:
        core.profile.save_profile(profile)


def _load_progress():
    return {**core.progress.empty_progress(), **_profile().get("progress", {})}


def _save_progress(progress):
    profile = _profile()
    profile["progress"] = progress
    _store_profile(profile)


def _is_owner(user):
    """CQ_OWNER_EMAILS (comma-separated): accounts allowed to use the server's
    own Claude login (yours). Everyone else connects their own Claude."""
    owners = {e.strip().lower() for e in os.environ.get("CQ_OWNER_EMAILS", "").split(",") if e.strip()}
    return bool(user and (user.get("email") or "").lower() in owners)


def _claude_for_request():
    """(api_key or None, error or None). Hosted with accounts: a signed-in
    learner's own connected key; the owner may fall back to the server's
    login; nobody else ever uses it. Locally: the server's own login."""
    if not core.cloud.enabled():
        return None, None
    user = _user()
    if not user:
        return None, ({"error": "Sign in with Google first.", "locked": "signin"}, 401)
    sealed = core.cloud.sealed_claude_key(user)
    if sealed:
        try:
            return core.secretbox.open_(sealed), None
        except (ValueError, core.secretbox.NoSecret):
            return None, ({"error": "Your saved Claude key can't be read any more — connect it again.", "locked": "claude"}, 403)
    if _is_owner(user):
        return None, None
    return None, ({"error": "Connect your Claude first — creating lessons uses your own Claude.", "locked": "claude"}, 403)


def _with_claude(fn):
    """Run fn() on the right Claude for this request, or return why not."""
    key, blocked = _claude_for_request()
    if blocked:
        return blocked
    if key:
        with core.lesson_gen.using_key(key):
            return fn()
    return fn()


def _check_anthropic_key(key, opener=urllib.request.urlopen):
    """True if Anthropic accepts the key (a free, read-only request)."""
    req = urllib.request.Request("https://api.anthropic.com/v1/models?limit=1",
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        with opener(req, timeout=15) as res:
            return res.status == 200
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return False
        raise


def api_claude_key(body):
    """Connect ({"key": "sk-ant-…"}) or disconnect ({"remove": true}) your own Claude."""
    user = _user()
    if not core.cloud.enabled() or not user:
        return {"error": "Sign in with Google first."}, 401
    if body.get("remove"):
        core.cloud.save_claude_key(user, None, None)
        return {"connected": False}
    key = str(body.get("key") or "").strip()
    if not key.startswith("sk-ant-") or len(key) < 30:
        return {"error": "That doesn't look like an Anthropic API key (they start with sk-ant-)."}, 400
    if not core.secretbox.available():
        return {"error": "The server can't store keys safely yet (CQ_SECRET_KEY isn't set)."}, 503
    try:
        ok = _check_anthropic_key(key)
    except OSError as exc:
        return {"error": f"Couldn't reach Anthropic to check the key ({exc})."}, 502
    if not ok:
        return {"error": "Anthropic didn't accept that key — check it on console.anthropic.com."}, 400
    core.cloud.save_claude_key(user, core.secretbox.seal(key), key[-4:])
    return {"connected": True, "hint": key[-4:]}


def _claude_status():
    """What the page shows on Create: ready, or locked (and why)."""
    if not core.cloud.enabled():
        return {"ready": bool(core.lesson_gen.backend()), "mode": "local"}
    user = _user()
    if not user:
        return {"ready": False, "mode": "signin"}
    hint = _profile().get("claude_key_hint")
    if hint:
        return {"ready": True, "mode": "own", "hint": hint}
    if _is_owner(user):
        return {"ready": bool(core.lesson_gen.backend()), "mode": "owner"}
    return {"ready": False, "mode": "locked"}


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
    core.cloud.sync_lessons()          # everyone's created lessons (no-op without accounts)
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
                        "parts_used": data.get("parts_used", []),
                        "source": data.get("source"), "substitutions": data.get("substitutions", []),
                        "creator": data.get("creator")})
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
    """How this bench reaches Claude: "api", "claude-code" or null — and, with
    accounts, whether this learner has connected their own Claude."""
    status = _claude_status()
    backend = core.lesson_gen.backend() if status["mode"] in ("local", "owner") else ("api" if status["ready"] else None)
    return {"backend": backend, "flow_check": core.lesson_gen.flow_check_mode(), "claude": status}


def api_ideas(body):
    """LLM lesson ideas from the learner's parts (needs the Anthropic SDK + a key)."""
    ids, unknown = core.lesson_finder.resolve_inventory(body.get("parts", []))
    try:
        ideas = _with_claude(lambda: core.lesson_gen.suggest_ideas(ids))
    except Exception as exc:
        return _ai_unavailable(exc)
    if isinstance(ideas, tuple):
        return ideas
    return {"inventory": ids, "unknown": unknown, "ideas": ideas}


def api_guide(body):
    """Read a tutorial page: every part (exact quantity/value), mapped onto the
    library — exact, or substituted only when we don't have it — for the
    learner to confirm before a lesson is built from it."""
    try:
        return _with_claude(lambda: core.guide_import.import_guide(body["url"]))
    except ValueError as exc:
        return {"error": str(exc)}, 400
    except OSError as exc:            # urllib: DNS, HTTP errors, timeouts
        return {"error": f"Couldn't open that page ({exc})."}, 502
    except Exception as exc:
        return _ai_unavailable(exc)


def api_generate(body):
    """Generate → validate → repair a lesson on the spot, then save it.
    With `guide` (a confirmed plan from /api/guide) it follows that tutorial exactly."""
    inventory = None
    if body.get("parts"):
        inventory, _ = core.lesson_finder.resolve_inventory(body["parts"])
    try:
        if body.get("guide"):
            result = _with_claude(lambda: core.guide_import.generate(body["guide"], inventory=inventory))
        else:
            result = _with_claude(lambda: core.lesson_gen.generate_lesson(body["request"], inventory=inventory))
    except Exception as exc:
        return _ai_unavailable(exc)
    if isinstance(result, tuple):          # locked: sign in / connect your Claude
        return result
    if isinstance(result, dict) and result.get("ok") and result.get("lesson_id"):
        _publish(result["lesson_id"])
    return result


def _publish(lesson_id):
    """Sign a new lesson with its maker and share it (accounts on)."""
    user = _user()
    if not user:
        return
    path = ROOT / "lessons" / lesson_id / "lesson.json"
    data = json.loads(path.read_text())
    data["creator"] = user["name"]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    try:
        core.cloud.save_lesson(lesson_id, user)
    except Exception as exc:          # the lesson still works here; say why it didn't share
        print(f"couldn't share {lesson_id}: {exc}")


def api_similar(body):
    """Before creating: lessons that might be the same (same tutorial link, or
    the same words) — the learner can open one or create anyway."""
    core.cloud.sync_lessons()
    lessons = []
    for path in sorted((ROOT / "lessons").glob("*/lesson.json")):
        d = json.loads(path.read_text())
        lessons.append({"id": d["id"], "title": d.get("title", d["id"]), "description": d.get("description", ""),
                        "source": d.get("source"), "creator": d.get("creator")})
    matches = core.similar.find_similar(body.get("request", ""), lessons, url=body.get("url"))
    by_id = {l["id"]: l for l in lessons}
    return {"matches": [{**m, "creator": by_id[m["id"]].get("creator")} for m in matches]}


def api_auth_config(_body):
    """Whether accounts are on, and the public bits the page needs to sign in."""
    return {**core.cloud.public_config(), "user": _user()}


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


MEDIA_DIRS = [ROOT / "library" / "tools" / "media", ROOT / "library" / "parts" / "media"]
LIB_CATEGORY = {"board": "Boards", "breadboard": "Wiring", "wire": "Wiring", "cable": "Wiring", "utility": "Wiring",
                "led": "Lights", "display": "Displays", "resistor": "Resistors", "potentiometer": "Inputs",
                "pushbutton": "Inputs", "switch": "Inputs", "input": "Inputs", "sensor": "Sensors", "buzzer": "Sound",
                "motor": "Motors", "driver": "Motors", "logic": "Chips", "storage": "Chips", "consumable": "Soldering"}

TOOL_CATEGORY = {"soldering-iron": "Soldering", "solder": "Soldering", "heat-shrink": "Soldering", "solder-wick": "Soldering",
                 "desoldering-pump": "Soldering", "flux-pen": "Soldering", "tip-cleaner": "Soldering",
                 "helping-hands": "Soldering", "heat-gun": "Soldering",
                 "flush-cutters": "Cut & grip", "needle-nose-pliers": "Cut & grip", "wire-stripper": "Cut & grip",
                 "tweezers": "Cut & grip", "small-screwdriver-set": "Cut & grip",
                 "digital-multimeter": "Measure", "safety-glasses": "Safety & finishing", "hot-glue-gun": "Safety & finishing"}


LEGAL_UPDATED = "24 September 2026"


def _legal_page(which):
    """/privacy and /terms — the pages Google asks for before the sign-in can be
    published. CQ_CONTACT_EMAIL (set on the host) is where deletion requests go."""
    folder = PAGE.parent / "legal"
    contact = os.environ.get("CQ_CONTACT_EMAIL", "").strip()
    how = (f'email <a href="mailto:{html.escape(contact)}">{html.escape(contact)}</a>' if contact
           else "contact the person who runs this CircuitQuest site")
    body = (folder / f"{which}.html").read_text().replace("{{UPDATED}}", LEGAL_UPDATED).replace("{{CONTACT}}", how)
    return ((folder / "page.html").read_text().replace("{{TITLE}}", "Privacy policy" if which == "privacy" else "Terms of use")
            .replace("{{BODY}}", body))


def _media_file(name):
    """A tutorial clip that is actually on disk, or None."""
    for d in MEDIA_DIRS:
        if name and (d / name).is_file():
            return d / name
    return None


def api_library(_body):
    """Every part and tool card for the Parts & Tools section: what it is,
    how to use it, its pins, the levels that use it, and its video if one
    is on disk."""
    library = core.library.load_library()
    used = {}
    for path in sorted((ROOT / "lessons").glob("*/lesson.json")):
        data = json.loads(path.read_text())
        for pid in set(data.get("parts_used", []) + data.get("tools_used", [])):
            used.setdefault(pid, []).append({"id": data["id"], "title": data.get("title", data["id"])})
    out = []
    for card in library.cards.values():
        if card.get("type") not in ("part", "tool"):
            continue
        wt = card.get("wokwi_type")
        wt = wt[0] if isinstance(wt, list) else wt
        clip = card.get("tutorial_clip")
        kind = "tool" if card["type"] == "tool" or card.get("subtype") == "consumable" else "part"
        out.append({"id": card["id"], "kind": kind, "name": card["display_name"],
                    "category": TOOL_CATEGORY.get(card["id"], "Tools") if kind == "tool" else LIB_CATEGORY.get(card.get("subtype"), "Other"),
                    "wokwi_type": wt, "attrs": {"value": card["wokwi_value"]} if card.get("wokwi_value") else {},
                    "description": card.get("description", ""), "how_to_use": card.get("how_to_use", ""),
                    "pins": card.get("pins", []), "polarized": bool(card.get("polarized")), "tier": card.get("tier"),
                    "aliases": card.get("aliases", []),
                    "video": f"/media/{clip}" if _media_file(clip) else None,
                    "used_in": used.get(card["id"], [])})
    out.sort(key=lambda c: (c["kind"], c["category"], c["name"]))
    return {"items": out}


def api_profile(body):
    """GET-style (no body) returns the learner; {"name": ...} saves it."""
    profile = _profile()
    if body.get("name"):
        profile["name"] = str(body["name"]).strip()[:40]
        _store_profile(profile)
    gid = str(body.get("adopt_guest") or "").lower()
    if _user() and core.cloud.valid_guest_id(gid):
        # a guest just signed in with Google: keep their progress if the account has none yet
        guest = core.cloud.load_guest(gid)
        if guest.get("progress", {}).get("xp") and not profile.get("progress", {}).get("xp"):
            profile["progress"] = guest["progress"]
            _store_profile(profile)
    user = _user()
    return {"name": profile.get("name"), "difficulty": profile.get("difficulty", "beginner"),
            "avatar": user and user.get("avatar"), "account": bool(user),
            "progress": _progress_summary(_load_progress())}


ROUTES = {"/api/lessons": api_lessons, "/api/start": api_start, "/api/event": api_event,
          "/api/find": api_find, "/api/ideas": api_ideas, "/api/generate": api_generate, "/api/part": api_part,
          "/api/parts_catalog": api_parts_catalog, "/api/plan": api_plan, "/api/guide": api_guide, "/api/ai_status": api_ai_status, "/api/profile": api_profile, "/api/library": api_library,
          "/api/similar": api_similar, "/api/auth_config": api_auth_config,
          "/api/claude_key": api_claude_key}


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
        auth = self.headers.get("Authorization", "")
        _request.user = core.cloud.user_from_token(auth[7:]) if auth.startswith("Bearer ") else None
        gid = (self.headers.get("X-CQ-Guest") or "").strip().lower()
        _request.guest = gid if not _request.user and core.cloud.enabled() and core.cloud.valid_guest_id(gid) else None
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
        if self.path.split("?")[0] in ("/privacy", "/terms"):
            return self._send(200, _legal_page(self.path.split("?")[0][1:]).encode(), "text/html; charset=utf-8")
        name = self.path.split("?")[0].lstrip("/")
        static = (PAGE.parent / name[len("bench/"):]) if name.startswith("bench/") else None
        if static and static.suffix in (".js", ".css") and PAGE.parent.resolve() in static.resolve().parents and static.exists():
            kind = "text/javascript" if static.suffix == ".js" else "text/css"
            return self._send(200, static.read_bytes(), f"{kind}; charset=utf-8")
        if name.startswith("media/"):
            return self._send_media(name[len("media/"):])
        self._dispatch({})

    def _send_media(self, name):
        """A tool video, with Range support so the browser can seek (Safari needs it)."""
        path = _media_file(name) if "/" not in name and not name.startswith(".") else None
        if path is None or path.suffix.lower() not in (".mp4", ".webm"):
            return self._send(404, {"error": "not found"})
        size = path.stat().st_size
        start, end = 0, size - 1
        rng = self.headers.get("Range", "")
        if rng.startswith("bytes="):
            a, _, b = rng[6:].split(",")[0].partition("-")
            try:
                start, end = (int(a), int(b) if b else size - 1) if a else (size - int(b), size - 1)
            except ValueError:
                pass
            end = min(end, size - 1)
            if start > end or start < 0:
                self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.end_headers(); return
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", "video/mp4" if path.suffix.lower() == ".mp4" else "video/webm")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 16, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk); left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

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
    # a port on the command line wins; hosts like Render pass it as $PORT
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", PORT))
    # only this machine by default; a container sets CQ_HOST=0.0.0.0 to be reachable
    host = os.environ.get("CQ_HOST", "127.0.0.1")
    route = core.lesson_gen.backend()
    how = {"claude-code": "your Claude Code login" + (" (token from .env)" if "CLAUDE_CODE_OAUTH_TOKEN" in loaded else ""),
           "api": "the Anthropic API key" + (" (from .env)" if "ANTHROPIC_API_KEY" in loaded else ""), None: "off"}[route]
    print("Accounts: Sign in with Google (Supabase) — created lessons are shared" if core.cloud.enabled() else "Accounts: off (local profile.json; see cloud/SETUP.md)")
    print(f"AI lessons: {how}")
    ThreadingHTTPServer.request_queue_size = 128   # the page fetches many JS modules at once; the default (5) drops some
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"CircuitQuest Wiring Bench running on the real engine → http://localhost:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
