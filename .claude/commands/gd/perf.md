---
description: Diagnose and fix a performance problem in cost order — shadows first
argument-hint: [scene or plan showing the problem]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Skill
---

# /gd:perf — triage in cost order

@gatekeeper/references/godot-patterns.md

Subject: **$ARGUMENTS**

Law 11: **shadows are the bill, not lights.** A light is cheap. A light that
casts shadows makes the renderer draw the scene again from that light's point of
view. Six hundred visible objects become fourteen thousand draws with a handful
of shadow-casting lamps in a corridor.

## 1. Measure the worst case, not the spawn point

A budget met at the spawn point is not met. Use (or build) a plan that stands
where the most is visible, facing the most expensive direction.

```bash
python gatekeeper/bin/gd.py playtest lab/perf_worst_case
```

Record `fps_avg`, `fps_1pct_low`, `frame_ms_worst`, `draw_calls_max`,
`primitives_max`, `lights`, `shadow_lights`.

**`fps_1pct_low` matters more than `fps_avg`.** An average of 70 with a 1% low
of 22 stutters, and the player feels the 22.

## 2. Triage in this order. Do not skip ahead.

**a. Turn off every shadow.** Set `shadow_enabled = false` on all lights, re-run.

- Recovered? → **stop here.** The fix is a shadow policy, not a mesh rebuild.
  Pick one hero light per space, let it cast, turn the rest off, and set
  `shadow_budget` on the `GDLightingRig` so it is enforced rather than
  remembered.
- Did not recover? → continue.

**b. Draw calls high with few objects?** → material/instance fragmentation.
Merge static geometry into single meshes; share materials. A modular kit is an
*authoring* convenience: 60 placed pieces at 4 materials each is 240 draws, and
once the layout is final it should be merged.

**c. Primitives high?** → geometry. Decimate in stages, or add LODs. Judge the
silhouette, not the triangle count.

**d. Only now** look at scripts and physics. The usual find is `_process` doing
per-frame work over the whole world instead of the ~120 m around the player
(godot-patterns.md: ask, don't cache — but ask *locally*).

## 3. Confirm you fixed the thing you think you fixed

Re-run the same plan. If the number moved but you cannot say which change moved
it, revert and change one thing at a time. A performance fix you cannot
attribute will come back, and next time you will not remember what you tried.

## 4. Record it

`.planning/BUDGET.md`:
- inside budget → snapshot the numbers so the next phase can detect a regression
- accepted an overspend → add a Deviations row with the reason and a revisit
  date. An unrecorded overspend quietly becomes the new normal.

New cost knowledge goes into `gatekeeper/references/godot-patterns.md` so the next
phase does not rediscover it.

## Finish

Report: before/after numbers, which triage step found it, exactly what changed,
and the policy you set so it does not recur.
