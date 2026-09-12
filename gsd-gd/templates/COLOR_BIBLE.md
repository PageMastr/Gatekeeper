# Color Bible — {{NAME}}

> **This file is a contract, not a mood board.**
> Every material in Blender and every colour in Godot resolves against the table
> below. `gdblend.mat("key")` raises on an unknown key, and `gd palette sync`
> regenerates `res://scripts/palette.gd` from this table — so an agent that
> invents a fourth shade of grey fails loudly instead of quietly.
>
> To add a swatch: add the row **and** the reason. A palette that grows without
> reasons is just a palette that has stopped working.

- reference: <path or URL to the image that started this>
- lighting condition of the reference: <e.g. overcast daylight>
- lighting condition of the game: <e.g. deep night, one firelight>
- translated: <yes/no — see "Translation" below>
- locked: <date, or "no" while still exploring>

## Translation

The reference almost never sits in the game's lighting condition. Translate
every swatch **once, here**, before anything is built — never per-asset, or
each asset drifts on its own.

For a daylight reference going to night: pull saturation toward the ambient
hue, crush value on anything not touched by the hero light, and keep exactly
one warm family for the light source so it reads as the only source of heat.

## Palette

| key | hex | roughness | metallic | emission | role |
|---|---|---|---|---|---|
| base_dark | #12161f | 0.85 | 0.0 | 0.0 | everything in shadow; the ground tone of the game |
| base_mid | #2a3342 | 0.80 | 0.0 | 0.0 | large surfaces catching ambient only |
| base_light | #55637a | 0.72 | 0.0 | 0.0 | surfaces facing the hero light |
| accent_warm | #e08a3c | 0.55 | 0.0 | 0.0 | the one warm family — light source, embers, signage |
| accent_cool | #4f7fa8 | 0.60 | 0.0 | 0.0 | sky bounce, cold metal, distance |
| metal_raw | #6e7479 | 0.38 | 0.9 | 0.0 | exposed structural metal |
| metal_worn | #4a4d50 | 0.62 | 0.8 | 0.0 | handled, scuffed metal |
| organic_dark | #1d2a1e | 0.88 | 0.0 | 0.0 | foliage in shadow |
| organic_light | #4a6b41 | 0.80 | 0.0 | 0.0 | foliage catching light |
| emissive_signal | #ff4436 | 0.40 | 0.0 | 2.5 | alarms, danger reads, emergency lighting |
| emissive_guide | #7fe3d0 | 0.40 | 0.0 | 1.8 | the readable line that survives a blackout |

## Rules that go with the table

1. **One warm family.** `accent_warm` is the only heat in the frame. Two warm
   families and the eye stops knowing where the light comes from.
2. **Shadow is a colour, not an absence.** `base_dark` is not `#000000`. Pure
   black kills silhouette reading and looks like missing geometry.
3. **Emission is for information.** If it glows, it should mean something the
   player must act on. Decorative glow spends the same budget and teaches the
   player to ignore glow.
4. **Roughness carries more than colour.** A wrong roughness reads as the wrong
   material even with the right hex. Tune roughness before re-tinting.
5. **Texture scale beats texture choice.** The same panel at the wrong world
   scale reads as concrete. Set metres-per-tile deliberately and write it down
   in the asset spec.

## Change log

Get the date from the tool, never from memory — `gd now`. An agent asked to
stamp a row will invent a plausible time every single time (observed: sixteen
rows stamped `18:40:00Z` in a file whose real mtime was `18:09:49`).

| date | change | why |
|---|---|---|
| {{DATE}} | seeded from template | starting point; replace every row from the real reference |
