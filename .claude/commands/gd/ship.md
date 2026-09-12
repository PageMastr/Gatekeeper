---
description: Beat 7 — close the phase: gates green, licences logged, budget recorded, learnings extracted
argument-hint: [optional: phase name]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /gd:ship — close the phase honestly

@gsd-gd/references/laws.md

Phase: **$ARGUMENTS** (empty = current phase from STATE.md)

Shipping a phase means the next phase can trust it. Everything here exists so
that trust is earned rather than assumed.

## 1. Every gate, green, right now

Not "green last week". Re-run them.

```bash
python gsd-gd/bin/gd.py godot import
for p in game/*/lab/*.json; do python gsd-gd/bin/gd.py playtest "$p" || echo "FAILED: $p"; done
for g in game/*/generators/*.py; do python gsd-gd/bin/gd.py asset "$g" || echo "FAILED: $g"; done
```

Every generator must still reproduce its asset. Law 7: if a generator no longer
runs, the asset is not regenerable, and it has quietly become a hand-edited
mesh.

A failing gate blocks the phase. If the user decides to ship anyway, that is
their call — record it in `BUDGET.md` Deviations or STATE.md "Known broken" with
the reason and a revisit date, and say plainly in your report that the phase
shipped with a known failure.

## 2. Licence ledger

```bash
cat .planning/CREDITS.md
```

Every asset not produced by one of our generators needs a row. Cross-check
against what is actually on disk:

```bash
ls game/*/assets/models game/*/assets/textures game/*/assets/audio
```

An unattributed CC-BY asset is a shipping blocker — that is a legal obligation,
not a preference. Either log it, or remove the asset.

## 3. Budget snapshot

Record the phase's measured numbers in `.planning/BUDGET.md` so the next phase
can detect a regression rather than argue about one:

| phase | fps_avg | fps_1pct_low | draw_calls_max | shadow_lights | scene |
|---|---|---|---|---|---|

Take the numbers from the worst-case plan's verdict, not the spawn point.

## 4. Extract the learnings

The part everyone skips, and the part that compounds.

- **Engine gotchas** discovered this phase → `gsd-gd/references/toolchain.md`
- **Patterns that worked** → `gsd-gd/references/godot-patterns.md` or
  `blender-patterns.md`
- **Model observations** (which model produced the accepted work, where one
  clearly beat another) → `gsd-gd/references/model-routing.md`
- **Decisions made** → `.planning/CONTEXT.md`, each with its reason
- **What the plan got wrong** — jobs that were really two jobs, waves that were
  not actually parallel, gates that passed for the wrong reason. Write it in the
  phase `PLAN.md` retro section. The next `/gd:plan` reads it.

## 5. Archive and commit

```bash
python gsd-gd/bin/gd.py state beat frame          # next milestone starts at frame
python gsd-gd/bin/gd.py state phase none
git add -A && git commit -m "ship phase NN-<slug>: <one line>"
git tag "phase-NN-<slug>"
```

`.gd_out/` is generated; it does not get committed.

## 6. Optional: a build

Only if the user asks. This is a Godot **source build**, so the export templates
are the ones in `D:/Godot/GodotEngine/bin/` (Windows x86_64 and Web wasm32) —
`export_presets.cfg` must point at those paths, not at downloaded templates.
See `gsd-gd/references/toolchain.md`.

## Finish

Report, plainly:
- gates: how many passed, and any that did not, with the output
- licences: complete or what is missing
- budget: this phase vs last
- learnings written, and where
- what the next milestone should be, and why

Then recommend `/gd:frame` for the next milestone, or `/gd:plan` if the loop and
palette still hold.
