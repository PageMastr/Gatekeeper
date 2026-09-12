---
description: What this system is and which command to reach for
allowed-tools: Read, Bash, Glob
---

# /gd:help

Read `CLAUDE.md` and `gsd-gd/references/laws.md`, then answer the user's
question directly. If they asked nothing specific, give them this:

## The beat loop

```
/gd:frame  -> /gd:plan -> /gd:greybox -> /gd:build -> /gd:gauntlet -> /gd:playtest -> /gd:ship
   |            |             |             |            |               |              |
contracts    one-session   loop proven   parallel    candidates +    measure+look+   gates, licences,
(reference,   jobs, each    in grey,      waves,      independent     budget, human   budget, learnings
color bible,  with a gate   incl. losing  fresh ctx   critic, loops
core loop,    written first                           until good
minute one)
```

| command | when |
|---|---|
| `/gd:frame` | a new idea, or the loop/palette needs rethinking |
| `/gd:plan` | a milestone needs breaking into one-session jobs |
| `/gd:greybox` | the loop is not yet playable in grey |
| `/gd:build` | run the next wave of jobs |
| `/gd:gauntlet` | one hard or aesthetic thing needs candidates + a judge |
| `/gd:playtest` | verify: measure, look, budget |
| `/gd:ship` | close the phase honestly |
| `/gd:asset` | build one Blender asset end to end |
| `/gd:lab` | isolate one system to see what it is really doing |
| `/gd:light` | author or tune lighting presets |
| `/gd:perf` | the frame rate dropped |
| `/gd:api` | look up an exact Godot 4.7 signature, or check a .gd file |
| `/gd:status` | where is everything |
| `/gd:next` | just tell me the next action |

## The CLI underneath

`python gsd-gd/bin/gd.py <verb>` - doctor, init, state, phase, palette, check,
blender, asset, godot, playtest, credits, harness.
`python gsd-gd/bin/gddoc.py <verb>` - index, class, member, search, exists, scan, stats.

Every verb prints one `GD<VERB> {json}` line; parse that, not the log noise.

## The rules that are actually enforced

- `/gd:build` refuses asset work while `greybox_passed: no`
- `gd asset` fails on palette, dimension, grid and triangle-budget violations
- `gd playtest` fails on checks, budgets, *and* runtime script errors
- `gd check` fails on engine type errors and Godot-3 API use
- a generator that never calls `gdblend.report()` fails
- screenshots go to `gd-critic`, never to the agent that built the thing
