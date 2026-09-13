extends CanvasLayer
class_name GDLightingPanel
## In-game lighting control panel. F9 toggles it.
##
## This is the highest-leverage debug tool in the whole system. An agent cannot
## see; a human can, but cannot remember numbers. So: the human drags sliders
## until the scene looks right, presses "Copy preset", and pastes a ready-made
## dictionary entry into gd_lighting_rig.gd. Taste goes in, source code comes out.
##
## Add to any scene: instantiate this alongside a GDLightingRig and point
## `rig_path` at it.

@export var rig_path: NodePath = ^"../LightingRig"
@export var toggle_key: Key = KEY_F9
@export var start_visible: bool = false

var rig: GDLightingRig
var _rows: Dictionary = {}
var _panel: PanelContainer
var _status: Label


func _ready() -> void:
	layer = 128
	rig = get_node_or_null(rig_path) as GDLightingRig
	if rig == null:
		push_warning("GDLightingPanel: no GDLightingRig at %s - panel disabled" % rig_path)
		return
	_build()
	visible = start_visible


func _input(e: InputEvent) -> void:
	if e is InputEventKey and e.pressed and not e.echo and (e as InputEventKey).keycode == toggle_key:
		visible = not visible


func _build() -> void:
	_panel = PanelContainer.new()
	_panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_panel.position = Vector2(-360, 12)
	_panel.custom_minimum_size = Vector2(348, 0)
	add_child(_panel)

	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)
	_panel.add_child(box)

	var title := Label.new()
	title.text = "LIGHTING  (F9)"
	box.add_child(title)

	var presets := OptionButton.new()
	var names := GDLightingRig.PRESETS.keys()
	for i in names.size():
		presets.add_item(str(names[i]), i)
		if names[i] == rig.preset:
			presets.select(i)
	presets.item_selected.connect(func(i: int):
		rig.apply_preset(str(names[i]))
		_sync())
	box.add_child(presets)

	_slider(box, "sun_energy", 0.0, 4.0, 0.01)
	_slider(box, "ambient_energy", 0.0, 1.5, 0.005)
	_slider(box, "sky_energy", 0.0, 2.0, 0.01)
	_slider(box, "fog_density", 0.0, 0.15, 0.001)
	_slider(box, "exposure", 0.2, 2.5, 0.01)
	_slider(box, "sun_pitch", -90.0, 0.0, 0.5)
	_slider(box, "sun_yaw", 0.0, 360.0, 1.0)

	var shadows := CheckBox.new()
	shadows.text = "sun shadow"
	shadows.button_pressed = rig.sun.shadow_enabled
	shadows.toggled.connect(func(on: bool): rig.sun.shadow_enabled = on)
	box.add_child(shadows)

	var copy := Button.new()
	copy.text = "Copy preset to clipboard"
	copy.pressed.connect(_copy_preset)
	box.add_child(copy)

	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.custom_minimum_size = Vector2(330, 0)
	box.add_child(_status)
	_sync()


func _slider(parent: VBoxContainer, key: String, lo: float, hi: float, step: float) -> void:
	var row := HBoxContainer.new()
	var lab := Label.new()
	lab.text = key
	lab.custom_minimum_size = Vector2(118, 0)
	row.add_child(lab)
	var s := HSlider.new()
	s.min_value = lo
	s.max_value = hi
	s.step = step
	s.custom_minimum_size = Vector2(160, 0)
	s.value_changed.connect(func(v: float): _set_value(key, v))
	row.add_child(s)
	var val := Label.new()
	val.custom_minimum_size = Vector2(52, 0)
	row.add_child(val)
	parent.add_child(row)
	_rows[key] = {"slider": s, "label": val}


func _set_value(key: String, v: float) -> void:
	var env: Environment = rig.world.environment
	match key:
		"sun_energy":
			rig.sun.light_energy = v
			rig.sun.visible = v > 0.0
		"ambient_energy": env.ambient_light_energy = v
		"sky_energy": env.background_energy_multiplier = v
		"fog_density":
			env.fog_density = v
			env.fog_enabled = v > 0.0
		"exposure": env.tonemap_exposure = v
		"sun_pitch": rig.sun.rotation_degrees.x = v
		"sun_yaw": rig.sun.rotation_degrees.y = v
	if _rows.has(key):
		_rows[key]["label"].text = "%.3f" % v


func _sync() -> void:
	if rig == null or rig.world == null or rig.world.environment == null:
		return
	var env: Environment = rig.world.environment
	var vals := {
		"sun_energy": rig.sun.light_energy,
		"ambient_energy": env.ambient_light_energy,
		"sky_energy": env.background_energy_multiplier,
		"fog_density": env.fog_density,
		"exposure": env.tonemap_exposure,
		"sun_pitch": rig.sun.rotation_degrees.x,
		"sun_yaw": rig.sun.rotation_degrees.y,
	}
	for k in vals:
		if _rows.has(k):
			_rows[k]["slider"].set_value_no_signal(vals[k])
			_rows[k]["label"].text = "%.3f" % float(vals[k])
	_status.text = "preset: %s" % rig.preset


func _copy_preset() -> void:
	var s := rig.snapshot()
	var c := func(col: Color) -> String:
		return "Color(%.3f, %.3f, %.3f)" % [col.r, col.g, col.b]
	var text := '\t"NAME_ME": {\n'
	text += '\t\t"sun_energy": %s, "sun_color": %s, "sun_angle": Vector2(%s, %s),\n' % [
			s["sun_energy"], c.call(s["sun_color"]), s["sun_angle"].x, s["sun_angle"].y]
	text += '\t\t"sun_shadow": %s, "ambient_energy": %s, "sky_energy": %s,\n' % [
			str(s["sun_shadow"]).to_lower(), s["ambient_energy"], s["sky_energy"]]
	text += '\t\t"fog": %s, "fog_density": %s, "fog_color": %s,\n' % [
			str(s["fog"]).to_lower(), s["fog_density"], c.call(s["fog_color"])]
	text += '\t\t"exposure": %s,\n\t},\n' % s["exposure"]
	DisplayServer.clipboard_set(text)
	_status.text = "Copied. Paste into GDLightingRig.PRESETS and rename it.\n" + text
	print(text)
