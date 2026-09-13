# STATE — {{NAME}}

> Machine-readable session memory. `gd state` reads it, `gd state <key> <value>`
> writes it. Every command updates this before it hands control back, so a fresh
> session can pick up without re-reading the whole project.
>
> Lines of the form `- key: value` are parsed. Prose below them is for humans.

## Now

- project: {{NAME}}
- slug: {{SLUG}}
- godot_project: {{PROJECT_PATH}}
- beat: frame
- phase: none
- loop_locked: no
- palette_locked: no
- greybox_passed: no
- greybox_stage: 01
- phase_gate: none
- last_verdict: none
- blockers: none
- updated: {{DATE}}

### Who writes what

`gd` writes `phase_gate` and `last_verdict` — the driver stamps them on every
`run record` and `run gate`, so a resumed session sees the real state rather
than the template's.

**`greybox_passed` is not automatic, and it is not per-phase.** The greybox is a
*block* of stages (see `ROADMAP.md`), and this flag refers to the block, not to
whichever one just went green. It flips only when the **last** greybox stage
clears **and** a person has played it and answered *would I press start again?*

So `phase_gate: green` with `greybox_passed: no` is the normal, correct state
for every greybox stage except the last — and for the last one, while waiting
for the human. `gd run init` reads it and refuses asset work until it is `yes`;
`gd run status` prints how many of the block's stages are done.

`greybox_stage` tracks which stage of the block is current, for readability.
`gd roadmap status` is the authority.

### Beat values

`frame` → `plan` → `greybox` → `build` → `gauntlet` → `playtest` → `ship`

## What just happened

<one paragraph, replaced each beat — not a log>

## What is next

<the single next action, as a command>

## Open decisions

Decisions that are *made* go in CONTEXT.md and never move back here. This list
is only for things genuinely still open, with the cost of deciding wrong.

| decision | options | cost if wrong | who decides |
|---|---|---|---|

## Known broken

Things that are wrong and knowingly left wrong, so no agent "helpfully" fixes
them mid-task and blows up a diff.

| thing | why it is left | when it gets fixed |
|---|---|---|
