# JOB {{ID}} — {{TITLE}}

- phase: {{PHASE}}
- agent: {{AGENT}}
- wave: {{WAVE}}
- status: pending

## Contracts you must honour

- @.planning/COLOR_BIBLE.md — no colour that is not in the table
- @.planning/CORE_LOOP.md — this job serves the loop or it does not ship
- @.planning/BUDGET.md — your gate includes the budget numbers
- @.planning/CONTEXT.md — settled decisions; do not re-open them

## Objective

<What this job produces. One thing.>

## Touches

Files this job is allowed to create or modify. Anything outside this list is a
deviation and must be reported, not silently done.

- <path>
- <path>

## Must not touch

- <paths owned by a parallel job in the same wave>

## Gate

How we will know it worked, before a human looks at it. Write this **before**
building.

- Measure: `gd playtest lab/<plan>.json` → <which checks must pass>
- Numbers: <dims / tri count / fps / draw calls>
- Look: screenshots at <markers> handed to gd-critic

## Deviation rules

1. Missing critical functionality that the gate requires → add it, report it.
2. The plan is wrong about how the engine works → do it correctly, report it.
3. The objective itself looks wrong → **stop and ask**. Do not redesign.

## Result

<filled in by the executor: what was built, what deviated, gate output>
