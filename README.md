# GSD-GameDev

A spec-driven, context-engineered system for building games with **Godot** and
**Blender**, using Claude Code.

Install it once, use it in every project. Nothing is hardcoded: `gd setup` finds
your engines wherever they live, on Windows, macOS or Linux.

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
   │                   └─ the WHOLE GAME playable in grey — every space, every
   │                      system, the loop closing, a way to lose — across as
   │                      many stages as it takes, before any art exists
   └─ contracts first: the reference, the Color Bible, the Core Loop, Minute One

   \_______________/          \_____________________________________/
    /gd:plan at kickoff        /gd:run drives these autonomously, halting at
    does both, + roadmap       one-way doors and at the phase gate
```

Other deliberate departures from GSD Core:

| GSD Core | here | why |
|---|---|---|
| `STATE.md` + `CONTEXT.md` | those **plus** `COLOR_BIBLE.md`, `CORE_LOOP.md`, `ROADMAP.md`, `BUDGET.md`, `CREDITS.md` | a game's contracts are visual, mechanical, numeric and legal — not just decisions |
| a phase roadmap | a **validated** stage roadmap: per-stage targets and pass conditions, a systems inventory, a levels table, a coverage matrix, a placeholder ledger | "the whole game gets built" has to be a check, not an intention |
| tests as the gate | **measure + look + perf**, and a human last | a passing test says nothing about whether a frame reads |
| reviewer agent | a **critic** that is structurally denied the code | a builder reviewing its own work sees what it intended |
| no asset pipeline | Blender generators as first-class, gated on measured geometry | assets are most of a game, and most of the risk |
| — | a **gauntlet** beat | taste needs candidates and a judge, not a better prompt |
| — | a local, version-exact **engine API reference** with a hard gate | Godot 3 recall is the single largest source of broken code |

---

## Install

Requires Python 3.10+, Godot 4.4+, Blender 4.0+ and git. Then, to use `/gd:*`
from **any** Claude Code session, in any directory:

```bash
python install.py             # copy into ~/.claude, then run the setup wizard
python install.py --link      # junction gsd-gd/ instead, so repo edits take effect live
python install.py --dry-run   # show what it would do
python install.py --uninstall
```

The installer ends by running **`gd setup`**, which searches this machine for
Godot and Blender, verifies each by running it, prefers the Windows `.console`
build (the plain `.exe` detaches from the terminal and you lose all stdout), and
asks only for what it could not find. Re-run it any time:

```bash
gd setup                      # detect and record
gd setup --show               # what is recorded
gd setup --godot <path> --blender <path>
```

It places:

| | |
|---|---|
| `~/.claude/gsd-gd/` | the system — shipped config, templates, lib, harness, `bin/gd.py`, `bin/gddoc.py`, references |
| `~/.claude/commands/gd/` | the slash commands |
| `~/.claude/agents/` | the agents |
| `~/.claude/skills/godot-api/` | the API-lookup skill |
| `~/.claude/settings.json` | two permissions **merged in** — your existing settings are preserved and backed up to `settings.json.gd-backup` |
| `~/.claude/gsd-gd.machine.json` | **your** Godot and Blender paths. Written by `gd setup`, **never touched by install** |
| `~/.claude/gsd-gd-cache/` | the generated API index, keyed by engine build |

The last two sit *beside* the install rather than inside it, because
`install.py` replaces the payload wholesale. An upgrade that silently unset your
engine path would be indistinguishable from a broken release.

### Nothing is hardcoded

Three config layers, lowest precedence first:

| # | file | holds | lifetime |
|---|---|---|---|
| 1 | `~/.claude/gsd-gd/config.json` | shipped defaults: budget, playtest defaults, model routing. **No paths** | replaced on every upgrade |
| 2 | `~/.claude/gsd-gd.machine.json` | this machine's Godot and Blender | written by `gd setup` |
| 3 | `<your game>/.planning/config.json` | that game's numbers | lives in the game's repo |

`gd config` prints all three and which one each value came from.
`GD_GODOT` / `GD_BLENDER` / `GD_GODOT_SOURCE` override on top, per shell.

**No Godot source checkout required.** `gddoc` builds its API index from the
engine's own class reference — read from a source tree if you have one, and
otherwise generated straight from the binary with `godot --doctool`. A release
download works fine.

Commands and agents are **rewritten on the way in**: every `python gsd-gd/bin/…`
becomes an absolute path, and every `@gsd-gd/references/…` include becomes an
explicit read of an absolute path. Relative paths only resolve when the cwd
happens to be this repo, which is exactly what a user-scope install is not.

### One install, many games

`SYS_DIR` (where the system lives) and `WORK` (where your game lives) are
separate. `.planning/` and `game/` are created in **whatever directory you are
working in** — so every game keeps its own Color Bible, Core Loop and roadmap,
and the install stays clean.

`WORK` resolves in this order: `$GD_PROJECT` → the nearest ancestor containing
`.planning/` → the nearest git root → the cwd. `gd doctor` prints both roots if
you are ever unsure which is which, and `gd init` **refuses** to scaffold a game
inside the installed system or inside this repo — the two placements that would
leak one game's contracts into every other.

Concurrent projects are safe: the install is read-only at runtime, every state
write is atomic, and `RUN.json` is locked for the read-modify-write that records
a job result — so two sessions recording into one phase cannot lose a verdict.

Project scope still wins where it exists, so this repo keeps using its own
`.claude/` copies — handy for changing the system without disturbing the
installed one.

## Getting started

**New here? Read [`QUICKSTART.md`](QUICKSTART.md)** — four commands and what each
one does.

Nothing else to install — Python 3, Godot and Blender are already here. In
Claude Code, two commands per phase is the whole loop:

```
/gd:new  a snowbound cabin at night, one fire, something out there
```

Verifies the toolchain, builds the local Godot API index, scaffolds the Godot
project with a **playable greybox** already in it, proves the scaffold's gates
pass — then interviews you properly: the reference, the loop and its four beats,
the tension and the failure state, **every system and what it does to the loop**,
**every space and its size in metres**, the session shape, the one-way doors and
the lighting condition. Then it writes the contracts and the roadmap, decomposes
the first stage into one-session jobs, and arms the driver.

It never asks you to cut a feature. If the game is large, the roadmap gets more
stages — that is what it is for.

```
/gd:run
```

Drives the phase: dispatches waves of agents in parallel with fresh contexts,
grades every gate itself, escalates a failing job up the model ladder, commits
per job — and **halts at one-way doors and at the phase gate** so you play it
before any art gets made. It refuses asset work outright until the greybox block
is finished and a person has played it.

Then `/gd:playtest` for the human pass and `/gd:ship` to close the phase. After
that the loop is `/gd:plan <next milestone>` then `/gd:run`, and `/gd:next` will
always tell you the single next action.

Every granular beat is still there (`/gd:frame`, `/gd:build`, `/gd:asset`,
`/gd:lab`, `/gd:light`, `/gd:perf`, `/gd:gauntlet`) for when you want to steer
one part by hand.

### How autonomous is it?

`/gd:run` is the autonomous layer, and it stops in exactly three situations:

| it stops when | because |
|---|---|
| the phase gate goes green | a human decides whether the loop is worth playing twice — that is Law 1, and no assertion replaces it |
| it hits a one-way door | animation approach, coordinate scale, streaming model. Taken inside a parallel wave, you find out four jobs later |
| a job exhausts the model ladder | 3 attempts each at its tier, the next, and the top. Nine failures means the **job or its gate** is wrong, not the model |

The state machine lives in `gd run`, not in a prompt: wave order, checkpoints
and the escalation ladder are all in `RUN.json`, so a run survives Ctrl+C, a
crash, or a `/clear` — `/gd:run` picks up exactly where it stopped.

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
| no asset work before the whole game is proven in grey | `gd run init` refuses a plan with `gd-modeler` jobs or `gd asset` gates until the greybox block is done **and** `greybox_passed: yes` |
| the greybox covers the whole game | `gd roadmap` fails unless every system and every space is greyboxed inside the block |
| the last greybox stage proves you can lose | `gd roadmap` fails if its pass conditions never mention losing |
| every stage has a target and pass conditions | `gd roadmap` fails a stage with no row in the targets table |
| a game cannot be scaffolded into the shared install | `gd init` refuses, and `gd doctor` checks the work root |
| no colour outside the Color Bible | `gdblend.mat()` raises; `Palette.get_color()` asserts; `check_palette()` fails the build |
| every asset is measured | bootstrap fails a generator that never calls `report()` |
| kit modules tile | `check_grid()` measures every bound against the 0.25 m snap grid |
| triangle budgets | `check_tris()` against `config.json` per asset class |
| scale applied, origin correct | `check_transforms()`, `check_origin_at_base()` |
| fps / draw calls / shadow-light count | `gd playtest` fails the verdict on budget |
| runtime script errors | scraped from the process output; they fail an otherwise-passing run |
| no Godot 3 API | `gd check` = engine analyser + 3.x-ism scan |
| model routing has a reason | stored per agent in `config.json`; `gd models` flags drift vs agent frontmatter |
| a failing job escalates, then stops | `gd run` owns the ladder — no agent grants itself a fourth attempt |
| an incomplete plan cannot be driven | `gd run init` refuses placeholder gates and untitled jobs |
| every stage stacks forward | `gd roadmap` fails a stage that depends on a later one |
| every Core Loop beat is assigned to a stage | `gd roadmap` fails an uncovered beat |
| no placeholder ships | `gd roadmap` fails a placeholder with no replacing stage |
| licences logged | `/gd:ship` cross-checks `CREDITS.md` against assets on disk |

---

## The toolchain

Discovered per machine by `gd setup`; `gd config` prints what is in force.

| tool | minimum | notes |
|---|---|---|
| Godot | 4.4 | an **editor** build, not an export template. On Windows the `.console.exe` is preferred and auto-detected — the plain `.exe` detaches from the terminal and you get no stdout at all, which presents as a silent hang |
| Blender | 4.0 | driven headless with `-b --factory-startup`, so user add-ons cannot make one machine's asset differ from another's |
| Python | 3.10 | the CLI |
| git | any | one commit per job, so a failing job reverts alone |

Verified end to end:

```
generator.py ──blender -b──> asset.glb ──godot --import──> .scn ──gd playtest──> verdict.json + shots/*.png
```

---

## Layout

```
CLAUDE.md                    the constitution, loaded every session
.claude/
  commands/gd/*.md           the slash commands
  agents/*.md                the agents, each routed to a model by role
  skills/godot-api/          the API-lookup discipline
  settings.json              toolchain permissions
gsd-gd/
  config.json                shipped defaults — budgets, playtest defaults, model
                             routing. No paths: those are per machine
  bin/gd.py                  the CLI: setup, doctor, init, state, phase, palette,
                             models, roadmap, run, check, blender, asset, godot,
                             playtest, config, version, credits, harness
  bin/gddoc.py               local version-exact Godot reference: class, member,
                             search, exists, scan, index
  lib/gdblend/               Blender library: palette contract, grid/dim checks,
                             measurement, decimate, bevel, Godot-shaped GLB export
  harness/godot/             gd_playtest (measure+look+perf), gd_lighting_rig,
                             gd_lighting_panel
  harness/blender/           bootstrap that guarantees one machine-readable result
  templates/                 STATE, CONTEXT, COLOR_BIBLE, CORE_LOOP, ROADMAP,
                             BUDGET, CREDITS, PLAN, JOB, ASSET_SPEC, greybox scene
  references/                laws, toolchain, decomposition, godot-patterns,
                             blender-patterns, gdscript-4x, playtest-recipes,
                             model-routing
.planning/                   the current game's contracts, incl. config.json
game/<slug>/                 the Godot project

~/.claude/gsd-gd.machine.json    this machine's engine paths (gd setup)
~/.claude/gsd-gd-cache/          the API index, keyed by engine build
```

---

## Commands

| | |
|---|---|
| `/gd:new` | **first command on a new game** — toolchain, scaffold, then kickoff |
| `/gd:plan` | kickoff interview, or the next milestone from the roadmap |
| `/gd:run` | **drive the phase** — waves, grading, escalation, to the gate |
| `/gd:frame` | revisit the contracts alone, without re-planning |
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
