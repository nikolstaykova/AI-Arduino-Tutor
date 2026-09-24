# Part Library — CircuitQuest

Reference doc for `library/parts/*.json` — same storage principle and schema as [`TOOLS.md`](./TOOLS.md): one flat dataset, same shape for every library item regardless of type. `description` (what it is) and `how_to_use` (how/where it's actually used) apply to every item, tool or part; `tutorial_clip` is the only field reserved for tools. See `PLAN.md` for the loader design and the research log (in git history) for the reasoning trail.

Lessons are built directly on Arduino's own official **Basics** examples (`docs.arduino.cc/built-in-examples/basics/`) — Blink, AnalogReadSerial, DigitalReadSerial, Fade, ReadAnalogVoltage, BareMinimum — rather than an invented curriculum. This is the parts list those six examples actually use, with descriptions grounded in Arduino's own documentation.

---

## Card schema

```json
{
  "id": "resistor-220",
  "type": "part",
  "wokwi_type": "wokwi-resistor",
  "wokwi_value": "220",
  "symmetric_pins": [["1", "2"]],
  "display_name": "220Ω Resistor",
  "aliases": ["220 ohm resistor"],
  "description": "Limits the amount of current allowed to flow through a circuit.",
  "how_to_use": "Placed in series between the Arduino's output pin and the LED's anode, protecting the LED from drawing too much current.",
  "image": "resistor-220.png"
}
```

`wokwi_type` is the bridge to the Wokwi-authored answer key — see the earlier discussion in the research log (in git history). `wokwi_value` is present only where the type alone is ambiguous (currently: resistors, since `wokwi-resistor` covers every resistance value — disambiguated by matching a diagram part's `attrs.value` against this field). Not every part has a Wokwi identity — a USB cable and jumper wires aren't simulated as discrete components in Wokwi (jumper wires are `connections` entries, not `parts` entries), so those two cards simply omit `wokwi_type`.

`symmetric_pins` marks pins on *that part* which are genuinely interchangeable — checked directly against Wokwi's own pin names, not guessed. A resistor's two legs (`"1"`, `"2"`) have no inherent direction, so they're declared symmetric on both `resistor-220` and `resistor-10k`. The potentiometer's `[["GND","VCC"]]` (its two outer legs) was the first case found; `SIG` is deliberately excluded — it's not interchangeable with either. The LED gets no `symmetric_pins` at all — reversing its legs genuinely breaks the circuit (real polarity), which is exactly why this is a per-part *declaration*, not a blanket rule.

`legs_placed_together: true` marks a part whose physical placement seats *more than one* functionally-distinct leg/pin at once — a potentiometer's three legs, a pushbutton's two contact groups, any header-pin sensor/display/driver breakout (HC-SR04, DHT22, an OLED, a shift register). Found via a real gap: `analog-read-serial`'s potentiometer originally had its three legs checked across three *separate* `expected_landing` steps (step-1a/2a/3a) — but physically, placing the part seats all three at once, so this both re-checked the same single physical action three times AND meant a genuine self-short between two of its legs (e.g. GND and VCC landing in the same column) wasn't caught until a much later wiring step, not at the moment of the actual mistake. A part with this flag should get ONE combined `expected_landing` step (a list of its legs, not a single pin — see COMMANDS.md/`core/engine.py`'s `_run_landing_check`), checked and self-short-verified together. A 2-leg part (a resistor, an LED, a buzzer) does *not* need this — its second leg naturally gets verified by whatever it's wired to next, and splitting a 2-leg part was never the redundant-restep problem this solves.

`straddles_center_gap: true` is a more specific sub-fact — real breadboards have a center gap splitting each column into two disconnected halves (see the breadboard-variant note above), and some multi-leg parts *must* be placed spanning it, with pins split across both sides, or their own opposite pins short together in the same row: DIP-packaged ICs (`74hc165`, `74hc595`, `nlsf595`, an ATtiny85), driver breakouts pin-compatible with a DIP footprint (`a4988`), a DIP-switch package, the pushbutton's own 4-leg tactile switch body (already correctly reflected in `digital-read-serial`'s own step-1a clip), a single-digit 7-segment display (pins on top *and* bottom, per its own `how_to_use`), and several breadboard-mountable dev boards (`arduino-nano`, `pi-pico`, `stm32-bluepill`, the ESP32 DevKit variants — unlike the full-size Uno/Mega, which are used off-board via jumper wires and never placed on the breadboard at all). A part can have `legs_placed_together` without `straddles_center_gap` (most header-strip sensor/display modules go in as one block, all pins in their own rows on a single side) but never the reverse. Corrected one real mistake found this way: `servo` was initially (wrongly) marked `legs_placed_together` — a servo's 3 wires connect via jumper wires directly to pins, like a DC motor or battery pack, never plugged into the breadboard at all.

Both flags were audited against a detailed, authoritative real-hardware breakdown the user supplied directly (which parts straddle the gap vs. go in as one block vs. use jumper wires only) rather than guessed from part names alone. A few borderline/cable-connected parts (`led-strip`, `pal-tv`, `biaxial-stepper`, `stepper-motor`, `logic-analyzer`) were deliberately left unmarked pending further verification, per this project's no-fact-without-verification rule.

**The pushbutton's two contact GROUPS are interchangeable (`symmetric_pins: [["1", "2"]]`), but its legs within a group are not a "swap" at all.** An early version of this card declared `[["1.l","2.l"],["1.r","2.r"]]`, which was wrong (checked against `docs.wokwi.com/parts/wokwi-pushbutton`): `1.l` and `1.r` are *permanently* the same metal (one contact group), `2.l`/`2.r` likewise, and pressing the button bridges group 1 to group 2. The within-group fact is handled as a pin-alias fold (`pin_aliases: {"mode": "prefix", "prefixes": ["1", "2"]}`), so using `1.l` where a lesson scripted `1.r` is a silent pass, the same as any Arduino GND pin. What *is* a genuine swap is the two groups themselves: a momentary switch works identically either way round, so 5V may go on group 1 instead of 2 (harmless). Declared on 2026-09-23 after the `llm-lesson-gen` experiment found the engine rejecting a correctly-wired button; `checker._swap_pin` maps a group swap onto physical legs (`1.r` ↔ `2.r`), and the engine's orientation lock keeps it consistent once a step has fixed which group is which.

`pins` (on every part the physics solver models: LED, resistors, potentiometer, pushbutton) lists each Wokwi pin name with what it physically is ("anode — the longer leg…"), and `polarized: true` marks a part that only works one way round (the LED). Together with `legs_placed_together`, `straddles_center_gap`, `symmetric_pins` and `pin_aliases`, these are the physical facts `core/lesson_gen.py` turns into the AI lesson brief's "Real parts" section and checks generated lessons against, so the model and the validator read the same source.

`wokwi_type` can be **either a single string or an array of strings** — some real-world parts correspond to more than one exact Wokwi type. Breadboards are the first confirmed case: Wokwi ships three size variants (`wokwi-breadboard`, `wokwi-breadboard-half`, `wokwi-breadboard-mini`) that are all just "a breadboard" to a learner, same real part. The `breadboard` card lists all three explicitly (`"wokwi_type": ["wokwi-breadboard", "wokwi-breadboard-half", "wokwi-breadboard-mini"]`) rather than picking one and having the mapping silently fail on the others. The loader matches against every string in the list, not just the first.

**Breadboard size varies by variant — matters for column-number range only, never for the letter scheme.** The three variants aren't cosmetically different, the mini/half boards genuinely have fewer *columns* than a full-size one — but every variant uses the exact same a-through-j letter scheme regardless of size; a mini board isn't missing letters, it just has fewer numbered rows to put them on. So the *valid column-number range* for a strip id (e.g. `6t`, `28b`) depends on which variant a lesson's diagram uses, but the letter range never does. This never affects the checker's correctness logic (`board_alias_map`'s "strip" mode just folds on the first `.`, regardless of how many columns exist), but it matters for generating *realistic* test/detection data and for a lesson author picking plausible column numbers.
- Confirmed real-world convention (from the user's own Wokwi exports, already relied on by `core/mock_vision.py`), constant across every variant: each row splits into two disconnected halves at the center gap — the `t` side only uses letters a-e, the `b` side only f-j.
- **Not yet confirmed against Wokwi's own specs** (its per-variant docs pages returned 404 when checked). What's documented below is the general real-world breadboard sizing convention, not Wokwi's own confirmed numbers — Wokwi's three variants most likely map to the first three of these four industry-standard tiers:

  | Real-world size | Tie points |
  |---|---|
  | Full-size | 830/840 |
  | Half-size (→ likely `wokwi-breadboard-half`) | 400 |
  | Mini (→ likely `wokwi-breadboard-mini`) | 170 |
  | Tiny (no confirmed Wokwi equivalent) | ~20–100 |

  Treat this table as a reasonable real-world reference, not a confirmed Wokwi fact, until checked directly in the Wokwi editor (e.g. by counting columns on each variant).

## Parts, sourced from docs.arduino.cc

| Qty | Part | Wokwi type | Used in | Description | How to use |
|---|---|---|---|---|---|
| 1 | **Arduino Uno R3** (or compatible) | `wokwi-arduino-uno` | All six | A microcontroller board built around the ATmega328P, with 14 digital I/O pins (6 usable as PWM outputs) and 6 analog inputs. ([UNO R3](https://docs.arduino.cc/hardware/uno-rev3)) | Connect it to a computer over USB to upload a sketch (program); it then runs that program on its own, reading inputs and driving outputs. |
| 1 | **USB cable** for your board | *(none — not simulated)* | All six, to upload sketches | A cable connecting the Arduino board to a computer. | Plug one end into the board, the other into the computer, to upload sketches and/or power the board while connected. |
| 1 | **Solderless breadboard** | `wokwi-breadboard` | AnalogReadSerial, DigitalReadSerial, Fade, ReadAnalogVoltage, external Blink LED | A reusable prototyping board with a grid of connected holes. | Push component legs and jumper wires into the holes to build a circuit without soldering — holes in the same row/rail are electrically connected. |
| 1 | **10k ohm potentiometer** (linear, "B10K") | `wokwi-potentiometer` | AnalogReadSerial, ReadAnalogVoltage | A variable resistor with a rotating shaft; turning it changes its resistance. ([AnalogReadSerial](https://docs.arduino.cc/built-in-examples/basics/AnalogReadSerial/)) | Wire the two outer pins to 5V and ground, and the center pin to an analog input — turning the shaft changes the voltage read on that pin. |
| 1 | **Momentary pushbutton** | `wokwi-pushbutton` | DigitalReadSerial | A momentary switch with 4 legs in 2 contact groups (`1.l`/`1.r` always tied together, `2.l`/`2.r` always tied together) — pressing bridges the two groups. ([DigitalReadSerial](https://docs.arduino.cc/built-in-examples/basics/DigitalReadSerial)) | Wire one leg from each group: one group to a digital input (with a pull-down resistor to ground), the other group to 5V. Either leg within a group works identically — it's not a wiring choice, they're the same node. |
| 1 | **10k ohm resistor** | `wokwi-resistor` (`value: "10000"`) | DigitalReadSerial | A fixed resistor. | Wired as a pull-down between the pushbutton's input-side leg and ground, so the input pin reads a steady LOW when the button isn't pressed instead of floating. ([DigitalReadSerial](https://docs.arduino.cc/built-in-examples/basics/DigitalReadSerial)) |
| 1 | **LED**, any colour | `wokwi-led` | Fade, external Blink | Lights up when current flows through it in the correct direction. | Connect the longer leg (anode) toward positive/the resistor, and the shorter leg (cathode) toward ground — reversed, it won't light. |
| 1 | **220 ohm resistor** | `wokwi-resistor` (`value: "220"`) | Fade | Limits the amount of current allowed to flow through a circuit. | Placed in series between the Arduino's output pin and the LED's anode, protecting the LED from drawing too much current. ([Fade](https://docs.arduino.cc/built-in-examples/basics/Fade/)) |
| 1 | **1k ohm resistor** | `wokwi-resistor` (`value: "1000"`) | external Blink | Limits the amount of current allowed to flow through a circuit — same job as the 220Ω one, just a higher value (dimmer LED). | Placed in series between the Arduino's output pin (13) and the LED's anode. The real, user-authored Blink diagram (`lessons/blink/diagram.json`) uses 1kΩ specifically, not the 220Ω commonly seen in other Arduino LED examples — both values are valid, this is just what that circuit actually specifies. |
| ~8–10 | **Jumper / hook-up wires** | *(none — a `connections` entry, not a `parts` entry)* | Wiring on the breadboard | A short wire with a connector pin on each end. | Plug the ends into breadboard holes or Arduino pins to make a connection between them. |
| 1–2 | **Alligator clip test lead** | *(none — not simulated)* | Any lesson, if a leg is wired straight to the Arduino (`engine._multi_leg_bypass`/the single-pin bypass), skipping the breadboard | A wire with a spring-jaw clip on one or both ends, for gripping a bare wire or component leg directly. | Clip onto the bare leg, plug or clip the other end onto the target — user-requested addition, found via a real gap: a plain jumper wire's pin end has nothing to grip a bare leg with, so a direct-to-leg bypass connection needs this (solderless) or a soldered joint (advanced, `library/tools/soldering-iron.json`) to actually be physically possible. |

## Notes carried over from the tools discussion

- No `polarity`/`identify_by`-style fields — that kind of fact (e.g. "longer leg is positive") lives inside `how_to_use`, phrased as an instruction, same as everything else. One schema, no type-specific structured fields beyond `tutorial_clip`.
- Parts don't get `tutorial_clip` — no technique to demonstrate, just identification and wiring facts (which `description` + `how_to_use` + `image` already cover).
