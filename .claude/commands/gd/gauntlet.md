---
description: Beat 5 — run one hard or aesthetic task through candidates + an independent critic + numeric gates, until it is good
argument-hint: <the one thing to get right, e.g. "the modular wall kit" or "the treehouse">
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent
---

# /gd:gauntlet — one task, many candidates, an independent judge

@gsd-gd/references/laws.md

Target: **$ARGUMENTS**

## When to use this

For the tasks that a single pass will not get right, because the target is
*taste* rather than *correctness*:

- a modular kit that has to tile and also look like something
- a hero asset (a treehouse, a bridge, a creature)
- a gait or a camera feel
- a lighting look for a signature space
- a shader effect where "does it work" and "is it good" are different questions

Not for ordinary jobs. A gauntlet costs many sessions; spend it where a normal
job's single pass measurably is not enough. These sessions can run for hours.

## The structure

Two independent forces, applied at the same time:

```
                  ┌─> candidate A ─┐
   the task ──────┼─> candidate B ─┼──> INDEPENDENT CRITIC ──> accept / send back
                  └─> candidate C ─┘           ▲
                                               │
                            NUMERIC GATE ──────┘
                    (dims, grid, tri budget, fps, draw calls)
```

- **Candidates** are built by separate fresh sessions that cannot see each
  other's work. Convergent thinking is what you are trying to avoid.
- **The critic never built anything.** Law 6. It sees renders and numbers, not
  code, and it has authority to send work back.
- **The numeric gate runs regardless of taste.** A beautiful wall kit that is
  3 mm off the snap grid is a failed wall kit. The metric is not a tiebreak, it
  is a veto.

## Running it

### 1. Define the target precisely enough to judge

Write `.planning/phases/NN/gauntlet-<slug>.md`:

- **The numbers** — exact dims and tolerance, snap grid, tri budget, material
  ceiling, fps floor. From the asset spec or `BUDGET.md`.
- **The aesthetic target** — in specifics, not adjectives. "The silhouette reads
  from 30 m against the sky"; "the fire is the only warm thing in frame";
  "the kit's seams are invisible at 2 m". "Make it stunning" is not a target;
  it is a hope, and a critic cannot rule on it.
- **The palette keys** it may use.
- **What failure looks like** — the specific ways this usually goes wrong.

### 2. Spawn candidates

Two or three, in one message so they run concurrently, each with a fresh
context and the same brief. Use different models where the task is aesthetic
(`gd-modeler` on fable, a second on opus) — the comparison is itself the
finding, and it is cheap.

Each candidate must produce a runnable artefact and its numbers:
```bash
python gsd-gd/bin/gd.py asset generators/<candidate>.py     # -> metrics + GLB
python gsd-gd/bin/gd.py playtest lab/<candidate>.json       # -> verdict + shots
```

### 3. Render every candidate the same way

Same lab scene, same lighting preset, same camera, same resolution. A candidate
that wins because it was shot from a better angle has not won.

`/gd:lab` builds that scene if it does not exist.

### 4. Judge

Spawn `gd-critic` with: the shots, the numbers, the aesthetic target, the Color
Bible. **Not** the generators. Its verdict is one of:

- **accept** — name the winner and why, in terms of the stated target
- **send back** — what specifically is wrong, and what to try. Not "improve the
  proportions" but "the roof overhang is half what it needs to be; the
  silhouette has no shadow line"

### 5. Loop

Send-backs re-enter step 2 as a new round, with the critic's findings and only
the surviving candidate lines. Keep a round log in the gauntlet file: what
changed, what the critic said, which numbers moved.

Stop when the critic accepts and the numbers pass — or when two consecutive
rounds produce no improvement, which means the *target* is wrong, not the work.
Say so rather than running a third.

### 6. Land it

The winner's generator becomes the real one. Delete the losers' generators but
keep the round log — it is the reasoning, and the next kit will want it.

```bash
git add -A && git commit -m "gauntlet <slug>: <winner> after N rounds"
```

## Finish

Report: rounds run, what each round changed, the critic's accepting verdict,
final numbers against budget, and a one-line note on which model produced the
winner (for `model-routing.md`).
