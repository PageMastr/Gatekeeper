extends Node
## GSD-GameDev scripted playtest driver.
##
## Two questions, one run:
##   MEASURE - did the thing actually happen? (numbers, pass/fail, no opinions)
##   LOOK    - what did it look like while it happened? (screenshots for a critic)
##
## Driven by `gd playtest <plan.json>`. Never edit this file to make a test pass;
## edit the plan, or fix the game.
##
## A scene under test can surface its own measurements: anything it prints
## with the `GDLAB ` prefix is collected into `verdict.log`. Use that for the
## numbers behind a check, rather than adding a check whose real purpose is to
## print a value - that pushes measurement into the gate, where a loose bound
## is invisible.
##
## Plan schema (all keys optional except `scene`):
## {
##   "name": "corridor-walk",
##   "scene": "res://scenes/station.tscn",
##   "warmup_frames": 30,
##   "timeout_frames": 3600,
##   "probes":  { "player": {"path": "Player", "property": "global_position"} },
##   "steps":   [ {"wait": 20},
##                {"actions": ["move_forward"], "frames": 120, "label": "walk"},
##                {"shot": "at_door"},
##                {"actions": ["interact"], "frames": 6} ],
##   "checks":  [ {"name": "moved", "kind": "moved", "probe": "player", "min": 3.0,
##                 "via": ["Spine/Seg01", "Spine/Seg02"]},
##                {"name": "door",  "kind": "expr",  "expr": "get_node('Door').is_open"} ],
##   "perf":    { "sample_frames": 120 }
## }

var plan: Dictionary = {}
var out_dir: String = "res://.gd_out/_run"
var checks: Array = []
var probe_first: Dictionary = {}
var probe_last: Dictionary = {}
var probe_path_len: Dictionary = {}
var probe_visited: Dictionary = {}   # probe -> {node_name: true} for `via` checks
## Numeric probes get real history. Without it a scalar probe reported
## path_length 0.0, which made `{"kind": "still", "probe": <float>}` vacuously
## green - a check that could not fail. That is a latent false pass, and a gate
## that cannot fail is worse than no gate.
var probe_min: Dictionary = {}       # probe -> lowest value seen
var probe_max: Dictionary = {}       # probe -> highest value seen
var probe_numeric: Dictionary = {}   # probe -> true once a number is seen
## Value of every probe at the end of each labelled step, so a gate can assert
## "X was true AT THE MOMENT Y happened" instead of only at the end of the run.
var probe_at: Dictionary = {}        # label -> {probe: value}
var _via_nodes: Array[String] = []
var _via_radius: float = 0.0
var scene_root: Node = null
var shot_index: int = 0
var frames: int = 0
var timeout_frames: int = 3600
var finished: bool = false
var errors: Array = []

# perf accumulators
var perf_samples: Array[float] = []
var draw_calls_max: int = 0
var prims_max: int = 0
var sampling: bool = false


## Frames during the scripted steps are pinned to this rate, so a step's
## `frames` count means a predictable amount of *game time* (120 frames = 2 s).
## Without the cap the process runs at 1500 fps, 120 frames is 80 ms, and every
## "did the player move far enough" check fails for reasons that have nothing to
## do with the game. The cap is lifted for the perf window, where the whole
## point is to find out how fast the frame really is.
const STEP_FPS := 60


func _ready() -> void:
	_parse_cmdline()
	# Perf numbers are meaningless behind vsync - it would just report the refresh rate.
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = STEP_FPS
	get_window().set_flag(Window.FLAG_NO_FOCUS, true)
	_run()


func _parse_cmdline() -> void:
	var plan_path := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--plan="):
			plan_path = arg.substr(7)
		elif arg.begins_with("--out="):
			out_dir = arg.substr(6)
	if plan_path == "":
		_bail("no --plan= given on the command line")
		return
	var txt := FileAccess.get_file_as_string(plan_path)
	if txt == "":
		_bail("could not read plan at %s" % plan_path)
		return
	var parsed = JSON.parse_string(txt)
	if typeof(parsed) != TYPE_DICTIONARY:
		_bail("plan at %s is not a JSON object" % plan_path)
		return
	plan = parsed
	timeout_frames = int(plan.get("timeout_frames", 3600))
	DirAccess.make_dir_recursive_absolute(out_dir)
	DirAccess.make_dir_recursive_absolute(out_dir + "/shots")


func _run() -> void:
	if plan.is_empty():
		return
	var scene_path := str(plan.get("scene", ""))
	if scene_path == "" or not ResourceLoader.exists(scene_path):
		_bail("scene not found: '%s'" % scene_path)
		return
	var packed := load(scene_path) as PackedScene
	if packed == null:
		_bail("scene failed to load as PackedScene: %s" % scene_path)
		return
	scene_root = packed.instantiate()
	add_child(scene_root)
	_collect_via_nodes()

	# Warm-up: the first frames of any process are garbage for both perf and looks
	# (shaders still compiling, physics not settled). Never measure them.
	var warmup := int(plan.get("warmup_frames", 30))
	for _i in range(max(warmup, 1)):
		await get_tree().process_frame

	_sample_probes(true)

	for step in plan.get("steps", []):
		if finished:
			break
		await _do_step(step)

	# Dedicated perf window, after the scripted interaction has settled. Frame
	# cap off: we are measuring what the frame costs, not what we asked for.
	var pf := int((plan.get("perf", {}) as Dictionary).get("sample_frames", 120))
	if pf > 0:
		Engine.max_fps = 0
		perf_samples.clear()
		draw_calls_max = 0
		prims_max = 0
		sampling = true
		for _i in range(pf):
			await get_tree().process_frame
		sampling = false

	_sample_probes(false)
	_evaluate_checks()
	_finish()


func _do_step(step_v: Variant) -> void:
	var step: Dictionary = step_v if typeof(step_v) == TYPE_DICTIONARY else {}
	var held: Array = []
	for a in step.get("actions", []):
		var act := str(a)
		if not InputMap.has_action(act):
			# A missing action is a real finding, not a harness problem: the plan
			# and the project's input map have drifted apart. Name what IS
			# available, so the fix is one step instead of a lookup round-trip.
			var known := InputMap.get_actions()
			var listed: Array[String] = []
			for k in known:
				var ks := str(k)
				if not ks.begins_with("ui_"):
					listed.append(ks)
			listed.sort()
			checks.append({"name": "input_action:" + act, "ok": false,
					"detail": "action not in InputMap. Available: %s" % ", ".join(listed)})
			continue
		Input.action_press(act, float(step.get("strength", 1.0)))
		held.append(act)

	# Write a property directly. Without this, exercising a public bool meant
	# binding a whole InputMap action to flip it and edge-detecting that action
	# in the lab script - one project burned `interact` to toggle one boolean.
	if step.has("set"):
		var spec: Dictionary = step["set"]
		var target := scene_root.get_node_or_null(NodePath(str(spec.get("path", "."))))
		if target == null:
			checks.append({"name": "set:" + str(spec.get("path", "")), "ok": false,
					"detail": "cannot set a property on a node that does not exist"})
		else:
			var prop := str(spec.get("property", ""))
			target.set_indexed(NodePath(prop), spec.get("value"))
			var got = target.get_indexed(NodePath(prop))
			if str(got) != str(spec.get("value")):
				# A silent no-op set is worse than an error: the rest of the plan
				# then measures a state that was never established.
				checks.append({"name": "set:" + prop, "ok": false,
						"detail": "set %s = %s but it read back %s" % [
								prop, spec.get("value"), got]})

	if step.has("shot"):
		await _shoot(str(step["shot"]))

	# `seconds` is the readable form; `frames` is the precise one. Both land on
	# the same clock because steps run pinned at STEP_FPS.
	var n := int(step.get("frames", step.get("wait", 1)))
	if step.has("seconds"):
		n = int(round(float(step["seconds"]) * STEP_FPS))
	for _i in range(max(n, 1)):
		await get_tree().process_frame
		_sample_probes(false)

	for act in held:
		Input.action_release(act)

	# Snapshot every probe at this moment, keyed by the step's label.
	if step.has("label"):
		var snap := {}
		for key in plan.get("probes", {}):
			if probe_last.has(key):
				snap[key] = probe_last[key]
		probe_at[str(step["label"])] = snap

	if step.has("shot_after"):
		await _shoot(str(step["shot_after"]))


func _shoot(label: String) -> void:
	if DisplayServer.get_name() == "headless":
		checks.append({"name": "shot:" + label, "ok": false,
				"detail": "cannot screenshot under --headless (dummy renderer); drop --headless for the LOOK pass"})
		return
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	shot_index += 1
	var fname := "%s/shots/%02d_%s.png" % [out_dir, shot_index, label]
	var err := img.save_png(fname)
	if err != OK:
		errors.append("screenshot failed (%s): %s" % [err, fname])


func _collect_via_nodes() -> void:
	"""Every node path named by a `via` on any check, gathered once up front so
	probe sampling does not re-scan the plan each frame."""
	_via_nodes.clear()
	for c in plan.get("checks", []):
		if typeof(c) != TYPE_DICTIONARY:
			continue
		for v in (c as Dictionary).get("via", []):
			var sv := str(v)
			if not _via_nodes.has(sv):
				_via_nodes.append(sv)
		_via_radius = maxf(_via_radius, float((c as Dictionary).get("via_radius", 0.0)))
	if _via_radius <= 0.0:
		_via_radius = 3.0


func _probe_is_inside(probe: Node, target: Node) -> bool:
	"""Has the probe reached `target`?

	Two strategies, because a `via` node may be a volume or just a marker. If
	the target has visual extents, use real AABB containment (expanded slightly
	so walking along a floor segment counts). Otherwise fall back to proximity,
	which is what a bare Marker3D can support."""
	if not (probe is Node3D) or not (target is Node3D):
		return false
	var p: Vector3 = (probe as Node3D).global_position
	var vis := _first_visual(target)
	if vis != null:
		var aabb: AABB = (vis as VisualInstance3D).get_aabb()
		aabb = (vis as Node3D).global_transform * aabb
		return aabb.grow(_via_radius * 0.5).has_point(p)
	return p.distance_to((target as Node3D).global_position) <= _via_radius


func _first_visual(root: Node) -> Node:
	if root is VisualInstance3D:
		return root
	for c in root.get_children():
		var found := _first_visual(c)
		if found != null:
			return found
	return null


func _sample_probes(first: bool) -> void:
	var probes: Dictionary = plan.get("probes", {})
	for key in probes:
		var spec: Dictionary = probes[key]
		var node := scene_root.get_node_or_null(NodePath(str(spec.get("path", "."))))
		if node == null:
			continue
		var val = node.get_indexed(NodePath(str(spec.get("property", "position"))))
		if not probe_visited.has(key):
			probe_visited[key] = {}
		# Record which of the plan's `via` nodes this probe has been inside.
		for want_node in _via_nodes:
			var n := scene_root.get_node_or_null(NodePath(want_node))
			if n == null:
				continue
			if _probe_is_inside(node, n):
				probe_visited[key][want_node] = true
		if typeof(val) in [TYPE_INT, TYPE_FLOAT]:
			var f := float(val)
			probe_numeric[key] = true
			probe_min[key] = f if not probe_min.has(key) else minf(float(probe_min[key]), f)
			probe_max[key] = f if not probe_max.has(key) else maxf(float(probe_max[key]), f)
		if first and not probe_first.has(key):
			probe_first[key] = val
			probe_path_len[key] = 0.0
		elif probe_last.has(key) and typeof(val) == TYPE_VECTOR3 and typeof(probe_last[key]) == TYPE_VECTOR3:
			probe_path_len[key] = float(probe_path_len.get(key, 0.0)) + (val as Vector3).distance_to(probe_last[key])
		probe_last[key] = val


func _process(delta: float) -> void:
	frames += 1
	if sampling and delta > 0.0:
		perf_samples.append(delta)
		draw_calls_max = maxi(draw_calls_max, int(RenderingServer.get_rendering_info(
				RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)))
		prims_max = maxi(prims_max, int(RenderingServer.get_rendering_info(
				RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)))
	if frames > timeout_frames and not finished:
		checks.append({"name": "timeout", "ok": false,
				"detail": "exceeded timeout_frames=%d - the run never reached its last step" % timeout_frames})
		_evaluate_checks()
		_finish()


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #
func _evaluate_checks() -> void:
	# Pre-seed a row per declared check, so a check that somehow aborts
	# evaluation leaves an unmistakable hole rather than vanishing. Guard 1
	# should make this unreachable; it is here because the failure it prevents
	# is a silent green light on work that was never checked.
	var declared: Array = plan.get("checks", [])
	for i in declared.size():
		var dc: Dictionary = declared[i] if typeof(declared[i]) == TYPE_DICTIONARY else {}
		checks.append({"name": str(dc.get("name", dc.get("kind", "check_%d" % i))),
				"ok": false, "kind": str(dc.get("kind", "expr")),
				"detail": "NOT EVALUATED - evaluation stopped before reaching this check"})
	var _slot := checks.size() - declared.size()

	for c_v in declared:
		var c: Dictionary = c_v
		var check_name := str(c.get("name", c.get("kind", "check")))
		var kind := str(c.get("kind", "expr"))
		var ok := false
		var detail := ""
		match kind:
			"moved":
				var key := str(c.get("probe", ""))
				var want := float(c.get("min", 1.0))
				if probe_numeric.get(key, false):
					checks.append({"name": check_name, "ok": false, "kind": kind,
							"detail": ("probe '%s' is numeric, not a position - `moved` "
									+ "measures path length. Use probe_min/probe_max/"
									+ "probe_at.") % key})
					continue
				var travelled := float(probe_path_len.get(key, 0.0))
				var straight := 0.0
				if typeof(probe_first.get(key)) == TYPE_VECTOR3 and typeof(probe_last.get(key)) == TYPE_VECTOR3:
					straight = (probe_last[key] as Vector3).distance_to(probe_first[key])
				var ratio := straight / maxf(travelled, 0.0001)
				ok = travelled >= want
				detail = "path=%.3f straight=%.3f directness=%.2f need>=%.3f" % [
						travelled, straight, ratio, want]
				# Distance alone is satisfied by any open floor - a player can
				# "walk the spine" 41m on a bare greybox with no spine in it.
				# `via` makes the check assert WHAT was traversed.
				var via: Array = c.get("via", [])
				if not via.is_empty():
					var missed: Array[String] = []
					for want_node in via:
						if not probe_visited.get(key, {}).has(str(want_node)):
							missed.append(str(want_node))
					if not missed.is_empty():
						ok = false
						detail += "; never entered: %s" % ", ".join(missed)
					else:
						detail += "; via %d node(s) ok" % via.size()
				elif ok and ratio < 0.35:
					detail += " (WARNING: wandering, not traversing - consider `via`)"
			"still":
				var key2 := str(c.get("probe", ""))
				var tol := float(c.get("max", 0.05))
				if probe_numeric.get(key2, false):
					# path_length is only accumulated for Vector3 probes, so on a
					# scalar this read 0.0 and passed for ANY tolerance - a check
					# that could not fail. Refuse it rather than be green.
					ok = false
					detail = ("probe '%s' is numeric, not a position - `still` measures "
							+ "path length and would pass vacuously. Use probe_min/"
							+ "probe_max/probe_at, or probe a Vector3.") % key2
				else:
					var moved := float(probe_path_len.get(key2, 0.0))
					ok = moved <= tol
					detail = "path=%.3f need<=%.3f" % [moved, tol]
			"probe_min", "probe_max":
				# The lowest/highest value a numeric probe reached during the run.
				# "did faith ever hit zero" is a different question from "is faith
				# zero now", and only this can answer it.
				var pk := str(c.get("probe", ""))
				if not probe_numeric.get(pk, false):
					detail = "probe '%s' never produced a number" % pk
				else:
					var actual: float = float(
							probe_min.get(pk, 0.0) if kind == "probe_min"
							else probe_max.get(pk, 0.0))
					var lo := float(c.get("min", -INF))
					var hi := float(c.get("max", INF))
					if c.has("gt"):
						lo = float(c["gt"])
						ok = actual > lo
					elif c.has("lt"):
						hi = float(c["lt"])
						ok = actual < hi
					else:
						ok = actual >= lo and actual <= hi
					detail = "%s(%s) = %.4f over the run" % [kind, pk, actual]
			"probe_at":
				# The value of a probe AT the end of a labelled step. This is how a
				# gate asserts "X was true at the moment Y happened" - an end-of-run
				# value cannot distinguish two causes that both reset the same field.
				var pk2 := str(c.get("probe", ""))
				var lbl := str(c.get("label", ""))
				if not probe_at.has(lbl):
					detail = ("no step labelled '%s' ran - label the step you mean, "
							+ "and note a step is only snapshotted after it finishes") % lbl
				elif not (probe_at[lbl] as Dictionary).has(pk2):
					detail = "probe '%s' had no value at '%s'" % [pk2, lbl]
				else:
					var v2 = (probe_at[lbl] as Dictionary)[pk2]
					var fv := float(v2) if typeof(v2) in [TYPE_INT, TYPE_FLOAT] else NAN
					if c.has("gt"):
						ok = fv > float(c["gt"])
					elif c.has("lt"):
						ok = fv < float(c["lt"])
					elif c.has("equals"):
						ok = str(v2) == str(c["equals"])
					else:
						ok = fv >= float(c.get("min", -INF)) and fv <= float(c.get("max", INF))
					detail = "%s at '%s' = %s" % [pk2, lbl, v2]
			"node_exists":
				var p := str(c.get("path", ""))
				ok = scene_root.get_node_or_null(NodePath(p)) != null
				detail = p
			"prop_between", "prop_gt", "prop_lt", "prop_eq":
				var node := scene_root.get_node_or_null(NodePath(str(c.get("path", "."))))
				if node == null:
					detail = "node not found: %s" % c.get("path", "")
				else:
					var v = node.get_indexed(NodePath(str(c.get("property", ""))))
					var f := float(v) if typeof(v) in [TYPE_INT, TYPE_FLOAT, TYPE_BOOL] else NAN
					match kind:
						"prop_between":
							ok = f >= float(c.get("min", -INF)) and f <= float(c.get("max", INF))
							detail = "%s = %s, want [%s..%s]" % [c.get("property"), v, c.get("min"), c.get("max")]
						"prop_gt":
							ok = f > float(c.get("value", 0.0))
							detail = "%s = %s, want > %s" % [c.get("property"), v, c.get("value")]
						"prop_lt":
							ok = f < float(c.get("value", 0.0))
							detail = "%s = %s, want < %s" % [c.get("property"), v, c.get("value")]
						"prop_eq":
							# Compare numerically when both sides are numbers.
							# String comparison alone made a correct integer
							# assertion fail as "motion_mode = 1, want 1.0",
							# because a JSON 1 arrives in Godot as a float.
							var want_v = c.get("value")
							var both_num := (typeof(v) in [TYPE_INT, TYPE_FLOAT]) \
									and (typeof(want_v) in [TYPE_INT, TYPE_FLOAT])
							if both_num:
								ok = is_equal_approx(float(v), float(want_v))
								detail = "%s = %s, want %s (numeric)" % [
										c.get("property"), v, want_v]
							else:
								ok = str(v) == str(want_v)
								detail = "%s = %s, want %s" % [c.get("property"), v, want_v]
			"expr":
				var e := Expression.new()
				var src := str(c.get("expr", ""))
				var base_desc := "%s (%s)" % [scene_root.get_path(), scene_root.get_class()]
				if e.parse(src, []) != OK:
					detail = "parse error in `%s`: %s" % [src, e.get_error_text()]
				else:
					var res = e.execute([], scene_root, false)
					if e.has_execute_failed():
						# Godot's message alone ("Invalid named index 'x' for base
						# type Object") never says which node was Object-typed, so
						# carry the expression and the resolved base with it.
						detail = "execute failed on `%s` | base=%s | %s" % [
								src, base_desc, e.get_error_text()]
					else:
						# NEVER `bool(res)` on an arbitrary Variant. `bool` has four
						# constructors - no-arg, bool, float, int - so a String,
						# Array, Dictionary or Vector result raised
						# "Nonexistent 'bool' constructor", which aborted
						# _evaluate_checks() and silently DELETED every check after
						# this one while the verdict still read passed: true. A
						# 35-check plan came back with one check and a green light.
						match typeof(res):
							TYPE_BOOL:
								ok = res
								detail = "%s -> %s" % [src, res]
							TYPE_INT, TYPE_FLOAT:
								ok = float(res) != 0.0
								detail = "%s -> %s" % [src, res]
							TYPE_NIL:
								ok = false
								detail = "%s -> <null>" % src
							_:
								# Ambiguous on purpose: truthiness of a String is
								# not what the author meant to assert.
								ok = false
								detail = ("`%s` returned %s, which is not a truth "
										+ "value. Compare it explicitly (`%s == ...`) "
										+ "or use prop_eq / probe_at.") % [
										src, type_string(typeof(res)), src]
			_:
				detail = "unknown check kind '%s'" % kind
		# Overwrite this check's pre-seeded row in place.
		checks[_slot] = {"name": check_name, "ok": ok, "detail": detail, "kind": kind}
		_slot += 1


func _perf() -> Dictionary:
	if perf_samples.is_empty():
		return {}
	var sorted: Array[float] = perf_samples.duplicate()
	sorted.sort()
	var total := 0.0
	for d in perf_samples:
		total += d
	var avg: float = total / float(perf_samples.size())
	var p99: float = sorted[mini(int(sorted.size() * 0.99), sorted.size() - 1)]
	var worst: float = sorted[sorted.size() - 1]
	var shadow_lights := 0
	var lights := 0
	for n in _all_nodes(scene_root):
		if n is Light3D:
			lights += 1
			if (n as Light3D).shadow_enabled:
				shadow_lights += 1
	return {
		"frames": perf_samples.size(),
		"fps_avg": snappedf(1.0 / maxf(avg, 0.000001), 0.1),
		"fps_1pct_low": snappedf(1.0 / maxf(p99, 0.000001), 0.1),
		"frame_ms_avg": snappedf(avg * 1000.0, 0.01),
		"frame_ms_worst": snappedf(worst * 1000.0, 0.01),
		"draw_calls_max": draw_calls_max,
		"primitives_max": prims_max,
		"lights": lights,
		"shadow_lights": shadow_lights,
	}


func _all_nodes(root: Node) -> Array:
	if root == null:
		return []
	var out: Array = [root]
	for c in root.get_children():
		out.append_array(_all_nodes(c))
	return out


func _finish() -> void:
	if finished:
		return
	finished = true
	# A run where nothing was actually asserted is NOT a pass. `passed` used to
	# start true and only flip on a failing check, so a plan with no checks - or
	# one whose checks all failed to evaluate - returned PASS with screenshots
	# attached. That is the worst failure this harness can produce: a gate that
	# certifies nothing while looking exactly like one that certified everything.
	#
	# Only rows carrying a `kind` came from the plan; `input_action:` / `shot:` /
	# `timeout` / `harness` rows are generated here and do not count as assertions.
	var evaluated := 0
	for c in checks:
		if c.has("kind"):
			evaluated += 1
	if evaluated == 0 and not plan.get("checks", []).is_empty():
		checks.append({"name": "no_checks_evaluated", "ok": false,
				"detail": "the plan declares %d check(s) but none were evaluated - "
						% plan.get("checks", []).size()
						+ "the run asserted nothing"})
	elif evaluated == 0:
		checks.append({"name": "no_checks_declared", "ok": false,
				"detail": "this plan declares no checks, so it can only prove the "
						+ "harness boots. Use `gd playtest --smoke` if that is what "
						+ "you meant; otherwise the run asserted nothing."})
	var passed := true
	for c in checks:
		if not c.get("ok", false):
			passed = false
	var verdict := {
		"name": plan.get("name", "unnamed"),
		"scene": plan.get("scene", ""),
		"passed": passed and errors.is_empty(),
		"checks": checks,
		"perf": _perf(),
		"probes": {"first": _stringify(probe_first), "last": _stringify(probe_last),
				"path_length": probe_path_len,
				"min": probe_min, "max": probe_max,
				"at": _stringify_nested(probe_at)},
		"frames_run": frames,
		"errors": errors,
		"renderer": DisplayServer.get_name(),
	}
	var f := FileAccess.open(out_dir + "/verdict.json", FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(verdict, "  "))
		f.close()
	print("GDVERDICT " + JSON.stringify(verdict))
	get_tree().quit(0 if verdict["passed"] else 1)


func _stringify_nested(d: Dictionary) -> Dictionary:
	var out := {}
	for k in d:
		out[k] = _stringify(d[k])
	return out


func _stringify(d: Dictionary) -> Dictionary:
	var out := {}
	for k in d:
		out[k] = str(d[k])
	return out


func _bail(reason: String) -> void:
	finished = true
	var verdict := {"name": plan.get("name", "unnamed"), "passed": false,
			"checks": [{"name": "harness", "ok": false, "detail": reason}],
			"errors": [reason], "perf": {}}
	DirAccess.make_dir_recursive_absolute(out_dir)
	var f := FileAccess.open(out_dir + "/verdict.json", FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(verdict, "  "))
		f.close()
	print("GDVERDICT " + JSON.stringify(verdict))
	get_tree().quit(1)
