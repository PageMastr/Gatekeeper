{
  "name": "minute_one",
  "_comment": "The first gate of every project. Replace the steps with the real Minute One from .planning/CORE_LOOP.md. Run with: gd playtest lab/minute_one.json",
  "scene": "res://scenes/main.tscn",
  "warmup_frames": 30,
  "timeout_frames": 2400,
  "probes": {
    "player": { "path": "Player", "property": "global_position" }
  },
  "steps": [
    { "wait": 20 },
    { "shot": "spawn" },
    { "actions": ["move_forward"], "frames": 120, "label": "walk_out" },
    { "shot": "after_walk" },
    { "actions": ["move_forward", "sprint"], "frames": 90, "label": "sprint" },
    { "shot": "sprinting" },
    { "wait": 30 }
  ],
  "checks": [
    { "name": "player_exists", "kind": "node_exists", "path": "Player" },
    { "name": "player_moved", "kind": "moved", "probe": "player", "min": 4.0 },
    { "name": "did_not_fall_through_floor", "kind": "prop_between",
      "path": "Player", "property": "global_position:y", "min": -1.0, "max": 6.0 },
    { "name": "lighting_rig_present", "kind": "node_exists", "path": "LightingRig" }
  ],
  "perf": { "sample_frames": 120 }
}
