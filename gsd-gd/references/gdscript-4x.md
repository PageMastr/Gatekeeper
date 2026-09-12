# GDScript 4.7 — look it up, don't recall it

**The problem this file exists for:** most models learned Godot from Godot 3
material. Godot 4 renamed, moved or deleted a large part of the API. Recalled
GDScript is therefore wrong in a specific and dangerous way — it *looks* right,
uses plausible names, and fails at runtime or silently does nothing.

**The rule: no GDScript is written from memory.** The exact signature for this
exact engine build is on this disk. Look it up. This is not a suggestion — it
is a gate, and `gd check` fails the job.

## The local reference

The engine's own XML class reference, from the same source tree the binary was
built from, so it cannot drift from the running engine:

```
D:/Godot/GodotEngine/doc/classes/*.xml            810 core classes
D:/Godot/GodotEngine/modules/*/doc_classes/*.xml  261 module classes
```

Indexed into `gsd-gd/cache/godot-api-index.json`: **1071 classes, 10 732
methods, 6 048 properties, 503 signals**.

```bash
python gsd-gd/bin/gddoc.py index                 # build/refresh (8s, once)
python gsd-gd/bin/gddoc.py class CharacterBody3D # every signature, + inheritance chain
python gsd-gd/bin/gddoc.py class Light3D --full   # with descriptions
python gsd-gd/bin/gddoc.py member Input.action_press
python gsd-gd/bin/gddoc.py search shadow          # find it when you don't know the name
python gsd-gd/bin/gddoc.py exists Spatial         # -> NO, use Node3D
python gsd-gd/bin/gddoc.py scan scripts/player.gd # flag 3.x-isms
```

`member` resolves through the inheritance chain and reports where a member is
actually declared — `CharacterBody3D.get_node` comes back as "declared on Node".
On a miss it suggests near names, which is usually the answer.

## The workflow, for any agent writing GDScript

1. **Before writing:** `gddoc class <Type>` for each type you will touch. If you
   do not know the name, `gddoc search <keyword>`.
2. **While writing:** use static types everywhere (`var x: Node3D = ...`). The
   engine's analyser can only catch mistakes on typed values — untyped code
   opts out of the one tool that would have caught you.
3. **After writing, before claiming done:**
   ```bash
   python gsd-gd/bin/gd.py check <file.gd>
   ```
   Two passes: the engine's own `--check-only` analyser (ground truth on types,
   identifiers and signatures — it even suggests the Godot 4 replacement name),
   and `gddoc scan` for the 3.x idioms the analyser accepts.
4. **A red gate is not a formatting nit.** Look the symbol up and fix it
   properly; do not guess a second time.

Note that `godot --check-only` **exits 0 even on a parse error**. Never gate on
its exit code — `gd check` parses its output, which is why you should use
`gd check` rather than calling the binary yourself.

## The traps that catch models most often

### Renamed nodes (3.x → 4.x)

`Spatial`→`Node3D`, `KinematicBody`→`CharacterBody3D`, `Area`→`Area3D`,
`MeshInstance`→`MeshInstance3D`, `Camera`→`Camera3D`, `Sprite`→`Sprite2D`,
`Position3D`→`Marker3D`, `Particles`→`GPUParticles3D`,
`SpatialMaterial`→`StandardMaterial3D`, `Reference`→`RefCounted`,
`Directory`→`DirAccess`, `File`→`FileAccess`, `VisualServer`→`RenderingServer`,
`Pool*Array`→`Packed*Array`.

The engine catches these with a helpful suggestion. `gddoc exists <Name>` answers
in one call.

### Moved functions

`OS.get_ticks_msec()` → `Time.get_ticks_msec()`. Most time functions left `OS`
for `Time`; most window/screen functions left `OS` for `DisplayServer`.
`deg2rad`→`deg_to_rad`, `stepify`→`snappedf`, `rand_range`→`randf_range`.

### Changed signatures

- **`move_and_slide()` takes no arguments.** Assign `velocity` first, then call
  it. The 3.x form passing a velocity vector is the single most common error.
- **`PackedScene.instance()` → `instantiate()`.**
- **`SceneTree.change_scene(path)` → `change_scene_to_file(path)`** (or
  `change_scene_to_packed`).
- **Signals are objects:** `button.pressed.connect(_on_pressed)`. The
  `connect("pressed", self, "_on_pressed")` three-argument form is gone
  (`connect("pressed", callable)` still works, but the object form is better).
- **`yield` → `await`.**
- **`export var` → `@export var`**, `onready` → `@onready`, `tool` → `@tool`,
  and `setget` is now a property block:
  ```gdscript
  var health: int = 100:
      set(v):
          health = clampi(v, 0, 100)
      get:
          return health
  ```

### Traps the analyser will *not* catch

- **Type inference through `Array.duplicate()` fails.** `var s := arr.duplicate()`
  yields an untyped Array and the *next* line becomes a parse error. Annotate:
  `var s: Array[float] = arr.duplicate()`.
- **Do not name a local variable `name`** in a `Node` subclass — it shadows
  `Node.name`. Same for `position`, `rotation`, `scale`, `owner`, `visible`.
- **A property setter must not be re-entered.** A function that assigns the
  property whose setter calls that function is unbounded recursion: it
  hard-crashes the process with `0xC0000005` and **no GDScript stack trace**, so
  it reads as an engine bug. If you see an access violation with no script
  error, look for a setter that calls itself.
- **`Input.parse_input_event()` is deferred** — the state is not visible on the
  same frame. For synthetic input use `Input.action_press()` /
  `action_release()`, which apply immediately.
- **`@tool` scripts run during `--import`**, in a process with no real renderer,
  on every asset reimport. Do not mutate rendering state in a `@tool` `_ready()`.
- **Never hand-write a `uid://`** in a `.tscn` — an invalid UID crashes the
  headless importer. Omit `uid=` and let Godot assign one.
- **`-Z` is forward** in 3D. `Vector3.FORWARD` is `(0, 0, -1)`.
- **Rotation properties are radians**; `rotation_degrees` is the degree view of
  the same value. Do not mix them in one calculation.

## When the docs are ambiguous, read the engine

The full C++ source is at `D:/Godot/GodotEngine`. For behaviour the XML does not
explain, grep the implementation — it is the same tree the binary came from, so
it is authoritative:

```bash
grep -rn "move_and_slide" D:/Godot/GodotEngine/scene/3d/physics/character_body_3d.cpp
```

This build is `4.7.2-rc custom_build c5198ffd3`. It is a release candidate, so
prefer the local XML and source over anything written about 4.7 elsewhere.
