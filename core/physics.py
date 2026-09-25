"""Real circuit physics — the DC operating point of the learner's actual
circuit (PLAN.md Phase 4).

The checker answers "is this the circuit the lesson asked for?". This
module answers "what does this circuit actually do?": it builds a circuit
from the same hole-level [pin, pin] pairs the checker uses, folds
breadboard strips and board pin-aliases into electrical nodes exactly the
way the checker does (checker.board_alias_map), and solves it with
modified nodal analysis — Ohm's law for every element, Kirchhoff's current
law at every node. The result is real numbers (volts, milliamps) that
feedback can cite: an LED with no series resistor is flagged because it
would draw ~90 mA, not because it "doesn't match the answer".

Scope, stated honestly (these are modelling assumptions, not facts about
every board):
- DC only: an OUTPUT pin is solved while HIGH (the "LED on" half of
  Blink, the worst case for current); analogWrite is treated as fully on.
  No timing, no transients, no PWM averaging.
- Parts modelled: resistors, LEDs (piecewise-linear: off below a
  colour-dependent forward voltage, then Vf plus a small series
  resistance), pushbuttons (every pressed/released combination is
  solved), potentiometers (two resistors split at the wiper, solved at
  mid-travel), and the board's 5V / 3.3V / GND / I/O pins. Anything else
  is listed in `unmodeled` rather than guessed at.
- Numbers are for a 5 V AVR board (Uno/Nano/Mega): I/O pins ~25 ohm output
  resistance, 20 mA recommended / 40 mA absolute maximum per pin
  (ATmega328P datasheet), internal pull-up ~35 kohm (datasheet range
  20-50 kohm). Typical 5 mm LED: 20 mA rated, ~30 mA absolute maximum.

Pure functions, standard library only, no I/O.
"""
import itertools
import re

from . import checker
from .library import load_library

VCC = 5.0
SUPPLY_RESISTANCE = 0.05          # ohms — a stiff 5V/3.3V rail, still finite so a short solves
IO_PIN_RESISTANCE = 25.0          # ohms — approximate ATmega328P output driver
PULLUP_RESISTANCE = 35_000.0      # ohms — INPUT_PULLUP, datasheet 20-50 kohm
BUTTON_CLOSED_RESISTANCE = 0.1    # ohms
POT_RESISTANCE = 10_000.0         # ohms — end-to-end, when the diagram doesn't say
LED_SERIES_RESISTANCE = 10.0      # ohms — dynamic resistance once conducting
GMIN = 1e-9                       # siemens — keeps a floating node solvable (1 Gohm to GND)

LED_FORWARD_VOLTAGE = {           # volts, typical 5 mm LEDs by colour
    "red": 2.0, "orange": 2.0, "yellow": 2.1, "green": 2.2,
    "blue": 3.1, "white": 3.1, "purple": 3.1, "violet": 3.1, "pink": 3.1,
}
LED_RATED_MA = 20.0
LED_ABS_MAX_MA = 30.0
PIN_RECOMMENDED_MA = 20.0
PIN_ABS_MAX_MA = 40.0
SHORT_CIRCUIT_MA = 500.0          # a USB port's polyfuse trips around here
LED_DIM_MA = 2.0
LED_OFF_MA = 0.1

LOGIC_HIGH_MIN = 0.6 * VCC        # ATmega328P V_IH
LOGIC_LOW_MAX = 0.3 * VCC         # ATmega328P V_IL

_RESISTOR_TYPES = {"wokwi-resistor"}
_LED_TYPES = {"wokwi-led"}
_BUTTON_TYPES = {"wokwi-pushbutton", "wokwi-pushbutton-6mm"}
# SPDT slide switch: pin 2 (common) joins pin 1 in one position, pin 3 in the
# other. It stays where it's put — "on" means the handle is at pin 3's side.
_SLIDE_TYPES = {"wokwi-slide-switch"}
# A piezo buzzer, as a DC load between its + (pin 2) and − (pin 1): it
# "sounds" while its + side is driven above its − side.
_BUZZER_TYPES = {"wokwi-buzzer"}
BUZZER_RESISTANCE = 1000.0
BUZZER_ON_VOLTS = 1.5
# A PIR motion sensor module (HC-SR501): VCC/GND power it (a light load), and
# while powered its OUT pin is actively driven — about 3.3 V when it sees
# motion, 0 V when all is still — through the module's output resistance.
# Unpowered (or powered backwards), OUT floats. "Motion" is a scenario, like
# a button being pressed.
_PIR_TYPES = {"wokwi-pir-motion-sensor"}
PIR_SUPPLY_RESISTANCE = 50_000.0      # ~0.1 mA quiescent draw
PIR_OUTPUT_RESISTANCE = 1_000.0
PIR_HIGH_VOLTS = 3.3
PIR_MIN_SUPPLY = 4.0                  # the module's regulator needs about 4.5–20 V
# Two-legged resistive sensors with two states the learner switches on the
# bench: (resistance at rest, resistance when "on", words for off/on).
# Photoresistor: lit ~2 kΩ, covered by a hand ~50 kΩ. FSR: open until pressed.
_VARRES_TYPES = {
    "cq-photoresistor": (2_000.0, 50_000.0, "in the light", "covered"),
    "cq-fsr": (10_000_000.0, 1_000.0, "not pressed", "pressed"),
}
_POT_TYPES = {"wokwi-potentiometer", "wokwi-slide-potentiometer"}
_SUPPLY_PINS = {"5V": 5.0, "3.3V": 3.3, "3V3": 3.3}
_BOARD_PINS_NOT_MODELLED = {"VIN", "AREF", "IOREF", "RESET"}


# ---------------------------------------------------------------------------
# Reading the circuit description
# ---------------------------------------------------------------------------

def parse_resistance(value, default=1000.0):
    """'220' -> 220.0, '4.7k' -> 4700.0, '1M' -> 1e6, '10kΩ' -> 10000.0.
    Wokwi's own default resistor value is 1 kohm."""
    if value is None:
        return default
    text = str(value).strip().replace("Ω", "").replace("ohm", "").replace(" ", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([kKmM]?)", text)
    if not match:
        return default
    number, suffix = float(match.group(1)), match.group(2)
    return number * {"": 1, "k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6}[suffix]


def pin_modes_from_code(code):
    """{board_pin: 'OUTPUT' | 'INPUT' | 'INPUT_PULLUP' | 'ANALOG_IN'} read
    from an Arduino sketch: pinMode() calls, plus analogRead()/analogWrite()
    pins that never got a pinMode. Resolves integer literals, A0-A5,
    LED_BUILTIN, and simple `const int name = N;` / `#define name N`
    constants — enough for Arduino's own Basics examples, not a C parser."""
    if not code:
        return {}
    constants = {"LED_BUILTIN": "13"}
    for name, value in re.findall(r"(?:const\s+)?(?:int|byte|uint8_t)\s+(\w+)\s*=\s*(A?\d+)\s*;", code):
        constants[name] = value
    for name, value in re.findall(r"#define\s+(\w+)\s+(A?\d+)", code):
        constants[name] = value

    def resolve(token):
        token = token.strip()
        token = constants.get(token, token)
        return token if re.fullmatch(r"A?\d+", token) else None

    modes = {}
    for pin, mode in re.findall(r"pinMode\s*\(\s*(\w+)\s*,\s*(OUTPUT|INPUT_PULLUP|INPUT)\s*\)", code):
        if resolve(pin):
            modes[resolve(pin)] = mode
    # a pin array — pinMode(ledPins[i], OUTPUT) sets every pin in it
    arrays = {}
    for name, items in re.findall(r"(\w*[Pp]ins?\w*)\s*\[\s*\d*\s*\]\s*=\s*\{([^{}]*)\}", code):
        pins = [x.strip() for x in items.split(",") if x.strip()]
        if pins and all(re.fullmatch(r"A?\d+", x) for x in pins):
            arrays[name] = pins
    for name, mode in re.findall(r"pinMode\s*\(\s*(\w+)\s*\[[^\]]*\]\s*,\s*(OUTPUT|INPUT_PULLUP|INPUT)\s*\)", code):
        for pin in arrays.get(name, []):
            modes[pin] = mode
    for pin in re.findall(r"analogWrite\s*\(\s*(\w+)\s*,", code):
        if resolve(pin):
            modes.setdefault(resolve(pin), "OUTPUT")
    for pin in re.findall(r"analogRead\s*\(\s*(\w+)\s*\)", code):
        if resolve(pin):
            p = resolve(pin)
            # analogRead(0) is A0 on an Arduino: a bare channel number means the analog input
            modes.setdefault(f"A{p}" if p.isdigit() and int(p) < 6 else p, "ANALOG_IN")
    return modes


def _board_ids(diagram_parts, library):
    ids = set()
    for part in diagram_parts:
        wtype = part.get("type", "")
        cards = library.find_by_wokwi_type(wtype, part.get("attrs", {}).get("value"))
        if any(card.get("subtype") == "board" for card in cards) or wtype.startswith("wokwi-arduino"):
            ids.add(part["id"])
    return ids


# ---------------------------------------------------------------------------
# Linear algebra (a handful of nodes — plain Gaussian elimination is plenty)
# ---------------------------------------------------------------------------

def _solve_linear(matrix, rhs):
    n = len(rhs)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-18:
            raise ValueError("singular circuit matrix")
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(col + 1, n):
            factor = a[r][col] / a[col][col]
            if factor:
                for c in range(col, n + 1):
                    a[r][c] -= factor * a[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (a[r][n] - sum(a[r][c] * x[c] for c in range(r + 1, n))) / a[r][r]
    return x


# ---------------------------------------------------------------------------
# The circuit
# ---------------------------------------------------------------------------

class _Circuit:
    """Nodes are canonical pins merged by union-find; the board's GND net
    is the 0 V reference. Elements are kept symbolic so the same topology
    can be re-stamped for every switch/LED state."""

    def __init__(self, pairs, diagram_parts, code, library):
        self.library = library
        self.alias_map = checker.board_alias_map(diagram_parts, library)
        self.board_ids = _board_ids(diagram_parts, library)
        self.uf = checker.UnionFind()
        for a, b in pairs:
            self.uf.union(self._canon(a), self._canon(b))

        self.resistors = []   # (name, node_a, node_b, ohms)
        self.leds = []        # (id, anode, cathode, vf)
        self.buttons = []     # (id, node_1, node_2)
        self.slides = []      # (id, node_1, node_common, node_3)
        self.buzzers = []     # (id, node_plus, node_minus)
        self.pots = []        # (id, gnd_end, wiper, vcc_end, ohms)
        self.pirs = []        # (id, vcc, out, gnd)
        self.varres = []      # (id, node_1, node_2, rest_ohms, on_ohms)
        self.pir_powered = {}
        self.unmodeled = []
        for part in diagram_parts:
            pid, wtype, attrs = part["id"], part.get("type", ""), part.get("attrs", {})
            if pid in self.board_ids or "breadboard" in wtype:
                continue
            if wtype in _RESISTOR_TYPES:
                self.resistors.append((pid, self.node(f"{pid}:1"), self.node(f"{pid}:2"), parse_resistance(attrs.get("value"))))
            elif wtype in _LED_TYPES:
                vf = LED_FORWARD_VOLTAGE.get(str(attrs.get("color", "red")).lower(), 2.0)
                self.leds.append((pid, self.node(f"{pid}:A"), self.node(f"{pid}:C"), vf))
            elif wtype in _BUTTON_TYPES:
                self.buttons.append((pid, self.node(f"{pid}:1.l"), self.node(f"{pid}:2.l")))
            elif wtype in _BUZZER_TYPES:
                plus, minus = self.node(f"{pid}:2"), self.node(f"{pid}:1")
                self.buzzers.append((pid, plus, minus))
                self.resistors.append((pid, plus, minus, BUZZER_RESISTANCE))
            elif wtype in _SLIDE_TYPES:
                self.slides.append((pid, self.node(f"{pid}:1"), self.node(f"{pid}:2"), self.node(f"{pid}:3")))
            elif wtype in _VARRES_TYPES:
                rest, on, *_ = _VARRES_TYPES[wtype]
                self.varres.append((pid, self.node(f"{pid}:1"), self.node(f"{pid}:2"), rest, on))
            elif wtype in _PIR_TYPES:
                vcc, out, gnd = self.node(f"{pid}:VCC"), self.node(f"{pid}:OUT"), self.node(f"{pid}:GND")
                self.pirs.append((pid, vcc, out, gnd))
                self.resistors.append((f"{pid} (supply)", vcc, gnd, PIR_SUPPLY_RESISTANCE))
                self.pir_powered[pid] = True
            elif wtype in _POT_TYPES:
                ohms = parse_resistance(attrs.get("value"), POT_RESISTANCE)
                self.pots.append((pid, self.node(f"{pid}:GND"), self.node(f"{pid}:SIG"), self.node(f"{pid}:VCC"), ohms))
            else:
                self.unmodeled.append(pid)

        # Board pins: which nets are driven, and how.
        self.ground = None
        self.supplies = []    # (label, node, volts)
        self.outputs = []     # (pin, node)
        self.pullups = []     # (pin, node)
        self.inputs = []      # (pin, node, mode)
        modes = pin_modes_from_code(code)
        for board in sorted(self.board_ids):
            self.ground = self.node(f"{board}:GND")
            for leg, volts in _SUPPLY_PINS.items():
                label = f"{board}:{leg}"
                if self._pin_is_used(label):
                    self.supplies.append((label, self.node(label), volts))
            for pin, mode in modes.items():
                label = f"{board}:{pin}"
                node = self.node(label)
                if mode == "OUTPUT":
                    self.outputs.append((label, node))
                else:
                    if mode == "INPUT_PULLUP":
                        self.pullups.append((label, node))
                    self.inputs.append((label, node, mode))
        if self.ground is None:
            self.ground = self.node("__gnd__")

        self.nodes = sorted({self.uf.find(x) for x in list(self.uf.parent)} - {self.ground})
        self.index = {n: i for i, n in enumerate(self.nodes)}

    def _canon(self, pin):
        return checker._canonicalize_pin(pin, self.alias_map)

    def node(self, pin):
        return self.uf.find(self._canon(pin))

    def _pin_is_used(self, pin):
        """A supply pin only counts once something else shares its net —
        an unused 5V pin drives nothing and shouldn't add an element."""
        root = self.node(pin)
        return sum(1 for x in list(self.uf.parent) if self.uf.find(x) == root) > 1

    def fixed_nodes(self):
        fixed = {self.ground}
        fixed.update(node for _, node, _ in self.supplies)
        fixed.update(node for _, node in self.outputs)
        fixed.update(node for _, node in self.pullups)
        return fixed

    # --- one DC solve for a given switch + LED state ---------------------

    def _stamp_and_solve(self, pressed, led_on):
        n = len(self.nodes)
        g = [[0.0] * n for _ in range(n)]
        b = [0.0] * n

        def conductance(na, nb, value):
            ia, ib = self.index.get(na), self.index.get(nb)
            if ia is not None:
                g[ia][ia] += value
            if ib is not None:
                g[ib][ib] += value
            if ia is not None and ib is not None:
                g[ia][ib] -= value
                g[ib][ia] -= value

        def source_to_ground(node, volts, ohms):
            """Norton equivalent of a voltage source behind a resistance."""
            i = self.index.get(node)
            if i is not None:
                g[i][i] += 1.0 / ohms
                b[i] += volts / ohms

        for i in range(n):
            g[i][i] += GMIN
        for _, na, nb, ohms in self.resistors:
            conductance(na, nb, 1.0 / ohms)
        for pid, n1, n2 in self.buttons:
            if pressed.get(pid):
                conductance(n1, n2, 1.0 / BUTTON_CLOSED_RESISTANCE)
        for pid, n1, nc, n3 in self.slides:
            conductance(nc, n3 if pressed.get(pid) else n1, 1.0 / BUTTON_CLOSED_RESISTANCE)
        for pid, n1, n2, rest, on in self.varres:
            conductance(n1, n2, 1.0 / (on if pressed.get(pid) else rest))
        for _, end_gnd, wiper, end_vcc, ohms in self.pots:
            conductance(end_gnd, wiper, 1.0 / (ohms / 2))
            conductance(wiper, end_vcc, 1.0 / (ohms / 2))
        for pid, anode, cathode, vf in self.leds:
            if led_on.get(pid):
                gs = 1.0 / LED_SERIES_RESISTANCE
                conductance(anode, cathode, gs)
                ia, ic = self.index.get(anode), self.index.get(cathode)
                if ia is not None:
                    b[ia] += gs * vf
                if ic is not None:
                    b[ic] -= gs * vf
            else:
                conductance(anode, cathode, GMIN)
        for pid, vcc, out, gnd in self.pirs:
            if self.pir_powered.get(pid) and out not in (gnd, vcc):
                # Norton source between OUT and the module's own GND
                volts_out, go = (PIR_HIGH_VOLTS if pressed.get(pid) else 0.0), 1.0 / PIR_OUTPUT_RESISTANCE
                conductance(out, gnd, go)
                io, ig = self.index.get(out), self.index.get(gnd)
                if io is not None:
                    b[io] += volts_out * go
                if ig is not None:
                    b[ig] -= volts_out * go
        for _, node, volts in self.supplies:
            source_to_ground(node, volts, SUPPLY_RESISTANCE)
        for _, node in self.outputs:
            source_to_ground(node, VCC, IO_PIN_RESISTANCE)
        for _, node in self.pullups:
            source_to_ground(node, VCC, PULLUP_RESISTANCE)

        x = _solve_linear(g, b) if n else []
        return {node: x[i] for node, i in self.index.items()} | {self.ground: 0.0}

    def solve(self, pressed):
        """Solve, then check which PIR modules really got enough supply; if
        that changes anything, solve again (a sensor only drives OUT when
        it's powered)."""
        self.pir_powered = {pid: True for pid, *_ in self.pirs}
        for _ in range(3):
            volts, led_on = self._solve_leds(pressed)
            powered = {pid: volts[vcc] - volts[gnd] >= PIR_MIN_SUPPLY for pid, vcc, _, gnd in self.pirs}
            if powered == self.pir_powered:
                break
            self.pir_powered = powered
        return volts, led_on

    def _solve_leds(self, pressed):
        """Piecewise-linear LED iteration: start all off, switch on any LED
        forward-biased past Vf, switch off any conducting LED whose current
        went negative, repeat until stable."""
        led_on = {pid: False for pid, *_ in self.leds}
        for _ in range(4 * len(self.leds) + 2):
            volts = self._stamp_and_solve(pressed, led_on)
            changed = False
            for pid, anode, cathode, vf in self.leds:
                vak = volts[anode] - volts[cathode]
                if not led_on[pid] and vak > vf + 1e-9:
                    led_on[pid] = changed = True
                elif led_on[pid] and (vak - vf) / LED_SERIES_RESISTANCE < 0:
                    led_on[pid] = False
                    changed = True
            if not changed:
                break
        return volts, led_on

    def reaches_fixed(self, start, pressed, led_on):
        """Is `start` tied, through any conducting element, to a node whose
        potential is set by the board? If not, it's floating."""
        edges = {}

        def link(a, b):
            edges.setdefault(a, set()).add(b)
            edges.setdefault(b, set()).add(a)
        for _, na, nb, _ in self.resistors:
            link(na, nb)
        for pid, n1, n2 in self.buttons:
            if pressed.get(pid):
                link(n1, n2)
        for pid, n1, nc, n3 in self.slides:
            link(nc, n3 if pressed.get(pid) else n1)
        for _, e1, w, e2, _ in self.pots:
            link(e1, w)
            link(w, e2)
        for _, n1, n2, _, _ in self.varres:
            link(n1, n2)
        for pid, anode, cathode, _ in self.leds:
            if led_on.get(pid):
                link(anode, cathode)
        for pid, _, out, gnd in self.pirs:
            if self.pir_powered.get(pid):
                link(out, gnd)                  # OUT is actively driven
        fixed, seen, todo = self.fixed_nodes(), {start}, [start]
        while todo:
            node = todo.pop()
            if node in fixed:
                return True
            for nxt in edges.get(node, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        return False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyze(pairs, diagram_parts, code, library=None):
    """Solve the circuit described by hole-level `pairs` (the same
    detected_pairs the checker grades) using the parts in `diagram_parts`
    (a Wokwi diagram's `parts` array) and the pin modes in `code` (the
    sketch the learner will upload — pass engine._adjusted_code so any pin
    substitution is reflected).

    Returns {
      "scenarios": [{"label", "pressed", "leds": {id: {...}}, "pins": {pin: {...}}}],
      "findings":  [{"severity": "hazard"|"warning"|"info", "kind", "component",
                     "message", "scenario"}],
      "hazard": bool,
      "unmodeled": [part ids not simulated],
    }"""
    library = library or load_library()
    circuit = _Circuit(pairs, diagram_parts, code, library)
    button_ids = [pid for pid, *_ in circuit.buttons] + [pid for pid, *_ in circuit.slides] + [pid for pid, *_ in circuit.pirs] + [pid for pid, *_ in circuit.varres]
    slide_ids = {pid for pid, *_ in circuit.slides}
    varres_words = {pid: _VARRES_TYPES[t][2:] for pid, t in ((p["id"], p.get("type")) for p in diagram_parts) if t in _VARRES_TYPES}
    pir_ids = {pid for pid, *_ in circuit.pirs}

    def state_word(pid, on):
        if pid in slide_ids:
            return "at pin 3" if on else "at pin 1"
        if pid in pir_ids:
            return "sees motion" if on else "sees no motion"
        if pid in varres_words:
            return varres_words[pid][1] if on else varres_words[pid][0]
        return "pressed" if on else "released"
    scenarios, findings = [], []
    seen_findings = set()

    def add(severity, kind, component, message, label):
        key = (kind, component)
        if key in seen_findings:
            return
        seen_findings.add(key)
        findings.append({"severity": severity, "kind": kind, "component": component,
                         "message": message, "scenario": label})

    for combo in itertools.product([False, True], repeat=len(button_ids)):
        pressed = dict(zip(button_ids, combo))
        label = ", ".join(f"{pid} {state_word(pid, p)}" for pid, p in pressed.items()) or "steady state"
        volts, led_on = circuit.solve(pressed)
        scenario = {"label": label, "pressed": pressed, "leds": {}, "pins": {}, "buzzers": {}, "pirs": {}}
        for pid, vcc, out, gnd in circuit.pirs:
            supply = volts[vcc] - volts[gnd]
            powered = circuit.pir_powered.get(pid, False)
            scenario["pirs"][pid] = {"powered": powered, "motion": bool(pressed.get(pid)), "supply_v": round(supply, 2),
                                     "out_v": round(volts[out] - volts[gnd], 2) if powered else None}
            if supply < -1.0:
                add("warning", "pir_reversed", pid, f"{pid}'s power is the wrong way round: VCC should go to 5V and GND to GND. "
                    "Swapped, the sensor stays off (and can be damaged).", label)
            elif not powered:
                add("warning", "pir_unpowered", pid, f"{pid} has no power, so it can't sense anything: connect its VCC leg to 5V "
                    "and its GND leg to GND.", label)
        for pid, plus, minus in circuit.buzzers:
            vd = volts[plus] - volts[minus]
            scenario["buzzers"][pid] = {"state": "sounding" if vd > BUZZER_ON_VOLTS else "reversed" if vd < -BUZZER_ON_VOLTS else "silent",
                                        "voltage": round(vd, 2)}
            if vd < -BUZZER_ON_VOLTS:
                add("warning", "buzzer_reversed", pid, f"{pid} is wired backwards: its + leg (pin 2) should go to the Arduino pin and its − leg (pin 1) to GND.", label)

        for pid, anode, cathode, vf in circuit.leds:
            va, vc = volts[anode], volts[cathode]
            current_ma = max(0.0, (va - vc - vf) / LED_SERIES_RESISTANCE) * 1000 if led_on[pid] else 0.0
            if current_ma < LED_OFF_MA:
                state = "off"
            elif current_ma < LED_DIM_MA:
                state = "dim"
            else:
                state = "on"
            scenario["leds"][pid] = {"state": state, "current_ma": round(current_ma, 2),
                                     "anode_v": round(va, 2), "cathode_v": round(vc, 2), "forward_v": vf}
            if current_ma > LED_ABS_MAX_MA:
                add("hazard", "led_overcurrent", pid,
                    f"{pid} would draw about {current_ma:.0f} mA — above a typical LED's {LED_ABS_MAX_MA:.0f} mA "
                    f"absolute maximum, so it would burn out. A series resistor limits it: "
                    f"(5 V − {vf:.1f} V) / 220 Ω ≈ {(VCC - vf) / 220 * 1000:.0f} mA.", label)
            elif current_ma > LED_RATED_MA:
                add("warning", "led_overcurrent", pid,
                    f"{pid} draws about {current_ma:.0f} mA — over its {LED_RATED_MA:.0f} mA rating. "
                    "It will work, but runs hot and won't last as long. A bigger series resistor fixes it.", label)
            elif state == "dim":
                add("info", "led_dim", pid,
                    f"{pid} only gets about {current_ma:.1f} mA, so it will glow faintly. "
                    "A smaller series resistor lets more current through.", label)
            if not led_on[pid] and vc - va > 1.0:
                add("warning", "led_reversed", pid,
                    f"{pid} is in backwards: its cathode (short leg) sits at {vc:.1f} V and its anode "
                    f"(long leg) at {va:.1f} V, so no current flows and it stays dark. Flip it around.", label)

        for pid, n1, n2 in circuit.buttons:
            if n1 == n2:
                add("warning", "switch_bypassed", pid,
                    f"{pid}'s two contact groups are wired to the same connection, so the switch is "
                    "permanently closed — pressing it changes nothing. Put the groups on opposite "
                    "sides of the gap / in different columns.", label)

        for label_pin, node, volts_set in circuit.supplies:
            current_ma = (volts_set - volts[node]) / SUPPLY_RESISTANCE * 1000
            scenario["pins"][label_pin] = {"mode": "SUPPLY", "voltage": round(volts[node], 2),
                                           "current_ma": round(current_ma, 1)}
            if current_ma > SHORT_CIRCUIT_MA:
                add("hazard", "short_circuit", label_pin,
                    f"{label_pin} is connected almost directly to GND — a short circuit. With nothing "
                    "to limit it, far more current tries to flow than the board can supply: the USB "
                    "port's fuse trips (around 500 mA) or the regulator overheats. Something needs to be "
                    "in between, such as a resistor, or an LED with a resistor.",
                    label)

        for label_pin, node in circuit.outputs:
            current_ma = (VCC - volts[node]) / IO_PIN_RESISTANCE * 1000
            scenario["pins"][label_pin] = {"mode": "OUTPUT (HIGH)", "voltage": round(volts[node], 2),
                                           "current_ma": round(current_ma, 1)}
            if current_ma > PIN_ABS_MAX_MA:
                add("hazard", "pin_overcurrent", label_pin,
                    f"Arduino pin {label_pin.split(':')[1]} would have to supply about {current_ma:.0f} mA while HIGH — "
                    f"the chip's absolute maximum is {PIN_ABS_MAX_MA:.0f} mA per pin, so the pin could be permanently "
                    "damaged. Add (or increase) a series resistor.", label)
            elif current_ma > PIN_RECOMMENDED_MA:
                add("warning", "pin_overcurrent", label_pin,
                    f"Arduino pin {label_pin.split(':')[1]} supplies about {current_ma:.0f} mA — above the "
                    f"{PIN_RECOMMENDED_MA:.0f} mA recommended per pin (absolute max {PIN_ABS_MAX_MA:.0f} mA).", label)

        for label_pin, node, mode in circuit.inputs:
            v = volts[node]
            floating = not circuit.reaches_fixed(node, pressed, led_on)
            entry = {"mode": mode, "voltage": None if floating else round(v, 2)}
            if mode == "ANALOG_IN":
                entry["reading"] = None if floating else round(max(0.0, min(VCC, v)) / VCC * 1023)
            elif floating:
                entry["reading"] = "floating"
            else:
                entry["reading"] = "HIGH" if v >= LOGIC_HIGH_MIN else ("LOW" if v <= LOGIC_LOW_MAX else "undefined")
            scenario["pins"][label_pin] = entry
            if floating:
                add("warning", "floating_input", label_pin,
                    f"Pin {label_pin.split(':')[1]} isn't tied to 5V or GND through anything when {label} — "
                    "a floating input picks up electrical noise and reads random values. "
                    "A pull-down resistor to GND (or INPUT_PULLUP) gives it a defined level.", label)

        scenarios.append(scenario)

    return {
        "scenarios": scenarios,
        "findings": findings,
        "hazard": any(f["severity"] == "hazard" for f in findings),
        "unmodeled": circuit.unmodeled,
    }
