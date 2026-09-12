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
- phase_gate: none
- last_verdict: none
- blockers: none
- updated: {{DATE}}

### Who writes what

`gd` writes `phase_gate` and `last_verdict` — the driver stamps them on every
`run record` and `run gate`, so a resumed session sees the real state rather
than the template's.

**`greybox_passed` is not automatic.** A green phase gate is necessary and not
sufficient: Law 1 also requires a person to play it and answer *would I press
start again?* `/gd:greybox` sets it, after that. `phase_gate: green` with
`greybox_passed: no` is the normal, correct state while waiting for the human.

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
