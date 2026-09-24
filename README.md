# CircuitQuest — an AI Arduino tutor

**Learn electronics by building real Arduino circuits.** You drive through a 3D world of levels, build each circuit on a 3D workbench — with or without a breadboard — and a deterministic engine checks every connection against real circuit physics. Claude can write brand-new lessons on the spot, and every one of them has to pass the same checks as the hand-made lessons before you ever see it.

> Formerly "Pinpoint", an AR-glasses tutor; the AR direction was dropped on 2026-09-23. Build plan and design principles: [`PLAN.md`](./PLAN.md). Data specs: [`LESSONS.md`](./LESSONS.md), [`PARTS.md`](./PARTS.md), [`TOOLS.md`](./TOOLS.md), [`COMMANDS.md`](./COMMANDS.md).

---

## Quick start

```bash
python3 bench_server.py          # the app → http://localhost:8765
python3 cli.py blink             # the same lessons, text-only
python3 -m pytest -q             # the test suite (~3,500 tests, ~2 min)
```

Python 3 standard library only (plus `pytest` for the tests). The page loads three.js and the Wokwi part artwork from a CDN, so the browser needs internet.

### AI lessons (optional)

"Create my own lesson" needs a way to reach Claude. The server picks one automatically:

| Route | Set-up | Billing |
|---|---|---|
| **Your Claude Code login** (default on your own machine) | Be logged in to [Claude Code](https://claude.com/claude-code) (`claude` in a terminal). On another machine: run `claude setup-token` and put the token in `.env` as `CLAUDE_CODE_OAUTH_TOKEN=…` | Your Claude plan |
| **Anthropic API key** | `pip install anthropic`, then `ANTHROPIC_API_KEY=…` in `.env` (from [console.anthropic.com](https://console.anthropic.com)) | Pay-as-you-go |

Copy [`.env.example`](./.env.example) to `.env` — it's git-ignored, so tokens never get committed. `CQ_AI_BACKEND=none` switches AI off (the test servers do this). Everything except AI lesson creation works without either.

---

## What you can do

### Learn on a 3D world map
- **One world per group of Arduino's official [built-in examples](https://docs.arduino.cc/built-in-examples/)** — Basics, Digital, Analog, Communication, Control Structures, Sensors, Display, Strings, USB, Arduino ISP — plus an **AI Lab** for lessons you invent. All 68 examples are on the map as numbered levels (1-1, 1-2 …); ones without a lesson yet are named "coming soon" stops, so numbers never shift.
- **Sparky drives a little car** along one winding road through themed low-poly worlds (a garden with a windmill, a neon arcade, a desert with a radio tower, a lighthouse bay, a switchyard, a forest, a pixel city with robots, a library, a keyboard cove, a chip factory) and a countryside of hills, rivers, lakes, cottages, sheep, bunnies and LED mushrooms.
- **Play any level in any order** — prerequisites are tips, not locks. Levels are coloured by what you own: green **ready**, blue **works with a stand-in**, white **needs parts**, gold **done**, with up to three stars each (finish / no hints / no wrong steps).
- **"What's on your desk?"** — pick your parts once and the map shows what you can build right now, including physics-checked stand-ins (a 220 Ω resistor where 1 kΩ is asked for: "2.9 mA → 11.8 mA, brighter, still safe").

### Build on a real-looking 3D workbench
- **True-size 3D models** (three.js, millimetres on the 0.1" pitch): a breadboard where **every hole is its own object**, an Arduino Uno with every component labelled and explained (USB, regulator, ATmega328P, crystal, headers …), and a 3D model for every one of the ~80 parts and tools in the library.
- **Drag parts into exact holes**, run wires hole-to-socket (drag, or click-then-click while you look around), press buttons, turn knobs; LEDs glow when the physics says current flows.
- **With or without a breadboard.** Without one, each connection is built the way you really would, and drawn that way: **solder** (an animated molten bead, then heat-shrink), **clip leads**, or leads **pushed in / twisted** — following the real legs: thin leads, a pushbutton's short legs, a knob's solder tabs, module header pins. The level card shows every way to build it, with the extra parts and tools each needs.
- **Beginner or advanced.** Beginner steps say exactly which leg goes where, in plain words; advanced shows only the goal ("Connect the LED's long leg to the free end of the resistor") and the hints reveal the how.
- **Reveal step** marks in red exactly which holes and sockets to connect — on *your* board, with *your* swapped pins.

### Create your own lessons with Claude
Describe a project ("a traffic light that cycles like a real one") and Claude writes the circuit (a Wokwi diagram), the sketch and the steps. The lesson is only saved once it passes **every** check a hand-made lesson passes — wiring, pin rules, code, circuit physics, a full engine run, and an explorer that tries every way a learner could build it (other pins, parts turned round, building ahead, mistakes). A failing draft goes back to Claude with the exact problems, up to three times.

---

## How it works

```
 browser: world map · 3D workbench · level card          (bench/*.js, three.js)
        │ the whole board as detected_pairs, on every check
        ▼
 bench_server.py ──► core/engine.py   handle_event(lesson, library, state, event)
                      ├─ checker.py        nets (union-find over pins, strips, rails)
                      ├─ physics.py        Ohm/Kirchhoff solve: currents, LED state, shorts, input levels
                      ├─ build_methods.py  breadboard / solder / clip leads / twist — per real leg
                      ├─ progress.py       XP, levels, stars, streaks, badges
                      ├─ lesson_finder.py  "what can I build with my parts?"
                      ├─ lesson_gen.py     Claude writes a lesson → validate → repair → save
                      ├─ worlds.py         the map: Arduino example groups → worlds → levels
                      └─ lessons/*, library/*   lessons (+ generated) and part / tool cards
```

Principles (full list in [`PLAN.md`](./PLAN.md)):
- **Code owns correctness.** The engine decides pass / harmless / wrong; the AI only writes lessons (which the engine then has to accept).
- **Compare electrical nets, not exact holes** — any hole in the right column, any free pin (the sketch is rewritten to match), a symmetric part either way round.
- **Physics decides safety.** A wiring that matches the script but would burn out a part is still wrong.
- **Every check is the whole board**, so a wire that comes loose, a part turned round or a stray connection is caught at the next check.

---

## Tests

`python3 -m pytest -q` runs ~3,500 tests: the engine against thousands of generated build orders, pin swaps and mistakes; the physics solver; every build method; the lesson finder; the AI generator with a fake model. Browser smoke tests (`bench/ui_*.js`, puppeteer-core, headless Chrome) play whole lessons through the real UI:

```bash
CQ_PROFILE=/tmp/test_profile.json CQ_AI_BACKEND=none python3 bench_server.py 8799 &
node bench/ui_3d_smoke.js /tmp/shots        # also ui_flow_smoke, ui_nobb_smoke, ui_reveal_smoke
```

`CQ_PROFILE` keeps tests away from your real progress; `CQ_AI_BACKEND=none` keeps them from calling Claude.

---

## Sources

[Arduino built-in examples](https://docs.arduino.cc/built-in-examples/) · [Wokwi elements](https://github.com/wokwi/wokwi-elements) (MIT, part artwork) · [Wokwi diagram.json format](https://docs.wokwi.com/diagram-format) · [three.js](https://threejs.org/) (MIT) · [Tinkercad Circuits](https://www.tinkercad.com/circuits) · [Brilliant](https://brilliant.org/)
