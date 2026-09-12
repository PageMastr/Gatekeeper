# GSD-GameDev

A GSD-style, spec-driven, context-engineered system for building games with
Godot and Blender. Read this file, then `gsd-gd/references/laws.md`.

## What this repo is

- `gsd-gd/` — the system. CLI, Blender library, Godot harness, templates, doctrine.
- `.claude/` — commands (`/gd:*`), agent definitions, skills.
- `.planning/` — the contracts for the game currently being built.
- `game/<slug>/` — the Godot project itself.

## Toolchain

| tool | path |
|---|---|
| Godot 4.7.2-rc | `D:/Godot/GodotEngine/bin/godot.windows.editor.x86_64.console.exe` |
| Blender 5.1.2 | `D:/Program Files/Blender Foundation/Blender 5.1/blender.exe` |

**Always the `.console.exe`.** The plain `.exe` detaches from the terminal on
Windows and you get no stdout. Paths live in `gsd-gd/config.json` — do not
hardcode them anywhere else. Details and engine gotchas:
`gsd-gd/references/toolchain.md`.

## Drive everything through `gd`

```bash
python gsd-gd/bin/gd.py <verb>
```

| verb | does |
|---|---|
| `doctor` | verify the toolchain end to end |
| `init <name>` | scaffold a game project + `.planning/` contracts |
| `state [k] [v]` | read/write `.planning/STATE.md` |
| `phase new\|list\|current` | phase directories |
| `palette` | regenerate `res://scripts/palette.gd` from the Color Bible |
| `models` | show model routing per agent + flag config/frontmatter drift |
| `run init\|next\|record\|gate\|resolve\|status` | the phase driver's state machine |
| `check [files]` | **GDScript gate** — engine type-check + Godot-3-ism scan |
| `blender <script.py>` | run a Blender script headless with `gdblend` on path |
| `asset <generator.py>` | generator → GLB → project → reimport, gated on metrics |
| `godot import\|script` | headless engine operations |
| `playtest <plan>` | measure + look + perf, writes `verdict.json` |
| `credits <asset> <source> <license>` | append to the licence ledger |

And the local Godot 4.7 API reference:

```bash
python gsd-gd/bin/gddoc.py <verb>
```

| verb | does |
|---|---|
| `class <Name> [--full]` | every signature + the inheritance chain |
| `member <Class>.<member>` | one exact signature + docs, resolved through base classes |
| `search <keyword>` | find a class or member when you do not know the name |
| `exists <Name>` | is this class real in 4.7? |
| `scan <file.gd>` | flag Godot-3-isms with their 4.x replacement |
| `index [--force]` | rebuild the index (needed after rebuilding the engine) |

Every verb of both tools prints one `GD<VERB> {json}` line. Parse that, not the
log noise.

## How a session normally goes

```
/gd:new <idea>      new game: toolchain, scaffold, then the kickoff interview
                    -> contracts -> roadmap -> phase 1 jobs -> driver armed
/gd:run             drive the phase until the gate is green or a door blocks
```

After phase 1 the loop is `/gd:plan <next milestone>` then `/gd:run`.

`/gd:new` owns first-run setup only (toolchain check, API index, git, naming,
and a guard against clobbering existing contracts) and then invokes `/gd:plan`
for the interview — the interview is defined in one place, not two. `/gd:plan`
is context-aware: unlocked contracts means kickoff, locked means next milestone.
`/gd:run` then dispatches waves, grades every gate itself, escalates a failing
job up the model ladder, and **halts at one-way doors and at the phase gate** so
a human plays it before art starts.

Beats underneath, all still callable by hand:

`/gd:frame` → `/gd:plan` → `/gd:greybox` → `/gd:build` → `/gd:gauntlet` →
`/gd:playtest` → `/gd:ship`

Utilities: `/gd:asset`, `/gd:lab`, `/gd:light`, `/gd:perf`, `/gd:api`,
`/gd:status`, `/gd:next`, `/gd:help`.

Everything runs through the slash commands — you should never need to type a
bare `python gsd-gd/...` command yourself; the commands do it.

## Hard rules

These are enforced by tooling, not just convention. Do not work around them.

1. **The loop before the look.** `.planning/CORE_LOOP.md` first; one complete
   turn of the loop playable on grey boxes — with a reachable failure state —
   before any asset work. `/gd:build` and `/gd:run` refuse asset work while
   `greybox_passed: no`.
2. **One job, one fresh session, one gate written before the job starts.** When
   a gate fails, one job goes back — not the game.
3. **A builder never grades its own work.** Screenshots go to `gd-critic`.
4. **Assets are scripts.** Blender runs headless on Python. The script is the
   source of truth; the `.glb` is a build artifact. Never hand-edit a mesh, and
   never put an interactive Blender session in the build path.
5. **The Color Bible is a contract.** `.planning/COLOR_BIBLE.md` is the only
   source of colour. `gdblend.mat()` raises on an unknown key;
   `Palette.get_color()` asserts. No hex literals in game code or generators.
6. **Every asset reports metrics.** A generator that does not call
   `gdblend.report()` fails. Unmeasured means ungateable.
7. **Shadows are rationed.** Budget in `gsd-gd/config.json`; enforced at runtime
   by `GDLightingRig.enforce_shadows()` and at gate time by `gd playtest`.
8. **Log the licence when the asset lands**, not at ship time.
9. **Model routing lives in `config.json` → `models`**, never hardcoded. Each
   agent's starting model is stored with the reason it was chosen, and
   `gd models` flags drift against the agent frontmatter. `gd run` owns the
   escalation ladder (3 attempts per tier, then climb) — no agent may grant
   itself a fourth attempt or pick its own model.
10. **No GDScript from memory.** Most training data is Godot 3; Godot 4 renamed,
   moved and deleted much of the API, so recalled GDScript looks right and fails
   at runtime. Before writing engine code, look every type up in the local
   version-exact reference (`gddoc`, or the `godot-api` skill). Use static types
   everywhere. Then `gd check` before claiming anything works — it runs the
   engine's own analyser plus a Godot-3-ism scan, and it is a gate, not advice.

## Conventions

- 1 Godot unit = 1 metre. Modular kit snap grid = 0.25 m.
- Assets: `game/<slug>/generators/<name>.py` → `assets/models/<name>.glb`.
- Playtest plans: `game/<slug>/lab/<name>.json`.
- Test scenes: `game/<slug>/lab/`. One system, one straight line.
- Never hand-write a `uid://` in a `.tscn` — an invalid UID crashes the importer.
- Never name a local variable `name` in a `Node` subclass.
- `.gd_out/` is generated output. Not committed, safe to delete.

## Where to read more

| topic | file |
|---|---|
| The fourteen laws and why they exist | `gsd-gd/references/laws.md` |
| Exact commands, engine gotchas | `gsd-gd/references/toolchain.md` |
| Engine patterns (tracks, lighting, occlusion, gait) | `gsd-gd/references/godot-patterns.md` |
| Generator craft, kits, foliage, decimation | `gsd-gd/references/blender-patterns.md` |
| Writing playtest plans and reading verdicts | `gsd-gd/references/playtest-recipes.md` |
| Godot 4.7 API discipline and the 3.x→4.x traps | `gsd-gd/references/gdscript-4x.md` |
| Which model does which job | `gsd-gd/references/model-routing.md` |
