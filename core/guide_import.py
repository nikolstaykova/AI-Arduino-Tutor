"""Build a lesson from a real tutorial (Arduino Project Hub, build-electronic-
circuits.com, …) — and follow it exactly.

1. `fetch_text(url)`   the page itself, as plain text (Claude runs with no tools,
                        so it never reads links on its own).
2. `analyze(text)`     Claude extracts EVERY part (exact quantity + value), the
                        circuit, the switch behaviour, what it does and the code.
3. `map_parts(...)`    plain code, no AI: each guide part -> a library card.
                        "exact" when we have it; "substitute" ONLY when we don't
                        (with the reason); "tool" for tools; "unsupported" when
                        nothing can stand in (the lesson can't be made faithfully).
4. The learner sees that plan and confirms it.
5. `generate(plan)`    lesson_gen with hard requirements (these parts, these
                        counts, these values, this circuit, this code) and an
                        extra validator: the generated circuit must contain
                        exactly the confirmed parts — or it goes back to Claude.
"""
import html.parser
import json
import re
import urllib.request

from . import lesson_gen
from .library import load_library

MAX_BYTES = 3_000_000
MAX_CHARS = 40_000

# ---------------------------------------------------------------------------
# 1. The page, as text
# ---------------------------------------------------------------------------
_SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "form", "iframe", "button"}
_BLOCK = {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "section", "article", "table", "ul", "ol"}


class _Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.title, self._in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in _BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in _BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data)


def html_to_text(page):
    """(title, readable text) from an HTML page."""
    p = _Text()
    p.feed(page)
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.out))
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return p.title.strip(), text[:MAX_CHARS]


def _get(url, opener, accept="text/html"):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (CircuitQuest guide import)", "Accept": accept})
    with opener(req, timeout=25) as resp:
        raw = resp.read(MAX_BYTES)
        charset = resp.headers.get_content_charset() if getattr(resp, "headers", None) else None
    return raw.decode(charset or "utf-8", errors="replace")


def _structured_text(page):
    """schema.org HowTo / Article data many pages embed for search engines —
    often the whole guide, even when the visible page is built by JavaScript."""
    out = []
    for attrs, body in re.findall(r"<script([^>]*)>(.*?)</script>", page, re.S | re.I):
        if "ld+json" not in attrs:
            continue
        try:
            data = json.loads(body)
        except ValueError:
            continue
        for item in data if isinstance(data, list) else data.get("@graph", [data]):
            if not isinstance(item, dict) or item.get("@type") not in ("HowTo", "Article", "TechArticle", "BlogPosting"):
                continue
            out.append(str(item.get("name") or item.get("headline") or ""))
            out.append(str(item.get("description") or ""))
            for key in ("supply", "tool"):
                for x in item.get(key, []) or []:
                    out.append("- " + (x.get("name", "") if isinstance(x, dict) else str(x)))
            for st in item.get("step", []) or []:
                if isinstance(st, dict):
                    out.append(f"\n{st.get('name', '')}\n{html_to_text(str(st.get('text', '')))[1]}")
            if item.get("articleBody"):
                out.append(str(item["articleBody"]))
    return "\n".join(x for x in out if x.strip())


def _instructables_text(url, opener):
    """Instructables renders in the browser; its own JSON API has the parts
    list and every step's full text."""
    m = re.search(r"instructables\.com/([^/?#]+)", url)
    if not m:
        return ""
    data = json.loads(_get(f"https://www.instructables.com/json-api/showInstructableModel?urlString={m.group(1)}", opener, "application/json"))
    out = [data.get("title", "")]
    if data.get("supplies"):
        out += ["\nSupplies:", html_to_text(data["supplies"])[1]]
    for st in data.get("steps", []):
        out += [f"\n{st.get('title', '')}", html_to_text(st.get("body", ""))[1]]
    return "\n".join(out)


def fetch_text(url, opener=urllib.request.urlopen):
    """(title, text) of a tutorial page: its HTML, else the structured data it
    embeds, else a site's own API. Pages that only exist after JavaScript runs
    and share nothing else can't be read — say so rather than guess."""
    if not re.match(r"^https?://", str(url or ""), re.I):
        raise ValueError("That isn't a web link (it should start with http:// or https://).")
    page = _get(url, opener)
    title, text = html_to_text(page)
    if len(text) < 1500:
        extra = _structured_text(page)
        try:
            extra = _instructables_text(url, opener) or extra
        except (OSError, ValueError):
            pass
        if len(extra) > len(text):
            text = extra[:MAX_CHARS]
    if len(text) < 300:
        raise ValueError("That page builds its content with JavaScript and doesn't share it, so I can't read it. "
                         "Copy the guide's parts list and steps and paste them here instead.")
    return title, text


# ---------------------------------------------------------------------------
# 2. Claude extracts the guide — completely, not simplified
# ---------------------------------------------------------------------------
GUIDE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "behaviour": {"type": "string"},
        "uses_microcontroller": {"type": "boolean"},
        "board": {"type": "string"},
        "switch_behaviour": {"type": "string", "enum": ["momentary", "latching", "none", "unspecified"]},
        "parts": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "quantity": {"type": "integer"}, "value": {"type": "string"},
            "color": {"type": "string"}, "optional": {"type": "boolean"}},
            "required": ["name", "quantity", "value", "color", "optional"], "additionalProperties": False}},
        "circuit": {"type": "array", "items": {"type": "string"}},
        "code": {"type": "string"},
    },
    "required": ["title", "summary", "behaviour", "uses_microcontroller", "board", "switch_behaviour", "parts", "circuit", "code"],
    "additionalProperties": False,
}

ANALYZE_SYSTEM = """You read an electronics tutorial and extract it EXACTLY and COMPLETELY, so
a lesson can reproduce it faithfully. Never simplify, merge, drop or invent anything.

- parts: every component and material in the guide's parts list (and any the
  text or code uses but the list forgets), each once, with the EXACT quantity
  (5 LEDs -> quantity 5, not 1), the value exactly as written ("100 Ω", "10k",
  "" if none) and the LED colour if stated ("" if not). optional = true only if
  the guide says it's optional. Tools (soldering iron, wire stripper) count as parts.
- circuit: the wiring, one plain line per connection or rule, as the guide
  describes it ("each LED has its own 100 Ω resistor in series",
  "the five LED+resistor pairs are in parallel between 5V and GND",
  "pin 9 -> red LED anode"). Keep series / parallel structure explicit.
- switch_behaviour: "momentary" if the light/output is on only while a button
  is held, "latching" for an on/off switch that stays where it's put, "none"
  if there's no switch, "unspecified" if the guide doesn't say.
- behaviour: what the finished project does, in one or two sentences.
- uses_microcontroller / board: whether an Arduino (which one) or other
  microcontroller is used at all.
- code: the guide's full sketch verbatim if it has one, else "".
"""


def analyze(title, text, url="", generate_fn=None):
    """Claude's structured reading of the guide."""
    generate_fn = generate_fn or (lambda system, messages: lesson_gen._call_model(system, messages, GUIDE_SCHEMA))
    messages = [{"role": "user", "content": f"Tutorial: {title}\nURL: {url}\n\n{text}"}]
    out, _ = generate_fn(ANALYZE_SYSTEM, messages)
    return out


# ---------------------------------------------------------------------------
# 3. Map the guide's parts onto the library — substitute only what we lack
# ---------------------------------------------------------------------------
PASSIVE = {"arduino-uno", "breadboard", "jumper-wire", "jumper-wire-mf", "usb-cable", "alligator-clip-wire"}

# things the library doesn't have (or lessons can't use yet), and what stands in
# parts we HAVE, whatever the guide calls them — always an exact match
KINDS = [
    (r"push ?-?buttons?|tactile|momentary (push )?switch", "pushbutton"),
    (r"piezo|buzzer", "buzzer"),
    (r"slide switch", "slide-switch"),
    (r"potentiometer|\bpot\b|trimmer|trim ?pot", "potentiometer-10k"),
]

SUBSTITUTES = [
    (r"usb.*(breakout|connector|port|plug|socket|power)|power ?bank|usb supply",
     "arduino-uno", "The Arduino's 5V and GND pins stand in for the USB breakout — they are the USB port's 5V supply."),
    (r"perf ?board|proto(typing)? ?board|strip ?board|\bpcb\b|vero",
     "breadboard", "A breadboard stands in for the perfboard. To build it the guide's way, pick No breadboard → Solder on the level card."),
    (r"\b9 ?v\b|battery|aa\b|aaa\b|coin cell",
     "arduino-uno", "Powered from the Arduino's 5V instead of a battery."),
    (r"arduino (mega|nano|leonardo|micro|due|pro)",
     "arduino-uno", "Lessons are built on the Arduino Uno; the same pins exist on it."),
    (r"\b(toggle|rocker|slide|on ?/ ?off|latching|spdt|spst)\b.*switch|switch.*\b(toggle|rocker|slide|on ?/ ?off)\b",
     "slide-switch", "A slide switch is the on/off switch: it stays where you put it."),
    (r"push ?button|tactile|momentary",
     "pushbutton", "A momentary pushbutton."),
]
TOOL_WORDS = (r"solder(ing)? iron|wire strip|cutter|pliers|multimeter|screwdriver|tweezer|heat ?shrink|hot glue|glue gun|solder\b"
              r"|helping hands?|third hand|desoldering|solder (sucker|wick|braid)|heat gun|hot air gun|safety (glasses|goggles)|flux|tip cleaner|brass wool")


def _ohms(value):
    m = re.search(r"([\d.]+)\s*([kKmM]?)", str(value or "").replace(",", "."))
    if not m:
        return None
    return float(m.group(1)) * {"": 1, "k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6}[m.group(2)]


def _modelled(card):
    wt = card.get("wokwi_type")
    types = wt if isinstance(wt, list) else [wt]
    return any(t in lesson_gen.MODELLED_TYPES for t in types)


def _resistor_cards(library):
    return {float(c["wokwi_value"]): c for c in library.cards.values() if c.get("subtype") == "resistor" and c.get("wokwi_value")}


def _tool_by_alias(text, library):
    """The tool card whose name or alias appears in the guide's wording
    (longest match wins: "desoldering pump" over "pump")."""
    best = None
    for card in library.cards.values():
        if card.get("type") != "tool" and card["id"] not in ("solder", "heat-shrink"):
            continue
        for word in [card["display_name"], card["id"].replace("-", " ")] + card.get("aliases", []):
            w = word.lower()
            if re.search(r"\b" + re.escape(w) + r"\b", text) and (best is None or len(w) > best[0]):
                best = (len(w), card)
    return best[1] if best else None


def map_part(part, switch_behaviour, library):
    """One guide part -> {card, status, note}."""
    name, value = part["name"], part.get("value", "")
    low = f"{name} {value}".lower()
    if re.search(TOOL_WORDS, low):
        card = library.get(name) or _tool_by_alias(low, library)
        return {"card": card["id"] if card else None, "status": "tool", "note": "A tool — listed, not simulated."}
    if "resistor" in low or re.search(r"\d\s*(Ω|ohm|k\b)", str(value), re.I):
        ohms = _ohms(value) or _ohms(name)
        cards = _resistor_cards(library)
        if ohms in cards:
            return {"card": cards[ohms]["id"], "status": "exact", "note": ""}
        if ohms:
            near = min(cards, key=lambda v: abs(v - ohms) / ohms)
            return {"card": cards[near]["id"], "status": "substitute",
                    "note": f"We don't stock {value}; {cards[near]['display_name']} is the nearest value we have."}
    if re.search(r"\bleds?\b|light.?emitting", low) and "bar" not in low and "strip" not in low and "matrix" not in low:
        return {"card": "led", "status": "exact", "note": ""}
    card = library.get(name) or library.get("-".join(name.lower().split()))
    if card and (card["id"] in PASSIVE or _modelled(card)):
        return {"card": card["id"], "status": "exact", "note": ""}
    for pattern, kind in KINDS:
        if re.search(pattern, low):
            if kind == "potentiometer-10k" and _ohms(value) and _ohms(value) != 10000:
                return {"card": kind, "status": "substitute", "note": f"We have a 10 kΩ potentiometer, not {value}; it works the same way here."}
            return {"card": kind, "status": "exact", "note": ""}
    for pattern, sub, why in SUBSTITUTES:
        if re.search(pattern, low):
            exact = card and card["id"] == sub
            return {"card": sub, "status": "exact" if exact else "substitute", "note": "" if exact else why}
    if re.search(r"\bswitch\b", low):
        sub = "pushbutton" if switch_behaviour == "momentary" else "slide-switch"
        return {"card": sub, "status": "substitute",
                "note": "A pushbutton (on while held), as the guide's switch is." if sub == "pushbutton" else "A slide switch, as the guide's on/off switch."}
    if re.search(r"jumper|hook.?up wire|\bwires?\b|dupont", low):
        return {"card": "jumper-wire", "status": "exact", "note": ""}
    if re.search(r"usb cable|usb lead", low):
        return {"card": "usb-cable", "status": "exact", "note": ""}
    return {"card": card["id"] if card else None, "status": "unsupported",
            "note": "CircuitQuest can't simulate this part yet." if card else "Not in the parts library."}


def map_parts(analysis, library=None):
    """The whole plan: every guide part, what the lesson will use, and why."""
    library = library or load_library()
    rows = []
    for part in analysis["parts"]:
        m = map_part(part, analysis.get("switch_behaviour", "unspecified"), library)
        if part.get("optional") and m["status"] == "unsupported":
            m = {**m, "status": "skipped", "note": "Optional in the guide — left out."}
        elif part.get("optional") and m["status"] == "substitute" and m["card"] == "arduino-uno":
            m = {**m, "status": "skipped", "note": "Optional in the guide, and not needed here — the Arduino's USB power does this."}
        qty = max(1, int(part.get("quantity") or 1))
        label = f"{qty}× {part['name']}" + (f" ({part['value']})" if part.get("value") and part["value"] not in part["name"] else "")
        rows.append({"guide": label, "name": part["name"], "quantity": qty, "value": part.get("value", ""),
                     "color": part.get("color", ""), **m,
                     "card_name": (library.get(m["card"]) or {}).get("display_name") if m["card"] else None})
    # a lesson always needs a board to draw power from / program
    if not any(r["card"] == "arduino-uno" for r in rows):
        rows.append({"guide": "(no microcontroller in the guide)", "name": "Arduino Uno", "quantity": 1, "value": "", "color": "",
                     "card": "arduino-uno", "status": "substitute", "card_name": "Arduino Uno R3",
                     "note": "The Arduino only supplies 5V and GND here — the guide's circuit needs no program."})
    blocked = [r for r in rows if r["status"] == "unsupported"]
    return {"title": analysis["title"], "summary": analysis["summary"], "behaviour": analysis["behaviour"],
            "switch_behaviour": analysis.get("switch_behaviour", "unspecified"),
            "uses_microcontroller": analysis.get("uses_microcontroller", False), "board": analysis.get("board", ""),
            "circuit": analysis.get("circuit", []), "code": analysis.get("code", ""),
            "parts": rows, "blocked": blocked, "ok": not blocked}


def import_guide(url, generate_fn=None, opener=urllib.request.urlopen, library=None):
    title, text = fetch_text(url, opener)
    analysis = analyze(title, text, url, generate_fn)
    return {"url": url, **map_parts(analysis, library)}


# ---------------------------------------------------------------------------
# 5. Generate — with hard requirements, and a check they were met
# ---------------------------------------------------------------------------
def required_counts(plan):
    """library id -> how many components of it the lesson's circuit must have."""
    need = {}
    for r in plan["parts"]:
        if r["status"] in ("exact", "substitute") and r["card"] and r["card"] not in PASSIVE:
            need[r["card"]] = need.get(r["card"], 0) + r["quantity"]
    return need


def requirements_text(plan, library=None):
    library = library or load_library()
    lines = [f"Build a lesson that follows this tutorial EXACTLY: \"{plan['title']}\" ({plan.get('url', '')}).",
             f"What it is: {plan['summary']}", f"What the finished project does: {plan['behaviour']}", "",
             "PARTS — use exactly these components, no more and no fewer, with these values:"]
    for card_id, n in required_counts(plan).items():
        card = library.get(card_id) or {"display_name": card_id}
        extra = ""
        if card.get("wokwi_value"):
            extra = f' (a wokwi-resistor with attrs.value "{card["wokwi_value"]}")'
        colours = sorted({r["color"].lower() for r in plan["parts"] if r["card"] == card_id and r["color"]})
        if colours:
            extra += f" (colour: {', '.join(colours)})"
        lines.append(f"- {n} × `{card_id}` — {card['display_name']}{extra}")
    subs = [r for r in plan["parts"] if r["status"] == "substitute"]
    if subs:
        lines += ["", "The ONLY allowed changes from the guide (we don't have these parts):"]
        lines += [f"- {r['guide']} → `{r['card']}`: {r['note']}" for r in subs]
    if plan["switch_behaviour"] == "latching":
        lines += ["", "The guide's switch is an ON/OFF switch: once switched on, the output must STAY on (a slide switch), not only while a button is held."]
    elif plan["switch_behaviour"] == "momentary":
        lines += ["", "The guide's switch is momentary: the output is on only while the button is held (a pushbutton)."]
    if plan["circuit"]:
        lines += ["", "CIRCUIT — wire it the way the guide does (keep its series/parallel structure):"] + [f"- {c}" for c in plan["circuit"]]
    if plan.get("code"):
        lines += ["", "CODE — keep the guide's sketch, changing only what the sketch rules require (named ...Pin constants, pins that exist on the Uno):", plan["code"]]
    elif not plan.get("uses_microcontroller"):
        lines += ["", "The guide has no microcontroller: the Arduino only supplies 5V and GND; write an empty sketch (empty setup and loop) with a comment saying so."]
    lines += ["", "Do not simplify, merge or drop parts. Every one of the listed components must appear in diagram_json and be wired."]
    return "\n".join(lines)


def check_against_plan(plan, library=None):
    """An extra validator for lesson_gen: the circuit must contain exactly the
    confirmed parts (counts and values)."""
    library = library or load_library()
    need = required_counts(plan)

    def check(data, diagram):
        have = {}
        for part in diagram.get("parts", []):
            cards = library.find_by_wokwi_type(part.get("type"), part.get("attrs", {}).get("value"))
            for c in cards[:1]:
                if c["id"] not in PASSIVE:
                    have[c["id"]] = have.get(c["id"], 0) + 1
        errors = []
        for card_id, n in need.items():
            got = have.get(card_id, 0)
            if got != n:
                name = (library.get(card_id) or {"display_name": card_id})["display_name"]
                errors.append(f"The guide uses {n} × {name}; your circuit has {got}. Use exactly {n}.")
        for card_id, got in have.items():
            if card_id not in need:
                name = (library.get(card_id) or {"display_name": card_id})["display_name"]
                errors.append(f"Your circuit has {got} × {name}, which the guide doesn't use. Remove it.")
        return errors
    return check


def generate(plan, inventory=None, library=None, generate_fn=None, save=True):
    """lesson_gen with the guide's requirements, its check, and where it came from."""
    library = library or load_library()
    if plan.get("blocked"):
        names = ", ".join(r["name"] for r in plan["blocked"])
        return {"ok": False, "lesson_id": None, "attempts": [], "errors": [f"This guide needs parts CircuitQuest can't simulate yet: {names}."]}
    extra = {"source": {"url": plan.get("url", ""), "title": plan["title"]},
             "substitutions": [{"guide": r["guide"], "used": r["card_name"] or r["card"], "why": r["note"]}
                               for r in plan["parts"] if r["status"] == "substitute"]}
    return lesson_gen.generate_lesson(requirements_text(plan, library), inventory=inventory, library=library,
                                      generate_fn=generate_fn, save=save,
                                      extra_check=check_against_plan(plan, library), extra_data=extra)
