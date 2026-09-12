# Decomposition — how a whole game becomes stackable pieces

The rule, stated in the reference builds almost verbatim:

> "These are the sections. Every section has smaller tasks inside. That's the
> rule. **One task should be one fresh session. And it must be easy to test.**"

Two levels, and only two:

| level | artefact | unit | ends with |
|---|---|---|---|
| **Stage** | a row in `.planning/ROADMAP.md` | a phase | something **playable** |
| **Slice** | a job row in that phase's `PLAN.md` | one fresh session | a **gate** that passes |

The roadmap is the whole game. A phase plan is one stage of it. A job is one
session. Nothing else is a unit of work here.

---

## The stacking rule

**Every stage must leave the game playable, and strictly more capable than the
stage before it.**

A stage that ends with "the modular kit is finished, nothing uses it yet" has
not stacked — it has accumulated. You cannot judge it, cannot playtest it, and
cannot tell whether it was worth building. Rework it so it ends with the kit
*placed and walked through*, even if only in one room.

This is what makes the pieces palatable: each one is small enough to hold in one
plan, and each one leaves you with a game you can press start on.

## The stage ladder

The order below is not invented — it is the order the reference builds actually
followed, three times, with different games. Treat it as the default and depart
from it deliberately, not by accident.

| # | stage | why it sits here |
|---|---|---|
| **Contracts** | reference, Color Bible, Core Loop, Minute One | `/gd:new`. Everything downstream reads these |
| **1. Greybox** | blueprint approved, then primitives; one whole loop turn playable, and losable | "Okay, step one, the grey boxes." The loop gets proven before anything is made to look good |
| **2. Core verb** | the one mechanic the loop rests on, tuned in `lab/` until it feels right | If the central verb feels bad, nothing later rescues it |
| **3. World system** | the systemic thing that makes the place a place — terrain height, snow depth, station modularity | Systems before decoration. It constrains every asset that follows |
| **4. Placeholder pass** | every noun the loop needs, as primitives, in position | "These are just placeholders. The real Blender models come later." Placeholders are *planned*, not accidental |
| **5. Modular kit** | the reusable blocks — walls, floors, corners — on a measured snap grid | "We want to split this wall into modules and then we can build whole station based on those modules" |
| **6. Props pass** | pipes, fans, grates, cable runs | A separate stage because it has a different failure mode from the kit: the kit must tile, the props must populate |
| **7. Hero asset** | *one* thing built to the quality bar with no budget excuses | "First step, a treehouse. No polygon limit. Two hours. Make it stunning." It sets the bar everything else is measured against, and it tells you early whether the bar is reachable |
| **8. Character** | model (several proposals, pick one) → rig/animate → `lab/` until it moves | "The next big milestone is the astronaut" |
| **9. Replace placeholders** | swap primitives for real assets, one at a time | Its own stage, because forgetting one is the default outcome. The ledger in the roadmap is what prevents it |
| **10. Textures & materials** | pick *one* source, set world-scale deliberately | Mixing photo-scanned PBR and code-generated noise in one scene is what looks wrong, not either alone |
| **11. Lighting** | presets + the F9 panel, hero-light discipline | After the world exists — lighting a world that is still changing shape is wasted tuning |
| **12. Performance** | measure worst case, triage shadows first | After lighting, because lighting is usually what broke it. 30 fps → 50 fps by disabling shadow casters |
| **13. Antagonist / pressure** | the thing that makes you lose | Needs the world and the character to exist to be tuned against |
| **14. Feedback & juice** | accumulating world state (tracks, scorch), VFX, hit reactions | "Every step paints into one picture." The layer that makes the world feel alive, cheap once the systems exist |
| **15. Audio** | SFX and mix; log every licence on arrival | |
| **16. Sequence / story** | the scripted beats that make it a game rather than a sandbox | "Something has to go wrong." Last, because it references everything |
| **Ship** | export, credits, budget snapshot, learnings | `/gd:ship` |

Not every game needs all sixteen. A 2D game collapses 5–7. A game with no
enemies drops 13. **Cutting a stage is fine; forgetting one is not** — which is
what the coverage matrix is for.

## Ordering rules, when you depart from the ladder

1. **Risk first.** Whatever is most likely to kill the project goes early, while
   changing your mind is still cheap. If the gait is the hard part, stage 2 is
   the gait.
2. **Systems before decoration.** A system constrains the assets that sit on it;
   assets built first get rebuilt.
3. **One-way doors early.** Animation approach, coordinate scale, streaming
   model, renderer. Each gets a checkpoint in the stage that takes it. Iteration
   gets more expensive as the project grows, so a door taken late is a door
   taken badly.
4. **One hero asset early**, not last. It is your quality bar and your reality
   check.
5. **Vertical before horizontal.** One crate generated, imported, placed, lit
   and playtested de-risks more than a finished kit with no scene. Prefer a
   tracer through every layer.
6. **Lighting and perf after the world has settled**, before more content is
   added on top.

## What makes a good slice (a job)

- **One session.** If it needs two to hold in context, it is two jobs.
- **Its gate is written before it is built.** A job without a gate is a wish.
- **It names the files it may touch**, and the ones it must not.
- **It is disjoint from its wave-mates.** `.tscn` files are the usual collision.
- **It is boring to describe.** "Corridor blockout, 18 m, three doorways,
  walkable end to end" is a job. "Improve the level" is a stage at best, and
  probably a milestone.

## The two mechanisms that guarantee coverage

A roadmap that reads well can still be missing half the game. Two tables in
`ROADMAP.md` exist to make that impossible to miss, and `gd roadmap` fails when
either has a hole:

**The coverage matrix.** Every beat of the Core Loop, and every required element
of the game, names the stage that delivers it. An element with no stage is a
hole in the plan — better found at kickoff than in month two.

**The placeholder ledger.** Every primitive standing in for a real thing names
the stage that replaces it. This is the single most forgettable category of work
in a game build: placeholders are invisible once you stop noticing them, and
then they ship.

## Revising the roadmap

`/gd:ship` revises it at the end of every stage, because the roadmap written at
kickoff is a forecast and stages 3+ will be wrong in detail.

What you learned is allowed to change the order, split a stage, or delete one.
What it is not allowed to do is quietly drop a coverage row — if an element is
no longer being built, it moves to **Not in this milestone** with a reason, so
the decision is visible instead of lost.
