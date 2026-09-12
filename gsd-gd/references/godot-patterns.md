# Godot patterns

Implementation patterns worth knowing before you design a system, most of them
recovered from watching AI-built games succeed and fail at them. Each entry says
what the pattern is *for* — copy the reasoning, not the code.

---

## Accumulating world state: one image, not a list

**Problem:** footprints in snow, scorch marks, blood, compressed grass. The
naïve version spawns a decal or mesh per event, and dies at a few hundred.

**Pattern:** one fixed-size `ViewportTexture` (say 1024×1024 covering a 256 m
square that follows the player). Every event draws a small brush into it. The
ground shader samples it for both displacement and colour. Wind fades it by
drawing a slightly transparent clear over it each second.

**Why:** cost is constant. A thousand tracks cost what one costs. Memory never
grows. And because the *enemy* reads the same texture, the bear can literally
walk into your footprints with no extra system.

```
SubViewport (1024x1024, render_target_update_mode = ALWAYS)
 └─ Node2D              # brush strokes drawn here
Ground shader: texture(tracks_tex, world_to_track_uv(world_pos)).r -> depth
```

Keep the track window centred on the player and re-project when it slides, or
accept a bounded play area. Sliding is the harder half — do it as its own job.

## Height fields: ask, don't cache

Terrain height that is modified by gameplay (snow compressed by boots, drifts
built by wind) is not a constant, so caching it is wrong. Query it per frame for
the ~120 m around the player only — that is 100k–ish samples, which is fine —
and never for the whole map.

The window slides with the character. Everything outside it does not exist yet.

## Surface resistance as one scalar

"Deep snow you walk, thin snow you can run" wants to be one number on the
player (`drag: float`), written by the terrain system and read by locomotion.
Resist the urge to make it a state machine. One scalar keeps the interaction
between locomotion, stamina, and sound to one multiply each.

## Interior reveal: remove the roof, don't change the scene

A building interior that is "the same place" as the exterior should not be a
separate scene — the player must be able to see the danger outside through the
doorway.

**Pattern:** on entering the trigger volume, hide the roof and the near wall.
That is the whole trick. Two `visible = false` assignments beat a level
transition, and the outside stays live.

## Camera occlusion fade

The camera fires a ray at the player every frame. Anything it hits between the
two gets faded (material `albedo_color.a` toward 0, or a dither shader). Fade the
whole object, not a sphere-mask — a partially dissolved tree reads as a bug, a
fully faded one reads as intent.

Requires materials with transparency enabled, which costs a sort. Only do it for
objects tagged as occluders (a group, not every mesh).

## Lighting: one hero light

Named presets live in `GDLightingRig.PRESETS`. The discipline they encode:

- The sky is *dim*. A bright moon lights the entire world and nothing you place
  can then create mood. Push `sky_energy` down until the fire matters.
- One hero light casts shadows. Fill lights never do.
- Fall-off into black is what reads as depth. If everything is legible
  everywhere, the scene is flat, no matter how good the assets are.
- Blackout is never `#000000`. Keep exactly one readable line — a floor strip, a
  door seal — or the player stops playing.

Tune with the F9 panel, press "Copy preset", paste the result back into the
dictionary. Taste in, source code out.

## Shadow discipline (the performance pattern that matters)

A shadow-casting light re-renders the scene from its own point of view. This is
the difference between 600 draws and 14 000.

Triage order when the frame rate collapses:

1. Turn off **all** shadows. Recovered? → shadow policy problem, stop here.
2. Draw calls high with few objects? → material/instance fragmentation. Merge
   static meshes; share materials.
3. Primitives high? → geometry. Decimate, or add LODs.
4. Only then look at scripts and physics.

`GDLightingRig.enforce_shadows()` disables shadows on the lowest-energy casters
until the scene is inside `shadow_budget`, and warns when it does. Modular kits
should be merged into single static meshes once a layout is final — a kit is an
authoring convenience, not a shipping strategy.

## Locomotion for many-legged things: build the observation tool first

A spider is a movement problem: eight legs, each finding its own floor. When it
starts flying, the first thing to build is **not** a fix — it is a button that
advances one leg at a time, and a lab scene with one straight line in it.

The failure is almost never in the walk cycle. It is at surface changes — floor
to wall, wall to ceiling — where the body commits before the legs have found
purchase. You cannot see that at full speed in a real level.

## Animation: rigged clips beat code-driven pieces

Two approaches to making a modelled character move:

- **Rig and animate in Blender**, Godot plays the clips back. Import free mocap
  (files open straight in Blender, no plugin) and it moves like a person,
  because it was a person.
- **Split the body into solid pieces and drive every joint from code**, no
  skeleton, no keyframes.

The first looks dramatically better and is dramatically less work. Choose the
second only as a deliberate experiment, and expect to spend a lab session per
gait. Record the choice in `CONTEXT.md` as a one-way door — the two approaches
need different asset shapes and you cannot cheaply switch later.

For organic bodies, model from blobs that melt into each other (metaballs, or
sculpt-like unions) rather than boxes: you get shoulders, ribs and a spine for
free, and boxes never will.

## Test scenes belong in `lab/`

One system, one straight line, no other moving parts. `lab/` scenes are where
gait, camera, weapon feel and creature behaviour get iterated. They are cheap to
playtest (small, fast, deterministic) and they never lie about which system
caused the failure.

## Sound

Generate or source, then log the licence immediately (`gd credits`). Free
libraries are fine; the ledger is not optional. Positional audio wants its own
job — mixing is a taste pass, not a build pass.
