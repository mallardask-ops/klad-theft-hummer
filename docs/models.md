# Blender assets

## Podro

Built by `tools/build_podro.py`, separate from the other characters. A CC0 Quaternius base
body (`assets/source/third_party/`) is welded and has its muscles smoothed away. The limbs are
slimmed, and a jacket and cargo layer is inflated over them. The feet become boots, and a high
collar and a hammer are added. The result is decimated to about 2.3k triangles, the GTA III /
early-PS2 range. UVs are projected onto the author's texture sheet
`assets/source/reference/podro_texture_sheet.png`, which holds the face, softshell, cargos,
boots and hands; the game uses a 512 px atlas. The rig is the 65-bone UE-style humanoid.
Clips come from the CC0 Universal Animation Library: `idle`, `walk` (jog), `run` (sprint),
`stroll`, `attack` (sword swing with the hammer), `punch`, `hit`, `death`, `drive`,
`jump_start`, `jump_air`, `jump_land`, `talk`, `pickup` and `interact`. The right hand is held
in a fist in every clip. The root is turned to face −Z.

```sh
blender --background -noaudio --factory-startup --python tools/build_podro.py -- --preview
```

`tools/build_models.py` and `tools/build_characters.py` no longer touch Podro.

## Other models

Original geometry built for this project in Blender 5.2.2. No extracted GTA models,
textures, rigs or animations are used.

| Runtime scene | Editable source | Purpose / scale |
| --- | --- | --- |
| `res://assets/models/podro.glb` | `assets/source/podro.blend` (built by `tools/build_podro.py`) | Player; approximately 1.73 m; feet at origin; see “Podro” below |
| `res://assets/models/npc_worker.glb` | `assets/source/npc_worker.blend` | Worker in tobacco coat and cap; approximately 1.75 m |
| `res://assets/models/edik.glb` | `assets/source/edik.blend` | Skinny mission giver; blue short sleeve tee, short hair, exposed forearms; approximately 1.79 m |
| `res://assets/models/serhiy.glb` | `assets/source/serhiy.blend` | Broad mission giver; brown jacket, dark trousers, moustache; approximately 1.77 m |
| `res://assets/models/cyber.glb` | `assets/source/cyber.blend` | Computer nerd; dark hoodie, raised hood, glasses, badge; approximately 1.83 m |
| `res://assets/models/podrina.glb` | `assets/source/podrina.blend` | Woman; olive jacket, jeans, long chestnut hair and ponytail; approximately 1.68 m |
| `res://assets/models/hammer.glb` | `assets/source/hammer.blend` | Standalone worn wood / steel hammer |
| `res://assets/models/sedan.glb` | `assets/source/sedan.blend` | Boxy sedan, approximately 1.9 × 4.4 × 1.45 m including bumper / mirrors |
| `res://assets/models/police_sedan.glb` | `assets/source/police_sedan.blend` | White / navy police sedan with separate red and blue siren meshes |
| `res://assets/models/minibus.glb` | `assets/source/minibus.blend` | Worn local minibus, approximately 2.3 × 4.9 × 2.23 m including mirrors |
| `res://assets/models/stone_monument.glb` | `assets/source/stone_monument.blend` | Cut granite shard with hammer relief; approximately 3.6 m high |

GLB scenes use Godot Y up and face local **−Z**. Blender sources use Z up and face
+Y; the exporter handles the axis conversion. Cars' wheels touch Y=0. The sedan
body is 1.85 m wide and 4.2 m long; mirrors and bumpers extend outside that hull.

All six humans export four verified clips: `idle`, `walk`, `run`, `attack`. Clips are
one second at 24 fps. Set idle, walk and run to loop in the imported AnimationPlayer;
attack should play once. Run can use a higher playback speed. Motion uses actual
keyframes on an editable object hierarchy, with tapered octagonal sleeves / legs,
faceted heads, articulated forearms and an attached hammer on Podro's right hand.

Named character pivots: `Body`, `Arm_L`, `Arm_R`, `Forearm_L`, `Forearm_R`, `Leg_L`,
`Leg_R`, and `Hammer_Grip` on Podro. These can also be found recursively for runtime
procedural adjustment. The hierarchy is not a skinned humanoid skeleton; it is a
lightweight rigid low-poly rig. Collision, navigation and damage belong to Godot
gameplay nodes, not these visual scenes.

Every vehicle has `Wheel_FL`, `Wheel_FR`, `Wheel_RL`, `Wheel_RR` pivots at wheel
centres. Roll around local X. Their meshes are children of the pivots. Other named
groups are `Headlights`, `Tail_Lights`, `Indicators`, `Glass`, `Grille`, `License`,
and `Exhaust`; police also has `Siren_Blue` and `Siren_Red`. Each group contains
one mesh, retaining an interface for runtime material changes. The remaining body
is joined into `Vehicle_Body`. Headlights and sirens use modest emissive materials;
gameplay lights can be attached in Godot.

Surface detail is original generated 64 × 64 texture work: dirt, abrasion and
scratches, with nearest filtering and restrained metal response. Images are packed
into `.blend` and embedded in `.glb`. Face, knuckles, collar, zip, seams, pockets,
laces, window pillars, wipers, grille slats, wheel hubs, tail lamps, indicators,
mirrors, exhaust and plates have real geometry. Vehicle paint materials are named
`Sedan_Paint`, `Police_Paint`, and `Minibus_Paint_Faded` for runtime recolouring.

Rebuild from the workspace root:

```sh
/usr/bin/blender --background -noaudio --factory-startup --python tools/build_models.py
```

Generate an isolated visual preview:

```sh
/usr/bin/blender --background -noaudio --factory-startup --python tools/build_models.py -- --preview podro
```

Rebuild only the four mission characters, preserving base runtime scenes:

```sh
/usr/bin/blender --background -noaudio --factory-startup --python tools/build_models.py -- --variants-only
```

The builder verifies clips directly from each exported GLB JSON chunk and writes
`assets/source/model_manifest.json`. Podro and sedan were rendered in Blender and
visually inspected. Their previews are `assets/source/podro_preview.png` and
`assets/source/sedan_preview.png`. The four mission givers also have individual
`assets/source/*_preview.png` renders. All eleven scenes were imported and instantiated
in an isolated Godot 4.7.2 headless project: all four clips were found and sampled,
and wheel / glass / lamp / grille / plate / exhaust group names passed assertions.
Godot graphical runtime acceptance is verified with the actual game by the main
integration / playtest workflow. `assets/source/.gdignore`
keeps editable Blender files out of Godot's runtime import pipeline.
