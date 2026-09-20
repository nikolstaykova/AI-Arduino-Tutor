# AR Project — Research Log

Running log of everything researched and explored for this project. Newest entries at the top.

**Full sources/bibliography lives at the bottom of this file, organized by topic.**

---

## 2026-09-20 (check logic simplified: LLM only fires on mismatch, not for every comparison)

Refinement to the checkpoint verification step: the actual **comparison** between detected wiring and the expected answer doesn't need an LLM at all — once both sides are expressed as hole-names (detected vs. the Wokwi `diagram.json` answer key), checking whether they match is plain deterministic code (`detected == expected`), not an AI decision.

Revised flow: detect wiring (via whichever method wins the classical-CV-vs-LLM research comparison) → plain logic check against the answer key → **if it matches, done, no LLM call at all** → **only if it doesn't match, call the LLM** — not to re-decide correctness, but to work out what actually went wrong and explain it usefully to the learner ("you're one row off, move it to hole 13").

**Why this is a real improvement, not just a detail**: it means the common case (a learner gets it right, assuming reasonably designed lessons) never needs an LLM call at all — further cost/latency savings on top of the existing checkpoint-triggered and cascade/routing decisions already logged. It also puts the LLM to work exactly where it's actually good (natural-language explanation) instead of where it's weak (precise spatial judgment, per the Spatial Blindspot finding) — the "is it correct" decision is handled by deterministic logic, not asked of the model at all. Updated the system-flow steps 8–9 and the Q2 architecture answer in the README and artifact to reflect this.

## 2026-09-20 (sharpened the central research question: LLM vs. classical CV, not just "does the LLM idea work")

Refined framing suggested and adopted: instead of "does a geometry-preprocessed image + LLM reliably identify the exact hole/pin," the central question is now **"can a general-purpose LLM, combined with our geometric preprocessing, reliably perform hole-level verification of breadboard wiring — and how does that compare against classical CV / a dedicated vision model built specifically for this task?"**

Why this is better: it turns the project from "does our idea work in isolation" into a proper comparative research question with a defensible result either way — either the LLM approach earns its place over a purpose-built classical detector, or the classical approach turns out simpler and just as good, which is itself a legitimate finding. This was actually already half-present (research-plan step 4 mentioned "a small custom-trained detector" as one baseline) but buried as a checklist item rather than stated as the actual thesis question. Elevated it to the central question in the README, artifact, and made research-plan step 4 explicit that this comparison is the core of the thesis, not a formality.

## 2026-09-20 (key architecture split: pointing vs. verifying are two different problems)

Worked example that surfaced this: a lesson step says "connect the red wire to pin 13" — the system needs to (a) show the learner exactly where pin 13 is, and (b) later check whether they actually put the wire there. These turned out to be two genuinely different problems, one much easier than the other:

- **Pointing** ("show me where pin 13 is") — the target location is already known and fixed. Pin 13's physical position on an Arduino Uno is documented and identical on every Uno ever made. Once the geometry step has tracked the board (markers + homography, already planned), the system already knows where that point is in the current camera view — it just draws a highlight there. **Pure classical geometry/graphics, real-time, no LLM call needed at all.** This is not a detection problem — nothing is being discovered, a known template coordinate is just being transformed into the live camera's coordinate space.
- **Verifying** ("did the user actually put the wire there") — this is about detecting something new and unknown: wherever the learner's real wire actually ended up. That's the hard, unsolved half — the actual research (grid-augmented VLM grounding) is needed here, not for pointing.

**Practical implication — this de-risks the build timeline**: the "pointing" half of the AR experience isn't blocked on the research succeeding at all. It can be built and demoed early using only the geometry/tracking pipeline (Category A, already-existing tools), giving a working, visually convincing AR experience well before the harder verification research (Category B) is proven out. The two capabilities should be built and evaluated on separate tracks.

### Revised: it's actually three capabilities, not two
Follow-up scenario raised: what if the required components are just loose on a table, not yet placed? Their positions aren't known in advance — a red wire could be anywhere, in any orientation — so this isn't a geometry problem like pointing to pin 13 is. It's a genuine object-identification problem, and reveals a third, distinct capability:

1. **Identify loose objects** ("which one's the resistor, roughly where is it on the table") — a semantic recognition task, not a precision task. VLMs are actually good at this (the spatial-blindspot finding is specifically about *exact coordinates*, not "what is this thing"). Well-trodden ground — prior art already found: Roboflow's resistor-detection dataset, the PMC electronic-parts-classification paper. Does **not** need the novel research.
2. **Point to a known board location** (pin/output N) — pure geometry once the board is tracked. No AI needed at all.
3. **Verify the actual connection** (did the wire really end up there) — the hard, unsolved precision-grounding problem. This is the actual research contribution — nothing else in this list is.

Only #3 is genuinely novel/risky; #1 and #2 are both solvable with existing techniques and could be built and demoed well before the research is proven out.

### UX shape this implies: wide → close, two phases
Storyboarded through: **Phase A (wide shot, gathering)** — camera sees the cluttered table, system identifies and circles/highlights what's needed for this step (capability #1) — "there's your board, there's the red wire, there's the tool." **Phase B (close-up, working)** — learner physically gathers the circled items and brings them together near the camera to actually connect them — now capabilities #2 (point to the exact pin) and #3 (verify the connection) take over. The transition from wide to close view is itself a usable signal for switching system modes — no separate detector needed for "which phase are we in."

## 2026-09-20 (worked example: what the conversation actually sounds like, + corrected checkpoint trigger)

A concrete natural-conversation walkthrough was worked out, tagging each line to the capability/system piece behind it:

> **AI:** Ready to start? **User:** Yes.
> **AI:** Perfect — take the board and place it on the table. Before we start, I'll recap what's what — stop me any time if something's unfamiliar. *(conversational pacing — chat/voice, Category A)*
> **AI:** Step one: take the blue wire and connect it to output 3, using [tool]. Do you know how to use this tool? **User:** Yes. *(readiness check — skips the fallback micro-tutorial since the answer was yes)*
> **AI:** *(points to the exact physical location of output 3)* Here's output 3. Let me know once you're done — feel free to ask questions. *(pointing — capability #2, pure geometry, plus the open quick-question chat assistant available throughout)*
> **User:** I'm done.
> **AI:** Amazing — let me see your work. Show me what you've wired and I'll check it. *(← this is the hard research part: capability #3, grid-augmented verification against the Wokwi answer key)*

**Correction to the checkpoint trigger**: earlier entries listed "step finished, camera holds still, or the learner asks" as the checkpoint signal. This worked example shows the natural and simplest version is just **the learner saying so** ("I'm done" / "check it") — a spoken trigger, not an inferred one. Stillness/timeout detection should be a backup signal, not the primary one.

## 2026-09-20 (new feature: audio-paced tutor with readiness checks + fallback micro-tutorials)

Added to the system: the tutor speaks first at the start of each step (states what tools/components are needed), then asks the learner out loud whether they have the item and know how to use it, waiting for a spoken answer rather than assuming and rushing ahead. If the learner says no, a short predefined video for that specific tool/skill plays before continuing. Both pieces are Category A (existing tools, not research): TTS/STT are off-the-shelf APIs, and the fallback clips are just static pre-recorded content, no different in kind from the lesson content already being authored.

**Full end-to-end system flow, now documented in the "What we're building" section of the artifact/README** (9 steps): Author (Wokwi) → Validate (Wokwi CI) → Ship answer key → Learner starts step (tutor states requirements) → Readiness check (spoken) → Fallback micro-tutorial if needed → Guided build (paced spoken directions) → Checkpoint verification (geometry + LLM vs. Wokwi answer key) → Feedback. This replaces the earlier shorter 4-step "Author/Validate/Ship/Runtime" list with the complete experience, tying together every piece decided so far (Wokwi authoring, the grid/hole-naming research, checkpoint-triggered LLM calls, model routing, and now voice pacing) into one flow.

## 2026-09-20 (checked: does Wokwi support custom lessons/curriculum?)

No. Checked [Wokwi Classroom](https://wokwi.com/classroom) and [pricing](https://wokwi.com/pricing) directly — "Classroom" is an infrastructure licensing tier (faster build servers, more CI minutes, private IoT gateway, offline VS Code, custom library uploads), not a curriculum/lesson-authoring product. No assignment system, no grading, no guided-tutorial builder. Academic papers using Wokwi in real courses confirm the pattern: the instructor designs their own curriculum externally and just assigns Wokwi *projects* as the hands-on component.

**Implication**: the entire lesson/curriculum/progression layer (steps, gamification, sequencing, unlocking) is 100% ours to build — no overlap or competition risk with Wokwi as a product. Its role stays exactly as narrow as already established: a backend tool for defining + validating one lesson's correct-circuit data (`diagram.json` + CI), nothing about the learner-facing experience.

**Confirmed workflow (free tier, no Classroom needed)**: the free/Community plan explicitly includes "unlimited public projects" and unlimited simulations — so anyone can go to wokwi.com right now, build a custom lesson circuit (e.g. "Lesson 1: wire an LED to pin 13") in the ordinary editor, and its `diagram.json` already exists as soon as it's built — no paid plan required. That file *is* the lesson's hole-level answer key. Full loop: **author lesson in Wokwi (free, one-time, offline) → learner wears glasses at runtime → our geometry model maps the camera view onto the same hole-naming scheme → LLM compares detected wiring against the pre-authored diagram.json → feedback.** "Classroom" (paid) is unrelated to this — it's only for institutions needing simulation capacity for many students using Wokwi themselves, not for lesson authoring.

## 2026-09-20 (clarified: division of labor between our research and Wokwi)

Question raised: does Wokwi reduce the need for our own hole-identification research, or is it purely for checking? Answer: **it doesn't reduce it at all — Wokwi can't see a photo, it only knows circuits explicitly declared as data.** Clean split:
- **Wokwi's job**: define + auto-validate the *correct* circuit for a lesson (via `diagram.json` + Wokwi CI), producing a pre-verified answer key.
- **Our research's job (unchanged, still the core contribution)**: given a real photo of a real board a learner built, identify which real hole/pin each real component/wire is actually touching.
- **The "check" itself** then becomes simple engineering, not more research: once our vision pipeline outputs hole names in the same format as Wokwi's answer key, comparing detected-vs-expected is a plain structural comparison.

**New finding — reuse Wokwi's own hole-naming convention.** Checked: Wokwi's virtual breadboard already names every individual hole (e.g. `bb1:18t.d` = row 18, top section, column d) — confirms "which exact hole" is a well-established, formally nameable concept, not something to invent a scheme for from scratch. Recommendation: adopt the same row/section/column naming for our own grid overlay, so a lesson's Wokwi-authored `diagram.json` (already hole-level, e.g. `"bb1:18t.d" → "uno:13"`) can be compared directly against our vision pipeline's output with no translation layer.
- 🔍 [Wokwi breadboard pin naming discussion (GitHub issue)](https://github.com/wokwi/wokwi-elements/issues/31)
- 📄 [diagram.json format reference](https://docs.wokwi.com/diagram-format)

## 2026-09-20 (deeper look: Wokwi's automation tooling is a genuine asset, not just a sandbox)

Follow-up research pass on the two Arduino simulators. [Tinkercad Circuits](https://www.tinkercad.com/) (Autodesk) is a good teaching UI (handles analog circuits well, has a step-through debugger) but no confirmed public API/export for programmatic wiring checks was found. [Wokwi](https://wokwi.com/) turned out to have real developer infrastructure worth building on directly:

- **`diagram.json` format** — stores a circuit's wiring as explicit, structured connections, e.g. `["led1:A", "uno:13", "green", []]` (LED anode pin → Arduino pin 13). This is a genuine machine-readable answer key per lesson, not a picture someone has to eyeball. 📄 [diagram.json format reference](https://docs.wokwi.com/diagram-format)
- **Wokwi CI / `wokwi-cli`** — runs a simulation headlessly, checks serial output automatically, fails the test if behavior doesn't match expectation, integrates with GitHub Actions. Built for automated "does this circuit + code actually work" testing, no physical hardware required. 📄 [Wokwi CI docs](https://docs.wokwi.com/wokwi-ci/getting-started)

**Practical implication:** author each lesson once as a `diagram.json`, let Wokwi CI auto-confirm it actually behaves correctly (e.g. "LED blinks every 1 second") *before* it's ever shipped as that lesson's ground truth. Removes the need to hand-derive "what's the correct wiring" per lesson, and gives an exact, structured, version-controllable answer key — much stronger than the earlier vague "use a simulator for lesson design" note.

**Still true / unchanged**: this doesn't compete with the actual research gap — Wokwi validates a *virtual* circuit built inside its own software; it never watches a real physical breadboard through a camera. Updated the visual brief and README to reflect Wokwi specifically (dropped the vaguer Tinkercad-or-Wokwi framing) and to describe the CI/JSON tooling concretely.

## 2026-09-20 (system architecture: multi-model, call frequency, local vs. server)

### Q1: Do we use multiple models, or different models for different parts of a lesson?
Two separate concerns, and — per follow-up — two separate *routing philosophies* within "production":
- **Research phase**: yes — benchmark multiple candidate models (Claude, GPT-4/5-class, Gemini) against the same grid-overlay test set, **per sub-skill** (reading grid labels, reasoning about expected wiring, writing feedback) rather than one overall accuracy number. This extends the "baseline comparison" step already in the research plan (step 4).
- **Production, lever A — cost-cascading**: cheap/fast model handles the easy, common checks; escalate to a stronger/pricier model (or a human specialist) only when the cheap model isn't confident. Cuts cost 45–85% while keeping ~95% of quality in production systems using this pattern. Optimizes for cost.
  - 📄 [arXiv: Cluster, Route, Escalate — Cascaded Framework for Cost-Aware LLM Serving](https://arxiv.org/pdf/2606.27457)
  - 🔍 [LLM Routing and Model Cascades: How to Cut AI Costs Without Sacrificing Quality](https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades)
- **Production, lever B — task-based/capability routing** (raised as the more natural fit for us): route each *kind* of question to whichever model is empirically best at that specific sub-skill, independent of price — not a cost ladder at all. Real deployments do exactly this: product-search queries to one model for speed, customer complaints to another for tone/nuance, fraud analysis to a third for multi-step reasoning.
  - 🔍 [Task-Based LLM Routing: Optimizing LLM Performance for the Right Job](https://portkey.ai/blog/task-based-llm-routing/)
  - 📄 RouteLLM (UC Berkeley, ICLR 2025) — 85%+ cost reduction while keeping ~95% of GPT-4-level performance, sending only 14% of queries to the strong model
- **Combined fallback rule**: on low confidence, reroute to "the model that's actually good at this sub-task" (task-based) rather than automatically "a bigger/pricier model" (cost-based) — human specialist is the last resort if nothing is confident.
- **Implication for the product**: the AI tier's uncertainty threshold becomes the natural trigger for offering to escalate to a human specialist tutor — ties the routing pattern directly to the tiering model already decided.

### Q2: Is the grid overlay/geometry step used constantly, or only for specific steps?
Split into two different-cost operations, running on different schedules:
- **Geometry/tracking (finding the board, keeping the grid aligned)** — cheap classical CV math, runs continuously, every frame, like any standard AR overlay tracking.
- **LLM reasoning call ("is this wired correctly")** — slow (seconds) and costs money per call — should NOT fire every frame. Triggered only at checkpoints: user finishes a step and requests a check, camera holds still (implying they've stopped adjusting), or a lesson-defined milestone.

### Q3: Local or server?
Hybrid — this is the standard architecture for this class of app, not something to invent:
- **On-device (local)**: geometry/tracking/overlay rendering. AR overlays lagging more than ~100ms feel visibly broken to a person, tighter than a network round-trip can reliably guarantee.
- **Server/cloud (API)**: the actual multimodal LLM call (Claude). Frontier models aren't run on a phone; since the call only fires occasionally (per Q2), a 1–3s round trip is fine.
- Real-world precedent for exactly this split: Apple Intelligence routes between on-device models and cloud compute; Google's Gemini Nano runs on-device but escalates harder requests to cloud Gemini.
- 📄 [Edge Assisted Real-time Object Detection for Mobile Augmented Reality (WINLAB/Rutgers)](https://www.winlab.rutgers.edu/~luyang/papers/mobicom19_augmented_reality.pdf)
- 🔍 [Hybrid Cloud-Edge LLM Inference: When On-Device Models Beat the Cloud](https://tianpan.co/blog/2026/04/10/hybrid-cloud-edge-llm-inference-when-to-run-on-device)

### Resulting architecture decision
Local: continuous geometric tracking + grid rendering (OpenCV, on-device). Cloud: occasional, checkpoint-triggered multimodal LLM calls, routed cheap-first with escalation to a stronger model or a human specialist when confidence is low. Not decided yet: exact confidence-threshold mechanics for escalation, and which "cheap" vs. "strong" models to pair for the cascade (needs the model-benchmarking research to inform this).

## 2026-09-20 (correction: don't overstate the pipeline as decided)

Caught an overconfidence issue in how the architecture was being presented (in both the research log and the first version of the visual brief): the marker/ArUco → homography → grid-overlay → LLM pipeline was described as "the spine of the project" in a way that read as a settled mechanism. **It isn't settled — it's the leading hypothesis for how step 3 below might work, and testing it is the whole point of the research.**

Corrected framing going forward (plain version): **① See** (capture what the learner's camera sees) → **② Identify the board** (recognize the model — v1: Arduino Uno only) → **③ Map the points** (work out where every hole/pin actually is — this is the hard, unsolved part, not yet built or proven) → **④ Guide & catch errors** (use that map to direct the learner and flag mistakes). The marker/homography/grid-overlay idea is the strongest *candidate* for step 3, backed by the VLM spatial-grounding research already logged above, but it is explicitly unproven until the research plan (test set, accuracy measurement, baseline comparison) is actually run. Updated both the visual brief and README to reflect this — should avoid stating the mechanism as fact anywhere else in the project's materials.

## 2026-09-20 (★★★ FINAL PROJECT DEFINITION — what's engineering vs. what's research)

### The final idea, one paragraph
A platform that teaches real, hands-on skills (starting with Arduino/electrical circuits) by watching the learner through a camera and giving live, corrective guidance — either from a human specialist (premium tier) or an AI tutor (cheaper tier). The AI tutor is the platform's core differentiator and the final-year project's research contribution: it combines classical geometric computer vision with a multimodal LLM to precisely identify which exact breadboard hole/Arduino pin a component is connected to — something no existing product or published system does today for this domain.

---

### ✅ CATEGORY A — Build with existing, off-the-shelf tools (engineering, not research)
These are solved problems; use proven libraries/services rather than reinventing them, so project time goes toward the actual research contribution.

| Feature | Existing tool/approach to use |
|---|---|
| Marker detection (breadboard/board corners) | OpenCV's built-in ArUco marker detection — mature, off-the-shelf |
| Homography / grid mapping from markers | OpenCV standard geometry functions — well-established, no research needed |
| The "brain" doing semantic reasoning over the grid-annotated image | Claude (or another frontier multimodal LLM) via API — used as-is, not trained/fine-tuned |
| AI chat assistant for quick questions | Same LLM API, prompted with session/lesson context (RAG-lite: stuff the current lesson state into the prompt) |
| Secure/encrypted specialist↔user channel | Existing secure protocol — TLS, or WebRTC's built-in DTLS-SRTP for live video. **Never hand-roll cryptography.** |
| Performance/mistake logging | Standard application logging + basic stats (accuracy over time, error-type breakdown) — software engineering, not novel research, but still required for the dissertation's evaluation chapter |
| Tool-selection verification (stretch goal) | Same object-detection/VLM pipeline as the core system, just pointed at a tool instead of a wire — reuse, don't rebuild |

### 🔬 CATEGORY B — The actual research (this IS the final-year project's contribution)
**Central question to research and answer: can a geometry-preprocessed image + a general-purpose multimodal LLM reliably identify the exact breadboard hole / Arduino pin a wire or component is connected to — accurately and consistently enough to power a real AI tutor?**

This is genuinely unsolved (confirmed: SmartBreadboard-3D's detection module is an unbuilt stub; the Roboflow project only does plain object detection, not grid-grounded hole identification; published VLM research — [Spatial Blindspot of VLMs](https://arxiv.org/pdf/2601.09954) — confirms raw multimodal LLMs are unreliable at this without help). What needs actual experimentation:
- How to best generate and render the grid overlay (line thickness, transparency, labeling scheme) for maximum LLM accuracy — draws on [Grid-augmented vision](https://arxiv.org/pdf/2411.18270) and [Visual Position Prompt](https://arxiv.org/pdf/2503.15426) as starting points, but needs to be adapted and tuned specifically for breadboard/Arduino imagery
- How much domain documentation/context to feed the LLM alongside the image (breadboard conventions, current lesson's expected circuit) to maximize correctness
- Measuring real accuracy: build a test set of real breadboard photos with ground-truth wiring, run the pipeline, measure hole-identification accuracy, error patterns, and where it fails
- Comparing this approach against baselines (e.g., raw LLM with no grid, or a custom-trained small object detector) to justify the architecture choice with data, not just intuition
- Deciding the safe scope boundary: one board (Arduino Uno), one/few lesson types — and documenting how the accuracy holds up or degrades as complexity increases

**This is the part of the dissertation that is a genuine, original contribution** — everything in Category A is "we used the right existing tool for a solved problem"; Category B is "we designed, built, and evaluated a new pipeline for a problem nobody has published a working solution to."

### 🕓 Deferred / future work (not built now, mentioned in dissertation as future direction)
- General object recognition → pull up manuals for *any* machine (scoped now to just the one board/domain instead)
- General appliance danger/safety detection across arbitrary device types (Arduino/breadboard is low-voltage DC, so lower real safety risk than mains appliances anyway — natural reason to defer this)

### Generalizability check: does the core technique transfer beyond breadboards? (e.g. car repair)
- **Transfers directly**: any flat, gridded, standardized structure — e.g. a car's **fuse box / relay panel** is almost the same geometric problem as a breadboard (flat, regular grid, known layout per model). Same pipeline (marker/corner detection → homography → grid overlay → LLM) applies with minimal adaptation.
- **Does not transfer directly**: a full 3D engine bay — irregular, occluded, no single flat plane, no fixed template across car models. That's a different problem (plain object/part recognition, which VLMs already handle reasonably via semantic knowledge) rather than the precise coordinate-grounding trick.
- **Market reality check** — car repair AI is already mature/crowded, unlike breadboards: 🏢 [ARI: AI Wiring Diagram Assistant](https://ari.app/2026/05/introducing-aris-ai-wiring-diagrams/), 🏢 [MECH AI](https://mechai.app/), 🏢 [Fixomotive Repair](https://fixomotive.in/repair), 🏢 [Identifix wiring diagrams](https://www.identifix.com/wiring-diagrams/) — all generate wiring diagrams/fuse data by make/model/year already. None do live-camera geometric grounding on the physical part in front of the user (they show a diagram to read, not AR-overlaid live verification) — so the technique would still differentiate, but this is a funded, populated market, unlike the empty breadboard/Arduino space.
- **Conclusion**: good validation the core research generalizes (worth a "future work" line in the dissertation), but confirms breadboard/Arduino remains the right FYP domain — it's the one place this exact technique has zero competition.

## 2026-09-20 (Architecture validated: grid-augmented VLM grounding for exact hole/pin ID)

### Question raised
Is it true that no current AI model — not even a frontier multimodal LLM like Claude — can reliably identify the exact breadboard hole/Arduino pin from an image? And could a Claude-class model + strong domain documentation + geometric preprocessing solve it?

### Findings — both parts confirmed by real research
**Part 1 — yes, this is a documented, real limitation of VLMs (including the Claude/GPT-4V/Gemini class), not just something nobody tried:**
- 📄 [arXiv: The Spatial Blindspot of Vision-Language Models](https://arxiv.org/pdf/2601.09954) — dedicated paper on this exact weakness
- 📄 [arXiv: ViewSpatial-Bench — Evaluating Multi-perspective Spatial Localization in VLMs](https://arxiv.org/abs/2505.21500)
- 📄 [arXiv: From Pixels to Places — geolocalization benchmark](https://arxiv.org/html/2508.01608v1) — general finding: VLMs "lack the reliability required for fine-grained or high-precision localization tasks compared to classical [geometric] methods"

**Part 2 — the proposed fix (VLM + geometric preprocessing/documentation) is a real, published, named technique, not something to invent from scratch:**
- 📄 [arXiv: Grid-augmented vision — simple yet effective approach for enhanced spatial understanding in multimodal agents](https://arxiv.org/pdf/2411.18270) — overlays a grid onto the image before feeding to the model; converts a hard coordinate-regression problem into an easy "which cell" classification problem
- 📄 [arXiv: Visual Position Prompt for MLLM based Visual Grounding](https://arxiv.org/pdf/2503.15426) — same family, structured spatial cues burned into the image
- General research finding: "external scaffolding — adding annotations, grids, or partitions to the input image — consistently improves model performance" on spatial/counting/description tasks

### ⭐ CORE ARCHITECTURE — central contribution of the whole project
> So the real architecture for your FYP is: homography/marker-based grid detection (classical CV, deterministic) → burn that grid visibly onto the image → feed to a multimodal LLM with strong domain documentation about breadboard/Arduino layout → ask it "which labeled cell is this wire in." You're not fighting the model's weakness, you're using classical geometry to hand it exactly the crutch this published research shows works. And since nobody's applied this specifically to breadboards/Arduino (SmartBreadboard-3D never finished its detection module; the Roboflow project does plain object detection, not this grid+VLM grounding approach), applying and evaluating it for this domain is a genuinely original contribution.

**This is the spine of the dissertation — everything else (chat assistant, tool recognition, safety detection, etc.) is a secondary feature built on top of this core pipeline, not a replacement for it.**

### Resulting architecture for the FYP AI-tutor component
1. Detect breadboard/Arduino board corners (via ArUco markers, per earlier decision) → classical CV, deterministic
2. Compute homography → derive the known grid (breadboard hole rows/columns, or Arduino pin template for the fixed board model, e.g. Uno)
3. **Burn that grid visibly onto the image** (labeled cells/rows) — this is the "geometric preprocessing" step
4. Feed the grid-annotated image + strong domain documentation (breadboard/Arduino layout conventions, lesson-specific expected wiring) to a multimodal LLM (Claude) as the reasoning/semantic layer
5. Ask it to identify component placement and wiring against the expected circuit for the current lesson, generate feedback

### Why this matters for the project
- Confirms genuine novelty: nobody has applied this "grid-augmented VLM grounding" technique to breadboards/Arduino specifically (checked — SmartBreadboard-3D's detection module is an unbuilt stub; Roboflow's resistor-detection project uses plain object detection, not this approach).
- De-risks the FYP significantly: no need to train a custom object detector from scratch or collect a large labeled dataset — leverages an existing frontier multimodal model (Claude) for the semantic/component-recognition part, while the hard geometric grounding is handled by classical, well-understood CV (homography), not by trying to force the LLM to do something the literature says it's bad at.
- Gives a clean, citable methodology section for a dissertation: apply + evaluate a published spatial-grounding technique (grid-augmented VLM prompting) in a novel domain (breadboard/Arduino circuit verification for AR-guided tutoring).

## 2026-09-20 (Final Year Project scoping: which AI piece to actually build)

### Context
This platform is the user's final year project, which requires a data-science/ML component. Two candidate AI features identified:
1. **"AI instead of tutor"** — AI vision system fully replaces a human specialist for guidance (the core differentiator of the business idea).
2. **"AI assists the specialist"** — AI copilot that helps a human tutor identify tools/components/steps, human stays in the loop as final authority.

### Key technical sub-question: can we identify the exact breadboard hole / Arduino pin the user should connect to?
**Yes — and it's more tractable than expected**, because a breadboard/Arduino board is a known, fixed grid, not an arbitrary scene:
1. Detect board corners (via edge detection, or much more reliably via printed ArUco/fiducial markers at the corners)
2. Compute a homography from the detected corners
3. Map any point in the camera frame to an exact row/column hole using the breadboard's known standard grid spacing — no need to ML-detect every individual hole
4. Same approach for Arduino pin headers: fix the target board to one known model (e.g. Arduino Uno) for v1, detect board outline/orientation, overlay the known/documented pin-position template

**Feasibility check:** searched for existing implementations — [SmartBreadboard-3D (GitHub)](https://github.com/sasivaradhansbee25-hue/SmartBreadboard-3D) attempts exactly this (breadboard detection + 3D visualization) but its own README confirms the actual hole-detection CV module is still an unbuilt stub ("Phase 9+"). **Nobody has shipped this specific piece yet** — confirms it's a real, well-scoped, unsolved technical problem (good for a FYP contribution), not something to build from an existing library.
- Other prior art found on component-level detection (not hole-level): [Roboflow: Resistor Detection dataset/model](https://universe.roboflow.com/circuits-project/resistor-detection-5azes) — explicit goal "take a picture of breadboard, circuit auto-simulated, tells you if it's safe/fully connected" — same vision, same unsolved-at-scale problem.
- [PMC: Vision-Based Detection and Classification of Used Electronic Parts](https://pmc.ncbi.nlm.nih.gov/articles/PMC9738186/) — academic precedent for component classification (1,734-image dataset, capacitor/potentiometer/regulator), useful methodology reference even though not breadboard-hole-specific.

### Recommendation / decision
Go with **Option 1 (AI instead of tutor), tightly scoped**: one board (Arduino Uno only for v1), one starter lesson (e.g. LED + resistor), full pipeline = corner/marker detection → homography → grid-position mapping → component detection → wiring correctness check → feedback. This is harder-sounding but the core hard part (exact hole ID) decomposes into a well-defined, solvable geometry + CV problem rather than an open-ended one. It also doubles as both the FYP's data-science contribution AND the platform's core product differentiator — stronger than Option 2 (AI-assists-human), which would build most of the same underlying tech without it standing alone as a complete system.

### Next steps
- Decide: markers (ArUco stickers on breadboard corners) for v1 reliability, vs. pure corner/edge detection (harder, more "impressive" but riskier) — markers strongly recommended for a FYP timeline.
- Scope exact v1 lesson + success criteria (e.g. "detect LED + resistor correctly placed across specific breadboard rows, powered from Arduino digital pin 13") before writing any code.
- Look into whether to train a custom object detector (YOLO-style) for components (LED, resistor, wires, Arduino board) vs. use an existing pretrained model + fine-tune — dataset size/collection effort needs its own research pass.

## 2026-09-20 (DECISION: starting domain = Arduino/electrical)

### Decision
First domain locked in: **Arduino / basic electrical circuits**, hands-on, AR-assisted. Confirmed via search that this exact combination doesn't exist — what's out there is either (a) developer tutorials on building AR apps that interface with Arduino hardware as a maker project (Vuforia+Unity+Arduino tutorials on Instructables/Hackaday), or (b) plain non-AR Arduino programming tutorial apps (e.g. a 200-lesson text/video app). No gamified, AR-guided, tutor-or-AI consumer learning product for Arduino/electrical exists yet.
- 🔍 [Hackaday.io: Augmented Reality and Arduino for Interaction](https://hackaday.io/project/6506-augmented-reality-and-arduino-for-interaction)
- 🔍 [Instructables: AR using Unity3D, Vuforia and Arduino](https://www.instructables.com/Augmented-Reality-using-Unity3D-Vuforia-and-Arduin/)
- 🏢 [Arduino Programming Tutorial app (App Store) — non-AR baseline competitor for content/curriculum structure](https://apps.apple.com/es/app/arduino-programming-tutorial/id6446804186?l=es-ES)

### Why Arduino/electrical specifically (recap of reasoning)
- Real physical hardware, real observable pass/fail state (circuit works / LED lights up / code runs)
- Huge existing maker community and teaching content to draw curriculum structure from, but no one has made it AR + gamified + tutor/AI hybrid
- Natural fit for the "AI vs. human tutor" tier: AI can plausibly judge simple circuit correctness (component placement, wiring) today; harder/ambiguous cases escalate to human tutor
- Sets up the platform's general engine (camera watches real task → guidance → correction → gamified progress) cleanly, before considering other domains (cooking, repair, etc.) later

### Next steps to scope v1
- Define lesson 1 scope precisely (e.g., "light an LED with a resistor on a breadboard" as the very first lesson) and map out first 5-10 lessons.
- Decide MVP form factor: phone-camera AR (fastest, cheapest, no hardware dependency) vs. AR glasses from day one. (Leaning phone-first based on earlier reasoning — revisit and confirm.)
- Research what a "kit" would need: does the learner need a specific starter kit (breadboard, resistors, LEDs, Arduino board) shipped/recommended, or should it work with whatever they already own? Check existing kits (Arduino Starter Kit, Elegoo, Kano) for pricing/contents baseline.
- Research computer-vision approach: how would the app actually detect "is this wired correctly" — fiducial markers on breadboard holes? Component recognition via ML model? Needs its own research pass.
- Revisit AI-vs-human tutor tiering/pricing once lesson scope is clearer.

## 2026-09-20 (concept consolidated: multi-domain hands-on learning platform)

### Current working definition of the platform
A platform that connects people who want to **learn a real, hands-on skill** (not theory — actually doing the physical task, seeing it get fixed/built/cooked in front of them) with either:
- **A live human specialist/tutor** — premium tier, real expert watching via camera/glasses, guiding in real time.
- **AI instead of a tutor** — cheaper tier, same live-guidance interaction pattern but powered by AI vision/tutoring instead of a person.

Domain is no longer locked to "electronics/circuits" — that's just the first proposed track. **Cooking** was raised as a second example domain (AI or human watches you cook a real dish, corrects technique in real time — knife cuts, heat control, timing). So the platform is explicitly **multi-domain**: circuits/electronics and cooking are two candidate first tracks, chosen because both involve a real physical task, real observable success/failure state, and benefit from live corrective guidance.

**Why this framing matters:** the underlying engine (live camera feed → specialist-or-AI watches → real-time correction/guidance → optional gamified progress tracking) is domain-agnostic. This is the same core mechanic explored across all prior sessions (remote expert assist for industrial work, circuit learning, appliance repair) — the platform's value is in that generic engine, and the domain (repair / circuits / cooking / anything else hands-on) is a content layer on top, with tutor-vs-AI as a pricing/tier lever rather than a different product.

### Open questions to resolve next
- Pricing/tier model: human tutor (premium, likely per-session or subscription with limited credits) vs. AI (cheaper, likely flat subscription) — need to research what similar hybrid human+AI platforms charge (e.g., tutoring platforms, language-exchange apps with AI vs human tutors).
- Which domains actually work well for AI-only guidance today vs. which still need a human (e.g., is AI vision good enough yet to judge "is this knife cut correct" or "is this circuit correctly wired" reliably?).
- Should the first launch pick ONE domain (e.g., circuits, since more differentiated/less crowded) or launch with two to prove the "generic engine, many domains" pitch to investors/users?

## 2026-09-20 (pivot: consumer skill-learning direction)

### Concept evolution
Pivoted from "B2B remote expert assistance" toward a **consumer learning platform**: "Duolingo, but for real electronics/circuits, in AR." Core idea:
- User builds a **real physical circuit** on their desk (not a simulation).
- AR glasses watch the circuit via camera + show AR overlays (hints, checks, next steps).
- User picks help mode: **(a) live human expert/trainer** (bridges back to the original remote-specialist idea, as a premium tier) **or (b) integrated AI** that watches via the glasses' camera and gives real-time feedback/tutoring — no human needed for most sessions.
- Wrapped in Duolingo-style gamification: streaks, XP, skill tree, bite-sized daily lessons.

### Why this combo is (still) open — checked existing players
Nothing found combines all of: real AR + real physical hardware + gamified daily-habit design + AI-or-human tutor toggle. Closest existing pieces, each covering only part of it:
- **"Electric Circuit AR" app** — AR circuit visualization/drag-drop building, but no gamified habit loop, no real physical circuit, no AI/human tutor.
- **Brilliant** — excellent Duolingo-grade gamification for STEM, but flat-screen only, no AR, no physical hands-on component.
- **LearnHub** — gamifies engineering coursework, but screen-based, curriculum-bound, not a consumer app.
- **AITEE (arXiv paper, "Agentic Tutor for Electrical Engineering")** — academic research on an AI agent tutor specifically for EE — validates that an AI circuit-tutor is a real, studied idea, but it's a research prototype, not a product, and not AR/glasses-based.
- **Elec-Mate AI Tutor** — real product, but it's exam-prep Q&A for licensed electricians on a phone, not hands-on real-time circuit feedback.
- **Intelgic / iFactoryApp AI vision inspection** — industrial machine-vision systems that already *can* detect wiring faults, loose wires, cross-connected terminals on control panels/PCBs. Proves the underlying computer-vision capability (detecting real wiring problems from a camera feed) is mature and already deployed — just not aimed at a consumer learner.
- **Google Project Astra / OpenAI GPT-6 Astra** — explicitly described (by commentators) as able to "observe a science experiment or student-built prototype and respond while learning is happening." This is close to the exact interaction wanted, but it's a general-purpose multimodal AI assistant/research prototype, not a dedicated circuit-learning product with gamification, hardware kit, or glasses integration.

**Conclusion:** every individual building block (AR circuit visualization, gamified STEM app, AI EE tutor research, industrial wiring-fault computer vision, multimodal AI glasses) already exists somewhere. Nobody has fused them into one consumer product. This is a real, well-defined gap.

### Key open technical/product decision: which glasses?
Not all "AI glasses" can support this — need BOTH a camera (to watch the real circuit) AND a visual AR display (to overlay hints/checks). Two different product categories exist right now:
- **Audio-only AI glasses** (original Ray-Ban Meta) — camera + AI, but no visual overlay, so hints would be audio-only (still usable, just less "AR").
- **Display AI glasses** (Meta Ray-Ban Display, XREAL One, Rokid) — actually show a visual overlay in your field of view, which is what "AR" really implies for showing circuit diagrams/checkmarks over the real board.
- Need to evaluate: cost, availability, SDK/API access for building a custom app on each of these before picking a hardware target. Also worth considering a **phone-AR MVP first** (skip glasses hardware risk entirely) before committing to a specific glasses platform.

### Next steps
- Decide MVP form factor: phone AR app first (fast, cheap, no hardware dependency) vs. building for a specific AR glasses SDK from day one.
- Look into what a "circuit kit" would need to look like (breadboard + real components + fiducial markers/QR codes so the camera can identify circuit state) — check if similar physical-kit-plus-app products exist (e.g., littleBits, Snap Circuits, Kano) since they solve a similar "teach hardware physically" problem without AR.
- Scope down starting domain: full "electronics/circuits" is broad — decide if v1 targets absolute beginners (batteries/LEDs/resistors) or a specific track (Arduino, basic house wiring, etc.).

## 2026-09-20

### Project concept
AR/VR glasses that connect a **remote specialist** to a **user in the field**, so the specialist can give live visual guidance in some domain (industrial repair, field service, medical, etc. — domain not yet decided). This category already exists commercially as "remote expert assistance" / "connected worker" tech — researching what's on the market.

### Market landscape (existing players)

**Hardware (the glasses themselves):**
- **RealWear Navigator Z1 / 500 / 520** — category leader for ruggedized, hands-free, voice-controlled industrial use. Broad software compatibility.
- **Vuzix M400 / Blade / Shield** — value alternative to RealWear; lighter-duty, cheaper, still supports major connected-worker platforms.
- **Microsoft HoloLens 2** — dominant for AR overlay + remote expert sessions + immersive training; true see-through AR (not just a camera+screen).
- **Iristick** — ATEX-certified, built for hazardous environments (oil & gas, explosive atmospheres).
- **Rokid, Almer, Moziware, XOEye, ThirdEye Gen** — other smart-glasses hardware makers supported by remote-assist software platforms.
- Consumer-adjacent AR glasses (XREAL, RayNeo, Even Realities, Brilliant Labs, Ray-Ban Meta) exist but are aimed at consumer AR/media, not specialist-guidance workflows — worth watching as the tech gets cheaper/lighter, but not built for this use case today.

**Software (the platform connecting specialist ↔ user, usually hardware-agnostic):**
- **TeamViewer Frontline** — most comprehensive "connected worker" suite; `xAssist` module does AR remote assistance (live annotation over video feed), plus `xInspect` (guided maintenance), `xMake` (assembly), `xPick` (warehouse picking). Supports Vuzix, RealWear, Almer, Moziware, Rokid hardware.
- **Microsoft Dynamics 365 Remote Assist** — built for HoloLens 2 but also runs on Android/iOS; heads-up, context-aware guidance from an off-site expert.
- **Scope AR WorkLink** — combines AR work instructions + remote assistance in one platform; strong CAD import (good fit if there's existing CAD content); cross-platform (iOS/Android/Windows/headsets).
- **Librestream Onsight** — oldest player (since 2003), strongest for extreme/harsh environments.
- **VSight** — another industrial remote-support platform, compatible with multiple smart glasses brands.
- Oculavis mentioned in industry round-ups but no solid data pulled yet — needs a dedicated look.

### How the core interaction actually works
Field user streams live video (POV) from the glasses/device → remote specialist sees it in real time → specialist overlays annotations (arrows, highlights, text, sometimes 3D markers pinned in space) directly onto the user's view → user gets hands-free, heads-up guidance without needing to hold a phone or look away from the task.

### Market signal / why this space is active
- AR+VR market forecast at ~$50.9B in 2026 (AR software alone ~$13B).
- Claimed impact: up to 64% faster maintenance/repair tasks, up to 38% fewer errors when using AR remote assistance vs. no guidance.
- Modern glasses are now <100g, full-shift battery life, and much cheaper than 5 years ago — hardware is no longer the main blocker, software/workflow fit is.
- Smart glasses shipped ~7.25M units in 2025 (~50% of all XR hardware shipped).

### Open questions / next steps
- Which domain/field are we targeting (medical, industrial/field-service, consumer DIY, education)? Most existing players are enterprise/industrial — a consumer or medical angle looks less crowded.
- Need to look into: Oculavis in more depth; medical-specific remote-guidance AR (surgical/telehealth use cases); actual pricing/cost of entry per platform; latency/bandwidth requirements; any 2026 new entrants beyond what's listed here.
- Should map "hardware options" against "software options" since most software is hardware-agnostic (buy any supported glasses + subscribe to a platform).

### Sources
- [See What I See: How Augmented Reality is Changing Remote Support](https://blitzz.co/blog/augmented-reality-remote-assistance-guide-2026)
- [Field Service – Vuzix Corporation](https://www.vuzix.com/pages/field-service)
- [Remote Assist Solutions | Vuzix Smart Glasses](https://www.vuzix.com/pages/vuzix-remote)
- [Best Smart Glasses for Industrial Workers 2026](https://reliamag.com/guides/best-smart-glasses-industrial/)
- [Best AR Glasses 2026: Comparison & Buyer's Guide](https://vr.org/ar-glasses)
- [Industrial Smart Glasses for AR Remote Support | VSight](https://vsight.io/industrial-smart-glasses-vsight-compatibility/)
- [Best Smart Glasses 2026 — Top 10 Picks](https://smartglasses.computer/blog/best-smart-glasses-2026)
- [TOP 5 Augmented Reality Remote Assistance Software Tools in 2026](https://hqsoftwarelab.com/blog/augmented-reality-remote-assistance-software/)
- [10 Best Remote Visual Support Software in 2026](https://blitzz.co/blog/best-remote-visual-support-software-in-2026)
- [Best AR Remote Assistance Software for Industrial Operations — 2026 Guide](https://www.continuumar.io/resources/compare/best-ar-remote-assistance-software.html)


---

## Sources & Links (full bibliography, by topic)

Credibility key: 🏢 = official company/product page (primary), 📄 = academic paper/preprint, 📰 = independent journalism, 🔍 = SEO/blog content (secondary — useful for landscape scanning, not for citing as proof on its own).

### Remote expert assistance — hardware
- 🏢 [RealWear Navigator 500](https://www.realwear.com/navigator-500/) — official product page
- 🏢 [Vuzix Remote Assist Kit](https://www.vuzix.com/pages/vuzix-remote) — official
- 🏢 [Vuzix Field Service](https://www.vuzix.com/pages/field-service) — official
- 🏢 [Iristick](https://www.iristick.com/) — official, lists real clients (Bayer, Siemens, JBT)
- 🔍 [Best Smart Glasses for Industrial Workers 2026 — Reliamag](https://reliamag.com/guides/best-smart-glasses-industrial/)
- 🔍 [Best AR Glasses 2026 Buyer's Guide — VR.org](https://vr.org/ar-glasses)
- 🔍 [Best Smart Glasses 2026 — smartglasses.computer](https://smartglasses.computer/blog/best-smart-glasses-2026)
- 🔍 [Wareable: best smart glasses and AR specs](https://www.wareable.com/ar/the-best-smartglasses-google-glass-and-the-rest)
- 🔍 [AI Smart Glasses Market Report — InsightAce Analytic](https://www.insightaceanalytic.com/report/ai-smart-glasses-market/3370)

### Remote expert assistance — software platforms
- 🏢 [TeamViewer Frontline](https://www.teamviewer.com/en-us/solutions/frontline/) — official, xAssist/xInspect/xMake/xPick
- 🏢 [Microsoft: Dynamics 365 Remote Assist docs](https://docs.microsoft.com/en-us/dynamics365/mixed-reality/remote-assist/) — official Microsoft Learn documentation
- 🔍 [VSight — industrial smart glasses compatibility](https://vsight.io/industrial-smart-glasses-vsight-compatibility/)
- 🔍 [G2: Dynamics 365 Remote Assist vs TeamViewer Frontline](https://www.g2.com/compare/dynamics-365-remote-assist-vs-teamviewer-frontline) — review-aggregator comparison
- 🔍 [TOP 5 AR Remote Assistance Software 2026 — HQ Software Lab](https://hqsoftwarelab.com/blog/augmented-reality-remote-assistance-software/)
- 🔍 [Best AR Remote Assistance Software — ContinuumAR](https://www.continuumar.io/resources/compare/best-ar-remote-assistance-software.html) (covers Scope AR WorkLink, Librestream Onsight)

### Real-world case study (independent, non-vendor)
- 📰 [AR Insider: Boeing Streamlines Aircraft Assembly with AR](https://arinsider.co/2022/08/23/case-study-boeing-streamlines-aircraft-assembly-with-ar/)
- 📰 [The IoT Integrator: Smart Glasses, AR Add Fuel to Boeing's Assembly Line](https://www.theiotintegrator.com/aerospace/smart-glasses-augmented-reality-add-fuel-to-boeing-s-assembly-line)
- 📰 [Forbes (Sept 2026): The Next Factory Interface May Be A Pair Of Glasses](https://www.forbes.com/sites/ethankarp/2026/09/18/the-next-factory-interface-may-be-a-pair-of-glasses-if-were-smart/)

### Adjacent niches explored (insurance, medical, veterinary)
- 🏢 [SightCall: AR for Insurance](https://sightcall.com/blog/augmented-reality-for-insurance-2/)
- 🏢 [AR Genie: AR in Insurance](https://www.argenie.ai/solutions/industries/insurance)
- 🔍 [Zoho Lens: AR Remote Assistance Trends 2026](https://www.zoho.com/lens/ar-remote-assistance-trends.html)
- 📄 [arXiv: CPR Emergency Assistance Through Mixed Reality Communication](https://arxiv.org/pdf/2312.09150)
- 📄 [NCBI/PMC: Telemedicine for Remote Surgical Guidance in ERCP](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7834938/)
- 📄 [NCBI/PMC: Augmented Reality as a Telemedicine Platform for Remote Procedural Training](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5676722/)
- 📄 [ScienceDirect: Perceptions About AR in Remote Medical Care (emergency telemedicine providers)](https://www.sciencedirect.com/org/science/article/pii/S2561326X23000471)
- 🔍 [Pawlicy Advisor: Veterinary Telemedicine guide](https://www.pawlicy.com/blog/veterinary-telemedicine/)
- 🔍 [dvm360: Understanding Veterinary Telehealth](https://www.dvm360.com/view/a-comprehensive-guide-to-understanding-veterinary-telehealth)
- 📄 [Veterinary Evidence: Veterinary Telemedicine literature review](https://veterinaryevidence.org/index.php/ve/article/view/349)

### AR + electronics/circuits learning apps
- 🏢 [Electric Circuit AR — App Store](https://apps.apple.com/us/app/electric-circuit-ar/id1475867502)
- 🏢 [Electric Circuit AR — Google Play](https://play.google.com/store/apps/details?id=com.threesixtyed.electriccircuitar&hl=en_ZA)
- 🏢 [360ed: Electric Circuit AR Learning Kit (kids' STEM toy)](https://360ed.com/products/electric-circuit-ar-learning-kit-interactive-augmented-reality-flashcards-for-kids-10-educational-electronics-game-stem-toys-for-children)
- 📄 [arXiv: Supporting Electronics Learning through Augmented Reality](https://arxiv.org/pdf/2210.13820)
- 📄 [ESPOL: Virtual Circuits — An Augmented Reality circuit simulator (PDF)](https://www.cti.espol.edu.ec/sites/default/files/docs_pdf/Virtual_Circuits_An_Augmented_Reality.pdf)
- 🔍 [Electric Circuit Simulator Applying AR and Gamification (academia.edu)](https://www.academia.edu/64164426/Electric_Circuit_Simulator_Applying_Augmented_Reality_and_Gamification)

### Gamified learning platforms (non-AR benchmark)
- 🏢 Brilliant, LearnHub — referenced via: [NerdSip: Duolingo but for Everything?](https://nerdsip.com/blog/duolingo-but-for-everything)
- 🔍 [Yu-kai Chou: 10 Best Gamification Education Apps](https://yukaichou.com/gamification-examples/10-best-gamification-education-apps/)
- 🔍 [ResearchGate: Analyzing Gamification of Duolingo](https://www.researchgate.net/publication/310623230_Analyzing_Gamification_of_Duolingo_with_Focus_on_Its_Course_Structure)

### AI tutors / AI vision for circuits & wiring
- 📄 [arXiv: AITEE — Agentic Tutor for Electrical Engineering](https://arxiv.org/pdf/2505.21582)
- 🏢 [Elec-Mate: AI Tutor for electricians](https://www.elec-mate.com/tools/electrical-app-with-ai)
- 🏢 [Intelgic: Control Panel Box Inspection using AI/Machine Vision](https://intelgic.com/control-panel-box-inspection-using-AI-and-machine-vision-camera-system)
- 🏢 [iFactoryApp: AI Vision Cable & Wire Defect Inspection](https://ifactoryapp.com/ai-vision-camera/ai-vision-cable-wire-defect-inspection)
- 🏢 [iFactoryApp: AI Vision Camera for Electronics/PCB Manufacturing](https://ifactoryapp.com/ai-vision-camera/ai-vision-camera-electronics-pcb-manufacturing)

### Multimodal AI glasses (hardware capability check)
- 🏢 [Meta: From research to product — Multimodal AI in Ray-Ban Meta glasses](https://www.metacareers.com/blog/from-research-to-product-multimodal-ai-in-ray-ban-meta-glasses/)
- 🏢 [Meta: Ray-Ban Meta Display glasses](https://www.meta.com/ai-glasses/meta-ray-ban-display/)
- 🏢 [Ray-Ban: Meta AI Glasses specs](https://www.ray-ban.com/usa/l/discover-ray-ban-meta-ai-glasses)
- 📄 [ZenML: Edge AI Architecture for Wearable Smart Glasses (LLMOps case study)](https://www.zenml.io/llmops-database/edge-ai-architecture-for-wearable-smart-glasses-with-real-time-multimodal-processing)
- 🔍 [Wikipedia: Ray-Ban Meta](https://en.wikipedia.org/wiki/Ray-Ban_Meta)
- 🔍 [Google Project Astra & learning — Medium](https://medium.com/@codecraftsphere/how-googles-project-astra-can-help-democratize-learning-b69221335cac)
- 🔍 [What Is Google's Project Astra? 5 Things K-12 Teachers Need to Know](https://davidpblross.substack.com/p/what-is-googles-project-astra-5-things)
- 🎥 [YouTube: Project Astra — Exploring the Future of Learning with an AI Tutor Research Prototype](https://www.youtube.com/watch?v=MQ4JfafE5Wo)

### Controller/joystick stick-drift repair (existing tools — NOT AR-based, confirms gap + demand)
- 🏢 [DriftGuard — Google Play (calibration/diagnostic tool, no AR)](https://play.google.com/store/apps/details?id=com.vestracode.driftguard)
- 🔍 [JoyCheck: How to Fix Controller Stick Drift](https://joycheck.io/blog/fix-controller-stick-drift/)
- 🔍 [GamepadTools: Controller Stick Drift Complete Guide](https://gamepadtools.com/guides/controller-stick-drift/)
- 🔍 [GamepadTest.app: How to Fix Stick Drift](https://gamepadtest.app/guides/stick-drift-fix)
- 🏢 [Turtle Beach: Fix Controller Drift](https://www.turtlebeach.com/blog/how-to-fix-controller-drift-anti-drift-solutions)

### AI-guided appliance/device repair apps (the competitive check — this space is crowded)
- 🏢 [iFixit: FixBot — AI Repair Helper](https://www.ifixit.com/go/fixbot) — **strongest incumbent, watch this one closely**
- 🏢 [AI Repair: DIY Home Fix Guide — Google Play](https://play.google.com/store/apps/details?id=com.ai.repair.appliances&hl=en_US)
- 🏢 [Fix It - Repair Anything w/ AI — App Store](https://apps.apple.com/us/app/fix-it-repair-anything-w-ai/id6745745255)
- 🏢 [aihomefix.com: Appliance Recognition AI](https://www.aihomefix.com/)
- 🏢 [aiventic: AI Repair Tools for Appliance Technicians](https://www.aiventic.ai/blog/ai-repair-tools-for-appliance-technicians)
- 🔍 [Fieldproxy: 7 Ways AI is Transforming Appliance Repair](https://www.fieldproxy.ai/blog/7-ways-ai-is-transforming-appliance-repair-service-delivery-d1-37)
