# Toolchain

Nothing in this system hardcodes a path to Godot or Blender. They are discovered
once per machine and recorded outside the install, so the same checkout works on
anyone's disk.

## Where the paths live

```bash
gd setup            # detect Godot and Blender, write the machine config
gd setup --show     # what is recorded
gd config           # all three layers, and which one each value came from
gd doctor           # prove the whole chain end to end
```

Three layers, lowest precedence first:

| # | file | holds | lifetime |
|---|---|---|---|
| 1 | `<install>/gatekeeper/config.json` | shipped defaults: budget, playtest defaults, model routing. **No paths.** | replaced on every upgrade |
| 2 | `~/.claude/gatekeeper.machine.json` | this machine's Godot and Blender | written by `gd setup`, never touched by `install.py` |
| 3 | `<game>/.planning/config.json` | that game's numbers | lives in the game's own repo |

Then `GD_GODOT`, `GD_BLENDER` and `GD_GODOT_SOURCE` on top, as a per-shell
escape hatch for testing against a second engine build.

A path committed to layer 1 is a path that is wrong for everyone who is not the
author, which is why the wizard writes to layer 2 instead. Layer 2 sits beside
the install rather than inside it because `install.py` replaces the payload
wholesale — an upgrade that silently unsets the engine path is indistinguishable
from a broken release.

## Requirements

| tool | minimum | why |
|---|---|---|
| Godot | 4.4 | `--check-only`, `--doctool`, `--quit-after` and the typed GDScript analyser |
| Blender | 4.0 | bundled Python, headless `-b --python`, GLTF exporter |
| Python | 3.10 | the CLI |
| git | any | one commit per job, so a failing job reverts alone |

## Always the console build, on Windows

`gd setup` prefers a `*.console.exe` when one sits beside the binary it found,
and `gd doctor` reports which is in use.

The plain Windows executable is built for the GUI subsystem: it detaches from
the terminal, so a caller gets an immediate return and **no stdout at all**.
Every parse error, every `SCRIPT ERROR`, every verdict line vanishes, and the
failure presents as a silent hang rather than as a misconfiguration. It is the
single most confusing thing this system can do to a new user.

Use an **editor** build, not an export template. A template cannot run
`--check-only`, `--doctool` or the import pass, so `gd setup` ranks templates
last even when they are in the same folder.

## The API reference does not need a source checkout

`gddoc` builds its index from the engine's own XML class reference. It gets it
one of two ways:

1. from `<source_root>/doc/classes/` and `<source_root>/modules/*/doc_classes/`,
   if `toolchain.godot.source_root` names a checkout; or
2. from `godot --headless --doctool <dir>`, which makes the binary dump the
   reference it was compiled with.

The second is the normal case: a Godot release download ships no C++ and no doc
XML. Either way the reference comes from the same build as the running engine,
which is the whole point — a stale API index is exactly the failure `gddoc`
exists to prevent.

The index is cached at `~/.claude/gatekeeper-cache/godot-api-<version>.json`, keyed
by engine build so two engines on one machine cannot serve each other's API. It
is written outside the install because the install is shared by every project
and, with `install.py --link`, is a live git checkout.

```bash
gddoc index --force     # rebuild after an engine upgrade
gddoc stats             # what the index holds
```

## Invoking the tools

Everything goes through `gd`. Agents should never construct an engine command
line themselves — the flags below are recorded so the behaviour is explainable,
not so they get typed.

```bash
gd godot import                  # headless import / reimport
gd check [files]                 # --check-only per script + Godot-3-ism scan
gd playtest <plan>               # windowed offscreen, scripted, screenshots
gd blender <script.py>           # -b --factory-startup --python, gdblend on path
gd asset <generator.py>          # generator -> GLB -> project -> reimport
```

### Engine flags that matter, and why

| flag | why |
|---|---|
| `--headless` | no window, no renderer. Measurement only — the dummy renderer **cannot screenshot**, which is why `gd playtest` is windowed by default |
| `--position 9000,9000` | renders for real but off the visible desktop, so a playtest does not steal focus |
| `--quit-after N` | engine-level backstop. If the harness script fails to parse, no GDScript runs at all and the window would sit open forever |
| `--check-only --script res://x.gd` | the analyser. Ground truth for types and identifiers — but its **exit code is 0 even on a parse error**, so the output must be read, not the return value |
| `--import` | rebuilds the global class cache. Without it a cross-file `class_name` reads as "identifier not declared" on perfectly correct code |
| `--doctool <dir>` | dumps the compiled-in class reference as XML |

### Blender

`gd blender` runs `-b --factory-startup --python <bootstrap> -- <script>` with
`gdblend` on the path and the **effective project config** in the environment,
so a generator's snap grid and triangle budgets come from that game rather than
from a machine default.

`--factory-startup` is not optional: user add-ons and preferences would make one
machine's output differ from another's, and an asset that only builds on one
person's Blender is not a build artifact.

## Gotchas worth remembering

- **`--check-only` returns before autoloads register.** A reference to an
  autoload singleton reports "identifier not found" on code that is correct at
  runtime. `gd check` reads `project.godot` and forgives declared autoload names
  — real unknown types are still caught, because the global class cache *is*
  loaded in that mode. One project had already bent its architecture into a
  static-accessor workaround before this was found.
- **The global class cache goes stale silently.** Any `.gd` newer than
  `.godot/global_script_class_cache.cfg` is absent from it, producing "could not
  find type X" on a type that exists. `gd check` and `gd playtest` reimport when
  they detect it.
- **Never hand-write a `uid://` in a `.tscn`.** An invalid UID crashes the
  importer.
- **Never name a local variable `name` in a `Node` subclass.** It shadows the
  property and the error is reported far from the cause.
- **A `.tscn` handed to `--check-only --script` reports no error**, because it is
  not a script. `gd check` extracts scene-embedded GDScript and checks that
  separately; a scene that silently "passes" is a false pass.
