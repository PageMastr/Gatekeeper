# Quickstart

## The whole thing in four lines

```
cd wherever-you-want-the-game
claude
/gd:new   a snowbound cabin at night, one fire, something out there
/gd:run
```

`.planning/` and `game/` are created in **that directory**. One install, as many
separate games as you like.

---

## What each step actually does

### 1. `/gd:new` — the only step that needs you the whole time

Checks the toolchain, scaffolds a Godot project with a **playable greybox**
already in it, then **interviews you**:

- the reference — what made you want to build this
- the loop — what the player does, over and over, and why they do it again
- the tension — what gets worse while they do nothing
- the one-way doors — camera, perspective, 2D/3D
- the lighting condition, and what's **not** in v1

Answer honestly and specifically. These answers become *contracts* that every
agent afterwards is bound by, so vague answers here cost you later.

**Out comes:** `CORE_LOOP.md`, `COLOR_BIBLE.md`, `CONTEXT.md`, `ROADMAP.md` (the
whole game as stackable stages), and stage 1 broken into jobs.

Budget 15–30 minutes of real attention. Everything after this is mostly waiting.

### 2. `/gd:run` — it builds

Dispatches jobs in parallel, grades every gate itself, retries failures on
stronger models, commits per job. It **stops** in exactly three situations:

| It stops | What you do |
|---|---|
| **Phase gate is green** | Play it. Answer one question: *would I press start again?* |
| **A one-way door** | Make the call (e.g. rigged animation vs procedural). It records your reason and continues. |
| **A job exhausted the model ladder** | 9 failed attempts means the *job or its gate* is wrong, not the model. Usually `/gd:plan` to re-cut it. |

Safe to Ctrl+C. State lives in `RUN.json`, so `/gd:run` picks up where it left
off — even after `/clear`.

### 3. `/gd:playtest` — the human pass

Measures, screenshots, checks budgets, and hands the frames to a critic that has
never seen the code. Then asks you one specific question.

### 4. `/gd:ship` — close the stage

Re-runs every gate, checks asset licences, snapshots performance, files what was
learned, advances the roadmap.

### 5. Repeat

```
/gd:plan  <next stage from the roadmap>
/gd:run
```

---

## Lost? Two commands

```
/gd:next      the single next action, and why
/gd:status    dashboard: stage, gates, perf, blockers
```

`/gd:next` is the honest one — it reads the driver's state and tells you one
thing to do, not a menu.

---

## Occasionally useful

| | |
|---|---|
| `/gd:asset  <thing>` | build one Blender asset end to end |
| `/gd:light  <mood>` | author lighting presets (press **F9** in-game for sliders) |
| `/gd:lab    <system>` | isolate one system to see what it's really doing |
| `/gd:perf` | frame rate dropped |
| `/gd:gauntlet <thing>` | something needs to be *good*, not just correct |
| `/gd:api    <Class>` | exact Godot 4.7 signature |
| `/gd:frame` | the loop or palette itself is wrong |
| `/gd:help` | all 17 commands |

---

## Five things that will surprise you

1. **It refuses to make art until the greybox passes.** A pile of beautiful
   rooms with no gameplay loop is the single most common way these projects die.
2. **No colour that isn't in the Color Bible.** Agents literally crash on an
   unknown palette key. That's why the game looks made rather than assembled.
3. **The agent that builds a thing never judges it.** Screenshots go to a critic
   with no access to the code, because a builder sees what it intended.
4. **Blender assets are Python scripts, not `.blend` files.** When the roof is
   wrong you fix one line and re-run. Nothing is hand-modelled.
5. **GDScript is type-checked against the real engine** before anything claims
   to work — most models learned Godot 3, and Godot 4 renamed half the API.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `/gd:*` missing in a new session | `python install.py` from the repo, then restart Claude Code |
| "no Godot project found" | You're outside the game dir. `cd` to it, or set `GD_PROJECT` |
| Contracts belong to the wrong game | `gd doctor` prints `system` and `work` roots — `work` is wrong |
| A job fails 9 times | The gate is testing the wrong thing, or the job is two jobs. Re-cut it |
| Everything looks black | Correct for `deep_night` with no local light yet. That's `/gd:light` |
| Rebuilt Godot from source | `python ~/.claude/gsd-gd/bin/gddoc.py index --force` |

---

## Where the depth is

You never need these to use the system, but they're what it's built on:

| | |
|---|---|
| `references/laws.md` | the 14 rules, and why each exists |
| `references/decomposition.md` | how a whole game becomes stackable stages |
| `references/godot-patterns.md` | footprint textures, lighting, occlusion, gait |
| `references/blender-patterns.md` | generators, kits, foliage, decimation |
| `references/gdscript-4x.md` | the Godot 3 → 4 traps |
| `references/playtest-recipes.md` | writing gates, reading verdicts |
