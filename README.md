# GSD-GameDev

A spec-driven, context-engineered system for building games with **Godot 4.7**
and **Blender 5.1**, using Claude Code.

It takes the structural idea from [GSD Core](https://github.com/open-gsd/gsd-core)
— persistent contracts, one-job-one-fresh-context, a gate before you move on —
and rebuilds the loop around how games actually get made: the loop before the
look, assets as scripts, and a judge who never saw the code.

---

## Why the loop is not GSD's loop

GSD Core's loop is Discuss → Plan → Execute → Verify → Ship. That is the right
shape for software where "done" means the tests are green.

Games have two extra failure modes that loop cannot see:

1. **A game can pass every test and still not be a game.** The characteristic
   death of an AI-built game is a folder of beautiful rooms with no reason to
   press start. No assertion catches that.
2. **A game can be correct and look wrong.** "This room is too dark" is a real
   defect, and it is invisible to any test suite.

So this system has seven beats, not five, and the two extra ones exist
specifically to catch those:

```
 frame  →  plan  →  greybox  →  build  →  gauntlet  →  playtest  →  ship
   │                   │                     │            │
   │                   │                     │            └─ measure AND look
   │                   │                     │               (a critic that
   │                   │                     │                never saw the code)
   │                   │                     └─ candidates + an independent
   │                   │                        judge + numeric vetoes,
   │                   │                        looping until it is good
   │                   └─ ONE WHOLE TURN of the loop, playable in grey,
   │                      including a way to lose — before any art exists
   └─ contracts first: the reference, the Color Bible, the Core Loop, Minute One
```

Other deliberate departures from GSD Core:

| GSD Core | here | why |
|---|---|---|
| `STATE.md` + `CONTEXT.md` | those **plus** `COLOR_BIBLE.md`, `CORE_LOOP.md`, `BUDGET.md`, `CREDITS.md` | a game's contracts are visual, mechanical, numeric and legal — not just decisions |
| tests as the gate | **measure + look + perf**, and a human last | a passing test says nothing about whether a frame reads |
| reviewer agent | a **critic** that is structurally denied the code | a builder reviewing its own work sees what it intended |
| no asset pipeline | Blender generators as first-class, gated on measured geometry | assets are most of a game, and most of the risk |
| — | a **gauntlet** beat | taste needs candidates and a judge, not a better prompt |
| — | a local, version-exact **engine API reference** with a hard gate | Godot 3 recall is the single largest source of broken code |

---

## Install / verify

Nothing to install — Python 3, Godot and Blender are already here.

```bash
python gsd-gd/bin/gd.py doctor        # verify the whole toolchain
python gsd-gd/bin/gddoc.py index      # build the Godot 4.7 API index (~8s)
python gsd-gd/bin/gd.py init "My Game"
```

`init` scaffolds `game/<slug>/` with a **playable greybox** (floor, wall,
character, lighting rig, F9 debug panel), installs the playtest harness, writes
the `.planning/` contracts, and generates `Palette` from the Color Bible.

Then, in Claude Code:

```
/gd:frame   a snowbound cabin at night, one fire, something out there
```

---

## The 14 laws, in one line each

The full reasoning is in [`gsd-gd/references/laws.md`](gsd-gd/references/laws.md).

1. **The loop comes before the look** — art on a missing loop is wasted art.
2. **Never ask for the whole game in one prompt** — one job, one fresh session.
3. **The best model plans and judges; it does not build.**
4. **Every job ends in a test written before the job starts.**
5. **Verification is measure *and* look, plus a human.**
6. **A builder never grades its own work.**
7. **Assets are scripts, not files** — fix one line, run it again.
8. **The Color Bible is a contract, not a mood board.**
9. **Simple forms, lit well — never "realistic".**
10. **Lighting is the largest quality lever, and it is data.**
11. **Shadows are the bill, not lights.**
12. **Accumulating world state goes in one fixed-size image.**
13. **Isolate before you debug** — build the observation tool first.
14. **Log the licence when the asset lands.**

---

## What is actually enforced

Doctrine that is only written down gets skipped. These are mechanical:

| rule | enforced by |
|---|---|
| no asset work before the loop is proven | `/gd:build` refuses while `greybox_passed: no` |
| no colour outside the Color Bible | `gdblend.mat()` raises; `Palette.get_color()` asserts; `check_palette()` fails the build |
| every asset is measured | bootstrap fails a generator that never calls `report()` |
| kit modules tile | `check_grid()` measures every bound against the 0.25 m snap grid |
| triangle budgets | `check_tris()` against `config.json` per asset class |
| scale applied, origin correct | `check_transforms()`, `check_origin_at_base()` |
| fps / draw calls / shadow-light count | `gd playtest` fails the verdict on budget |
| runtime script errors | scraped from the process output; they fail an otherwise-passing run |
| no Godot 3 API | `gd check` = engine analyser + 3.x-ism scan |
| licences logged | `/gd:ship` cross-checks `CREDITS.md` against assets on disk |

---

## The toolchain

| tool | path | notes |
|---|---|---|
| Godot | `D:/Godot/GodotEngine/bin/godot.windows.editor.x86_64.console.exe` | 4.7.2-rc, source build. **Always the `.console.exe`** — the plain `.exe` detaches from the terminal on Windows and you get no stdout. |
| Blender | `D:/Program Files/Blender Foundation/Blender 5.1/blender.exe` | 5.1.2, driven headless with `-b --factory-startup` |

Verified end to end:

```
generator.py ──blender -b──> asset.glb ──godot --import──> .scn ──gd playtest──> verdict.json + shots/*.png
```

---

## Layout

```
CLAUDE.md                    the constitution, loaded every session
.claude/
  commands/gd/*.md           15 slash commands
  agents/*.md                9 agents, each routed to a model by role
  skills/godot-api/          the API-lookup discipline
  settings.json              toolchain permissions
gsd-gd/
  config.json                toolchain paths + budgets (the only place they live)
  bin/gd.py                  the CLI: doctor, init, state, phase, palette, check,
                             blender, asset, godot, playtest, credits, harness
  bin/gddoc.py               local Godot 4.7 reference: class, member, search,
                             exists, scan, index
  lib/gdblend/               Blender library: palette contract, grid/dim checks,
                             measurement, decimate, bevel, Godot-shaped GLB export
  harness/godot/             gd_playtest (measure+look+perf), gd_lighting_rig,
                             gd_lighting_panel
  harness/blender/           bootstrap that guarantees one machine-readable result
  templates/                 STATE, CONTEXT, COLOR_BIBLE, CORE_LOOP, BUDGET,
                             CREDITS, PLAN, JOB, ASSET_SPEC, greybox scene
  references/                laws, toolchain, godot-patterns, blender-patterns,
                             gdscript-4x, playtest-recipes, model-routing
  cache/                     the API index (generated)
.planning/                   the current game's contracts
game/<slug>/                 the Godot project
```

---

## Commands

| | |
|---|---|
| `/gd:frame` | idea → reference, Color Bible, Core Loop, Minute One |
| `/gd:plan` | milestone → one-session jobs, waves, checkpoints |
| `/gd:greybox` | prove one whole turn of the loop in grey, incl. losing |
| `/gd:build` | run the next wave, fresh context per job |
| `/gd:gauntlet` | candidates + independent critic + numeric vetoes, until good |
| `/gd:playtest` | measure, look, budget |
| `/gd:ship` | gates, licences, budget snapshot, learnings |
| `/gd:asset` | one Blender asset end to end |
| `/gd:lab` | isolate one system and watch what it really does |
| `/gd:light` | author/tune lighting presets |
| `/gd:perf` | triage a frame-rate drop in cost order |
| `/gd:api` | exact Godot 4.7 signatures, or check a `.gd` file |
| `/gd:status` · `/gd:next` · `/gd:help` | where am I / what next / what is this |
