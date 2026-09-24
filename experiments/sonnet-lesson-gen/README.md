# Experiment: can Sonnet generate our existing lessons correctly?

**Question:** given only the official Arduino tutorial page (text, circuit image, schematic, sketch) and the exact instructions CircuitQuest's generator sends (`BRIEF.md` = `core.lesson_gen._system_prompt`, whose "Real parts" section is generated from the parts library), does Claude Sonnet produce a lesson that passes every check, describes the same circuit as the hand-made lesson, behaves the same physically, and works for a learner who builds the real circuit?

**Setup (2026-09-23).** No API key on this machine, so the generator was Sonnet run as fresh, isolated agents (one per tutorial) told to read only `BRIEF.md` and their `sources/` files, not the project's lessons, code or tests. The repair loop was reproduced by hand: validation errors were sent back to the same agent verbatim, exactly as `generate_lesson` would. Sources were copied from the `llm-lesson-gen` experiment (a separate copy of this project).

## Scoring: `evaluate.py <run_dir> <reference_id>`

| Check | Pass means |
|---|---|
| validate | `core.lesson_gen.validate` returns no errors: structure, library ids, pin names from the part cards, physical placement (one landing per one-object part, before its legs are wired; no two internal connections sharing a column-half; button straddles the gap; every leg connected to its hole), step/final/diagram consistency, sketch pins wired, physics, full engine dry run |
| equivalent | same circuit as the hand-made lesson under some instance-id mapping, with interchangeable parts either way round; board pins compared by kind (so pin 12 vs 13, GND.1 vs GND.2 don't count) |
| behaves | same LED states/currents (±0.05 mA) and input readings per button state, from `core.physics` |
| cross-play | the hand-made lesson's real wiring, shown at every check, completes the generated lesson |
| adapts | the same with every signal pin moved (13→12, A0→A1, 2→3): must complete, and since `final_check` now compares behaviour with the code the learner will upload, the sketch must follow the pin |

Self-check: all three hand-made lessons score all-pass against themselves; a reversed LED is correctly not equivalent.

## Results (final engine, stable across PYTHONHASHSEED 0/1/3/5)

| Run | Drafts | validate | equivalent | behaves | cross-play | adapts |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| blink-run1 | 1 | ✅ | ✅ | 220 Ω vs 1 kΩ: 11.8 vs 2.9 mA (both safe) | ✅ | ✅ |
| blink-run2 | 1 | ✅ | ✅ | same 220 Ω difference | ✅ | ✅ |
| analog-read-serial-run1 | 2 | ✅ | ✅ | ✅ | ✅ | ✅ |
| analog-read-serial-run2 | 1 | ✅ | ✅ | ✅ | ✅ | ✅ |
| digital-read-serial-run1 | 1 | ✅ | ✅ (button turned round) | ✅ | ✅ | ✅ |
| digital-read-serial-run2 | 1 | ✅ | ✅ | ✅ | ✅ | ✅ |

**6/6 lessons correct; 5/6 on the first draft.** The one repair: analog-read-serial-run1 draft 1 placed the potentiometer by position only, with no leg-to-hole connections (a circuit with no nets). The validator caught it and one repair round fixed it. Run 2 used the updated brief, which states that rule, and passed first time. Blink used the tutorial's 220 Ω; the hand-made lesson uses 1 kΩ. The solver shows the difference and both are safe.

Note: analog-read-serial-run1's agent ran a small script to check its own repair, against instructions. It only read its own output files. Round-2 agents were told explicitly not to run anything and didn't.

## Engine bugs this experiment found (all fixed, with regression tests)

1. **Building ahead** (`tests/test_build_ahead.py`). A learner who wires the whole circuit before pressing "check" was rejected at DigitalReadSerial step 2, because the pull-down was already on the pin-2 column. Now an extra member is allowed if the lesson's own finished circuit puts it in that same net. Anything the design doesn't contain is still refused.
2. **Unannounced pin choice.** Built ahead on pin 12, a step's target silently followed the learner's pin with no `pin_substituted`. The code was right, but the learner was never told. Now recorded and announced.
3. **`LED_BUILTIN`.** Both Sonnet Blinks kept the official sketch's `LED_BUILTIN`. Moving the LED to pin 12 left the shown code driving 13 (the LED would stay dark). The board cards now carry `led_builtin`, and the code adjustment rewrites the constant.
4. **"Complete" but not working.** The final check verified wiring and safety, not behaviour. It now solves the learner's circuit with the code they'll upload and compares LED states and input readings with the lesson's own circuit.
5. **Hash-order dependence.** `_pin_owner` returned whichever component came first in a set, so the same wiring passed or was remapped to a random pin depending on `PYTHONHASHSEED`. Now component-aware and sorted.
6. **Moved pin + building ahead together** failed: the substitution search didn't use the build-ahead allowance, and the planned circuit used scripted rather than actual pins. Fixed.
7. **Turned-round button + moved pin.** The code adjustment looked legs up by their scripted names, missing the orientation lock, so the shown code kept pin 2. Legs are now resolved by physical identity (`_oriented_leg`).

## Files

`BRIEF.md` (instructions given), `sources/` (tutorial pages), `runs/<lesson>-run<N>/` (generated lesson.json / diagram.json / code.ino, as last written), `evaluate.py` (scorer).


## Round 3 and the merged stress test (2026-09-23, later)

**Round 3 (one LLM call, no repair, new brief):** the brief now carries the full Wokwi context (diagram format, what `top`/`left`/`rotate` do and don't mean, wire colours and routing, the Uno's full pin list, the half breadboard's columns/rows/gap/rails, naming) and rules that make pin substitution reliable (declare each pin once as a `...Pin` constant; no pin arithmetic or arrays; no `LED_BUILTIN` for an external part; say "pin 13" in prose). Blink and AnalogReadSerial passed every check from a single call. DigitalReadSerial's agent died on a network error before writing anything.

**Merged stress test (`core/flow_stress.py`, `tests/test_flow_stress.py`):** the engine's own hand-written crazy cases, generated for any lesson and mixed. Dimensions: board (Uno/Mega/Nano via translation), every free pin, changing their mind (moving a pin again later), parts turned round, built ahead, every GND pin, the other leg of a group, other rows, a shifted layout, power rails vs direct, a leg straight onto the Arduino, several persistent mistakes per flow (forgot / wrong kind of pin / one column off / accidental short jumper / one-object part with two legs in one column / reversed LED; each stays until the engine catches it, then gets fixed), hints, going back. Pairwise covering set plus a fixed-seed random sample. Invariants per flow: finishes; every mistake caught before the end and never advanced past; pin moves tracked through chains and announced; orientation tracked; the engine's record equals the physical board; the sketch changes exactly on the pins (checked by an independent "everything that isn't a pin is byte-identical" oracle); physics behaves like the lesson's own circuit.

| | Flows | Failing |
|---|---:|---:|
| Suite run (11 lessons: 3 hand-made + 8 Sonnet) | 8,479 | 0 |
| Deep run (3 seeds × 600 random + pairwise, 11 lessons) | 40,288 | 0 |

The stress test is itself checked: it catches the old add-only tracking and the old whole-word code rewriter.

**Engine bugs this found (all fixed, with regression tests):**
1. **Pin rewriting touched non-pins.** A pin-2 → 3 move changed `delay(2)`, array sizes and "group-2 contact" in clip text; remaps used a raw substring replace. Now `rewrite_pins_in_code` (pin-function arguments, pin constants, "pin N" in comments) and `rewrite_pin_mentions` ("pin N" in prose); distinctive names (A0, LED_BUILTIN) are replaced everywhere. Board translation uses the same functions.
2. **Add-only tracking.** A wire moved or removed after its step stayed in the engine's record forever. Whole-board checks now send `snapshot: true` (the Wiring Bench always does), and a passing snapshot replaces the record.
3. **A pin moved again after its own step** (a change of mind) was followed but never recorded or announced. The final check now records it.
4. **A leg straight onto a substitute pin** (bypass + moved pin) was rejected at multi-leg and single-leg placement steps. Now it's accepted through the same pin-swap search as wiring steps.
5. **Any-orientation build-ahead in the pin-swap search:** a turned-round part + moved pin + built ahead failed.
6. **A removed short kept failing:** the short detector read the stale record. On a snapshot it now judges the board as it is now.
