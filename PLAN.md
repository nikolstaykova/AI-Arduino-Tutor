# CircuitQuest — Plan of Action

A gamified AI tutor for real electronics: guided Arduino builds in a
simulator (the Wiring Bench) that follows real wiring rules and real
circuit physics, an LLM tutor that explains mistakes from the engine's
verdict and the circuit's actual currents/voltages, and an optional
phone/webcam photo check of a real board. See `README.md` for the
framing and research question, the research log (in git history) for full history.
Library data specs: `TOOLS.md`, `PARTS.md`, `LESSONS.md`, `COMMANDS.md`.

**Pivot note (2026-09-23).** This project started as "Pinpoint", a live
AR-glasses tutor (Xreal One + Eye). The AR layer was dropped: marker
geometry, live hole-level detection, and glasses integration are gone
from this plan. Everything else carried over unchanged. Phase numbers
inside the historical notes of Phases 1–2 below refer to the OLD plan:

| Old phase | Now |
|---|---|
| 1 — UI and skeleton | Phase 1 (unchanged) |
| 2 / 2b — marker geometry, frame source | dropped; the frame-source contract survives in Phase 7 |
| 3 / 4 — object + precise detection | reduced to Phase 7 (single still photo, optional) |
| 5 — the checker | Phase 2 — the wiring engine |
| 6 — voice + LLM layer | Phase 6 — AI tutor |
| 7 — final check | folded into Phases 2 and 4 |
| 8 — glasses integration | dropped |
| 9 — evaluate and write up | Phase 8 |

---

## Guiding principles

- **Code owns state. The LLM never advances a step or decides
  correctness.** The model may only return one of a fixed set of
  actions or explanatory text; a validator checks the action is legal
  for the current phase before anything happens.
- **Nothing is faked.** Pin rules, protocol pins, and electrical
  behavior follow real hardware. If a wiring would work on a real
  bench, it's accepted (and the shown code adapts); if it would damage
  a part, it's wrong even when it "matches the script".
- **Compare nets, not exact holes, when judging correctness.** A
  breadboard strip's five holes are electrically identical.
- **Physics decides safety and behavior; nets decide structure.** The
  net checker answers "is this the circuit the lesson asked for?"; the
  physics solver answers "what does this circuit actually do?"
- **One engine, many front ends.** CLI, Wiring Bench, and (later) the
  photo check all feed the same `handle_event`; none reimplements it.
- **Build and test every layer with no camera and no model** before the
  next one is added.
- **Scripted first, LLM second.** A fully deterministic tutor must work
  end to end before any model call is added.

---

## Phase 1 — UI and skeleton (no vision, no LLM)

**Goal:** click/type through a full lesson, every command works, nothing
depends on a camera or a model.

- [x] Repo layout: `core/`, `lessons/`, `library/{parts,tools}`, `tests/`,
      `logs/` (scaffolded).
- [x] `library.py` — loads `card.json` files into one id+alias index.
- [x] `lesson.py` — loads a `lesson.json`.
- [x] `checker.py` — net comparison (`check(expected, detected)`), plus
      `mock_detected_nets()` standing in for the camera via a `sim`
      command.
- [x] `engine.py` — pure `handle_event(lesson, library, state, event) ->
      (state, actions)`. No I/O inside. State is plain, JSON-serializable
      dict (`step_index`, `phase`, `hints_used`, `last_check`,
      `mock_result`, `started`, `finished`, `last_shown` — see `repeat`
      below).
- [x] `eventlog.py` — append-only JSON-lines log per session, replayable.
- [x] First lesson authored: `lessons/led-blink/lesson.json` — gather →
      3 build steps → final_check.
- [x] Part cards: `breadboard`, `led`, `resistor`, `jumper_wire`.
- [ ] Alias table in front of the engine (`next`/`ready`/`finished` →
      `done`, `back` → `previous`, `again`/`say that again` → `repeat`,
      etc.) — exact-match only for now; this is the seam the LLM
      replaces later.
- [ ] Terminal CLI (`cli.py`): reads a line, normalizes via the alias
      table, calls `handle_event`, prints actions, writes to the event
      log.
- [ ] Checker script (`check_lesson.py`): every `help`/item id referenced
      by a step exists in `library/`; every step has valid
      `expected_nets` pin references; (once hints are used) every step
      that needs one has hint text.
- [ ] Unit tests: one per (phase, command) pair in the table below; a
      random-walk fuzz test asserting no crash and "done" is always
      reachable; a replay test (saved log → fresh engine → same final
      state).
- [ ] Browser page (mirrors the CLI): step text, parts list, command
      buttons, dev panel with `sim` buttons, browser built-in
      text-to-speech reading the clip text. **Note:** camera access
      needs HTTPS/localhost — irrelevant until Phase 7 (photo check) but worth
      remembering when standing up the server.

**Command → action table (v1, exact-match only — no natural-language
aliases yet; that's the seam the LLM replaces in Phase 6, deliberately
deferred until then):**

| Command | gather | build (work) | build (feedback) | upload | final_check |
|---|---|---|---|---|---|
| `start` | enter step 0, play intro | — | — | — | — |
| `done` | mark gathered, advance | run check → advance or feedback | re-run check | advance (no check — learner self-confirms by watching the board) | run full check → complete or feedback |
| `previous` | go to prior step (or error if first) | same | same | same | same |
| `repeat` | replay whichever was shown last — see below | same | same | same | same |
| `hint` | (v1: re-list items) | next hint level | next hint level | n/a | n/a |
| `help <item>` | play card (description/how_to_use), **text only** | same | same | same | same |
| `video <item>` | play the card's `tutorial_clip`, or say plainly there isn't one | same | same | same | same |
| `sim <label>` | n/a | set mock result | set mock result | n/a | set mock result |
| `tools` | list library ids | same | same | same | same |

- **`help` and `video` are separate commands, not one bundled together**
  (user request, added after initially building `help` to auto-play a
  tutorial_clip if the card had one) — a learner should be able to ask
  for just the explanation or just the video, not always get both at
  once. `video` on an item with no `tutorial_clip` says so plainly
  (`"No video available for <name>."`) rather than doing nothing.
- **`repeat` tracks `last_shown`**, not just "the current step's clip" —
  every action that plays a clip or a `tutorial_clip` video updates
  `last_shown: {type: "clip"|"video", ref: "..."}`; `repeat` replays
  whichever it points at. So `repeat` right after `video wire-stripper`
  re-plays the video, not the step instruction — but `help wire-stripper`
  (text-only) never becomes the `repeat` target, even if a video played
  earlier in the session.
- **Video sourcing** (raised when the first real tool video was added):
  self-hosted files are simpler to embed reliably than a YouTube
  iframe player, but downloading and
  redistributing someone *else's* YouTube video without permission is a
  real licensing problem, not just a technical choice — YouTube's own
  embed player is what their terms actually permit for free reuse.
  Realistic options, in order of preference: (1) film original videos —
  fully owned, self-host freely; (2) find explicitly reusable (Creative
  Commons/public-domain) tool-usage videos, downloadable and self-
  hostable; (3) embed via YouTube's real player. Since Phase 6's LLM tutor will need live
  internet anyway, "videos need internet" stopped being a real argument
  either way. The schema doesn't care which is picked — `tutorial_clip`
  is just an opaque string reference; `library/tools/media/wire_stripper.mp4`
  (the first real one, user-provided) is self-hosted per option (1).
- **No separate `set_status` command.** Considered one for manually
  forcing a step to done-correct/done-incorrect/not-yet-done for
  testing, and rejected it: it would bypass the real checker entirely,
  so that logic would never get exercised until the camera exists —
  backwards from this phase's whole goal. `sim <label>` already covers
  it and stays closer to the real production path (fake the earliest
  thing that doesn't exist yet — camera detection — let everything
  downstream, including the checker, run for real). `sim`'s label
  vocabulary should match the checker's actual verdict/feedback
  categories once Phase 5 defines them (`correct`, `wrong_strip`
  /harmless, `missing_connection`, `wrong_polarity`, etc.) rather than
  being freeform strings. "Not yet done" needs no label at all — it's
  just the state before `done` has been called.

**Done when:** you can run `start → done (gather) → sim wrong_strip →
done → hint → sim correct → done → previous → help resistor → sim correct
→ done → done (upload) → done (final_check)` and every step behaves as
documented, with no crashes and a clean replay from the log.

---

---

## Phase 2 — The wiring engine (deterministic, no AI)

**Goal:** turn Wokwi's answer key + a detected-connections graph into a
pass/fail/harmless verdict with a specific reason.

- [ ] Author each lesson step's circuit in Wokwi; export `diagram.json`
      **at authoring time only** — this is the frozen answer key, not
      something re-simulated per learner action.
- [ ] Confirm (empirically, on a trivial diagram) whether Wokwi emits
      explicit connection entries for parts plugged directly into
      breadboard holes, or only `left`/`top` coordinates — this decides
      whether hole assignment must be computed by hand for the answer
      key too.
- [ ] Write each step's `expected_nets` as component-pin pairs
      (`["r1:2","led1:A"]`), independent of which physical hole realizes
      them.
- [ ] Strip map: every hole name → strip id (`18t`, `18b`, `bn`, `bp`,
      …), accounting for the center gap and rail continuity on the real
      board.
- [ ] Union-find over detected connections → detected nets (per Phase
      4's output).
- [ ] **Net comparison must be strip-agnostic**: before comparing, reduce
      every net (expected and detected alike) to just its real
      component-pin members, discarding the anonymous breadboard-strip
      label used to realize it. A strip's job is only to join things —
      its specific name is never meaningful to the circuit. Comparing
      raw net contents (including strip ids) would wrongly fail a
      learner who wired everything correctly one row over from the
      scripted position.
- [ ] Compare detected vs. expected partitions (post strip-reduction) →
      `pass` / `harmless deviation` / `wrong`, with specific missing/
      extra connections named (already stubbed in `checker.py`). Same
      component-pin membership on a different strip is exactly the
      "harmless deviation" case below, not a separate mechanism — it
      falls out of the reduction for free.
- [ ] Per-step strict/flexible flag (does this step require the exact
      target hole, or just the right net?).
- [ ] **Symmetric pin pairs, per part — classified as harmless, not
      silent.** Some parts have two pins that are truly interchangeable
      — a potentiometer's two outer legs can go to 5V/GND in either
      order and the circuit still works correctly (it only flips which
      way the reading increases as the shaft turns; nothing breaks, no
      lesson claim depends on the direction). This is different from
      LED polarity, where swapping legs genuinely breaks the circuit.
      Mark symmetric pairs on the part's own card (e.g. potentiometer:
      `GND`/`VCC`, via `symmetric_pins`) and treat a swap the same way
      as the different-strip-same-net case just above: **harmless
      deviation**, not a silent equivalent and not "wrong" — flagged to
      the learner, doesn't block progress. The explanation of what it
      actually means ("this still works, it just reverses which way the
      reading changes as you turn it") is exactly the kind of thing the
      Phase 6 LLM layer generates for any harmless deviation — no new
      mechanism needed, this is one more case feeding the existing one.
- [ ] Feedback text: global templates keyed by error type (missing
      connection, extra connection, wrong polarity, missing part,
      harmless deviation), not per-step hand-written text.
- [x] Wire real `check()` into the engine, replacing `mock_detected_nets`
      — keep `sim` around as a dev/test-only override.
- [x] **Board pin-aliasing implemented** (`checker.board_alias_map` /
      `BOARD_PIN_ALIAS_RULES`): any Arduino GND pin folds to one canonical
      node ("prefix" mode); a breadboard hole like `6b.f` folds to its
      strip id `6b` ("strip" mode), dropping the row-letter that only ever
      picks one of five physically identical holes. This is what lets
      `expected_nets` be authored/derived without a human manually
      reasoning through which holes share a strip.
- [x] **`derive_expected_nets(diagram)` implemented**: turns a raw Wokwi
      diagram (breadboard hops and all) into component-pin-only
      expected_nets automatically, via union-find + alias folding +
      dropping connector-only pins. Verified against the real
      `analog-read-serial` diagram — matches the hand-written
      `lesson.json` exactly. Available as an authoring-time consistency
      check even while `expected_nets` are still hand-written.
- [x] **Connector-only pins must be dropped from *both* sides before
      comparing, not just at authoring time.** Found by feeding the
      checker realistic hole-level detected data (mimicking a breadboard-
      routed real vision detection) instead of only the already-reduced
      `sim` shortcut: union-find correctly merges `{pot1:GND, bb2:6b,
      uno:GND}` into one net when routed through a breadboard, but
      comparing that 3-member net directly against the 2-member expected
      `{pot1:GND, uno:GND}` always failed — frozensets of different sizes
      are never equal. Every breadboard-routed connection read as `wrong`
      even when exactly right. Fixed: `check()` now takes
      `connector_component_ids` (from `checker.connector_ids`) and drops
      those pins from both expected and detected nets before comparing —
      not just in `derive_expected_nets`. `engine.py`'s `_run_check`
      computes and passes this alongside `alias_map` on every check.
- [ ] **Methodology note for whatever assembles `final_check`'s detected
      data (real vision, later, or a hand-built test scenario now)**: it
      must be one fresh, self-consistent snapshot of the whole board as it
      currently stands — never a naive concatenation of separate
      per-step detections. Concatenating step-1's and step-2's detected
      pairs can accidentally claim the same physical leg is in two
      different places at once (caught by exactly this mistake while
      testing) — which the checker correctly rejects as `wrong`, but for
      the right reason (self-contradictory input), not because anything
      about the circuit itself is actually wrong.
- [x] **Which breadboard variant the learner has is asked, not assumed —
      for both regular checks and `final_check`.** A lesson's own
      `diagram.json` is authored against one variant (e.g. `mini`), but a
      real learner could have a `full`, `half`, or `mini` board on their
      desk, and nothing about the checker's correctness logic depends on
      knowing which — `board_alias_map`'s "strip" mode folds a hole to its
      strip regardless of column count. What the variant *does* inform is
      a separate, non-authoritative **plausibility warning**: if the
      detected data names a column number that couldn't fit the stated
      variant (e.g. column 40 on a declared `mini`, ~17 columns
      estimated), that's worth surfacing to the learner as a "worth
      double-checking" note — but explicitly *not* folded into the
      pass/harmless/wrong verdict itself, since the column-count estimates
      per variant are an unverified real-world convention, not a confirmed
      Wokwi spec (see `PARTS.md`). Implemented as a new `board <variant>`
      command (`core/engine.py`'s `BREADBOARD_VARIANTS`,
      `_breadboard_column_number`, `plausibility_warning`) that sets
      `state["breadboard_variant"]`, plus a `plausibility_warning` action
      emitted alongside (never instead of) the normal `feedback`/advance
      actions on every check once a variant is known. Unset by default —
      no variant means no warning is possible, never a wrong guess.
      **Phase 1 evolution note (explicitly confirmed by the user — "rn we
      will ask later on the object detection will do that for us"):**
      asking the learner directly is the correct *current*-phase
      approach, precisely because Phase 3/4's object detection doesn't
      exist yet. Once it does, identifying which breadboard variant is
      physically present becomes something the vision pipeline infers
      from the camera feed instead — `board` then stops being a command
      the learner types and becomes an internal event the detection layer
      emits, with the rest of the pipeline (the warning logic, the state
      field) needing no change. Same "ask now, detect later" boundary
      already established by `core/mock_vision.py` for connection data.
- [x] **A wiring step is two physical actions, not one — split
      accordingly.** What used to be one build step ("connect the
      potentiometer's GND leg to the Arduino's GND pin") checked as a
      single net comparison, but a real learner does this as two separate
      wire insertions through the breadboard: leg -> some breadboard hole,
      then that same column -> the Arduino pin. A single end-of-net check
      can't tell the learner *which* of the two wires is wrong. Each
      former build step (`step-1`/`step-2`/`step-3`) is now two lesson
      steps: an `*a` **landing** step (`expected_landing`: a single pin —
      "is this leg plugged into the breadboard at all yet, any hole")
      followed by a `*b` **wiring** step (`expected_nets`, unchanged
      mechanism — re-checks the *whole* net against the current snapshot,
      which naturally fails if the second wire lands on a different strip
      than the first; no lookup needed, that falls out of the existing
      union-find for free).
  - New checker primitive: `checker.check_landed(pin, detected_pairs,
    connector_component_ids, symmetric_pairs=None)` — not a net-equality
    comparison like `check()`, just "does this pin (or, harmlessly, its
    declared symmetric counterpart) touch any hole belonging to a
    connector-only component." Returns the same
    `{"verdict", "missing"}` shape as `check()` so callers don't branch on
    which kind of check ran. Paired with `synthesize_landed` (the `sim`
    analogue of `synthesize_detected` for this check type).
  - `engine._run_landing_check` mirrors `_run_check` (shares the new
    `_resolve_detected` helper below) and is dispatched whenever the
    current step has `expected_landing` instead of `expected_nets`.
    `final_check` is untouched — it always re-verifies the whole circuit's
    full net set in one check, same as before the split.
  - **`find_confirmed_pin` now searches most-recent-first.** A pin can
    appear in more than one `confirmed_pairs` entry now (once from its own
    landing check, again from the wiring step's net check), so the later,
    more complete confirmation must win over the earlier breadboard-only
    landing fact when a future step asks "where did this actually end up."
- [x] **`sim` accepts real hole-level pairs, not just a canned label**
      (user request — the canned `correct`/`wrong`/`swapped` labels always
      picked the verdict category in advance, which couldn't exercise the
      landing/wiring split or the `board`-driven plausibility warning
      realistically). New shared `engine._resolve_detected` helper:
      explicit `detected_pairs` on the event wins, then a raw pairs list
      stashed by `sim` (`state["mock_result"]` as a list, not a string)
      wins, then falls back to label-based synthesis. The literal pairs go
      through the *same* `checker.check`/`check_landed` call a real
      detection would — the verdict is computed, not chosen. CLI syntax:
      `sim pot1:GND-bb2:6b.a uno:GND.3-bb2:6b.c ...` (space-separated
      `pinA-pinB` tokens); `sim correct`/`wrong`/`swapped` unchanged.
- [x] **200-case test matrix** (`tests/test_sim_and_board_200.py`)
      covering all 6 build sub-steps (3 landing + 3 wiring) × 4 modes
      (correct in-range column, correct out-of-range column, empty/wrong,
      harmless symmetric-swap) × 4 stated-board states (full/half/mini/
      none) end to end through the real engine — confirming both the
      computed verdict and the plausibility warning's presence/absence/
      content are right in every combination.
- [x] **"Taken hole/pin" question, resolved without new gating logic.**
      User asked whether taken breadboard holes/Arduino pins need explicit
      reservation tracking. They don't, for correctness: union-find
      already merges anything sharing a literal hole/pin into one net, and
      a merged net that doesn't exactly equal an expected net is already
      caught as `wrong` — accidental hole/pin sharing was never a gap.
      What *was* missing was better use of that fact:
  - **`conflicts` field on a `wrong` verdict** — `checker.check`/
    `check_landed` now report, per missing pin, what it's *actually*
    wired to right now (if anything), via `_actual_net_for_pin`/
    `_conflicts_for_missing`. A pin that's simply unconnected gets no
    entry (that's the plain missing-connection case); a pin tied to the
    wrong thing names it. Threaded through `engine._run_check`/
    `_run_landing_check`'s `feedback` action and rendered in `cli.py`.
  - **Proactive "that spot's taken" hint** (`engine._occupied_column_note`)
    — on a landing step, `hint` now checks `confirmed_pairs` for any
    sibling leg of the same component already confirmed on a breadboard
    column, and warns before the learner reuses it, e.g. "pot1's GND leg
    is already in column bb2:6t — use a different column for this leg."
    Purely additive (an extra sentence on the existing hint tier) — no new
    hint-tier bookkeeping, existing hint tests unaffected.
  - Explicitly *not* built: an authoring-time diagram.json occupancy
    check (out of scope per the user's own prioritization) and full
    resource-reservation state (unnecessary — see above).
- [x] **Exhaustive (not sampled) variation coverage for one connection**
      (`tests/test_exhaustive_wire1_variations.py`, user request — "test
      all possible variations ... see if only the correct ones pass").
      Enumerates every *meaningfully distinct* choice for wire #1 (the
      potentiometer's GND leg) rather than every literal hole number,
      since column number and row-letter are already proven never to
      matter: for the landing half, all 3 pot pins × 3 destinations (9
      cases); for the wiring half, all 3 pot pins × 6 Arduino targets × 3
      routings (54 cases) — confirming only GND/VCC-to-any-GND-pin,
      direct or same-strip, ever passes or is harmless, and everything
      else is `wrong`. A second, independent cross-check
      (`test_only_the_documented_correct_combinations_actually_pass_or_harmless`)
      derives the accepted set from the verdict tables themselves and
      compares it against the declared symmetric pins/alias rules.
- [x] **Mini-board-specific exhaustive matrix, down to every physical hole**
      (`tests/test_mini_board_exhaustive.py`, user follow-up — "test all
      combos with a mini board," then "also the breadboard possible
      holes"). States `board mini` for real and always feeds literal
      hole-level pairs through `sim`'s real-pairs path — the actual
      evaluation algorithm decides the verdict, never a canned label
      standing in for it (explicitly confirmed: "we will use the
      evaluation algorithm not the old sim style test"). 1,089 cases:
      every one of the mini board's 170 physical holes (17 columns × 2
      sides × 5 letters) lands `pot1:GND` cleanly; every one of the 850
      hole-pairs *within* a strip (any letter to any letter, same column
      and side) wires correctly, not just a sampled letter; same column
      number on opposite sides of the gap (`Nt` vs `Nb`) is wrong at every
      valid column; columns past the ~17 estimate still pass/fail
      correctly but do warn (with a boundary check that 17 itself does
      not); and GND/VCC/SIG pot-pin discrimination holds at both ends of
      the valid range. 1,539 tests passing project-wide.
- [x] **Landing check accepts a direct wire to the correct final pin as a
      bypass, not a wrong** (user-caught gap: "wired straight to A0, not
      the board" as a test case was actually wrong for two independent
      reasons at once — wrong pin *and* no breadboard — which hid that
      `check_landed` also rejected wiring straight to the *correct* pin,
      e.g. `pot1:GND` directly to `uno:GND.1`, even though that's
      electrically fine; the breadboard is this lesson's chosen method,
      not an electrical requirement). User's resolution: allow it, but
      explain the effect, warn about it, and track it — not silently
      identical to the taught (breadboard-routed) method.
  - `engine._run_landing_check`: if the plain `check_landed` result is
    `wrong`, it now also tries the *paired wiring step's own*
    `expected_nets` (`lesson.step(state["step_index"] + 1)`) directly
    against the same detected data via the existing `checker.check()` —
    reusing all of its machinery (aliasing, symmetric-swap, connector-
    dropping) rather than duplicating any of it. If that succeeds
    (pass/harmless), the bypass is accepted and that result is used.
  - New `breadboard_bypassed` action explains the deviation in plain
    language; new `state["breadboard_bypasses"]` list tracks every
    occurrence (`{"pin", "step"}`); a symmetric-pin swap still layers a
    `harmless` feedback on top, independently; a direct wire to a
    genuinely wrong pin is unaffected — still `wrong`, no bypass recorded.
  - **Known follow-up, not yet fixed**: the paired wiring step's own clip
    text (e.g. "run a *second* wire from that same column...") still
    assumes the breadboard hop happened, and reads oddly after a bypass —
    a minor pedagogical rough edge, not a correctness bug (the wiring
    step's own check still passes instantly on the same already-complete
    data). Worth revisiting if/when step clips become state-aware.
- [x] **Wiring to a different analog pin (A0 vs. A1) is a tracked
      substitution, not wrong — and the shown code is adjusted to match**
      (user follow-up question: "wiring into A0/A1 ... would it be an
      issue, or do we just need to keep track and change the code too").
      Unlike GND pins (genuinely one internal net), A0–A5 are distinct
      signals — wiring to a different one *is* a real functional break
      unless the sketch's own `analogRead()` call is updated to match. So
      this isn't the same kind of equivalence as GND-pin-aliasing or the
      breadboard bypass; it required actually tracking the deviation
      through to the code the learner is shown.
  - `engine._try_analog_pin_substitution`: if a wiring check against a
    specific analog pin (`ANALOG_PINS = {A0..A5}`) fails, tries the same
    net with each *other* analog pin substituted in, reusing
    `checker.check()` wholesale; a pass/harmless match is accepted, with
    the substitution recorded in new `state["pin_substitutions"]`
    (`{"original", "actual", "step"}`) and a `pin_substituted` action
    explaining the effect. Applies uniformly to both a regular wiring step
    and `final_check` (same shared `_run_check`).
  - **The `upload` step now actually shows code** — previously
    `lesson.code_path()` existed but nothing ever loaded or displayed it;
    the clip just said "copy this code" with nothing to copy. New
    `show_code` action fires when entering the upload phase, with
    `engine._adjusted_code` textually substituting every tracked pin
    change into the loaded `code.ino` content (both the functional
    `analogRead()` call and its explanatory comment) — so what's shown
    matches what was actually wired, not the lesson's original assumption.
  - `hint` during `upload` (previously always "No hints available here")
    now surfaces the pin substitution as a reminder if one occurred
    ("use `analogRead(A1)` instead of `analogRead(A0)`"), and still
    declines cleanly when there's nothing to hint about.
  - **Found and fixed while verifying this** (user asked directly whether
    re-showing the code would reflect what was actually wired):
    `repeat` at the upload phase only ever replayed the instructional
    clip text ("copy this code...") — it never re-emitted `show_code` at
    all, so a learner had no way to see the code again once past the
    initial transition, let alone confirm it matched their wiring.
    `repeat` now also re-emits `show_code`, recomputed fresh via
    `_adjusted_code` each time (not a cached snapshot from when upload
    was first entered) — so it always reflects the current
    `pin_substitutions`.
  - **Second real gap, user-caught, in the substitution search itself**:
    it originally considered each candidate alternate pin in total
    isolation, with no awareness that a *different* real component might
    already need that exact pin — either already confirmed (an earlier
    connection), or scripted for later (a future step's own
    `expected_nets`). Either way, silently accepting the substitution
    would set up a genuine electrical conflict (two components sharing
    one physical Arduino pin), not a harmless deviation. Fixed with two
    new checks in `_try_analog_pin_substitution`:
    - `_analog_pin_owner(confirmed_pairs, pin, alias_map,
      connector_component_ids)` — traces through any breadboard hop (a
      confirmed pair stores a pin next to a *hole*, not the far
      component, when routed through the board) to find which real
      component, if any, already owns a candidate pin; skips it unless
      the owner is the *same* component being checked (so a step can
      still be legitimately re-confirmed with its own prior pin).
    - `_reserved_analog_pins(lesson, exclude_component)` — scans every
      other step's own `expected_nets` (and `final_check`'s) for analog
      pins already committed to a *different* component, regardless of
      lesson order; a substitution never offers one of these. This
      catches the mistake at the step where it actually happened, rather
      than deferring a confusing `wrong` to whichever step tries to use
      that pin correctly second.
    Verified both with a synthetic two-analog-pin-connection scenario
    (this lesson only has one — SIG↔A0 — so the conflict case can't occur
    in real content yet, but the mechanism is lesson-agnostic and ready
    for one that does).
- [x] **Superseded by user feedback, same session**: the
    `_reserved_analog_pins` check above, as first built, *refused* the
    earlier step's substitution outright when it collided with a later
    step's own scripted pin — correct but not what was actually wanted.
    User's real ask: accept the earlier step's choice (it's the learner's
    actual wiring, nothing to gain by rejecting it), and have the *later*
    step silently reassign itself around the collision instead — no
    accusation, no forced redo, just an instruction that already reflects
    the right target. Removed the reserved-pin block from
    `_try_analog_pin_substitution` (an earlier step's own substitution
    search no longer refuses a pin just because another step also wants
    it) and built the actual mechanism for the later step's side:
    - `_compute_pin_remap(lesson, state, step)` — when a step is entered,
      checks whether its own scripted analog-pin target is already
      confirmed (via `_analog_pin_owner`) as belonging to a *different*
      component; if so, picks a genuinely free replacement (still using
      `_reserved_analog_pins`, but now only to choose a *good*
      replacement, never to block the earlier step). Returns
      `{"original", "actual", "component"}`.
    - `_enter_step` computes this once per step (cached in new
      `state["pin_remaps"]`, so re-entering the same step via `previous`
      doesn't recompute or duplicate it) and silently substitutes the new
      pin's leg into the step's own clip text — the learner sees the
      corrected instruction, never an explanation of why it changed.
    - `_apply_pin_remaps(state, expected_pairs)` substitutes every active
      remap into whatever `expected_nets` a check runs against — threaded
      into the regular build-step dispatch, the landing-check bypass
      fallback, and `final_check`, so every check validates against the
      pin the learner is actually being told to use.
    - **Reaches *any* later step, not just the immediately next one** —
      verified with an unrelated step (a digital pin, no analog
      involvement) sitting between the deviation and the affected step;
      the remap still applies correctly, since `_compute_pin_remap` runs
      fresh every time any step is entered, checking current
      `confirmed_pairs` at that moment, not a one-shot fix targeted at
      "the next step."
    - `_adjusted_code` reworked to derive every pin substitution from
      **ground truth** (`confirmed_pairs`, resolved per-component via
      `_final_analog_pin_for_component`) rather than chaining
      `pin_substitutions`/`pin_remaps` as sequential text replacements —
      the naive sequential version corrupted output whenever one change's
      target text coincided with another's source (e.g. a remap's A2→A1
      also clobbering an unrelated component's newly-A2 text). A
      placeholder pass keeps every replacement independent regardless of
      how many are live at once.
    - Verified end to end with a synthetic two-component lesson: LED
      wired to A2 instead of its scripted A0 (accepted, tracked as a
      substitution); the *sensor* component's own later step — several
      steps away, with an unrelated digital-pin step in between —
      silently reassigns from its scripted A2 to A1 the moment it's
      entered, before the learner even sees it; the final code correctly
      shows `analogRead(A2)` for the LED and `analogRead(A1)` for the
      sensor, with zero cross-contamination.
- [x] **`check()`'s `wrong` report now names the closest-matching
      variant, not always the plain unswapped one** — found by stress-
      testing against a real, larger Wokwi diagram the user supplied (an
      Arduino Uno + buzzer + 8 pushbuttons sharing one GND rail, all with
      independently declared symmetric pins). With several components
      each independently swappable, a genuine mistake on *one* of them
      used to make `missing` also list every *other*, already-fine
      harmless swap as if it were broken too — because `check()` only
      tried "no swaps at all" or "every declared swap at once" as
      candidates, and fell back to the unswapped baseline for its error
      report whenever neither fully matched. Fixed: every symmetric
      variant's own `missing` count is computed, and the `wrong` report
      uses whichever variant comes closest (fewest missing nets) — so a
      real error on one component no longer drags unrelated, correctly-
      swapped components into the diagnostic. Verified on the 8-button
      diagram: 3 simultaneous harmless deviations (two leg-swaps, one
      alternate GND pin) plus a genuine wrong-pin mistake elsewhere now
      reports `missing` as exactly that one broken connection, nothing
      else.
- [x] **Full end-to-end session tests, each its own case, including a real
      `final_check`** (user request — verify "the keeping track and
      everything," with each test being a whole session, not an isolated
      step). `tests/test_full_session_variations.py`:
  - 16 full successful sessions (2³ routing combos — breadboard or
    direct-bypass, independently per connection — × power-swap on/off,
    applied consistently to GND/VCC together since swapping just one
    would mean the shared potentiometer leg serving two Arduino pins at
    once, which the checker correctly calls `wrong`, not a meaningful
    variation to test). Each session is checked at all 6 build sub-steps
    *and* a fresh, independent `final_check`, plus its exact
    `confirmed_pairs` and `breadboard_bypasses` contents — not just
    whether it finished. Verdict tally across all 16: 72 `pass`, 40
    `harmless`, 0 `wrong`, 24 `breadboard_bypassed` — 112 individually
    verified classifications.
  - 4 blocked sessions (wrong pin, wrong Arduino target, nothing
    connected, wrong strip) confirming the session halts at the exact
    failing step and `confirmed_pairs` holds only what was genuinely
    confirmed before the failure.
  - 3 late-breaking-fault sessions where every build step reports correct
    but `final_check`'s own fresh snapshot is disconnected, misrouted, or
    shorted — all caught as `wrong`, reconfirming `final_check` never
    trusts build-phase history, with more independent instances of the
    fault than the single existing regression test in `test_engine.py`.
  - 1,567 tests passing project-wide.
- [x] **`difficulty` — a session setting deciding how many stops a lesson
      makes, not a per-lesson content fork.** User request: an experienced
      learner shouldn't be walked through every landing checkpoint a
      beginner needs. Resolved by authoring every lesson ONCE, at full
      granularity, and letting the *engine* — not the lesson content —
      decide whether to stop at every `expected_landing` step or silently
      skip it. Asked via a new `difficulty <level>` command (`beginner`,
      the default so every existing lesson/test behaves exactly as
      before, or `advanced`), same "asked, not assumed" precedent as
      `board`. See `COMMANDS.md`.
  - `engine._skip_landing_steps_for_advanced`: in advanced mode, whenever
    `state["step_index"]` lands on a step with `expected_landing`, it's
    advanced past automatically (looped, in case of consecutive landing
    steps), collecting each skipped step's clip text and hints along the
    way. `_advance_or_finish` merges the collected clips into one
    instruction and stores the collected hints in new
    `state["merged_hints"]`, which `hint` prepends ahead of the landing
    step's own hints.
  - `previous` mirrors this going backward: repeatedly steps back over
    any landing step in advanced mode, so it always lands on the same
    "real stop" a forward walk would have used, not an intermediate one.
  - **No correctness is lost by skipping the landing stop** — the wiring
    step's own net check was always a complete, independent verification
    on its own; the landing pass was only ever a beginner-mode pinpointing
    aid (which of the two wires is wrong), never a requirement. One
    consequence, correctly not special-cased: the breadboard-bypass
    feature becomes moot in advanced mode, since there's no landing check
    left to reject a direct-to-Arduino wire in the first place — it just
    passes via the plain wiring check.
  - Verified end to end on `analog-read-serial`: advanced mode collapses
    all three landing/wiring pairs, `previous` correctly returns to
    `step-1b` (not `step-2a` or `step-1a`) from `step-2b`, a direct wire
    passes with zero bypass noise, and a full session still reaches
    `finished`. 1,591 tests passing.
- [x] **Blink (external LED) lesson built** — the first lesson with a
      genuinely different topology from `analog-read-serial`: one of its
      three connections (`led1:A ↔ r1:2`) is **component-to-component**,
      not component-to-Arduino, and is realized purely by inserting the
      LED into the resistor's own breadboard column — no separate jumper
      wire at all. This surfaced a real design question, discussed with
      the user before building: a rigid 2-terminal part (resistor, LED)
      has both legs land on the board *simultaneously* the instant it's
      inserted, unlike the potentiometer's three independent, separately-
      wired legs. Resolved: only add a landing sub-step where there's an
      actual separate wire-pulling action to pinpoint; a connection formed
      purely by correct component placement (no wire) is just a plain
      wiring check, since there's no second physical action to distinguish
      it from. Concretely: `step-1a`/`step-1b` (landing + wiring for
      `r1:1↔uno:13`, a real wire) → `step-2` (`led1:A↔r1:2`, no landing at
      all — the shared column *is* the connection) → `step-3`
      (`led1:C↔uno:GND`, no landing either — it rode along with `led1:A`'s
      placement in step-2). `checker.derive_expected_nets` on the real,
      user-authored `diagram.json` matches the hand-written `final_check`
      exactly. New `library/parts/resistor-1k.json` (the diagram's actual
      resistor value — 1kΩ, not the more commonly-seen 220Ω — both valid,
      this is just what this specific circuit uses). Verified: full
      correct walkthrough completes; the resistor's declared symmetric
      legs make a swap `harmless` at both landing and wiring; the LED
      (no symmetric_pins — real polarity) reversed is `wrong`; a wrong
      Arduino pin is caught with a precise `missing` entry; advanced
      difficulty collapses only `step-1a`/`step-1b` (steps 2/3 already
      have no landing to skip). 1,598 tests passing.
- [x] **Verified `difficulty` doesn't weaken correctness, only reduces
      stops** (two direct user questions): skipping a landing checkpoint
      in advanced mode never means skipping *verification* of that
      connection — `final_check` re-checks the whole circuit fresh
      regardless of which steps had a separate landing stop, catching a
      secretly-broken connection whose landing was skipped just as
      reliably as in beginner mode. And each substep, even a combined
      advanced-mode one, still gets its own immediate pass/harmless/wrong
      classification and `confirmed_pairs` tracking — never a silent
      pass-through that only gets checked at the very end. Both locked in
      as tests.
- [x] **Local learner profile** (`core/profile.py` + `cli.py`) — user
      request to remember a learner's difficulty level (and name) between
      sessions. Scoped down after discussion: this is a single-learner
      prototype, not a hosted app, so it's deliberately just a local
      `profile.json`, no login, no password, no database — "real
      accounts" (hashed passwords, a proper DB) would be a meaningfully
      bigger, separate feature if this ever becomes a shared/hosted
      service, not something to half-build now. Kept entirely out of
      `core/engine.py` (whose own docstring requires no I/O and a plain,
      replayable state) — `cli.py` loads the profile at startup, greets
      by name, and applies the saved `difficulty` right after a manual
      `start`; a `difficulty_set` action during the session immediately
      re-saves the profile. Added to `.gitignore` (per-learner local
      state, like `logs/`).
  - **`board` deliberately excluded from the profile**, caught by the
    user immediately after the first version shipped: difficulty is a
    property of the *learner* (their experience level doesn't reset every
    lesson), but which breadboard is on the desk is a property of *that
    session* — a learner could easily use a different one next time.
    Auto-applying a saved value would silently reintroduce exactly the
    "assumed, not asked" behavior `board` was built to avoid in the first
    place. Removed the `board_set` → profile write entirely; `board` is
    now always asked fresh, every session, regardless of what a learner
    used last time.
  - **Found and fixed a real, separate, pre-existing bug while wiring this
    up**: `cli.py`'s `parse()` never actually handled `board <variant>` or
    `difficulty <level>` arguments at all — only `help` and `sim` were
    special-cased, so typing either command in the interactive CLI always
    silently dropped the argument, producing "Unknown breadboard variant
    'None'" no matter what was typed. This means the `board`/`difficulty`
    commands, despite being fully correct in `core/engine.py` and covered
    by its tests, were **never actually usable from the CLI** until now —
    the engine-level test suite never exercises `cli.py`'s own parser.
    Fixed, with regression tests in `tests/test_cli.py`.
  - 1,606 tests passing.
- [x] **`board` asked prominently at the start of every lesson, not left
      as an easy-to-miss optional command** (user request — "introduce
      the breadboard as an input for each lesson... before we build...
      we determine what exactly it is... on build the checks respectfully
      adapt"). Discussed the enforcement strength before building: a hard
      gate (can't leave `gather` unanswered) would have required updating
      ~1,700 existing tests, since almost none of them set `board` before
      advancing. User's resolution — assume a default, ask prominently,
      let the learner correct it in `gather` if needed — needed zero
      engine changes and broke nothing.
  - Purely a `cli.py`-level behavior: `core/engine.py`'s own
    `state["breadboard_variant"]` still starts `None` and only ever
    changes via an explicit `board` event — the engine itself stays
    exactly "asked, not assumed." Right after a successful `start`,
    `cli.py` now automatically sends `board full`
    (`DEFAULT_BREADBOARD_ASSUMPTION` — the largest variant, chosen to
    minimize false "column doesn't fit" warnings from a wrong guess) and
    prints an explicit invitation to correct it before building starts.
    Never written to the saved profile (a per-session guess, not a
    learner fact — consistent with `board` never being persisted at all).
  - Verified the user's exact scenario: column 20 produces no warning
    under the assumed `full` board, but the *same* column correctly
    warns once corrected to `mini` (`plausibility_warning` already
    handled this per-variant column-estimate logic — this only changes
    when/how prominently the question is asked, not the check itself).
  - 1,702 tests passing.
- [x] **Real bug found and fixed while starting lesson 3 (DigitalReadSerial)**:
      `pushbutton`'s `symmetric_pins: [["1.l","2.l"],["1.r","2.r"]]` was
      wrong. Caught by verifying `docs.wokwi.com/parts/wokwi-pushbutton`
      directly instead of assuming from the pin names' visual symmetry,
      once a real diagram using the pushbutton was actually in hand. The
      real internal wiring: `1.l`/`1.r` are *permanently* connected (one
      contact group), and separately `2.l`/`2.r` are permanently
      connected (the other group) — always, not just when pressed;
      pressing bridges group 1 to group 2. That's a hardware-level
      "always the same net" fact — the same shape as the Uno's several
      GND pins — not a symmetric *swap* (a genuine, flaggable deviation).
      Removed `symmetric_pins` from `pushbutton.json` entirely and added
      `"wokwi-pushbutton": {"mode": "prefix", "prefixes": ["1", "2"]}` to
      `checker.BOARD_PIN_ALIAS_RULES` instead — using `1.l` where a
      lesson scripted `1.r` is now a silent `pass`, not `harmless`,
      matching reality (nothing was actually deviated from). No existing
      tests broke — the only prior pushbutton-shaped test fixtures used
      synthetic component ids (`btn_a`/`btn1`..`btn8`) with their own
      inline, hand-declared symmetric maps, never the real library card.
      2,059 tests passing.
- [x] **Found and fixed a second, related bug while building the lesson**:
      `checker.check_landed` had no `alias_map` parameter at all — only
      `symmetric_pairs` — so a component with its *own* board-pin-alias
      rule (the pushbutton's new one, above) was still wrongly rejected
      at the *landing* check specifically: a learner using `2.l` where
      `expected_landing` named `2.r` got `wrong`, since the function
      compared raw, un-folded pin strings. Fixed by adding `alias_map` to
      `check_landed` and canonicalizing both the target pin and every
      detected pair member before comparing (mirrors what `check()`
      already did) — threaded through `engine._run_landing_check`, which
      already computed `alias_map` but never passed it along.
- [x] **DigitalReadSerial lesson built** — the first lesson using the
      pushbutton for real, and the first with the breadboard's own power
      rails (`bp`/`bn`) in the diagram. Verified the rails need no special
      handling: `BOARD_PIN_ALIAS_RULES`'s existing "strip" mode (fold on
      the first `.`) already folds every `bp.N` together and every `bn.N`
      together, since a rail and a numbered row share the same
      `prefix.suffix` naming shape — nothing new needed there. The real
      circuit forms a genuine 3-member net (`btn1:1.r`, `r1:1`, `uno:2`
      all sharing one physical strip, confirmed via
      `derive_expected_nets` against the real diagram and matched exactly
      by the hand-written `final_check`) — the first lesson where a
      single junction needs more than one wiring step to fully form.
      Steps: `step-1a`/`step-1b` (landing + wiring for the button's power-
      side contact group, a real wire), `step-2` (wiring only — the
      signal-side contact group to pin 2), `step-3` (wiring only, no
      landing — placing the resistor with one leg sharing the existing
      column *is* the connection, same pattern as Blink's LED-to-resistor
      step), `step-4` (wiring only, no landing needed — the resistor's
      other leg already landed alongside the first). Verified: the
      pushbutton's aliased leg (`2.l` for the scripted `2.r`) is a silent
      pass at both landing and wiring; wiring the *wrong* contact group
      entirely is a real `wrong` (genuinely different internal nodes);
      the resistor's declared symmetric legs still work harmlessly; a
      full walkthrough reaches completion. 2,068 tests passing.
- [x] **Pin-substitution/remap mechanism generalized from analog-only to
      digital pins too** (user question: was this ever tested against a
      digital-pin-only diagram? — it wasn't, and didn't work at all).
      `ANALOG_PINS` generalized into `_pin_pool(pin, board_component_ids)`
      covering `ANALOG_PINS` and a new `DIGITAL_PINS` (`"2"`-`"13"`,
      excluding `0`/`1` — verified via docs.wokwi.com/parts/wokwi-arduino-uno
      that those are RX/TX and every lesson calls `Serial.begin()`). PWM
      (3/5/6/9/10/11), interrupt (2/3) and I2C (A4/A5) distinctions
      deliberately deferred — nothing built or planned yet depends on
      them; revisit once Fade (PWM) exists. Analog-specific functions
      renamed domain-generic (`_pin_owner`, `_reserved_pins`,
      `_try_pin_substitution`, `_final_pin_for_component`).
      Two real bugs caught while generalizing, both fixed: (1) `_pin_pool`
      matched on bare leg string alone, so a resistor's own leg `"2"`
      (every resistor card's `symmetric_pins` is literally `["1","2"]`)
      was misidentified as Arduino digital pin 2 — fixed with
      `_board_component_ids(diagram_parts)`, scoping the domain check to
      actual `wokwi-arduino-*` parts only; (2) `_adjusted_code`'s code-
      substitution was a raw substring replace, safe for `"A2"` but not
      for a bare digit colliding with unrelated numbers already in real
      lesson code (`9600`, `delay(1000)` next to Blink's `pinMode(13,
      ...)`) — fixed with a `\b`-word-boundary regex, applied to both
      domains.
      Design choice (user decision, trialed both before shipping):
      unlike analog (unconditional — any of the 6 pins is always an
      accepted substitute), a digital-pin deviation is only accepted when
      this lesson's own script has a genuine reason — some *other*
      component actually wanting a pin from the same domain somewhere
      (via `_reserved_pins`). Unconditional acceptance was trialed first
      and broke 9 existing Blink tests (a single-LED lesson with nothing
      else ever wanting a digital pin — "wired to the wrong pin" stopped
      being flaggable at all); the contention-gated version passed the
      full suite unmodified (2,068/2,068) and was verified end-to-end on
      a real two-component collision (an LED deviates onto the pin an
      LCD's own script needs, correctly triggers accept-then-remap,
      `LiquidCrystal lcd(...)`'s multi-pin constructor unaffected).
      A further edge case (user-raised): what if the pin pool is fully
      exhausted — no free pin left to remap to? Found this ambiguity
      already latent in `_compute_pin_remap` for analog too (just harder
      to trigger with only 6 pins) — "no remap needed" and "remap needed
      but impossible" both returned a bare `None`, so `_enter_step` would
      silently leave a step's instruction pointing at a pin another
      component already owned, with the learner never told. Fixed:
      `_compute_pin_remap` now returns `{"original", "actual": None,
      "component"}` on exhaustion; `_enter_step` never persists a broken
      remap to state and instead appends an explicit "needs the lesson
      author's attention" warning to the clip. 2,072 tests passing.
- [x] **Fixed a multi-pin-per-component bug in `_adjusted_code`**, found
      by stress-testing a real user-supplied sketch (an HC-SR04 parking-
      alarm circuit — TRIG and ECHO are two independent digital
      connections on one component, the first part this project hit with
      more than one substitutable pin per component). The generated code
      only ever reflected the FIRST of a component's substitutable pins
      being remapped/substituted — the second was silently left stale,
      because `_adjusted_code` deduped by bare component id and
      `_final_pin_for_component` took only a component id (not a
      specific leg), so it couldn't tell two of the same component's nets
      apart. Fixed by keying both on the *specific* non-Arduino pin (e.g.
      `"sensor1:ECHO"`, not just `"sensor1"`) — that side of a connection
      never changes across a substitution, only the Arduino side does, so
      it's a stable anchor into `confirmed_pairs`. 2,073 tests passing.
- [x] **Fixed a real electrical-correctness bug found via a real I2C
      diagram** (LCD1602 in I2C mode, SDA→A4/SCL→A5): the analog
      substitution mechanism was about to accept a deviation onto a
      *different* analog pin as if I2C were as freely interchangeable as
      a plain `analogRead()` sensor — it isn't; A4/A5 are hardware-fixed
      to the Uno's TWI peripheral (docs.wokwi.com/parts/wokwi-arduino-uno).
      Added `RESERVED_PROTOCOL_LEGS = {"SDA", "SCL"}`: a connection whose
      component-side leg is named SDA/SCL *on the analog domain* is
      refused a substitution/remap outright, in both
      `_try_pin_substitution` and `_compute_pin_remap`. Caught and fixed
      a false positive in the fix itself before shipping: DHT22 also
      names its (plain digital, one-wire) data leg "SDA" — matching by
      leg name alone would have wrongly blocked it too, so the guard is
      scoped to `pool is ANALOG_PINS` specifically, not name alone.
      Documented, not yet fixed (no real diagram exists to verify the
      exact leg-naming convention against): the same class of risk for
      SPI (pins 10-13) and PWM (`analogWrite()` needing 3/5/6/9/10/11).
      2,077 tests passing.
- [x] **Fixed a second, more serious real gap in the I2C fix**: refusing
      to move the I2C connection itself wasn't enough — a plain
      analogRead() sensor could still be silently accepted onto A4 in an
      EARLIER step (nothing yet marked it taken), permanently shorting
      it onto the I2C bus once the LCD's own (un-remappable) SDA step
      was followed correctly, with zero warning. Added
      `_protocol_reserved_pins(lesson)`: every analog pin this lesson's
      own script ties to SDA/SCL anywhere is now excluded as a
      substitution/remap TARGET for any other, unrelated component too.
      2,078 tests passing.
- [x] **Fixed a real, undocumented Uno alias**: two independent real
      diagrams wired an I2C device's SDA/SCL to `A4.2`/`A5.2` instead of
      plain `A4`/`A5` — Wokwi's basic docs page doesn't list these, but
      real Uno hardware has a genuine second SDA/SCL breakout header near
      AREF (same electrical nodes). A proposed alternate theory ("`.N`
      means multiple wires share a hole") was directly ruled out by a
      diagram wiring three separate connections to the literal same
      `GND.1` with no increment — confirming `.N` names a fixed physical
      pin location, same as GND.1/2/3. Extended
      `BOARD_PIN_ALIAS_RULES["wokwi-arduino-uno"]`'s prefix list from
      `["GND"]` to `["GND", "A4", "A5"]` — same fold mode, no new
      mechanism. Checker-only fix; the engine's substitution layer never
      needed a matching change, since candidate pins are always
      constructed from the canonical `ANALOG_PINS` strings, never a
      diagram's literal `.2` spelling. 2,079 tests passing.
- [x] **Session close-out: full 9-diagram regression pass** — every real
      diagram tested across this stress-testing arc (photoresistor+I2C
      LCD, Mega+MAX7219 matrix chain, OLED+encoder+TM1637+buzzer,
      servo+OLED+I2C+encoder, four plain LED/resistor/servo/buzzer
      diagrams, and a final simple servo+buzzer one) re-run through both
      the checker and a representative real-contention tracking scenario
      each — 19/19 clean in one consolidated pass. Clarified a
      distinction worth keeping straight going forward: checker-level
      aliasing (GND.1/2/3, A4/A4.2, pushbutton groups, 7-segment COM)
      means a pin pair was never actually a deviation at all, so
      substitution/remap tracking correctly never engages for it —
      "was tracking tested" and "was the checker's equivalence tested"
      are two different questions. One diagram-authoring mistake spotted
      along the way (a servo's `V+` wired to a digital GPIO pin instead
      of `5V`) — not a checker bug, flagged to the user. See
      the research log (in git history) for full detail. Still open: the Mega/MAX7219
      matrix's `.2` pins (unconfirmed, single diagram only), whether to
      generalize the domain pools beyond the Uno's shape, and the
      "suggest an alternative on refusal" feature (designed, not built).
      2,079 tests passing throughout.
- [x] **Both remaining items closed out.** Domain pools generalized
      beyond the Uno: `BOARD_PIN_SHAPES`/`BOARD_PROTOCOL_PINS` (verified
      against docs.wokwi.com/parts/wokwi-arduino-mega — A0-A15 analog,
      digital 0-53 minus all 4 hardware serial ports, I2C on DIGITAL
      pins 20/21 unlike the Uno's analog A4/A5), replacing the old
      `pool is ANALOG_PINS` set-identity check (which couldn't survive
      per-board pools, and was never precise about *which* pin anyway)
      with an exact per-board pin-identity check. "Suggest an
      alternative on refusal" built as `_refusal_hint`, a
      `substitution_refused` action alongside `feedback`: explains a
      stolen I2C pin, explains a hardware-fixed I2C pin that moved, and
      — added after the first two per further request — gives a
      concrete "Connect X's leg to Arduino pin Y" instruction even for a
      plain refusal with no special reason. One more real gap found by
      directly testing substitution-then-hint: the `hint` command never
      applied the same pin-remap substitution `_enter_step` already
      applies to the main instruction, so a hint on a remapped step
      showed the stale, pre-remap pin — fixed to match. See
      the research log (in git history) for full detail. 2,088 tests passing.
- [x] **First real Mega diagram tested since the board generalization** —
      found a gap in a different layer than the one just generalized:
      `checker.BOARD_PIN_ALIAS_RULES` (net-equivalence folding) only had
      an entry for the Uno. Verified via docs.wokwi.com/parts/
      wokwi-arduino-mega: the Mega has five GND legs (GND.1-GND.5) and a
      secondary power header (5V.1/5V.2) — same "N physical legs, one
      net" shape as the Uno's GND, just more of them. Added
      `"wokwi-arduino-mega": {"mode": "prefix", "prefixes": ["GND",
      "5V"]}`. User then pasted the full Wokwi Mega reference page,
      confirming every fact already used in the engine-level
      generalization (PWM, all 4 serial ports, I2C on 20/21, SPI). 2,089
      tests passing.
- [x] **A larger real Mega diagram (4 pushbutton-6mm + 2 RGB LEDs +
      buzzers on a breadboard) found two more gaps.** Checker: verified
      `wokwi-pushbutton-6mm`'s docs ("same as wokwi-pushbutton") then
      added a matching `BOARD_PIN_ALIAS_RULES` entry — it's a different
      type string, so the existing pushbutton rule never applied to it.
      Engine: reconsidered the Mega's serial-port exclusion from earlier
      this session — the diagram wired a button straight to `mega:19`
      and a buzzer to `mega:1`'s Serial1 counterpart, real evidence that
      excluding all four hardware serial ports (14/15, 16/17, 18/19,
      plus 0/1) was reasoning by analogy, not the verified-fact standard
      the Uno's 0/1 exclusion actually met (every built lesson calls
      Serial.begin()). Narrowed back to excluding only 0/1 (also needed
      by the USB bootloader itself, a hardware concern independent of
      any lesson's code) and deferred 14-19 the same way PWM/interrupt/
      SPI already are — narrow the pool for a verified need, not a
      plausible one. 2,089 tests passing (one Mega test's assertions
      updated to match).
- [x] **32-servo ring diagram on the Mega verified clean** (true cycle
      topology for power/ground, PWM pins across the full 22-53 range,
      including the extreme edge at 53) — no code changes.
- [x] **SPI given the same protection as I2C**, found via a real Mega
      diagram (ILI9341 touch LCD + microSD card sharing one SPI bus):
      generalized `BOARD_PROTOCOL_PINS`/`RESERVED_PROTOCOL_LEGS` to cover
      MISO/MOSI/SCK (CS/SS deliberately excluded — confirmed per-device
      via the same diagram's two different CS pins). Also added `DO`/`DI`
      (the microSD card's own naming for the same bus lines, verified via
      its docs page) — without it the LCD's connection was protected but
      the SD card's own wasn't. The user then pasted that same docs page
      directly, which included a full worked **Uno** SPI example ("SCK
      13, DO 12, DI 11, CS 10") — the real evidence needed to extend the
      same protection to the Uno (previously deferred for lack of one).
      That change surfaced a second bug via the test suite itself:
      `_refusal_hint` hardcoded "I2C" in its explanation regardless of
      which protocol was actually involved — once pin 13 became a real
      Uno SPI pin, an existing test's example collided with it. Fixed by
      making `BOARD_PROTOCOL_PINS` map each pin to its real protocol name
      and phrasing the message accordingly. 2,095 tests passing.
- [x] **Closed a real coverage gap**: `analog-read-serial` and `blink`
      both had dedicated exhaustive-variation test files;
      `digital-read-serial` didn't. Added
      `test_exhaustive_digital_read_serial_variations.py` — all four
      build steps, 221 cases, plus algebraic cross-checks. One test-
      design collision found and fixed along the way (not an engine
      bug): the "wired directly to an Arduino pin" landing-check test
      case had picked `5V`, which is also step-1b's own correct target,
      so it triggered the breadboard-bypass path instead of testing the
      intended dimension — switched to `A0` (never a real target),
      matching `test_exhaustive_wire1_variations.py`'s own precedent,
      and added a dedicated bypass test for the pushbutton's aliased leg
      specifically. 2,316 tests passing.
- [x] **A third board, Arduino Nano, generalized from real docs the user
      pasted directly** (no WebFetch needed). Same digital range as the
      Uno; the real difference is two extra analog-ONLY pins (A6/A7),
      needing no special-casing since they're simply never members of
      the digital set either. Confirmed via the diagram itself: two GND
      legs (same alias-fold shape as Uno/Mega) and I2C on A4/A5 (an
      OLED's SDA/SCL). Added matching entries to `BOARD_PIN_SHAPES`,
      `BOARD_PROTOCOL_PINS`, and `checker.BOARD_PIN_ALIAS_RULES`. 2,319
      tests passing.

---

---

## Phase 3 — Wiring Bench (the simulator UI)

**Goal:** a browser breadboard where the learner drags parts, draws
wires, and gets the real engine's verdict. Runs locally.

- [x] `bench_server.py` — standard-library HTTP server; calls
      `core.engine.handle_event` exactly as `cli.py` does, against the
      real `lessons/` + `library/`. Engine modules reloaded on every
      lesson start. Every event logged to `logs/<lesson>/bench-*.jsonl`
      (replayable).
- [x] `bench/index.html` — breadboard/Arduino canvas, drag-and-drop
      placement with hole-accurate preview, wire drawing, step panel,
      hints, tracking panel (confirmed pairs / substitutions / remaps),
      adjusted code at upload, final check. No engine logic in the page.
- [x] Verified end to end against the live server (Blink with a pin
      substitution; a deliberately missing wire on DigitalReadSerial).
- [x] Tray parts derived from each lesson's `diagram.json` + part cards
      (`bench_server._tray_parts`), so a new or AI-generated lesson needs
      no page edit. The page's `LESSONS` table now only overrides canvas
      layout where a hand-tuned one exists.
- [ ] Touch support (tablet/phone) for drag and wire drawing.
- [x] Physics panel (Phase 4) after every check: LED state + current,
      pin readings per button state, hazards/warnings with their numbers.
- [ ] Draw physics on the board itself (glowing LED, highlighted short).
- [ ] Browser text-to-speech reading the step clip (optional).
- [ ] Free-build sandbox mode: no script, just the physics solver and
      net inspector.

---

## Phase 4 — Circuit physics (real electrical behavior)

**Goal:** solve the learner's actual circuit, so feedback is about what
it *does*, not only whether it matches the answer key.

- [x] `core/physics.py` — build a circuit from the same pin pairs the
      checker uses (breadboard strips folded into nodes), then solve DC
      operating point with modified nodal analysis (Ohm's + Kirchhoff's
      laws). Standard library only.
- [x] Component models, from the part cards: resistor (value from
      `wokwi_value`), LED (forward voltage per color, off below it,
      max ~20 mA continuous), pushbutton (open/closed state), Arduino
      pins as sources (5V, 3V3, GND; an OUTPUT pin driving HIGH/LOW;
      ~40 mA absolute max per I/O pin, ~20 mA recommended).
      Potentiometer as two resistors split by wiper position.
- [x] Findings, each with the numbers behind it: LED lit/dim/dark
      and its current; overcurrent on an LED or I/O pin (e.g. no series
      resistor); direct short between supply and GND; LED reversed;
      floating digital input (no pull-up/down).
- [x] Engine integration: at `final_check`, a physics hazard (short,
      overcurrent) turns an otherwise-passing check into `wrong` with a
      `physics_hazard` action; non-hazard findings are informational.
      Not yet applied to individual build steps.
- [x] Tests (`tests/test_physics.py`, 33): hand-calculated reference circuits (Blink with 220 Ω,
      1 kΩ, 10 kΩ, none; reversed LED; 5V–GND short; button with and
      without pull-down), plus every existing lesson's reference
      `diagram.json` must solve cleanly and light/read as expected.

---

## Phase 5 — Gamification

**Goal:** make practice feel like a game without ever rewarding a wrong
circuit.

- [x] `core/progress.py` — pure functions; a session is scored by
      replaying its event log through the engine: XP per step (first-try pass > pass after hints > harmless),
      lesson-complete bonus, no-hint bonus, physics-clean bonus.
- [x] Levels (50·n·(n+1) XP thresholds), daily streak, badges (first
      circuit, no hints, perfectionist, pin swapper, inventor, explorer,
      3-day streak). Replays only earn the improvement over a lesson's
      best score. (A "first real-board check" badge waits for Phase 7.)
- [x] Unlocks: `requires` in `lesson.json` (Blink first; DigitalRead
      and AnalogRead after it). Generated lessons are always unlocked.
- [ ] Extend the tree as Fade / ReadAnalogVoltage are built.
- [ ] "Fix the broken circuit" challenges: a pre-wired circuit with one
      physics-meaningful fault (missing resistor, reversed LED, floating
      input, wrong resistor value) to diagnose and repair.
- [x] Progress saved under `profile.json`'s `progress` key; XP bar,
      level, streak, badges, lock state and a completion award shown in
      the Wiring Bench.

---

## Phase 5b — Where lessons come from

**Goal:** three ways to get something to build.

- [x] **Predefined lessons**: hand-authored from Arduino's official
      Basics examples (`lessons/`).
- [x] **"I have these parts, what can I build?"** —
      `core/lesson_finder.py`: free-text inventory → library ids; every
      lesson classified ready / buildable with a stand-in / missing parts.
      A stand-in (currently resistors) is only offered after re-solving
      the lesson's reference circuit with it: no new hazard or warning,
      no input reading changed, and the note says what changes
      ("led1: 2.9 mA → 11.8 mA, brighter, still safe").
- [x] **Lessons generated on the spot by an LLM** — `core/lesson_gen.py`:
      Claude (`claude-opus-5`, structured output, server-side refusal
      fallback) writes lesson.json + diagram.json + code.ino; `validate`
      runs structure, library ids, pin names, step/final/diagram
      consistency, sketch-vs-circuit pins, the physics solver and a full
      engine dry run; errors go back to the model (up to 3 drafts); only
      a lesson passing everything is saved as `lessons/gen-*`. Brief and
      checks adapted from the `llm-lesson-gen` experiment (separate copy
      of this project), including its one end-to-end failure (four
      pushbutton legs as a landing), now stated in the brief and caught
      by the dry run. `suggest_ideas` proposes projects from an
      inventory. All three hand-authored lessons pass the same validator.
- [ ] First live generation runs (needs `pip install anthropic` + a key):
      measure drafts-to-pass and pass rate per request type.
- [ ] Quantities in the inventory (two LEDs, three resistors).
- [ ] More substitutable kinds (LED colours, via their forward voltage).

---

## Phase 6 — AI tutor (LLM layer)

**Goal:** free-form questions and explanations, without the LLM ever
owning lesson state.

- [ ] `snapshot_for_llm(state, lesson, physics)`: assembles what the
      model sees — tutor rules, current step + neighbors, allowed
      actions, allowed reveal level (from `hints_used`), the check
      result's diff, **the physics solve of the learner's own circuit**,
      recent turns, the event.
- [ ] Model output is constrained JSON: one action from the allowed
      list, or `answer` with text. Same validator as typed commands.
- [ ] Explanations cite the solver's real numbers ("5 V − 2 V across
      220 Ω ≈ 14 mA"), never invented ones.
- [ ] Ablation switch: physics context on/off, for the research
      question's A/B comparison.
- [ ] Natural-language command recognition (the equivalents already
      listed in `COMMANDS.md`), with typed/button fallback always
      available.
- [ ] Small eval set of learner utterances → expected action, and of
      faulty circuits → expected explanation, measured before trusting
      it live.

---

## Phase 7 — Real-board photo check (optional, normal camera)

**Goal:** check a circuit built on a real desk from one phone/webcam
still, using the same engine.

- [x] Detection contract already exists: flat hole-level `[pin, pin]`
      pairs (`detected_pairs`), exercised by `core/mock_vision.py` and
      `tests/test_realistic_detection_100.py`. A real photo analyzer is
      just a second producer of the same data.
- [ ] Capture-on-demand in the Wiring Bench (upload a photo / use the
      webcam), not continuous streaming.
- [ ] Ground-truth set: photos of known builds, correct and with
      deliberate errors, labeled at build time; split by build, not by
      image.
- [ ] Compare (secondary research question): raw multimodal LLM vs.
      grid-augmented LLM (board rectified and overlaid with labeled
      columns) vs. classical CV. Metric: net-level accuracy.
- [ ] Failure analysis: glare, wire color, occlusion, off-axis angle.

---

## Phase 8 — Evaluate and write up

- [ ] Learning study: physics-grounded vs. generic AI feedback (Phase 6
      ablation) — time per step, hints used, repeated mistakes, quiz on
      the underlying concepts.
- [ ] Transfer: simulator performance vs. real-board photo check on the
      same lesson.
- [ ] Engagement: does gamification change completion/return rate?
- [ ] Photo-check accuracy table (Phase 7).
- [ ] Limitations: simulator abstractions (DC operating point only, no
      timing/transients), lesson set size, cross-family board
      translation (e.g. Uno → ESP32) out of scope.

---

## Open decisions to resolve along the way

- [ ] Whether `final_check`'s `expected_nets` is hand-maintained or
      auto-derived from the union of step nets (recommend: derive it).
- [ ] Whether the model ever sees the answer key directly, or only the
      check result's diff and the physics solve.
- [ ] How much of the physics to show beginners by default (numbers vs.
      plain-language "too much current") — a difficulty setting?
- [ ] Hosting: stay local-only, or deploy the bench server so it can be
      shared.
