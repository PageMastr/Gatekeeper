---
description: Beat 3 — prove the whole game on grey boxes, across as many stages as it takes, before any art
argument-hint: [optional: a stage id, area or system to greybox]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent
---

# /gd:greybox — the loop, in grey, or nothing

@gatekeeper/references/laws.md
@gatekeeper/references/decomposition.md
@gatekeeper/references/playtest-recipes.md

Scope: **$ARGUMENTS**

This beat enforces Law 1. Art on top of a missing loop is wasted art, and it is
wasted *late*, after it feels too expensive to throw away. The gates here are the
most valuable gates in the system.

## What the greybox actually is

**The whole game, end to end, in grey.** Not a sample room and not one mechanic:
every space walkable at real distances, every system running and observable, the
loop closing, and a reachable failure state. When the block is finished there
should be nothing left to learn about whether the game works.

That is usually more than one phase can hold, so the roadmap splits it into a
**block of consecutive stages numbered from 01**, marked `greybox` in the `block`
column, with `- greybox block:` naming the last one. Each stage in the block ends
playable, so you learn something at the end of each rather than at the end of all
of them.

```bash
python gatekeeper/bin/gd.py roadmap status
```

That prints the block and how many systems and spaces it has to prove. If the
block looks too small for what the systems inventory and levels table contain,
`gd roadmap` says so — the fix is another stage, not a thinner one.

## First: is this already a planned phase?

```bash
python gatekeeper/bin/gd.py run status 2>/dev/null
```

**If that returns a phase with jobs, stop and invoke the `gd:run` skill instead.**
Once a greybox stage has been decomposed into jobs with an armed `RUN.json`, this
command and `/gd:run` claim the same territory, and only one of them records
attempts, escalates failures and survives an interruption. `/gd:run` is that one.

Use the hand-driven path below only when there is no phase plan.

## The rule

`/gd:build` and `/gd:run` refuse asset work while `greybox_passed: no`. Do not
set that flag by hand. It is set by a passing playtest **of the last stage in the
block**, plus a human having played it — and only by that.

Stages in the middle of the block pass their own gates and advance the roadmap;
they do not flip `greybox_passed`.

## Sequence, per stage in the block

### 1. Blueprint first, then boxes

Before placing anything, write the layout down: rooms, distances in metres,
sightlines, where the player enters and where the pressure comes from. It should
already be in the roadmap's levels table — check it against that rather than
inventing a second version. Show it to the user and get a yes.

A blueprint is cheap to argue with; a built greybox is not.

Distances matter more than shapes at this stage. A corridor someone hurries down
is 1.6–2.0 m wide. A room that should feel exposed is not 4×4.

### 2. Build it out of primitives

`CSGBox3D` or `BoxMesh` + `StaticBody3D`. Grey. No textures, no palette work —
`base_mid` for everything is correct here. The `GDLightingRig` on a neutral
preset (`maintenance`) so you can actually see the space.

Do not model anything. Do not run a generator. This block produces no assets.

Record every placeholder in the roadmap's ledger **as you place it**, with the
stage that replaces it. A placeholder recorded later is a placeholder that ships.

### 3. Make each system observable before you wire it in

Law 13: build the observation tool before the fix. Every system this stage owns
gets a `lab/` scene where it runs on its own — one straight line, one system, a
readout you can watch. Wiring a system into the level before you can see it
working means debugging it with six other things also moving.

`GDLAB ` prefixed prints land in the verdict's `log`, so a lab scene can report
its own numbers without turning them into checks.

### 4. Close the loop, in the last stage of the block

Every beat of `.planning/CORE_LOOP.md`, reachable and completable, plus:

- **The state change.** Beat 4 must change beat 1. Without it you have a
  treadmill, and the greybox will pass while the game stays unplayable.
- **A reachable failure state.** You must be able to lose. Forgotten in almost
  every first pass, which is why `gd roadmap` checks the last stage mentions it.

### 5. Tune it — inside the block, not after

A greybox whose numbers were never tuned proves the loop runs, not that it is
worth running. At the end of each stage, adjust against **measured** numbers from
the playtests rather than guesses:

- traversal times from the `moved` checks (is the trip a real cost?)
- rates and drains from `GDLAB` log lines (does the pressure bite before the
  player can answer it?)
- distances from the blockout verdicts (does the space feel like the roadmap
  said it would?)

Say what you changed and what number drove it. "Raised drain 0.8 → 1.1/s: at 0.8
the player never had to leave the fire" is a tuning note; "felt better" is not.

### 6. Write the gates

Authored by `gd-playtester`, in wave 1, before the stage is built. Per stage, at
minimum a blockout walk; in the last stage of the block, all of:

- `loop_complete.json` — drives one entire turn of the loop, asserts the state
  change happened.
- `can_lose.json` — drives the player into the failure state deliberately and
  asserts it occurred.
- `partial_input.json` — for every interaction needing more than one press,
  presses **only the first part** and asserts the game does not lie about it: no
  cost charged, no half-applied state, no UI claiming it happened.

That third plan exists because a phase once passed a green gate on **220 checks
across 18 plans** — with two audit jobs hunting checks that pass for the wrong
reason — and then failed a five-minute human playtest in three ways. Every plan
pressed the whole interaction; none modelled the player who pressed half of it.

```bash
python gatekeeper/bin/gd.py playtest blockout_walk
python gatekeeper/bin/gd.py playtest loop_complete
python gatekeeper/bin/gd.py playtest can_lose
python gatekeeper/bin/gd.py playtest partial_input
python gatekeeper/bin/gd.py playtest minute_one
```

Read the `detail` field of **every** check. A check that passes for the wrong
reason is worse than one that fails. A `moved` check with no `via` is satisfied
by any open floor — that is how `walked_the_spine` passed at 41 m in a scene with
no spine.

### 7. Advance the roadmap

At the end of each stage in the block:

```bash
python gatekeeper/bin/gd.py roadmap done <stage id>
```

Then plan the next one with `/gd:plan`. Stages in the middle of the block are
ordinary phases: they ship, they teach you something, and the next one starts
from what you learned.

## Finish — only at the last stage of the block

### Play it yourself, and have the user play it

The automated gates prove it works. They cannot tell you whether it is worth
doing twice. Hand the user the build and ask one question: *would you press start
again?*

If the answer is no, the fix is in `.planning/CORE_LOOP.md`, not in the greybox.
Go back to `/gd:frame`. This is the cheapest moment this project will ever have
to change its mind — spend it.

Only when the last stage's plans all pass **and** the user has played it:

```bash
python gatekeeper/bin/gd.py state greybox_passed yes
python gatekeeper/bin/gd.py state beat build
```

Report: the loop as built, every verdict, the tuning notes with the numbers that
drove them, what felt wrong when you played it, and what you would change. Then
`/gd:plan` for the first stage after the block.
