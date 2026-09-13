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

## 4. Advance and revise the roadmap

```bash
python gsd-gd/bin/gd.py roadmap done <stage id>
python gsd-gd/bin/gd.py roadmap
```

The first marks the stage done and advances `current stage`. The second
re-validates — and this is where it earns its keep, because what you just
learned is allowed to change the plan:

- a stage that turned out to be two stages → split it
- a stage that turned out to belong later → move it to **Later stages** *with
  the stage number it will get*. It is rescheduled, not cut (Law 13b); a stage
  genuinely deleted takes its coverage rows with it and says why
- an order that was wrong → reorder, keeping `depends on` pointing backwards
- a placeholder you introduced this phase → add it to the ledger **now**, with
  the stage that will replace it

Revising is expected; the kickoff roadmap is a forecast. What is not allowed is
silently dropping a coverage row — that is how an element stops being built
without anyone deciding it should. The validator will not catch a deletion, so
this is on you: if something leaves the plan, it leaves visibly.

Add a row to the Revisions table saying what changed and why.

## 5. Sweep the system findings

```bash
cat .planning/SYSTEM_FINDINGS.md
```

This is the highest-value artefact a phase produces, because it is the only
evidence of how the *system* behaves under real load. Go through it:

- **Any `false-pass` entry is an emergency.** A gate certified something untrue,
  so every verdict that gate produced this phase is suspect. Say so explicitly
  in your report, and re-run the affected gates before shipping.
- **Engine knowledge** → fold into `references/gdscript-4x.md`,
  `godot-patterns.md` or `blender-patterns.md` via `gd-scribe`, so the next
  project starts with it instead of rediscovering it.
- **Workarounds in force** → check each against the findings' status. A fixed
  finding whose workaround is still in the code is debt to remove now, while
  you remember why it was there.
- Mark each finding `reported` once it is written up here. Do not mark anything
  `fixed` — that is the system's call, not the project's.

Findings do not get closed by shipping. They travel with the project until the
system changes.

## 6. Extract the learnings

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

## 7. Archive and commit

```bash
python gsd-gd/bin/gd.py state beat frame          # next milestone starts at frame
python gsd-gd/bin/gd.py state phase none
git add -A && git commit -m "ship phase NN-<slug>: <one line>"
git tag "phase-NN-<slug>"
```

`.gd_out/` is generated; it does not get committed.

## 8. Optional: a build

Only if the user asks. This is a Godot **source build**, so the export templates
are the ones beside the configured engine binary (`gd config` prints its path) —
`export_presets.cfg` must point at those paths, not at downloaded templates.
See `gsd-gd/references/toolchain.md`.

## Finish

Report, plainly:
- gates: how many passed, and any that did not, with the output
- licences: complete or what is missing
- budget: this phase vs last
- learnings written, and where
- system findings: how many, how many `false-pass`, and what you folded into
  the references
- the roadmap: stages done / total, and any revision you made
- what the next stage is, straight off the roadmap, and what it de-risks

Then recommend `/gd:plan "<next stage from the roadmap>"`. Only send them back
to `/gd:frame` if this phase showed the *contracts* are wrong — the loop is not
fun, or the palette is fighting the assets. That is a real finding, not a
failure; say it plainly if you saw it.
