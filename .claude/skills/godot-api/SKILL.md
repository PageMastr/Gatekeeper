---
name: godot-api
description: Look up exact Godot 4.7 GDScript API signatures in the local, version-exact class reference, and verify written GDScript against the engine's own analyser. Use this BEFORE writing or editing any GDScript, .tscn, or Godot engine code, and whenever you are about to name a Godot class, method, property, signal or constant. Also use when GDScript fails at runtime, a method "does not exist", a node type is not found, or code that looks correct silently does nothing — these are the symptoms of Godot 3 API recall.
---

# Godot 4.7 API lookup

**Do not write Godot code from memory.** Most training data is Godot 3. Godot 4
renamed, moved and deleted a large part of the API, so recalled GDScript is
wrong in a way that looks right: plausible names, no syntax error, fails at
runtime or silently does nothing.

The exact signatures for the exact engine build on this machine
(`4.7.2-rc custom_build c5198ffd3`) are indexed locally from the engine's own
source tree. Looking one up costs one tool call.

## Before you write

```bash
python gsd-gd/bin/gddoc.py class <Type>             # every signature + inheritance chain
python gsd-gd/bin/gddoc.py class <Type> --full      # with descriptions
python gsd-gd/bin/gddoc.py member <Class>.<member>  # one exact signature + docs
python gsd-gd/bin/gddoc.py search <keyword>         # when you don't know the name
python gsd-gd/bin/gddoc.py exists <Name>            # is this class real in 4.7?
```

Look up **every** type you are about to touch — not just the unfamiliar ones.
The familiar ones are where Godot 3 recall hides, because you are confident.

`member` resolves through the inheritance chain and tells you where a member is
really declared. On a miss it suggests near names, which is usually the answer:

```
$ python gsd-gd/bin/gddoc.py member Input.action_pres
NOT FOUND: action_pres on Input (or bases: Object)
did you mean: action_press, is_action_pressed
```

## While you write

**Use static types everywhere.** `var body: CharacterBody3D = ...`, typed
parameters, typed returns, `Array[float]` not `Array`. The engine's analyser can
only catch mistakes on typed values — untyped code opts out of the one tool that
would have caught the error.

## After you write, before you claim it works

```bash
python gsd-gd/bin/gd.py check <file.gd>     # or with no args: every .gd in the project
```

Two passes, because neither alone is enough:

1. **The engine's own analyser** (`godot --check-only`) — ground truth on types,
   unknown identifiers and signatures. It even suggests the Godot 4 replacement
   name for a Godot 3 class.
2. **`gddoc scan`** — the 3.x idioms the analyser accepts on untyped receivers
   (`change_scene`, `OS.get_ticks_msec`, `yield`, `export var`, `setget`,
   `move_and_slide(velocity)`, the three-argument `connect`), each reported with
   its 4.x replacement.

`godot --check-only` **exits 0 even on a parse error** — never gate on its exit
code. `gd check` parses its output, which is why you call `gd check` rather than
the binary.

A red gate is not a nit. Look the symbol up and fix it properly; do not guess a
second time.

## The traps, in short

| you might write | 4.7 wants |
|---|---|
| `Spatial`, `KinematicBody`, `Area`, `Camera`, `Sprite` | `Node3D`, `CharacterBody3D`, `Area3D`, `Camera3D`, `Sprite2D` |
| `OS.get_ticks_msec()` | `Time.get_ticks_msec()` |
| `move_and_slide(velocity)` | assign `velocity`, then `move_and_slide()` |
| `scene.instance()` | `scene.instantiate()` |
| `get_tree().change_scene(p)` | `get_tree().change_scene_to_file(p)` |
| `connect("pressed", self, "_on")` | `pressed.connect(_on)` |
| `yield(...)` | `await ...` |
| `export var`, `onready`, `setget` | `@export var`, `@onready`, a property block |
| `deg2rad`, `stepify`, `rand_range` | `deg_to_rad`, `snappedf`, `randf_range` |
| `Directory`, `File`, `VisualServer` | `DirAccess`, `FileAccess`, `RenderingServer` |

Full list, plus the traps the analyser cannot catch (type inference through
`duplicate()`, shadowing `name`, re-entrant setters, `@tool` during `--import`,
hand-written `uid://`): `gsd-gd/references/gdscript-4x.md`.

## When the docs are ambiguous

The full C++ source is at `toolchain.godot.source_root` **if this machine has a
checkout** (`gd config` prints it; blank means none) — the same tree the binary was
built from, so it is authoritative. Grep the implementation:

```bash
grep -rn "move_and_slide" "$SOURCE_ROOT/scene/3d/physics/character_body_3d.cpp"
```

## If the index is missing

```bash
python gsd-gd/bin/gddoc.py index          # 8s, 1071 classes
python gsd-gd/bin/gddoc.py index --force  # after upgrading or rebuilding the engine
```
