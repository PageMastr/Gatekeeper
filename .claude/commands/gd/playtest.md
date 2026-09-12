---
description: Beat 6 — measure, look, and check budgets; a builder never grades its own frames
argument-hint: [plan name, or empty for every plan in lab/]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent
---

# /gd:playtest — measure, look, budget

@gsd-gd/references/playtest-recipes.md
@gsd-gd/references/laws.md

Plan: **$ARGUMENTS** (empty = every plan in `game/<slug>/lab/`)

Law 5: verification is measure **and** look, plus a human. Skipping the look pass
is how a game ends up technically correct and visually broken; skipping the
measure pass is how it ends up pretty and unplayable.

## 1. Measure

```bash
python gsd-gd/bin/gd.py playtest <plan>
```

Runs every plan if none is named:
```bash
for p in game/*/lab/*.json; do python gsd-gd/bin/gd.py playtest "$p"; done
```

Read the `detail` on **every** check, passing ones included. A check that
passes for the wrong reason (the player "moved 4 m" because they fell off the
map) is worse than a failure, because it buys false confidence.

Watch for:
- `runtime_errors` — non-empty fails the verdict. The harness cannot see script
  errors; the process output can.
- `budget_fails` — fps, draw calls, shadow-casting light count.
- `input_action:<name>` failures — the plan and `project.godot` have drifted.

## 2. Look

The same run wrote `.gd_out/<plan>/shots/*.png`.

Spawn **`gd-critic`** with the shots, the Color Bible, and the scene's intent.
Give it no code and no build history. If you built the thing being tested in
this session, you are disqualified from judging it — that is not a formality,
it is the mechanism: you will see what you intended rather than what is there.

Ask the critic for findings of the kind an assertion cannot produce:
- Is the space readable? Can you tell where to go?
- Is the silhouette legible against its background?
- Does the hero light carry the frame, or is the sky doing the work?
- Are there colours outside the Color Bible?
- Texture scale: does anything read as the wrong material?
- Is anything floating, z-fighting, clipping, or scaled wrong?

## 3. Human

Hand the user the build, or the shots if they would rather look than play. The
two automated passes exist so their attention goes to taste, not to catching
crashes. Ask one specific question, not "how is it?" — for example: *does the
corridor feel as long as it should?*

## 4. Triage

| symptom | where to go |
|---|---|
| a check failed | one job goes back — `/gd:build` with that job alone |
| budget failed | `/gd:perf` |
| critic says it looks wrong, numbers fine | `/gd:gauntlet` on that asset, or `/gd:light` |
| the loop is not fun | `/gd:frame` — the fix is in `CORE_LOOP.md`, not the code |
| harness produced no verdict | the harness scene failed to load; check the log tail for a parse error |

## Finish

```bash
python gsd-gd/bin/gd.py state last_verdict "<n passed, m failed>"
```

Report: each plan's verdict with its numbers, the critic's findings verbatim
(do not soften them), the user's reaction, and the single next action.
