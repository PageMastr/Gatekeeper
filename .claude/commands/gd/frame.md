---
description: Beat 1 — turn an idea into contracts: reference, Color Bible, Core Loop, Minute One
argument-hint: [idea, or a path/URL to a reference image]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# /gd:frame — lock the contracts before anything is built

> **Most of the time you want `/gd:plan` instead.** At kickoff `/gd:plan` runs
> this interview *and* the roadmap *and* phase 1's decomposition in one guided
> pass. Use `/gd:frame` when the contracts alone need revisiting — the loop is
> not working, or the palette is fighting the assets — without re-planning.

@gsd-gd/references/laws.md

Read the laws above. This beat exists to satisfy Law 1 (the loop before the look)
and Law 8 (the Color Bible is a contract). Nothing else runs until both are
locked, because everything downstream reads them.

Idea / reference from the user: **$ARGUMENTS**

## Before you start

```bash
python gsd-gd/bin/gd.py doctor
python gsd-gd/bin/gd.py state
```

If `.planning/` does not exist yet, ask for a project name and run
`gd init "<name>"`. If it does, you are refining existing contracts — read them
first and do not silently discard what is there.

## What you produce

Four things, in this order. Each is a file, not a conversation.

### 1. The reference

The thing that made someone want to build this. A Pinterest image, a screenshot,
a photograph, a description. Not to copy — to catch the same feeling.

Record in `.planning/CONTEXT.md`: what it is, what specifically about it matters
(the light? the silhouette? the emptiness?), and what it is explicitly *not*
(we are not copying the art style / the genre / the camera).

If the user has no reference, ask for one or generate a description precise
enough to argue with. "Cold, empty, one warm light" is a reference. "Atmospheric"
is not.

### 2. `.planning/COLOR_BIBLE.md`

The reference is almost never in the game's lighting condition. A daylight
photograph feeding a night game must be **translated once, here** — never
per-asset, or every asset drifts on its own.

Fill in:
- the reference's lighting condition, and the game's
- the translation rule you applied (how saturation, value and hue move)
- every swatch: key, hex, roughness, metallic, emission, role

Rules to honour while choosing: one warm family only; shadow is a colour, never
`#000000`; emission means information, not decoration; roughness carries material
identity more than hex does.

Then:
```bash
python gsd-gd/bin/gd.py palette      # regenerates res://scripts/palette.gd
python gsd-gd/bin/gd.py state palette_locked yes
```

### 3. `.planning/CORE_LOOP.md`

The part projects die without. Answer, concretely:

- **One sentence:** the player does X to get Y at the risk of Z.
- **The loop table:** four beats, and beat 4 must change the state of beat 1. If
  the loop returns to identical starting conditions it is a treadmill.
- **Tension:** what gets worse while the player does nothing; what they can do
  about it; the tradeoff that makes two players play differently.
- **Scope fence:** what is explicitly *not* in the first milestone. Name it now
  so it can be defended later, when it looks cheap mid-build.

Do not accept a loop you cannot describe in one sentence. If it takes a
paragraph, it is several loops and none of them is built yet.

### 4. Minute One + its playtest plan

The first 60 seconds as a testable sequence, in `CORE_LOOP.md`, then written as
`game/<slug>/lab/minute_one.json` (`gd init` seeds a starting version — replace
its steps with the real ones).

@gsd-gd/references/playtest-recipes.md

Then prove the harness runs against it, even if it fails on content:
```bash
python gsd-gd/bin/gd.py playtest minute_one
```
A harness that does not run is a gate that does not exist.

## Ask, don't assume

Use `AskUserQuestion` for exactly the decisions that change the work:
- the feeling being chased, when the reference is ambiguous
- the loop's central tradeoff, if two readings lead to different games
- perspective and camera (first/third person, fixed) — a one-way door

Do not ask about things you can pick sensibly and note as an assumption.

## Finish

```bash
python gsd-gd/bin/gd.py state beat plan
python gsd-gd/bin/gd.py state loop_locked yes
```

Update STATE.md's "What just happened" / "What is next", then report to the user:
the one-sentence loop, the palette keys, the scope fence, and any assumption you
made on their behalf. Recommend `/gd:plan`.
