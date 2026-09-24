"""Does a lesson like this already exist? Checked before spending Claude on
a new one.

Two signals, both deterministic:
  - the tutorial link: every lesson records the tutorial it follows
    (`source.url`); the same page (ignoring http/https, www, a trailing
    slash, ?query and #fragment) is a match;
  - the words: the request against each lesson's title (and description),
    after dropping filler words ("a", "with", "make", "led" stays).

The learner decides: a match is only a suggestion ("this might be the same
— want to check it out?"), they can still create a new one.
"""
import re
import urllib.parse

STOP = set("""a an the and or of to for with without in on at by from my me i we you it its is are be this that
make build create want wanna would like please can could lesson level project tutorial circuit simple small little
using use uses arduino uno how do does""".split())

# a couple of everyday synonyms so rewordings still meet
SYNONYMS = {"stoplight": ("traffic", "light"), "stoplights": ("traffic", "light"), "lights": "light", "leds": "led", "blinking": "blink",
            "blinks": "blink", "flashing": "blink", "flash": "blink", "buttons": "button", "pushbutton": "button",
            "knob": "potentiometer", "pot": "potentiometer", "fade": "fade", "fading": "fade", "flashlight": "flashlight",
            "torch": "flashlight", "buzzer": "buzzer", "beeper": "buzzer", "piezo": "buzzer", "sensor": "sensor"}


def norm_url(url):
    if not url:
        return None
    p = urllib.parse.urlsplit(url.strip())
    host = p.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", p.path).lower()
    return host + path if host else None


# words too common to identify a project on their own ("an LED" alone isn't a match)
GENERIC = {"led", "light", "resistor", "button", "sensor", "wire", "power", "usb", "one", "two", "three", "four", "five",
           "red", "green", "blue", "yellow", "on", "off", "input", "output", "read", "serial", "digital", "analog"}


def words(text):
    out = set()
    for w in re.findall(r"[a-z0-9]+", (text or "").lower()):
        w = SYNONYMS.get(w, w)
        for x in (w if isinstance(w, tuple) else (w,)):
            if len(x) > 1 and x not in STOP:
                out.add(x)
    return out


def find_similar(request, lessons, url=None, limit=3):
    """lessons: [{"id", "title", "description", "source": {"url"}}] → the best
    matches, most likely first: [{"id", "title", "why", "score"}]."""
    target = norm_url(url) or norm_url((re.findall(r"https?://\S+", request or "") or [None])[0])
    req = words(re.sub(r"https?://\S+", " ", request or ""))
    found = []
    for l in lessons:
        src = norm_url((l.get("source") or {}).get("url"))
        if target and src and src == target:
            found.append({"id": l["id"], "title": l.get("title", l["id"]), "why": "It follows the same tutorial link.", "score": 1.0})
            continue
        if not req:
            continue
        title = words(l.get("title")) or words(l["id"])
        desc = words(l.get("description"))
        if not title:
            continue
        shared = title & req
        if not shared - GENERIC:
            continue                                        # only common words in common
        in_title = len(shared) / len(title)                 # how much of the lesson's name the request covers
        covered = len(req & (title | desc)) / len(req)      # how much of the request the lesson is about
        extra = 1 - covered
        score = max(in_title * (1 - 0.5 * extra), 0.7 * covered if covered == 1 else 0)
        if score >= 0.45:
            found.append({"id": l["id"], "title": l.get("title", l["id"]), "score": round(score, 2),
                          "why": f"Same words: {', '.join(sorted(shared))}."})
    found.sort(key=lambda m: -m["score"])
    return found[:limit]
