---
description: Decide and state the single next action
allowed-tools: Read, Bash, Glob, Grep
---

# /gd:next

```bash
python gsd-gd/bin/gd.py state
python gsd-gd/bin/gd.py phase current
```

Work down this table and stop at the first row that matches. The order encodes
the laws: contracts before plans, the loop before the look, a green gate before
more building.

| condition | next |
|---|---|
| no `.planning/` | `gd init "<name>"`, then `/gd:frame` |
| `loop_locked: no` or `palette_locked: no` | `/gd:frame` |
| no current phase | `/gd:plan "<milestone>"` |
| `greybox_passed: no` | `/gd:greybox` |
| a gate is failing | `/gd:build` with that one job (Law 2: one job goes back, not the game) |
| `gd check` reports GDScript errors | fix them with the `godot-api` skill first; nothing else is trustworthy until it is clean |
| a budget is failing | `/gd:perf` |
| an asset came back weak twice | `/gd:gauntlet` on it - a third guess is not a plan |
| jobs remain in the wave | `/gd:build` |
| all jobs done, gates green | `/gd:playtest`, then `/gd:ship` |
| phase shipped | `/gd:frame` or `/gd:plan` for the next milestone |

State the next action as a command, with one sentence of why. If two rows are
arguably live, say which you chose and what you are deferring - do not present
a menu.
