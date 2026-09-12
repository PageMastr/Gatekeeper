extends CharacterBody3D
## Greybox player. Deliberately minimal and deliberately replaceable.
##
## It builds its own capsule, collider and camera in _ready() so the starting
## scene stays readable as text. When the real character arrives, this script
## dies - but the input action names it uses (`move_forward` etc.) must survive,
## because every playtest plan presses those names.

@export var walk_speed: float = 4.0
@export var sprint_speed: float = 7.0
@export var jump_velocity: float = 4.5
@export var third_person: bool = true

## Surface resistance, 0..1, written by whatever the player is standing in
## (deep snow, mud, water). Locomotion reads it; the terrain system writes it.
## Keeping it a single scalar on the player is what lets "deep snow slows you
## down" be one line of gameplay code instead of a system.
var drag: float = 0.0

var _cam: Camera3D


func _ready() -> void:
	if get_node_or_null("Col") == null:
		var col := CollisionShape3D.new()
		col.name = "Col"
		var cap := CapsuleShape3D.new()
		cap.height = 1.8
		cap.radius = 0.35
		col.shape = cap
		add_child(col)
	if get_node_or_null("Mesh") == null:
		var mi := MeshInstance3D.new()
		mi.name = "Mesh"
		var cm := CapsuleMesh.new()
		cm.height = 1.8
		cm.radius = 0.35
		mi.mesh = cm
		add_child(mi)
	if get_node_or_null("Cam") == null:
		_cam = Camera3D.new()
		_cam.name = "Cam"
		if third_person:
			_cam.position = Vector3(0, 1.6, 4.5)
			_cam.rotation_degrees = Vector3(-12, 0, 0)
		else:
			_cam.position = Vector3(0, 0.7, 0)
		add_child(_cam)
		_cam.make_current()


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity += get_gravity() * delta
	elif Input.is_action_just_pressed("jump"):
		velocity.y = jump_velocity

	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var dir := (transform.basis * Vector3(input.x, 0, input.y)).normalized()
	var speed := sprint_speed if Input.is_action_pressed("sprint") else walk_speed
	# Deep snow: you walk. Thin snow: you can run. One scalar, both behaviours.
	speed *= (1.0 - clampf(drag, 0.0, 0.9))
	if Input.is_action_pressed("sprint") and drag > 0.5:
		speed = walk_speed * (1.0 - clampf(drag, 0.0, 0.9))

	if dir:
		velocity.x = dir.x * speed
		velocity.z = dir.z * speed
	else:
		velocity.x = move_toward(velocity.x, 0.0, speed)
		velocity.z = move_toward(velocity.z, 0.0, speed)
	move_and_slide()
