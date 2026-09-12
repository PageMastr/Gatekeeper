extends Node3D
class_name GDLightingRig
## One rig owns every global light in the scene, and every look is a *named preset*.
##
## Why this exists: lighting is the single largest quality lever in an AI-built
## game, and it is also the one an agent cannot judge from code. So we make it
## data. The agent writes presets; a human (or gd-critic, on screenshots) picks
## the winner; the winner is a few numbers in a dictionary that never drift.
##
## Two hard rules encoded here:
##   * ONE hero light. Everything else falls off into black - that fall-off is
##     what reads as depth. A second bright light flattens the scene.
##   * Shadows are rationed. Each shadow-casting light re-renders the scene from
##     its own point of view; four of them cost four extra scene draws. The
##     `shadow_budget` is enforced, not advisory.

## Every preset needs the ten required keys below. Nine more are optional and
## defaulted, so an existing preset keeps working untouched:
##
##   sun_color_key / fog_color_key / ambient_color_key  - Color Bible keys,
##       resolved against the project Palette; they override the literal
##   sky_top_key / sky_horizon_key / sky_ground_key     - sky gradient colours
##   sky_curve, sky_top_energy, sky_ground_energy       - sky gradient shape
##   fog_sky_affect, fog_light_energy                   - fog against the sky
##   sky_ambient_contribution                           - how much sky lights the scene
##
## PROJECT-SPECIFIC PRESETS DO NOT BELONG HERE. Add them to a subclass or to the
## project's own scene. A preset naming a palette key that only one game defines
## is broken in every other game - observed: two presets referencing
## `sky_nebula_far` leaked into three games that have no such swatch.
const PRESETS: Dictionary = {
	"midday": {
		"sun_energy": 1.6, "sun_color": Color(1.0, 0.98, 0.94), "sun_angle": Vector2(-55, 35),
		"sun_shadow": true, "ambient_energy": 0.35, "sky_energy": 1.0,
		"fog": false, "fog_density": 0.004, "fog_color": Color(0.72, 0.78, 0.86),
		"exposure": 1.0,
	},
	"pale_day": {
		"sun_energy": 0.9, "sun_color": Color(0.92, 0.94, 1.0), "sun_angle": Vector2(-40, 20),
		"sun_shadow": true, "ambient_energy": 0.5, "sky_energy": 0.9,
		"fog": true, "fog_density": 0.012, "fog_color": Color(0.78, 0.82, 0.88),
		"exposure": 1.0,
	},
	"sunrise": {
		"sun_energy": 1.2, "sun_color": Color(1.0, 0.68, 0.42), "sun_angle": Vector2(-6, 95),
		"sun_shadow": true, "ambient_energy": 0.22, "sky_energy": 0.7,
		"fog": true, "fog_density": 0.018, "fog_color": Color(0.95, 0.66, 0.45),
		"exposure": 1.05,
	},
	"nightfall": {
		"sun_energy": 0.25, "sun_color": Color(0.55, 0.66, 0.9), "sun_angle": Vector2(-3, 250),
		"sun_shadow": true, "ambient_energy": 0.10, "sky_energy": 0.25,
		"fog": true, "fog_density": 0.02, "fog_color": Color(0.12, 0.16, 0.26),
		"exposure": 1.1,
	},
	"deep_night": {
		# The moon is deliberately dim. A bright moon lights the whole world from
		# the sky and then no local light - a fire, a lamp - can carry any mood.
		"sun_energy": 0.06, "sun_color": Color(0.42, 0.55, 0.85), "sun_angle": Vector2(-30, 210),
		"sun_shadow": false, "ambient_energy": 0.035, "sky_energy": 0.12,
		"fog": true, "fog_density": 0.03, "fog_color": Color(0.05, 0.07, 0.12),
		"exposure": 1.15,
	},
	"blizzard": {
		"sun_energy": 0.5, "sun_color": Color(0.86, 0.9, 0.96), "sun_angle": Vector2(-70, 0),
		"sun_shadow": false, "ambient_energy": 0.7, "sky_energy": 0.6,
		"fog": true, "fog_density": 0.09, "fog_color": Color(0.84, 0.87, 0.92),
		"exposure": 0.95,
	},
	"maintenance": {
		"sun_energy": 0.0, "sun_color": Color(1, 1, 1), "sun_angle": Vector2(-45, 0),
		"sun_shadow": false, "ambient_energy": 0.55, "sky_energy": 0.0,
		"fog": false, "fog_density": 0.0, "fog_color": Color(0.1, 0.1, 0.1),
		"exposure": 1.0,
	},
	"emergency": {
		"sun_energy": 0.0, "sun_color": Color(1, 0.15, 0.12), "sun_angle": Vector2(-45, 0),
		"sun_shadow": false, "ambient_energy": 0.05, "sky_energy": 0.0,
		"fog": true, "fog_density": 0.035, "fog_color": Color(0.25, 0.03, 0.03),
		"exposure": 1.2,
	},
	"brownout": {
		"sun_energy": 0.0, "sun_color": Color(1, 0.8, 0.5), "sun_angle": Vector2(-45, 0),
		"sun_shadow": false, "ambient_energy": 0.12, "sky_energy": 0.0,
		"fog": true, "fog_density": 0.02, "fog_color": Color(0.08, 0.07, 0.05),
		"exposure": 1.1, "flicker": 0.55,
	},
	"blackout": {
		# Never fully black. You always keep one readable line - a floor strip,
		# a door seal - or the player stops playing and starts quitting.
		"sun_energy": 0.0, "sun_color": Color(1, 1, 1), "sun_angle": Vector2(-45, 0),
		"sun_shadow": false, "ambient_energy": 0.012, "sky_energy": 0.0,
		"fog": true, "fog_density": 0.05, "fog_color": Color(0.01, 0.012, 0.02),
		"exposure": 1.3,
	},
}

## NOTE ON THE SETTER: the setter refreshes, and `apply_preset()` writes through
## the setter. Never let the refresh path assign `preset` again - that is a
## setter calling itself, which is unbounded recursion and hard-crashes the
## process (0xC0000005) with no GDScript stack trace to explain it.
@export_enum("midday", "pale_day", "sunrise", "nightfall", "deep_night", "blizzard",
		"maintenance", "emergency", "brownout", "blackout")
var preset: String = "deep_night":
	set(v):
		preset = v
		if is_inside_tree():
			_refresh()

@export var shadow_budget: int = 4
@export var enforce_shadow_budget: bool = true

var sun: DirectionalLight3D
var world: WorldEnvironment
var _flicker: float = 0.0
var _t: float = 0.0


func _ready() -> void:
	sun = get_node_or_null("Sun") as DirectionalLight3D
	if sun == null:
		sun = DirectionalLight3D.new()
		sun.name = "Sun"
		add_child(sun)
	world = get_node_or_null("World") as WorldEnvironment
	if world == null:
		world = WorldEnvironment.new()
		world.name = "World"
		world.environment = _default_env()
		add_child(world)
	_refresh()
	if enforce_shadow_budget:
		call_deferred("enforce_shadows")


func _default_env() -> Environment:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	sky.sky_material = ProceduralSkyMaterial.new()
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.ssao_enabled = false
	env.glow_enabled = true
	env.glow_intensity = 0.35
	return env


func apply_preset(preset_name: String) -> void:
	"""Public entry point. Writes through the setter, which calls _refresh()."""
	if not PRESETS.has(preset_name):
		push_warning("GDLightingRig: unknown preset '%s'" % preset_name)
		return
	preset = preset_name
	if not is_inside_tree():
		_refresh()


## Optional per-preset keys, all defaulted, all applied below. A preset may name
## Color Bible keys instead of literals - `"sun_color_key": "accent_warm"` - and
## the rig resolves them against the project's generated `Palette`. That closes a
## real hole: a rig full of hardcoded `Color("d9953a")` literals quietly breaks
## Law 8, because the lighting is the one place a fourth shade of grey is least
## visible and most damaging.
##
## Resolution is soft. An unknown key, or a project with no Palette yet, falls
## back to the literal already in the preset rather than asserting - the harness
## must boot in a scaffold that has no Color Bible filled in.
const _PALETTE_PATH := "res://scripts/palette.gd"
static var _palette_colors: Dictionary = {}
static var _palette_loaded := false


static func palette_color(key: String, fallback: Color) -> Color:
	if key == "":
		return fallback
	if not _palette_loaded:
		_palette_loaded = true
		if ResourceLoader.exists(_PALETTE_PATH):
			var scr = load(_PALETTE_PATH)
			if scr != null and "COLORS" in scr:
				_palette_colors = scr.COLORS
	return _palette_colors.get(key, fallback)


func _refresh() -> void:
	if not PRESETS.has(preset):
		return
	var p: Dictionary = PRESETS[preset]
	var sun_col: Color = palette_color(str(p.get("sun_color_key", "")), p["sun_color"])
	var fog_col: Color = palette_color(str(p.get("fog_color_key", "")), p["fog_color"])
	if sun:
		sun.light_energy = p["sun_energy"]
		sun.light_color = sun_col
		sun.shadow_enabled = p["sun_shadow"]
		var a: Vector2 = p["sun_angle"]
		sun.rotation_degrees = Vector3(a.x, a.y, 0.0)
		sun.visible = p["sun_energy"] > 0.0
	if world and world.environment:
		var env := world.environment
		env.ambient_light_energy = p["ambient_energy"]
		env.background_energy_multiplier = p["sky_energy"]
		env.ambient_light_source = (Environment.AMBIENT_SOURCE_SKY if p["sky_energy"] > 0.0
				else Environment.AMBIENT_SOURCE_COLOR)
		# Ambient colour: an explicit key wins, else the fog colour, which is the
		# convention the built-in presets already follow.
		env.ambient_light_color = palette_color(
				str(p.get("ambient_color_key", "")), fog_col)
		env.ambient_light_sky_contribution = float(p.get("sky_ambient_contribution", 1.0))
		env.fog_enabled = p["fog"]
		env.fog_density = p["fog_density"]
		env.fog_light_color = fog_col
		env.fog_light_energy = float(p.get("fog_light_energy", 1.0))
		env.fog_sky_affect = float(p.get("fog_sky_affect", 1.0))
		env.tonemap_exposure = p["exposure"]
		# Sky gradient. A bright outdoor game and a nebula both need this and the
		# rig used to expose neither, which is why two projects reached for it.
		var sky_mat := env.sky.sky_material as ProceduralSkyMaterial if env.sky else null
		if sky_mat != null:
			sky_mat.sky_top_color = palette_color(
					str(p.get("sky_top_key", "")), sky_mat.sky_top_color)
			sky_mat.sky_horizon_color = palette_color(
					str(p.get("sky_horizon_key", "")), sky_mat.sky_horizon_color)
			sky_mat.ground_bottom_color = palette_color(
					str(p.get("sky_ground_key", "")), sky_mat.ground_bottom_color)
			sky_mat.ground_horizon_color = palette_color(
					str(p.get("sky_horizon_key", "")), sky_mat.ground_horizon_color)
			sky_mat.sky_curve = float(p.get("sky_curve", sky_mat.sky_curve))
			sky_mat.sky_energy_multiplier = float(p.get("sky_top_energy", 1.0))
			sky_mat.ground_energy_multiplier = float(p.get("sky_ground_energy", 1.0))
	_flicker = float(p.get("flicker", 0.0))


func _process(delta: float) -> void:
	if _flicker <= 0.0 or sun == null:
		return
	_t += delta
	# Power failing: irregular, not a sine. A regular pulse reads as a disco.
	var n := sin(_t * 37.0) * sin(_t * 11.3) * sin(_t * 3.1)
	var e: float = PRESETS[preset]["ambient_energy"]
	if world and world.environment:
		world.environment.ambient_light_energy = maxf(e * (1.0 - _flicker * absf(n)), 0.002)


func enforce_shadows() -> int:
	"""Turn off the cheapest shadow casters until we are inside budget.

	Ranked by light_energy: the dim fill lights lose their shadows first, the
	hero light keeps its own. Returns how many were disabled."""
	var lights: Array[Light3D] = []
	for n in _walk(get_tree().current_scene if get_tree().current_scene else self):
		if n is Light3D and (n as Light3D).shadow_enabled:
			lights.append(n as Light3D)
	if lights.size() <= shadow_budget:
		return 0
	lights.sort_custom(func(a: Light3D, b: Light3D): return a.light_energy < b.light_energy)
	var disabled := 0
	while lights.size() - disabled > shadow_budget:
		lights[disabled].shadow_enabled = false
		disabled += 1
	push_warning("GDLightingRig: disabled shadows on %d light(s) to stay inside shadow_budget=%d"
			% [disabled, shadow_budget])
	return disabled


func _walk(root: Node) -> Array:
	if root == null:
		return []
	var out: Array = [root]
	for c in root.get_children():
		out.append_array(_walk(c))
	return out


func snapshot() -> Dictionary:
	"""Dump live values as a preset literal, so a human tuning sliders produces
	source code instead of a memory."""
	if sun == null or world == null or world.environment == null:
		return {}
	var env := world.environment
	return {
		"sun_energy": snappedf(sun.light_energy, 0.01),
		"sun_color": sun.light_color,
		"sun_angle": Vector2(snappedf(sun.rotation_degrees.x, 0.1), snappedf(sun.rotation_degrees.y, 0.1)),
		"sun_shadow": sun.shadow_enabled,
		"ambient_energy": snappedf(env.ambient_light_energy, 0.001),
		"sky_energy": snappedf(env.background_energy_multiplier, 0.01),
		"fog": env.fog_enabled,
		"fog_density": snappedf(env.fog_density, 0.001),
		"fog_color": env.fog_light_color,
		"exposure": snappedf(env.tonemap_exposure, 0.01),
	}
