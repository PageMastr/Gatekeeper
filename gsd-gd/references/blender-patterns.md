# Blender patterns

How to write a generator that produces an asset worth putting in the game.

Read `gsd-gd/lib/gdblend/__init__.py` for the API. This file is about judgement.

---

## The shape of a generator

```python
import bpy
import gdblend as gd

a = gd.args(out=".", width=2.0, height=3.0, name="wall_2m")   # 1. parameters

# 2. primitives only
bpy.ops.mesh.primitive_cube_add(size=1.0)
ob = bpy.context.active_object
...

gd.assign(ob, "metal_worn")                                    # 3. palette keys
gd.bevel(ob, 0.01, 2)

gd.check_dims(ob, [a["width"], 0.2, a["height"]])              # 4. contracts
gd.check_grid(ob)
gd.check_tris(ob, 3000)
gd.check_palette()
gd.check_transforms(ob)

path = gd.export_glb(a["out"] + "/" + a["name"], [ob])         # 5. export
gd.report(glb=path)                                            # 6. measure
```

Six parts, always in that order. The bootstrap fails the run if `report()` is
never called — an unmeasured asset cannot be gated on, which makes it worthless
to the pipeline regardless of how it looks.

## Parameterise, don't duplicate

One `wall.py` that takes `--width` makes a family. Ten near-identical scripts
make ten things to fix when the spec changes. If two generators share more than
a few lines, one of them should have been an argument.

## Simple forms, honest proportions

Do not attempt realistic geometry. A house is boxes and a roof. A crate is a box
and four thin boxes. A tree is a trunk and clustered planes. What makes these
read as real:

- **A bevel on every edge.** 0.8–1.5 cm, 2 segments. Every edge then catches a
  highlight, and highlights are what the eye reads as "solid object".
- **Correct proportions.** A door is 2.0–2.1 m. A step is 0.18 m. A corridor a
  person hurries down is 1.6–2.0 m wide. Getting these right does more than
  any amount of detail.
- **Asymmetry.** One panel rotated 2°, one plank shorter. Perfect repetition
  reads as a texture, not a thing.
- **Detail where the player stands.** Budget geometry to eye level and hand
  height; the ceiling can be a plane.

## Foliage: use scanned leaves on planes

The gap between good and bad vegetation in an AI-built scene is almost entirely
this: clustering *photographed* leaf material on flat rectangles versus modelling
leaf geometry from scratch. Modelled leaves come out as visible triangles and
cost ten times as much.

So: a trunk (real geometry, bevelled, tapered), and leaf clusters as a few
crossed planes carrying an alpha-cut leaf texture. Rotate each cluster randomly.
Vary scale ±20%. Three or four cluster prototypes, scattered, is a tree.

## Modular kits: the grid is the whole contract

A kit only pays off if the pieces tile. Which means every bound must land on the
snap grid (`gdblend.GRID`, 0.25 m), measured, not eyeballed:

```python
gd.check_grid(ob)             # every min/max bound on the grid
gd.check_dims(ob, [2.0, 0.2, 3.0])
```

Get this wrong and you find out three phases later, when 80 placed pieces have
a 3 mm seam each. Also fix, and write down:

- **Origin convention** — a wall's origin at its base centre, so it sits on the
  floor; a socket piece's origin at the socket.
- **Which axis is "outward"** for one-sided pieces.
- **A naming scheme** — `wall_2m`, `wall_2m_door`, `corner_in`, `corner_out`.
  Kits get large; names are the only index you will have.

Build the module set first, then the props that decorate it (pipes, fans,
grates, cable runs). Props are what turn a correct kit into a place, and they
are a separate job because they have a different failure mode.

## Textures: roughness first, scale above all

- **Scale is the biggest lever.** The same panel texture at the wrong
  metres-per-tile reads as concrete. Decide metres-per-tile explicitly and write
  it into the asset spec.
- **Roughness carries material identity** more than albedo does. A wrong
  roughness reads as the wrong material even with the right colour. Tune
  roughness before re-tinting anything.
- **Pick one source and stay there.** Photo-scanned PBR sets (albedo +
  roughness + normal) and code-generated noise both work. Mixing them in one
  scene is what looks wrong, not either one alone.

## Importing something realistic: decimate in stages

A downloaded asset that does not match the game's poly density has to come down.
Run three decimation ratios, look at all three, pick one — the right amount is a
judgement call and it differs per asset.

```python
gd.decimate(ob, 0.35)      # then 0.2, then 0.1; compare, choose
```

Check the silhouette, not the triangle count: decimation that preserves the count
budget but collapses the outline has failed.

Log the licence the moment it lands (`gd credits`).

## Export hygiene

`gd.export_glb()` handles Y-up and applies modifiers. What it cannot fix:

- **Unapplied scale.** A 0.01 scale baked into the object is the classic "wrong
  size in Godot" bug. `check_transforms()` catches it.
- **Material count.** Each extra material is an extra draw call *per instance*.
  A kit wall with four materials placed 60 times costs 240 draws. Two is
  usually the sane ceiling for a module.
- **Origin.** `check_origin_at_base()` for anything that sits on ground.

## Reproducibility

Same arguments in, same bytes out. If a generator uses randomness, seed it from
an argument (`--seed`) and record the seed in the report. An asset you cannot
regenerate is a hand-edited mesh wearing a script's clothes.
