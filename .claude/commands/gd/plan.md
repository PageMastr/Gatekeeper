---
description: Beat 2 — decompose a milestone into one-session jobs, each with a gate written first
argument-hint: [milestone name, e.g. "station greybox" or "snow traversal"]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, AskUserQuestion
---

# /gd:plan — decompose into jobs that fit one session each

@gsd-gd/references/laws.md
@gsd-gd/references/model-routing.md

Milestone: **$ARGUMENTS**

## Preconditions

```bash
python gsd-gd/bin/gd.py state
```

`loop_locked` and `palette_locked` must both be `yes`. If not, stop and run
`/gd:frame` — planning against an unlocked loop produces a plan for a different
game than the one that gets built.

## Your role here

You are the orchestrator. **You do not build in this session.** Law 3: the
planning context stays clean precisely because it never fills with
implementation. If you start writing GDScript here, every subsequent plan in
this session is worse.

## Produce the plan

```bash
python gsd-gd/bin/gd.py phase new "<milestone>"
```

Then fill in the generated `.planning/phases/NN-<slug>/PLAN.md`.

### Objective and definition of done

One paragraph: what is true at the end that is not true now. Then a done list of
*observable outcomes* — each verified by a named playtest plan or a measured
number, never by "implemented X".

### Jobs

One job = one fresh session = one testable gate. Rules:

- **If a job needs two sessions to hold in context, it is two jobs.** Be
  ruthless here; this is the decision the whole system rests on.
- **Every job names its gate before it is built.** A job without a gate is a
  wish. Write the gate into the job file first.
- **Every job lists the files it may touch**, and the files it must not.
- **Jobs in the same wave must not share a `.tscn`.** Two agents editing one
  scene in parallel produce a merge no one can review. Either serialise them, or
  have each build its own scene and compose them in a later job.
- **Assign an agent and model per job** (see model-routing.md). Mechanics →
  `gd-mechanics`/opus. Assets → `gd-modeler`/fable. Aesthetic or gait work that
  will need iteration → flag it for `/gd:gauntlet`.

Write each job as its own file: `.planning/phases/NN-<slug>/jobs/NN-<job>.md`,
from `gsd-gd/templates/JOB.md`.

### Waves

Group jobs into waves by dependency. Wave 1 is everything with no dependency
and no file overlap. State the overlap analysis explicitly — "jobs 1 and 2 are
parallel-safe: job 1 touches only `scripts/terrain/`, job 2 only
`generators/` and `assets/models/`."

### Checkpoints

Mark any one-way door (animation approach, coordinate scale, streaming model,
renderer settings) as a checkpoint. Execution **stops** there and asks. A
one-way door taken inside a parallel wave is the most expensive mistake
available in this system.

Record doors in `.planning/CONTEXT.md` as they are decided, with the reason.

### Tracer first

Prefer a thin vertical slice that touches every layer over a complete horizontal
layer. One crate that is generated, imported, placed, lit and playtested teaches
you more — and de-risks more — than a finished kit with no scene.

## Sanity pass

Before you hand the plan over, check it against these:

- Does the milestone advance the Core Loop, or is it decoration? Decoration
  before the loop is complete is out of scope by definition.
- Is every gate runnable by `gd playtest` or `gd asset`, with no human in the
  loop for pass/fail? (Taste judgements are `gd-critic`'s, and that is a
  separate, named step — not a gate.)
- Is there a job that proves you can *lose*? Failure states are routinely
  forgotten and they are half the loop.
- Does any job depend on a model's taste rather than a measurement? Route it to
  `/gd:gauntlet` instead of hoping.

## Finish

```bash
python gsd-gd/bin/gd.py state phase "NN-<slug>"
python gsd-gd/bin/gd.py state beat greybox   # or build, if greybox already passed
```

Report: the wave structure, the checkpoints, and the one job you think is most
likely to fail — with what you would try instead. Recommend `/gd:greybox` (if
the loop is not yet proven) or `/gd:build`.
