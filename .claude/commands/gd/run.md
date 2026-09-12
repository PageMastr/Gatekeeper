---
description: Drive the current phase autonomously — dispatch waves, grade gates, escalate failures — and stop at the phase gate or a one-way door
argument-hint: [optional: phase name, or --dry-run to show the plan of action]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, Skill
---

# /gd:run — run the phase until it is green or it needs you

@gsd-gd/references/laws.md
@gsd-gd/references/model-routing.md

Target: **$ARGUMENTS** (empty = the current phase from STATE.md)

This is `/gd:build` in a loop, with grading and escalation. It does not replace
the granular commands — it calls the same machinery.

## The contract

**The state machine is not yours to reason about.** `gd run` owns the wave
order, the checkpoints and the escalation ladder. You ask it what to do next and
you record what happened. Never decide a job "probably passed", never skip to a
later wave, never change a job's model by hand — if you do, the ladder and the
resumability both break.

```bash
python gsd-gd/bin/gd.py run init      # first time in a phase (parses PLAN.md)
python gsd-gd/bin/gd.py run next      # -> dispatch | checkpoint | phase_gate | stop
python gsd-gd/bin/gd.py run record <job> pass|fail --note "..."
python gsd-gd/bin/gd.py run gate      # runs the phase gate commands
python gsd-gd/bin/gd.py run status    # the whole board
```

## Preconditions

```bash
python gsd-gd/bin/gd.py state
python gsd-gd/bin/gd.py run status || python gsd-gd/bin/gd.py run init
```

- **Law 1 check.** If this phase contains asset work (any `gd-modeler` job, or a
  job whose gate is `gd asset ...`) **and** `greybox_passed` is `no`, stop and
  say so — the honest move is to finish the greybox phase first. Driving the
  greybox phase itself with `greybox_passed: no` is exactly correct; that is
  what it is for.
- `PLAN.md` must have real job rows and at least one `- gate:` line. A phase with
  no machine-readable definition of done cannot be driven; send it back to
  `/gd:plan`.

If `$ARGUMENTS` contains `--dry-run`: print `run status` and the next action,
explain what you *would* dispatch, and stop without building anything.

## The loop

Repeat until `run next` returns `stop`, `checkpoint`, or a green `phase_gate`:

### 1. Ask what is next

```bash
python gsd-gd/bin/gd.py run next
```

### 2. `action: dispatch`

Spawn **one agent per job, all in a single message** so the wave runs
concurrently. For each job use exactly the `agent` and `model` the tool
returned — the model may have been escalated, and that is the ladder working.

Give each agent: its job file, the contracts (`CORE_LOOP.md`, `COLOR_BIBLE.md`,
`CONTEXT.md`, `BUDGET.md`), its `touches` / must-not-touch lists, and its gate.
Give it **nothing about the other jobs in the wave**.

On a retry, also give it: the previous verdict output, and what the last attempt
tried. An agent repeating a failed approach because nobody told it what failed
is the most common way a retry budget gets wasted.

Before dispatching, re-read the `touches` lists and confirm the wave is
genuinely disjoint. If two jobs overlap, stop and report it — the plan's
dependency analysis is wrong, and running them in parallel produces a merge
nobody can review.

### 3. Grade every job yourself

Do not take an agent's word for it. Run its gate:

```bash
python gsd-gd/bin/gd.py check                     # any job that touched .gd
python gsd-gd/bin/gd.py asset <generator>         # asset jobs
python gsd-gd/bin/gd.py playtest <plan>           # mechanics jobs
```

Then record the truth:

```bash
python gsd-gd/bin/gd.py run record <job> pass --note "<measured result>"
python gsd-gd/bin/gd.py run record <job> fail --note "<which check, actual vs wanted>"
```

The `--note` is what the next attempt reads. "gate red" is useless; "player_moved
path=0.9 need>=4.0; door never opened" is actionable.

Also check: did anything land outside the job's `touches` list? That is a
finding even when the code is good, and it goes in the note.

Commit each passing job separately, with its id:
```bash
git add -A && git commit -m "job <id>: <what it does>"
```

A wave that lands as one commit cannot be reverted job-by-job, which defeats the
point of one-job-one-gate.

### 4. Visual work goes to the critic

Any job that produced screenshots: spawn **`gd-critic`** with the shots and the
Color Bible, and **not** the code. A send-back is a `fail` — record it with the
critic's reasoning as the note.

If the same job gets sent back twice on aesthetics, stop the loop and recommend
`/gd:gauntlet` on it. A third guess is not a plan; that job needs candidates and
a judge.

### 5. `action: checkpoint`

**Stop.** This is a one-way door. Present the decision, the options and what each
forecloses, and ask the user. Then:

```bash
python gsd-gd/bin/gd.py run resolve <after_job> --note "<decision and why>"
```

Record it in `.planning/CONTEXT.md` with its reason before continuing.

### 6. `action: phase_gate`

```bash
python gsd-gd/bin/gd.py run gate
```

- **Green** → stop the loop and hand back to the user. Beat 6/7 are next.
- **Red** → the failure tells you where to go: a check failure means a job goes
  back (record it `fail` and loop); a budget failure means `/gd:perf`. Do not
  edit the gate to make it pass.

### 7. `action: stop`

Report the reason verbatim and stop. The usual reason is a job that exhausted
the ladder — three attempts each at its tier, the next, and the top. When that
happens the problem is the **job or its gate**, not the model, so say what you
think is actually wrong: an underspecified objective, a gate asserting the wrong
thing, or a missing dependency the plan did not see.

## Escalation, for reference

Owned by `gd run record`, configured in `config.json` → `models`:

```
3 attempts at the job's model  →  climb one tier  →  3 more  →  …  →  3 at the top  →  stop
haiku → sonnet → opus → fable
```

Starting model per agent comes from `config.json`; `python gsd-gd/bin/gd.py models`
prints the table and flags drift against the agent files.

## While it runs

Say what you are doing each iteration in one or two lines — wave, jobs, models,
gate results. Enough to follow, not a transcript. The user may be watching, and
Ctrl+C is their brake.

`RUN.json` is written every iteration, so an interrupted run resumes from
`/gd:run` with nothing lost.

## Finish

Report:
- the phase gate result, with the numbers
- per-job: attempts, final model, what its gate measured
- every escalation, and whether the stronger model actually fixed it (this is
  the feedback that improves `model-routing.md` — file it via `gd-scribe`)
- every deviation and anything that landed outside its `touches` list
- the critic's findings, verbatim
- the single next command
