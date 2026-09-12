# STATE — Audit2

> Machine-readable session memory. `gd state` reads it, `gd state <key> <value>`
> writes it. Every command updates this before it hands control back, so a fresh
> session can pick up without re-reading the whole project.
>
> Lines of the form `- key: value` are parsed. Prose below them is for humans.

## Now
- palette_synced: 2026-09-12T20:05:56Z

- project: Audit2
- slug: audit2
- godot_project: D:/ClaudeGameDev/game/audit2
- beat: frame
- phase: none
- loop_locked: no
- palette_locked: no
- greybox_passed: no
- last_verdict: none
- blockers: none
- updated: 2026-09-12T20:05:56Z

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
