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
            "photoresistor": "light sensor (photoresistor)", "fsr": "force sensor (FSR)", "resistor-1m": "1 MΩ resistor",
            "ping-sensor": "Ping))) ultrasonic sensor", "adxl335": "ADXL335 accelerometer", "memsic2125": "Memsic 2125 accelerometer", "rgb-led": "RGB LED (common anode)",
            "led-bar-graph": "10-segment LED bar graph", "led-matrix-8x8": "8×8 LED matrix", "midi-jack": "MIDI socket (5-pin DIN)", "analog-joystick": "analog joystick module",
            "atmega328p": "ATmega328P chip", "crystal-16mhz": "16 MHz crystal", "capacitor-22pf": "22 pF capacitor", "capacitor-10uf": "10 µF capacitor"}
NAME = {"resistor-220": "220 Ω resistors", "resistor-10k": "10 kΩ resistors", "resistor-4k7": "a 4.7 kΩ resistor", "led": "LEDs",
        "pushbutton": "a pushbutton", "potentiometer-10k": "a knob (10 kΩ potentiometer)", "buzzer": "a piezo buzzer",
        "photoresistor": "a light sensor (photoresistor)", "fsr": "force sensors (FSR)"}


# pin layouts of the bench parts (same as bench/three/models.js PART_PINS): name, column offset, row offset (3 = across the gap)
PIN_LAYOUT = {
    "wokwi-analog-joystick": [("VCC", 0, 0), ("VERT", 1, 0), ("HORZ", 2, 0), ("SEL", 3, 0), ("GND", 4, 0)],
    "cq-ping": [("GND", 0, 0), ("5V", 1, 0), ("SIG", 2, 0)],
    "cq-adxl335": [("ST", 0, 0), ("Z", 1, 0), ("Y", 2, 0), ("X", 3, 0), ("GND", 4, 0), ("VCC", 5, 0)],
    "cq-memsic2125": [("TOUT", 0, 0), ("YOUT", 1, 0), ("GND.1", 2, 0), ("VDD", 0, 3), ("XOUT", 1, 3), ("GND.2", 2, 3)],
    # DIP-28: pins 1–14 left to right along the bottom row, 15–28 right to left along the top
    "cq-atmega328p": [(str(k + 1), k, 3) for k in range(14)] + [(str(k + 15), 13 - k, 0) for k in range(14)],
    "cq-crystal": [("1", 0, 0), ("2", 1, 0)],
    "cq-capacitor-ceramic": [("1", 0, 0), ("2", 2, 0)],
    "cq-capacitor-electrolytic": [("POS", 0, 0), ("NEG", 1, 0)],
}


ORD = {2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth"}


class Lesson:
    def __init__(self, lid, title, description, source_url, source_title, code, *, requires=(), full_board=False, difficulty="beginner",
                 fixed_pins=False, board="uno", board_type="wokwi-arduino-uno", board_card="arduino-uno", board_name="Arduino Uno"):
        self.id, self.title, self.description = lid, title, description
        self.source = {"url": source_url, "title": f"Arduino docs: {source_title}"}
        self.code, self.requires, self.difficulty = code, list(requires), difficulty
        self.bb = "wokwi-breadboard" if full_board else "wokwi-breadboard-half"
        self.board, self.board_type, self.board_card, self.board_name = board, board_type, board_card, board_name
        self.parts = [{"type": self.bb, "id": "bb1", "top": 73.8, "left": 156.4, "attrs": {}},
                      {"type": board_type, "id": board, "top": 19.8, "left": -231, "attrs": {}}]
        self.conns, self.steps, self.nets, self.items = [], [], [], [board_card, "usb-cable", "breadboard"]
        self.col = 1                     # next free breadboard column (bottom half)
        self.counts = {}
        self.rails = False
        self.upload_note = ""
        self.fixed_pins = fixed_pins

    # ---- helpers --------------------------------------------------------------------------
    def _id(self, prefix):
        self.counts[prefix] = self.counts.get(prefix, 0) + 1
        return f"{prefix}{self.counts[prefix]}"

    def _nth(self, prefix, word):
        """"the knob" for the first one, "the second knob" once there are more."""
        n = self.counts.get(prefix, 1)
        return f"the {word}" if n == 1 else f"the {ORD.get(n, str(n) + 'th')} {word}"

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
        self._wire("bb1:bn.1", f"{self.board}:GND.1", "black") if which == "gnd" else self._wire(f"{self.board}:5V", "bb1:bp.1", "red")
        return (f"Two wires:<br>1. The Arduino's <b>{pin}</b> pin → the {row} at the bottom of the breadboard.<br>"
                f"2. {what[0].upper() + what[1:]} → that same row.")

    # ---- circuit blocks ---------------------------------------------------------------------
    def led(self, pin, color="red", label=None, compact=False):
        """An LED on `pin` through a 220 Ω resistor, cathode to the GND row.
        compact: 5 columns instead of 6 (twelve LEDs fit on a full breadboard)."""
        self.power_rails()
        c = self.col; self.col += 5 if compact else 6
        r, d = self._id("r"), self._id("led")
        self._part("wokwi-resistor", r, {"value": "220"}); self._part("wokwi-led", d, {"color": color})
        self._need("resistor-220"); self._need("led")
        self._wire(f"{r}:1", f"bb1:{c}b.h"); self._wire(f"{r}:2", f"bb1:{c + 4}b.h")
        self._wire(f"bb1:{c}b.g", f"{self.board}:{pin}", "orange")
        self._wire(f"{d}:A", f"bb1:{c + 4}b.i"); self._wire(f"{d}:C", f"bb1:{c + 3}b.i")
        self._wire(f"bb1:{c + 3}b.j", f"bb1:bn.{self._rail_n(c + 3)}", "black")
        what = label or (self._nth("led", "LED") if color == "red" or self.counts["led"] > 1 else f"the {color} LED")
        exact = " Use exactly this pin — the code counts through the pins in order." if self.fixed_pins else ""
        self._step(f"{d}-resistor", "Push a 220 Ω resistor into the breadboard. Put its two legs in two different columns.",
                   f"Put the resistor for {what} on the breadboard.",
                   ["A resistor works either way round.", "It protects the LED — without it the LED can burn out."], landing=f"{r}:1")
        self._step(f"{d}-pin", f"Run a wire from one leg of the resistor you just placed to pin <b>{pin}</b> on the Arduino.",
                   f"Connect the resistor to pin {pin}.",
                   [f"Put the wire in any hole in the same column as the leg.{exact}", f"Pin {pin} is on the Arduino's row of numbered sockets."],
                   nets=[[f"{r}:1", f"{self.board}:{pin}"]])
        self._step(f"{d}-legs", f"Put {what} in: the <b>long</b> leg in the same column as that resistor's other leg, the <b>short</b> leg "
                   "in the next column.", f"Connect {what}'s long leg (+) to the resistor.",
                   ["The long leg is + (the anode). Backwards, the LED stays dark.", "Legs in the same column are connected — no wire needed."],
                   nets=[[f"{d}:A", f"{r}:2"]])
        self._step(f"{d}-gnd", self._to_rail("gnd", f"{what}'s short leg"), f"Connect {what}'s short leg (−) to GND.",
                   ["The short leg is − (the cathode).", "GND is the minus side of the circuit."], nets=[[f"{d}:C", f"{self.board}:GND.1"]])
        self.nets += [[f"{r}:1", f"{self.board}:{pin}"], [f"{d}:A", f"{r}:2"], [f"{d}:C", f"{self.board}:GND.1"]]
        return d

    def button(self, pin, pulldown=True, label=None):
        """A pushbutton across the gap. pulldown: 5V on one side, the pin + a 10 kΩ
        pull-down to GND on the other. Otherwise (INPUT_PULLUP): pin and GND."""
        self.power_rails()
        c = self.col; self.col += 7 if pulldown else 4
        b = self._id("btn")
        what = label or self._nth("btn", "button")
        What = what[0].upper() + what[1:]
        self._part("wokwi-pushbutton", b, {"color": "green"}); self._need("pushbutton")
        self._wire(f"{b}:1.l", f"bb1:{c}t.e"); self._wire(f"{b}:1.r", f"bb1:{c}b.f")
        self._wire(f"{b}:2.l", f"bb1:{c + 2}t.e"); self._wire(f"{b}:2.r", f"bb1:{c + 2}b.f")
        self._step(f"{b}-place", f"Push {what} in across the middle gap: two legs above the gap, two below.",
                   f"Put {what} across the middle gap.",
                   ["The two legs in one column (above and below the gap) are always joined inside the button.",
                    "Pressing joins the left column to the right column."], landing=[f"{b}:1.r", f"{b}:2.r"])
        self._step(f"{b}-pin", f"Run a wire from {what}'s <b>left</b> column (top half) to pin <b>{pin}</b> on the Arduino.",
                   f"Connect one side of {what} to pin {pin}.",
                   ["Any hole in that column works.", f"Pin {pin} is on the Arduino's row of numbered sockets."],
                   nets=[[f"{b}:1.r", f"{self.board}:{pin}"]])
        self._wire(f"bb1:{c}t.a", f"{self.board}:{pin}", "orange")
        if pulldown:
            r = self._id("r")
            self._part("wokwi-resistor", r, {"value": "10000"}); self._need("resistor-10k")
            self._wire(f"bb1:{c + 2}b.j", f"bb1:bp.{self._rail_n(c + 2)}", "red")
            self._wire(f"{r}:1", f"bb1:{c}b.h"); self._wire(f"{r}:2", f"bb1:{c + 4}b.h")
            self._wire(f"bb1:{c + 4}b.j", f"bb1:bn.{self._rail_n(c + 4)}", "black")
            self._step(f"{b}-5v", self._to_rail("5v", f"{what}'s right column (bottom half)"), f"Connect the other side of {what} to 5V.",
                       ["When you press, 5V flows through the button to the pin."], nets=[[f"{b}:2.r", f"{self.board}:5V"]])
            self._step(f"{b}-pulldown", f"Push a 10 kΩ resistor in: one leg in {what}'s <b>left</b> column (bottom half), the other leg "
                       "in an empty column.", f"Put a 10 kΩ resistor on {what}'s pin {pin} side.",
                       ["This is a pull-down: it keeps the pin LOW until you press.", "Without it the pin 'floats' and reads random values."],
                       nets=[[f"{r}:1", f"{b}:1.r"]])
            self._step(f"{b}-pulldown-gnd", self._to_rail("gnd", "the 10 kΩ resistor's other leg"), "Connect the 10 kΩ resistor to GND.",
                       ["Now the pin reads LOW, and HIGH only while you press."], nets=[[f"{r}:2", f"{self.board}:GND.1"]])
            self.nets += [[f"{b}:1.r", f"{self.board}:{pin}"], [f"{b}:2.r", f"{self.board}:5V"], [f"{r}:1", f"{b}:1.r"], [f"{r}:2", f"{self.board}:GND.1"]]
        else:
            self._wire(f"bb1:{c + 2}b.j", f"bb1:bn.{self._rail_n(c + 2)}", "black")
            self._step(f"{b}-gnd", self._to_rail("gnd", f"{what}'s right column (bottom half)"), f"Connect the other side of {what} to GND.",
                       ["No resistor needed: INPUT_PULLUP turns on one inside the chip.", "So the pin reads HIGH, and LOW while you press."],
                       nets=[[f"{b}:2.r", f"{self.board}:GND.1"]])
            self.nets += [[f"{b}:1.r", f"{self.board}:{pin}"], [f"{b}:2.r", f"{self.board}:GND.1"]]
        return b

    def pot(self, pin):
        """A knob: outer legs to the rails, the middle (wiper) to an analog pin."""
        self.power_rails()
        c = self.col; self.col += 4
        p = self._id("pot")
        self._part("wokwi-potentiometer", p); self._need("potentiometer-10k")
        self._wire(f"bb1:{c}b.f", f"{p}:GND"); self._wire(f"bb1:{c + 1}b.f", f"{p}:SIG"); self._wire(f"bb1:{c + 2}b.f", f"{p}:VCC")
        self._wire(f"bb1:{c}b.j", f"bb1:bn.{self._rail_n(c)}", "black"); self._wire(f"bb1:{c + 2}b.j", f"bb1:bp.{self._rail_n(c + 2)}", "red")
        self._wire(f"bb1:{c + 1}b.h", f"{self.board}:{pin}", "orange")
        knob = self._nth("pot", "knob")
        self._step(f"{p}-place", f"Push {'the knob' if knob == 'the knob' else 'a ' + knob[4:]} into the breadboard, each of its three legs in its own column.", f"Put {knob} on the breadboard.",
                   ["The two outer legs are for power; the middle leg gives the reading."], landing=[f"{p}:GND", f"{p}:SIG", f"{p}:VCC"])
        self._step(f"{p}-gnd", self._to_rail("gnd", f"one outer leg of {knob}"), f"Connect one outer leg of {knob} to GND.",
                   ["Either outer leg works."], nets=[[f"{p}:GND", f"{self.board}:GND.1"]])
        self._step(f"{p}-5v", self._to_rail("5v", f"{knob}'s other outer leg"), f"Connect {knob}'s other outer leg to 5V.",
                   ["Now the knob has 0 V at one end and 5 V at the other."], nets=[[f"{p}:VCC", f"{self.board}:5V"]])
        self._step(f"{p}-pin", f"Run a wire from {knob}'s <b>middle</b> leg to pin <b>{pin}</b> on the Arduino.",
                   f"Connect {knob}'s middle leg to pin {pin}.",
                   [f"Pin {pin} is on the ANALOG IN side of the Arduino.", "The middle leg's voltage follows the knob: 0 V to 5 V."],
                   nets=[[f"{p}:SIG", f"{self.board}:{pin}"]])
        self.nets += [[f"{p}:GND", f"{self.board}:GND.1"], [f"{p}:VCC", f"{self.board}:5V"], [f"{p}:SIG", f"{self.board}:{pin}"]]
        return p

    def buzzer(self, pin):
        """A piezo buzzer: + to the pin, − to the GND row."""
        self.power_rails()
        c = self.col; self.col += 5
        z = self._id("bz")
        self._part("wokwi-buzzer", z); self._need("buzzer")
        self._wire(f"{z}:1", f"bb1:{c}b.f"); self._wire(f"{z}:2", f"bb1:{c + 3}b.f")
        self._wire(f"bb1:{c}b.j", f"bb1:bn.{self._rail_n(c)}", "black"); self._wire(f"bb1:{c + 3}b.j", f"{self.board}:{pin}", "orange")
        bz = self._nth("bz", "buzzer")
        self._step(f"{z}-place", f"Push {'the buzzer' if bz == 'the buzzer' else 'a ' + bz[4:]} in, its two legs in two different columns.", f"Put {bz} on the breadboard.",
                   ["The + leg is marked on top (and is usually longer).", "It only works one way round."], landing=[f"{z}:1", f"{z}:2"])
        self._step(f"{z}-pin", f"Run a wire from {bz}'s <b>+</b> leg to pin <b>{pin}</b> on the Arduino.", f"Connect {bz}'s + leg to pin {pin}.",
                   ["tone() on this pin makes the buzzer sing."], nets=[[f"{z}:2", f"{self.board}:{pin}"]])
        self._step(f"{z}-gnd", self._to_rail("gnd", f"{bz}'s other leg"), f"Connect {bz}'s − leg to GND.",
                   ["GND is the minus side of the circuit."], nets=[[f"{z}:1", f"{self.board}:GND.1"]])
        self.nets += [[f"{z}:2", f"{self.board}:{pin}"], [f"{z}:1", f"{self.board}:GND.1"]]
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
        self._wire(f"bb1:{c}b.j", f"bb1:bp.{self._rail_n(c)}", "red")
        self._wire(f"bb1:{c + 2}b.i", f"{self.board}:{pin}", "orange")
        self._wire(f"{r}:1", f"bb1:{c + 2}b.h"); self._wire(f"{r}:2", f"bb1:{c + 6}b.h")
        self._wire(f"bb1:{c + 6}b.j", f"bb1:bn.{self._rail_n(c + 6)}", "black")
        the = self._nth(prefix, word)
        self._step(f"{sid}-place", f"Push {'the ' + word if the == 'the ' + word else 'a ' + the[4:]} in, its two legs in two different columns.", f"Put {the} on the breadboard.",
                   ["It works either way round."], landing=[f"{sid}:1", f"{sid}:2"])
        self._step(f"{sid}-5v", self._to_rail("5v", f"one leg of {the}"), f"Connect one leg of {the} to 5V.",
                   ["Either leg works."], nets=[[f"{sid}:1", f"{self.board}:5V"]])
        self._step(f"{sid}-pin", f"Run a wire from {the}'s <b>other</b> leg to pin <b>{pin}</b> on the Arduino.",
                   f"Connect {the}'s other leg to pin {pin}.", [f"Pin {pin} is on the ANALOG IN side of the Arduino."],
                   nets=[[f"{sid}:2", f"{self.board}:{pin}"]])
        self._step(f"{sid}-resistor", f"Push a {rtext} resistor in: one leg in the same column as the pin {pin} wire, the other "
                   "leg in an empty column.", f"Put a {rtext} resistor next to the pin {pin} wire.",
                   [f"The {word} and this resistor share the 5 V between them — so the pin's voltage changes as the {word} does."],
                   nets=[[f"{r}:1", f"{sid}:2"]])
        self._step(f"{sid}-gnd", self._to_rail("gnd", f"that resistor's other leg"), f"Connect the {rtext} resistor to GND.",
                   ["Now the reading goes up when the " + ("light gets brighter." if kind == "ldr" else "pad is pressed.")],
                   nets=[[f"{r}:2", f"{self.board}:GND.1"]])
        self.nets += [[f"{sid}:1", f"{self.board}:5V"], [f"{sid}:2", f"{self.board}:{pin}"], [f"{r}:1", f"{sid}:2"], [f"{r}:2", f"{self.board}:GND.1"]]
        return sid

    def knock(self, pin):
        """A piezo used as a knock sensor: + to an analog pin, − to GND, and a 1 MΩ
        resistor across it (from + to the GND row) to drain its spikes."""
        self.power_rails()
        c = self.col; self.col += 9
        z, r = self._id("bz"), self._id("r")
        self._part("wokwi-buzzer", z); self._part("wokwi-resistor", r, {"value": "1000000"})
        self._need("buzzer"); self._need("resistor-1m")
        self._wire(f"{z}:1", f"bb1:{c}b.f"); self._wire(f"{z}:2", f"bb1:{c + 3}b.f")
        self._wire(f"bb1:{c}b.j", f"bb1:bn.{self._rail_n(c)}", "black"); self._wire(f"bb1:{c + 3}b.i", f"{self.board}:{pin}", "orange")
        self._wire(f"{r}:1", f"bb1:{c + 3}b.h"); self._wire(f"{r}:2", f"bb1:{c + 7}b.h"); self._wire(f"bb1:{c + 7}b.j", f"bb1:bn.{self._rail_n(c + 7)}", "black")
        self._step(f"{z}-place", "Push the piezo in, its two legs in two different columns.", "Put the piezo on the breadboard.",
                   ["Here the piezo is a sensor: a knock squeezes it and it makes a tiny voltage.", "Its + leg is marked on top."], landing=[f"{z}:1", f"{z}:2"])
        self._step(f"{z}-gnd", self._to_rail("gnd", "the piezo's − leg"), "Connect the piezo's − leg to GND.", ["The − leg is the unmarked one."],
                   nets=[[f"{z}:1", f"{self.board}:GND.1"]])
        self._step(f"{z}-pin", f"Run a wire from the piezo's <b>+</b> leg to pin <b>{pin}</b> on the Arduino.", f"Connect the piezo's + leg to pin {pin}.",
                   [f"Pin {pin} is on the ANALOG IN side: a knock shows up as a jump in the reading."], nets=[[f"{z}:2", f"{self.board}:{pin}"]])
        self._step(f"{r}-place", "Push the 1 MΩ resistor in: one leg in the same column as the piezo's + leg, the other leg in an empty column.",
                   "Put the 1 MΩ resistor next to the piezo's + leg.", ["It slowly drains the piezo's charge so each knock is a fresh spike."],
                   nets=[[f"{r}:1", f"{z}:2"]])
        self._step(f"{r}-gnd", self._to_rail("gnd", "the 1 MΩ resistor's other leg"), "Connect the 1 MΩ resistor to GND.", ["Now it sits across the piezo."],
                   nets=[[f"{r}:2", f"{self.board}:GND.1"]])
        self.nets += [[f"{z}:1", f"{self.board}:GND.1"], [f"{z}:2", f"{self.board}:{pin}"], [f"{r}:1", f"{z}:2"], [f"{r}:2", f"{self.board}:GND.1"]]
        return z

    def module(self, wtype, card, prefix, word, wiring, *, place_note="", straddle=False, pin_words=None):
        """A sensor module on header pins, each pin wired as `wiring` says:
        {"PIN": "5v" | "gnd" | "3v3" | "<Arduino pin>" | None (unused)}. Pin
        order comes from the bench part (models.js PART_PINS); `straddle` for a
        chip-style part across the middle gap (pins in a top and a bottom row)."""
        self.power_rails()
        from json import loads
        rows = PIN_LAYOUT[wtype]
        c = self.col; self.col += max(dx for _, dx, _ in rows) + 3
        mid = self._id(prefix)
        self._part(wtype, mid); self._need(card)
        hole = {}
        for name, dx, dz in rows:
            hole[name] = f"{c + dx}{'b' if dz else ('t' if straddle else 'b')}"
            self._wire(f"{mid}:{name}", f"bb1:{hole[name]}.{'f' if dz or not straddle else 'e'}")
        self._step(f"{mid}-place", f"Push the {word} in{place_note}.", f"Put the {word} on the breadboard.",
                   ["Its pin names are printed next to the pins."], landing=[f"{mid}:{n}" for n, _, _ in rows])
        words = pin_words or {}
        for name, target in wiring.items():
            if not target:
                continue
            label = words.get(name, name)
            strip, row = hole[name], ("a" if hole[name].endswith("t") else "j")
            if target in ("5v", "gnd"):
                self._wire(f"bb1:{strip}.{row}", f"bb1:{'bp' if target == '5v' else 'bn'}.{int(strip[:-1])}", "red" if target == "5v" else "black")
                self._step(f"{mid}-{name.lower().replace('.', '')}", self._to_rail(target, f"the {word}'s {label} pin"), f"Connect the {word}'s {label} pin to {'5V' if target == '5v' else 'GND'}.",
                           ["Power first: + to 5V, − to GND." if target == "5v" else "GND is the minus side."],
                           nets=[[f"{mid}:{name}", f"{self.board}:5V" if target == "5v" else f"{self.board}:GND.1"]])
                self.nets.append([f"{mid}:{name}", f"{self.board}:5V" if target == "5v" else f"{self.board}:GND.1"])
            else:
                board_pin = "3.3V" if target == "3v3" else target
                self._wire(f"bb1:{strip}.{row}", f"{self.board}:{board_pin}", "orange")
                where = board_pin if target == "3v3" else f"pin {board_pin}"
                self._step(f"{mid}-{name.lower().replace('.', '')}", f"Run a wire from the {word}'s <b>{label}</b> pin to <b>{where}</b> on the Arduino.",
                           f"Connect the {word}'s {label} pin to {where}.",
                           ["3.3V is on the Arduino's power header, next to 5V." if target == "3v3" else f"Pin {board_pin} is on the Arduino's {'ANALOG IN side' if board_pin.startswith('A') else 'row of numbered sockets'}."],
                           nets=[[f"{mid}:{name}", f"{self.board}:{board_pin}"]])
                self.nets.append([f"{mid}:{name}", f"{self.board}:{board_pin}"])
        return mid

    def _rail_n(self, col):
        """The + / − row hole nearest to column `col` (the rows have a gap every 6th column)."""
        count = (63 if self.bb == "wokwi-breadboard" else 30) - 1
        count = count * 5 // 6
        best = min(range(1, count + 1), key=lambda n: abs(1 + (n - 1) + (n - 1) // 5 - col))
        return best

    @staticmethod
    def rail_index(col):
        """The − / + row hole under column `col` (the rows have a gap every 6th column), or None."""
        for n in range(1, 60):
            if 1 + (n - 1) + (n - 1) // 5 == col:
                return n
        return None

    def bargraph(self, pins):
        """A 10-segment bar graph across the gap: each segment's + leg to its pin,
        its − leg through a 220 Ω resistor that hops straight into the − row
        (turned sideways, from row h). A column over a gap in the − row gets a
        short wire to a free column first."""
        self.power_rails()
        c = self.col; self.col += 10
        bar = self._id("bar")
        self._part("wokwi-led-bar-graph", bar); self._need("led-bar-graph")
        for k in range(1, 11):
            self._wire(f"{bar}:A{k}", f"bb1:{c + k - 1}t.e"); self._wire(f"{bar}:C{k}", f"bb1:{c + k - 1}b.f")
        self._step(f"{bar}-place", "Push the bar graph in across the middle gap: ten legs above the gap, ten below. The printed side (the + legs) goes on top.",
                   "Put the bar graph across the middle gap.", ["Each of the ten bars is its own little LED: + leg on top, − leg below the gap."],
                   landing=[f"{bar}:A{k}" for k in range(1, 11)] + [f"{bar}:C{k}" for k in range(1, 11)])
        spare = self.col; self.col += 2
        first_gnd = True
        for k, pin in enumerate(pins, start=1):
            col = c + k - 1
            self._wire(f"bb1:{col}t.a", f"{self.board}:{pin}", "orange")
            self._step(f"{bar}-a{k}", f"Run a wire from bar <b>{k}</b>'s + leg (top half) to pin <b>{pin}</b> on the Arduino.",
                       f"Connect bar {k}'s + leg to pin {pin}.", ["Any hole in that column works."], nets=[[f"{bar}:A{k}", f"{self.board}:{pin}"]])
            r = self._id("r"); self._part("wokwi-resistor", r, {"value": "220"}); self._need("resistor-220")
            n = self.rail_index(col)
            todo = []
            if first_gnd:
                self._gnd_done = True; self._wire("bb1:bn.1", f"{self.board}:GND.1", "black"); first_gnd = False
                todo.append("A wire from the Arduino's <b>GND</b> pin to the blue − row at the bottom.")
            upright = "Stand a 220 Ω resistor upright: one leg in {where} (row h), the other leg in the blue − row just below it."
            if n:
                self._wire(f"{r}:1", f"bb1:{col}b.h"); self._wire(f"{r}:2", f"bb1:bn.{self._rail_n(n)}")
                todo.append(upright.format(where=f"bar {k}'s − column"))
                hint = "Each bar needs its own resistor, like any LED."
            else:
                n2 = self.rail_index(spare)
                self._wire(f"bb1:{col}b.j", f"bb1:{spare}b.j", "black")
                self._wire(f"{r}:1", f"bb1:{spare}b.h"); self._wire(f"{r}:2", f"bb1:bn.{self._rail_n(n2)}")
                todo += [f"A short wire from bar {k}'s − column (row j) to the empty column {spare}.", upright.format(where=f"column {spare}")]
                hint = f"The − row has a small gap under bar {k}, so its resistor stands in column {spare} instead."
            clip = todo[0] if len(todo) == 1 else f"{'Two' if len(todo) == 2 else 'Three'} things:<br>" + "<br>".join(f"{i}. {t}" for i, t in enumerate(todo, 1))
            self._step(f"{bar}-c{k}", clip, f"Connect bar {k}'s − leg to GND through a 220 Ω resistor.", [hint],
                       nets=[[f"{r}:1", f"{bar}:C{k}"], [f"{r}:2", f"{self.board}:GND.1"]])
            self.nets += [[f"{bar}:A{k}", f"{self.board}:{pin}"], [f"{r}:1", f"{bar}:C{k}"], [f"{r}:2", f"{self.board}:GND.1"]]
        return bar

    def matrix(self, row_pins, col_pins):
        """An 8x8 LED matrix: pins in rows a (R1–R8) and j (C1–C8) of columns 5–12.
        Rows wire straight to their pins; each column goes through a 220 Ω
        resistor out to a free column 4 holes away (1–4 on the left, 13–16 on
        the right), then a wire to its pin."""
        self.power_rails()
        c = 5; self.col = max(self.col, 17)
        m = self._id("mx")
        self._part("cq-led-matrix-8x8", m); self._need("led-matrix-8x8")
        for k in range(1, 9):
            self._wire(f"{m}:R{k}", f"bb1:{c + k - 1}t.a"); self._wire(f"{m}:C{k}", f"bb1:{c + k - 1}b.j")
        self._step(f"{m}-place", "Push the 8×8 matrix into the middle of the breadboard (columns 5–12): its top pins in row a, its bottom pins in row j. "
                   "It covers the holes between — that's fine.", "Put the LED matrix on the breadboard.",
                   ["The top 8 pins (R1–R8) feed the matrix's rows (+), the bottom 8 (C1–C8) its columns (−).", "Wires can still go into the covered holes."],
                   landing=[f"{m}:R{k}" for k in range(1, 9)] + [f"{m}:C{k}" for k in range(1, 9)])
        for k, pin in enumerate(row_pins, start=1):
            self._wire(f"bb1:{c + k - 1}t.c", f"{self.board}:{pin}", "orange")
            self._step(f"{m}-r{k}", f"Run a wire from matrix pin <b>R{k}</b> (breadboard column {c + k - 1}, top half) to pin <b>{pin}</b> on the Arduino.",
                       f"Connect matrix pin R{k} to pin {pin}.", ["Any hole in that column's top half works."], nets=[[f"{m}:R{k}", f"{self.board}:{pin}"]])
            self.nets.append([f"{m}:R{k}", f"{self.board}:{pin}"])
        for k, pin in enumerate(col_pins, start=1):
            col = c + k - 1
            free = col - 4 if k <= 4 else col + 4
            r = self._id("r"); self._part("wokwi-resistor", r, {"value": "220"}); self._need("resistor-220")
            self._wire(f"{r}:1", f"bb1:{col}b.h"); self._wire(f"{r}:2", f"bb1:{free}b.h")
            self._wire(f"bb1:{free}b.j", f"{self.board}:{pin}", "orange")
            self._step(f"{m}-c{k}-r", f"Push a 220 Ω resistor in: one leg in breadboard column {col} (bottom half, under matrix pin <b>C{k}</b>), the other leg in the empty "
                       f"column {free}.", f"Put a resistor on matrix pin C{k}.", ["Each of the 8 C pins needs its own resistor, like any LED."],
                       nets=[[f"{r}:1", f"{m}:C{k}"]])
            self._step(f"{m}-c{k}-pin", f"Run a wire from that resistor's other leg (column {free}) to pin <b>{pin}</b> on the Arduino.",
                       f"Connect C{k}'s resistor to pin {pin}.", [f"Pin {pin} is on the Arduino's {'ANALOG IN side' if str(pin).startswith('A') else 'row of numbered sockets'}."],
                       nets=[[f"{r}:2", f"{self.board}:{pin}"]])
            self.nets += [[f"{r}:1", f"{m}:C{k}"], [f"{r}:2", f"{self.board}:{pin}"]]
        return m

    def midi(self):
        """A MIDI out socket: pin 4 through 220 Ω to 5V, pin 5 to TX (pin 1), pin 2 to GND."""
        self.power_rails()
        c = self.col; self.col += 9
        j, r = self._id("midi"), self._id("r")
        self._part("cq-midi-jack", j); self._part("wokwi-resistor", r, {"value": "220"})
        self._need("midi-jack"); self._need("resistor-220")
        for k in range(1, 6):
            self._wire(f"{j}:{k}", f"bb1:{c + k - 1}b.f")
        self._wire(f"bb1:{c + 1}b.j", f"bb1:bn.{self._rail_n(c + 1)}", "black")
        self._wire(f"{r}:1", f"bb1:{c + 3}b.h"); self._wire(f"{r}:2", f"bb1:{c + 7}b.h"); self._wire(f"bb1:{c + 7}b.j", f"bb1:bp.{self._rail_n(c + 7)}", "red")
        self._wire(f"bb1:{c + 4}b.j", f"{self.board}:1", "orange")
        self._step(f"{j}-place", "Push the MIDI socket in, its five pins in five columns (numbered 1–5 from the left), the round socket facing you.",
                   "Put the MIDI socket on the breadboard.", ["Only pins 2, 4 and 5 are used; 1 and 3 stay empty."], landing=[f"{j}:{k}" for k in range(1, 6)])
        self._step(f"{j}-gnd", self._to_rail("gnd", "the socket's pin 2"), "Connect the socket's pin 2 to GND.", ["Pin 2 is the cable's shield (its outer metal)."], nets=[[f"{j}:2", f"{self.board}:GND.1"]])
        self._step(f"{j}-resistor", "Push a 220 Ω resistor in: one leg in the same column as the socket's pin 4, the other leg in an empty column.", "Put a 220 Ω resistor on the socket's pin 4.",
                   ["MIDI sends a small current through the cable: this resistor limits it."], nets=[[f"{r}:1", f"{j}:4"]])
        self._step(f"{j}-5v", self._to_rail("5v", "the resistor's other leg"), "Connect the resistor to 5V.", ["The socket's pin 4 gets 5V through this resistor."],
                   nets=[[f"{r}:2", f"{self.board}:5V"]])
        self._step(f"{j}-tx", "Run a wire from the socket's pin 5 to pin <b>1</b> (TX) on the Arduino.", "Connect the socket's pin 5 to pin 1 (TX).",
                   ["TX is the Arduino's serial output — the MIDI notes come out here.", "Unplug the MIDI cable while uploading: uploads use this pin too."],
                   nets=[[f"{j}:5", f"{self.board}:1"]])
        self.nets += [[f"{j}:2", f"{self.board}:GND.1"], [f"{r}:1", f"{j}:4"], [f"{r}:2", f"{self.board}:5V"], [f"{j}:5", f"{self.board}:1"]]
        return j

    def rgb(self, red, green, blue):
        """A common-anode RGB LED: COM to 5V, each colour through a 220 Ω resistor to its pin."""
        self.power_rails()
        c = self.col; self.col += 9
        d = self._id("rgb")
        self._part("wokwi-rgb-led", d, {"common": "anode"}); self._need("rgb-led")
        for name, dx in (("R", 0), ("COM", 1), ("G", 2), ("B", 3)):
            self._wire(f"{d}:{name}", f"bb1:{c + dx}t.e")
        self._wire(f"bb1:{c + 1}t.d", f"bb1:bp.{self._rail_n(c + 1)}", "red")
        self._step(f"{d}-place", "Push the RGB LED in, each of its four legs in its own column (top half). The longest leg is the common one.",
                   "Put the RGB LED on the breadboard.", ["Legs from left to right: red, common (longest), green, blue."],
                   landing=[f"{d}:R", f"{d}:COM", f"{d}:G", f"{d}:B"])
        self._step(f"{d}-com", self._to_rail("5v", "the RGB LED's longest leg"), "Connect the common leg to 5V.",
                   ["This LED is common anode: the shared leg is +. A colour lights when its own pin goes LOW."], nets=[[f"{d}:COM", f"{self.board}:5V"]])
        self.nets.append([f"{d}:COM", f"{self.board}:5V"])
        for colour, dx, pin, row, span in (("R", 0, red, "a", 4), ("G", 2, green, "b", 4), ("B", 3, blue, "c", 4)):
            r = self._id("r")
            self._part("wokwi-resistor", r, {"value": "220"}); self._need("resistor-220")
            far = c + dx + span
            self._wire(f"{r}:1", f"bb1:{c + dx}t.{row}"); self._wire(f"{r}:2", f"bb1:{far}t.{row}")
            self._wire(f"bb1:{far}t.d", f"{self.board}:{pin}", "orange")
            name = {"R": "red", "G": "green", "B": "blue"}[colour]
            self._step(f"{d}-{colour.lower()}-resistor", f"Push a 220 Ω resistor in: one leg in the same column as the {name} leg, the other leg in an empty column.",
                       f"Put a resistor on the {name} leg.", ["Each colour needs its own resistor."], nets=[[f"{r}:1", f"{d}:{colour}"]])
            self._step(f"{d}-{colour.lower()}-pin", f"Run a wire from that resistor's other leg to pin <b>{pin}</b> on the Arduino.",
                       f"Connect the {name} resistor to pin {pin}.", [f"Pin {pin} has a ~ next to it: it can dim the colour (PWM)."],
                       nets=[[f"{r}:2", f"{self.board}:{pin}"]])
            self.nets += [[f"{r}:1", f"{d}:{colour}"], [f"{r}:2", f"{self.board}:{pin}"]]
        return d

    # ---- writing ---------------------------------------------------------------------------
    # ---- a bare ATmega328P on the breadboard (Arduino as ISP / chip on a breadboard) -------------
    def _seat(self, pid, wtype, col, row="h", straddle=False):
        """Wire a part's legs into the breadboard as PIN_LAYOUT lays them out
        from column `col`. Returns {pin: strip}."""
        hole = {}
        for name, dx, dz in PIN_LAYOUT[wtype]:
            strip, r = ((f"{col + dx}t", "e") if dz == 0 else (f"{col + dx}b", "f")) if straddle else (f"{col + dx}b", row)
            self._wire(f"{pid}:{name}", f"bb1:{strip}.{r}")
            hole[name] = strip
        return hole

    def _free(self, strip):
        """A hole in `strip` nothing is in yet — rows nearest the edge first."""
        used = {p.split(".", 1)[1] for c in self.conns for p in c[:2] if p.startswith(f"bb1:{strip}.")}
        return next(r for r in ("abcd" if strip.endswith("t") else "jihg") if r not in used)

    def _rail_wire(self, strip, which):
        """A wire from `strip` to the nearest free hole of the − (gnd) or + (5v) row."""
        rail = "bn" if which == "gnd" else "bp"
        used = {p for c in self.conns for p in c[:2] if p.startswith(f"bb1:{rail}.")}
        count = ((63 if self.bb == "wokwi-breadboard" else 30) - 1) * 5 // 6
        col = int(strip[:-1])
        n = min((k for k in range(1, count + 1) if f"bb1:{rail}.{k}" not in used), key=lambda k: abs(1 + (k - 1) + (k - 1) // 5 - col))
        self._wire(f"bb1:{strip}.{self._free(strip)}", f"bb1:{rail}.{n}", "black" if which == "gnd" else "red")

    def _rail_step(self, sid, strip, which, what, goal, hints, net):
        """A step wiring `strip` to a power row (the first time, with the row's own wire to the Arduino)."""
        clip = self._to_rail(which, what)
        self._rail_wire(strip, which)
        self._step(sid, clip, goal, hints, nets=self._net(*net))

    def _net(self, a, b):
        self.nets.append([a, b])
        return [[a, b]]

    def bare_chip(self):
        """An ATmega328P across the gap, its four power pins, and its clock: the
        16 MHz crystal on pins 9 and 10 with a 22 pF capacitor from each leg to GND."""
        self.power_rails()
        gnd, v5 = f"{self.board}:GND.1", f"{self.board}:5V"
        c = self.col; self.col += 15
        u = self._id("chip"); self._part("cq-atmega328p", u); self._need("atmega328p")
        hole = self._seat(u, "cq-atmega328p", c, straddle=True)
        self.chip, self.chip_hole = u, hole
        self._step(f"{u}-place", "Push the ATmega328P chip in across the middle gap, the notch (the little half-moon dent) on the <b>left</b>.",
                   "Put the chip on the breadboard.",
                   ["With the notch on the left, pin 1 is bottom-left. Pins 1–14 run left to right along the bottom, 15–28 come back along the top.",
                    "Press gently on both ends so all 28 legs go in straight."], landing=[f"{u}:{k}" for k in range(1, 29)])
        for pin, which, label, why in [("7", "5v", "VCC", "VCC is the chip's power in."), ("8", "gnd", "GND", "The chip's ground."),
                                       ("20", "5v", "AVCC", "AVCC powers the chip's analog side — it needs 5V too."),
                                       ("22", "gnd", "GND", "The chip's second ground pin — connect both.")]:
            self._rail_step(f"{u}-p{pin}", hole[pin], which, f"chip pin <b>{pin}</b> ({label})", f"Connect chip pin {pin} ({label}) to {'5V' if which == '5v' else 'GND'}.",
                            [why, "Count from pin 1 (bottom-left): along the bottom to 14, then back along the top from 15 on the right."],
                            (f"{u}:{pin}", v5 if which == "5v" else gnd))
        x = self.col; self.col += 8
        y, k1, k2 = self._id("xtal"), self._id("cap"), self._id("cap")
        self._part("cq-crystal", y); self._part("cq-capacitor-ceramic", k1, {"value": "22p"}); self._part("cq-capacitor-ceramic", k2, {"value": "22p"})
        self._need("crystal-16mhz"); self._need("capacitor-22pf")
        self._seat(y, "cq-crystal", x + 2, row="g"); self._seat(k1, "cq-capacitor-ceramic", x, row="h"); self._seat(k2, "cq-capacitor-ceramic", x + 3, row="h")
        self._step(f"{y}-place", "Push the 16 MHz crystal (the small silver can) in to the right of the chip, its two legs in two columns next to each other.",
                   "Put the crystal on the breadboard.", ["The crystal is the chip's clock. It works either way round."], landing=[f"{y}:1", f"{y}:2"])
        for pin, leg, side in [("9", "1", "left"), ("10", "2", "right")]:
            leg_strip = f"{x + 1 + int(leg)}b"
            self._wire(f"bb1:{hole[pin]}.{self._free(hole[pin])}", f"bb1:{leg_strip}.{self._free(leg_strip)}", "yellow")
            self._step(f"{y}-p{pin}", f"Run a wire from chip pin <b>{pin}</b> to the crystal's {side} leg.", f"Connect chip pin {pin} to the crystal.",
                       [f"Chip pin {pin} is the {pin}th leg from the left on the bottom row.", "Either crystal leg is fine — it has no + or −."],
                       nets=self._net(f"{u}:{pin}", f"{y}:{leg}"))
        for cap, leg, cap_leg, side, far in [(k1, "1", "2", "left", "left"), (k2, "2", "1", "right", "right")]:
            self._step(f"{cap}-place", f"Push a 22 pF capacitor (marked “22”) in: one leg in the same column as the crystal's {side} leg, the other leg two columns to the {far}.",
                       f"Put a 22 pF capacitor on the crystal's {side} leg.", ["It helps the crystal start and keep a steady beat.", "It works either way round."],
                       landing=[f"{cap}:1", f"{cap}:2"], nets=self._net(f"{cap}:{cap_leg}", f"{y}:{leg}"))
            other = "1" if cap_leg == "2" else "2"
            self._rail_step(f"{cap}-gnd", f"{x if cap == k1 else x + 5}b", "gnd", "the capacitor's other leg", "Connect the capacitor's other leg to GND.",
                            ["Each crystal leg gets its own 22 pF capacitor to GND."], (f"{cap}:{other}", gnd))
        return u

    def isp_wires(self):
        """The Arduino programs the chip: 13→19 (SCK), 12→18 (MISO), 11→17 (MOSI), 10→1 (RESET)."""
        u, hole = self.chip, self.chip_hole
        for pin, chip_pin, name, why in [("13", "19", "SCK", "SCK is the clock: the Arduino ticks it for every bit it sends."),
                                         ("12", "18", "MISO", "MISO carries bits from the chip back to the Arduino."),
                                         ("11", "17", "MOSI", "MOSI carries bits from the Arduino to the chip."),
                                         ("10", "1", "RESET", "Pin 10 holds the chip in reset while it is being programmed.")]:
            self._wire(f"{self.board}:{pin}", f"bb1:{hole[chip_pin]}.{self._free(hole[chip_pin])}", "orange")
            self._step(f"{u}-{name.lower()}", f"Run a wire from pin <b>{pin}</b> on the Arduino to chip pin <b>{chip_pin}</b> ({name}).",
                       f"Connect pin {pin} to chip pin {chip_pin}.", [why + " Use exactly this pin.", f"Chip pin {chip_pin} is on the {'bottom' if int(chip_pin) <= 14 else 'top'} row."],
                       nets=self._net(f"{self.board}:{pin}", f"{u}:{chip_pin}"))

    def reset_cap(self):
        """10 µF from the Arduino's RESET to GND: it stops the Arduino resetting when the computer talks to it."""
        e = self.col; self.col += 4
        k = self._id("cap"); self._part("cq-capacitor-electrolytic", k, {"value": "10u"}); self._need("capacitor-10uf")
        hole = self._seat(k, "cq-capacitor-electrolytic", e, row="h")
        self._step(f"{k}-place", "Push the 10 µF capacitor (the small can) in, its legs in two columns next to each other — the <b>short</b> leg, by the pale stripe, on the right.",
                   "Put the 10 µF capacitor on the breadboard.", ["It only works one way round: the stripe marks the − leg."], landing=[f"{k}:POS", f"{k}:NEG"])
        self._wire(f"bb1:{hole['POS']}.{self._free(hole['POS'])}", f"{self.board}:RESET", "white")
        self._step(f"{k}-reset", "Run a wire from the capacitor's <b>long</b> leg to <b>RESET</b> on the Arduino.", "Connect the long leg to RESET.",
                   ["RESET is on the Arduino's power header, next to 3.3V.", "It stops the Arduino restarting itself when the computer starts talking to it."],
                   nets=self._net(f"{k}:POS", f"{self.board}:RESET"))
        self._rail_step(f"{k}-gnd", hole["NEG"], "gnd", "the capacitor's short leg", "Connect the short leg to GND.", ["The short leg is −."],
                        (f"{k}:NEG", f"{self.board}:GND.1"))

    def reset_pullup(self):
        """A 10 kΩ from chip pin 1 (RESET) to 5V: keeps the chip running instead of stuck in reset."""
        u, hole = self.chip, self.chip_hole
        r = self._id("r"); self._part("wokwi-resistor", r, {"value": "10000"}); self._need("resistor-10k")
        c1 = int(hole["1"][:-1])
        self._wire(f"{r}:2", f"bb1:{hole['1']}.{self._free(hole['1'])}"); self._wire(f"{r}:1", f"bb1:{c1 - 4}b.h")
        self._step(f"{r}-place", "Push a 10 kΩ resistor in: one leg in the same column as chip pin 1 (bottom-left), the other leg four columns to the left.",
                   "Put a 10 kΩ resistor on chip pin 1 (RESET).", ["Pin 1 is bottom-left, by the notch.", "A resistor works either way round."],
                   nets=self._net(f"{r}:2", f"{u}:1"))
        self._rail_step(f"{r}-5v", f"{c1 - 4}b", "5v", "the resistor's other leg", "Connect the resistor to 5V.",
                        ["RESET held at 5V lets the chip run. At GND it would restart."], (f"{r}:1", f"{self.board}:5V"))

    def chip_led(self, chip_pin):
        """An LED on a chip pin (not an Arduino pin) through 220 Ω to GND."""
        u, hole = self.chip, self.chip_hole
        c = self.col; self.col += 6
        r, d = self._id("r"), self._id("led")
        self._part("wokwi-resistor", r, {"value": "220"}); self._part("wokwi-led", d, {"color": "red"})
        self._need("resistor-220"); self._need("led")
        self._wire(f"{r}:1", f"bb1:{c}b.h"); self._wire(f"{r}:2", f"bb1:{c + 4}b.h")
        self._wire(f"bb1:{hole[chip_pin]}.{self._free(hole[chip_pin])}", f"bb1:{c}b.g", "orange")
        self._wire(f"{d}:A", f"bb1:{c + 4}b.i"); self._wire(f"{d}:C", f"bb1:{c + 3}b.i")
        self._step(f"{d}-resistor", "Push a 220 Ω resistor into an empty part of the breadboard, its legs in two different columns.",
                   "Put the LED's resistor on the breadboard.", ["A resistor works either way round."], landing=f"{r}:1")
        self._step(f"{d}-pin", f"Run a wire from chip pin <b>{chip_pin}</b> to one leg of the resistor.", f"Connect chip pin {chip_pin} to the resistor.",
                   [f"Chip pin {chip_pin} is the chip's digital pin 13 — the Blink pin.", f"It is on the {'bottom' if int(chip_pin) <= 14 else 'top'} row."],
                   nets=self._net(f"{r}:1", f"{u}:{chip_pin}"))
        self._step(f"{d}-legs", "Put the LED in: the <b>long</b> leg in the same column as the resistor's other leg, the <b>short</b> leg in the next column.",
                   "Connect the LED's long leg (+) to the resistor.", ["The long leg is +. Backwards, the LED stays dark."], nets=self._net(f"{d}:A", f"{r}:2"))
        self._rail_step(f"{d}-gnd", f"{c + 3}b", "gnd", "the LED's short leg", "Connect the LED's short leg (−) to GND.", ["The short leg is −."],
                        (f"{d}:C", f"{self.board}:GND.1"))

    def upload(self, note, clip=None):
        self.upload_note = note
        self.upload_clip = clip

    def write(self):
        # how many of each part, from the diagram ("6 LEDs", "1 knob")
        card_of = {"wokwi-led": "led", "wokwi-pushbutton": "pushbutton", "wokwi-potentiometer": "potentiometer-10k", "wokwi-buzzer": "buzzer",
                   "cq-photoresistor": "photoresistor", "cq-fsr": "fsr", "cq-ping": "ping-sensor", "cq-adxl335": "adxl335",
                   "cq-memsic2125": "memsic2125", "wokwi-rgb-led": "rgb-led", "wokwi-led-bar-graph": "led-bar-graph", "cq-led-matrix-8x8": "led-matrix-8x8", "cq-midi-jack": "midi-jack", "wokwi-analog-joystick": "analog-joystick",
                   "cq-atmega328p": "atmega328p", "cq-crystal": "crystal-16mhz", "cq-capacitor-ceramic": "capacitor-22pf", "cq-capacitor-electrolytic": "capacitor-10uf"}
        count = {}
        for part in self.parts:
            cid = card_of.get(part["type"]) or ({"220": "resistor-220", "10000": "resistor-10k", "4700": "resistor-4k7", "1000000": "resistor-1m"}.get(part["attrs"].get("value"))
                                                  if part["type"] == "wokwi-resistor" else None)
            if cid:
                count[cid] = count.get(cid, 0) + 1
        names = ", ".join(f"{n} × {SINGULAR.get(i, i)}" for i, n in count.items())
        gather = {"id": "gather", "phase": "gather",
                  "clip": f"You need: an {self.board_name} and its USB cable, a breadboard, {names}, and some jumper wires.",
                  "items": self.items + (["jumper-wire"] if "jumper-wire" not in self.items else [])}
        steps = [gather] + self.steps + [{"id": "upload-code", "phase": "upload",
                                          "clip": getattr(self, "upload_clip", None) or "Copy the code into the Arduino IDE and click Upload. " + self.upload_note, "code": "code.ino"}]
        lesson = {"id": self.id, "title": self.title, "description": self.description, "source": self.source,
                  "difficulty": self.difficulty, "board": self.board_card, "requires": self.requires,
                  "code": "code.ino", "wokwi_diagram": "diagram.json", "tools_used": [],
                  "parts_used": gather["items"], "steps": steps, "final_check": {"expected_nets": self.nets}}
        if self.fixed_pins:
            lesson["fixed_pins"] = True
        if getattr(self, "runs_on", None):
            lesson["sketch_runs_on"] = self.runs_on
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
