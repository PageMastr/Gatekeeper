---
description: Start a new game — verify the toolchain, scaffold the project, then run the kickoff interview that produces the contracts and roadmap
argument-hint: [the game idea, and/or a project name]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Skill, AskUserQuestion
---

# /gd:new — start a game from nothing

@gsd-gd/references/laws.md

Idea: **$ARGUMENTS**

This is the front door. It does the things that happen exactly once for a
project, then hands straight over to the kickoff interview.

It does **not** duplicate that interview — `/gd:plan` owns it, and you invoke it
at the end. Two copies of the same interview would drift apart within a week.

---

## 1. Where are we, and is this actually a new project?

```bash
python gsd-gd/bin/gd.py doctor
```

Read the `system` and `work` lines it prints. `work` is where `.planning/` and
`game/` will be created — **the directory you are working in**, not where the
system is installed. One install drives many games, and each one's contracts stay
in its own folder.

Two placements to catch before anything is written:

- **`work_root_outside_install` red** — you are inside the installed system.
  Stop; the game would be shared by every project on the machine and destroyed by
  the next upgrade. `gd init` refuses this outright.
- **`work_root_is_system_repo` red** — you are in the GSD-GameDev source
  checkout. A game created here lands in the system's own git history. Say so and
  ask where the game should live instead; `cd` there, or set `GD_PROJECT`.

**If `.planning/` already exists**, stop and resolve it before touching anything.
`.planning/` is per-directory, so there is one game's contracts per workspace — a
second game here would silently share the first one's Color Bible and Core Loop.
Use `AskUserQuestion` to offer:

- **Plan the next stage instead** → this is the same game, they wanted
  `/gd:plan`. Invoke that and stop.
- **Revisit the contracts** → the loop or palette is wrong, not the project.
  That is `/gd:frame`. Invoke that and stop.
- **Start this game over** → confirm explicitly, then `gd init "<Name>" --force`.
  Say plainly that it overwrites the existing contracts, and that the previous
  ones are recoverable from git history if the repo has any.
- **A genuinely separate game** → it needs its own directory. Say so; do not try
  to make one workspace hold two.

Never overwrite contracts without an explicit yes. They are the most expensive
artefact in the repo to recreate, because they encode decisions, not code.

## 2. Verify the toolchain before promising anything

Every hard check in `gd doctor` must pass. `planning_dir` and `godot_project` are
expected to fail here — that is what you are about to create.

**If `machine_config` is red, or Godot or Blender is missing**, run the wizard:

```bash
python gsd-gd/bin/gd.py setup
```

It searches this machine for both engines, verifies each by running it, prefers
the Windows `.console` build, and records what it found in
`~/.claude/gsd-gd.machine.json` — outside the install, so upgrading never
destroys it. If it cannot find something it asks for the path; in a
non-interactive session it reports its candidates and exits non-zero instead of
hanging, and you pass the path explicitly:

```bash
python gsd-gd/bin/gd.py setup --godot "<path>" --blender "<path>"
```

Never edit `gsd-gd/config.json` to fix a path. It is shipped, shared and replaced
on every upgrade; a path written there is gone at the next install and wrong for
every other user.

Do not scaffold a project you cannot build.

## 3. The API index

`gd setup` builds it. If you skipped setup because the toolchain was already
configured, confirm it is there:

```bash
python gsd-gd/bin/gddoc.py stats 2>/dev/null || python gsd-gd/bin/gddoc.py index
```

~1000 classes, from the engine's own class reference — read from a source
checkout if this machine has one, and otherwise generated from the binary with
`--doctool`. Every agent that writes GDScript depends on it; without it they fall
back on Godot 3 recall, which is the single largest source of broken code here.

## 4. Make sure git is live

```bash
git rev-parse --git-dir 2>/dev/null || git init
```

The system commits once per job so a failing job can be reverted alone. Without a
repo, `/gd:run`'s per-job commits silently do nothing and Law 2 stops working. If
you have to run `git init`, say so.

## 5. Name it

If `$ARGUMENTS` contains a plausible project name, use it and say which part you
took. Otherwise ask — one question, and offer a name derived from the idea so
there is something to accept.

The name becomes `game/<slug>/`, so keep it short and filesystem-safe. It is
awkward to change later; the slug ends up in scene paths.

```bash
python gsd-gd/bin/gd.py init "<Name>"
```

That writes the contract templates, scaffolds the Godot project with a **playable
greybox** already in it (floor, wall, character, lighting rig, F9 panel),
installs the playtest harness, creates `.planning/config.json` for this game's
own numbers, and generates `Palette` from the starting Color Bible.

## 6. Prove the scaffold works before interviewing anyone

```bash
python gsd-gd/bin/gd.py godot import
python gsd-gd/bin/gd.py check
python gsd-gd/bin/gd.py playtest minute_one
```

All three should pass on the fresh scaffold. If they do not, the problem is the
system, not the user's game — fix it and say so, rather than proceeding into a
design conversation on top of a broken harness.

## 7. Hand over to the kickoff interview

Now invoke the **`gd:plan`** skill, passing the idea from `$ARGUMENTS`.

If `$ARGUMENTS` contained `--then-run`, pass it through — `/gd:plan` will chain
into the driver rather than stopping after planning. Without it, an unattended
build parks itself after the interview and waits for a keystroke.

It will see unlocked contracts and enter KICKOFF mode: the interview (reference,
loop, tension, **systems**, **levels and distances**, session shape, one-way
doors, lighting condition, ordering), then `CONTEXT.md` → `COLOR_BIBLE.md` →
`CORE_LOOP.md` → `minute_one.json` → `ROADMAP.md`, then the first stage's job
decomposition, ending with the driver armed.

The roadmap is the big one: the whole game broken into stages that stack, with a
greybox block sized to this game, per-stage targets and pass conditions, a
systems inventory, a levels table, a coverage matrix and a placeholder ledger.
`gd roadmap` validates all of it and fails on a hole, so kickoff is not finished
until it passes.

Do not pre-answer its questions from `$ARGUMENTS`. Pass the idea through and let
it ask — the answers are the game, and guessing them is how you end up building
something adjacent to what the user wanted.

**And do not propose cutting anything.** If the game is large, the roadmap gets
more stages; that is what it is for (Law 13b).

## Finish

After the kickoff returns, report as one short block:

- toolchain: verified, and the resolved system / work roots
- project: name, path, scaffold gates green
- contracts: the one-sentence loop, the palette keys, the systems list
- roadmap: the stages in order, the greybox block, `gd roadmap` green, and what
  the first stage de-risks
- the next command: `/gd:run`

Then stop. Do not start building — `/gd:run` is a separate, deliberate step, and
the user may want to read the roadmap first.
