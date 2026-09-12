# PLAN — {{PHASE}}

- created: {{DATE}}
- status: draft
- depends_on: <previous phase, or none>

## Objective

<One paragraph. What is true at the end of this phase that is not true now?>

## Definition of done

The phase is done when these are all green — not when the jobs are finished.

- [ ] <observable outcome, verified by a named playtest plan or metric>
- [ ] <…>
- [ ] No budget regressions vs previous phase

## Phase gate

Machine-readable. `gd run` treats these as the phase's definition of done and
re-runs them after every wave; `/gd:run` halts here for you to play it. Every
line must be a command that exits non-zero on failure.

- gate: python gsd-gd/bin/gd.py check
- gate: python gsd-gd/bin/gd.py playtest <plan>

## Jobs

One job = one fresh session = one testable gate. If a job needs two sessions to
hold in context, it is two jobs. Jobs in the same wave must not touch the same
files.

`model` is optional — leave it blank and the agent's default from
`references/model-routing.md` is used. `gd run` escalates it on repeated
failure; do not hand-edit it mid-run.

| # | job | agent | model | wave | touches | gate |
|---|---|---|---|---|---|---|
| 1 | | gd-mechanics | | 1 | | |
| 2 | | gd-modeler | | 1 | | |
| 3 | | gd-mechanics | | 2 | | |

### Waves

- **Wave 1** (parallel): jobs 1, 2 — disjoint file sets, no shared scene edits.
- **Wave 2** (after 1): job 3 — needs wave 1's output.

Scene files (`.tscn`) are the usual collision. Two agents editing one scene in
parallel produces a merge you cannot review. Either serialise them, or have each
build its own scene and compose them in a later job.

## Checkpoints

Points where the run stops and asks, because the decision is a one-way door.

| after job | decision | why it stops |
|---|---|---|

## Risks

| risk | early signal | what we do about it |
|---|---|---|

## Out of scope for this phase

- <…>
