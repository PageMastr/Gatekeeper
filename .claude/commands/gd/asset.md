---
description: Build one Blender asset generator end to end — spec, script, contracts, GLB, import, critique
argument-hint: <asset name or description, e.g. "2m modular wall with a door">
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent
---

# /gd:asset — one asset, generated and gated

@gsd-gd/references/blender-patterns.md
@gsd-gd/references/laws.md

Asset: **$ARGUMENTS**

Law 7: the script is the source of truth, the `.glb` is a build artifact. You
will not open Blender's UI, and you will not hand-edit a mesh. When the roof is
wrong you fix one line and run it again.

## 1. Spec before script

Write `.planning/phases/NN/assets/<slug>.md` from
`gsd-gd/templates/ASSET_SPEC.md`. It must pin down:

- **class** — prop / hero_prop / environment_module / character (this sets the
  tri budget from `gsd-gd/config.json`)
- **dimensions in metres**, with tolerance
- **snap grid** compliance if it is a kit module (0.25 m)
- **origin convention** — at base centre for anything that sits on ground
- **palette keys** it may use, from `.planning/COLOR_BIBLE.md`
- **silhouette**, described as primitives — boxes, a roof, a taper. Not
  "detailed". Law 9: simple forms lit well, never "realistic".

A spec you cannot check numerically is not a spec.

## 2. Write the generator

`game/<slug>/generators/<name>.py`. Six parts, in order — see
blender-patterns.md for the canonical shape:

1. `gd.args(...)` with defaults, so the script makes a *family*, not one thing
2. primitives only
3. `gd.assign(ob, "<palette key>")` — never a raw colour
4. contracts: `check_dims`, `check_grid`, `check_tris`, `check_palette`,
   `check_transforms`, `check_origin_at_base`
5. `gd.export_glb(...)`
6. `gd.report(glb=path)`

Bevel every edge (`gd.bevel(ob, 0.01, 2)`). That one line is the cheapest
realism available — every edge gets a highlight, and highlights are what read as
"solid object".

If the asset uses randomness, seed it from `--seed` and report the seed.
Reproducibility is the whole point.

## 3. Build it

```bash
python gsd-gd/bin/gd.py asset generators/<name>.py
```

This runs Blender headless, enforces the contracts, exports the GLB into
`assets/models/`, and reimports in Godot. **Exit code is non-zero if any check
fails**, and `failed_checks` names them. A red gate means the asset does not
exist yet — do not proceed to placing it.

Iterate: change a number, run again. That is the loop. Do not fix geometry by
adding code that patches earlier code; fix the line that was wrong.

## 4. Look at it

Place it in the lab scene and render it under the game's real lighting preset —
an asset judged under neutral light is not judged.

```bash
python gsd-gd/bin/gd.py playtest lab/asset_<name>.json
```

(`/gd:lab` builds that plan and scene if they do not exist.)

Then spawn **`gd-critic`** with the shots, the spec and the Color Bible. Not with
the generator. Law 6.

Expect the first pass to be wrong in a specific way. Common ones, worth checking
before the critic does: proportions off (doors are 2.0–2.1 m); too symmetric
(rotate one panel 2°, shorten one plank); detail in the wrong place (budget it
to eye and hand height); material count too high (each extra material is an
extra draw call *per instance*).

## 5. Anything downloaded

If any part of this came from outside — a mesh, a texture, a mocap clip — log it
the moment it lands:

```bash
python gsd-gd/bin/gd.py credits "<asset>" "<source>" "<license>" --url <url> --attribution "<text>"
```

Then decimate it in stages to match the game's poly density (`gd.decimate` at
0.35, 0.2, 0.1 — look at all three, pick one). Judge the silhouette, not the
triangle count.

## Finish

Report: the spec's numbers vs measured, tri count vs budget, the critic's
findings, and the command to regenerate. If the critic sent it back twice, stop
and recommend `/gd:gauntlet` — two failed passes means the target needs
candidates and a judge, not a third guess.
