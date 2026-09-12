---
description: Beat 3 — prove one whole turn of the Core Loop on grey boxes, before any art
argument-hint: [optional: area or system to greybox]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent
---

# /gd:greybox — the loop, in grey, or nothing

@gsd-gd/references/laws.md
@gsd-gd/references/playtest-recipes.md

Scope: **$ARGUMENTS**

This beat exists to enforce Law 1. Art on top of a missing loop is wasted art,
and it is wasted *late*, after it feels too expensive to throw away. The gate
here is the most valuable gate in the system.

## The rule

`/gd:build` will refuse asset work while `greybox_passed: no`. Do not set that
flag by hand. It is set by a passing playtest, and only by that.

## Sequence

### 1. Blueprint first, then boxes

Before placing anything, write the layout down: rooms, distances in metres,
sightlines, where the player enters and where the pressure comes from. Show it
to the user and get a yes. A blueprint is cheap to argue with; a built greybox
is not.

Distances matter more than shapes at this stage. A corridor someone hurries down
is 1.6–2.0 m wide. A room that should feel exposed is not 4×4.

### 2. Build it out of primitives

`CSGBox3D` or `BoxMesh` + `StaticBody3D`. Grey. No textures, no palette work —
`base_mid` for everything is correct here. The `GDLightingRig` on a neutral
preset (`maintenance`) so you can actually see the space.

Do not model anything. Do not run a generator. This beat produces no assets.

### 3. Make the loop completable

Every beat of `.planning/CORE_LOOP.md`, reachable and completable, plus:

- **The state change.** Beat 4 must change beat 1. Without it you have a
  treadmill and the greybox will pass while the game stays unplayable.
- **A reachable failure state.** You must be able to lose. This is forgotten
  in almost every first pass.

Placeholder everything else: a cube is an enemy, a cylinder is a fire, a flat
plane is a door. Placeholders are honest; a half-finished asset is not.

### 4. Write the gates

Two plans in `game/<slug>/lab/`:

- `loop_complete.json` — drives one entire turn of the loop, asserts the state
  change happened.
- `can_lose.json` — drives the player into the failure state deliberately and
  asserts it occurred.

```bash
python gsd-gd/bin/gd.py playtest loop_complete
python gsd-gd/bin/gd.py playtest can_lose
python gsd-gd/bin/gd.py playtest minute_one
```

All three must pass. Read the `detail` field of every check — a check that
passes for the wrong reason is worse than one that fails.

### 5. Play it yourself, and have the user play it

The automated gates prove it works. They cannot tell you whether it is worth
doing twice. Hand the user the build and ask one question: *would you press
start again?*

If the answer is no, the fix is in `.planning/CORE_LOOP.md`, not in the
greybox. Go back to `/gd:frame`. This is the cheapest moment this project will
ever have to change its mind — spend it.

## Finish

Only when all three plans pass **and** the user has played it:

```bash
python gsd-gd/bin/gd.py state greybox_passed yes
python gsd-gd/bin/gd.py state beat build
```

Report: the loop as built, the three verdicts, what felt wrong when you played
it, and what you would cut. Recommend `/gd:build`.
