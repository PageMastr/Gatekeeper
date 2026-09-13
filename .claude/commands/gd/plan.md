---
description: Kickoff or next milestone — interviews you, writes the contracts and roadmap, then decomposes stage work into one-session jobs
argument-hint: [the game idea, or a milestone name; empty to continue from STATE.md]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, AskUserQuestion, Skill
---

# /gd:plan

@gsd-gd/references/laws.md
@gsd-gd/references/model-routing.md

Input: **$ARGUMENTS**

If `$ARGUMENTS` contains `--then-run`, strip it and remember it: after the
driver is armed at the end, invoke the `gd:run` skill instead of stopping.
Without it, planning ends with a recommendation and waits for a human — which
parks an unattended build indefinitely.

## First, work out which mode you are in

```bash
python gsd-gd/bin/gd.py doctor
python gsd-gd/bin/gd.py state 2>/dev/null || echo "NO_PROJECT"
```

| situation | mode |
|---|---|
| no `.planning/`, or `loop_locked: no` / `palette_locked: no` | **KICKOFF** — run the whole interview below |
| contracts locked, no current phase | **MILESTONE** — skip to "Decompose" |
| contracts locked, current phase has a `PLAN.md` with jobs | already planned; report `run status` and recommend `/gd:run` |

State which mode you picked in one line before you start.

**If `gd doctor` reports `machine_config` missing**, stop and run
`gd setup` first — it autodetects Godot and Blender on this machine. There is no
point designing a game on a toolchain that is not there.

**If you are in KICKOFF and `.planning/` does not exist at all**, `/gd:new` is
the better front door — it verifies the toolchain, builds the API index, checks
git is live, and proves the scaffold's gates pass *before* anyone spends time
designing on top of it. Say so and invoke the `gd:new` skill instead; it comes
back here for the interview. If `.planning/` already exists and the contracts are
merely unlocked, stay here and carry on.

---

# KICKOFF

The whole of beats 1 and 2, in one guided pass: interview → contracts → roadmap
→ first stage plan, ending ready for `/gd:run`.

## 1. Scaffold

If `.planning/` does not exist, get a project name (ask if `$ARGUMENTS` does not
imply one) and:

```bash
python gsd-gd/bin/gd.py init "<Name>"
```

That creates the Godot project with a **playable greybox** already in it, the
harness, and the contract templates.

## 2. The interview

This is the part that cannot be automated, because the answers *are* the game.
Use `AskUserQuestion`, a few questions at a time. Every answer constrains the
next, so keep the order.

### The standing rule for this whole interview

**You are not here to reduce scope.** Never propose cutting a feature, never ask
what the user is willing to drop, and never describe something they want as "out
of scope". If the game is big, the roadmap gets more stages — that is what the
roadmap is for, and `gd roadmap` will keep them honest.

The only scope question you may ask is about **order**: what the player should
touch first, and what depends on what. Everything else gets a stage number, even
if that number is 19.

If something genuinely cannot be built — it needs an asset pipeline that does
not exist, or it contradicts a decision already locked — say that specifically,
say what it would take, and let the user decide. That is different from asking
them to trim.

### 2.1 The reference

What made you want to build this? An image, a screenshot, a game, a described
scene. Ask for it. You are not copying it — you are catching the same feeling.

Pin down *what specifically* matters about it: the light? the emptiness? the
silhouette? the pace? And what is explicitly **not** being taken from it.

If there is no reference, get a description precise enough to argue with. "Cold,
empty, one warm light" is a reference. "Atmospheric" is not.

### 2.2 The loop

What does the player *do*, repeatedly, and why do they want to do it again?

Push until it fits one sentence of the form **the player does X to get Y at the
risk of Z**. If it takes a paragraph, it is several loops — name each of them and
ask which one the game is actually about; the others become systems that feed it,
not competing loops.

Then the four beats, explicitly: what the player reads, what they decide, what
they do, and **what changes as a result so that turn two is different from turn
one**. That fourth beat is the one that gets skipped, and a loop without it is a
treadmill that will pass every gate and still be unplayable.

### 2.3 The tension

- What gets **worse** while the player does nothing?
- What can they do about it?
- What is the **tradeoff** that makes two players play differently?

A loop with no pressure is a chore list; pressure with no choice is a timer.

And: **how does the player lose?** Ask it plainly. Half of every loop is the
failure state, and it is the half almost every first pass forgets.

### 2.4 The systems — go wide here

This is the section that most determines whether the roadmap is any good, so
spend real time on it. A **system** is anything with state that changes over time
and feeds the loop: fuel, heat, faith, inventory, a day clock, weather, an AI, a
reputation, a save. Not a noun — a *behaviour*.

Work through, one at a time, and write each down as you go:

- **What state does it hold?** One number, a set of flags, a grid, a texture?
- **What changes it?** The player, time, another system, the world?
- **What does the player see of it?** A system the player cannot read is a system
  that does not exist to them — and that is a job in its own right.
- **What does it do to the loop?** If the answer is "nothing yet", it is either a
  later stage or it is decoration; say which.
- **What does it interact with?** Systems that touch each other must be
  greyboxed in the same stage or in a stated order, because tuning one moves the
  other.

Keep asking "and what else does the world do while the player is doing that?"
until the answers stop being new. Then read the list back and ask what is
missing. People remember the fourth system when they see the first three.

Aim to come out of this with a list you could hand to a programmer, not a mood:
each system named, its state, its inputs, its visible output.

### 2.5 The world — levels, maps and distances

The other half of the plan, and the half that is usually left until it is
expensive.

- **What spaces exist?** Name every one the player can be in.
- **How big is each, in metres?** Push for real numbers. A corridor someone
  hurries down is 1.6–2.0 m wide. A room that should feel exposed is not 4×4. If
  the user does not know, offer a number with a reason and let them correct it —
  that is much easier than answering from nothing.
- **How do they connect?** Draw the graph in text. Which are dead ends, which are
  loops, where does the player enter?
- **What happens in each?** A space with no answer is a space that does not need
  to exist yet — or a space nobody has designed.
- **How long does it take to cross?** Distance is a cost. If walking to the
  woodline is meant to be a decision, it has to take long enough to be one.
- **Is the world fixed, or generated?** If generated: what are the rules, what
  must always be true of an instance, and what does a bad instance look like?
- **Where does the pressure come from**, spatially? Where is the player safe?

For anything larger than a few rooms, sketch the map as an ASCII diagram in the
conversation and get a yes on it. It is enormously cheaper to argue with a
diagram than with a built blockout.

### 2.6 The shape of a session

- How long is one sitting?
- What does the player have at the start, and what do they have at the end?
- Is there progression across sessions, or does each one start clean?
- What is **Minute One** — the first sixty seconds, as a sequence of concrete
  actions? This becomes a playtest plan, so it has to be specific enough to
  script.

### 2.7 The one-way doors

Ask these explicitly, because they are expensive later. Record each with its
reason:

- perspective and camera — first person, third person, fixed, isometric
- 2D or 3D
- whether the player character is ever seen (it decides whether a character
  stage exists at all)
- single scene or streamed world
- animation approach — rigged clips, or procedural in the engine
- coordinate scale (default: 1 unit = 1 metre; only change this deliberately)

### 2.8 The lighting condition

What time of day, what weather, what light sources, and what the darkest part of
the frame should still tell you. This determines the whole palette translation,
so it is a question, not an assumption.

### 2.9 Order, not scope

The only prioritisation question:

> Of everything we have listed, **what does the player touch first**, and what
> would you most regret getting wrong?

Use the answer to order the stages and to decide what the greybox block proves
first. Nothing is dropped. Anything that clearly depends on something else goes
in **Later stages** in the roadmap *with the stage number it will get*.

### When to stop asking

Stop when new answers stop changing the stage list — not when you have hit a
question count. If you can already write the systems inventory, the levels table
and the four loop beats without guessing, you are done.

## 3. Write the contracts

Now write, in this order, because each depends on the last:

**`.planning/CONTEXT.md`** — the reference, the settled decisions with reasons,
the one-way doors, the technical shape, the systems list and the map sketch.

**`.planning/COLOR_BIBLE.md`** — the palette. The reference is almost never in
the game's lighting condition, so **translate it once, here**: record the
translation rule you applied, then every swatch with roughness, metallic,
emission and role. One warm family; shadow is a colour, not `#000000`; emission
means information. Then:

```bash
python gsd-gd/bin/gd.py palette
python gsd-gd/bin/gd.py state palette_locked yes
```

**`.planning/CORE_LOOP.md`** — the one-sentence loop, the four-beat table where
beat 4 changes the state of beat 1, the tension, the failure state, Minute One
as a testable sequence.

```bash
python gsd-gd/bin/gd.py state loop_locked yes
```

**`game/<slug>/lab/minute_one.json`** — replace the seeded steps with the real
Minute One. Lint it, then prove the harness runs in **smoke mode**:

```bash
python gsd-gd/bin/gd.py playtest minute_one --lint
python gsd-gd/bin/gd.py playtest minute_one --smoke
```

`--smoke` gates on the harness booting, the scene loading and screenshots being
written, and records checks against not-yet-existing content as **pending**
rather than failed. Without it, kickoff leaves a `verdict.json` that says
`passed: false` and is indistinguishable from a real regression for the rest of
the project.

## 4. Write the roadmap — the whole game, in stackable stages

@gsd-gd/references/decomposition.md

Read that reference before writing this; it carries the stage ladder, the
greybox block rules and the ordering rules, all derived from builds that
actually shipped.

Fill in `.planning/ROADMAP.md` (already scaffolded from the template). Every
section below is validated, so none of them is optional.

**The end state.** One sentence: what the finished thing is, and what "done"
means concretely enough to argue about.

**The greybox block.** Size it from the interview — count the systems from 2.4
and the spaces from 2.5:

| systems + spaces | block |
|---|---|
| one system, one space | 01 alone |
| two or three systems, a few spaces | 01–02 |
| several systems, distinct areas | 01–04 |
| many interacting systems, a large world | 01–06 |

Mark those stages `greybox` in the `block` column, make them contiguous from 01,
and set `- greybox block:` to the last one. Split by **space** or by **system**,
never by layer — "all the scripts then all the scenes" produces stages that are
not playable, which defeats the point.

The block must cover the **whole** game in grey: every space walkable at real
distances, every system running and observable, the loop closing, and a
reachable failure state in the last stage. Tuning happens inside the block, at
the end of each stage.

**The stages.** For each one:
- `playable at the end` describes **something a person can do**, not a component
  that exists. "The cabin is built from kit pieces and walked through" stacks;
  "the kit is finished" does not — that is accumulation, and you cannot judge it.
- `depends on` names only **earlier** stages. The validator enforces it, and it
  is what makes the pieces stack rather than tangle.
- `gate` is the phase gate that stage's `PLAN.md` will carry.

**Stage targets and pass conditions.** Every stage says what it is *for* and
exactly what must hold at the end. This is Law 4 one level up: a stage whose pass
conditions you cannot write is a stage that is not defined yet. Numbers where
numbers exist — this is what that stage's gate will have to assert, so vagueness
here becomes a gate that cannot fail usefully.

**The systems inventory.** Every system from 2.4, with the greybox stage that
proves it and the stage that finishes it. The greybox stage must be inside the
block: every system runs in grey before any of them is made to look good.

**The levels table.** Every space from 2.5, with its size in metres and the
greybox stage that blocks it out. Every space is blocked out inside the block.

**The coverage matrix.** Every beat of the Core Loop, plus every noun the game
needs, names the stage that delivers it. This is what makes "the entire game gets
built" real rather than aspirational.

**The placeholder ledger.** Every primitive standing in for a real thing names
the stage that replaces it. The most forgettable work in a game build.

**The one-way doors**, each assigned to the stage that takes it. **The risk
order**, saying what each early stage retires. **Later stages**, each with the
stage number it will get — this is a schedule, not a graveyard.

Then validate. This is a gate, not a formatting check:

```bash
python gsd-gd/bin/gd.py roadmap
```

Fix the roadmap rather than working around it; every failure it reports is a
real hole. Show the user the stage list, the greybox block and the risk order,
and **get a yes before decomposing**. This is the cheapest moment the project
will ever have to reorder itself.

## 5. Set the budget, then commit the contracts

**`.planning/BUDGET.md` is a contract too, and it is the one that gets
forgotten.** Observed across three separate games: not one kickoff touched it, so
all three inherited the shipped defaults regardless of scope — and nobody finds
out until the performance stage fails against numbers nobody chose.

Now that the roadmap describes the real scene scope, set it:
- name the target (desktop / handheld / web) — it changes every other number
- scale `max_draw_calls` and the per-class triangle budgets to what the levels
  table actually describes
- if the defaults are genuinely right, **say so in Deviations** with a date. An
  unreviewed contract is indistinguishable from a forgotten one.

Numbers live in `.planning/config.json`; `BUDGET.md` is where they are justified.
Change both together — never the shipped `gsd-gd/config.json`, which is every
game on the machine.

```bash
python gsd-gd/bin/gd.py config          # confirm the override landed
```

Then **commit**. The contracts are the most expensive artefact in the project —
they encode decisions, not code — and until now they have been one bad edit from
gone.

```bash
git add -A && git commit -m "kickoff: contracts, roadmap and budget for <Name>"
```

Then continue into **Decompose** below for **stage 01 only**. Do not plan later
stages in detail — they will be wrong by the time you reach them, and `/gd:ship`
revises the roadmap with what was actually learned.

---

# MILESTONE / Decompose

You are the orchestrator. **You do not build in this session.** The planning
context stays good precisely because it never fills with implementation.

Read the stage's row in `ROADMAP.md` and its **target and pass conditions**
before anything else. The plan you write has to deliver exactly that, and the
phase gate has to assert exactly those pass conditions. If the pass conditions
cannot be turned into runnable commands, fix the roadmap row first — do not
invent a weaker gate here.

```bash
python gsd-gd/bin/gd.py phase new "<milestone>"
```

Then fill in `.planning/phases/NN-<slug>/PLAN.md`:

## Objective and definition of done

One paragraph: what is true at the end that is not true now — taken from the
stage's target, not reinvented. Then the **machine-readable phase gate**, which
is what `/gd:run` drives toward and must cover every pass condition in the
roadmap row:

```
- gate: gd check
- gate: gd playtest loop_complete
```

**Write gate lines in the short `gd ...` form.** `gd run gate` resolves `gd` and
`gddoc` against whichever install is running, so `PLAN.md` stays portable. A
repo-relative `python gsd-gd/bin/gd.py ...` resolves only inside the system's own
checkout — in a normal install it fails with `can't open file .../<game>/gsd-gd/
bin/gd.py`, which reads as a broken project rather than a broken gate. Anything
that is not a `gd` command runs as written.

Every line must exit non-zero on failure. A phase whose gate you cannot write is
a phase that is not defined yet.

## Jobs

**One job = one fresh session = one testable gate.**

- If a job needs two sessions to hold in context, it is two jobs. Be ruthless —
  this is the decision the whole system rests on.
- **Write each job's gate before the job exists.** A job without a gate is a
  wish, and it must be runnable with no human needed for pass/fail.
- Fill the `touches` column, and the must-not-touch list in the job file.
- Leave `model` blank to use the agent's default from config (`gd models` shows
  the table). Set it only to deliberately start lower or higher; `/gd:run`
  escalates it on repeated failure.

Write each job as its own file from `gsd-gd/templates/JOB.md` into
`.planning/phases/NN-<slug>/jobs/`.

### If this is a greybox stage

It must produce enough jobs to actually build that slice of the game end to end,
not a token pass. Expect, at minimum:

- **one blockout job per space** the stage owns, each ending in a walk-through
  playtest that names the nodes traversed — a `moved` check with `via`, never a
  bare distance. A distance-only check is satisfied by any open floor, and that
  is how a check named `walked_the_spine` passed at 41 m in a scene with no
  spine.
- **one job per system** the stage owns, each with a `lab/` scene that makes the
  system observable on its own before it is wired into the level (Law 13).
- **wiring jobs**, serialised, because they touch shared scenes.
- **a tuning job at the end**, adjusting distances, rates and timings against
  measured numbers from the playtests rather than guesses. A greybox whose
  numbers were never tuned proves the loop runs, not that it is worth running.
- **a partial-input plan** in the last greybox stage: press only the first half
  of every multi-press interaction and assert the game does not lie about it.

If that job list will not fit one plan, **the stage is too big — split it in the
roadmap** and re-run `gd roadmap`. Do not thin the job list to fit; that is
cutting the game to fit the plan, which is the one thing this system does not do.

### The gates job — always emit one, always first

**Law 6 says a builder never grades its own work, and per-job gates broke it.**
Observed: an implementing agent wrote its own six-check gate and then passed it.
Nothing was wrong with the work, but the test that certified it was written by
the thing being certified, and no mechanism noticed.

So **job 01 of every phase is a `gd-playtester` job, alone in wave 1, that
authors every playtest plan the phase's gates name** — including the phase
gate's. Implementing agents may then only *run* those plans, never write or edit
them.

Its own gate is lint, which needs no game to exist yet:

```
| 1 | Gates written ahead | gd-playtester | | 1 | lab/*.json | gd playtest <each plan> --lint |
```

If a later job finds its gate genuinely wrong, that is a deviation to report —
the fix goes back through `gd-playtester`, not into the builder's own hands.

**Never put a `lab/*.json` path in a builder's `touches`.** Two projects
independently hit the same contradiction: a job file told a builder the plan was
"yours to write" while the builder's own brief forbade exactly that, and nothing
said which won. `gd run init` now refuses a plan that does this, so the
precedence is settled where it cannot be missed: **the agent brief wins, builders
never author gates.** A builder's `touches` may name the code under test; the
plan that grades it belongs to the gates job.

## Waves

Group by dependency, and state the disjointness analysis **explicitly** — not
"these look independent" but "job 1 touches only `scripts/terrain/`, job 2 only
`generators/`; no overlap."

`.tscn` files are the usual collision. Two agents editing one scene in parallel
produce an unreviewable merge. Serialise them, or have each build its own scene
and compose them in a later job.

## Checkpoints

Every one-way door gets a row in the Checkpoints table. `/gd:run` **halts** at
these and asks. A door taken inside a parallel wave is the most expensive mistake
available here, because you find out after four jobs have built on it.

## Sanity pass

- Does this stage deliver its roadmap target, and does the gate assert its
  roadmap pass conditions? Check them off one by one.
- Is there a job proving the player can **lose**, if this is the last greybox
  stage? Routinely forgotten, and it is half the loop.
- Does any job depend on taste rather than a measurement? Route it to
  `/gd:gauntlet` rather than hoping one pass lands it.
- Prefer a **tracer** over a layer: one crate generated, imported, placed, lit
  and playtested de-risks more than a finished kit with no scene.

## Arm the driver

```bash
python gsd-gd/bin/gd.py run init
python gsd-gd/bin/gd.py run next      # confirm it parsed the plan as you intended
```

If `run init` reports fewer jobs or waves than you wrote, the tables are
malformed — fix `PLAN.md`, do not work around it.

## Finish

```bash
python gsd-gd/bin/gd.py state phase "NN-<slug>"
python gsd-gd/bin/gd.py state beat build
```

Report: the contracts written (kickoff), the roadmap with its greybox block, the
wave structure, the checkpoints and why each is a door, and the one job you think
is most likely to fail with what you would try instead.

**If `--then-run` was passed**, invoke the `gd:run` skill now and let it drive.
Otherwise end with the next command on its own line, as the last thing you say —
not buried under the report:

```
/gd:run
```
