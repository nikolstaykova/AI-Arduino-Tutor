"""Lesson kit: write a breadboard lesson from a compact description.

A lesson is built from circuit blocks — an LED on a pin, a button with a
pull-down, a button to GND, a knob on an analog pin, a buzzer on a pin. Each
block lays itself out on the breadboard (its own columns), adds its wires to
the Wokwi diagram, and writes its own beginner steps (clip / goal / hints);
the lesson gets the official sketch. Everything it writes must then pass
core/lesson_gen.validate — the same checks as every other lesson.

    python3 tools/lesson_kit.py            # (re)write every lesson in tools/lessons_spec.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CARD = {"led": "led", "r220": "resistor-220", "r10k": "resistor-10k", "button": "pushbutton", "pot": "potentiometer-10k",
        "buzzer": "buzzer"}
SINGULAR = {"resistor-220": "220 Ω resistor", "resistor-10k": "10 kΩ resistor", "resistor-4k7": "4.7 kΩ resistor", "led": "LED",
            "pushbutton": "pushbutton", "potentiometer-10k": "knob (10 kΩ potentiometer)", "buzzer": "piezo buzzer",
            "photoresistor": "light sensor (photoresistor)", "fsr": "force sensor (FSR)"}
NAME = {"resistor-220": "220 Ω resistors", "resistor-10k": "10 kΩ resistors", "resistor-4k7": "a 4.7 kΩ resistor", "led": "LEDs",
        "pushbutton": "a pushbutton", "potentiometer-10k": "a knob (10 kΩ potentiometer)", "buzzer": "a piezo buzzer",
        "photoresistor": "a light sensor (photoresistor)", "fsr": "force sensors (FSR)"}


class Lesson:
    def __init__(self, lid, title, description, source_url, source_title, code, *, requires=(), full_board=False, difficulty="beginner",
                 fixed_pins=False):
        self.id, self.title, self.description = lid, title, description
        self.source = {"url": source_url, "title": f"Arduino docs: {source_title}"}
        self.code, self.requires, self.difficulty = code, list(requires), difficulty
        self.bb = "wokwi-breadboard" if full_board else "wokwi-breadboard-half"
        self.parts = [{"type": self.bb, "id": "bb1", "top": 73.8, "left": 156.4, "attrs": {}},
                      {"type": "wokwi-arduino-uno", "id": "uno", "top": 19.8, "left": -231, "attrs": {}}]
        self.conns, self.steps, self.nets, self.items = [], [], [], ["arduino-uno", "usb-cable", "breadboard"]
        self.col = 1                     # next free breadboard column (bottom half)
        self.counts = {}
        self.rails = False
        self.upload_note = ""
        self.fixed_pins = fixed_pins

    # ---- helpers --------------------------------------------------------------------------
    def _id(self, prefix):
        self.counts[prefix] = self.counts.get(prefix, 0) + 1
        return f"{prefix}{self.counts[prefix]}"

    def _part(self, wtype, pid, attrs=None):
        self.parts.append({"type": wtype, "id": pid, "top": 0, "left": 60 * len(self.parts), "attrs": attrs or {}})

    def _wire(self, a, b, colour="green"):
        self.conns.append([a, b, colour, ["v0"]])

    def _need(self, card_id):
        if card_id not in self.items:
            self.items.append(card_id)

    def _step(self, sid, clip, goal, hints, *, nets=None, landing=None):
        s = {"id": sid, "phase": "build", "clip": clip}
        if landing is not None:
            s["expected_landing"] = landing
        if nets is not None:
            s["expected_nets"] = nets
        s.update({"strict": False, "hints": hints, "goal": goal})
        self.steps.append(s)

    def power_rails(self):
        """5V and GND to the breadboard's long edge rows — every block then uses them."""
        if self.rails:
            return
        self.rails = True
        self._need("jumper-wire")

    def _to_rail(self, which, what):
        """The clip for wiring `what` to the + or − row. The first time a row is
        used it also needs its own wire to the Arduino — written as two short
        numbered lines, not one long sentence."""
        row = "blue − row" if which == "gnd" else "red + row"
        pin = "GND" if which == "gnd" else "5V"
        flag = "_gnd_done" if which == "gnd" else "_5v_done"
        if getattr(self, flag, False):
            return f"Run a wire from {what} to the {row}."
        setattr(self, flag, True)
        self._wire("bb1:bn.1", "uno:GND.1", "black") if which == "gnd" else self._wire("uno:5V", "bb1:bp.1", "red")
        return (f"Two wires:<br>1. The Arduino's <b>{pin}</b> pin → the {row} at the bottom of the breadboard.<br>"
                f"2. {what[0].upper() + what[1:]} → that same row.")

    # ---- circuit blocks ---------------------------------------------------------------------
    def led(self, pin, color="red", label=None):
        """An LED on `pin` through a 220 Ω resistor, cathode to the GND row."""
        self.power_rails()
        c = self.col; self.col += 6
        r, d = self._id("r"), self._id("led")
        self._part("wokwi-resistor", r, {"value": "220"}); self._part("wokwi-led", d, {"color": color})
        self._need("resistor-220"); self._need("led")
        self._wire(f"{r}:1", f"bb1:{c}b.h"); self._wire(f"{r}:2", f"bb1:{c + 4}b.h")
        self._wire(f"bb1:{c}b.g", f"uno:{pin}", "orange")
        self._wire(f"{d}:A", f"bb1:{c + 4}b.i"); self._wire(f"{d}:C", f"bb1:{c + 3}b.i")
        self._wire(f"bb1:{c + 3}b.j", f"bb1:bn.{c + 3}", "black")
        what = label or (f"the {color} LED" if color != "red" else "the LED")
        exact = " Use exactly this pin — the code counts through the pins in order." if self.fixed_pins else ""
        self._step(f"{d}-resistor", "Push a 220 Ω resistor into the breadboard. Put its two legs in two different columns.",
                   f"Put the resistor for {what} on the breadboard.",
                   ["A resistor works either way round.", "It protects the LED — without it the LED can burn out."], landing=f"{r}:1")
        self._step(f"{d}-pin", f"Run a wire from one leg of the 220 Ω resistor to pin <b>{pin}</b> on the Arduino.",
                   f"Connect the resistor to pin {pin}.",
                   [f"Put the wire in any hole in the same column as the leg.{exact}", f"Pin {pin} is on the Arduino's row of numbered sockets."],
                   nets=[[f"{r}:1", f"uno:{pin}"]])
        self._step(f"{d}-legs", f"Put {what} in: the <b>long</b> leg in the same column as the 220 Ω resistor's other leg, the <b>short</b> leg "
                   "in the next column.", f"Connect {what}'s long leg (+) to the resistor.",
                   ["The long leg is + (the anode). Backwards, the LED stays dark.", "Legs in the same column are connected — no wire needed."],
                   nets=[[f"{d}:A", f"{r}:2"]])
        self._step(f"{d}-gnd", self._to_rail("gnd", f"{what}'s short leg"), f"Connect {what}'s short leg (−) to GND.",
                   ["The short leg is − (the cathode).", "GND is the minus side of the circuit."], nets=[[f"{d}:C", "uno:GND.1"]])
        self.nets += [[f"{r}:1", f"uno:{pin}"], [f"{d}:A", f"{r}:2"], [f"{d}:C", "uno:GND.1"]]
        return d

    def button(self, pin, pulldown=True):
        """A pushbutton across the gap. pulldown: 5V on one side, the pin + a 10 kΩ
        pull-down to GND on the other. Otherwise (INPUT_PULLUP): pin and GND."""
        self.power_rails()
        c = self.col; self.col += 7 if pulldown else 4
        b = self._id("btn")
        self._part("wokwi-pushbutton", b, {"color": "green"}); self._need("pushbutton")
        self._wire(f"{b}:1.l", f"bb1:{c}t.e"); self._wire(f"{b}:1.r", f"bb1:{c}b.f")
        self._wire(f"{b}:2.l", f"bb1:{c + 2}t.e"); self._wire(f"{b}:2.r", f"bb1:{c + 2}b.f")
        self._step(f"{b}-place", "Push the button in across the middle gap: two legs above the gap, two below.",
                   "Put the button across the middle gap.",
                   ["The two legs in one column (above and below the gap) are always joined inside the button.",
                    "Pressing joins the left column to the right column."], landing=[f"{b}:1.r", f"{b}:2.r"])
        self._step(f"{b}-pin", f"Run a wire from the button's <b>left</b> column (top half) to pin <b>{pin}</b> on the Arduino.",
                   f"Connect one side of the button to pin {pin}.",
                   ["Any hole in that column works.", f"Pin {pin} is on the Arduino's row of numbered sockets."],
                   nets=[[f"{b}:1.r", f"uno:{pin}"]])
        self._wire(f"bb1:{c}t.a", f"uno:{pin}", "orange")
        if pulldown:
            r = self._id("r")
            self._part("wokwi-resistor", r, {"value": "10000"}); self._need("resistor-10k")
            self._wire(f"bb1:{c + 2}b.j", f"bb1:bp.{c + 2}", "red")
            self._wire(f"{r}:1", f"bb1:{c}b.h"); self._wire(f"{r}:2", f"bb1:{c + 4}b.h")
            self._wire(f"bb1:{c + 4}b.j", f"bb1:bn.{c + 4}", "black")
            self._step(f"{b}-5v", self._to_rail("5v", "the button's right column (bottom half)"), "Connect the other side of the button to 5V.",
                       ["When you press, 5V flows through the button to the pin."], nets=[[f"{b}:2.r", "uno:5V"]])
            self._step(f"{b}-pulldown", "Push a 10 kΩ resistor in: one leg in the button's <b>left</b> column (bottom half), the other leg "
                       "in an empty column.", "Put a 10 kΩ resistor on the button's pin side.",
                       ["This is a pull-down: it keeps the pin LOW until you press.", "Without it the pin 'floats' and reads random values."],
                       nets=[[f"{r}:1", f"{b}:1.r"]])
            self._step(f"{b}-pulldown-gnd", self._to_rail("gnd", "the 10 kΩ resistor's other leg"), "Connect the pull-down resistor to GND.",
                       ["Now the pin reads LOW, and HIGH only while you press."], nets=[[f"{r}:2", "uno:GND.1"]])
            self.nets += [[f"{b}:1.r", f"uno:{pin}"], [f"{b}:2.r", "uno:5V"], [f"{r}:1", f"{b}:1.r"], [f"{r}:2", "uno:GND.1"]]
        else:
            self._wire(f"bb1:{c + 2}b.j", f"bb1:bn.{c + 2}", "black")
            self._step(f"{b}-gnd", self._to_rail("gnd", "the button's right column (bottom half)"), "Connect the other side of the button to GND.",
                       ["No resistor needed: INPUT_PULLUP turns on one inside the chip.", "So the pin reads HIGH, and LOW while you press."],
                       nets=[[f"{b}:2.r", "uno:GND.1"]])
            self.nets += [[f"{b}:1.r", f"uno:{pin}"], [f"{b}:2.r", "uno:GND.1"]]
        return b

    def pot(self, pin):
        """A knob: outer legs to the rails, the middle (wiper) to an analog pin."""
        self.power_rails()
        c = self.col; self.col += 4
        p = self._id("pot")
        self._part("wokwi-potentiometer", p); self._need("potentiometer-10k")
        self._wire(f"bb1:{c}b.f", f"{p}:GND"); self._wire(f"bb1:{c + 1}b.f", f"{p}:SIG"); self._wire(f"bb1:{c + 2}b.f", f"{p}:VCC")
        self._wire(f"bb1:{c}b.j", f"bb1:bn.{c}", "black"); self._wire(f"bb1:{c + 2}b.j", f"bb1:bp.{c + 2}", "red")
        self._wire(f"bb1:{c + 1}b.h", f"uno:{pin}", "orange")
        self._step(f"{p}-place", "Push the knob into the breadboard, each of its three legs in its own column.", "Put the knob on the breadboard.",
                   ["The two outer legs are for power; the middle leg gives the reading."], landing=[f"{p}:GND", f"{p}:SIG", f"{p}:VCC"])
        self._step(f"{p}-gnd", self._to_rail("gnd", "one outer leg of the knob"), "Connect one outer leg to GND.",
                   ["Either outer leg works."], nets=[[f"{p}:GND", "uno:GND.1"]])
        self._step(f"{p}-5v", self._to_rail("5v", "the knob's other outer leg"), "Connect the other outer leg to 5V.",
                   ["Now the knob has 0 V at one end and 5 V at the other."], nets=[[f"{p}:VCC", "uno:5V"]])
        self._step(f"{p}-pin", f"Run a wire from the knob's <b>middle</b> leg to pin <b>{pin}</b> on the Arduino.",
                   f"Connect the knob's middle leg to {pin}.",
                   [f"{pin} is on the ANALOG IN side of the Arduino.", "The middle leg's voltage follows the knob: 0 V to 5 V."],
                   nets=[[f"{p}:SIG", f"uno:{pin}"]])
        self.nets += [[f"{p}:GND", "uno:GND.1"], [f"{p}:VCC", "uno:5V"], [f"{p}:SIG", f"uno:{pin}"]]
        return p

    def buzzer(self, pin):
        """A piezo buzzer: + to the pin, − to the GND row."""
        self.power_rails()
        c = self.col; self.col += 5
        z = self._id("bz")
        self._part("wokwi-buzzer", z); self._need("buzzer")
        self._wire(f"{z}:1", f"bb1:{c}b.f"); self._wire(f"{z}:2", f"bb1:{c + 3}b.f")
        self._wire(f"bb1:{c}b.j", f"bb1:bn.{c}", "black"); self._wire(f"bb1:{c + 3}b.j", f"uno:{pin}", "orange")
        self._step(f"{z}-place", "Push the buzzer in, its two legs in two different columns.", "Put the buzzer on the breadboard.",
                   ["The + leg is marked on top (and is usually longer).", "It only works one way round."], landing=[f"{z}:1", f"{z}:2"])
        self._step(f"{z}-pin", f"Run a wire from the buzzer's <b>+</b> leg to pin <b>{pin}</b> on the Arduino.", f"Connect the buzzer's + leg to pin {pin}.",
                   ["tone() on this pin makes the buzzer sing."], nets=[[f"{z}:2", f"uno:{pin}"]])
        self._step(f"{z}-gnd", self._to_rail("gnd", "the buzzer's other leg"), "Connect the buzzer's − leg to GND.",
                   ["GND is the minus side of the circuit."], nets=[[f"{z}:1", "uno:GND.1"]])
        self.nets += [[f"{z}:2", f"uno:{pin}"], [f"{z}:1", "uno:GND.1"]]
        return z

    def sensor(self, kind, pin, ohms=10000):
        """A two-legged resistive sensor in a voltage divider: one leg to 5V, the
        other to an analog pin and through a fixed resistor to GND.
        kind: "ldr" (photoresistor) or "fsr" (force-sensitive resistor)."""
        self.power_rails()
        c = self.col; self.col += 8
        wtype, card, word, prefix = {"ldr": ("cq-photoresistor", "photoresistor", "light sensor", "ldr"),
                                     "fsr": ("cq-fsr", "fsr", "force sensor", "fsr")}[kind]
        rcard, rtext = {10000: ("resistor-10k", "10 kΩ"), 4700: ("resistor-4k7", "4.7 kΩ")}[ohms]
        sid, r = self._id(prefix), self._id("r")
        self._part(wtype, sid); self._part("wokwi-resistor", r, {"value": str(ohms)})
        self._need(card); self._need(rcard)
        self._wire(f"{sid}:1", f"bb1:{c}b.f"); self._wire(f"{sid}:2", f"bb1:{c + 2}b.f")
        self._wire(f"bb1:{c}b.j", f"bb1:bp.{c}", "red")
        self._wire(f"bb1:{c + 2}b.i", f"uno:{pin}", "orange")
        self._wire(f"{r}:1", f"bb1:{c + 2}b.h"); self._wire(f"{r}:2", f"bb1:{c + 6}b.h")
        self._wire(f"bb1:{c + 6}b.j", f"bb1:bn.{c + 6}", "black")
        self._step(f"{sid}-place", f"Push the {word} in, its two legs in two different columns.", f"Put the {word} on the breadboard.",
                   ["It works either way round."], landing=[f"{sid}:1", f"{sid}:2"])
        self._step(f"{sid}-5v", self._to_rail("5v", f"the {word}'s first leg"), f"Connect one leg of the {word} to 5V.",
                   ["Either leg works."], nets=[[f"{sid}:1", "uno:5V"]])
        self._step(f"{sid}-pin", f"Run a wire from the {word}'s <b>other</b> leg to pin <b>{pin}</b> on the Arduino.",
                   f"Connect the {word}'s other leg to {pin}.", [f"{pin} is on the ANALOG IN side of the Arduino."],
                   nets=[[f"{sid}:2", f"uno:{pin}"]])
        self._step(f"{sid}-resistor", f"Push a {rtext} resistor in: one leg in that same column (the {word}'s other leg), the other "
                   "leg in an empty column.", f"Put a {rtext} resistor on the {word}'s pin side.",
                   [f"The {word} and this resistor share the 5 V between them — so the pin's voltage changes as the {word} does."],
                   nets=[[f"{r}:1", f"{sid}:2"]])
        self._step(f"{sid}-gnd", self._to_rail("gnd", f"the {rtext} resistor's other leg"), "Connect the resistor to GND.",
                   ["Now the reading goes up when the " + ("light gets brighter." if kind == "ldr" else "pad is pressed.")],
                   nets=[[f"{r}:2", "uno:GND.1"]])
        self.nets += [[f"{sid}:1", "uno:5V"], [f"{sid}:2", f"uno:{pin}"], [f"{r}:1", f"{sid}:2"], [f"{r}:2", "uno:GND.1"]]
        return sid

    # ---- writing ---------------------------------------------------------------------------
    def upload(self, note):
        self.upload_note = note

    def write(self):
        # how many of each part, from the diagram ("6 LEDs", "1 knob")
        card_of = {"wokwi-led": "led", "wokwi-pushbutton": "pushbutton", "wokwi-potentiometer": "potentiometer-10k", "wokwi-buzzer": "buzzer",
                   "cq-photoresistor": "photoresistor", "cq-fsr": "fsr"}
        count = {}
        for part in self.parts:
            cid = card_of.get(part["type"]) or ({"220": "resistor-220", "10000": "resistor-10k", "4700": "resistor-4k7"}.get(part["attrs"].get("value"))
                                                  if part["type"] == "wokwi-resistor" else None)
            if cid:
                count[cid] = count.get(cid, 0) + 1
        names = ", ".join(f"{n} × {SINGULAR.get(i, i)}" for i, n in count.items())
        gather = {"id": "gather", "phase": "gather",
                  "clip": f"You need: an Arduino Uno and its USB cable, a breadboard, {names}, and some jumper wires.",
                  "items": self.items + (["jumper-wire"] if "jumper-wire" not in self.items else [])}
        steps = [gather] + self.steps + [{"id": "upload-code", "phase": "upload",
                                          "clip": "Copy the code into the Arduino IDE and click Upload. " + self.upload_note, "code": "code.ino"}]
        lesson = {"id": self.id, "title": self.title, "description": self.description, "source": self.source,
                  "difficulty": self.difficulty, "board": "arduino-uno", "requires": self.requires,
                  "code": "code.ino", "wokwi_diagram": "diagram.json", "tools_used": [],
                  "parts_used": gather["items"], "steps": steps, "final_check": {"expected_nets": self.nets}}
        if self.fixed_pins:
            lesson["fixed_pins"] = True
        diagram = {"version": 1, "author": "CircuitQuest (from the Arduino built-in examples)", "editor": "wokwi",
                   "parts": self.parts, "connections": self.conns, "dependencies": {}}
        folder = ROOT / "lessons" / self.id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "lesson.json").write_text(json.dumps(lesson, indent=2, ensure_ascii=False) + "\n")
        (folder / "diagram.json").write_text(json.dumps(diagram, indent=2) + "\n")
        (folder / "code.ino").write_text(self.code.strip() + "\n")
        return lesson, diagram


def validate(lid, mode="smart"):
    import os
    os.environ["CQ_FLOW_CHECK"] = mode
    from core import lesson_gen
    folder = ROOT / "lessons" / lid
    return lesson_gen.validate(json.loads((folder / "lesson.json").read_text()), json.loads((folder / "diagram.json").read_text()),
                               (folder / "code.ino").read_text())


if __name__ == "__main__":
    from tools.lessons_spec import LESSONS
    bad = 0
    for make in LESSONS:
        lesson = make()
        lesson.write()
        errs = validate(lesson.id)
        print(("OK  " if not errs else "FAIL") + f" {lesson.id}" + ("" if not errs else "\n   - " + "\n   - ".join(e[:240] for e in errs[:4])))
        bad += bool(errs)
    sys.exit(1 if bad else 0)
