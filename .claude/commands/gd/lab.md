---
description: Build an isolation test scene for one system — gait, camera, weapon feel, a single asset
argument-hint: <system or asset to isolate, e.g. "spider gait" or "wall kit tiling">
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Skill
---

# /gd:lab — isolate before you debug

@gsd-gd/references/godot-patterns.md

Subject: **$ARGUMENTS**

Law 13: when something moves wrong, the first thing to build is not a fix — it
is an observation tool. In the real level six other systems are also moving, and
you will blame the wrong one.

## Before writing any GDScript

Use the `godot-api` skill. Look up every type you are about to touch. Then
`python gsd-gd/bin/gd.py check <file.gd>` before you claim the lab works.

## What a lab scene is

One system. One straight line. Nothing else.

`game/<slug>/lab/<subject>.tscn` plus `game/<slug>/lab/<subject>.json`:

- **A floor and a marked distance.** Metres along the line, so "it drifts" and
  "it drifts 0.4 m over 10 m" are different statements.
- **The surface changes that break things.** For a walker:
  floor → ramp → wall → ceiling. Surface transitions are where the body commits
  before the legs have found purchase, and that is never visible at full speed
  in a real level.
- **`GDLightingRig` on `maintenance`.** Bright and neutral — you are looking at
  motion, not mood.
- **No enemies, no pickups, no HUD.** If it is not the subject, it is noise.

## Build the observation tool first

Before changing any behaviour, add the thing that lets you see what it is
actually doing:

- **Gait** — a key that advances one leg at a time, and one that freezes the body
  while the legs keep solving. Draw each leg's IK target and ground raycast.
- **Camera** — draw the ray the camera fires at the player, and what it hits.
- **Locomotion** — a corner label printing velocity, `is_on_floor()`, and the
  surface scalar every frame.
- **An asset** — a turntable, plus a second copy at 30 m to check the silhouette.

This is the step that gets skipped, and skipping it is why debugging sessions
run long. A fix applied without seeing the failure is a guess.

## Then iterate

```bash
python gsd-gd/bin/gd.py playtest lab/<subject>
```

Keep every attempt. The progression is information — the eighth walk cycle only
makes sense next to the first. Log each attempt: what changed, what the numbers
did, what the screenshots showed.

## Graduation

A subject leaves the lab when all three hold:

- its lab plan passes
- it passes in the **real** scene, with everything else running
- its numbers are inside `BUDGET.md`

Do not delete the lab scene afterwards. It is the regression test, and it is the
only place the next change to this system can be safely tried.

## Finish

Report: what the observation tool showed, the attempt log, the passing numbers,
and the lab plan name so it can be re-run later.
