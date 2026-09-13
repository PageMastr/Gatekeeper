# ROADMAP — {{NAME}}

> **The whole game, broken into stages that stack.** Written at kickoff by
> `/gd:plan`, revised by `/gd:ship` at the end of every stage, and validated by
> `gd roadmap` — which fails on a hole, so this cannot quietly drift into
> fiction.
>
> The rule it obeys (see `gsd-gd/references/decomposition.md`):
> **one stage = one phase = something playable. One slice = one session = one
> gate.** Nothing else is a unit of work.
>
> A stage that ends "the kit is finished, nothing uses it yet" has not stacked,
> it has accumulated. Rework it so it ends with something you can press start on.
>
> **Nothing gets cut to make this fit.** Everything the game needs gets a stage.
> If there is more game than one stage can hold, that is more stages — not less
> game. The only decision this document makes is *order*.

- created: {{DATE}}
- end state: <one sentence: what the finished thing is, and what "done" means>
- current stage: 01
- greybox block: 04
  <the LAST stage of the greybox block. Stages 01..this are greyboxed in grey;
   `greybox_passed` flips only when this one clears. See "The greybox block".>

---

## Stages

`depends on` must reference only **earlier** stages. `playable at the end` must
describe something a person can do, not a component that exists. `gate` is the
phase gate — the `- gate:` lines that stage's `PLAN.md` will carry. `block`
groups stages that belong to one arc of work; `greybox` is the only block with
special meaning to the tooling.

| # | block | stage | playable at the end | depends on | gate | status |
|---|---|---|---|---|---|---|
| 01 | greybox | <traversal & space> | <the player moves through the real shape of the map, at the real distances> | - | `blockout_walk` | planned |
| 02 | greybox | <the core verb> | <the central mechanic works end to end on primitives> | 01 | `core_verb` | planned |
| 03 | greybox | <the supporting systems> | <every system the loop needs runs, in grey> | 02 | `systems_live` | planned |
| 04 | greybox | <loop closure & failure> | <one whole turn of the loop, including losing> | 03 | `loop_complete` + `can_lose` + `partial_input` | planned |
| 05 | feel | <core verb polish> | <the central mechanic feels right, tuned in lab/> | 04 | <plan> | planned |
| 06 | systems | <world system> | <the systemic thing that makes the place a place> | 04 | <plan> | planned |
| 07 | art | <modular kit> | <one room built from kit pieces, walked through> | 04 | <plan> | planned |
| 08 | art | <props pass> | <that room reads as a place, not a box> | 07 | <plan> | planned |
| 09 | art | <hero asset> | <one thing at the quality bar, in the scene, lit> | 07 | <plan> | planned |
| 10 | art | <character> | <the real character moves through the world> | 04 | <plan> | planned |
| 11 | art | <replace placeholders> | <no primitives left in the player's path> | 07,10 | <plan> | planned |
| 12 | art | <textures> | <one material language across the whole scene> | 11 | <plan> | planned |
| 13 | look | <lighting> | <the target mood, from named presets> | 12 | <plan> | planned |
| 14 | look | <performance> | <inside budget at the worst case> | 13 | `perf_worst_case` | planned |
| 15 | game | <pressure> | <you can lose to something, and it is tuned> | 10 | <plan> | planned |
| 16 | game | <feedback & juice> | <the world reacts and feels alive> | 15 | <plan> | planned |
| 17 | game | <audio> | <it sounds like a place> | 16 | <plan> | planned |
| 18 | game | <sequence> | <the game has a beginning and an end> | 15 | <plan> | planned |

`status`: `planned` → `active` → `done`. Set by `gd roadmap done <id>` at ship
time, never by hand.

**Add the stages this game needs; reorder freely.** The rows above are a
starting ladder, not a quota. A game with three systems needs more greybox
stages than a game with one; a 2D game folds the kit and props stages together.
Anything that does not belong in this milestone moves to **Later stages** at the
bottom *with its stage number kept* — it is scheduled, not deleted.

---

## The greybox block

**The greybox is not one phase unless the game is small enough for one.** Its
job is the entire game, end to end, in grey: every space at real distances,
every system running, the loop closing, and a reachable failure state. That is
routinely more work than a single phase can hold, and squeezing it into one
produces a phase gate so large that a failure late in it invalidates everything
before it.

So the greybox is a **block of consecutive stages, numbered from 01**, sized to
this game. Every stage in it ends playable, so you learn something at the end of
each one instead of at the end of all of them.

`greybox block:` at the top of this file names the **last** stage of the block.
`gd roadmap` checks that those stages are contiguous from 01, that the block
covers every system and every space, and that the last one proves the loop
closes and the player can lose. `greybox_passed` flips only when that last stage
clears — including a human actually playing it.

How many stages: one per coherent arc of work, sized so each one's job list fits
a single plan.

| systems + spaces in the game | typical block |
|---|---|
| one system, one space (an arena, a puzzle box) | 01 alone |
| two or three systems, a few connected spaces | 01–02 |
| several systems, a map with distinct areas | 01–04, as seeded above |
| many interacting systems, a large or streamed world | 01–06, split by area and by system |

**Sizing rule:** if a greybox stage's job list would exceed what one plan can
hold — roughly a dozen jobs across four or five waves — split it. Split by
*space* (each area blocked out and walked) or by *system* (each system live and
observable), never by layer ("all the scripts", then "all the scenes"), because
a layer split produces stages that are not playable.

---

## Stage targets and pass conditions

**Every stage says what it is for and how it will be judged, before it is
planned.** This is Law 4 raised one level: a phase whose pass conditions you
cannot write is a phase that is not defined yet, and writing them at kickoff is
what stops the gate being reverse-engineered from whatever got built.

Pass conditions are what that stage's `PLAN.md` gate must actually assert. Write
them so a person reading the verdict can tell whether they were met. Numbers
where numbers exist.

| stage # | target — what this stage is for | pass conditions — all must hold |
|---|---|---|
| 01 | <prove the map's shape and distances are right before anything is built on them> | <the player walks from <A> to <B> via <the named spaces> in <N>s; no gap the player can fall through; every area reachable> |
| 02 | <prove the central verb works at all> | <the verb succeeds, the verb fails, and the failure is visible to the player> |
| 03 | <prove the supporting systems run together without fighting> | <each system observable in lab/; state survives one full turn; no runtime errors> |
| 04 | <prove one whole turn of the loop, and that it can be lost> | <beat 4 changes beat 1 measurably; the failure state is reachable; a half-pressed interaction charges nothing and claims nothing> |
| <05> | <…> | <…> |

Every stage in the Stages table needs a row here. `gd roadmap` fails on a
missing one, and on a row still holding template text.

---

## Systems inventory

**Every system the game needs, and the two stages that own it.** A system is
anything with state that changes over time and affects the loop: inventory,
heat, faith, weather, an AI, a day clock, a save. Not a noun — a *behaviour*.

`greyboxed in` must be a stage inside the greybox block: every system runs, in
grey, before any of them is made to look good. `finished in` is the stage that
makes it real — tuned, presented, with feedback the player can read.

| system | what it does to the loop | greyboxed in | finished in |
|---|---|---|---|
| <the core verb> | <what the player does, and what it costs> | 02 | 05 |
| <the pressure> | <what gets worse while the player does nothing> | 03 | 15 |
| <the state carrier> | <what makes turn two different from turn one> | 03 | 06 |
| <…> | <…> | <…> | <…> |

---

## Levels, maps and spaces

**Every space the player can be in, at real distances, and the stage that blocks
it out.** Sizes in metres, decided here rather than discovered during a build —
a corridor someone hurries down is 1.6–2.0 m wide, and a room that should feel
exposed is not 4×4.

`blocked out in` must be a greybox-block stage. Nothing is "designed later": a
space with no blockout stage is a space nobody has thought about.

| space | size (m) | what happens here | connects to | blocked out in |
|---|---|---|---|---|
| <spawn / hub> | <8 × 8> | <where the player starts and returns to> | <corridor> | 01 |
| <…> | <…> | <…> | <…> | 01 |

If the game is procedural or streamed, the rows describe the *kinds* of space
and their generation rules, and the blockout stage proves one generated instance
walkable end to end.

---

## Coverage matrix

**Every beat of the Core Loop and every required element of the game names the
stage that delivers it.** An element with no stage is a hole in the plan, and it
is far cheaper to find here than in month two. `gd roadmap` fails on an empty or
unknown stage reference, and on a Core Loop beat with no row.

| element | delivered by stage |
|---|---|
| beat 1: <from CORE_LOOP.md> | 01 |
| beat 2: <…> | 02 |
| beat 3: <…> | 03 |
| beat 4: <the state change that makes turn two different> | 04 |
| the failure state (you can lose) | 04 |
| the player character | 10 |
| the place the game happens in | 07 |
| <every other noun the game needs> | <stage> |

## Placeholder ledger

The most forgettable work in a game build. A placeholder is invisible once you
stop noticing it, and then it ships. Every primitive standing in for a real
thing names the stage that replaces it; `gd roadmap` fails if that stage does
not exist.

| placeholder | stands in for | replaced by stage |
|---|---|---|
| grey capsule | the player character | 10 |
| grey boxes | <the building / the rooms> | 07 |
| <…> | <…> | <…> |

## One-way doors

Each becomes a checkpoint in that stage's `PLAN.md`, where `/gd:run` halts and
asks. Taken late these are expensive; taken inside a parallel wave they are
worse — you find out four jobs later.

| door | taken in stage | decided |
|---|---|---|
| coordinate scale (1 unit = 1 m) | 01 | yes — asserted in every asset spec |
| perspective / camera | 01 | <…> |
| animation approach: rigged clips vs procedural | 10 | <not yet> |
| single scene vs streamed world | 01 | <not yet> |

## Risk order

Why the stages are in this order — specifically, what each early stage retires.
A stage that de-risks nothing belongs later.

| stage | the risk it retires |
|---|---|
| 01 | that the map's shape does not work at real distances |
| 04 | that there is no game here — the most expensive thing to discover late |
| <09> | that the quality bar is not reachable with this pipeline |

## Later stages

Everything named during the interview that is not in the stage list above, **with
the stage number it will get**. This is a schedule, not a graveyard: the roadmap
grows to fit the game rather than the game shrinking to fit the roadmap. A row
here is a promise that it has been thought about and deliberately sequenced.

| what | why it waits | stage it lands in |
|---|---|---|
| <…> | <depends on <X>, which does not exist yet> | <19> |

## Revisions

The kickoff roadmap is a forecast; later stages will be wrong in detail.
Revising is expected — silently dropping a coverage row is not.

| date | change | why |
|---|---|---|
| {{DATE}} | created at kickoff | |
