# Lesson Library — CircuitQuest

Reference doc for `lessons/<id>/lesson.json`. See [`TOOLS.md`](./TOOLS.md) and [`PARTS.md`](./PARTS.md) for the library items lessons reference, `PLAN.md` for the engine/checker design this schema plugs into, and the research log (in git history) for the full reasoning trail.

Lessons are built directly on Arduino's own official **Basics** examples (`docs.arduino.cc/built-in-examples/basics/`) — not an invented curriculum.

---

## Lesson schema

```json
{
  "id": "fade",
  "title": "Fade an LED",
  "description": "Control an LED's brightness with PWM by fading it up and down using analogWrite().",
  "difficulty": "beginner",
  "board": "arduino-uno",
  "code": "sketches/fade.ino",
  "wokwi_diagram": "fade.diagram.json",
  "tools_used": ["wire-stripper", "needle-nose-pliers"],
  "parts_used": ["breadboard", "led", "resistor-220", "jumper-wire"],
  "steps": [
    { "id": "gather", "phase": "gather", "clip": "Let's gather what you need: a breadboard, an LED, a 220 ohm resistor, and jumper wires.", "items": ["breadboard", "led", "resistor-220", "jumper-wire"] },
    { "id": "step-1", "phase": "build", "clip": "Place the LED across the center gap of the breadboard.", "expected_nets": [["led1:A", "bb1:18t"], ["led1:C", "bb1:18b"]], "strict": false, "hints": ["Look for the two legs — the longer one is positive.", "Straddle the center gap so each leg lands in a different row."] },
    { "id": "upload-code", "phase": "upload", "clip": "Copy this code into the Arduino IDE and click Upload — you should see the LED fade in and out.", "code": "sketches/fade.ino" }
  ],
  "final_check": { "expected_nets": [] }
}
```

*(Simplified for illustration — the real schema in use also includes `expected_landing` steps for the landing/wiring split; see `lessons/analog-read-serial/lesson.json` and `lessons/blink/lesson.json` for actual authored examples, and the `difficulty` section below for how those get shown or skipped.)*

## Four step phases

| Phase | What happens | What checks it |
|---|---|---|
| `gather` | The learner collects the listed parts | Nothing to check yet (a phone-photo parts check is a Phase 7 option) |
| `build` (one or more) | Learner places parts / draws wires on the Wiring Bench (or builds for real), then says "done" | The engine's net check against `expected_nets` / `expected_landing` |
| `upload` | Learner copies the (pin-adjusted) code into the Arduino IDE and uploads it | None — the learner confirms it runs |
| `final_check` | The whole circuit, re-verified from scratch | Net check **plus** the physics solver: a matching circuit that would short the supply or overload a part still fails |

`code` appears twice for two different reasons: at the lesson level it's what Wokwi CI simulates against the circuit at *authoring time*, to confirm the lesson's circuit+code combination actually behaves correctly before it ships; inside the `upload` step it's shown live to the learner.

`final_check.expected_nets` leans toward being auto-derived as the union of every `build` step's nets, rather than hand-maintained — same precedent `PLAN.md` already sets for this field, one source of truth instead of two copies to keep in sync.

Net comparison (both `build` checkpoints and `final_check`) is **strip-agnostic** — every net is reduced to its real component-pin members before comparing, so a learner who wires everything correctly one row off from the scripted position reads as correct, not wrong. See `PLAN.md` Phase 5.

## The six lessons (Arduino's official Basics examples)

| Order | Lesson | Status | Parts introduced | Concept |
|---|---|---|---|---|
| 1 | AnalogReadSerial | ✅ built | breadboard, 10k potentiometer | Analog input, the 0–1023 reading range |
| 2 | Blink (external LED) | ✅ built | breadboard, LED, 1kΩ resistor | Digital output, timing with `delay()` |
| 3 | DigitalReadSerial | ✅ built | breadboard, pushbutton, 10k resistor | Digital input, pull-down resistors |
| 4 | Fade | not yet built | breadboard, LED, 220Ω resistor | PWM / `analogWrite()` |
| 5 | ReadAnalogVoltage | not yet built | breadboard, 10k potentiometer | Converting an analog reading to a real voltage |
| 6 | BareMinimum | not yet built | — (no components) | The minimal valid sketch structure (`setup()`/`loop()`) — no diagram, code-only |

All six are officially tagged "Basics" by Arduino itself — no internal difficulty ranking is invented here, just a build order chosen with the user as each real diagram is supplied.

## `difficulty` — a session setting, not a per-lesson label (PLAN.md)

Every lesson is authored once, at full granularity: a separate landing check for every leg that lands on the breadboard, even one with no wire of its own (e.g. Blink's `led1:A`, confirmed on its own before the `led1:A↔r1:2` net is checked). The learner's own experience level — asked via the `difficulty` command, not assumed, "beginner" (default) or "advanced" — decides at the *engine* level whether those landing checkpoints are shown at all: beginner stops at each one; advanced silently skips them, merging the skipped instruction and hints into the paired wiring step's own. Same underlying checks run either way — nothing about correctness changes, only how many stops the tutor makes along the way. See `PLAN.md` Phase 5/6 and `COMMANDS.md`.

Not every leg needs a landing check to begin with — see Blink below.

## Open questions (tracked in README section 2.5)

- `tools_used`/`parts_used`: hand-written per lesson, or auto-derived by scanning every step's `items`/`expected_nets` for referenced ids (via each part/tool's `wokwi_type`)?
## `requires` and generated lessons

`"requires": ["blink"]` lists the lessons that must be completed before this one unlocks (PLAN.md Phase 5). Lessons generated by `core/lesson_gen.py` are saved as `lessons/gen-<slug>/` with `"generated": true` and no prerequisites, after passing the same validation every hand-authored lesson passes.

**Known data inconsistency:** `digital-read-serial` lists `resistor-10k` in `parts_used` (the official tutorial's value), but its reference `diagram.json` uses a 1 kΩ resistor. Both work as a pull-down (the solver confirms it), but the two should agree.

- `wokwi_diagram`: one file per lesson (the final, complete circuit; each `build` step's `expected_nets` hand-authored as a progressive subset of it), or one file per step?
