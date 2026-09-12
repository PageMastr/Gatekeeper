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

Also read the driver's own view, which is authoritative about the current phase:

```bash
python gsd-gd/bin/gd.py run status 2>/dev/null
python gsd-gd/bin/gd.py run next 2>/dev/null
```

| condition | next |
|---|---|
| no `.planning/`, or contracts not locked | `/gd:plan "<the idea>"` - kickoff runs the interview, contracts and roadmap |
| contracts locked, no current phase | `/gd:plan "<milestone>"` |
| `run next` says `dispatch` | `/gd:run` |
| `run next` says `checkpoint` | `/gd:run` - it will surface the one-way door for you to decide |
| `run next` says `stop` | read the stop reason; a ladder-exhausted job means the **job or its gate** is wrong, not the model. Usually `/gd:plan` to re-cut that job, or `/gd:gauntlet` if it is aesthetic |
| `run next` says `phase_gate` | `/gd:run` finishes it, then `/gd:playtest` and `/gd:ship` |
| `greybox_passed: no` and the phase builds assets | `/gd:greybox` first - Law 1 |
| `gd check` reports GDScript errors | fix them with the `godot-api` skill; nothing downstream is trustworthy until it is clean |
| a budget is failing | `/gd:perf` |
| an asset came back weak twice | `/gd:gauntlet` on it - a third guess is not a plan |
| phase gate green | `/gd:playtest` for the human pass, then `/gd:ship` |
| phase shipped | `/gd:plan` for the next milestone on the roadmap |

State the next action as a command, with one sentence of why. If two rows are
arguably live, say which you chose and what you are deferring - do not present
a menu.
