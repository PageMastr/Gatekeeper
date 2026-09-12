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

## 1. Is this actually a new project?

```bash
python gsd-gd/bin/gd.py state 2>/dev/null || echo "NO_PROJECT"
ls game/ 2>/dev/null
```

**If `.planning/` already exists**, stop and resolve it before touching
anything. `.planning/` is repo-level, so there is one game's contracts per
checkout — a second game here would silently share the first one's Color Bible
and Core Loop. Use `AskUserQuestion` to offer:

- **Plan the next milestone instead** → this is the same game, they wanted
  `/gd:plan`. Invoke that and stop.
- **Revisit the contracts** → the loop or palette is wrong, not the project.
  That is `/gd:frame`. Invoke that and stop.
- **Start this game over** → confirm explicitly, then `gd init "<Name>" --force`.
  Say plainly that it overwrites the existing contracts, and that the previous
  ones are recoverable from git history if the repo has any.
- **A genuinely separate game** → it needs its own directory. Say so; do not
  try to make one checkout hold two.

Never overwrite contracts without an explicit yes. They are the most expensive
artefact in the repo to recreate, because they encode decisions, not code.

## 2. Verify the toolchain before promising anything

```bash
python gsd-gd/bin/gd.py doctor
```

Every hard check must pass. `planning_dir` and `godot_project` are expected to
fail here — that is what you are about to create.

If Godot or Blender is missing, stop and report the exact path that is wrong.
The paths live in `gsd-gd/config.json` and nowhere else, so that is the one file
to fix. Do not scaffold a project you cannot build.

## 3. Build the API index if it is not there

```bash
python gsd-gd/bin/gddoc.py stats 2>/dev/null || python gsd-gd/bin/gddoc.py index
```

~8 seconds, 1071 classes, from the engine's own source tree. Every agent that
writes GDScript depends on it — without it they fall back on Godot 3 recall,
which is the single largest source of broken code here.

## 4. Make sure git is live

```bash
git rev-parse --git-dir 2>/dev/null || git init
```

The system commits once per job so a failing job can be reverted alone. Without
a repo, `/gd:run`'s per-job commits silently do nothing and Law 2 stops working.
If you have to run `git init`, say so.

## 5. Name it

If `$ARGUMENTS` contains a plausible project name, use it and say which part you
took. Otherwise ask — one question, and offer a name derived from the idea so
there is something to accept.

The name becomes `game/<slug>/`, so keep it short and filesystem-safe. It is
awkward to change later; the slug ends up in scene paths.

```bash
python gsd-gd/bin/gd.py init "<Name>"
```

That writes the contract templates, scaffolds the Godot project with a
**playable greybox** already in it (floor, wall, character, lighting rig, F9
panel), installs the playtest harness, and generates `Palette` from the starting
Color Bible.

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

It will see unlocked contracts and enter KICKOFF mode: the interview (reference,
loop, tension, one-way doors, lighting condition, scope), then
`CONTEXT.md` → `COLOR_BIBLE.md` → `CORE_LOOP.md` → `minute_one.json` →
`ROADMAP.md`, then stage 1's job decomposition, ending with the driver armed.

The roadmap is the big one: the whole game broken into stages that stack, each
ending in something playable, with a coverage matrix that assigns every Core
Loop beat and every required element to a stage. `gd roadmap` validates it and
fails on a hole, so kickoff is not finished until it passes.

Do not pre-answer its questions from `$ARGUMENTS`. Pass the idea through and let
it ask — the answers are the game, and guessing them is how you end up building
something adjacent to what the user wanted.

## Finish

After the kickoff returns, report as one short block:

- toolchain: verified (and anything you had to fix)
- project: name, path, scaffold gates green
- contracts: the one-sentence loop, the palette keys, the scope fence
- roadmap: the stages in order, `gd roadmap` green, and what stage 1 de-risks
- the next command: `/gd:run`

Then stop. Do not start building — `/gd:run` is a separate, deliberate step, and
the user may want to read the roadmap first.
