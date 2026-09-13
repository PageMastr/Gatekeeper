---
description: What this system is and which command to reach for
allowed-tools: Read, Bash, Glob
---

# /gd:help

Read `CLAUDE.md` and `gatekeeper/references/laws.md`, then answer the user's
question directly. If they asked nothing specific, give them this — and if they
are new to the system, point them at `QUICKSTART.md` first:

## Once per machine

```bash
gd setup                     find Godot and Blender and record them. Writes
                             ~/.claude/gatekeeper.machine.json, which no upgrade
                             touches. `gd setup --show` prints what it found.
gd doctor                    prove the whole chain, and print which directory
                             this game will live in
```

Nothing in the system hardcodes an engine path. `gd config` shows all three
layers — shipped defaults, this machine's toolchain, this game's overrides — and
which one each value came from.

## Start here

```
/gd:new   <your idea>        brand new game: checks the toolchain, scaffolds the
                             project, then runs the kickoff interview
/gd:run                      builds until the phase gate is green, or until it
                             hits a one-way door and needs your decision
```

`.planning/` and `game/` are created in the directory you are working in, so one
install drives as many separate games as you like without them touching.

After the first phase, the loop is two commands:

```
/gd:plan  <next milestone>   decompose it into one-session jobs, arm the driver
/gd:run                      drive it to the gate
```

Everything else is for steering a specific part by hand.

## The beat loop underneath

```
 frame  ->  plan  ->  greybox  ->  build  ->  gauntlet  ->  playtest  ->  ship
   \_________/          |            |           |            |             |
   /gd:plan at       THE WHOLE     parallel   candidates+   measure+look   gates,
   kickoff does      GAME in grey, waves,     independent   +budget        licences,
   both, + roadmap   over N stages fresh ctx  critic, loops +human         learnings
                          \____________/____________/
                            /gd:run drives these autonomously
```

**The greybox is a block of stages, not one phase.** Its job is the entire game
in grey — every space at real distances, every system running, the loop closing,
a way to lose — and that is usually more than one phase holds. The roadmap sizes
the block to the game: one stage for something small, six for something large.
Art is refused by `gd run init` until the last one clears and you have played it.

| command | when |
|---|---|
| `/gd:new` | **first command on a new game.** Toolchain, scaffold, then the kickoff interview |
| `/gd:plan` | kickoff interview (if not already done) or the next milestone from the roadmap |
| `/gd:run` | **drive the phase** — waves, grading, escalation, until the gate is green or a door blocks |
| `/gd:frame` | the contracts alone need revisiting, without re-planning |
| `/gd:greybox` | the loop is not yet playable in grey |
| `/gd:build` | run one wave by hand |
| `/gd:gauntlet` | one hard or aesthetic thing needs candidates + a judge |
| `/gd:playtest` | verify: measure, look, budget |
| `/gd:ship` | close the phase honestly |
| `/gd:asset` | build one Blender asset end to end |
| `/gd:lab` | isolate one system to see what it is really doing |
| `/gd:light` | author or tune lighting presets |
| `/gd:perf` | the frame rate dropped |
| `/gd:api` | look up an exact Godot 4.7 signature, or check a .gd file |
| `gd models` | see which model each agent starts on, and why |
| `/gd:status` | where is everything |
| `/gd:next` | just tell me the next action |

## The CLI underneath

`python gatekeeper/bin/gd.py <verb>` - doctor, init, state, phase, palette, models,
run, check, blender, asset, godot, playtest, credits, harness.
`python gatekeeper/bin/gddoc.py <verb>` - index, class, member, search, exists, scan, stats.

Every verb prints one `GD<VERB> {json}` line; parse that, not the log noise.

## The rules that are actually enforced

- `/gd:build` refuses asset work while `greybox_passed: no`
- `gd asset` fails on palette, dimension, grid and triangle-budget violations
- `gd playtest` fails on checks, budgets, *and* runtime script errors
- `gd check` fails on engine type errors and Godot-3 API use
- a generator that never calls `gdblend.report()` fails
- screenshots go to `gd-critic`, never to the agent that built the thing
- `/gd:run` halts at every one-way door, and at the phase gate so you can play it
- a failing job escalates 3 attempts per model tier, then stops - `gd run` owns
  that ladder, so no agent can talk itself into a fourth attempt
