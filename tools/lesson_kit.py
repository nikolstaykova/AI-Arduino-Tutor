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
NAME = {"resistor-220": "220 Ω resistor", "resistor-10k": "10 kΩ resistor", "led": "LED", "pushbutton": "pushbutton",
        "potentiometer-10k": "10 kΩ potentiometer (knob)", "buzzer": "piezo buzzer"}


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

    def _rail(self, which):
        """Words for reaching the + / − row. The first step that uses a row also
        wires that row to the Arduino (a rail on its own joins no parts, so it
        can't be a step by itself)."""
        if which == "gnd":
            if getattr(self, "_gnd_done", False):
                return "the − (blue) row"
            self._gnd_done = True
            self._wire("bb1:bn.1", "uno:GND.1", "black")          # only once something uses the − row
            return ("the − (blue) row along the bottom edge — and, since this is the first thing using it, one more wire from "
                    "that − row to a GND pin on the Arduino (now the whole row is GND)")
        if getattr(self, "_5v_done", False):
            return "the + (red) row"
        self._5v_done = True
        self._wire("uno:5V", "bb1:bp.1", "red")                 # only once something uses the + row
        return ("the + (red) row along the bottom edge — and, since this is the first thing using it, one more wire from that "
                "+ row to the 5V pin on the Arduino (now the whole row is 5V)")

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
        self._step(f"{d}-resistor", f"Push a 220 Ω resistor into the breadboard, its two legs in two different numbered columns"
                   f"{' (leave some space from the last part)' if c > 1 else ''}.", f"Put the resistor for {what} on the breadboard.",
                   ["A resistor works either way round.", "It protects the LED: without it too much current flows and the LED burns out."],
                   landing=f"{r}:1")
        self._step(f"{d}-pin", f"A jumper wire from one of the resistor's columns to pin {pin} on the Arduino.",
                   f"Connect the resistor to pin {pin}.",
                   [f"Pin {pin} is on the Arduino's row of numbered sockets.{exact}", "Any free hole in that column works."],
                   nets=[[f"{r}:1", f"uno:{pin}"]])
        self._step(f"{d}-legs", f"Now {what}: its long leg in the same column as the resistor's other leg, its short leg in an "
                   "empty column right next to it.", f"Connect {what}'s long leg (+) to the resistor.",
                   ["The long leg is + (the anode) — it must face the resistor or the LED stays dark.",
                    "Legs in the same column are already connected."], nets=[[f"{d}:A", f"{r}:2"]])
        self._step(f"{d}-gnd", f"A jumper wire from the short leg's column to {self._rail('gnd')}.",
                   f"Connect {what}'s short leg (−) to GND.",
                   ["The short leg is − (the cathode).", "The − row is already joined to GND."], nets=[[f"{d}:C", "uno:GND.1"]])
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
        self._step(f"{b}-place", "Push the button into the breadboard so it sits across the middle gap: two legs above the gap, "
                   "two below.", "Put the button across the middle gap.",
                   ["The two legs in the same column — one above the gap, one below — are always connected inside the button.",
                    "Pressing the button connects its left column to its right column."], landing=[f"{b}:1.r", f"{b}:2.r"])
        self._step(f"{b}-pin", f"A jumper wire from the top half of the button's left column to pin {pin} on the Arduino.",
                   f"Connect one side of the button to pin {pin}.",
                   [f"Pin {pin} is on the Arduino's row of numbered sockets.", "Any free hole in that column works."],
                   nets=[[f"{b}:1.r", f"uno:{pin}"]])
        self._wire(f"bb1:{c}t.a", f"uno:{pin}", "orange")
        if pulldown:
            r = self._id("r")
            self._part("wokwi-resistor", r, {"value": "10000"}); self._need("resistor-10k")
            self._wire(f"bb1:{c + 2}b.j", f"bb1:bp.{c + 2}", "red")
            self._wire(f"{r}:1", f"bb1:{c}b.h"); self._wire(f"{r}:2", f"bb1:{c + 4}b.h")
            self._wire(f"bb1:{c + 4}b.j", f"bb1:bn.{c + 4}", "black")
            self._step(f"{b}-5v", f"A jumper wire from the button's right column (bottom half) to {self._rail('5v')}.",
                       "Connect the other side of the button to 5V.",
                       ["When you press, 5V flows through the button to the pin.", "The + row is already 5V."],
                       nets=[[f"{b}:2.r", "uno:5V"]])
            self._step(f"{b}-pulldown", "Now a 10 kΩ resistor: one leg in the button's left column (bottom half), the other leg in "
                       "an empty column.", "Put a 10 kΩ resistor on the button's pin side.",
                       ["This is a pull-down: it keeps the pin at 0 (LOW) while the button isn't pressed.",
                        "Without it the pin 'floats' and reads random values."], nets=[[f"{r}:1", f"{b}:1.r"]])
            self._step(f"{b}-pulldown-gnd", f"A jumper wire from the resistor's other column to {self._rail('gnd')}.",
                       "Connect the pull-down resistor to GND.",
                       ["The − row is GND.", "Now the pin reads LOW, and HIGH only while you press."], nets=[[f"{r}:2", "uno:GND.1"]])
            self.nets += [[f"{b}:1.r", f"uno:{pin}"], [f"{b}:2.r", "uno:5V"], [f"{r}:1", f"{b}:1.r"], [f"{r}:2", "uno:GND.1"]]
        else:
            self._wire(f"bb1:{c + 2}b.j", f"bb1:bn.{c + 2}", "black")
            self._step(f"{b}-gnd", f"A jumper wire from the button's right column (bottom half) to {self._rail('gnd')}.",
                       "Connect the other side of the button to GND.",
                       ["The Arduino's own pull-up keeps the pin HIGH; pressing connects it to GND, so it reads LOW.",
                        "No resistor needed — INPUT_PULLUP turns on the one inside the chip."], nets=[[f"{b}:2.r", "uno:GND.1"]])
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
        self._step(f"{p}-place", "Push the knob into the breadboard so each of its three legs is in a different numbered column.",
                   "Put the knob on the breadboard.",
                   ["The two outer legs are for power; the middle leg gives the reading.",
                    "Two legs in the same column would be joined, so use three different columns."],
                   landing=[f"{p}:GND", f"{p}:SIG", f"{p}:VCC"])
        self._step(f"{p}-gnd", f"A jumper wire from one outer leg's column to {self._rail('gnd')}.", "Connect one outer leg to GND.",
                   ["Either outer leg works — swapping them only reverses which way is 'more'."], nets=[[f"{p}:GND", "uno:GND.1"]])
        self._step(f"{p}-5v", f"A jumper wire from the other outer leg's column to {self._rail('5v')}.", "Connect the other outer leg to 5V.",
                   ["Now the knob has 0 V at one end and 5 V at the other."], nets=[[f"{p}:VCC", "uno:5V"]])
        self._step(f"{p}-pin", f"A jumper wire from the middle leg's column to pin {pin} on the Arduino.",
                   f"Connect the knob's middle leg to {pin}.",
                   [f"{pin} is on the Arduino's ANALOG IN header.", "The middle leg's voltage follows the knob: 0 V to 5 V."],
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
        self._step(f"{z}-place", "Push the buzzer into the breadboard, its two legs in two different columns.", "Put the buzzer on the breadboard.",
                   ["The + leg is marked on the top (and is usually longer).", "It only works one way round."], landing=[f"{z}:1", f"{z}:2"])
        self._step(f"{z}-pin", f"A jumper wire from the + leg's column to pin {pin} on the Arduino.", f"Connect the buzzer's + leg to pin {pin}.",
                   ["tone() on this pin makes the buzzer sing."], nets=[[f"{z}:2", f"uno:{pin}"]])
        self._step(f"{z}-gnd", f"A jumper wire from the other leg's column to {self._rail('gnd')}.", "Connect the buzzer's − leg to GND.",
                   ["The − row is GND."], nets=[[f"{z}:1", "uno:GND.1"]])
        self.nets += [[f"{z}:2", f"uno:{pin}"], [f"{z}:1", "uno:GND.1"]]
        return z

    # ---- writing ---------------------------------------------------------------------------
    def upload(self, note):
        self.upload_note = note

    def write(self):
        names = ", ".join(NAME.get(i, i) for i in self.items if i not in ("arduino-uno", "usb-cable", "breadboard", "jumper-wire"))
        gather = {"id": "gather", "phase": "gather",
                  "clip": f"Grab an Arduino Uno and its USB cable, a breadboard, {names} and a few jumper wires.",
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
