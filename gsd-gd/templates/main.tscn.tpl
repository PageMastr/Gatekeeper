; Greybox starting scene, scaffolded by `gd init`.
;
; This is deliberately ugly and deliberately playable: a floor, a wall to walk
; into, a lighting rig on `deep_night`, and the debug panel on F9. The Core Loop
; gets proven here, in grey, before a single asset is generated.
[gd_scene load_steps=8 format=3]

[ext_resource type="Script" path="res://addons/gd_harness/gd_lighting_rig.gd" id="1_rig"]
[ext_resource type="Script" path="res://addons/gd_harness/gd_lighting_panel.gd" id="2_panel"]
[ext_resource type="Script" path="res://scripts/greybox_player.gd" id="3_player"]

[sub_resource type="BoxMesh" id="BoxMesh_floor"]
size = Vector3(40, 0.5, 40)

[sub_resource type="BoxShape3D" id="BoxShape3D_floor"]
size = Vector3(40, 0.5, 40)

[sub_resource type="BoxMesh" id="BoxMesh_wall"]
size = Vector3(8, 3, 0.4)

[sub_resource type="BoxShape3D" id="BoxShape3D_wall"]
size = Vector3(8, 3, 0.4)

[node name="Main" type="Node3D"]

[node name="LightingRig" type="Node3D" parent="."]
script = ExtResource("1_rig")
preset = "deep_night"

[node name="Floor" type="StaticBody3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, -0.25, 0)

[node name="Mesh" type="MeshInstance3D" parent="Floor"]
mesh = SubResource("BoxMesh_floor")

[node name="Col" type="CollisionShape3D" parent="Floor"]
shape = SubResource("BoxShape3D_floor")

[node name="Wall" type="StaticBody3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1.5, -12)

[node name="Mesh" type="MeshInstance3D" parent="Wall"]
mesh = SubResource("BoxMesh_wall")

[node name="Col" type="CollisionShape3D" parent="Wall"]
shape = SubResource("BoxShape3D_wall")

[node name="Player" type="CharacterBody3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0)
script = ExtResource("3_player")

[node name="Panel" type="CanvasLayer" parent="."]
script = ExtResource("2_panel")
rig_path = NodePath("../LightingRig")
