---
description: Beat 4 — execute the plan's jobs in parallel waves, one fresh session each
argument-hint: [optional: wave number, or a single job id]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent
---

# /gd:build — run the waves

@gsd-gd/references/laws.md
@gsd-gd/references/model-routing.md

Target: **$ARGUMENTS** (empty = next incomplete wave)

## Preconditions

```bash
python gsd-gd/bin/gd.py state
python gsd-gd/bin/gd.py phase current
```

- `greybox_passed` must be `yes`. If it is not, stop and run `/gd:greybox`.
  Do not "just do a bit of art first" — that is precisely the failure Law 1
  exists to prevent, and it always looks reasonable at the time.
- A current phase with a `PLAN.md` and job files must exist. If not, `/gd:plan`.

## Your role

Orchestrator. You dispatch jobs and grade what comes back. **You do not build.**

For each job in the wave, spawn one agent with a fresh context, using the agent
and model the plan assigned. Pass it:

- the job file (`.planning/phases/NN/jobs/NN-*.md`)
- the contracts: `COLOR_BIBLE.md`, `CORE_LOOP.md`, `CONTEXT.md`, `BUDGET.md`
- its gate, and nothing about the other jobs in the wave

Launch a wave's jobs in **one message with multiple Agent calls** so they run
concurrently. Never give one agent two jobs to save a session — that is the
thing this whole system is built to avoid.

## Wave discipline

- **Verify file disjointness before dispatch.** Re-read the plan's "touches"
  lists. If two jobs in the wave overlap, split the wave. Two agents editing one
  `.tscn` produces an unreviewable merge.
- **Stop at checkpoints.** If a job in this wave is marked as a one-way door,
  do not dispatch past it. Ask the user, record the decision in `CONTEXT.md`
  with its reason, then continue.
- **A job that fails its gate goes back alone.** Re-dispatch that one job with a
  fresh session and the verdict attached. The other jobs' results stand. Law 2.

## Grading what comes back

For each returned job, in this order:

1. **Did its gate pass?** Run it yourself; do not take the agent's word.
   ```bash
   python gsd-gd/bin/gd.py asset <generator>        # asset jobs
   python gsd-gd/bin/gd.py playtest <plan>          # mechanics jobs
   ```
   `gd asset` fails on contract violations (palette, dims, grid, tri budget);
   `gd playtest` fails on checks, budgets and runtime script errors.

2. **Were deviations reported?** An unreported deviation is the only real
   failure. Check the job's Result section against what actually changed on
   disk (`git status`, `git diff --stat`).

3. **Did anything land outside its "touches" list?** If so, that is a finding
   even when the code is fine — it means the plan's dependency analysis was
   wrong, and the next wave's parallelism assumptions are unsafe.

4. **Screenshots go to `gd-critic`, never to the builder.** Law 6. Spawn it
   with the shots and the Color Bible; give it no access to the job's code.

## Commit per job

One commit per job, with the job id in the message. A wave that lands as one
commit cannot be reverted job-by-job, which defeats Law 2's whole point.

```bash
git add -A && git commit -m "job NN-<slug>: <what it does>"
```

## After the wave

```bash
python gsd-gd/bin/gd.py state last_verdict "<pass/fail summary>"
```

Update the phase `PLAN.md` job table with status, and STATE.md's "What just
happened".

Report: per-job pass/fail with the measured numbers, every deviation, and
`gd-critic`'s findings. Then recommend the next beat — another wave,
`/gd:gauntlet` for anything that came back aesthetically weak, `/gd:perf` if a
budget slipped, or `/gd:playtest` if the wave was the last one.
