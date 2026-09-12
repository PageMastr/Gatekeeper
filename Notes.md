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

---

# Loop 2 — 19:02Z · kickoff complete, then a dead stop

State: **stage 1 planned and armed, nothing built.** `beat: greybox`,
`phase: 01-greybox`, 13 jobs across 6 waves, `RUN.json` written, all jobs
`pending` with 0 attempts. Three commits exist.

**No file has been written anywhere in the workspace since 18:30.** Clean git
status, no work in flight. The session has been idle ~32 minutes.

## Two loop-1 risks closed themselves

Worth recording, because it validates the loop-1 decision to log them as *risks*
rather than *faults*:

- **Kickoff did finish.** It went on to decompose stage 1 and arm the driver. No
  completion gate was needed for it to happen — though see below, one is still
  worth having.
- **Git commits appeared** — three, with real messages: `kickoff contracts
  locked, greybox scaffold green`, `stage 01: greybox decomposed into 13 jobs,
  6 waves, driver armed`, `setting fixed — the Ring orbits a hot white dwarf`.

## The system handled a late contract revision correctly

That third commit is a **setting change made after the contracts were locked** —
the Ring re-set to orbit a hot white dwarf. The system absorbed it cleanly:
`COLOR_BIBLE.md` edited 18:45:39, `palette.gd` regenerated 18:45:45 (six seconds
later), and `gd roadmap` still validates. That is the palette contract doing
exactly its job on a change that would otherwise have drifted silently into the
first asset built.

## The decomposition is good, and it followed the hard advice

Wave 2 runs **seven** jobs in parallel, and they genuinely are disjoint — each
owns its own `scripts/<subsystem>/` and its own `scenes/greybox/<thing>.tscn`:
player, station, crew, clock, wreck, hud, gates. And `scenes/main.tscn` is
touched by **exactly one** job (11, wave 4, "compose main.tscn").

That is the `.tscn`-collision advice from `/gd:plan` followed to the letter —
each subsystem builds its own scene, composed in a later job, rather than seven
agents merging one scene file. It is the part of the plan I most expected to be
got wrong, and it was got right.

Model routing came out sensible unprompted too: 12 jobs on `gd-mechanics`/opus,
job 10 on `gd-playtester`/sonnet, no `gd-modeler` anywhere — correct, a greybox
has no assets.

## Confirmed faults

### 7. The plan-to-run handoff is a hard stop, and it is the entire idle gap

`/gd:plan` ends by *recommending* `/gd:run` and stopping. That is exactly what I
wrote it to do — and it means an overnight build parks itself indefinitely after
planning, waiting for one keystroke. The 32 idle minutes are not a malfunction,
they are the design.

For someone who asked for autonomy, "plan, then stop" is the wrong default.
There is an autonomy layer and no way to reach it without a human turn.

**Fix:** `/gd:plan --then-run` and `/gd:new --then-run`, chaining straight into
the driver. Also make the stop louder when it is deliberate — the final line
should be the literal next command, alone, not buried under a report.

### 8. `/gd:greybox` and `/gd:run` now claim the same territory

`beat: greybox`, with a planned phase, 13 jobs and an armed driver. Should the
user type `/gd:greybox` or `/gd:run`? Both are defensible from the docs.
`/gd:next` resolves it correctly — the phase has no asset jobs, so the Law-1 row
does not fire and it routes to `/gd:run` — but only if the user thinks to ask.

**Fix:** once a phase has a `RUN.json`, `/gd:greybox` should detect it and hand
off to `/gd:run` rather than offering a parallel hand-driven path. Keep
`/gd:greybox` for when no phase plan exists.

### 9. The driver has no `running` state, so in-flight is indistinguishable from never-started

Every job reads `pending / 0 attempts`. A job being actively worked right now
looks identical to one nobody has touched. That cost me a real diagnostic step
this loop — I had to fall back on file mtimes and `git status` to establish that
nothing was in flight.

It is worse than an observability gap: after a crash, a job that was 90% done
and one never begun resume identically.

**Fix:** `gd run start <job>` setting `status: running` with a timestamp, called
before dispatch. Then `run status` shows what is in flight, and a `running` job
older than a threshold is a visible stall.

### 10. Per-job gates are written by the agent that implements the job — Law 6 has a hole

Law 6 says a builder never grades its own work, and we enforce it for
*screenshots* (`gd-critic` never sees the code). But `gd-mechanics` is told: *"If
your job needs a playtest plan that does not exist yet, write it. The gate is
part of the job."* So the implementing agent authors the test it must pass. That
is self-grading one level up, and much easier to miss than a builder praising
its own render.

**The planner independently noticed and worked around it.** Job 10 is "Gates
written ahead", assigned to `gd-playtester` — pulling `loop_complete`,
`can_lose_dawn` and `can_lose_abandoned` out to a *different* agent, in an
earlier wave than the jobs they gate. Our own doctrine being patched by the
plan is the clearest possible signal the doctrine is wrong.

**Fix:** promote that pattern into the system. Per-job playtest plans get
authored by `gd-playtester` in an earlier wave, never by the implementing agent.
`/gd:plan` should emit that job automatically instead of relying on the planner
to invent it.

### 11. No way to validate a playtest plan without running it

Job 10's gate is *"plan schema check (python one-liner)"* — the agent had to
improvise, because there is no `gd` verb for "is this plan well-formed?".

**Fix:** `gd playtest --lint <plan>`: validate the JSON schema, confirm every
`actions` entry exists in the project InputMap (which would have caught the
`confirm` drift from loop 1 *before* a run), and warn on `expr` checks whose
node paths do not resolve in the named scene. That turns "gates written ahead"
into a checkable deliverable rather than a promise.

### 12. STATE.md's `updated` field lies after a contract edit

`STATE.md` says `updated: 18:30:59`, but `CONTEXT.md` and `COLOR_BIBLE.md` were
edited at 18:45. Contract edits do not touch STATE, so the one timestamp a fresh
session reads first is stale by fifteen minutes.

**Fix:** `gd palette` and every contract-touching verb should stamp `state
updated`. Cheap, and STATE is the file a resumed session trusts.

## Observation, not yet a fault

**The open checkpoint already contains its own answer.** The one-way door after
job 01 reads: *"Faith representation: one global scalar vs a per-crew state
machine. **Recommendation:** per-crew…"* with a full paragraph of reasoning.
Genuinely useful, and it also risks reducing the checkpoint to a rubber stamp.
Watch whether the user gets a real choice or just an assent. If it recurs,
`/gd:run` should present the options and the cost of each, not lead with the
recommendation.

## Next loop should check

1. Did `/gd:run` get invoked — any job attempts, any files in `verdicts/`?
2. If wave 1 ran: did job 01 add the `confirm` action, closing the loop-1
   InputMap drift?
3. How the checkpoint after job 01 gets presented and resolved.
4. Whether the 18-check `minute_one.json` from kickoff gets rewritten by job 10
   or 11, or inherited as permanent noise.
