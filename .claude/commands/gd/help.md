---
description: What this system is and which command to reach for
allowed-tools: Read, Bash, Glob
---

# /gd:help

Read `CLAUDE.md` and `gsd-gd/references/laws.md`, then answer the user's
question directly. If they asked nothing specific, give them this:

## Start here

```
/gd:plan  <your idea>        interviews you, writes the contracts + roadmap,
                             decomposes phase 1, arms the driver
/gd:run                      builds until the phase gate is green, or until it
                             hits a one-way door and needs your decision
```

Two commands per phase is the normal loop. Everything else is for when you want
to steer a specific part by hand.

## The beat loop underneath

```
 frame  ->  plan  ->  greybox  ->  build  ->  gauntlet  ->  playtest  ->  ship
   \_________/          |            |           |            |             |
   /gd:plan at       loop proven   parallel   candidates+   measure+look   gates,
   kickoff does      in grey,      waves,     independent   +budget        licences,
   both, + roadmap   incl. losing  fresh ctx  critic, loops +human         learnings
                          \____________/____________/
                            /gd:run drives these autonomously
```

| command | when |
|---|---|
| `/gd:plan` | **the entry point.** Kickoff (interview + contracts + roadmap) or the next milestone |
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

`python gsd-gd/bin/gd.py <verb>` - doctor, init, state, phase, palette, models,
run, check, blender, asset, godot, playtest, credits, harness.
`python gsd-gd/bin/gddoc.py <verb>` - index, class, member, search, exists, scan, stats.

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
