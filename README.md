# Gatekeeper

A spec-driven, context-engineered system for building games with **Godot** and
**Blender**, using [Claude Code](https://claude.com/claude-code).

It is named for what it does. Every step of a game build here ends at a gate
that was written *before* the work started, and nothing moves forward until the
gate is green: the loop is proven playable before art exists, a generator that
does not measure itself fails, a colour outside the palette raises, and the
agent that built a thing is structurally forbidden from judging it.

Install it once, use it in every project. Nothing is hardcoded — `gd setup`
finds your engines wherever they live, on Windows, macOS or Linux.

```bash
git clone https://github.com/PageMastr/Gatekeeper.git
cd Gatekeeper
python install.py
```

Then, in any directory, in Claude Code:

```
/gd:new   a snowbound cabin at night, one fire, something out there
/gd:run
```

**New here? [`QUICKSTART.md`](QUICKSTART.md)** walks through it in five minutes.

---

## What problem this solves

Ask a capable model to "build me a game" and you reliably get one of two
outcomes: a folder of rooms with nothing to do in them, or a pile of code that
runs and is not fun. Both failures share a cause — nothing in the loop can tell
the difference between *correct* and *good*, and nothing forces the question
"is this actually a game yet?" to be answered early, while changing your mind is
still cheap.

Gatekeeper is the structure that forces those questions, mechanically:

- **The whole game is proven on grey boxes before any art exists.** Every space
  at real distances, every system running, the loop closing, and a reachable way
  to lose. The tooling refuses asset work until that is done and a human has
  played it.
- **One job, one fresh session, one gate written first.** A session carrying
  nine other jobs reads more, holds more, and makes more mistakes — and when it
  fails you cannot tell which of the ten things broke.
- **A builder never grades its own work.** Screenshots go to a critic that has
  never seen the code, because a builder sees what it intended.
- **Assets are Python scripts, not `.blend` files.** When the roof is wrong you
  fix one line and re-run it. Nothing is hand-modelled, so everything is
  reviewable, diffable and re-runnable.
- **GDScript is type-checked against your actual engine build** before anything
  claims to work. Most models learned Godot 3; Godot 4 renamed half the API, so
  recalled code looks right and fails at runtime.

It borrows its structural idea — persistent contracts, one-job-one-fresh-context,
a gate before you move on — from [GSD Core](https://github.com/open-gsd/gsd-core),
and rebuilds the loop around how games actually get made.

---

## The loop

Software's Discuss → Plan → Execute → Verify → Ship is the right shape when
"done" means the tests are green. Games have two failure modes that loop cannot
see:

1. **A game can pass every test and still not be a game.** No assertion catches
   "there is no reason to press start."
2. **A game can be correct and look wrong.** "This room is too dark" is a real
   defect and invisible to any test suite.

So there are seven beats, and the two extra ones exist to catch exactly those:

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

In practice it is two commands per stage: `/gd:plan`, then `/gd:run`.

### How autonomous is it?

`/gd:run` dispatches waves of agents in parallel with fresh contexts, grades
every gate itself, escalates a failing job up the model ladder, and commits per
job. It stops in exactly three situations:

| it stops when | because |
|---|---|
| the phase gate goes green | a human decides whether the loop is worth playing twice — no assertion replaces that |
| it hits a one-way door | animation approach, coordinate scale, streaming model. Taken inside a parallel wave, you find out four jobs later |
| a job exhausts the model ladder | 3 attempts each at its tier, the next, and the top. Nine failures means the **job or its gate** is wrong, not the model |

The state machine lives in `gd run`, not in a prompt: wave order, checkpoints
and the escalation ladder are all in `RUN.json`, so a run survives Ctrl+C, a
crash, or a `/clear` — `/gd:run` picks up exactly where it stopped.

---

## Install

**Requirements:** Python 3.10+, Godot 4.4+ (an editor build), Blender 4.0+, git,
and Claude Code.

No Godot source checkout is needed — a release download from
[godotengine.org](https://godotengine.org) is enough.

```bash
python install.py             # copy into ~/.claude, then run the setup wizard
python install.py --link      # symlink instead, so repo edits take effect live
python install.py --dry-run   # show what it would do
python install.py --uninstall # remove it (--purge also drops the machine config)
```

The installer ends by running **`gd setup`**, which searches your machine for
Godot and Blender, verifies each by actually running it, prefers the Windows
`.console` build, and asks only for what it could not find. Re-run it any time:

```bash
gd setup                                   # detect and record
gd setup --show                            # what is recorded
gd setup --godot <path> --blender <path>   # if autodetection misses
```

It places:

| | |
|---|---|
| `~/.claude/gatekeeper/` | the system — shipped config, templates, lib, harness, `bin/gd.py`, `bin/gddoc.py`, references |
| `~/.claude/commands/gd/` | the slash commands |
| `~/.claude/agents/` | the agents |
| `~/.claude/skills/godot-api/` | the API-lookup skill |
| `~/.claude/settings.json` | two permissions **merged in** — your existing settings are preserved and backed up to `settings.json.gd-backup` |
| `~/.claude/gatekeeper.machine.json` | **your** Godot and Blender paths. Written by `gd setup`, **never touched by install** |
| `~/.claude/gatekeeper-cache/` | the generated API index, keyed by engine build |

The last two sit *beside* the install rather than inside it, because
`install.py` replaces the payload wholesale. An upgrade that silently unset your
engine path would be indistinguishable from a broken release.

Commands and agents are **rewritten on the way in**: every
`python gatekeeper/bin/…` becomes an absolute path, and every
`@gatekeeper/references/…` include becomes an explicit read of an absolute path.
Relative paths only resolve when the cwd happens to be this repo, which is
exactly what a user-scope install is not.

### Nothing is hardcoded

Three config layers, lowest precedence first:

| # | file | holds | lifetime |
|---|---|---|---|
| 1 | `~/.claude/gatekeeper/config.json` | shipped defaults: budget, playtest defaults, model routing. **No paths** | replaced on every upgrade |
| 2 | `~/.claude/gatekeeper.machine.json` | this machine's Godot and Blender | written by `gd setup` |
| 3 | `<your game>/.planning/config.json` | that game's numbers | lives in the game's repo |

`gd config` prints all three and which layer each value came from.
`GD_GODOT` / `GD_BLENDER` / `GD_GODOT_SOURCE` override on top, per shell.

The API index comes from the engine's own class reference — read from a source
tree if you have one, and otherwise generated straight from the binary with
`godot --doctool`. Either way it matches the build you are actually running,
which is the whole point.

### One install, many games

The system's directory and your game's directory are separate roots.
`.planning/` and `game/` are created in **whatever directory you are working
in**, so every game keeps its own Color Bible, Core Loop and roadmap, and the
install stays clean.

The workspace resolves in this order: `$GD_PROJECT` → the nearest ancestor
containing `.planning/` → the nearest git root → the cwd. `gd doctor` prints
both roots if you are ever unsure, and `gd init` **refuses** to scaffold a game
inside the installed system or inside this repo — the two placements that would
leak one game's contracts into every other.

Concurrent projects are safe: the install is read-only at runtime, every state
write is atomic, and `RUN.json` is locked for the read-modify-write that records
a job result — so two sessions recording into one phase cannot lose a verdict.

---

## The fifteen laws, in one line each

Full reasoning in [`gatekeeper/references/laws.md`](gatekeeper/references/laws.md).

1. **The loop comes before the look** — art on a missing loop is wasted art.
2. **Never ask for the whole game in one prompt** — one job, one fresh session.
3. **The best model plans and judges; it does not build.**
4. **Every job ends in a test written before the job starts.**
5. **Verification is measure *and* look, plus a human.**
6. **A builder never grades its own work.**
6b. **Never modify the instrument that grades you.**
7. **Assets are scripts, not files** — fix one line, run it again.
8. **The Color Bible is a contract, not a mood board.**
9. **Simple forms, lit well — never "realistic".**
10. **Lighting is the largest quality lever, and it is data.**
11. **Shadows are the bill, not lights.**
12. **Accumulating world state goes in one fixed-size image.**
13. **Isolate before you debug** — build the observation tool first.
13b. **More game means more stages, never less game.**
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
| every stage stacks forward | `gd roadmap` fails a stage that depends on a later one |
| every Core Loop beat is assigned to a stage | `gd roadmap` fails an uncovered beat |
| no placeholder ships | `gd roadmap` fails a placeholder with no replacing stage |
| a game cannot be scaffolded into the shared install | `gd init` refuses, and `gd doctor` checks the work root |
| no colour outside the Color Bible | `gdblend.mat()` raises; `Palette.get_color()` asserts; `check_palette()` fails the build |
| every asset is measured | the Blender bootstrap fails a generator that never calls `report()` |
| kit modules tile | `check_grid()` measures every bound against the snap grid |
| triangle budgets | `check_tris()` against the effective config, per asset class |
| scale applied, origin correct | `check_transforms()`, `check_origin_at_base()` |
| fps / draw calls / shadow-light count | `gd playtest` fails the verdict on budget |
| runtime script errors | scraped from the process output; they fail an otherwise-passing run |
| a run that asserted nothing is not a pass | the harness refuses to report `passed` with no evaluated checks |
| a verdict must prove it belongs to its plan | name and check-set are cross-validated; a mismatch is refused, not reported |
| no Godot 3 API | `gd check` = the engine's own analyser + a 3.x-ism scan |
| model routing has a reason | stored per agent in config; `gd models` flags drift vs agent frontmatter |
| a failing job escalates, then stops | `gd run` owns the ladder — no agent grants itself a fourth attempt |
| an incomplete plan cannot be driven | `gd run init` refuses placeholder gates, untitled jobs and unrunnable gate commands |
| a builder cannot write its own gate | `gd run init` refuses a plan that puts a playtest plan in a builder's `touches` |
| a green gate expires when the code moves | gates record a source fingerprint; a stale one is re-run, not trusted |

---

## The toolchain

Discovered per machine by `gd setup`; `gd config` prints what is in force.

| tool | minimum | notes |
|---|---|---|
| Godot | 4.4 | an **editor** build, not an export template. On Windows the `.console.exe` is preferred and auto-detected — the plain `.exe` detaches from the terminal and you get no stdout at all, which presents as a silent hang |
| Blender | 4.0 | driven headless with `-b --factory-startup`, so user add-ons cannot make one machine's asset differ from another's |
| Python | 3.10 | the CLI |
| git | any | one commit per job, so a failing job reverts alone |

The pipeline, end to end:

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
  settings.json              permissions
gatekeeper/
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

in YOUR game's directory, never here:
  .planning/                 that game's contracts, incl. its config.json
  game/<slug>/               the Godot project

beside the install, never inside it:
  ~/.claude/gatekeeper.machine.json    this machine's engine paths (gd setup)
  ~/.claude/gatekeeper-cache/          the API index, keyed by engine build
```

---

## Commands

| | |
|---|---|
| `/gd:new` | **first command on a new game** — toolchain, scaffold, then kickoff |
| `/gd:plan` | kickoff interview, or the next stage from the roadmap |
| `/gd:run` | **drive the stage** — waves, grading, escalation, to the gate |
| `/gd:frame` | revisit the contracts alone, without re-planning |
| `/gd:greybox` | prove the whole game in grey, across as many stages as it takes |
| `/gd:build` | run the next wave, fresh context per job |
| `/gd:gauntlet` | candidates + independent critic + numeric vetoes, until good |
| `/gd:playtest` | measure, look, budget |
| `/gd:ship` | gates, licences, budget snapshot, learnings |
| `/gd:asset` | one Blender asset end to end |
| `/gd:lab` | isolate one system and watch what it really does |
| `/gd:light` | author/tune lighting presets |
| `/gd:perf` | triage a frame-rate drop in cost order |
| `/gd:api` | exact signatures from your engine build, or check a `.gd` file |
| `/gd:status` · `/gd:next` · `/gd:help` | where am I / what next / what is this |

---

## Contributing

Issues and pull requests are welcome. Two things worth knowing before you open
one:

- **The harness is the instrument that grades every build.** A change to
  `gatekeeper/harness/` changes how every project on every machine is judged, so
  it gets reviewed like a change to a test framework — with the failure it fixes
  described, and ideally reproduced.
- **Doctrine changes want evidence.** The references are written from builds that
  actually ran; the most useful contribution is "here is what the system got
  wrong under load, with the line number", which is how most of the current
  rules got there.

`python install.py --link` symlinks the payload instead of copying it, so repo
edits take effect immediately while you work.

---

## Status

Working and in use, but young. The system is well tested at the start of a
game — contracts, roadmap validation, the greybox block, the playtest harness —
and less exercised in the middle of one, where the asset, lighting and
performance stages live. Expect sharper edges there, and please file what you
find.

## Licence

[MIT](LICENSE).
