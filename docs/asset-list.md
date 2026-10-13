# Asset record

| Asset | Purpose | Source / authoring | Runtime binding | License / status |
| --- | --- | --- | --- | --- |
| Podro, worker, Edik, Serhiy, Cyber, Podrina | Player / world / mission giver silhouettes, 1.7–1.8 m | Blender5.2.2, editable `assets/source/*.blend`, `tools/build_models.py` | `KPlayer`, `KPerson`, four imported animation clips | Original project geometry and animations, integrated |
| Sedan, police, minibus | Driving and pursuit, 4–5 m | Blender original models and packed64px wear textures | `KVehicle`, named wheel pivots and lamp groups | Original, integrated |
| Hammer, granite monument | Combat identity / plaza landmark | Blender original geometry | Hammer held in player rig, monument in KCity | Original, integrated |
| 33 surface/sign textures | Readable Soviet architecture and local storefronts | `tools/build_textures.py`, native authored patterns and Cyrillic signs | KCity materials, nearest pixel sampling | Original, integrated |
| 30 WAV + 1 Ogg audio assets | Recorded Foley, layered petrol/diesel engines, spatial siren/traffic, world ambience, composed radio music | CC0 recordings from BigSoundBank/OpenGameArt; sources and processing in `assets/audio/recorded/manifest.json` | Cached main audio players, five mix buses + Master limiter | CC0; integrated; see `docs/audio-sources.md` |
| Fira Sans Condensed Heavy/SemiBold | Compact Cyrillic HUD | Installed Fira font distribution | KHud | SIL OFL, copied license in assets/fonts |
| DejaVu Serif Condensed Italic | District names | Installed DejaVu distribution | KHud | DejaVu font license, copied in assets/fonts |

Model source directory has `.gdignore`; Godot uses GLB, so Blender installation is needed only for editing/rebuild. Runtime resources use `res://` relative paths. Reference-source snapshots are excluded from the exported game. See `docs/models.md` and `docs/city.md` for actual dimensions, interfaces and validation evidence.
