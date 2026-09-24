# Tool Library — CircuitQuest

Reference doc for `library/tools/*.json` (see `PLAN.md` for the loader design and directory layout; see the research log (in git history) for the full reasoning trail behind these decisions).

Pulled out of `README.md` into its own file since this is actual data spec, not narrative — it'll keep growing as new tiers/tools get added.

---

## Storage principle: one dataset, tier is a field, not a folder split

"Tier" is a content-rollout concept (which tools a lesson actually uses *now* vs. *later*), not a storage concept. All tools — regardless of tier — live in the same flat dataset: one JSON folder today, a single SQL table later if it migrates. Each card carries a `tier` field; nothing about the schema or the loader changes based on tier. `library.py` already loads every card (parts and tools alike) into one id+alias index — this is the same principle applied one level further.

## Card schema

```json
{
  "id": "wire-stripper",
  "type": "tool",
  "tier": 1,
  "display_name": "Wire Stripper",
  "aliases": ["stripper", "wire strippers"],
  "description": "Removes insulation from a wire's end without cutting the copper inside.",
  "how_to_use": "Open the jaws, seat the wire in the notch matching its gauge, squeeze, and pull to strip the insulation.",
  "tutorial_clip": "wire-stripper-howto.mp4",
  "image": "wire-stripper.png"
}
```

Same shape for parts (`library/parts/*.json`, `"type": "part"`) — `description` and `how_to_use` apply to every item, tool or part; `tutorial_clip` is the only field reserved for tools, since only tools need a technique demonstrated. See [`PARTS.md`](./PARTS.md), which also adds `wokwi_type`/`wokwi_value` fields — the bridge between a part and its identity in a Wokwi-authored answer key. None of the Tier 1 tools get this field: Wokwi doesn't simulate hand tools (wire strippers, pliers, a multimeter aren't circuit components), so it's simply absent here, not omitted by choice.

## Tier 1 — building now (Arduino Uno + breadboard, solderless)

The only tools an LED-blink-style lesson set actually touches. These get real `library/tools/<id>.json` cards written now.

| Tool | Why it's needed here |
|---|---|
| Wire stripper | Prepping custom-length wire, if a lesson doesn't use pre-made jumpers |
| Needle-nose pliers | Bending leads, reaching into tight breadboard rows — the precision type, not general/combination pliers |
| Flush cutters | Trimming LED/resistor leads to length |
| Tweezers | Precisely seating thin component legs into breadboard holes |
| Digital multimeter | Continuity checks, verifying voltage at a pin, confirming a resistor's actual value — a real transferable electronics skill, not just circuit-building |
| Small screwdriver set | Cheap to include now rather than gated behind a future lesson |

## Tier 2 — later, once lessons move to custom parts / permanent assembly

A real planned second track (confirmed: soldering becomes necessary once parts stop being breadboard-compatible), not a "maybe." Cards get authored when this track actually starts, same schema, `"tier": 2`.

**`soldering-iron` is now authored**, ahead of the rest of this tier — user request: a direct-to-leg connection (skipping the breadboard entirely, `engine._multi_leg_bypass`/the single-pin bypass) needs a real physical way to attach a wire to a bare component leg, and a plain `jumper-wire`'s pin end has nothing to grip one with. The solderless answer is `alligator-clip-wire` (see PARTS.md); soldering is the advanced, permanent alternative to it, so its own tool card exists even though the rest of tier 2 (helping hands, desoldering pump, solder wick, magnifier) hasn't started yet — none of those are needed to make one first joint.

| Tool | Why it waits |
|---|---|
| Helping hands | Soldering aid, nothing to hold in place without solder |
| Desoldering pump | Solder-removal tool |
| Solder wick | Solder-removal tool |
| Magnifier | Reading a solder joint benefits from magnification far more than a breadboard build does |

## Cut entirely — wrong category of work, regardless of tier

Flux, PCB vise, crimpers, heat gun, heat-shrink tubing, hot glue gun, fume extractor, ESD mat/wrist strap, drill/Dremel, calipers, isopropyl alcohol + brush, label maker. None of these fit either the breadboard track or a hobbyist soldering track for this platform's scope.
