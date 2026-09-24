# Command Vocabulary — CircuitQuest

Reference doc for the engine's action vocabulary. See `PLAN.md` Phase 1 for the exact command→action table (how each command behaves per lesson phase) and Phase 6 for how this file gets used once the LLM layer exists.

**Status:** the canonical commands below are active now (Phase 1, exact-match only). The "equivalents" are captured here for later — **not implemented yet**, deliberately deferred until Phase 6, when a model classifies free-form learner speech into one of these canonical actions. This file is meant to seed that classifier's prompt/eval set when the time comes.

---

## `start`
Begins the lesson — enters step 0, plays its intro.
**Equivalents (future):** "begin," "let's go," "ready," "go," "start"

## `done`
Marks the current step complete. Phase-dependent: in `gather` it advances after marking items gathered; in `build` it triggers the real (or `sim`'d) wiring check; in `upload` it just advances, since there's nothing to check — the learner confirms success themselves; in `final_check` it runs the whole-circuit check.
**Equivalents (future):** "ready," "finished," "next," "continue," "ok," "got it," "I did it," "yes"
**Note:** "ready" is ambiguous between `start` and `done` depending on phase — the classifier will need lesson state as context, not just the utterance, to resolve it.

## `previous`
Goes back to the prior step (errors if already at the first step).
**Equivalents (future):** "back," "go back," "wait, go back"

## `repeat`
Replays whichever was shown last — a step's instruction clip, or a tool's `tutorial_clip` video if that's what most recently played. Tracked via engine state (`last_shown`), not just "the current step's clip."
**Equivalents (future):** "again," "say that again," "what," "come again," "repeat that," "sorry?"

## `hint`
Reveals the next hint level for the current step (v1 in `gather`: just re-lists the needed items). On a landing step (`expected_landing`), a hint also proactively warns if a sibling leg of the same component already landed on a breadboard column, per `confirmed_pairs` — e.g. "pot1's GND leg is already in column bb2:6t — use a different column for this leg" — before the learner reuses it by mistake. During `upload`, a hint normally says "No hints available here" — unless an analog-pin substitution happened during wiring (see below), in which case it reminds the learner which `analogRead()` pin their actual code needs.
**Equivalents (future):** "I'm stuck," "help me," "give me a hint," "clue," "I don't know"

## `help <item>`
Looks up an item (tool or part, same shared library index) and shows its card — `description`/`how_to_use` — **text only**. Never plays a video, even if the item has a `tutorial_clip`; that's `video`'s job (below). A learner asking for `help` again on the same item never hijacks `repeat` — see `repeat`'s own note.
**Equivalents (future):** "what is `<item>`," "show me `<item>`," "what's a `<item>`," "explain `<item>`"

## `video <item>`
Plays the item's `tutorial_clip` if it has one. If it doesn't (parts never do — no technique to demonstrate; some tools might not yet either), says so plainly rather than silently doing nothing. Split from `help` on user request, so a learner can ask for just the explanation or just the video, not always get both bundled together. Becomes the new `repeat` target — a one-off `help` text lookup never does (see `repeat`).
**Equivalents (future):** "show me a video," "how do I use `<item>`," "I want to see it," "just explain, no video" (routes to `help` instead)

## `tools`
Lists the library's item ids.
**Equivalents (future):** "what tools," "what do I need," "list tools"

## `sim <label>` / `sim <pin>-<pin> <pin>-<pin> ...`
**Dev/test only, never reaches a real learner.** Two input modes, both feeding the *real* checker rather than skipping it:
- **Canned label** (`sim correct` / `sim wrong` / `sim swapped`) — fabricates a plausible detected-pairs list from the current step's own expected data (`checker.synthesize_detected`/`synthesize_landed`). Quick, but the label itself picks the verdict category in advance.
- **Real hole-level pairs** (`sim pot1:GND-bb2:6b.a uno:GND.3-bb2:6b.c ...`) — literal pin-to-pin pairs, exactly the shape a real vision detection would produce. These go straight through `checker.check`/`check_landed` (board-strip aliasing, connector-dropping, symmetric-pin-swap detection, the works) on the next `done`, so the verdict is *computed*, not chosen. This is how the `board <variant>`-driven plausibility warning gets exercised interactively — a canned label never has a column number to be implausible about. The component side of a pin (before the `:`) also accepts a friendly name in place of the raw diagram id when it's unambiguous in the current lesson — e.g. `sim resistor:1-breadboard:3b` instead of `sim r1:1-bb1:3b` (resolved via `cli.component_name_map`, against the part's library card subtype/aliases/id). A bare column number without the hole letter also works (`bb1:3b` same as `bb1:3b.h`) — the checker only ever compares by column/strip, never the individual hole.

Deliberately *not* a `set_status` shortcut that bypasses the checker — see the research log (in git history) for the reasoning.

## `board <variant>`
Tells the engine which physical breadboard the learner has (`full`, `half`, or `mini`). Errors on an unrecognized variant without changing state. Once set, it feeds `plausibility_warning` (a separate, non-authoritative signal, never folded into the pass/harmless/wrong verdict) when a detected breadboard column number couldn't plausibly fit the stated variant — see `PLAN.md` Phase 5 for the column-estimate caveat. **Phase 1 only asks the learner directly; Phase 3/4's object detection is expected to infer this from the camera instead, at which point `board` becomes an internal event rather than a command the learner types.**
**Equivalents (future):** N/A — this isn't free-form speech to classify, it's a setup question the tutor asks once at the start (Phase 6 may turn it into a spoken Q&A, but the vocabulary stays a fixed choice among known variants, not open classification).

**At the `core/engine.py` level this is still "asked, not assumed"** — `state["breadboard_variant"]` starts `None` and only ever changes via an explicit `board` event; nothing in the engine guesses. **The CLI layers a convenience on top**: right after `start`, it automatically sends `board full` (the largest variant, chosen to minimize false "column doesn't fit" warnings if the guess is wrong) and prints an explicit invitation to correct it — "I'll assume a 'full'-size breadboard for now — if that's not what you have, say `board mini`/`board half`." This is asked prominently, at the very start of `gather`, rather than left as an easy-to-forget optional command — but it's still fully correctable at any point before (or during) building, and the assumption is never written to the saved profile (see below) since it's a per-session guess, not a learner fact.

## `difficulty <level>`
Tells the engine the learner's experience level — `beginner` (the default) or `advanced` — **asked, not assumed**, same precedent as `board`. Every lesson is authored once, at full granularity (a landing check for every leg that lands on the breadboard, even one with no wire of its own). `beginner` stops at every one of those checkpoints, one at a time. `advanced` silently skips landing steps — no accusation, no explanation of why — merging the skipped step's instruction text and hints into the paired wiring step's own, and jumping straight to it. The underlying check is identical either way: skipping the landing stop never skips any actual verification, since the wiring step's own net check is already a complete, independent correctness check on its own (a landing pass was only ever a beginner-mode pinpointing aid, not a requirement). `previous` and `hint` both account for this — `previous` skips backward over landing steps the same way, and `hint` merges in whichever landing step's hints were skipped to reach the current step. See `PLAN.md` Phase 5/6.
**Equivalents (future):** N/A — a setup question, same as `board`, not open classification.

## `arduino <model>`
Translates the current lesson onto a *different board in the same MCU family* than the one it was authored for (see `core/board_translate.py`). Every board card now declares its own `mcu_family` — `"avr"` (Uno/Nano/Mega) or `"esp32"` (DevKit V1/S3/C3/S2/C6) — and translation checks this FIRST: same family, proceed; different family, refuse outright, always, before looking at pins at all. Crossing families (e.g. Uno -> any ESP32) means a different Arduino core, different `#include`s, different `Serial`/Wi-Fi boilerplate — this command only ever rewrites pin literals and prose text, never toolchain-level code, so a cross-family "translation" would silently produce something wrong rather than something merely incomplete. Every current lesson is Uno-authored, so in practice this only ever offers Nano/Mega today — ESP32-family translation is implemented and tested (synthetically; no ESP32-authored lesson exists yet), ready for whenever one does.

Resolves `<model>` through the same alias index every other board lookup uses (a board card's own `aliases`, e.g. `arduino-mega.json`'s `["mega", "arduino mega", "mega 2560"]`) — `arduino` alone resolves to the Uno, which is also every current lesson's own authored board, so it's always a safe no-op answer if the learner just has "an Arduino" without being sure which.

**Asked, not assumed, same precedent as `board`/`difficulty`** — printed once, up front, right after the lesson banner, inviting a correction (`This lesson was authored for the Arduino Uno — if you have a different Arduino (Mega or Nano), say e.g. \`arduino mega\` before \`start\`.`) rather than a blocking prompt, so a scripted/non-interactive session isn't forced through it. Can be said more than once before `start` — each call translates from whichever board is *currently* active, not always the lesson's original author board, so switching back and forth (even chained: Mega -> Nano -> back to Uno) is harmless.

**Only ever safe before `start`.** Once a lesson is underway, `state["confirmed_pairs"]` references the original board's literal pins with no defined way to reinterpret that history under a different board — this is an explicit limitation, not silently handled: the command just refuses ("already started — the board can only be changed before `start`") and leaves the active lesson untouched.

**Feasibility isn't guaranteed even within a family.** A lesson that genuinely needs more pins/capability than the target board has (e.g. a many-pin Mega lesson translated down to a Nano/Uno) is refused with the exact pin(s) that don't fit and why — never a silent partial translation. An unrecognized board name (not a real board card, or missing `pin_domains`) is refused the same way, plainly, with the original lesson kept active either way.

**Known, flagged gap**: each ESP32 variant names its own default serial-monitor pins differently (DevKit V1: `RX0`/`TX0`; S3/C3/S2/C6: bare `RX`/`TX`) — a connection to one of these currently isn't translated (falls through to "keep the literal name," which is wrong across that specific naming boundary). No current lesson wires `$serialMonitor` in its `expected_nets`, so this hasn't caused a real wrong translation yet — documented in `core/board_translate.py`'s module docstring rather than guessed at.

## Remembered settings (local profile, not a command)
`difficulty` (and the learner's name) is saved to a local `profile.json` (via `core/profile.py`) the moment it's set, and auto-applied — quietly, printed as "using your saved difficulty" — right after `start` in future sessions, so the learner isn't asked the same setup question every single time. This is deliberately just a local file for one learner, not a login system — see `PLAN.md` for the "real accounts" scope that was explicitly considered and deferred.

**`board` is deliberately excluded from this.** Difficulty is a property of the *learner* — their experience level doesn't reset from one lesson to the next. Which breadboard is on the desk is a property of *that session* — a learner could easily grab a different one next time — so persisting and auto-applying it would silently reintroduce exactly the "assumed, not asked" behavior `board` exists to avoid. It's always asked fresh, every session, and never written to the profile even if it was set during one.

---

## Not yet assigned a command

- **`pause`** — mentioned in `PLAN.md`'s Phase 6 voice-recognition bullet, not yet in the Phase 1 table. Decide when Phase 6 work starts whether it needs Phase 1 behavior too.


## Whole-board checks (`snapshot`)
A `done` event may carry `"snapshot": true` with `detected_pairs`, meaning "this is the learner's WHOLE board right now", which is what the Wiring Bench and a camera send. On a snapshot:
- **Before the step is judged,** everything earlier steps confirmed must still be on the board. A wire that came loose or a part that was pulled out gets a `connection_lost` action per missing connection (e.g. "The connection from r1's 1 leg to Arduino pin 13 (from step 'step-1b') is gone — it may have come loose. Put it back, then check again."), and the step isn't advanced. These aren't losses: moving a wire to another free pin of the same kind (a change of mind, recorded as a substitution), turning an interchangeable part round, a leg plugged straight onto its Arduino pin, and extra members a later step added.
- **A passing check replaces the engine's record** of confirmed connections with the board as it is, so moved or removed wires are never remembered as present.
- **Shorts are judged on the board as it is now,** so a removed mistake stops failing checks.

- **What changed since the last confirmed board** is compared first, as connections between parts and pins (moving a wire to another hole of the same column is no change):
  - a leg moved to another free pin of the same kind: recorded and announced at this check ("You moved r1:1 from uno:13 to uno:12…");
  - an orientation-locked part turned round: the lock is flipped, with a `part_turned` note;
  - a new connection the lesson's finished circuit doesn't contain, and this step isn't about: `stray_connection`, verdict wrong.
  The final check adds a `board_changes` summary ("Since your last check: …") and then re-proves the whole circuit from scratch as always.

Without `snapshot` (the CLI's `sim`, which sends one step's pairs), none of this applies: the engine can't tell what's missing from partial input.
