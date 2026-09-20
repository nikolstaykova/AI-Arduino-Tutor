# Pinpoint

**A platform that teaches real, hands-on skills by watching the learner through a camera and correcting them live — from a human specialist, or from an AI tutor that must first learn to see the workbench as precisely as a person does.**

> Working title. Domain: Arduino & electrical circuits. Status: concept validated, pre-build.
> Full chronological research trail (every session, every source checked) lives in [`research-log.md`](./research-log.md). This file is the current-state summary.

---

## 1. How we landed on this domain

The idea went through three re-scopes before settling — each cut by checking what already exists, not by preference:

1. **Starting point — remote-expert AR glasses.** A specialist guides a field user live through AR glasses. Real, but already a mature B2B market: RealWear, Vuzix, TeamViewer Frontline, and Microsoft Dynamics 365 Remote Assist all do this for industrial field service today.
2. **Pivot — consumer skill-learning, not enterprise service.** Reframed as "Duolingo, but for a real hands-on skill" — same live-guidance mechanic, aimed at an individual learner instead of a company's technician.
3. **Considered and rejected — appliance/device repair.** iFixit's FixBot and several photo-diagnosis apps already own this space with a trusted incumbent brand. Crowded, not where the open ground is.
4. **Committed — Arduino & electrical circuits.** Real hardware, an observable pass/fail state, an existing maker community to draw curriculum from — and, critically, a geometry that's actually solvable: a breadboard is a fixed, known grid.

## 2. What already exists (the landscape)

Ten adjacent products/research systems were checked against five things this platform needs together. No single one has all five — that gap is the project.

| Product | What it actually does | Real hardware | Live AR view | Gamified | AI ⇄ human toggle | Exact spatial ID |
|---|---|:---:|:---:|:---:|:---:|:---:|
| Electric Circuit AR | AR app for inspecting components & drag-and-drop building virtual circuits in 3D | – | ✓ | – | – | – |
| Brilliant | Gamified, bite-sized interactive STEM/logic problem sets, entirely on a flat screen | – | – | ✓ | – | – |
| LearnHub | Gamifies university engineering coursework with streaks, leaderboards, per-user progress | – | – | ✓ | – | – |
| AITEE | Academic research prototype: an agentic AI tutor for electrical-engineering concepts (arXiv) | partial | – | – | AI-only | – |
| Elec-Mate AI Tutor | Phone-based AI Q&A app for electricians studying for licensing exams | – | – | – | AI-only | – |
| Intelgic / iFactoryApp | Industrial machine-vision systems that inspect wiring/control panels for faults | ✓ | – | – | AI-only | component-level |
| Ray-Ban Meta / Project Astra | Multimodal AI glasses that see what you see and answer questions about it live | – | ✓ | – | AI-only | – |
| iFixit FixBot | Snap one photo of a broken device; AI identifies it and writes a repair guide | ✓ | – | – | AI-only | – |
| RealWear / Vuzix / TeamViewer | Industrial smart glasses + software connecting a live human expert to a field worker | ✓ | ✓ | – | human-only | – |
| **Pinpoint (ours)** | Watches a real breadboard/Arduino build live; AI-or-human corrects it as you learn | **✓** | **✓** | **✓** | **✓** | **✓** |

*AI-only = no human fallback offered · human-only = no AI mode offered · component-level = detects a fault, not an exact hole/pin.*

## 3. The gap, precisely

The unsolved piece is narrow and specific: telling a learner **which exact breadboard hole or Arduino pin** something belongs in, from a camera image, live — not "is there a fault," the exact cell.

- [SmartBreadboard-3D (GitHub)](https://github.com/sasivaradhansbee25-hue/SmartBreadboard-3D) attempts exactly this — its own README lists the hole-detection module as an unbuilt stub ("Phase 9+"). Closest known prior art, unfinished.
- [arXiv: The Spatial Blindspot of Vision-Language Models](https://arxiv.org/pdf/2601.09954) — general-purpose multimodal models, the Claude/GPT-4V/Gemini class included, are documented to be unreliable at fine-grained spatial localization without help.

## 4. What we're building

A live camera-guided tutor for one board (**Arduino Uno**) and a first lesson track in basic circuits, priced in two tiers: a human specialist, or the AI tutor below.

### Build — existing tools (engineering, not research)
| Feature | Existing tool/approach |
|---|---|
| Marker & corner detection | OpenCV's built-in ArUco tracking |
| Homography / grid mapping | Standard OpenCV geometry |
| The reasoning layer | Claude via API, used as-is (not trained/fine-tuned) |
| Quick-question chat assistant | Same API, given the live lesson/session state |
| Specialist ⇄ learner channel | TLS / WebRTC's built-in DTLS-SRTP encryption — never hand-rolled |
| Mistake & accuracy logging | Standard application analytics |
| Lesson design & ground truth | Define each lesson's correct circuit as a Wokwi `diagram.json` (explicit pin-to-pin connections, machine-readable), auto-validated by Wokwi CI's headless simulation before it's used as an answer key |
| Voice interaction | Off-the-shelf text-to-speech for the tutor's spoken directions, speech-to-text for the learner's answers ("yes I know this tool" / "no, show me") |
| Readiness check & fallback tutorials | Short pre-recorded clips for common tools/skills, played on demand when the learner says they don't know one |
| Tool-selection verification (stretch goal) | Same object-detection/VLM pipeline, pointed at a tool instead of a wire |

> **Doesn't compete with the research gap:** Wokwi already checks whether a *virtual* circuit built in its own software is wired correctly, and its `diagram.json` format + headless `wokwi-cli` CI runner mean lesson answer-keys can be authored and auto-validated as structured data, not screenshots. It never watches a real physical board through a camera, though — that's still the unsolved half of the problem this project is about.

### Deeper look: Wokwi's automation tooling (worth building on)
- **`diagram.json`** stores wiring as explicit, structured connections — e.g. `["led1:A", "uno:13", "green", []]` means the LED's anode pin connects to Arduino pin 13. That's a real machine-readable answer key per lesson, not a picture to eyeball.
- **Wokwi CI / `wokwi-cli`** runs a simulation headlessly, checks serial output automatically, fails the test if behavior doesn't match, and integrates with GitHub Actions — built for exactly "does this circuit + code actually work," automated, no physical hardware needed.
- **Practical use for this project:** author each lesson once as a `diagram.json`, let Wokwi CI confirm it actually behaves correctly (e.g. "LED blinks every 1 second") before it's ever shipped as a lesson's ground truth — removes the need to hand-derive "what's the correct wiring" for every lesson by hand.
- **Tinkercad Circuits**, by contrast, has no confirmed public API/export for programmatic wiring checks — a good teaching UI, but without Wokwi's developer tooling behind it.
- 📄 [Wokwi CI docs](https://docs.wokwi.com/wokwi-ci/getting-started) · [diagram.json format reference](https://docs.wokwi.com/diagram-format)

### The exact division of labor (this doesn't shrink the research)
Wokwi can't see a photo — it only knows circuits explicitly declared as data. So the split stays clean:
- **Wokwi's job**: define + auto-validate the *correct* circuit for a lesson, producing a pre-verified, hole-level answer key (Wokwi's virtual breadboard already names every hole, e.g. `bb1:18t.d` = row 18, top section, column d — [source](https://github.com/wokwi/wokwi-elements/issues/31)).
- **Our research's job (unchanged)**: given a real photo of a real board a learner built, identify which real hole/pin each real component/wire is actually touching. Wokwi cannot help with this part at all.
- **The check itself** becomes plain engineering once both sides agree on format: adopt Wokwi's own row/section/column hole-naming convention for our grid overlay, so detected-vs-expected is a direct structural comparison, no translation layer needed.

### System flow, start to finish
Everything above, in the order it actually happens — before a lesson exists, and while a learner is doing it. The free/Community Wokwi plan already includes "unlimited public projects" and unlimited simulations, so the authoring half costs nothing and needs no special account.

1. **Author** (before the lesson exists) — free Wokwi account, build the lesson's circuit in the ordinary editor (e.g. "Lesson 1: wire an LED to pin 13"). The `diagram.json` exists the moment it's built.
2. **Validate** — run it through Wokwi CI to auto-confirm it actually behaves correctly (e.g. the LED really blinks) before trusting it as ground truth.
3. **Ship the answer key** — that `diagram.json` is the lesson's hole-level correct answer (e.g. `"bb1:18t.d" → "uno:13"`), done once, offline, by whoever designs the lesson.
4. **Learner starts the step (wide shot)** — the tutor speaks first: what's needed for this step ("you'll need a small breadboard and a 220Ω resistor"), and identifies/circles those items wherever they sit on the cluttered table.
5. **Readiness check** — tutor asks, out loud: "do you have this, and do you know how to use it?" Waits for a spoken answer, no rushing ahead.
6. **Fallback micro-tutorial, if needed** — learner says no → a short predefined video for that specific tool/skill plays, then the tutor checks back in before continuing.
7. **Guided build (close-up)** — learner brings the gathered items in close; spoken, paced directions ("now connect the LED to pin 13") plus a highlight drawn at the exact known pin location — the tutor waits for the learner to actually act, not a fixed script running ahead of them.
8. **Checkpoint verification** — triggered by the learner saying so ("I'm done" / "check it"), not an inferred signal — our geometry model maps the camera view onto the same hole-naming scheme, and the LLM compares it against the Wokwi answer key.
9. **Feedback** — spoken + visual correction if something's wrong, or move on to the next step if it's right.

"Classroom" is unrelated to this workflow entirely — it's only for institutions needing simulation capacity for many students using Wokwi themselves, not for lesson authoring.

### Research — the actual contribution
**Central question:** can modern general-purpose LLMs — combined with our geometric preprocessing — reliably perform hole-level verification of breadboard wiring, and how does that approach compare against classical computer vision / dedicated vision models built specifically for this task?

That comparison arm matters as much as the LLM side: it makes this a real research question with a defensible result either way — either the LLM approach genuinely earns its place, or a purpose-built classical detector turns out to be simpler and just as good, which is itself a legitimate, publishable finding. This is genuinely unsolved either way (confirmed above), which is exactly what a final-year data-science project should be. It doubles as the dissertation's contribution *and* the product's core differentiator.

## 5. How it might work (not yet decided — this is the research)

**The exact mechanism is the research question itself, not a settled fact.** In plain terms, before any of it is tested:

```
① See                →   ② Identify the board   →   ③ Map the points        →   ④ Guide & catch errors
   capture what the        recognize which model      work out where every        point to where things
   learner's camera        it is (v1: one board,       hole/pin actually is —      go, flag what's wrong
   is looking at           the Arduino Uno)            the hard, unsolved part
```

**Leading candidate for step 3** (still to be built and tested, not assumed): use fixed reference points on the board to work out a grid geometrically, then let the AI model read that *labeled* grid instead of guessing raw coordinates from the photo. This is backed by published findings that raw AI vision alone struggles at exact spatial localization ([Spatial Blindspot of VLMs, arXiv](https://arxiv.org/pdf/2601.09954)) but improves substantially once given that kind of visual scaffolding ([Grid-augmented vision, arXiv](https://arxiv.org/pdf/2411.18270); [Visual Position Prompt for MLLM Grounding, arXiv](https://arxiv.org/pdf/2503.15426)). Since nobody's applied this specifically to breadboards/Arduino, building and evaluating it for this domain — proving it actually works, not just assuming it will — is the genuine research contribution here.

### Three different capabilities — only one of them is the hard research
Step ④ above ("guide & catch errors") actually splits into two very different jobs, and there's a third, earlier one worth naming too:

1. **Identify loose objects** — "which one's the resistor, roughly where is it on the table." A semantic recognition task, not a precision task — the spatial-blindspot finding is specifically about *exact coordinates*, not "what is this thing," so VLMs are actually fine here. Well-trodden ground (Roboflow's resistor-detection dataset, electronic-parts-classification research already exist). **Doesn't need the novel research.**
2. **Point to a known board location** — "here's output 3." Once the board is tracked, its pin layout is fixed and documented, so this is pure geometry — transform a known template coordinate into the live camera view and draw a highlight. **No AI call needed at all.**
3. **Verify the actual connection** — "did the wire really end up there." This is about detecting something new and unknown, not a fixed reference — the hard, unsolved precision-grounding problem. **This is the actual research contribution.**

This also implies a natural two-phase UX: a **wide shot** where the camera sees the cluttered table and the system circles what's needed for the step (capability 1), then a **close-up** once the learner gathers those items together to actually connect them, where pointing and verifying (2 and 3) take over. The wide→close transition doubles as the signal for switching modes — no separate detector needed.

**What this sounds like in practice:**
> **AI:** Ready to start? **User:** Yes.
> **AI:** Perfect — take the board and place it on the table. Before we start, I'll recap what's what — stop me any time if something's unfamiliar.
> **AI:** Step one: take the blue wire and connect it to output 3, using [tool]. Do you know how to use this tool? **User:** Yes.
> **AI:** *(points to the exact physical location of output 3)* Here's output 3. Let me know once you're done — feel free to ask questions.
> **User:** I'm done.
> **AI:** Amazing — let me see your work. Show me what you've wired and I'll check it. *(← this is the hard research part)*

Note the checkpoint trigger in that example: it's simply **the learner saying so** ("I'm done"), not an inferred signal like the camera holding still. Spoken trigger first; stillness/timeout detection is only a backup.

## 6. Research plan, once the system exists

The build proves the pipeline runs. This is what proves it's *right* — the part a dissertation has to defend.

1. **Ground-truth test set** — real breadboard photos, wiring known and labeled hole-by-hole, across lighting/angle conditions.
2. **Grid-render tuning** — vary line weight, transparency, labeling scheme; find what the LLM actually reads best.
3. **Prompt/context design** — test how much domain documentation (breadboard conventions, the lesson's expected circuit) actually improves accuracy.
4. **Baseline comparison, the core of the thesis** — raw LLM (no grid) vs. grid-augmented LLM vs. **classical CV / a dedicated vision model built specifically for this task** (e.g. a small custom-trained keypoint/object detector, no LLM involved at all). Not a formality — this is the actual research question: does the LLM approach earn its place, or does a purpose-built classical detector do just as well or better?
5. **Accuracy measurement** — hole-identification accuracy, false-positive/negative wiring calls, end-to-end latency.
6. **Failure analysis** — where it actually breaks (glare, wire color, occlusion, off-axis angle) and why.
7. **Lock the scope boundary** — decide, from the data, how much lesson complexity the accuracy can support for v1.

## 7. Multiple models, timing & where it runs

Three practical questions, answered with patterns already proven elsewhere rather than invented from scratch.

**Do we use multiple models, or different models for different parts of a lesson?**
- *Research phase:* yes — benchmark multiple candidate models (Claude, GPT-4/5-class, Gemini) against the same grid-overlay test set, per sub-skill (reading grid labels, reasoning about expected wiring, writing feedback) rather than one overall score. Extends research-plan step 4.
- *Production — two different, combinable levers:*
  - **Task-based routing**: send each kind of question to whichever model is actually best at that specific sub-skill, independent of price. Different models genuinely excel at different tasks — real deployments route product-search to one model for speed, complaints to another for tone/nuance, fraud analysis to a third for multi-step reasoning. ([Task-Based LLM Routing](https://portkey.ai/blog/task-based-llm-routing/))
  - **Cost-cascading**: a cheap/fast model handles the easy, common checks; escalate to a pricier model (or a human specialist) only when it isn't confident. Cuts cost 45–85% while keeping ~95% of quality. ([Cluster, Route, Escalate, arXiv](https://arxiv.org/pdf/2606.27457); [LLM Routing and Model Cascades](https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades))
  - On low confidence, the fallback is "ask the model that's good at this" (task-based), not just "ask a bigger one" (cost-based) — a human is the last resort if nothing's confident.
- Implication: the AI tier's uncertainty threshold becomes the natural trigger for offering to escalate to a human specialist — ties routing directly to the pricing tiers.

**Is the grid overlay/geometry step used constantly, or only for specific steps?**
- *Geometry/tracking* (finding the board, keeping the grid aligned) is cheap classical math — runs continuously, every frame, like any standard AR overlay.
- *The LLM reasoning call* ("is this wired correctly") is slow and costs money per call — fires only at checkpoints, primarily **the learner saying so** ("I'm done" / "check it"), with stillness/timeout as a backup signal only. Never every frame.

**Local or server?**
- *On-device:* geometry/tracking/overlay rendering. AR overlays lagging past ~100ms feel visibly broken — tighter than a network round trip can reliably guarantee.
- *Server/cloud (API):* the actual multimodal LLM call (Claude) — not something a phone runs locally, and since it fires occasionally, a 1–3s round trip is fine.
- Real-world precedent for this exact split: Apple Intelligence routes between on-device models and cloud compute; Google's Gemini Nano runs on-device but escalates harder requests to cloud Gemini. ([Edge Assisted Real-time Object Detection for Mobile AR](https://www.winlab.rutgers.edu/~luyang/papers/mobicom19_augmented_reality.pdf); [Hybrid Cloud-Edge LLM Inference](https://tianpan.co/blog/2026/04/10/hybrid-cloud-edge-llm-inference-when-to-run-on-device))

**Net decision:** local, continuous geometric tracking + grid rendering on-device (OpenCV) — cloud, checkpoint-triggered multimodal calls, routed cheap-first with escalation to a stronger model or a human when confidence is low. Still open: the exact confidence threshold for escalation, and which specific models pair well for the cascade — both wait on the benchmarking results from the research plan.

## 8. Generalizability & where to stop

- **Transfers:** any flat, gridded, standardized layout works the same way — a car **fuse box or relay panel** is nearly the same geometry problem as a breadboard. Worth a "future work" line, not a reason to widen scope now.
- **Doesn't transfer:** a 3D engine bay has no single flat plane and no fixed layout across car models — a different problem (semantic part recognition), and one where [ARI](https://ari.app/2026/05/introducing-aris-ai-wiring-diagrams/), [MECH AI](https://mechai.app/), [Fixomotive](https://fixomotive.in/repair), and [Identifix](https://www.identifix.com/wiring-diagrams/) already compete hard. Breadboard/Arduino stays the right first domain because it's the one place this exact technique is uncontested.

## Deferred / future work

- General object recognition → pull up manuals for *any* machine (scoped now to just this one board/domain)
- General appliance danger/safety detection across arbitrary device types (Arduino/breadboard is low-voltage DC, so lower real safety risk than mains appliances — natural reason to defer)

## Open decisions still on the table

- MVP form factor: phone-camera AR first (fast, cheap, no hardware dependency) vs. committing to AR glasses hardware from day one — currently leaning phone-first
- Kit vs. bring-your-own: does the learner need a specific recommended starter kit, or does it work with whatever Arduino gear they already have
- Pricing/tier model for human tutor vs. AI mode — not yet researched in depth

## Key sources

**Prior art & competitors:** [Electric Circuit AR](https://apps.apple.com/us/app/electric-circuit-ar/id1475867502) · [iFixit FixBot](https://www.ifixit.com/go/fixbot) · [TeamViewer Frontline](https://www.teamviewer.com/en-us/solutions/frontline/) · [RealWear Navigator](https://www.realwear.com/navigator-500/) · [Elec-Mate AI Tutor](https://www.elec-mate.com/tools/electrical-app-with-ai)

**Academic grounding:** [AITEE — Agentic Tutor for EE](https://arxiv.org/pdf/2505.21582) · [Spatial Blindspot of VLMs](https://arxiv.org/pdf/2601.09954) · [Grid-augmented vision](https://arxiv.org/pdf/2411.18270) · [Visual Position Prompt for MLLM Grounding](https://arxiv.org/pdf/2503.15426) · [Supporting Electronics Learning through AR](https://arxiv.org/pdf/2210.13820)

**Automotive generalizability check:** [ARI: AI Wiring Diagrams](https://ari.app/2026/05/introducing-aris-ai-wiring-diagrams/) · [MECH AI](https://mechai.app/) · [Identifix](https://www.identifix.com/wiring-diagrams/)

*Full bibliography with every source touched (100+ links, credibility-tagged) is in [`research-log.md`](./research-log.md).*
