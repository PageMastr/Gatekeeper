"""gdblend - the Blender half of GSD-GameDev.

Asset generators are *scripts*, not .blend files. The script is the source of
truth; the .glb is a build artifact. When the roof is wrong you fix one line
and run it again - you never hand-edit a mesh, because a hand-edit cannot be
reproduced, reviewed, or diffed.

This library exists so every generator gets the same four things for free:

  1. A palette contract.  `mat("snow_lit")` resolves against
     .planning/COLOR_BIBLE.md and *raises* on an unknown key. No agent can
     invent a fourth shade of grey.
  2. A dimension contract. `check_grid()` / `check_dims()` make a modular kit's
     snap grid a measured fact instead of a hope.
  3. Measurement.  `measure()` returns tris/verts/dims/bounds, and `report()`
     prints the single GDMETRICS line the CLI parses.
  4. A Godot-shaped export. `export_glb()` writes Y-up, modifiers applied,
     +Z forward - the orientation Godot expects, every time.

Generators are expected to be idempotent: same args in, same bytes out.
"""
from __future__ import annotations

import json
import math
import os
import re

import bpy
from mathutils import Vector

__version__ = "1.0.0"

# Filled in by harness/blender/bootstrap.py
ARGV: list = []
SCRIPT: str = ""

def _load_config() -> dict:
    """Effective config, handed in by `gd blender` as GD_CONFIG_JSON.

    Machine defaults merged with this project's `.planning/config.json`, so a
    game with a 0.5 m kit grid or tighter triangle budgets does not have to
    change a value that every other game on the machine shares.
    """
    raw = os.environ.get("GD_CONFIG_JSON")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return {}


CONFIG: dict = _load_config()

# Modular-kit snap grid, in metres. Everything a kit emits should land on it.
# Per-project overridable: `.planning/config.json` -> {"blender": {"grid": 0.5}}
GRID: float = float((CONFIG.get("blender") or {}).get("grid", 0.25))


def tri_budget(asset_class: str) -> int:
    """Triangle budget for an asset class, from the effective config.

    Prefer this to a literal: `check_tris(ob, gd.tri_budget("prop"))` tracks the
    project's own budget, while `check_tris(ob, 1500)` silently ignores it.
    """
    table = ((CONFIG.get("budget") or {}).get("max_asset_tris") or {})
    return int(table.get(asset_class, 1500))

_checks: list = []
_reported = False


# --------------------------------------------------------------------------- #
# scene lifecycle
# --------------------------------------------------------------------------- #
def reset_scene() -> None:
    """Empty, deterministic scene. Factory startup alone still leaves a cube."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.render.fps = 30


def args(**defaults):
    """Parse `--key value` / `--flag` pairs out of ARGV with defaults.

    gdblend.args(out=".", width=1.0, hollow=False) -> namespace-ish dict
    Types are coerced to match the default's type.
    """
    out = dict(defaults)
    i = 0
    while i < len(ARGV):
        tok = ARGV[i]
        if not tok.startswith("--"):
            i += 1
            continue
        key = tok[2:].replace("-", "_")
        default = defaults.get(key)
        if isinstance(default, bool):
            out[key] = True
            i += 1
            continue
        if i + 1 >= len(ARGV):
            i += 1
            continue
        raw = ARGV[i + 1]
        if isinstance(default, bool):
            out[key] = raw.lower() in ("1", "true", "yes")
        elif isinstance(default, int) and not isinstance(default, bool):
            out[key] = int(float(raw))
        elif isinstance(default, float):
            out[key] = float(raw)
        elif isinstance(default, (list, tuple)):
            out[key] = [float(x) for x in raw.split(",")]
        else:
            out[key] = raw
        i += 2
    return out


# --------------------------------------------------------------------------- #
# the palette contract
# --------------------------------------------------------------------------- #
_palette_cache: dict | None = None


def _color_bible_path() -> str:
    p = os.environ.get("GD_PLANNING")
    if p:
        cand = os.path.join(p, "COLOR_BIBLE.md")
        if os.path.exists(cand):
            return cand
    root = os.environ.get("GD_ROOT", "")
    cand = os.path.join(root, ".planning", "COLOR_BIBLE.md")
    return cand


def palette() -> dict:
    """Parse the Color Bible table into {key: {hex, rgb, roughness, metallic, emission, role}}.

    Table shape (see gsd-gd/templates/COLOR_BIBLE.md):
      | key | hex | roughness | metallic | emission | role |
    """
    global _palette_cache
    if _palette_cache is not None:
        return _palette_cache
    path = _color_bible_path()
    if not os.path.exists(path):
        raise RuntimeError(
            "no COLOR_BIBLE.md found at %s - run /gd:frame before building any asset. "
            "Nothing enters the game without the palette." % path)
    entries: dict = {}
    for line in open(path, encoding="utf-8"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0].lower() in ("key", "---") or set(cells[0]) <= {"-", ":"}:
            continue
        m = re.fullmatch(r"#?([0-9a-fA-F]{6})", cells[1])
        if not m:
            continue
        key = cells[0]

        def num(idx, dflt):
            try:
                return float(cells[idx])
            except (IndexError, ValueError):
                return dflt

        entries[key] = {
            "hex": "#" + m.group(1).lower(),
            "rgb": hex_to_linear(m.group(1)),
            "roughness": num(2, 0.7),
            "metallic": num(3, 0.0),
            "emission": num(4, 0.0),
            "role": cells[5] if len(cells) > 5 else "",
        }
    if not entries:
        raise RuntimeError("COLOR_BIBLE.md at %s has no parsable palette rows" % path)
    _palette_cache = entries
    return entries


def hex_to_linear(h: str):
    """sRGB hex -> linear RGB. Blender and Godot both want linear; skipping this
    is the single most common reason 'the colours came out washed out'."""
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def mat(key: str, *, roughness=None, metallic=None, emission=None):
    """Material from a Color Bible key. Unknown key = hard failure, by design."""
    pal = palette()
    if key not in pal:
        raise KeyError(
            "'%s' is not in the Color Bible. Allowed keys: %s. "
            "Add the swatch to .planning/COLOR_BIBLE.md (and say why) before using it."
            % (key, ", ".join(sorted(pal))))
    e = pal[key]
    name = "pal_" + key
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    r, g, b = e["rgb"]
    bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
    bsdf.inputs["Roughness"].default_value = e["roughness"] if roughness is None else roughness
    bsdf.inputs["Metallic"].default_value = e["metallic"] if metallic is None else metallic
    em = e["emission"] if emission is None else emission
    if em > 0 and "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (r, g, b, 1.0)
        bsdf.inputs["Emission Strength"].default_value = em
    return m


def assign(obj, key: str, **kw):
    obj.data.materials.clear()
    obj.data.materials.append(mat(key, **kw))
    return obj


# --------------------------------------------------------------------------- #
# measurement
# --------------------------------------------------------------------------- #
def measure(obj) -> dict:
    """Measure the mesh *with modifiers applied* - what ships, not what's authored."""
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    try:
        pts = [obj.matrix_world @ v.co for v in me.vertices]
        tris = sum(max(len(p.vertices) - 2, 0) for p in me.polygons)
        ngons = sum(1 for p in me.polygons if len(p.vertices) > 4)
        verts = len(me.vertices)
    finally:
        ev.to_mesh_clear()
    if not pts:
        return {"name": obj.name, "tris": 0, "verts": 0,
                "dims": [0, 0, 0], "min": [0, 0, 0], "max": [0, 0, 0], "ngons": 0}
    mn = [min(p[i] for p in pts) for i in range(3)]
    mx = [max(p[i] for p in pts) for i in range(3)]
    return {
        "name": obj.name,
        "tris": tris,
        "verts": verts,
        "ngons": ngons,
        "dims": [round(mx[i] - mn[i], 4) for i in range(3)],
        "min": [round(v, 4) for v in mn],
        "max": [round(v, 4) for v in mx],
        "origin": [round(v, 4) for v in obj.location],
        "scale": [round(v, 4) for v in obj.scale],
        "materials": [m.name for m in obj.data.materials if m],
    }


def scene_metrics() -> dict:
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    per = [measure(o) for o in objs]
    return {
        "objects": len(per),
        "tris": sum(p["tris"] for p in per),
        "verts": sum(p["verts"] for p in per),
        "meshes": per,
        "materials": sorted({m for p in per for m in p["materials"]}),
    }


# --------------------------------------------------------------------------- #
# contracts / checks
# --------------------------------------------------------------------------- #
def check(name: str, ok: bool, detail: str = "") -> bool:
    _checks.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    return bool(ok)


def check_dims(obj, expect, tol: float = 0.001) -> bool:
    """A kit module either is the advertised size or it is broken. No eyeballing."""
    m = measure(obj)
    got = m["dims"]
    ok = all(abs(got[i] - expect[i]) <= tol for i in range(3))
    return check("dims:" + obj.name, ok, "expected %s got %s (tol %s)" % (list(expect), got, tol))


def check_grid(obj, grid: float = None, tol: float = 0.001) -> bool:
    """Every bound of a modular piece must land on the snap grid, or the kit
    will not tile and you will find out three phases later."""
    grid = grid or GRID
    m = measure(obj)
    off = []
    for axis, vals in (("min", m["min"]), ("max", m["max"])):
        for i, v in enumerate(vals):
            r = abs(v / grid - round(v / grid)) * grid
            if r > tol:
                off.append("%s.%s=%.4f" % (axis, "xyz"[i], v))
    return check("grid:" + obj.name, not off,
                 "grid %s; off-grid bounds: %s" % (grid, ", ".join(off)) if off else "grid %s" % grid)


def check_tris(obj, budget: int) -> bool:
    m = measure(obj)
    return check("tris:" + obj.name, m["tris"] <= budget,
                 "%d / %d" % (m["tris"], budget))


def check_palette() -> bool:
    """No material may exist that did not come from the Color Bible."""
    stray = [m.name for m in bpy.data.materials
             if m.users and not m.name.startswith("pal_")]
    return check("palette_only", not stray,
                 "non-palette materials: %s" % stray if stray else "all materials from Color Bible")


def check_transforms(obj) -> bool:
    """Unapplied scale is the classic 'it's the wrong size in Godot' bug."""
    s = [round(v, 5) for v in obj.scale]
    return check("transform:" + obj.name, s == [1.0, 1.0, 1.0],
                 "scale %s (apply it before export)" % s)


def check_origin_at_base(obj, tol: float = 0.001) -> bool:
    """Props whose origin sits at their base drop onto terrain without guesswork."""
    m = measure(obj)
    ok = abs(m["min"][2] - m["origin"][2]) <= tol
    return check("origin_at_base:" + obj.name, ok,
                 "min.z=%.4f origin.z=%.4f" % (m["min"][2], m["origin"][2]))


# --------------------------------------------------------------------------- #
# modelling helpers
# --------------------------------------------------------------------------- #
def apply_transforms(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)


def set_origin_to_base(obj) -> None:
    """Put the origin on the footprint centre at z=min, so the prop can simply be
    dropped at a terrain height with no per-asset fudge offset."""
    m = measure(obj)
    cx = (m["min"][0] + m["max"][0]) / 2.0
    cy = (m["min"][1] + m["max"][1]) / 2.0
    prev = tuple(bpy.context.scene.cursor.location)
    bpy.context.scene.cursor.location = (cx, cy, m["min"][2])
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.context.scene.cursor.location = prev


def decimate(obj, ratio: float, *, mode: str = "COLLAPSE"):
    """Reduce triangle count. This is how a realistic download becomes a
    low-poly asset that matches the rest of the game (three passes, pick one)."""
    md = obj.modifiers.new("gd_decimate", "DECIMATE")
    md.decimate_type = mode
    if mode == "COLLAPSE":
        md.ratio = float(ratio)
    return obj


def bevel(obj, width: float = 0.01, segments: int = 2):
    """A 1cm bevel is the cheapest realism there is: it gives every edge a
    highlight, so light does the work instead of geometry."""
    md = obj.modifiers.new("gd_bevel", "BEVEL")
    md.width = width
    md.segments = segments
    md.limit_method = "ANGLE"
    md.angle_limit = math.radians(30)
    return obj


def shade_smooth_by_angle(obj, degrees: float = 30.0):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    try:  # Blender 4.1+ replaced auto-smooth with a modifier-driven operator
        bpy.ops.object.shade_auto_smooth(angle=math.radians(degrees))
    except Exception:
        pass
    return obj


def join(objs, name: str):
    objs = [o for o in objs if o]
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    out = bpy.context.active_object
    out.name = name
    return out


# --------------------------------------------------------------------------- #
# export
# --------------------------------------------------------------------------- #
def export_glb(path: str, objs=None, *, apply_modifiers: bool = True) -> str:
    """Export Godot-shaped GLB: Y-up, modifiers applied, absolute path returned.

    Godot imports GLB without needing Blender installed on the player's machine,
    and .glb diffs as a binary artifact you can regenerate - which is the point.
    """
    path = os.path.abspath(path)
    if not path.lower().endswith(".glb"):
        path += ".glb"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    use_sel = objs is not None
    if use_sel:
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=use_sel,
        export_apply=apply_modifiers,
        export_yup=True,
        export_cameras=False,
        export_lights=False,
    )
    return path


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #
def reported() -> bool:
    return _reported


def report(**extra) -> dict:
    """Print the one GDMETRICS line the CLI parses. Call this once, at the end."""
    global _reported
    payload = {"ok": all(c["ok"] for c in _checks), "script": os.path.basename(SCRIPT or ""),
               "checks": _checks, "scene": scene_metrics()}
    payload.update(extra)
    _reported = True
    print("GDMETRICS " + json.dumps(payload, default=str))
    if not payload["ok"]:
        for c in _checks:
            if not c["ok"]:
                print("  [FAIL] %s  %s" % (c["name"], c["detail"]))
    return payload


def fail(reason: str) -> dict:
    global _reported
    _reported = True
    print("GDMETRICS " + json.dumps({"ok": False, "error": reason, "checks": _checks}))
    return {"ok": False}
