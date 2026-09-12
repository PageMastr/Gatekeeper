# Field notes — Ringfall (D:/TestGame) observed against GSD-GameDev

A running log from a 10-loop observation of the system building a real game, so
we can improve the base system tomorrow. One entry per loop, appended.

**The game under test:** *"Rebuild a shattered ring station one module at a time
while managing air, heat, and a crew that's losing faith."* Kicked off with
`/gd:new`, interview completed by the user.

**Observer cadence:** hourly at :47 (cron `82df0d8a`). 45m was rounded up —
`*/45` fires at :00 then :45, giving alternating 45/15-minute gaps.

## Methodology caveat, learned the hard way in loop 1

**The target is a live session that is actively writing files.** In loop 1 I read
`COLOR_BIBLE.md`, found it byte-identical to the template with foliage keys on a
space station, and nearly recorded that as the headline failure. Thirty seconds
later the same file was a locked, 17-key, fully-reasoned contract — the agent had
been mid-write.

So, for every later loop: **timestamp the read, check mtimes, and re-read before
asserting anything is wrong.** A single-pass read of a live workspace produces
false findings. Distinguish *"the system failed to do X"* from *"the system has
not reached X yet"* — at t+0 of a build almost everything is the latter.

---

# Loop 1 — 18:11Z · baseline

State: **mid-kickoff.** `/gd:new` ran at 17:48, contracts being written since.
Nothing built yet. `beat: frame`, `phase: none`, `.planning/phases/` empty.

Timeline from mtimes: init 17:48 → CORE_LOOP 18:05 → ROADMAP 18:08 →
COLOR_BIBLE locked 18:09:49 → palette synced + STATE 18:10:23 → CONTEXT 18:10:34.
**~22 minutes from cold start to locked contracts**, which is inside the 15–30
min the quickstart promises.

## What the system got right

This is worth recording as carefully as the faults, because it tells us which
parts not to touch.

**The Core Loop came out genuinely good.** One sentence: *"The player spends
their crew's faith to get hands for an EVA salvage run, in order to bring one
more dark module online and repay that faith with light and heat."* Beat 4 does
change beat 1 — the module lights up, capacity rises, faith is repaid. That is
the exact shape `CORE_LOOP.md` demands and the hardest thing to get out of an
interview.

**The Color Bible is better than the template it came from.** 17 keys, and the
change log gives a reason for all 17. The decisions it made on its own:
- added `void_dark` because *"interior shadow and exterior shadow are different
  colours"* — a distinction the template does not make and this game needs
- added `tape` because *"the reference is duct tape. The one material that says
  a person has been here"*
- added `sun_raw` as *"the resolution of the one-warm-family problem"* — it hit
  the palette's own one-warm-family rule, recognised the conflict, and solved it
  rather than ignoring the rule
- added `frost`, tied to the cold-is-visible mechanic
- **cut `organic_dark`/`organic_light`** with the reason *"template foliage keys.
  The station is…"*

That last one is the strongest signal in this loop: the template's defaults did
not survive contact with the game, and the system's "add the row **and** the
reason" rule produced a real audit trail instead of silent drift.

**The roadmap validated on the first try.** 17 stages, 37 coverage rows, 12
placeholders, `gd roadmap` green — every stage stacks forward, every Core Loop
beat assigned, every placeholder has a replacing stage. The stage ladder from
`decomposition.md` was clearly followed and then adapted: it inserted
*"crew and faith system"* and *"ring-dawn clock and Wreck"* as stages 04–05,
which are this game's real risks, ahead of the generic asset stages.

## Confirmed faults — ours, not the game's

### 1. The kickoff smoke-test playtest produces a misleading verdict
`lab/minute_one.json` was written with **18 checks** asserting against
`Station/Modules/Hab`, `Crew/Mika`, `Clock`, `Planet` — none of which exist yet.
It ran, produced 7 screenshots, and 15 of 18 checks failed.

The agent did exactly what `/gd:plan` tells it to: *"prove the harness runs
against it, even if it fails on content."* But the artefact left behind is a
`verdict.json` with `passed: false`, which is indistinguishable from a real
regression, and `last_verdict` would read as a failure from here on.

**Fix:** add `gd playtest --smoke`, which asserts only that the harness booted,
the scene loaded, and screenshots were written — and records the content checks
as *pending* rather than *failed*. Kickoff should call that, not a full gate.

### 2. A check passed for the wrong reason — the exact failure our own docs warn about
`player_walked_the_spine` **passed**: `path=41.450 straight=19.841 need>=8.000`.
There is no spine. The player walked 41 m across the bare greybox floor.

`playtest-recipes.md` says a check that passes for the wrong reason *"is worse
than a failure, because it buys false confidence"* — and then we shipped no
mechanism to catch it. A `moved` check is satisfied by any open floor.

**Fix:** a `moved` check should be able to require *what* was traversed, not just
how far — e.g. `"via": ["Spine/Seg01", "Spine/Seg02"]` asserting the probe
entered named areas in order. Cheap to add to the harness and it makes distance
checks meaningful. Second, smaller: report `straight/path` ratio as a signal —
41 m of path for 20 m of displacement means wandering, not traversal.

### 3. `Expression` check failures lose their error text
Two failures read `execute failed: On call to 'get_child_count':` — truncated
mid-sentence — and `execute failed: Invalid named index 'needed_part' for base
type Object`, which does not say *which* node was Object-typed.

`gd_playtest.gd` reports `e.get_error_text()` but Godot's `Expression` puts the
useful part elsewhere, and we throw away the node context we already have.

**Fix:** include the expression source, the resolved base node's path and class,
and the full error text. An `expr` failure should be debuggable without
re-running.

### 4. A missing input action doesn't say what actions exist
`input_action:confirm` failed correctly — the plan pressed `confirm`, the project
ships `interact`. The harness caught a genuine drift, which is the design
working. But the message gives no way to fix it in one step.

**Fix:** on a missing action, list the actions that *do* exist in the InputMap.
One line, removes a whole lookup round-trip.

### 5. Hand-written timestamps are invented
The Color Bible change log stamps 16 rows `2026-09-12T18:40:00Z`. The file's real
mtime is `18:09:49`, and it is now `18:11`. The agent invented a plausible time
rather than reading the clock — so the audit trail we just praised has fictional
times in it.

**Fix:** the templates should say timestamps come from the tool, and `gd` should
expose the value (a `gd now`, or have `gd state`/`gd palette` stamp change-log
rows). Anything an agent types from memory will be wrong.

### 6. `godot_project` records a miscased path
`STATE.md` has `D:/testgame/game/ringfall`; the directory is `D:/TestGame`.
Harmless on Windows, but it will break any future case-sensitive comparison, and
it leaks into anything that echoes the path.

**Fix:** resolve and normalise the work root's real casing in `gd init`.

## Risks to watch, not yet faults

- **Kickoff has no completion gate.** It is *currently* correct that
  `.planning/phases/` is empty and `beat: frame` — it has not finished. But
  nothing would notice if it stopped here permanently. `/gd:plan` KICKOFF is
  meant to flow into decomposing stage 1; watch whether it does. If it does not,
  the fix is a `gd kickoff check` that fails unless contracts are locked, the
  roadmap validates, stage 1 has a plan, and the driver is armed.
- **Nothing is committed to git.** The repo has `.git` but zero commits, so the
  most expensive artefacts in the project — the contracts — are one bad edit from
  gone. `/gd:new` runs `git init` and never commits. Watch whether `/gd:run`'s
  per-job commits are the first ones.
- **`STATE.md` prose is still template text** (`<one paragraph…>`). `gd state`
  only rewrites `- key: value` lines, so "What just happened" / "What is next"
  stay boilerplate unless an agent edits them by hand. Low harm, but it is the
  one part of STATE a human reads first.
- **`BUDGET.md` untouched since init.** Fine at kickoff — but this game has a
  full Ring plus a planet, and the default 1200 draw calls / 4 shadow lights may
  not survive stage 14. Watch whether anything revisits it before then.

## Next loop should check

1. Did kickoff finish — stage 1 planned, `RUN.json` armed, `beat: build`?
2. First git commit appeared?
3. If `/gd:run` started: are jobs being graded, and did any escalate a tier?
4. Whether the 18-check `minute_one.json` gets rewritten into a real stage-1
   gate, or left as-is and inherited as permanent noise.
