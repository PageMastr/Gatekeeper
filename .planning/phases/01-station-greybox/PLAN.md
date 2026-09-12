# PLAN — 01-station-greybox

- created: 2026-09-12T16:38:13Z
- status: draft
- depends_on: <previous phase, or none>

## Objective

<One paragraph. What is true at the end of this phase that is not true now?>

## Definition of done

The phase is done when these are all green — not when the jobs are finished.

- [ ] <observable outcome, verified by a named playtest plan or metric>
- [ ] <…>
- [ ] `gd playtest lab/<plan>.json` passes
- [ ] No budget regressions vs previous phase

## Jobs

One job = one fresh session = one testable gate. If a job needs two sessions to
hold in context, it is two jobs. Jobs in the same wave must not touch the same
files.

| # | job | agent | wave | touches | gate |
|---|---|---|---|---|---|
| 1 | | gd-mechanics | 1 | | |
| 2 | | gd-modeler | 1 | | |
| 3 | | gd-mechanics | 2 | | |

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
