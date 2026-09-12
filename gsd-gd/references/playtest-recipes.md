# Playtest recipes

`gd playtest <plan>` runs a plan from `<project>/lab/`. It drives the game with
synthetic input, asserts on numbers, screenshots named moments, measures the
frame, and writes `verdict.json`.

## Plan anatomy

```json
{
  "name": "door-opens",
  "scene": "res://scenes/station.tscn",
  "warmup_frames": 30,
  "timeout_frames": 2400,
  "probes":  { "player": { "path": "Player", "property": "global_position" } },
  "steps":   [ { "wait": 20 },
               { "shot": "spawn" },
               { "actions": ["move_forward"], "seconds": 2.0, "label": "to_door" },
               { "actions": ["interact"], "frames": 6 },
               { "wait": 45 },
               { "shot": "door_open" } ],
  "checks":  [ { "name": "reached_door", "kind": "moved", "probe": "player", "min": 4.0 },
               { "name": "door_open", "kind": "expr", "expr": "get_node('Door').is_open" } ],
  "perf":    { "sample_frames": 120 }
}
```

Steps run pinned at 60 fps, so `"frames": 120` and `"seconds": 2.0` are the same
thing. Use `seconds` for readability.

`probes` are sampled every frame during steps; that is how `moved` knows path
length rather than just start-to-end displacement (a player who walks in a
circle has travelled but not displaced — usually you want to know both, and the
verdict reports both).

## Check kinds

| kind | fields | asserts |
|---|---|---|
| `moved` | `probe`, `min`, `via?`, `via_radius?` | total path length ≥ min, **and** the probe entered every node in `via` |
| `still` | `probe`, `max` | probe barely moved (idle, frozen, anchored) |
| `node_exists` | `path` | node present in the loaded scene |
| `prop_between` | `path`, `property`, `min`, `max` | numeric property inside range |
| `prop_gt` / `prop_lt` | `path`, `property`, `value` | numeric comparison |
| `prop_eq` | `path`, `property`, `value` | string-compared equality |
| `probe_min` / `probe_max` | `probe`, `gt`/`lt`/`min`/`max` | the lowest/highest value a **numeric** probe reached at any point in the run |
| `probe_at` | `probe`, `label`, `gt`/`lt`/`equals`/`min`/`max` | the probe's value at the end of the step with that `label` |
| `expr` | `expr` | arbitrary GDScript `Expression`, evaluated against the scene root |

**`moved` and `still` are for position probes only.** On a numeric probe they
now fail with an explanation rather than passing — `still` on a float used to be
green for any tolerance, because path length is only accumulated for `Vector3`.
A check that cannot fail is worse than no check.

**To assert something about a *moment*, label the step and use `probe_at`.**
Every check is otherwise evaluated once, after the last step, so an end-of-run
value cannot distinguish two causes that both reset the same field:

```json
{"steps": [{"actions": ["wait_for_dawn"], "seconds": 3, "label": "dawn_fired"}],
 "checks": [{"name": "had_faith_when_dawn_hit", "kind": "probe_at",
             "probe": "mika_faith", "label": "dawn_fired", "gt": 0}]}
```

`property` accepts sub-paths: `"global_position:y"`, `"velocity:x"`.

`expr` is the escape hatch — `"get_node('Player').health < 100"`,
`"get_tree().get_nodes_in_group('enemy').size() == 3"`. Prefer a typed kind when
one fits; `expr` failures are harder to read.

## The standing recipes

**`minute_one.json`** — the project's first gate, created by `gd init`. The first
60 seconds of the Core Loop. Must pass on grey boxes before any asset work.

**`loop_complete.json`** — one entire turn of the Core Loop, including the state
change that makes turn two different from turn one. This is the gate that
closes `/gd:greybox`.

**`can_lose.json`** — drive the player into the failure state deliberately and
assert it happened. A loop you cannot lose is not a loop, and this check is
routinely forgotten.

**`lab/<system>.json`** — one system, isolated. Gait, camera, weapon feel. Small
scene, deterministic, fast.

**`perf_worst_case.json`** — the heaviest scene, standing where the most is
visible, looking at the most expensive direction. Budget gates only mean
something if they are measured at the worst case, not the spawn point.

## Lint before you run

```bash
gd playtest <plan> --lint
```

No Godot launch. Catches a typo'd input action (and names the ones that exist),
an unknown check kind, a check referencing an undeclared probe, an empty `expr`,
and a `moved` check with no `via` (an **error** - add `via`, or set
`"distance_only": true` to state that distance really is the claim).
Run it on every plan you write — it is
seconds versus a full engine boot.

## Smoke mode

```bash
gd playtest <plan> --smoke
```

Gates on the harness booting, the scene loading and shots being written; records
content checks as **pending** instead of failed. For kickoff, when the plan
describes a game that does not exist yet. Never use it as a real gate.

## Writing a good check

- **Assert the outcome, not the implementation.** "player moved 4 m" survives a
  locomotion rewrite; "velocity.z == -4.0" does not.
- **A distance is not a route.** `moved` with only a `min` is satisfied by any
  open floor — observed passing at 41 m in a scene containing no spine at all,
  which is the "passes for the wrong reason" failure this file warns about.
  Always add `via`:
  `{"kind": "moved", "probe": "player", "min": 8.0, "via": ["Spine/Seg01", "Spine/Seg02"]}`
  A `via` node is entered by AABB containment when it has visual extents, else
  by proximity within `via_radius` (default 3 m). The verdict also reports
  `directness` (straight ÷ path) and warns below 0.35 — wandering, not traversing.
- **Bound both sides.** `prop_between` on `global_position:y` catches falling
  through the floor *and* being launched into orbit. A one-sided check catches
  half the bugs.
- **One check, one claim.** A check that fails should tell you what broke.
- **Include a negative.** Something that should *not* happen. Most regressions
  are things that started happening.
- **Screenshot before and after the interesting moment**, not during. A frame
  mid-transition tells a critic nothing.

## Reading a verdict

`verdict.json` lands in `<project>/.gd_out/<plan>/` next to `shots/`.

- `checks[]` — per-check pass/fail with the actual measured value in `detail`.
- `perf` — `fps_avg`, `fps_1pct_low`, `frame_ms_worst`, `draw_calls_max`,
  `primitives_max`, `lights`, `shadow_lights`.
- `budget_fails[]` — budget violations from `gsd-gd/config.json`.
- `runtime_errors[]` — `SCRIPT ERROR` lines scraped from the process output. The
  harness cannot see these; a run that "passed" while spraying script errors has
  not passed, so they fail the verdict.
- `shot_files[]` — hand these to `gd-critic`. **Not** to the agent that built
  the thing.

Exit code is 0 only if every check, every budget, and zero runtime errors agree.

## Never run two playtests at once by hand

`gd playtest` is now safe under concurrency — each run gets a unique plan file,
and a verdict whose check names do not belong to the plan you asked for is
**refused** rather than reported. That guard exists because the shared inbox
once produced a green PASS filed under the wrong plan's name.

If you see *"verdict does not match the plan that was run"*, something else was
in flight. Re-run that plan alone; the answer you got was not about your plan.

## When the harness itself is the problem

- *"harness produced no verdict"* → the harness scene failed to load. Look for a
  GDScript parse error in the log tail. `--quit-after` means it will not hang.
- *`input_action:<name>` failed* → the plan presses an action the project does
  not define. Fix `project.godot` or the plan; this is a real drift finding.
- *`shot:<label>` failed with "cannot screenshot under --headless"* → drop
  `--headless`. The dummy renderer has no framebuffer to read.
- *Every movement check fails with a tiny path length* → you are probably not
  on the pinned clock; check `STEP_FPS` handling in `gd_playtest.gd`.
