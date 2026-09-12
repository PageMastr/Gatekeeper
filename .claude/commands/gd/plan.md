---
description: Kickoff or next milestone — interviews you, writes the contracts and roadmap, then decomposes phase work into one-session jobs
argument-hint: [the game idea, or a milestone name; empty to continue from STATE.md]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, AskUserQuestion, Skill
---

# /gd:plan

@gsd-gd/references/laws.md
@gsd-gd/references/model-routing.md

Input: **$ARGUMENTS**

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

**If you are in KICKOFF and `.planning/` does not exist at all**, `/gd:new` is
the better front door — it verifies the toolchain, builds the API index, checks
git is live, and proves the scaffold's gates pass *before* anyone spends twenty
minutes designing on top of it. Say so and invoke the `gd:new` skill instead;
it will come back here for the interview. If `.planning/` already exists and the
contracts are merely unlocked, stay here and carry on.

---

# KICKOFF

The whole of beats 1 and 2, in one guided pass: interview → contracts →
roadmap → phase 1 plan, ending ready for `/gd:run`.

## 1. Scaffold

If `.planning/` does not exist, get a project name (ask if `$ARGUMENTS` does not
imply one) and:

```bash
python gsd-gd/bin/gd.py init "<Name>"
```

That creates the Godot project with a **playable greybox** already in it, the
harness, and the contract templates.

## 2. Interview

This is the part that cannot be automated, because the answers are the game. Use
`AskUserQuestion`, a few questions at a time, and **stop asking once the answers
stop changing the work**.

Cover, in this order — each answer constrains the next:

**The reference.** What made you want to build this? An image, a screenshot, a
game, a described scene. Ask for it. You are not copying it — you are catching
the same feeling. Pin down *what specifically* matters about it: the light? the
emptiness? the silhouette? And what is explicitly not being taken.

If there is no reference, get a description precise enough to argue with. "Cold,
empty, one warm light" is a reference. "Atmospheric" is not.

**The loop.** What does the player *do*, repeatedly, and why do they want to do
it again? Push until it fits one sentence of the form *the player does X to get Y
at the risk of Z*. If it takes a paragraph, it is several loops and none of them
is built yet — say so and narrow it.

**The tension.** What gets worse while the player does nothing? What can they do
about it? And what is the tradeoff that makes two players play differently? A
loop with no pressure is a chore list; pressure with no choice is a timer.

**The one-way doors.** Ask these explicitly, because they are expensive later:
perspective and camera (first/third person, fixed); 2D or 3D; whether the player
character is ever seen; single scene or streamed world. Record each with its
reason.

**The lighting condition.** What time of day, what weather, what light sources.
This determines the whole palette translation, so it is a question, not an
assumption.

**Scope.** What is deliberately *not* in the first milestone. Get three things
named. This is the question people most want to skip and most need.

## 3. Write the contracts

Now write, in this order, because each depends on the last:

**`.planning/CONTEXT.md`** — the reference, the settled decisions with reasons,
the one-way doors, the technical shape.

**`.planning/COLOR_BIBLE.md`** — the palette. The reference is almost never in
the game's lighting condition, so **translate it once, here**: record the
translation rule you applied, then every swatch with roughness, metallic,
emission and role. One warm family; shadow is a colour not `#000000`; emission
means information. Then:

```bash
python gsd-gd/bin/gd.py palette
python gsd-gd/bin/gd.py state palette_locked yes
```

**`.planning/CORE_LOOP.md`** — the one-sentence loop, the four-beat table where
beat 4 changes the state of beat 1, the tension, Minute One as a testable
sequence, and the scope fence.

```bash
python gsd-gd/bin/gd.py state loop_locked yes
```

**`game/<slug>/lab/minute_one.json`** — replace the seeded steps with the real
Minute One, then prove the harness runs (it may fail on content; that is fine,
a harness that does not run is a gate that does not exist):

```bash
python gsd-gd/bin/gd.py playtest minute_one
```

## 4. Write the roadmap — the whole game, in stackable stages

@gsd-gd/references/decomposition.md

This is the contract that guarantees the *whole* game gets built, in pieces
small enough to hold in one plan each. Read the reference above before writing
it; it carries the stage ladder and the ordering rules, both derived from builds
that actually shipped.

Fill in `.planning/ROADMAP.md` (already scaffolded from the template):

**The end state.** One sentence: what the finished thing is, and what "done"
means concretely enough to argue about.

**The stages.** Start from the ladder in the reference — greybox, core verb,
world system, placeholder pass, kit, props, hero asset, character, replace
placeholders, textures, lighting, performance, pressure, feedback, audio,
sequence — and then **cut what this game does not need**. A 2D game collapses
the kit/props/hero stages; a game with no enemies drops pressure. Cutting is
expected; forgetting is what the coverage matrix catches.

For each stage that survives:
- **Stage 1 is always the greybox.** Non-negotiable.
- `playable at the end` describes **something a person can do**, not a component
  that exists. "The cabin is built from kit pieces and walked through" stacks;
  "the kit is finished" does not — that is accumulation, and you cannot judge it.
- `depends on` names only **earlier** stages. The validator enforces this, and
  it is what makes the pieces stack rather than tangle.
- `gate` is the phase gate that stage's `PLAN.md` will carry.

**The coverage matrix.** Every beat of the Core Loop, plus every noun the game
needs, names the stage that delivers it. This is the mechanism that makes
"ensure the entire game gets built" real rather than aspirational — an element
with no stage is a hole, and it is enormously cheaper to find here than in month
two.

**The placeholder ledger.** Every primitive standing in for a real thing names
the stage that replaces it. This is the most forgettable work in a game build:
placeholders stop being visible once you stop noticing them, and then they ship.

**The one-way doors**, each assigned to the stage that takes it. **The risk
order**, saying what each early stage retires. **Not in this milestone**, with
reasons.

Then validate it — this is a gate, not a formatting check:

```bash
python gsd-gd/bin/gd.py roadmap
```

It fails on a stage that depends on a later stage, a placeholder `playable`/
`gate`/name, a Core Loop beat with no coverage row, and a coverage row or
placeholder pointing at a stage that does not exist. Fix the roadmap rather than
working around it; every one of those is a real hole.

Show the user the stage list and the risk order, and **get a yes before
decomposing**. This is the cheapest moment to reorder the whole project.

Then continue into **Decompose** below for **stage 1 only**. Do not plan stages
2+ in detail — they will be wrong by the time you reach them, and `/gd:ship`
revises the roadmap with what was actually learned.

---

# MILESTONE / Decompose

You are the orchestrator. **You do not build in this session.** The planning
context stays good precisely because it never fills with implementation.

```bash
python gsd-gd/bin/gd.py phase new "<milestone>"
```

Then fill in `.planning/phases/NN-<slug>/PLAN.md`:

## Objective and definition of done

One paragraph: what is true at the end that is not true now. Then the
**machine-readable phase gate** — this is what `/gd:run` drives toward:

```
- gate: python gsd-gd/bin/gd.py check
- gate: python gsd-gd/bin/gd.py playtest loop_complete
```

Every line must exit non-zero on failure. A phase whose gate you cannot write is
a phase that is not defined yet.

## Jobs

**One job = one fresh session = one testable gate.**

- If a job needs two sessions to hold in context, it is two jobs. Be ruthless —
  this is the decision the whole system rests on.
- **Write each job's gate before the job exists.** A job without a gate is a
  wish, and it must be runnable with no human needed for pass/fail.
- Fill the `touches` column, and the must-not-touch list in the job file.
- Leave `model` blank to use the agent's default from `config.json`
  (`gd models` shows the table). Set it only to deliberately start lower or
  higher; `/gd:run` escalates it on repeated failure.

Write each job as its own file from `gsd-gd/templates/JOB.md` into
`.planning/phases/NN-<slug>/jobs/`.

## Waves

Group by dependency, and state the disjointness analysis **explicitly** — not
"these look independent" but "job 1 touches only `scripts/terrain/`, job 2 only
`generators/`; no overlap."

`.tscn` files are the usual collision. Two agents editing one scene in parallel
produce an unreviewable merge. Serialise them, or have each build its own scene
and compose them in a later job.

## Checkpoints

Every one-way door gets a row in the Checkpoints table. `/gd:run` **halts** at
these and asks. A door taken inside a parallel wave is the most expensive
mistake available here, because you find out after four jobs have built on it.

## Sanity pass

- Does this milestone advance the Core Loop, or is it decoration? Decoration
  before the loop is complete is out of scope by definition.
- Is there a job proving the player can **lose**? Routinely forgotten, and it is
  half the loop.
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

Report: the contracts written (kickoff), the roadmap, the wave structure, the
checkpoints and why each is a door, and the one job you think is most likely to
fail with what you would try instead.

Then recommend `/gd:greybox` if the loop is not yet proven, otherwise `/gd:run`.
