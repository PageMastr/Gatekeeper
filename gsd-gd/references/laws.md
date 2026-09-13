# The Laws

Fourteen rules. Every command and every agent in this system is an attempt to
make one of them unavoidable. They are ordered by how expensive it is to break
them.

---

## 1. The loop comes before the look

The characteristic failure of AI-built games is not ugliness. It is a folder of
beautiful rooms with nothing to do in them. Projects die here, not at the art
stage.

So: `.planning/CORE_LOOP.md` is written before any code, and one complete turn
of the loop must be playable **on grey boxes** — including a reachable failure
state — before a single asset is generated. `/gd:build` refuses to start asset
work while `greybox_passed: no` is in STATE.md.

## 2. Never ask for the whole game in one prompt

One job, one fresh session, one testable gate. A session carrying nine other
jobs reads more, holds more, and makes more mistakes — and when it fails you
cannot tell which of the ten things broke.

When a gate fails, **one job goes back, not the game**.

## 3. The best model plans and judges; it does not build

The planner decomposes and grades. It does not write the mechanics. Keeping the
planning context clean is the whole reason the plan stays good on job forty.

## 4. Every job ends in a test written before the job starts

If you cannot say how you will know it worked, you do not have a job — you have
a wish. Write the gate into the job file first, then build.

## 5. Verification is measure **and** look, plus a human

- **Measure**: a script drives the game and prints numbers. Did the player
  move 4 metres? Did the door open? Pass or fail, no opinion. → `gd playtest`
- **Look**: the same run takes screenshots, and a *different* agent reads them.
  "This room is too dark" is a finding no assertion will ever produce.
- **Human**: the last gate is always a person. The two automated passes exist to
  make sure the person's attention is spent on taste, not on catching crashes.

**And know what a gate cannot prove.** A playtest plan presses exactly the keys
it lists, so it proves *the machine's input path*, never the player's. A phase
once reached a green gate on **220 checks across 18 plans**, with two audit jobs
specifically hunting checks that pass for the wrong reason — and a human played
it for five minutes and found the core loop broken in three ways, every one
invisible to every gate. The cause was simple: asking a crew member took two
presses, every plan pressed both, and no plan modelled the player who presses
the first, reads *"-15 faith"*, and sees nothing happen.

So: **write plans that press only part of an interaction.** A gate that only
ever performs complete, correct input is a gate that certifies the happy path
and nothing else. And never treat a green gate as a substitute for the human —
this is why the third clause of this law is not optional.

## 6. A builder never grades its own work

The agent that made the thing is the worst possible judge of it — it knows what
it intended, so it sees what it intended. Screenshots go to `gd-critic`, which
has never seen the code. This separation is the single highest-value structure
in the system; do not collapse it to save a session.

## 6b. Never modify the instrument that grades you

Law 6 says a builder does not judge its own work. The same applies to the
*measuring device*: the playtest harness, the gate plans, and the installed
system under `~/.claude/gsd-gd/`.

The risk is not malice, it is an **unreviewed grader**. A subtly wrong change to
a check makes future gates pass that should not, and every verdict after it is
worth less. Observed twice: a builder committing a harness it had not authored,
and a game writing its own lighting presets into the shared rig, from where they
propagated into three unrelated games.

So: the harness is read-only to every agent. `gd harness --check` reports drift,
`gd doctor` fails on it, and every verdict records the hash of the harness that
produced it. A needed improvement is proposed, reviewed, and upstreamed into the
repo - never edited in place.

## 7. Assets are scripts, not files

Blender is driven headless by Python. The script is the source of truth; the
`.glb` is a build artifact, regenerable and disposable.

When the roof is wrong you do not touch the mesh — you fix one line and run it
again. A hand-edited mesh cannot be reviewed, diffed, re-run with different
parameters, or explained six weeks later.

(This also means no interactive Blender MCP in the build path. A mouse-driven
edit is an un-reproducible edit.)

## 8. The Color Bible is a contract, not a mood board

Every colour in the game resolves against one table. `gdblend.mat()` raises on
an unknown key; `gd palette` regenerates `Palette` for GDScript from the same
table. Without this, every model invents its own fourth shade of grey and the
game reads as assembled rather than made.

Translate the reference into the game's lighting condition **once**, in the
Bible, before anything is built. A daylight reference used directly for a night
game produces washed-out assets that each get "fixed" differently.

## 9. Simple forms, lit well — never "realistic"

Ask a model for a realistic mesh and you get mush. Ask for boxes, a roof, a
bevel on every edge, and honest proportions, and you get a house. The light
supplies the detail; the geometry supplies the silhouette.

A 1 cm bevel is the cheapest realism available: it gives every edge a highlight.

## 10. Lighting is the largest quality lever, and it is data

The difference between a game that looks like PS5 and one that looks like PS3 is
usually one number: how bright the sky is. Light the world from the sky and
nothing you place can create mood; dim the sky, let one hero light do the work,
and let everything else fall off into black — that fall-off *is* depth.

So lighting lives in `GDLightingRig.PRESETS` as named, diffable numbers, and the
tuning surface is an in-game panel with sliders (F9) whose "Copy preset" button
turns a human's taste into source code.

## 11. Shadows are the bill, not lights

A light is cheap. A light that casts shadows makes the renderer draw the scene
again from that light's point of view. Six hundred visible objects become
fourteen thousand draws with a handful of shadow-casting lamps in a corridor.

First move when the frame rate collapses: turn off every shadow except the hero
light's. If that fixes it, the fix is a shadow policy — not a mesh rebuild.
`GDLightingRig.enforce_shadows()` applies the policy and warns when it has to.

## 12. Accumulating world state goes in one fixed-size image

Footprints, scorch marks, snow compression, blood: do not keep a list of
instances. Paint into one render target of fixed size that the shader reads and
the wind erases. A thousand tracks then cost exactly what one costs, and memory
never grows.

Same principle for queries: never ask about the whole map. Ask about the 120
metres around the player, and slide that window with them. And do not cache what
changes — a boot compresses snow, wind builds a drift; the height is not a
constant, so asking every frame is correct.

## 13. Isolate before you debug

When something moves wrong, the first thing to build is not a fix — it is an
observation tool. A lab scene with one straight line in it. A button that steps
the creature one leg at a time. Then you can see what it is actually doing.

Locomotion and creature gait get fixed in `lab/`, never in the real level, where
six other systems are also moving.

## 14. Log the licence when the asset lands

Every asset that did not come out of our own generator gets a row in
`.planning/CREDITS.md` the moment it arrives — not at ship time, when nobody
remembers where the bear came from. An unattributed CC-BY asset is a shipping
blocker, and `/gd:ship` checks.

---

## Deviation rules for any job

When reality and the plan disagree mid-job:

1. **Missing critical functionality** the gate requires → add it, report it.
2. **Plan is wrong about the engine** → do it correctly, report it.
3. **The objective itself looks wrong** → stop and ask. Do not redesign
   unilaterally; a job that redesigns its own objective silently is how a
   milestone quietly becomes a different milestone.

Report deviations in the job's Result section. An unreported deviation is the
only real failure in this list.
