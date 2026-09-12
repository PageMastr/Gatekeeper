---
description: Author or tune lighting presets — the largest quality lever in the game
argument-hint: [scene or mood, e.g. "greenhouse at night" or "emergency"]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, Skill
---

# /gd:light — lighting as data

@gsd-gd/references/godot-patterns.md

Subject: **$ARGUMENTS**

Law 10: lighting is the largest quality lever, and it is data. The difference
between a scene that reads as current-gen and one that reads two generations old
is usually a single number — how bright the sky is.

## The discipline

- **One hero light.** Everything else falls off into black. That fall-off *is*
  depth. If everything is legible everywhere, the scene is flat no matter how
  good the assets are.
- **The sky is dim.** Light the world from the sky and nothing you place can
  create mood — the fire stops mattering. Push `sky_energy` down until the local
  light carries the frame.
- **Fill lights never cast shadows.** Law 11: shadows are the bill.
- **Blackout is never `#000000`.** Keep exactly one readable line — a floor
  strip, a door seal — or the player stops playing and starts quitting.
- **Emission means information.** Decorative glow spends the same budget and
  teaches the player to ignore glow.

## Tune with the panel, not by guessing

`GDLightingPanel` is already in the greybox scene. Press **F9** in the running
game: sliders for sun energy, ambient, sky, fog density, exposure, sun angle,
plus a shadow toggle.

Drag until it looks right, press **Copy preset to clipboard**, then paste the
result into **the project**, not the shared rig.

**Game-specific presets do not go in `GDLightingRig.PRESETS`.** That file lives
in the install root, shared by every game on the machine — one game's presets
there leaked into three others, two of them naming a palette swatch those games
do not define. Put yours in a project subclass or the scene that uses them.

A preset may name Color Bible keys instead of hex literals — `"sun_color_key":
"accent_warm"`, `"sky_top_key": "..."` — and the rig resolves them against the
project's generated `Palette`, falling back to the literal when a key is absent.
Prefer keys: a hex literal in the lighting rig is a fourth shade of grey in the
one place it is hardest to notice. Taste goes in, source code comes out —
which is the point. A human can see; a human cannot remember numbers.

```bash
"D:/Godot/GodotEngine/bin/godot.windows.editor.x86_64.console.exe" --path game/<slug>
```

## Presets that ship by default

`midday`, `pale_day`, `sunrise`, `nightfall`, `deep_night`, `blizzard`,
`maintenance`, `emergency`, `brownout` (irregular flicker), `blackout`.

A starting library, not an answer. A game with its own reference needs its own
presets — derive them from `.planning/COLOR_BIBLE.md`, and make the fog and
ambient colours agree with the palette's `base_dark`. A fog colour that is not
in the Bible will fight every asset in the scene.

If you write GDScript here, use the `godot-api` skill first and
`gd check` after. `Environment` and `Light3D` property names changed in 4.x.

## Judge on frames, not in the editor

```bash
python gsd-gd/bin/gd.py playtest lab/light_<preset>
```

Shoot the *same* camera under each candidate preset, then hand the set to
**`gd-critic`** — one image per preset, identical angle. Law 6: if you tuned it,
you do not get to grade it.

Ask specifically: which frame has depth? Where does the eye go first? Is the warm
family doing the work, or is a second one competing with it?

## Budget check

Every preset must hold the shadow budget. `GDLightingRig.enforce_shadows()`
disables shadows on the lowest-energy casters and warns when it does — a warning
in the log means the scene went over budget and the policy chose for you.

```bash
python gsd-gd/bin/gd.py playtest lab/perf_worst_case
```

Watch `shadow_lights` and `draw_calls_max`. A preset that looks good and costs
20 fps is not a preset, it is a wish. If that is the tradeoff, say so and let
the user decide — then record it in `BUDGET.md` Deviations.

## Finish

Report: presets written or changed with their numbers, the critic's pick and its
reasoning, and the perf cost of the chosen look.
