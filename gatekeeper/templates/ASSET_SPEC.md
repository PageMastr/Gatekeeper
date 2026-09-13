# ASSET SPEC — {{NAME}}

- class: <prop | hero_prop | environment_module | character>
- generator: `generators/{{SLUG}}.py`
- output: `assets/models/{{SLUG}}.glb`

## Dimensions (metres, 1 unit = 1 m)

| axis | size | tolerance |
|---|---|---|
| x | | ±0.001 |
| y | | ±0.001 |
| z | | ±0.001 |

- snap grid: 0.25 m — every bound must land on it (`gdblend.check_grid`)
- origin: <at base centre / at pivot / at socket>
- forward axis: -Z (Godot convention after Y-up export)

## Palette keys used

Only keys from @.planning/COLOR_BIBLE.md.

- <key> → <which surfaces>

## Budget

- tris: ≤ <n> (`gdblend.check_tris`)
- materials: ≤ <n> (each extra material is an extra draw call per instance)

## Silhouette

Describe the shape in terms an agent can build out of primitives. Simple forms
done well beat detailed forms done badly — the light provides the detail. Boxes
and a roof, bevelled, is a house. A "realistic" mesh is not on the table.

- <…>

## Checks the generator must run

- [ ] `check_dims` against the table above
- [ ] `check_grid` (modules only)
- [ ] `check_tris`
- [ ] `check_palette` — no material outside the Color Bible
- [ ] `check_transforms` — scale applied, no baked-in 0.01
- [ ] `check_origin_at_base` (props that sit on ground)

## Done when

- [ ] `gd asset generators/{{SLUG}}.py` reports `ok: true`
- [ ] GLB imports into Godot with no import warnings
- [ ] Placed in the lab scene, screenshotted, passed by gd-critic
