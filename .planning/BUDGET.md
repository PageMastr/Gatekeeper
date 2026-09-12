# Performance Budget — Audit2

> Budgets are enforced by `gd playtest`, which fails the run when a number goes
> out of bounds.
>
> **The numbers live in `.planning/config.json` — this project's own file.** This
> is where they are *justified*, and where the cost model is written down so
> nobody has to rediscover it at 30 fps. One source of truth each: change a
> number there, explain it here.
>
> ```bash
> gd config                 # what is in force, and what this project overrode
> ```
>
> `gsd-gd/config.json` in the install root holds machine defaults only. It is
> shared by every game here, so a number set there is a number set for all of
> them — which is why per-project overrides exist.

## Hard gates

| metric | budget | measured by |
|---|---|---|
| fps_avg | ≥ 60 | `gd playtest` perf window, vsync off |
| fps_1pct_low | ≥ 40 | same |
| draw_calls_max | ≤ 1200 | `RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME` |
| shadow-casting lights | ≤ 4 | walk of the live scene tree |

## Triangle budgets, per asset class

| class | tris | notes |
|---|---|---|
| prop | ≤ 1 500 | crates, pipes, debris — most of the world |
| hero prop | ≤ 6 000 | things the player stands next to and looks at |
| environment module | ≤ 3 000 | a kit wall/floor/corner; multiplied by every instance |
| character | ≤ 12 000 | main character; enemies target half |

Enforced in the generator with `gdblend.check_tris(obj, budget)`. A generator
that exceeds budget fails its own build — it does not get to the engine.

## The cost model (read this before optimising anything)

**Shadows, not lights, are the bill.** A light is cheap. A light that casts
shadows makes the renderer draw the scene *again* from that light's point of
view. Six hundred visible objects can become fourteen thousand draws with a
handful of shadow-casting lamps in a corridor. The first thing to try when the
frame rate collapses is switching shadows off on every light except the hero
light — if that fixes it, you have found it, and the fix is a shadow policy, not
a mesh rebuild.

Order of investigation, cheapest first:

1. Turn off all shadows. Did fps recover? → shadow policy problem.
2. Count draw calls. High with few objects? → material/instance fragmentation;
   merge static meshes, share materials.
3. Count primitives. High? → geometry problem; decimate or LOD.
4. Only then look at scripts and physics.

## Standing policies

- **One shadow-casting light per room**, chosen as the hero light. Fill lights
  never cast. `GDLightingRig.enforce_shadows()` applies this at runtime and
  warns when it has to.
- **Static geometry is merged**, not instanced per-piece, once a kit layout is
  final. Modular kits are for authoring, not for shipping 400 draw calls.
- **No shadow-casting light on anything that moves** unless it is the hero light
  of that moment.
- **Measure at the target resolution.** A budget met at 640×360 is not met.

## Deviations

Every accepted overspend, with its reason and its expiry.

| date | metric | budget | actual | why accepted | revisit |
|---|---|---|---|---|---|
