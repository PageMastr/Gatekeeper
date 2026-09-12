#!/usr/bin/env python3
"""gddoc - a local, version-exact Godot API reference.

Why this exists: most models learned Godot from Godot 3 material. Godot 4
renamed, moved or deleted a large part of the API, so recalled-from-memory
GDScript is wrong in ways that look right. Guessing is not acceptable when the
correct signature is sitting on this disk.

The source of truth is the engine's own XML class reference, from the *same
source tree the binary was built from* - so it cannot drift from the running
engine:

    D:/Godot/GodotEngine/doc/classes/*.xml          (810 core classes)
    D:/Godot/GodotEngine/modules/*/doc_classes/*.xml (261 module classes)

Verbs:
    gddoc index [--force]         build/refresh the symbol index
    gddoc class <Name> [--full]   signatures for a class (--full adds descriptions)
    gddoc member <Class.member>   exact signature + description for one member
    gddoc search <query>          find classes and members by keyword
    gddoc exists <Name>           is this a real class in this build?
    gddoc scan <file.gd>          flag Godot-3-isms and unknown symbols
    gddoc stats                   what the index contains
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# Engine docs contain typographic quotes, arrows and accents. The Windows console
# defaults to cp1252 and a UnicodeEncodeError here would look like a tool bug.
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
SYS_DIR = ROOT / "gsd-gd"
CACHE = SYS_DIR / "cache"
INDEX = CACHE / "godot-api-index.json"


def cfg() -> dict:
    return json.loads((SYS_DIR / "config.json").read_text(encoding="utf-8"))


def godot_source() -> Path:
    p = Path(cfg()["toolchain"]["godot"]["source_root"])
    if not (p / "doc" / "classes").is_dir():
        print("gddoc: error: no doc/classes under " + str(p), file=sys.stderr)
        raise SystemExit(2)
    return p


def emit(verb: str, payload: dict) -> None:
    print("GDDOC" + verb.upper() + " " + json.dumps(payload, default=str))


# --------------------------------------------------------------------------- #
# BBCode -> plain text
# --------------------------------------------------------------------------- #
def detag(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    # [method Class.foo] / [member x] / [constant X] -> the bare symbol
    s = re.sub(r"\[(?:method|member|constant|signal|enum|param|theme_item)\s+([^\]]+)\]", r"`\1`", s)
    s = re.sub(r"\[(?:code|codeblock)(?:\s[^\]]*)?\](.*?)\[/(?:code|codeblock)\]", r"`\1`", s, flags=re.S)
    s = re.sub(r"\[url=([^\]]+)\](.*?)\[/url\]", r"\2 (\1)", s, flags=re.S)
    s = re.sub(r"\[/?(?:b|i|u|s|center|br|kbd|color[^\]]*|font[^\]]*|img[^\]]*)\]", "", s)
    s = re.sub(r"\[([A-Z][A-Za-z0-9_]*)\]", r"\1", s)          # [Node3D] -> Node3D
    s = re.sub(r"\$DOCS_URL", "https://docs.godotengine.org/en/4.7", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def signature(m: ET.Element) -> str:
    ret = (m.find("return").get("type") if m.find("return") is not None else "void")
    params = []
    for p in m.findall("param"):
        t = "%s: %s" % (p.get("name"), p.get("type"))
        if p.get("default") is not None:
            t += " = " + p.get("default")
        params.append(t)
    quals = m.get("qualifiers") or ""
    sig = "%s %s(%s)" % (ret, m.get("name"), ", ".join(params))
    return (sig + " " + quals).strip()


# --------------------------------------------------------------------------- #
# index
# --------------------------------------------------------------------------- #
def xml_paths(src: Path):
    yield from sorted((src / "doc" / "classes").glob("*.xml"))
    yield from sorted(src.glob("modules/*/doc_classes/*.xml"))


def cmd_index(a) -> int:
    src = godot_source()
    if INDEX.exists() and not a.force:
        idx = json.loads(INDEX.read_text(encoding="utf-8"))
        emit("index", {"ok": True, "cached": True, "classes": len(idx["classes"]),
                       "generated": idx.get("generated"), "path": str(INDEX)})
        return 0
    CACHE.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    classes: dict = {}
    failed = []
    for xf in xml_paths(src):
        try:
            root = ET.parse(xf).getroot()
        except ET.ParseError as e:
            failed.append(xf.name + ": " + str(e))
            continue
        if root.tag != "class":
            continue
        name = root.get("name")
        methods = {}
        for m in root.findall("./methods/method"):
            methods[m.get("name")] = signature(m)
        props = {}
        for p in root.findall("./members/member"):
            props[p.get("name")] = p.get("type") or "Variant"
        signals = {}
        for s in root.findall("./signals/signal"):
            args = ["%s: %s" % (q.get("name"), q.get("type")) for q in s.findall("param")]
            signals[s.get("name")] = "(%s)" % ", ".join(args)
        consts = {}
        enums: dict = {}
        for c in root.findall("./constants/constant"):
            consts[c.get("name")] = c.get("value")
            if c.get("enum"):
                enums.setdefault(c.get("enum"), []).append(c.get("name"))
        ops = sorted({o.get("name") for o in root.findall("./operators/operator")})
        classes[name] = {
            "inherits": root.get("inherits") or "",
            "xml": str(xf.relative_to(src)).replace("\\", "/"),
            "brief": detag("".join(root.find("brief_description").itertext())
                           if root.find("brief_description") is not None else ""),
            "methods": methods,
            "properties": props,
            "signals": signals,
            "constants": consts,
            "enums": enums,
            "operators": ops,
        }
    idx = {
        "godot_version": cfg()["toolchain"]["godot"]["version"],
        "source_root": str(src),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "classes": classes,
    }
    INDEX.write_text(json.dumps(idx), encoding="utf-8")
    emit("index", {"ok": not failed, "cached": False, "classes": len(classes),
                   "methods": sum(len(c["methods"]) for c in classes.values()),
                   "seconds": round(time.time() - t0, 2),
                   "bytes": INDEX.stat().st_size, "failed": failed[:10],
                   "path": str(INDEX)})
    return 0


def load_index() -> dict:
    if not INDEX.exists():
        cmd_index(argparse.Namespace(force=False))
    return json.loads(INDEX.read_text(encoding="utf-8"))


def ancestry(idx: dict, name: str):
    """Class plus every base class, nearest first."""
    out = []
    seen = set()
    cur = name
    while cur and cur in idx["classes"] and cur not in seen:
        out.append(cur)
        seen.add(cur)
        cur = idx["classes"][cur]["inherits"]
    return out


# --------------------------------------------------------------------------- #
# lookup
# --------------------------------------------------------------------------- #
def cmd_class(a) -> int:
    idx = load_index()
    name = a.name
    if name not in idx["classes"]:
        near = [c for c in idx["classes"] if c.lower() == name.lower()]
        near += [c for c in idx["classes"] if name.lower() in c.lower()][:8]
        emit("class", {"ok": False, "name": name, "reason": "not a class in this build",
                       "did_you_mean": near[:8]})
        return 1
    c = idx["classes"][name]
    chain = ancestry(idx, name)
    emit("class", {"ok": True, "name": name, "inherits": chain[1:],
                   "methods": len(c["methods"]), "properties": len(c["properties"]),
                   "signals": len(c["signals"])})
    print("=== %s%s ===" % (name, (" < " + " < ".join(chain[1:])) if len(chain) > 1 else ""))
    if c["brief"]:
        print(c["brief"])
    src = Path(idx["source_root"])

    def section(title, items, fmt):
        if not items:
            return
        print("\n-- %s (%d) --" % (title, len(items)))
        for k in sorted(items):
            print("  " + fmt(k, items[k]))

    section("methods", c["methods"], lambda k, v: v)
    section("properties", c["properties"], lambda k, v: "%s: %s" % (k, v))
    section("signals", c["signals"], lambda k, v: k + v)
    if c["enums"]:
        print("\n-- enums --")
        for e, vals in sorted(c["enums"].items()):
            print("  %s: %s" % (e, ", ".join(vals)))
    consts_plain = {k: v for k, v in c["constants"].items()
                    if not any(k in v2 for v2 in c["enums"].values())}
    section("constants", consts_plain, lambda k, v: "%s = %s" % (k, v))

    if a.full:
        print("\n-- descriptions --")
        root = ET.parse(src / c["xml"]).getroot()
        d = root.find("description")
        if d is not None:
            print(detag("".join(d.itertext())))
        for m in root.findall("./methods/method"):
            desc = m.find("description")
            print("\n  " + signature(m))
            if desc is not None:
                for line in detag("".join(desc.itertext())).splitlines():
                    print("      " + line)
    if not a.full:
        print("\n(use --full for descriptions; `gddoc member %s.<name>` for one member)" % name)
    return 0


def cmd_member(a) -> int:
    idx = load_index()
    if "." not in a.target:
        print("gddoc: error: use Class.member", file=sys.stderr)
        return 2
    cname, mname = a.target.rsplit(".", 1)
    if cname not in idx["classes"]:
        emit("member", {"ok": False, "reason": "unknown class", "class": cname})
        return 1
    src = Path(idx["source_root"])
    for owner in ancestry(idx, cname):
        c = idx["classes"][owner]
        root = None
        kind = None
        if mname in c["methods"]:
            kind = "method"
        elif mname in c["properties"]:
            kind = "property"
        elif mname in c["signals"]:
            kind = "signal"
        elif mname in c["constants"]:
            kind = "constant"
        if kind is None:
            continue
        root = ET.parse(src / c["xml"]).getroot()
        sig, desc = "", ""
        if kind == "method":
            for m in root.findall("./methods/method"):
                if m.get("name") == mname:
                    sig = signature(m)
                    d = m.find("description")
                    desc = detag("".join(d.itertext())) if d is not None else ""
        elif kind == "property":
            for m in root.findall("./members/member"):
                if m.get("name") == mname:
                    sig = "%s: %s" % (mname, m.get("type"))
                    if m.get("default"):
                        sig += " = " + m.get("default")
                    if m.get("setter"):
                        sig += "   [setter %s / getter %s]" % (m.get("setter"), m.get("getter"))
                    desc = detag("".join(m.itertext()))
        elif kind == "signal":
            for m in root.findall("./signals/signal"):
                if m.get("name") == mname:
                    sig = mname + c["signals"][mname]
                    d = m.find("description")
                    desc = detag("".join(d.itertext())) if d is not None else ""
        else:
            sig = "%s = %s" % (mname, c["constants"][mname])
        emit("member", {"ok": True, "target": a.target, "kind": kind,
                        "declared_on": owner, "signature": sig})
        print("%s.%s   [%s, declared on %s]" % (cname, mname, kind, owner))
        print("  " + sig)
        if desc:
            for line in desc.splitlines():
                print("  " + line)
        return 0
    cands = [m for m in idx["classes"][cname]["methods"]
             if mname.lower() in m.lower()][:8]
    for owner in ancestry(idx, cname)[1:]:
        cands += [m for m in idx["classes"][owner]["methods"] if mname.lower() in m.lower()][:5]
    emit("member", {"ok": False, "target": a.target,
                    "reason": "not found on %s or any base class" % cname,
                    "searched": ancestry(idx, cname), "did_you_mean": cands[:8]})
    print("NOT FOUND: %s on %s (or bases: %s)" % (mname, cname, ", ".join(ancestry(idx, cname)[1:6])))
    if cands:
        print("did you mean: " + ", ".join(cands[:8]))
    return 1


def cmd_search(a) -> int:
    idx = load_index()
    q = a.query.lower()
    hits_c, hits_m = [], []
    for cn, c in idx["classes"].items():
        if q in cn.lower() or q in c["brief"].lower():
            hits_c.append({"class": cn, "brief": c["brief"][:110]})
        for m, sig in c["methods"].items():
            if q in m.lower():
                hits_m.append({"symbol": cn + "." + m, "signature": sig})
        for p in c["properties"]:
            if q in p.lower():
                hits_m.append({"symbol": cn + "." + p, "signature": p + ": " + c["properties"][p]})
    hits_c.sort(key=lambda h: (len(h["class"]), h["class"]))
    hits_m.sort(key=lambda h: (len(h["symbol"]), h["symbol"]))
    emit("search", {"ok": bool(hits_c or hits_m), "query": a.query,
                    "classes": [h["class"] for h in hits_c[:a.limit]],
                    "members": [h["symbol"] for h in hits_m[:a.limit]]})
    if hits_c:
        print("-- classes --")
        for h in hits_c[:a.limit]:
            print("  %-32s %s" % (h["class"], h["brief"]))
    if hits_m:
        print("-- members --")
        for h in hits_m[:a.limit]:
            print("  %-44s %s" % (h["symbol"], h["signature"]))
    if not (hits_c or hits_m):
        print("no matches for " + a.query)
        return 1
    return 0


def cmd_exists(a) -> int:
    idx = load_index()
    ok = a.name in idx["classes"]
    alt = []
    if not ok:
        alt = ([GODOT3_RENAMES[a.name]] if a.name in GODOT3_RENAMES
               else [c for c in idx["classes"] if a.name.lower() in c.lower()][:6])
    emit("exists", {"ok": ok, "name": a.name, "did_you_mean": alt})
    print(("YES  " if ok else "NO   ") + a.name + ("" if ok else "   -> " + ", ".join(alt)))
    return 0 if ok else 1


def cmd_stats(a) -> int:
    idx = load_index()
    c = idx["classes"]
    emit("stats", {"ok": True, "godot_version": idx["godot_version"],
                   "classes": len(c), "methods": sum(len(x["methods"]) for x in c.values()),
                   "properties": sum(len(x["properties"]) for x in c.values()),
                   "signals": sum(len(x["signals"]) for x in c.values()),
                   "constants": sum(len(x["constants"]) for x in c.values()),
                   "generated": idx["generated"], "index": str(INDEX)})
    return 0


# --------------------------------------------------------------------------- #
# scan - catch Godot-3-isms the engine checker lets through
# --------------------------------------------------------------------------- #
GODOT3_RENAMES = {
    # 3.x name -> 4.x name.  The engine's own checker catches most *class*
    # renames; this table exists for the ones it cannot (untyped receivers) and
    # to give the fix, not just the complaint.
    "Spatial": "Node3D",
    "KinematicBody": "CharacterBody3D",
    "KinematicBody2D": "CharacterBody2D",
    "RigidBody": "RigidBody3D",
    "StaticBody": "StaticBody3D",
    "Area": "Area3D",
    "CollisionShape": "CollisionShape3D",
    "MeshInstance": "MeshInstance3D",
    "Camera": "Camera3D",
    "DirectionalLight": "DirectionalLight3D",
    "OmniLight": "OmniLight3D",
    "SpotLight": "SpotLight3D",
    "RayCast": "RayCast3D",
    "Particles": "GPUParticles3D",
    "Particles2D": "GPUParticles2D",
    "CPUParticles": "CPUParticles3D",
    "AnimatedSprite": "AnimatedSprite2D",
    "Sprite": "Sprite2D",
    "Position2D": "Marker2D",
    "Position3D": "Marker3D",
    "ARVROrigin": "XROrigin3D",
    "WorldEnvironment": "WorldEnvironment",
    "SpatialMaterial": "StandardMaterial3D",
    "ShaderMaterial": "ShaderMaterial",
    "TextureButton": "TextureButton",
    "YSort": "(removed - set Node2D.y_sort_enabled)",
    "Navigation": "NavigationRegion3D / NavigationServer3D",
    "InterpolatedCamera": "(removed)",
    "GDNativeLibrary": "GDExtension",
    "Reference": "RefCounted",
    "PoolStringArray": "PackedStringArray",
    "PoolByteArray": "PackedByteArray",
    "PoolIntArray": "PackedInt32Array",
    "PoolRealArray": "PackedFloat32Array",
    "PoolVector2Array": "PackedVector2Array",
    "PoolVector3Array": "PackedVector3Array",
    "PoolColorArray": "PackedColorArray",
    "Directory": "DirAccess",
    "File": "FileAccess",
    "Thread": "Thread",
    "SceneTreeTween": "Tween (via create_tween)",
    "VisualServer": "RenderingServer",
    "ARVRServer": "XRServer",
    "Physics2DDirectSpaceState": "PhysicsDirectSpaceState2D",
    "PhysicsDirectSpaceState": "PhysicsDirectSpaceState3D",
}

# Only defects belong in this table. A gate that also reports style opinions
# gets ignored, and then it catches nothing. Each entry is something that does
# not work in 4.x, paired with what does.
GODOT3_CALLS = [
    (r"\bchange_scene\s*\(", "SceneTree.change_scene_to_file(path) / change_scene_to_packed(packed)"),
    (r"\.instance\s*\(\s*\)", "PackedScene.instantiate()"),
    (r"\bis_a_parent_of\s*\(", "Node.is_ancestor_of()"),
    (r"\bget_parent_spatial\s*\(", "Node3D.get_parent_node_3d()"),
    (r"\.empty\s*\(\s*\)", "is_empty()"),
    # The 3-argument string form is gone; connect("sig", callable) is still fine.
    (r"\.connect\s*\(\s*[\"'][^\"']+[\"']\s*,\s*[^,)]+,\s*[\"']",
     "signal.connect(callable) - the (signal, target, method_name) form is gone"),
    (r"\byield\s*\(", "await"),
    (r"\bOS\.get_ticks_msec\s*\(", "Time.get_ticks_msec()"),
    (r"\bOS\.get_ticks_usec\s*\(", "Time.get_ticks_usec()"),
    (r"\bOS\.get_datetime\s*\(", "Time.get_datetime_dict_from_system()"),
    (r"\bOS\.get_unix_time\s*\(", "Time.get_unix_time_from_system()"),
    (r"\bOS\.window_fullscreen\b", "DisplayServer.window_set_mode()"),
    (r"\bOS\.get_screen_size\s*\(", "DisplayServer.screen_get_size()"),
    (r"\bOS\.get_window_size\s*\(", "DisplayServer.window_get_size()"),
    (r"(?<!@)\bexport\s*(?:\([^)]*\))?\s+var\b", "@export var (and @export_range / @export_enum ...)"),
    (r"(?<!@)\bonready\s+var\b", "@onready var"),
    (r"^tool\s*$", "@tool"),
    (r"\bsetget\b", "a property block: var x: int = 0: set(v): ... get: ..."),
    (r"\bmove_and_slide\s*\(\s*[^)\s]", "CharacterBody3D/2D.move_and_slide() takes no arguments; assign `velocity` first"),
    (r"\bget_tree\(\)\s*\.\s*set_input_as_handled\s*\(", "get_viewport().set_input_as_handled()"),
    (r"\bVisualServer\b", "RenderingServer"),
    (r"\bdeg2rad\s*\(", "deg_to_rad()"),
    (r"\brad2deg\s*\(", "rad_to_deg()"),
    (r"\bstepify\s*\(", "snappedf() / snappedi()"),
    (r"\brand_range\s*\(", "randf_range() / randi_range()"),
    (r"\bOS\.exit\s*\(", "get_tree().quit()"),
    (r"\bNode2D\s*\.\s*set_z_as_relative\s*\(", "CanvasItem.z_as_relative property"),
]


# Members every class has that the XML reference does not list, because they are
# provided by the scripting layer rather than declared per class.
BUILTIN_PSEUDO = {"new"}


def pretty_pattern(pat: str) -> str:
    """A regex is not a useful thing to show a reader. Strip it back to the API."""
    s = re.sub(r"\\[sb]|\\\*|\[\^\)\]\+|\(\?:|[\\()\[\]+*?^$]", "", pat)
    return re.sub(r"\s{2,}", " ", s).strip() or pat


def cmd_scan(a) -> int:
    idx = load_index()
    path = Path(a.file)
    if not path.exists():
        print("gddoc: error: no such file " + str(path), file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    findings = []

    def add(kind, line_no, sym, detail):
        findings.append({"kind": kind, "line": line_no, "symbol": sym, "detail": detail})

    known = idx["classes"]
    for i, line in enumerate(lines, 1):
        code = re.sub(r"#.*$", "", line)
        if not code.strip():
            continue
        for word in set(re.findall(r"\b([A-Z][A-Za-z0-9]{2,})\b", code)):
            if word in GODOT3_RENAMES and word not in known:
                add("godot3_class", i, word, "Godot 3 name -> use " + GODOT3_RENAMES[word])
        for pat, fix in GODOT3_CALLS:
            if re.search(pat, code):
                add("godot3_api", i, pretty_pattern(pat), fix)
        # Class.member on a known class: verify the member exists somewhere in
        # its ancestry. High precision, so worth failing on.
        for cname, mname in re.findall(r"\b([A-Z][A-Za-z0-9]*)\.([a-z_][A-Za-z0-9_]*)\s*\(", code):
            if cname not in known or mname in BUILTIN_PSEUDO:
                continue
            found = False
            for owner in ancestry(idx, cname):
                c = known[owner]
                if mname in c["methods"] or mname in c["properties"] or mname in c["signals"]:
                    found = True
                    break
            if not found:
                cands = [m for owner in ancestry(idx, cname)
                         for m in known[owner]["methods"] if mname[:4].lower() in m.lower()]
                add("unknown_member", i, cname + "." + mname,
                    "not on %s or its bases%s" % (cname, ("; did you mean: " + ", ".join(cands[:4])) if cands else ""))
    ok = not findings
    emit("scan", {"ok": ok, "file": str(path), "findings": findings})
    if ok:
        print("clean: no Godot-3-isms or unknown symbols in " + path.name)
    else:
        for f in findings:
            print("  %s:%d  [%s] %s\n        -> %s"
                  % (path.name, f["line"], f["kind"], f["symbol"], f["detail"]))
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gddoc", description="local Godot 4.7 API reference")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("index", help="build/refresh the symbol index")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser("class", help="signatures for a class")
    p.add_argument("name")
    p.add_argument("--full", action="store_true", help="include descriptions")
    p.set_defaults(fn=cmd_class)

    p = sub.add_parser("member", help="exact signature + description for Class.member")
    p.add_argument("target")
    p.set_defaults(fn=cmd_member)

    p = sub.add_parser("search", help="find classes and members by keyword")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("exists", help="is this a real class in this build?")
    p.add_argument("name")
    p.set_defaults(fn=cmd_exists)

    p = sub.add_parser("scan", help="flag Godot-3-isms and unknown symbols in a .gd file")
    p.add_argument("file")
    p.set_defaults(fn=cmd_scan)

    sub.add_parser("stats", help="what the index contains").set_defaults(fn=cmd_stats)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
