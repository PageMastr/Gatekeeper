# Field notes — Ringfall (D:/TestGame) observed against GSD-GameDev

A running log from a 10-loop observation of the system building a real game, so
we can improve the base system tomorrow. One entry per loop, appended.

**The game under test:** *"Rebuild a shattered ring station one module at a time
while managing air, heat, and a crew that's losing faith."* Kicked off with
`/gd:new`, interview completed by the user.

**Observer cadence:** hourly at :47 (cron `70fe3521`). 45m was rounded up —
`*/45` fires at :00 then :45, giving alternating 45/15-minute gaps.

**Targets** (widened at loop 3, from one game to three — cross-game repetition is
what separates a system fault from one agent's bad day):

| workspace | game |
|---|---|
| `D:/TestGame` | Ringfall — rebuild a shattered ring station, manage air, heat and crew faith |
| `D:/testgame2` | The Last Lamp |
| `D:/testgame3` | Henhouse |
| `D:/testgame4` | Paper Boat — kicked off *after* the 16 fixes, so it validates them |

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

---

# Loop 3 — 19:20Z · scope widened to three games

**Scope change.** Now observing three independent kickoffs of the same system,
which turns single-game anecdotes into cross-game evidence. Cron rescheduled:
`82df0d8a` cancelled, **`f731ad41`** created, same hourly-at-:47 cadence.

| workspace | game | beat | phase | jobs | commits | roadmap |
|---|---|---|---|---|---|---|
| `D:/TestGame` | Ringfall | greybox | 01-greybox | 13 / 6 waves, **job 01 passed** | 3 | 17 stages, 37 coverage, valid |
| `D:/testgame2` | The Last Lamp | build | 01-greybox | 7, all pending | 1 | 14 stages, 27 coverage, valid |
| `D:/testgame3` | Henhouse | frame | none | 0 (mid-decomposition) | **0** | 16 stages, 32 coverage, valid |

## Methodology addendum 2 — my own tooling produced a second false finding

`find -newermt "2026-09-12 19:00"` returned nothing for a job that had just
written five files. **`-newermt` takes local time; every timestamp in this
document is UTC**, and this machine is UTC−5. I was comparing against 00:00
tomorrow and nearly recorded "job 01 passed without writing any files."

For the remaining loops: compare with `date -u -r <file>` per file, never
`-newermt` with a UTC string. Two near-misses in three loops, both from reading
a live system with a stale or mis-scoped query — the pattern is that **the
observation tooling is the least reliable part of this exercise**, not the
system under test.

## The roadmap contract is holding across three different games

Three kickoffs, three genuinely different games — a dying ring station, something
called The Last Lamp, and a henhouse — and `gd roadmap` came back green on all
three, first try: **17 / 14 / 16 stages, 37 / 27 / 32 coverage rows, 12 / 10 / 13
placeholders, zero errors.** Stage counts vary with the game rather than
converging on the template's 16, which is what adaptation looks like.

This is the strongest evidence yet that the roadmap contract and its validator
are right. Leave them alone.

## Ringfall: the system closed a loop end to end

Job 01 passed on the first attempt on opus, and the recorded note is specific:
*"gd check 9/9 ok, godot3_findings [] on all. playtest foundations PASS 6/6."*
It wrote `scripts/core/{events,carrier,interactable,interactor}.gd` between
19:07 and 19:11 and recorded the pass at 19:15.

**And it added the `confirm` input action.** That is fault 4 from loop 1 closing
itself: the kickoff smoke test flagged `input_action:confirm` as drift → the
planner scoped it into job 01 ("Foundations: `confirm` action…") → the job added
it → `gd check` and a real gate verified it. A failed check in a throwaway
kickoff run became a tracked requirement and got fixed. That whole path worked
without a human touching it, and it is the best argument for the harness
reporting drift as a hard failure rather than a warning.

## New faults

### 13. `BUDGET.md` is never written — 3 of 3 games, exactly the template
All three budget files still have exactly the template's 11 table rows, with
mtimes equal to their `gd init` time (17:48 / 18:48 / 19:03). Not one kickoff
touched it.

It is one of the six contracts, and `/gd:plan` never mentions writing it — so
every game inherits 60 fps / 1200 draw calls / 4 shadow lights / the default
per-class triangle budgets regardless of what it is. Ringfall has a full ring
station plus a lit planet; Henhouse is a henhouse. They should not share a
budget, and the first time anyone finds out is stage 12–14, when the performance
stage fails against numbers nobody chose.

**Fix:** add a budget step to the kickoff, after the roadmap. It does not need
to be elaborate — pick the target (desktop/handheld), scale the draw-call and
triangle numbers to the scene scope the roadmap just described, and if the
defaults are genuinely right, write a line in Deviations saying they were
reviewed and accepted. An unreviewed contract is indistinguishable from a
forgotten one, which is exactly the problem the ledger idea solves elsewhere.

### 14. Every phase gets a `verdicts/` directory that nothing ever writes to
`gd phase new` creates `<phase>/verdicts/` (gd.py:324). Nothing in the system
writes there — verdicts land in `game/<slug>/.gd_out/<plan>/verdict.json`. All
three games have an empty `verdicts/` in their phase directory.

Minor, but it is a dead artefact that implies a place to look for results that
will always be empty, and it cost me a diagnostic step this loop.

**Fix:** either drop it from `gd phase new`, or — better — have the driver copy
each graded verdict into it as `<job>-<attempt>.json`. A per-phase, per-attempt
verdict history is genuinely useful for exactly the retro that `/gd:ship` asks
for, and right now that history only exists as the last-run file in `.gd_out`,
which the next run overwrites.

### 15. Commit discipline is inconsistent across games at identical stages
Ringfall: 3 commits, including one at contract lock. The Last Lamp: 1 commit
covering the whole kickoff. Henhouse: **0 commits**, with all six contracts and
a validated 16-stage roadmap written and a phase directory created.

Same system, same beat, three different behaviours — so this is not the game, it
is the absence of a rule. `/gd:new` runs `git init` and nothing ever says
*commit the contracts once they are locked.*

**Fix:** make it explicit and mechanical — `gd state palette_locked yes` and
`loop_locked yes` are already the moment the contracts become real, so the
kickoff should commit immediately after. Two lines in `/gd:plan`, and it removes
the case where a night of interview work is one bad edit from gone.

### 16. `STATE.md` can disagree with the phase directory that exists
Henhouse has `phase: none` in STATE while `.planning/phases/01-greybox/` exists.
`gd phase new` creates the directory; `gd state phase <name>` is a *separate*
call the agent must remember. Between the two, STATE lies about where the project
is — and STATE is what a resumed session trusts.

**Fix:** `gd phase new` should set `state phase` itself. There is no case where
you create a phase and do not want it to be the current one.

## Fault 10 is now confirmed in practice, not just in theory

Loop 2 flagged that the implementing agent authors its own gate. Ringfall job 01
did exactly that: it wrote `lab/foundations.json` — its own 6-check gate — and
then passed it. `gd check` is independent and caught nothing to complain about,
so nothing is actually wrong with this work; but the gate that certified it was
written by the thing being certified, and no mechanism noticed.

That raises fault 10 from a doctrinal hole to an observed one. It is now the
highest-value fix on the list.

## Next loop should check

1. Ringfall wave 2 — seven parallel jobs is the real test of the disjointness
   claim. Watch for anything landing outside its `touches` list.
2. How the Ringfall checkpoint after job 01 gets presented (it still reads OPEN,
   and it contains its own recommendation).
3. Whether The Last Lamp's 7-job greybox is under-decomposed relative to
   Ringfall's 13 — compare what a job covers in each.
4. Whether Henhouse commits anything, and whether its `phase: none` desync
   resolves on its own.

---

# Fixes applied — 19:32Z (between loops 3 and 4)

All 16 faults from loops 1–3 fixed, verified against the real engine, and the
global install at `~/.claude/gsd-gd/` refreshed. Every fix was proved by
reproducing the original failure first.

| # | fault | fix | proof |
|---|---|---|---|
| 1 | kickoff smoke test left a `passed: false` verdict | `gd playtest --smoke` — gates on harness boot, records content checks as `pending` | same plan: full run exit 1, `--smoke` exit 0 with 2 pending |
| 2 | `moved` check passed on a floor with no spine | `via: [...]` asserts *what* was traversed; AABB containment or `via_radius`; `directness` reported | `walked_the_spine_VIA` now FAILS `never entered: Spine/Seg01`, while a real traversal still passes |
| 3 | `Expression` failures lost their error text | now carries the expression source, the resolved base node path + class, and the full error | code inspected; type-checks clean |
| 4 | missing input action didn't say what exists | lists the non-`ui_` InputMap actions in the failure detail | lint output names all 8 available actions |
| 5 | agents invent timestamps | `gd now`; Color Bible change log tells authors to use it | `gd now` returns real UTC |
| 6 | `godot_project` miscased | `_true_case()` resolves each path segment against its real parent listing | `cd d:/clauDEgameDEV` → `work D:\ClaudeGameDev` |
| 7 | plan→run was a hard stop | `--then-run` on `/gd:plan` and `/gd:new`; otherwise the next command is the last line, alone | doc change |
| 8 | `/gd:greybox` and `/gd:run` overlapped | greybox checks `run status` first and hands off when a `RUN.json` exists | doc change |
| 9 | no `running` state | `gd run start <job>`; `run next` returns `in_flight` and stops re-offering it | job 01 `running`; next offered only job 02 |
| 10 | implementers wrote their own gates (Law 6 hole) | `gd-playtester` owns every plan, as job 01 alone in wave 1; `/gd:plan` emits that job; `gd-mechanics` forbidden from editing a plan | doc change across 3 files |
| 11 | no way to validate a plan without running it | `gd playtest --lint` | caught 4 errors + 2 warnings in a bad plan, no Godot launch |
| 12 | `STATE.md updated` went stale | shared `write_state()`; `gd palette` stamps `palette_synced` | `palette_synced` present after init |
| 13 | `BUDGET.md` untouched in 3/3 games | kickoff step 5 sets it from the roadmap's scene scope, or records acceptance in Deviations | doc change |
| 14 | `verdicts/` was a dead directory | `gd run record --verdict` archives to `<phase>/verdicts/<job>-attemptNN.json` | `01-attempt01.json` written |
| 15 | commit discipline inconsistent (3/1/0 commits) | kickoff commits the contracts explicitly after the budget step | doc change |
| 16 | STATE could disagree with the phase dir | `gd phase new` sets `state phase` itself | `set_current: true` |

**Clean-slate regression, all exit 0:** doctor, now, init, check, playtest
`--lint`, playtest `--smoke`, playtest full, asset, models. `roadmap` exits 1 on
the unfilled template, which is correct. The modified harness type-checks clean
against Godot 4.7 (`gd check` 5/5).

**Installed copy verified** from an unrelated directory: init, check, smoke,
asset all green; `run` exposes `start`; `playtest` exposes `--lint/--smoke`; the
harness carries the `via` support.

## Note for the remaining loops

The three games under observation are running against the **old** installed
copy — they were kicked off before these fixes. So:

- Do **not** re-report faults 1–16 against them; they are fixed in the system
  but those workspaces still contain the old artefacts (the 18-check
  `minute_one.json`, the distance-only `moved` checks, the miscased
  `godot_project`).
- Their remaining value is as evidence for *new* faults, and for watching
  whether the parts we did not touch hold up — wave-2 parallelism, the
  escalation ladder, the checkpoint presentation, and whether any gate passes
  for a reason nobody intended.
- A fresh `/gd:new` in a fourth workspace would be the way to test the fixes
  end to end, if that is wanted.

---

# Loop 4 — 19:46Z · the shared-harness incident

**Scope widened again** to four games; `D:/testgame4` (paper-boat) was kicked off
after the 16 fixes. Cron re-created as **`70fe3521`**, and it now includes a
harness-diff step, because of what this loop found.

## The incident

A game edited the **shared installed harness** at `~/.claude/gsd-gd/harness/
godot/gd_lighting_rig.gd`, and `install_harness()` — which recopies on every
`gd playtest` — then propagated it into every other project on the machine.

Authored by **the-last-lamp** (`330a1f5 job 04: cabin_interior and
nebula_exterior lighting presets`). Two presets, plus twelve new per-preset keys
and a palette-key indirection. Result:

| game | had the presets | has the palette swatch they need |
|---|---|---|
| Ringfall | yes | **no** |
| the-last-lamp | yes | yes |
| henhouse | yes | **no** |
| paper-boat | yes | **no** |

**Three of four games were carrying presets that reference `sky_nebula_far` /
`sky_nebula_near`, swatches only the-last-lamp defines.** Not cosmetic — applying
`nebula_exterior` in henhouse resolves nothing. And the install root is not under
version control, so none of it was recorded anywhere.

### I made the same mistake, in the other direction

At 19:32 I installed the 16 fixes into the same shared root **while three agents
were mid-build**. Their grader changed under them. Ringfall's job 06 then
committed a 101-line `gd_playtest.gd` diff as part of an unrelated 23-file
commit — it was the recopy of *my* `via` code, swept up incidentally. Same hole,
different culprit: I hot-patched a live shared dependency.

### Attribution was wrong three times, and that is the finding

I first blamed Ringfall (its copy was byte-identical to canonical — but identical
means *most recent recopy*, not *author*). Then I read a `git log` that listed
two harness commits and my own echo label said "empty", so I concluded no harness
edit existed. Only the palette keys settled it.

**A shared mutable system with no version control makes authorship unknowable**,
even under deliberate forensics. That is worse than the leak itself, and it is
the reason the fix below is about *recording* as much as preventing.

## Was the change worth keeping?

Partly. Judged on its merits:

- **Keep the idea.** The rig hardcoded `Color(...)` literals everywhere, which
  quietly breaks Law 8 in the one place a fourth shade of grey is least visible.
  `"sun_color_key": "accent_warm"` resolving against the project `Palette` is
  correct, and it is our own law applied to our own blind spot.
- **Keep the sky and fog parameters.** `sky_curve`, `sky_top/ground_energy`,
  `fog_sky_affect`, `fog_light_energy` are real Godot 4.7 properties (verified
  against the local index) and the rig exposed none of them. Two games reached
  for them independently, which is the signal.
- **Reject the two presets.** Game-specific, and broken everywhere else.
- **Reject the keys as written.** `_refresh()` never read them — the file's own
  comment admits *"Keys `_refresh()` does not read … are applied by the scene"*.
  Twelve keys of dead data in a grader is a trap: it reads as configuration and
  does nothing.

**Upstreamed properly:** all nine optional keys, applied for real in `_refresh()`
via `palette_color()`, which soft-resolves against `res://scripts/palette.gd` and
falls back to the literal when a key or the Palette is absent — so the harness
still boots in a scaffold with no Color Bible filled in. Type-checks clean
against the engine. No project presets.

## New faults, and the fixes shipped this loop

### 17. Agents could edit the shared installed system
**Fix:** `~/.claude/gsd-gd/` is now declared read-only to every agent in
`CLAUDE.md`, in `gd-mechanics`, and as **Law 6b** — *never modify the instrument
that grades you*. `/gd:light` now says game presets go in the project, never in
the shared rig, and explains why with this incident.

### 18. An unreviewed grader, with no record of which grader graded
The real risk is not malice, it is that a subtly wrong check makes future gates
pass that should not — and every verdict after it is worth less.

**Fixes, all verified:**
- `gd harness --check` diffs a project's harness against canonical and exits 1
  on drift. Tested against a deliberately tampered `gd_playtest.gd` (edited so
  every `moved` check passes): `[DRIFT] gd_playtest.gd differs from canonical`.
- `gd doctor` fails on it: `[FAIL] harness  local edits to the grader`.
- **Every verdict now records `harness_hash`**, plus `harness_was_modified` when
  the project harness had drifted before the run. A verdict is only as
  trustworthy as the harness that produced it.
- `install_harness()` no longer silently clobbers a local edit — it backs the
  file up as `<name>.local` and reports `overwrote_local_edits`. That protects
  a genuine local fix from being destroyed by an install, which is exactly what
  my 19:32 install did.

### Leak cleanup
Ringfall, henhouse and paper-boat restored to the canonical harness (their local
rigs preserved as `.local`). the-last-lamp keeps its own — it is mid-build and
its presets are legitimately its — but it now reports as **drifted** rather than
silently sharing.

I also started writing a project-local subclass to hold the-last-lamp's presets
properly, then deleted it: it referenced a `_project_preset` member the base rig
does not have and would have failed `gd check` in a live project. Injecting
untested code into someone's mid-build workspace is worse than the leak. A real
project-preset extension point is worth designing, but not at 20:00 into a
running build — **carried forward as the top open item**.

## Carried forward

1. **Design a project-preset extension point** for `GDLightingRig` so a game can
   add presets without touching the shared rig. Candidate: the rig reads an
   optional `res://scripts/project_presets.gd` and merges its `PRESETS`.
2. **Version the install.** `harness_hash` covers the harness; `gd.py`,
   templates and references are still unversioned shared state. A `gd version`
   recording an install fingerprint would let a verdict name its whole toolchain.
3. **Never hot-patch a live shared install again.** Either install to a
   versioned directory and let projects pin, or stop the world first.
4. paper-boat is the only game running fully post-fix — next loop, check whether
   `--smoke`, `--lint`, `via` and the gates-first job actually show up in its
   plan and artefacts.

---

# Full audit — cross-project leakage (20:10Z)

**The principle, as stated:** the GD system is installed once and shared by many
projects. Every value a project might need to change must be overridable *in the
project*, without touching the global. No cross-project leaking.

Audited every file under the install root against that. Results below; the
faults are numbered continuing from the earlier loops.

## The architectural fix

`gsd-gd/config.json` is now **machine defaults only**. Each project gets
`.planning/config.json`, deep-merged on top, created by `gd init`:

```bash
gd config            # what is in force, and exactly which keys this project overrode
gd config --init     # add one to an existing project
```

Merge is recursive — `budget.max_asset_tris.prop` can be overridden without
restating the other three classes. `gd config` prints provenance, so a number is
never mysterious.

## Verdict per shared artefact

| artefact | shared? | verdict |
|---|---|---|
| `config.json` → `toolchain` | yes | **correct** — describes the machine, not the game. Still overridable for a project pinned to another engine build. |
| `config.json` → `budget` | was global | **fixed (17)** — per-project, and the engine side now sees it too |
| `config.json` → `defaults` (resolutions, warmup/sample frames) | was global | **fixed (18)** — per-project |
| `config.json` → `models` (agents, ladder, attempts) | was global | **fixed (19)** — per-project |
| `gdblend.GRID` (0.25 m snap grid) | was a module constant | **fixed (20)** — from the effective config |
| `gdblend` triangle budgets | not readable at all | **fixed (20)** — `gd.tri_budget("prop")` |
| `GDLightingRig.PRESETS` | yes | **fixed (17, loop 4)** — extension point; game presets live in `res://scripts/project_presets.gd` |
| `GDLightingRig.shadow_budget` | default 4, global | **fixed (21)** — reads the project budget |
| harness `.gd` / `.tscn` | yes | **correct** — it is the grader, and must be one thing. Now drift-detected, hashed into every verdict, and local edits are preserved rather than clobbered. |
| `gd_playtest.gd` `STEP_FPS` | yes | **correct** — a harness invariant. Changing it per project would make verdicts incomparable. |
| `cache/godot-api-index.json` | yes | **correct** — engine-global, derived from the engine's own source. |
| `templates/*` | yes | **correct** — seeds, copied per project at init. |
| `references/*` | yes | **correct** — doctrine. Shared on purpose. |
| `bin/gd.py`, `bin/gddoc.py` | yes | **open (22)** — shared unversioned code. See carried forward. |

## The faults, and what each fix was proved against

### 17. Budget was machine-global, with no per-project override
The trigger: Paper Boat wants 450 draw calls and 1 shadow light against
defaults of 1200 and 4. The only lever was the shared file, which would have
imposed a small scene's budget on a full ring station.

Fixed, and **proved by making it fail**: with
`.planning/config.json` → `budget.max_draw_calls = 1`, a run reports
`[FAIL] budget: draw_calls_max 3 > 1`, and the verdict records
`budget_source: .planning/config.json`, `budget_overrides: {max_draw_calls: 1}`.

### The two-sources-of-truth mistake I made and then removed
My first cut put `- budget:` lines in `BUDGET.md` **and** kept the json. The
template's defaults then silently beat the explicit project values — I set 450
and `gd config` reported 1200. Exactly the failure class I have been
criticising, committed in the act of fixing it.

`BUDGET.md` now holds justification and the cost model; `.planning/config.json`
holds the numbers. One source each.

### 20. `gdblend` could not see project config at all
`GRID = 0.25` was a module constant and the triangle budgets were unreachable,
so every generator hardcoded `check_tris(ob, 1500)` — a literal that ignores
whatever the project decided.

`gd blender` now passes the effective config as `GD_CONFIG_JSON`. Verified
inside Blender against a project setting `blender.grid = 0.5` and
`budget.max_asset_tris.prop = 400`:

```
ok  grid_from_project_config            GRID=0.5 (expected 0.5)
ok  tri_budget_from_project_config      prop budget=400 (expected 400)
ok  tri_budget_inherits_machine_default character budget=12000 (inherited)
```

### 21. The runtime enforced one shadow budget while the gate enforced another
`GDLightingRig.shadow_budget` defaulted to the shared `4`. A project set to `1`
would have had `enforce_shadows()` disable down to four casters at runtime and
then fail its own gate at one — two numbers, both "the budget".

`gd palette` / `gd playtest` now generate `res://scripts/gd_project.gd` from the
effective config, and the rig reads `max_shadow_casting_lights` from it. Same
pattern as the generated `Palette`: the project's contract compiled into
something GDScript can read.

### 19. A project model override looked like drift
`gd models` compared agent frontmatter against the *merged* config, so a
legitimate project override was reported as drift. Frontmatter is machine-global
and can only be compared to the machine config; the two are now separate, and
the table shows the **effective** model with `*` where the project overrode it:

```
  gd-modeler         opus*    asset work is an aesthetic task disguised as a scripting task
  * = overridden by this project (.planning/config.json)
```

## A blocking bug the audit surfaced

`gd playtest` calls `install_harness()`, which rewrites the harness scripts —
and that by itself makes Godot's global class cache stale, so every run after a
reinstall sprayed `Could not find type "GDLightingRig"` and failed on
`runtime_errors`. My earlier stale-cache fix was in `gd check` only.

Both now share `ensure_class_cache()`, called after the harness recopy.
`runtime_errors: []` confirmed.

This also explains Ringfall's earlier "2 failing files": one was a genuine
in-flight airlock bug, the other a false `Could not find type "Airlock"` from
the same stale cache. All four games now report **0 failing files**.

## Carried forward

1. **22. `gd.py` / `gddoc.py` / templates / references are shared unversioned
   code.** `harness_hash` covers the grader; nothing covers the rest. A
   `gd version` writing an install fingerprint into each verdict would let a
   result name its whole toolchain. This is the last of the shared-state
   problem, and the one I hit personally by hot-patching a live install.
2. **Never hot-patch a live shared install again.** Install to a versioned
   directory and let projects pin, or stop the world first.
3. The `.local` backup convention needs a documented recovery path — right now a
   preserved edit sits there with nothing telling anyone to look at it.

---

# Loop 5 — 20:08Z · the games start auditing the system

All four building, all four writing files in the last 25 minutes.

| game | beat | commits | latest |
|---|---|---|---|
| Ringfall | greybox | **16** | `wave 3 findings: E.11 prop_eq/int, E.12 project_presets` |
| the-last-lamp | build | 12 | `job 06: fix two references stale since the Law 6b redesign` |
| henhouse | greybox | 5 | `job 01: isometric camera rig, three pitch candidates` |
| paper-boat | greybox | 2 | `plan: stage 01 greybox loop — 6 jobs, 5 waves, 2 checkpoints` |

Two things worth noting before the findings: **the-last-lamp noticed my Law 6b
change mid-build and fixed its own stale references to it** — a doctrine edit
propagated and was absorbed without being told. And Ringfall has been keeping a
numbered findings table about the *system*, in its own PLAN.md, with engine
source citations. Twelve entries. That is the most valuable artefact this
exercise has produced, and I did not ask for it.

## E.10 — `gd playtest` was not parallel-safe, and produced a FALSE GREEN

The worst fault found so far, and Ringfall found it, with line numbers:

> Every invocation writes the plan to the single shared path
> `<project>/.gd_out/_inbox/plan.json` (L1363) and launches Godot with
> `--plan=res://.gd_out/_inbox/plan.json` (L1385), while `verdict["plan"]` is set
> from gd.py's own argument (L1409) rather than from what Godot actually ran.
> Two overlapping runs therefore produce a **silent wrong answer**: job 04 saw
> job 06's `crew_dawn` checks reported under the heading
> `plan station_modules.json` with a green PASS.

A green PASS filed under the wrong plan. `/gd:run` dispatches parallel waves by
design — Ringfall's own wave 2 has seven — so this was live, not theoretical.
And it correctly refused to patch it: *"This is a bug in the tool, not in the
project. Do not work around it by editing `gd.py` from inside a job."* Law 6b
held under pressure.

**Fixed two ways**, because one was not enough:
- Unique inbox per run (`_inbox/<stem>-<pid>-<uuid>.json`), so plans cannot
  collide.
- **Identity cross-validation**: the verdict's `name` must match the plan's, and
  any check name in the verdict that is not in the plan (and is not a
  harness-generated `input_action:` / `shot:` / `timeout` / `harness` entry)
  makes `gd playtest` *refuse to report the verdict at all*. Stamping our own
  argument into `verdict["plan"]` is precisely what made the swap invisible.

Verified by running two playtests concurrently: `pa` reported only `pa_moved`,
`pb` only `pb_moved`.

## E.1 — my gate was false-failing on autoloads, and it bent a project's architecture

> `gd check` runs `godot --headless --check-only --script <file>`, and
> `Main::start()` returns at `main.cpp:4372` **before** autoload globals are
> registered at `main.cpp:4509`. So `Events.x.emit()` fails the gate with
> `Identifier not found: Events` on code that is perfectly correct at runtime.

Ringfall had already worked around it — E.1 instructs every job to write
`var _bus: EventBus = EventBus.bus()` and never the bare autoload identifier.
**My broken gate reshaped their architecture into a static-accessor pattern.**
That is worse than a false failure; it is a false failure that got designed
around.

Fixed: `gd check` reads the `[autoload]` section of `project.godot` and forgives
`Identifier not found` / `not declared` **only** for declared autoload names,
reporting them as `autoloads_forgiven`. Ringfall's own note that the global
*class* cache is loaded in that mode is what makes this safe.

Regression-tested, because masking real errors would be far worse: a script
using `NotAnAutoload.do_thing()` and `Spatial.new()` still fails on both.

## E.11 — `prop_eq` could not assert an integer

> It compares `str(actual) == str(want)`, and a JSON `1` arrives in Godot as a
> float, so a correct `motion_mode == MOTION_MODE_FLOATING` fails as
> `motion_mode = 1, want 1.0`.

Fixed: numeric comparison via `is_equal_approx()` when both sides are numbers,
string comparison otherwise. Verified — `int_equality  motion_mode = 0, want 0.0
(numeric)` now passes, and string equality still works.

## Engine knowledge worth keeping (from Ringfall's E.4, E.8, E.9)

Not system faults, but real Godot 4.7 findings with citations, and better than
anything in our references:

- **E.4** — `_notification(NOTIFICATION_ENTER_TREE)` fires at *every* level of
  the script chain (`gdscript.cpp:1973`, "notification is not virtual, it gets
  called at ALL levels"), whereas `_ready` fires only on the most-derived
  script. So a base class can register itself in a group without depending on
  every subclass remembering `super._ready()`.
- **E.8** — `@export var range` shadows the global `range()` **inside that class
  only**, and the analyser is silent about it.
- **E.9** — a `.tscn` `Transform3D` is written as basis *rows*; the GDScript
  constructor takes *columns*.

## Post-fix validation: paper-boat

The one game kicked off after the 16 fixes, so it is the test of whether they
took.

**Fault 10 took, and took cleanly.** Its plan's job 01 is *"Gates written ahead —
author all four playtest plans this phase is graded by"*, `gd-playtester`,
wave 1, touching `lab/*.json`. That is the pattern I promoted into `/gd:plan`
verbatim, emitted without being asked. `--lint` appears in three of its files.

**But `via` did not take.** Its `minute_one.json` has
`current_carried_the_boat` as a distance-only `moved` check — `--lint` warned,
and the warning was ignored. Which is the whole lesson of fault 2 repeating: a
check named for a route, asserting only a distance.

**So the warning is now an error.** A distance-only `moved` check fails
`--lint` unless it sets `"distance_only": true` — distance-only is still
allowed, it just has to be *stated*. testgame4's plan now fails lint, correctly.

## 23. Projects created before the config change had no override file

`gd init` now writes `.planning/config.json`, but all four games predate that,
so none had one — including paper-boat, the very game that needed a tighter
budget. Backfilled all four with `gd config --init`.

**Paper Boat's budget is now applied**: `max_draw_calls: 450`,
`max_shadow_casting_lights: 1`, with the reason recorded in the file. Ringfall
still reads 1200/4. That is the per-project mechanism doing its job on the case
that prompted it.

## Carried forward

1. **22** (unchanged): `gd.py` and friends are still shared unversioned code.
2. **24**: `--smoke` has not appeared in any game's artefacts. It was added to
   `/gd:plan`'s kickoff, but all four kickoffs predate it, so it is untested in
   the wild. Watch the next fresh project.
3. Fold Ringfall's E.4 / E.8 / E.9 into `references/gdscript-4x.md` and
   `toolchain.md` — they are better than what is there now.
4. **A system-findings artefact should be first-class.** Ringfall invented a
   numbered `E.n` table with source citations and it caught three real faults in
   one wave. That should be a template, not an emergent behaviour — something
   like `.planning/SYSTEM_FINDINGS.md` that `/gd:ship` sweeps into the
   references via `gd-scribe`.

---

# Loop 6 — 20:24Z · the driver's own fixes show up in the field

| game | jobs | passed | running | blocked | check | harness |
|---|---|---|---|---|---|---|
| Ringfall | 13 | **10** | 0 | 0 | 0 failing | current |
| the-last-lamp | 7 | 2 | 0 | 0 | 0 failing | current |
| henhouse | 9 | 3 | 0 | 0 | 0 failing | current |
| paper-boat | 6 | 0 | **1** | 0 | 0 failing | current |

Ringfall is 10/13 through its greybox with nothing failing. And **paper-boat
shows a job in `running`** — the fault-9 fix in live use, doing exactly what it
was for: the board now distinguishes "being worked on" from "nobody has touched
it".

## 25. `gd harness --check` could not tell *stale* from *tampered*

paper-boat reported two drifted files with:

> `[DRIFT] gd_playtest.gd differs from canonical - a local edit to the
> instrument that grades this project`

**It had edited nothing.** Its harness was hash `398b5dd8`; canonical had moved
to `046bd23c` because I had shipped the E.11 and shadow-budget fixes since. The
project was simply *behind*.

So the check I built to catch Law 6b violations was accusing a project of
tampering for the crime of not having been reinstalled. Wrong, and alarming —
and it would train people to ignore the one message that matters.

**Fixed:** `install_harness()` now stamps `addons/gd_harness/.installed_hash`
with the canonical hash at install time, and drift is classified:

| status | meaning | gate |
|---|---|---|
| `current` | matches canonical | pass |
| `stale` | untouched since install, canonical moved on — `gd harness` to update | **pass** |
| `edited` | differs from what was installed here — the Law 6b case | **fail** |
| `unknown` | installed before stamping existed | fail, conservatively |

All four games now read `current`. paper-boat's prior files were preserved as
`.local` on the way through, per the loop-4 fix.

## 26. My own measurement bug, again

The sweep reported `exit=2` for all four harness checks. Not the tool — I had
set `GD="python gsd-gd/bin/gd.py"`, a **relative** path, and then `cd`'d into
each game directory where it does not exist.

Third measurement error in six loops, all mine, all from reading a live system
carelessly. The tooling around the observation continues to be less reliable
than the system being observed. Absolute paths only, from here.

## Carried-forward item patched: system findings are now first-class

This was the top open item from loop 5, and the reason was that a project
invented the artefact spontaneously and **out-performed this observation loop**
— Ringfall's `E.n` table caught three real faults in one wave, two severe, that
testing the system against itself would never have found.

Shipped:

- **`.planning/SYSTEM_FINDINGS.md`**, created by `gd init` alongside the other
  contracts. Three tables: findings, engine knowledge, and **workarounds
  currently in force** — the last because a workaround outlives the fault unless
  something is tracking it.
- **A severity vocabulary**, with `false-pass` at the top: *a gate certified
  something untrue*. That is the only category that invalidates work already
  accepted, and it earns its own emergency handling.
- **`gd-mechanics`, `gd-modeler` and `gd-rigger` are told to file**, and told
  plainly that filing is **not** permission to fix (Law 6b). Ringfall got this
  right unprompted — *"This is a bug in the tool, not in the project. Do not
  work around it by editing `gd.py` from inside a job."* — and that instinct is
  now written down instead of hoped for.
- **`/gd:ship` sweeps them** as its own numbered step, before extracting
  learnings: any `false-pass` is an emergency and its gates get re-run;
  engine knowledge folds into the references; workarounds are checked against
  their finding's status and removed when the fault is fixed.
- **`gd-scribe` reads findings first**, keeps citations verbatim
  (`main.cpp:4372` is the finding; "autoloads are tricky" is not), and may not
  mark anything `fixed` — the project reports, the system decides.

The template says what makes a finding useful, using the real examples: cite the
mechanism, say whether it was a false pass or a false failure, and record the
workaround.

## Global install refreshed

`install.py` re-run: 28 files rewritten to absolute paths, 1071 classes indexed,
`doctor: all checks pass`. A fresh `gd init` now produces:

```
BUDGET.md  COLOR_BIBLE.md  CONTEXT.md  CORE_LOOP.md  CREDITS.md
ROADMAP.md  STATE.md  SYSTEM_FINDINGS.md  config.json  phases/
```

Regression from clean: doctor, config, models, check, harness --check, playtest,
asset all exit 0; roadmap correctly exits 1 on the unfilled template. All four
live games: harness `current`, zero failing files.

## Carried forward

1. **22** — `gd.py`, `gddoc.py`, templates and references are still shared
   unversioned code. `harness_hash` covers the grader and `.installed_hash`
   now covers staleness, but nothing fingerprints the rest. A `gd version`
   stamped into each verdict would close it. This is the last of the
   shared-state problem.
2. **24** — `--smoke` still unexercised: every current game's kickoff predates
   it.
3. Backfill `SYSTEM_FINDINGS.md` into the four running games, and move
   Ringfall's `E.n` table out of its `PLAN.md` into it, so the sweep at ship
   time finds it where it expects to.

---

# Loop 7 — 21:00Z · the findings artefact pays for itself in 35 minutes

| game | jobs | passed | running | open ckpt | check | harness | findings |
|---|---|---|---|---|---|---|---|
| Ringfall | 13 | **12** | 0 | 0 | 0 failing | current | 1 real |
| the-last-lamp | 7 | 3 | 0 | 4 | 0 failing | current | 0 |
| henhouse | 9 | 3 | 0 | 2 | 0 failing | current | 0 |
| paper-boat | 6 | 3 | 1 | 2 | 0 failing | current | 1 real |

Ringfall is 12/13 with no open checkpoints. the-last-lamp ran a gauntlet —
`gauntlet arena: 78/78, 15 frames rendered identically in one run`.

**`SYSTEM_FINDINGS.md` shipped 35 minutes ago and has already produced two real
faults**, both with mechanism, evidence, severity and a suggested fix. Neither
would have come from testing the system against itself. The artefact is
justified.

## E.12 (Ringfall) — a latent **false pass** in the harness

The best bug report this exercise has received. Abridged:

> The playtest harness keeps no history for scalar probes, and every check is
> evaluated only once, after the last step. So a gate can never assert "X was
> true *at the moment* Y happened" — which is exactly what a failure-state gate
> needs. […] `{"kind": "still", "probe": <a float probe>}` is **vacuously green
> — a check that cannot fail**.

With line numbers: `_sample_probes()` accumulates `probe_path_len` only inside
`elif … typeof(val) == TYPE_VECTOR3` (L258), so a scalar probe keeps the `0.0`
written at L257, and `still` reads that same dictionary at L319 — green for any
tolerance ≥ 0.

The concrete cost: `can_lose_dawn` could not distinguish death-by-ring-dawn from
death-by-starvation, because `_become_gone()` zeroes `faith` in both and only
the end-of-run value was visible.

**A gate that cannot fail is worse than no gate**, and it is the top severity in
our own vocabulary. Fixed:

- **`still` and `moved` on a numeric probe now FAIL with an explanation** rather
  than passing. Refusing is right: the check is meaningless on that probe.
- **Numeric probes keep real history** — `min`/`max` across the whole run,
  exposed in the verdict.
- **New `probe_min` / `probe_max` kinds** — "did faith ever reach zero" is a
  different question from "is faith zero now".
- **New `probe_at` kind**, and every labelled step now snapshots all probes.
  This is the "X was true at the moment Y happened" assertion that was
  unexpressible. `{"kind": "probe_at", "probe": "mika_faith", "label":
  "dawn_fired", "gt": 0}` says exactly what job 13 wanted to say.

Verified end to end on a jump:

```
[FAIL] LATENT_FALSE_PASS_still_on_scalar  probe 'height' is numeric, not a
       position - `still` measures path length and would pass vacuously.
[ok]   rose_at_some_point                 probe_max(height) = 1.9718 over the run
[ok]   height_at_the_moment_of_jump       height at 'jumped' = 1.30999839305878
[FAIL] moved_on_a_scalar_is_refused       probe 'height' is numeric…
```

## E.1 (paper-boat) — `gd check` could not see a scene-embedded script

> Project-wide `gd check` reported `"files": 8` — every `.gd` on disk, and zero
> scene-embedded scripts; `scenes/lab_soak.tscn` carries a 50-line
> `[sub_resource type="GDScript"]` that was not among them. […] the failure
> surfaces 150 s later as a runtime error instead of instantly as a type error.

And it filed its workaround, exactly as the template asks: *"wrote the driver
source to `scripts/_zz_tmp_check.gd`, ran `gd check` on it, deleted it, then
embedded the verified source"* — with the fix it wanted: *"`gd check` learns to
extract `script/source` from `.tscn`/`.tres`"*.

**Fixed as asked.** `gd check` now extracts every
`[sub_resource type="GDScript"]` from `.tscn`/`.tres`, unescapes it, type-checks
it inside the project so `res://` resolves, and reports it as
`res://scenes/x.tscn::GDScript_id`. Verified against a scene whose built-in
script uses `Spatial`:

```
[FAIL] res://scenes/embedded.tscn::GDScript_soak
       engine: Identifier "Spatial" not declared. Did you mean to use "Node3D"?
```

The workaround in paper-boat can now come out — which is precisely why the
template has a *workarounds currently in force* table.

## 27. Cleanup left its own litter

First cut of the above deleted the temp `.gd` files but left the directory:
Godot writes a `.uid` beside every script it imports, so `rmdir` found it
non-empty. A tool that checks your project should not leave files in it.
`shutil.rmtree` now. Small, but it is the class of thing that erodes trust in a
tool that is supposed to be invisible.

## The template's placeholder row is being filed as a finding

Three of four games have a literal `| E.1 | | | | open |` row — the template's
example, left in place and counted. Harmless, but it makes "how many findings"
unreliable, which matters now that `/gd:ship` sweeps on it. The example row
should be commented out rather than look like data.

## Carried forward

1. **22** — `gd.py` and friends still unversioned. Unchanged.
2. **24** — `--smoke` still unexercised in the wild.
3. Fix the `SYSTEM_FINDINGS.md` placeholder row so it cannot be miscounted.
4. Ringfall's `E.n` numbering collides with its own `PLAN.md` engine-contract
   namespace (it started at E.12 to avoid it, and said so). Worth a note in the
   template that the findings file owns its own numbering.

---

# Loop 8 — 21:55Z · #22 closed, and a regression I shipped

| game | jobs | passed | running | check | harness | findings |
|---|---|---|---|---|---|---|
| Ringfall | 13 | **13** | 0 | 0 fail | current | 1 |
| the-last-lamp | 7 | 4 | 0 | 0 fail | current | 1 |
| henhouse | 9 | 4 | 0 | 0 fail | current | 1 |
| paper-boat | 6 | 3 | **2** | 0 fail | current | **2** |

**Ringfall is 13/13** — the first phase to finish its job list. `gd run next`
returns `phase_gate` with five gates queued. paper-boat has two jobs in flight
concurrently, which is the `run start` fix carrying real load.

## 22 closed — a verdict now names its toolchain

The last of the shared-state problem. `harness_hash` covered the grader and
`.installed_hash` covered staleness, but `gd.py`, the templates and the
references were unversioned — so a phase had no way to notice the toolchain
changing underneath it. Not hypothetical: I hot-patched this install while three
builds were mid-flight, and the only trace was an incidental recopy inside an
unrelated commit.

`gd version` fingerprints the install by component:

```
  system    50a6db6b25f5   (declared 1.0.0)
    cli         6d6b69ad6ba1  2 file(s)
    config      3a6790d85f7d  1 file(s)
    harness     5941e4fe01ed  5 file(s)
    lib         a30f64d17c96  1 file(s)
    references  65260be319bb  8 file(s)
    templates   171155949ed1  16 file(s)
```

- `gd init` records it as the project's baseline (`.planning/.system`).
- **Every verdict carries `system: {version, hash}`** alongside `harness_hash`
  and `run_id`.
- `gd run init` stamps it into `RUN.json`, and **`gd run status` warns when the
  system has moved mid-phase**: *"SYSTEM changed mid-phase: armed on
  50a6db6b25f5, now 7959c17992e2 — jobs graded before the change used a
  different toolchain."*
- Component-level, so the warning says *what* moved. Provoked by touching one
  reference file: `! references 1270df230fc2`.

That is the thing I most wanted after loop 4, and it would have caught my own
mistake at the time it happened rather than an hour later.

## E.2 (paper-boat) — my loop-7 fix shipped a false-fail, caught within the hour

> **The new embedded-script extractor added for E.1 double-unescapes, and now
> false-fails a correct scene.** […] `res://scenes/lab_soak.tscn::GDScript_driver`
> → `SCRIPT ERROR: Parse Error: Expected new line after "\"`. The scene is job
> 03's, was green before the tool changed, and is not broken.

A `false-fail` introduced by a fix for a `friction` finding. Fixing one fault and
shipping a worse one is the risk of patching a live system, and it took a
project under load 50 minutes to find it.

**Their mechanism was right; my label was not.** They called it
double-unescaping. It was under-unescaping: a `.tscn` stores an embedded script
**on one line**, where `\n` is a real newline and `\\n` is a literal backslash-n
that must survive inside a GDScript string literal. My
`replace('\\"','"').replace('\\\\','\\')` never handled `\n` at all, so the
extracted source was one enormous line and GDScript hit a stray backslash —
exactly the error they reported.

Chained `str.replace` cannot do this correctly in any order: it either misses a
case or rewrites the output of an earlier pass. Replaced with a **single
left-to-right scan** where each backslash consumes exactly one following
character and is never re-examined, handling `\n \t \r \" \\ \uXXXX` and
leaving unknown escapes verbatim rather than guessing.

Verified against **the actual file from paper-boat's git history** (`c4438bc`):
extraction now yields 53 lines instead of one, the literal
`"...m/s\nstate=%s\n..."` keeps its escapes intact, and `gd check` reports
**zero** `Expected new line after "\"` errors. The only error left is
`Could not find type "Run"` — which is exactly what they predicted would remain,
being their project's own `class_name` absent from a throwaway test project.

Their workaround (moving the driver out of the `.tscn` to an `ExtResource`) can
now be reverted — though it is arguably better practice anyway, and they flagged
it honestly as a *dodge* rather than a fix.

## What this loop says about the method

Three of the last four real faults came from projects under load, not from
testing the system against itself:

| found by | fault | severity |
|---|---|---|
| Ringfall | playtest race → green PASS under the wrong plan | false-pass |
| Ringfall | `still` on a scalar probe cannot fail | false-pass (latent) |
| paper-boat | `gd check` blind to embedded scripts | friction |
| paper-boat | my fix for the above → false-fail | **false-fail** |

The last row is the important one: **the projects now catch the system's
regressions, including regressions introduced to fix their own findings.** That
loop closed on its own, in under an hour, without me asking.

## Carried forward

1. **24** — `--smoke` still unexercised; every current kickoff predates it.
2. Ringfall is at `phase_gate` with five gates queued. Next loop should see
   whether a completed greybox actually passes them — the first end-to-end test
   of the whole beat.
3. `gd version` exits 1 whenever the install has moved since a project recorded
   its baseline. That is correct, but it means `doctor`-style green boards will
   show a red until each project re-records. Watch whether that reads as signal
   or as noise; if noise, it should warn rather than fail.

---

# Loop 9 — 22:00Z · the first complete greybox, and STATE was lying about it

| game | jobs | passed | running | next action | verdicts archived | findings |
|---|---|---|---|---|---|---|
| Ringfall | 13 | **13** | 0 | `phase_gate` | 7 | 2 |
| the-last-lamp | 7 | 4 | 0 | dispatch job 05 | 12 | 1 |
| henhouse | 9 | 4 | 0 | dispatch job 07 | 9 | 1 |
| paper-boat | 6 | 3 | **2** | **`in_flight`** | 5 | 3 |

Two fixes visibly carrying load:

- **paper-boat returns `in_flight`** — *"wave 3 job(s) already dispatched and not
  yet recorded"*. Exactly the fault-9 fix doing its job: two concurrent jobs, and
  the driver refuses to hand either to a second agent.
- **33 verdicts archived** across the four, in a directory that was dead until
  loop 4. `/gd:ship`'s retro now has a per-attempt history to read.

the-last-lamp closed a gauntlet: *"gauntlet CLOSED: A ships; three checkpoints
resolved"*.

## Ringfall passed its phase gate — 52 minutes before I noticed

`RUN.json` records it plainly:

```json
{"at": "2026-09-12T21:08:23Z", "ok": true, "failed": []}
```

**All five gates green** — `check`, `minute_one`, `loop_complete`,
`can_lose_dawn`, `can_lose_abandoned`. That is the first complete greybox to go
through the entire system: contracts → roadmap → 13 jobs in 6 waves → every job
graded → the phase's own definition of done, measured.

And it is correctly *stopped* there, waiting for a human, which is what
`/gd:run` is supposed to do at a green phase gate.

## 28 + 29 — STATE was stale, and in two different ways

`last_verdict: none` in **all four** games, despite 33 archived verdicts and a
green phase gate.

**28. Nothing ever wrote `last_verdict`.** Two command docs mention setting it
(`/gd:build`, `/gd:playtest`) and neither is the driver. `/gd:run` — the thing
that actually grades every job — never touched it. A field in the template that
no code writes is worse than no field: it reads as "no verdict yet" forever.

**29. A green phase gate never reached STATE.** `run gate` set
`RUN.json.status = gate_green` and stopped there. STATE — the file a resumed
session trusts first — said `greybox_passed: no` with no indication that the
gate had been cleared at all. Ringfall's greybox had been green for the better
part of an hour and nothing outside `RUN.json` knew.

**Fixed in the CLI, not in the docs**, because the docs were already right and
were being skipped:

- `gd run record` stamps `last_verdict: <phase> job NN pass|fail (<model>)`.
- `gd run gate` stamps `last_verdict: <phase> N/M gates green` and
  `phase_gate: green|red`.
- New `phase_gate` field in the STATE template.

**`greybox_passed` is deliberately still not automatic.** A green phase gate is
necessary and not sufficient — Law 1 also requires a person to play it and
answer *would I press start again?* Auto-setting it on a green gate would have
been the easy fix and would have quietly deleted the most valuable gate in the
system. `phase_gate: green` with `greybox_passed: no` is now the documented,
correct state while waiting for the human, and the STATE template says who owns
which field.

Verified: a job record writes `01-greybox job 01 pass (opus)`; a green gate
writes `phase_gate: green` and `01-greybox 2/2 gates green`; `greybox_passed`
stays `no`.

Backfilled all four live games from their own `RUN.json`, so STATE now says what
happened:

```
TestGame    green | 01-greybox phase gate GREEN at 2026-09-12T21:08:23Z
testgame2         | 01-greybox jobs 4/7 passed, gate not yet run
testgame3         | 01-greybox jobs 4/9 passed, gate not yet run
testgame4         | 01-greybox-loop jobs 3/6 passed, gate not yet run
```

## The pattern in these last three loops

Every fault since loop 7 has been of one shape: **the system knew something and
failed to write it where the next reader would look.**

| loop | the system knew | where it failed to say so |
|---|---|---|
| 7 | scalar probe history existed frame by frame | nowhere — discarded, so `still` could not fail |
| 8 | which toolchain produced a verdict | nowhere — no fingerprint |
| 9 | the phase gate was green | only `RUN.json`, not STATE |

Not logic errors. Plumbing between a component that measured something and the
artefact someone reads later. Worth remembering when reviewing the rest: the
question to ask is not "is this correct" but "where does this end up, and who
reads it".

## Carried forward

1. **24** — `--smoke` still unexercised; every current kickoff predates it.
2. Ringfall is one human playtest away from `greybox_passed: yes` and the first
   `/gd:ship`. That will be the first exercise of the ship beat, the
   `SYSTEM_FINDINGS` sweep, and the roadmap advancing to stage 02.
3. `gd version` exits 1 once a project's baseline is older than the install. As
   predicted in loop 8, all four now do — the fix is either to re-record on
   purpose at phase boundaries, or to soften it to a warning outside `--check`.
   Decide next loop rather than letting it become noise everyone ignores.
