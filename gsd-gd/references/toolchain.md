# Toolchain

Verified on this machine, 2026-09-12. Paths live in `gsd-gd/config.json`; never
hardcode them anywhere else.

| tool | path | version |
|---|---|---|
| Godot editor | `D:/Godot/GodotEngine/bin/godot.windows.editor.x86_64.exe` | 4.7.2-rc (custom build c5198ffd3) |
| Godot console | `D:/Godot/GodotEngine/bin/godot.windows.editor.x86_64.console.exe` | same binary, console subsystem |
| Godot source | `D:/Godot/GodotEngine` | for reading engine source when docs are ambiguous |
| Blender | `D:/Program Files/Blender Foundation/Blender 5.1/blender.exe` | 5.1.2, bundled Python 3.13.9 |
| Python | system | 3.14.4 |
| git | system | 2.55.0 |

## Rule 1: always use the `.console.exe` on Windows

The plain `godot.windows.editor.x86_64.exe` is a *windowed-subsystem* binary. It
detaches from the terminal, so an agent invoking it gets **no stdout at all** and
sits there waiting. Every invocation from this system goes through the
`.console.exe`. `gd doctor` checks for it.

## Rule 2: this is a source build, so there are no export templates

`D:/Godot/GodotEngine/bin` contains editor binaries plus the debug/release
templates that were built alongside (Windows x86_64 and Web wasm32). Exporting
is therefore possible, but only to those platforms, and `export_presets.cfg`
must point at the template paths in `bin/` rather than at downloaded templates.

## Godot invocations

Everything below is wrapped by `gd`; these are the underlying commands for when
you need to do something the CLI does not cover.

```bash
G="D:/Godot/GodotEngine/bin/godot.windows.editor.x86_64.console.exe"

# Reimport assets after a generator has written a new .glb. Required - Godot
# will not see the file otherwise.
"$G" --headless --path <proj> --import

# Run a SceneTree script with no rendering (fast; good for data/logic probes).
"$G" --headless --path <proj> --script res://tools/probe.gd

# Run a scene for real, off-screen. THIS is what the LOOK pass needs: --headless
# uses the dummy renderer and cannot produce a screenshot.
"$G" --path <proj> --resolution 1280x720 --position 9000,9000 \
     --quit-after 4800 res://addons/gd_harness/gd_playtest.tscn -- --plan=...
```

**`--headless` cannot screenshot.** The dummy rendering driver has no framebuffer
to read back. To capture frames you must run a real window; `--position 9000,9000`
puts it off the visible desktop, which works and still renders (verified: Vulkan
1.4.341, RTX 3050).

**Always pass `--quit-after`.** If the harness script fails to parse, no GDScript
runs, nothing calls `quit()`, and the process hangs until something kills it.
`gd playtest` always sets it.

## Blender invocations

```bash
B="D:/Program Files/Blender Foundation/Blender 5.1/blender.exe"

# Always -b (background) and --factory-startup (no user prefs, no addons, so the
# result is the same on every machine).
"$B" -b --factory-startup --python <script.py> -- <args...>
```

`gd blender` / `gd asset` wrap this and add `gdblend` to `sys.path` via
`gsd-gd/harness/blender/bootstrap.py`, which also guarantees that a generator
which crashes or forgets to report still emits one machine-readable line.

## Verified pipeline

This end-to-end path is tested and working:

```
generator.py  --(blender -b)-->  asset.glb  --(godot --import)-->  .scn  --(gd playtest)-->  verdict.json + shots/*.png
```

## Engine gotchas found the hard way on this build

- **Never hand-write a `uid://...`** in a `.tscn`. An invalid UID crashes the
  headless importer. Omit the `uid=` attribute and let Godot assign one.
- **A property setter must not be re-entered.** `apply_preset()` assigning
  `preset`, whose setter calls `apply_preset()`, is unbounded recursion. It
  hard-crashes the process with `0xC0000005` / `CrashHandlerException` and **no
  GDScript stack trace** — so it looks like an engine bug. If you see an access
  violation with no script error, look for a setter that calls itself.
- **Avoid `@tool` on anything that mutates rendering state in `_ready()`.** It
  runs during `--import`, in a process with no real renderer, on every asset
  reimport. Editor preview is not worth a pipeline that crashes.
- **Type inference through `Array.duplicate()` fails.** `var s := arr.duplicate()`
  gives an untyped Array, and `var x := s[0]` is then a parse error
  ("cannot infer the type"). Annotate: `var s: Array[float] = arr.duplicate()`.
- **Do not name a local `name` in a Node subclass.** It shadows `Node.name`.
- **`Input.parse_input_event()` is deferred** — the state is not visible on the
  same frame. For synthetic input use `Input.action_press()` /
  `action_release()`, which apply immediately. This is why playtest plans press
  *actions*, never keycodes.
- **With vsync off, a frame count is not a duration.** The process runs at
  ~1500 fps, so 120 frames is 80 ms of game time and every movement assertion
  fails for reasons unrelated to the game. The harness pins steps to 60 fps
  (`STEP_FPS`) and only lifts the cap for the perf window.
