# Gatekeeper

A spec-driven, context-engineered system for building games with Godot and
Blender. Named for what it does: every step ends at a gate written before the
work started, and nothing moves forward until it is green.

Read this file, then `gatekeeper/references/laws.md`.

## Installing / two roots

`python install.py` installs this at user scope so the commands work in any
session, and ends by running `gd setup` to find Godot and Blender on this
machine. It installs for **whichever front-ends are present** — Claude Code
(`~/.claude/`, commands as `/gd:*`) and Codex (`~/.codex/skills/`, the same
commands as `$gd-*`); `--host claude|codex|both` picks explicitly. The system
payload itself is installed **once** and shared, so one machine has one
`gd version` fingerprint no matter how many front-ends drive it. **`SYS_DIR` and `WORK` are separate roots**: the system lives where it
is installed, while `.planning/` and `game/` are created in the directory you are
working in. Conflating them would make every game on the machine share one Color
Bible. `gd doctor` prints both, and `gd init` refuses to scaffold inside either
the install or this repo.

## Nothing is hardcoded

This is meant to be downloaded and used by people whose disks look nothing like
this one. Three config layers, lowest precedence first:

| # | file | holds | lifetime |
|---|---|---|---|
| 1 | `gatekeeper/config.json` | shipped defaults: budget, playtest defaults, model routing. **No paths** | replaced on every upgrade |
| 2 | `~/.claude/gatekeeper.machine.json` | this machine's Godot and Blender | written by `gd setup`, never touched by install; one file, shared by every front-end (`GD_MACHINE_CONFIG` moves it) |
| 3 | `<game>/.planning/config.json` | that game's numbers | lives in the game's own repo |

Then `GD_GODOT` / `GD_BLENDER` / `GD_GODOT_SOURCE` on top, per shell.

```bash
gd setup          # detect the toolchain and record it (once per machine)
gd setup --show   # what is recorded
gd config         # all three layers, and where each value came from
```

**Never write a path into `gatekeeper/config.json`.** It is shipped, shared by every
game, and replaced on every upgrade. A Godot **source checkout is optional** —
with none, `gddoc index` has the engine generate its own class reference with
`--doctool`. Details: `gatekeeper/references/toolchain.md`.

## What this repo is

- `gatekeeper/` — the system. CLI, Blender library, Godot harness, templates, doctrine.
- `.claude/` — commands (`/gd:*`), agent definitions, skills. **This is the only
  place a command or an agent is written.** The Codex front-end is *rendered*
  from these same files at install time (`/gd:x` → `$gd-x`, `gd-y` →
  `$gd-agent-y`), because two hand-maintained copies of the same doctrine is how
  they drift, and doctrine that drifts silently is worse than doctrine missing.
- `.planning/` — the contracts for the game currently being built:
  `CONTEXT.md` (settled decisions, systems, the map), `COLOR_BIBLE.md` (the
  palette), `CORE_LOOP.md` (what the player does), **`ROADMAP.md`** (the whole
  game as stages that stack, with targets, pass conditions, a systems inventory
  and a levels table), `BUDGET.md`, `CREDITS.md`, `STATE.md`,
  **`SYSTEM_FINDINGS.md`** (what the *system* got wrong while building this),
  and `config.json` (this project's config overrides).
- `game/<slug>/` — the Godot project itself.

## Drive everything through `gd`

```bash
python gatekeeper/bin/gd.py <verb>
```

| verb | does |
|---|---|
| `setup` | **detect Godot and Blender on this machine**; run once, before anything else |
| `doctor` | verify the toolchain end to end |
| `init <name>` | scaffold a game project + `.planning/` contracts |
| `state [k] [v]` | read/write `.planning/STATE.md` |
| `phase new\|list\|current` | phase directories |
| `palette` | regenerate `res://scripts/palette.gd` from the Color Bible |
| `roadmap [status\|done <id>]` | **validate the stage roadmap** — stacking, targets, greybox block, systems, spaces, coverage, placeholders |
| `now` | current UTC timestamp — never type one from memory |
| `config [--init]` | effective config across all three layers |
| `version [--record]` | fingerprint of the installed system, by component |
| `harness [--check]` | (re)install the harness, or detect drift in the grader |
| `models [--host claude\|codex\|all]` | show model routing per agent for a front-end + flag config/frontmatter drift |
| `run init\|next\|record\|gate\|resolve\|status` | the phase driver's state machine |
| `check [files]` | **GDScript gate** — engine type-check + Godot-3-ism scan |
| `blender <script.py>` | run a Blender script headless with `gdblend` on path |
| `asset <generator.py>` | generator → GLB → project → reimport, gated on metrics |
| `godot import\|script` | headless engine operations |
| `playtest <plan> [--lint\|--smoke]` | measure + look + perf. `--lint` validates a plan without running it; `--smoke` gates on the harness booting |
| `credits <asset> <source> <license>` | append to the licence ledger |

And the local, version-exact API reference:

```bash
python gatekeeper/bin/gddoc.py <verb>
```

| verb | does |
|---|---|
| `class <Name> [--full]` | every signature + the inheritance chain |
| `member <Class>.<member>` | one exact signature + docs, resolved through base classes |
| `search <keyword>` | find a class or member when you do not know the name |
| `exists <Name>` | is this class real in this build? |
| `scan <file.gd>` | flag Godot-3-isms with their 4.x replacement |
| `index [--force]` | rebuild the index (needed after an engine upgrade) |

Every verb of both tools prints one `GD<VERB> {json}` line. Parse that, not the
log noise.

## How a session normally goes

```
/gd:new <idea>      new game: toolchain, scaffold, then the kickoff interview
                    -> contracts -> roadmap -> first stage's jobs -> driver armed
/gd:run             drive the stage until the gate is green or a door blocks
```

After the first stage the loop is `/gd:plan <next stage>` then `/gd:run`.

**Under Codex the same commands are skills:** `$gd-new`, `$gd-run`,
`$gd-plan`, and the agents are `$gd-agent-mechanics`, `$gd-agent-critic` and so
on. Everything below this line is identical on both — the laws, the gates, the
harness and the numbers are about Godot and Blender, not about the front-end.

`/gd:new` owns first-run setup only (toolchain check, API index, git, naming, and
a guard against clobbering existing contracts) and then invokes `/gd:plan` for
the interview — the interview is defined in one place, not two. `/gd:plan` is
context-aware: unlocked contracts means kickoff, locked means next stage.
`/gd:run` then dispatches waves, grades every gate itself, escalates a failing
job up the model ladder, and **halts at one-way doors and at the phase gate** so
a human plays it before art starts.

Beats underneath, all still callable by hand:

`/gd:frame` → `/gd:plan` → `/gd:greybox` → `/gd:build` → `/gd:gauntlet` →
`/gd:playtest` → `/gd:ship`

Utilities: `/gd:asset`, `/gd:lab`, `/gd:light`, `/gd:perf`, `/gd:api`,
`/gd:status`, `/gd:next`, `/gd:help`.

Everything runs through the slash commands — you should never need to type a
bare `python gatekeeper/...` command yourself; the commands do it.

## Hard rules

These are enforced by tooling, not just convention. Do not work around them.

1. **The loop before the look.** `.planning/CORE_LOOP.md` first, then the
   **whole game playable on grey boxes** — every space at real distances, every
   system running, the loop closing, and a reachable failure state — before any
   asset work. That is a **block** of consecutive stages numbered from 01 in the
   roadmap, sized to the game. `gd run init` refuses a plan containing asset work
   until the block is done and `greybox_passed: yes`.
2. **One job, one fresh session, one gate written before the job starts.** When
   a gate fails, one job goes back — not the game.
3. **A builder never grades its own work.** Screenshots go to `gd-critic`.
4. **Assets are scripts.** Blender runs headless on Python. The script is the
   source of truth; the `.glb` is a build artifact. Never hand-edit a mesh, and
   never put an interactive Blender session in the build path.
5. **The Color Bible is a contract.** `.planning/COLOR_BIBLE.md` is the only
   source of colour. `gdblend.mat()` raises on an unknown key;
   `Palette.get_color()` asserts. No hex literals in game code or generators.
6. **Every asset reports metrics.** A generator that does not call
   `gdblend.report()` fails. Unmeasured means ungateable.
7. **Shadows are rationed.** Budget in the effective config; enforced at runtime
   by `GDLightingRig.enforce_shadows()` and at gate time by `gd playtest`.
8. **Log the licence when the asset lands**, not at ship time.
9. **The roadmap is a validated contract, not a document.** `.planning/ROADMAP.md`
   breaks the whole game into stages that each end in something **playable**, and
   `gd roadmap` fails on a stage that depends on a later stage, a stage with no
   target or pass conditions, a system or space not greyboxed inside the block, a
   Core Loop beat with no stage, or a placeholder with no stage that replaces it.
   A stage that ends "the kit is done, nothing uses it" has not stacked — rework
   it.
10. **Model routing lives in config → `models`**, never hardcoded. Each agent's
   starting model is stored with the reason it was chosen, and `gd models` flags
   drift against the agent frontmatter. `gd run` owns the escalation ladder
   (3 attempts per tier, then climb) — no agent may grant itself a fourth
   attempt or pick its own model. **The role and its reason are host-neutral;
   only the tier names differ** (`models.hosts.<host>`), so a routing decision
   is made once and `gd models --host all` shows what each front-end resolves
   it to.
11. **No GDScript from memory.** Most training data is Godot 3; Godot 4 renamed,
   moved and deleted much of the API, so recalled GDScript looks right and fails
   at runtime. Before writing engine code, look every type up in the local
   version-exact reference (`gddoc`, or the `godot-api` skill). Use static types
   everywhere. Then `gd check` before claiming anything works — it runs the
   engine's own analyser plus a Godot-3-ism scan, and it is a gate, not advice.
12. **More game means more stages, never less game.** Do not propose cutting a
   feature, and do not ask the user what they are willing to drop. Something that
   will not fit gets its own stage; something that must wait goes in the
   roadmap's **Later stages** *with the stage number it will get*. The only
   judgement the roadmap makes is order.

## Conventions

- 1 Godot unit = 1 metre. Modular kit snap grid = 0.25 m.
- Assets: `game/<slug>/generators/<name>.py` → `assets/models/<name>.glb`.
- Playtest plans: `game/<slug>/lab/<name>.json`.
- Test scenes: `game/<slug>/lab/`. One system, one straight line.
- Never hand-write a `uid://` in a `.tscn` — an invalid UID crashes the importer.
- Never name a local variable `name` in a `Node` subclass.
- `.gd_out/` is generated output. Not committed, safe to delete. Graded
  verdicts are archived per attempt to `<phase>/verdicts/`.
- **Never type a timestamp.** `gd now`. Agents invent plausible ones.

**Per-project config, never the shipped one.** `gatekeeper/config.json` is **shipped
defaults only** — it is shared by every game on this machine and replaced on
every upgrade, so a number set there is a number set for all of them, until it
is not. Each project overrides what it needs in `.planning/config.json`,
deep-merged on top:

```bash
gd config            # what is in force, and which layer each value came from
gd config --init     # add an override file to an existing project
```

Budget, playtest defaults, model routing and the Blender snap grid are all
per-project. `BUDGET.md` justifies the numbers in prose; `.planning/config.json`
holds them. One source of truth each.

**File what the system gets wrong.** When the toolchain rejects correct work,
produces a verdict you cannot trust, or behaves in a way the references do not
cover, append a row to `.planning/SYSTEM_FINDINGS.md` and carry on. A project
under real load is the only thing that finds these — one did, and caught a gate
that was certifying the wrong plan's checks as green. Filing is not permission
to fix (Law 6b).

**A verdict names its toolchain.** `gd version` fingerprints the install by
component (cli, harness, lib, templates, references, config). Every verdict
records it, `gd init` pins it as the project's baseline, and `gd run status`
warns when the system has changed mid-phase — because jobs graded before a
change were graded by a different toolchain.

**Never edit the installed system.** The installed `gatekeeper/` (under
`~/.claude/`, or `~/.codex/` on a Codex-only machine — `gd doctor` prints which)
is shared by every game on this machine and is not under version control. Editing the harness,
templates or CLI there changes how every other project is graded, with no
record. Observed: one game wrote two of its own lighting presets into the shared
rig, and `install_harness()` then copied them into three unrelated games — two
referencing a palette swatch those games do not define.

If a harness change is genuinely needed, say so and stop. It is a change to the
system, reviewed once and upstreamed into the repo — not a file edit.

- **An implementing agent never writes its own gate.** `gd-playtester` authors
  every playtest plan, in an earlier wave. A test written by the thing it
  certifies is self-grading — Law 6, one level up.

## Where to read more

| topic | file |
|---|---|
| The fifteen laws and why they exist | `gatekeeper/references/laws.md` |
| Setup, config layers, engine gotchas | `gatekeeper/references/toolchain.md` |
| Engine patterns (tracks, lighting, occlusion, gait) | `gatekeeper/references/godot-patterns.md` |
| Generator craft, kits, foliage, decimation | `gatekeeper/references/blender-patterns.md` |
| Writing playtest plans and reading verdicts | `gatekeeper/references/playtest-recipes.md` |
| Godot 4 API discipline and the 3.x→4.x traps | `gatekeeper/references/gdscript-4x.md` |
| Breaking a whole game into stackable stages, and sizing the greybox block | `gatekeeper/references/decomposition.md` |
| Which model does which job | `gatekeeper/references/model-routing.md` |
