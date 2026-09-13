# Quickstart

## Once per machine

```
python install.py
```

Copies the system into `~/.claude/` and runs `gd setup`, which finds Godot and
Blender wherever they live and asks only for what it cannot find. You need
Godot 4.4+, Blender 4.0+, Python 3.10+ and git. No Godot source checkout is
needed — a release download is fine.

Your engine paths go to `~/.claude/gsd-gd.machine.json`, which no upgrade
touches.

## Then, per game

```
cd wherever-you-want-the-game
claude
/gd:new   a snowbound cabin at night, one fire, something out there
/gd:run
```

`.planning/` and `game/` are created in **that directory**. One install, as many
separate games as you like, and nothing one game sets can reach another. `gd
init` refuses to scaffold inside the install itself, which is the one placement
that would leak.

---

## What each step actually does

### 1. `/gd:new` — the only step that needs you the whole time

Checks the toolchain, scaffolds a Godot project with a **playable greybox**
already in it, then **interviews you**:

- the reference — what made you want to build this, and what specifically
  matters about it
- the loop — what the player does over and over, its four beats, and what makes
  turn two different from turn one
- the tension — what gets worse while they do nothing, and how they lose
- **the systems** — every behaviour with state: what it holds, what changes it,
  what the player sees of it. This is the longest part, and it is what makes the
  roadmap any good
- **the world** — every space, its size in metres, how they connect, how long it
  takes to cross. Bring a rough map or let it sketch one for you to correct
- the session shape, and Minute One as a concrete sequence
- the one-way doors — camera, perspective, 2D/3D, animation approach
- the lighting condition

**It will not ask you to cut anything.** If the game is big, the roadmap gets
more stages. The only prioritisation question is what the player touches first.

Answer honestly and specifically. These answers become *contracts* that every
agent afterwards is bound by, so vague answers here cost you later.

**Out comes:** `CORE_LOOP.md`, `COLOR_BIBLE.md`, `CONTEXT.md`, `ROADMAP.md` (the
whole game as stackable stages, each with its target and pass conditions), and
the first stage broken into jobs.

Budget 20–45 minutes of real attention — longer for a game with many systems.
Everything after this is mostly waiting.

#### The greybox block

The first stages are the **greybox block**: the whole game in grey — every space
walkable at real distances, every system running, the loop closing, and a way to
lose. That is usually too much for one phase, so the roadmap splits it into as
many stages as the game needs (one for a small game, six for a large one). Each
one ends playable, and art is blocked by the tooling until the last one clears
*and you have played it*.

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
| `/gd:api    <Class>` | exact signature from your engine build |
| `/gd:frame` | the loop or palette itself is wrong |
| `/gd:help` | every command |

---

## Five things that will surprise you

1. **It refuses to make art until the whole game works in grey.** Not a sample
   room — every space, every system, the loop closing, and a way to lose. `gd
   run init` will not even arm a plan containing asset work before that. A pile
   of beautiful rooms with no gameplay loop is the single most common way these
   projects die.
2. **No colour that isn't in the Color Bible.** Agents literally crash on an
   unknown palette key. That's why the game looks made rather than assembled.
3. **The agent that builds a thing never judges it.** Screenshots go to a critic
   with no access to the code, because a builder sees what it intended.
4. **Blender assets are Python scripts, not `.blend` files.** When the roof is
   wrong you fix one line and re-run. Nothing is hand-modelled.
5. **GDScript is type-checked against the real engine** before anything claims
   to work — most models learned Godot 3, and Godot 4 renamed half the API.
6. **It never asks you to cut a feature.** Everything you name gets a stage
   number. The plan grows to fit the game, not the other way round.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `/gd:*` missing in a new session | `python install.py` from the repo, then restart Claude Code |
| "no Godot path is configured" | `gd setup` — or `gd setup --godot <path> --blender <path>` if autodetection misses |
| Godot or Blender moved | `gd setup --force` |
| `gd setup` found a template build | Point it at the **editor** build: `gd setup --godot <path-to-editor-binary>` |
| Engine commands produce no output on Windows | You are on the plain `.exe`. `gd setup` prefers the `.console.exe`; check `gd config` |
| "no Godot project found" | You're outside the game dir. `cd` to it, or set `GD_PROJECT` |
| Contracts belong to the wrong game | `gd doctor` prints `system` and `work` roots — `work` is wrong |
| A job fails 9 times | The gate is testing the wrong thing, or the job is two jobs. Re-cut it |
| Everything looks black | Correct for `deep_night` with no local light yet. That's `/gd:light` |
| Upgraded or rebuilt Godot | `gd setup --force` (re-detects and re-indexes), or `gddoc index --force` |
| Installed over an existing setup and lost paths | You should not — the machine config sits outside the payload. If it did happen, `gd setup` restores it in seconds |
| A game got created in the wrong folder | `gd doctor` prints `work`; move the `.planning/` and `game/` dirs, or set `GD_PROJECT` |

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
