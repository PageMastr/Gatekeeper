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

## The first rule: more game means more stages, never less game

When the plan does not fit, **the plan is what changes**. Not the game.

This is the single most important instruction in this file, because the default
behaviour of a planner under pressure is to propose cuts — it feels responsible,
it makes the roadmap tidy, and it is almost always wrong. The person asking for
the game has already decided what the game is. A stage list that cannot hold it
is a stage list that needs another row.

So:

- A feature that will not fit in the current stage gets **its own stage**.
- A stage whose job list will not fit in one plan gets **split into two stages**.
- Something that genuinely has to wait goes in **Later stages, with the stage
  number it will get** — scheduled, not deleted.
- "Should we cut X?" is not a question this system asks. "Which stage does X
  land in?" is.

The only judgement the roadmap makes is **order**. Order is decided by risk and
by dependency, never by appetite.

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

---

## The greybox block

**The greybox is the whole game, end to end, in grey.** Not a sample room, not
one mechanic. Every space at real distances, every system running and
observable, the loop closing, and a reachable failure state. Law 1 says art
waits for this; the point of the block is that there is genuinely nothing left
to discover about whether the game works before art starts.

That is more work than a single phase can usually hold. A phase is bounded by
what one plan can carry — roughly a dozen jobs across four or five waves — and
by what one gate can usefully fail. One enormous greybox phase has a gate so
large that a failure in its last job invalidates everything before it, and
nothing is learned until the very end.

So the greybox is a **block of consecutive stages numbered from 01**, sized to
the game. `ROADMAP.md` marks them `greybox` in the `block` column and names the
last one in `- greybox block:`. `gd roadmap` enforces the shape:

- the block starts at stage 01 and is contiguous — nothing may be interleaved,
  because a non-greybox stage inside the block means art gets built on an
  unproven loop
- **every system** in the Systems inventory is greyboxed inside the block
- **every space** in the Levels table is blocked out inside the block
- the **last** stage's pass conditions mention losing — the reachable failure
  state is forgotten in almost every first pass, so it is checked, not trusted

`greybox_passed` flips only when that last stage clears, human playtest
included.

### Sizing the block

One stage per coherent arc of work. Count the systems and the spaces:

| the game | typical block |
|---|---|
| one system, one space (an arena, a puzzle box, a single-screen 2D game) | 01 alone |
| two or three systems, a few connected spaces | 01–02 |
| several systems, a map with distinct areas | 01–04 |
| many interacting systems, a large or streamed world | 01–06, split by area and by system |

**Split by space or by system — never by layer.** "All the scripts, then all the
scenes" produces two stages neither of which is playable, which breaks the
stacking rule and destroys the reason for splitting in the first place.

A workable default shape for a mid-sized game:

| stage | what it proves |
|---|---|
| 01 traversal and space | the map's real shape at real distances, walkable end to end |
| 02 the core verb | the central mechanic works, succeeds and fails, on primitives |
| 03 supporting systems | every other system runs and is observable, state survives a turn |
| 04 loop closure and failure | beat 4 changes beat 1; the player can lose; partial input does not lie |

Large games insert per-area blockout stages after 01, and per-system stages
after 02. Small games collapse the whole thing into 01.

### What a greybox stage contains

Enough jobs to actually build that slice of the game, not a token pass:

- **blockout jobs** — one per space, each ending in a walk-through playtest that
  names the nodes traversed (a `moved` check with `via`, not a distance)
- **system jobs** — one per system, each with a `lab/` scene that makes the
  system observable on its own before it is wired into the level
- **wiring jobs** — the ones that connect systems to the level, serialised
  because they touch shared scenes
- **a tuning job** — distances, rates and timings adjusted against measured
  numbers from the playtests, not guessed
- **the gates job** — `gd-playtester`, wave 1, authoring every plan the stage's
  gates name, before any of it is built

Tuning belongs **inside** the block, at the end of each stage. A greybox whose
numbers were never tuned proves the loop runs, not that it is worth running —
and the whole point of the block is to answer the second question while
changing your mind is still cheap.

### Placeholders are planned here

"These are just placeholders. The real Blender models come later." Every
primitive placed in the block goes in the placeholder ledger with the stage that
replaces it, at the moment it is placed. A placeholder recorded later is a
placeholder that ships.

---

## The stage ladder after the greybox

The order below is the order the reference builds actually followed, three
times, with different games. Treat it as the default and depart from it
deliberately.

| # | stage | why it sits here |
|---|---|---|
| **Contracts** | reference, Color Bible, Core Loop, Minute One, roadmap | `/gd:plan` kickoff. Everything downstream reads these |
| **Greybox block** | the whole game in grey, in as many stages as it takes | "Okay, step one, the grey boxes." The loop gets proven before anything is made to look good |
| **Core verb polish** | the mechanic the loop rests on, tuned in `lab/` until it feels right | If the central verb feels bad, nothing later rescues it |
| **World system** | the systemic thing that makes the place a place — terrain height, snow depth, station modularity | Systems before decoration. It constrains every asset that follows |
| **Modular kit** | the reusable blocks — walls, floors, corners — on a measured snap grid | "We want to split this wall into modules and then we can build whole station based on those modules" |
| **Props pass** | pipes, fans, grates, cable runs | A separate stage because it has a different failure mode from the kit: the kit must tile, the props must populate |
| **Hero asset** | *one* thing built to the quality bar with no budget excuses | "First step, a treehouse. No polygon limit. Two hours. Make it stunning." It sets the bar everything else is measured against, and tells you early whether the bar is reachable |
| **Character** | model (several proposals, pick one) → rig/animate → `lab/` until it moves | "The next big milestone is the astronaut" |
| **Replace placeholders** | swap primitives for real assets, one at a time | Its own stage, because forgetting one is the default outcome. The ledger is what prevents it |
| **Textures & materials** | pick *one* source, set world-scale deliberately | Mixing photo-scanned PBR and code-generated noise in one scene is what looks wrong, not either alone |
| **Lighting** | presets + the F9 panel, hero-light discipline | After the world exists — lighting a world that is still changing shape is wasted tuning |
| **Performance** | measure worst case, triage shadows first | After lighting, because lighting is usually what broke it. 30 fps → 50 fps by disabling shadow casters |
| **Antagonist / pressure** | the thing that makes you lose, tuned | Needs the world and the character to exist to be tuned against |
| **Feedback & juice** | accumulating world state (tracks, scorch), VFX, hit reactions | "Every step paints into one picture." Cheap once the systems exist |
| **Audio** | SFX and mix; log every licence on arrival | |
| **Sequence / story** | the scripted beats that make it a game rather than a sandbox | "Something has to go wrong." Last, because it references everything |
| **Ship** | export, credits, budget snapshot, learnings | `/gd:ship` |

Not every game needs all of these, and a game may need several of one. A 2D game
folds kit/props/hero into one. A game with three enemy types has three pressure
stages. **Adding is as normal as skipping** — the coverage matrix is what makes
either one visible.

## Ordering rules, when you depart from the ladder

1. **Risk first.** Whatever is most likely to kill the project goes early, while
   changing your mind is still cheap. If the gait is the hard part, the greybox
   block contains a gait stage.
2. **Systems before decoration.** A system constrains the assets that sit on it;
   assets built first get rebuilt.
3. **One-way doors early.** Animation approach, coordinate scale, streaming
   model, renderer. Each gets a checkpoint in the stage that takes it. Iteration
   gets more expensive as the project grows, so a door taken late is taken badly.
4. **One hero asset early**, not last. It is your quality bar and your reality
   check.
5. **Vertical before horizontal.** One crate generated, imported, placed, lit and
   playtested de-risks more than a finished kit with no scene. Prefer a tracer
   through every layer.
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

## The four mechanisms that guarantee coverage

A roadmap that reads well can still be missing half the game. Four tables in
`ROADMAP.md` exist to make that impossible to miss, and `gd roadmap` fails when
any has a hole:

**The coverage matrix.** Every beat of the Core Loop, and every required element
of the game, names the stage that delivers it.

**The systems inventory.** Every system names the greybox stage that proves it
and the stage that finishes it. A system that appears in neither is a system
nobody has scheduled.

**The levels table.** Every space, with its size in metres, names the greybox
stage that blocks it out. Distances decided during a build are distances nobody
chose.

**The placeholder ledger.** Every primitive standing in for a real thing names
the stage that replaces it. The single most forgettable category of work in a
game build: placeholders are invisible once you stop noticing them, and then
they ship.

## Revising the roadmap

`/gd:ship` revises it at the end of every stage, because the roadmap written at
kickoff is a forecast and later stages will be wrong in detail.

What you learned is allowed to change the order, split a stage, or add one. What
it is not allowed to do is quietly drop a coverage row — if an element is no
longer being built *now*, it moves to **Later stages** with the stage it will
land in, so the decision stays visible instead of getting lost.
