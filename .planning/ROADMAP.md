# ROADMAP — Audit2

> **The whole game, broken into stages that stack.** Written by `/gd:new` at
> kickoff, revised by `/gd:ship` at the end of every stage, and validated by
> `gd roadmap` — which fails on a hole, so this cannot quietly drift into
> fiction.
>
> The rule it obeys (see `gsd-gd/references/decomposition.md`):
> **one stage = one phase = something playable. One slice = one session = one
> gate.** Nothing else is a unit of work.
>
> A stage that ends "the kit is finished, nothing uses it yet" has not stacked,
> it has accumulated. Rework it so it ends with something you can press start on.

- created: 2026-09-12T20:05:56Z
- end state: <one sentence: what the finished thing is, and what "done" means>
- current stage: 01

## Stages

`depends on` must reference only **earlier** stages. `playable at the end` must
describe something a person can do, not a component that exists. `gate` is the
phase gate — the `- gate:` lines that stage's `PLAN.md` will carry.

| # | stage | playable at the end | depends on | gate | status |
|---|---|---|---|---|---|
| 01 | greybox | one whole turn of the Core Loop, in grey, including losing | - | `loop_complete` + `can_lose` + `minute_one` | planned |
| 02 | <core verb> | <the central mechanic feels right, tuned in lab/> | 01 | <plan> | planned |
| 03 | <world system> | <the systemic thing that makes the place a place> | 01 | <plan> | planned |
| 04 | <placeholder pass> | <every noun the loop needs is present, as primitives> | 03 | <plan> | planned |
| 05 | <modular kit> | <one room built from kit pieces, walked through> | 04 | <plan> | planned |
| 06 | <props pass> | <that room reads as a place, not a box> | 05 | <plan> | planned |
| 07 | <hero asset> | <one thing at the quality bar, in the scene, lit> | 05 | <plan> | planned |
| 08 | <character> | <the real character moves through the world> | 04 | <plan> | planned |
| 09 | <replace placeholders> | <no primitives left in the player's path> | 05,08 | <plan> | planned |
| 10 | <textures> | <one material language across the whole scene> | 09 | <plan> | planned |
| 11 | <lighting> | <the target mood, from named presets> | 10 | <plan> | planned |
| 12 | <performance> | <inside budget at the worst case> | 11 | `perf_worst_case` | planned |
| 13 | <pressure> | <you can lose to something, and it is tuned> | 08 | <plan> | planned |
| 14 | <feedback & juice> | <the world reacts and feels alive> | 13 | <plan> | planned |
| 15 | <audio> | <it sounds like a place> | 14 | <plan> | planned |
| 16 | <sequence> | <the game has a beginning and an end> | 13 | <plan> | planned |

`status`: `planned` → `active` → `done`. Set by `gd roadmap done <id>` at ship
time, not by hand.

**Delete the stages this game does not need.** A 2D game collapses 05–07; a game
with no enemies drops 13. Cutting a stage is fine — forgetting one is what the
coverage matrix below is for.

## Coverage matrix

**Every beat of the Core Loop and every required element of the game names the
stage that delivers it.** An element with no stage is a hole in the plan, and it
is far cheaper to find here than in month two. `gd roadmap` fails on an empty or
unknown stage reference, and on a Core Loop beat with no row.

| element | delivered by stage |
|---|---|
| beat 1: <from CORE_LOOP.md> | 01 |
| beat 2: <…> | 01 |
| beat 3: <…> | 01 |
| beat 4: <the state change that makes turn two different> | 01 |
| the failure state (you can lose) | 01 |
| the player character | 08 |
| the place the game happens in | 05 |
| <every other noun the game needs> | <stage> |

## Placeholder ledger

The most forgettable work in a game build. A placeholder is invisible once you
stop noticing it, and then it ships. Every primitive standing in for a real
thing names the stage that replaces it; `gd roadmap` fails if that stage does
not exist.

| placeholder | stands in for | replaced by stage |
|---|---|---|
| grey capsule | the player character | 08 |
| grey boxes | <the building / the rooms> | 05 |
| <…> | <…> | <…> |

## One-way doors

Each becomes a checkpoint in that stage's `PLAN.md`, where `/gd:run` halts and
asks. Taken late, these are expensive; taken inside a parallel wave, they are
worse — you find out four jobs later.

| door | taken in stage | decided |
|---|---|---|
| coordinate scale (1 unit = 1 m) | 01 | yes — asserted in every asset spec |
| perspective / camera | 01 | <…> |
| animation approach: rigged clips vs procedural | 08 | <not yet> |
| single scene vs streamed world | 03 | <not yet> |

## Risk order

Why the stages are in this order — specifically, what each early stage retires.
A stage that de-risks nothing belongs later.

| stage | the risk it retires |
|---|---|
| 01 | that there is no game here — the most expensive thing to discover late |
| <02> | <…> |
| <07> | that the quality bar is not reachable with this pipeline |

## Not in this milestone

Named so it can be defended later, when it looks cheap mid-build. Anything cut
from the stage list moves here **with a reason**, so the decision stays visible
instead of getting lost.

- <…>
- <…>
- <…>

## Revisions

The kickoff roadmap is a forecast; stages 3+ will be wrong in detail. Revising
is expected — silently dropping a coverage row is not.

| date | change | why |
|---|---|---|
| 2026-09-12T20:05:56Z | created at kickoff | |
