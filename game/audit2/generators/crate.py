"""Example asset generator - a supply crate.

Run it:   gd asset generators/crate.py
Iterate:  change a number, run again. You never open Blender's UI, and you never
          hand-edit the mesh; when the proportions are wrong you fix one line.

Read this once and the shape of every other generator is obvious:
  1. args with defaults, so the same script makes a family of crates
  2. primitives only - boxes, cylinders, a bevel. Light supplies the detail.
  3. palette keys, never raw colours
  4. checks that make the spec a measured fact
  5. export + report, so the pipeline can gate on numbers
"""
import bpy
import gdblend as gd

a = gd.args(out=".", size=0.8, slats=4, name="crate")

body = None
parts = []

# Main box
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, a["size"] / 2.0))
body = bpy.context.active_object
body.name = a["name"]
body.scale = (a["size"], a["size"], a["size"])
gd.apply_transforms(body)
gd.assign(body, "base_mid")
parts.append(body)

# Slats: a few thin boxes. This is the whole trick - simple forms, repeated,
# with a bevel so every edge catches a highlight.
inset = a["size"] * 0.02
for i in range(int(a["slats"])):
    t = (i + 0.5) / float(a["slats"])
    z = t * a["size"]
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, z))
    s = bpy.context.active_object
    s.name = "%s_slat_%d" % (a["name"], i)
    s.scale = (a["size"] + inset, a["size"] + inset, a["size"] * 0.06)
    gd.apply_transforms(s)
    gd.assign(s, "metal_worn")
    parts.append(s)

crate = gd.join(parts, a["name"])
gd.bevel(crate, width=0.008, segments=2)
gd.set_origin_to_base(crate)

# The spec, enforced.
gd.check_dims(crate, [a["size"], a["size"], a["size"]], tol=0.05)
gd.check_tris(crate, 1500)
gd.check_transforms(crate)
gd.check_origin_at_base(crate)
gd.check_palette()

path = gd.export_glb(a["out"] + "/" + a["name"], [crate])
gd.report(glb=path)
