"""Render Podro posters for the GTA III style front end (transparent PNGs).

Run: blender --background -noaudio assets/source/podro.blend --python tools/ui/render_podro_pose.py
Writes assets/source/ui/podro_pose_<name>.png
"""
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(bpy.data.filepath).resolve().parents[2]
OUT = ROOT / "assets/source/ui"
OUT.mkdir(parents=True, exist_ok=True)
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.film_transparent = True
sc.render.resolution_x, sc.render.resolution_y = 900, 1400
sc.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (.55, .5, .48, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = .9
sc.world = world
for name, energy, rot, color in (("key", 4.5, (math.radians(50), 0, math.radians(-35)), (1, .9, .78)),
                                 ("rim", 3.0, (math.radians(65), 0, math.radians(150)), (.6, .75, 1))):
    light = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN"))
    light.data.energy = energy
    light.data.color = color
    light.rotation_euler = rot
    sc.collection.objects.link(light)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.lens = 50
# the rig faces Blender +Y after the export rotation; the camera looks from slightly below
for track in rig.animation_data.nla_tracks:
    track.mute = True
poses = {"hero": ("attack", 9, Vector((-1.4, 3.5, .5)), Vector((0, 0, 1.05))),
         "idle": ("idle", 20, Vector((-1.0, 3.8, .8)), Vector((0, 0, 1.0)))}
for name, (action, frame, cpos, target) in poses.items():
    rig.animation_data.action = bpy.data.actions[action]
    if hasattr(rig.animation_data, "action_slot") and rig.animation_data.action.slots:
        rig.animation_data.action_slot = rig.animation_data.action.slots[0]
    sc.frame_set(frame)
    cam.location = cpos
    cam.rotation_euler = (target - cpos).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = str(OUT / f"podro_pose_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("POSE", name)
