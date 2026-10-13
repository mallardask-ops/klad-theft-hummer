# Korostyshiv source data

- `korostyshiv-overpass.json`: OpenStreetMap extract for bbox 50.290,29.010,50.340,29.110, fetched 2026-10-12 via the Overpass API (overpass.kumi.systems).
  © OpenStreetMap contributors, ODbL 1.0, https://www.openstreetmap.org/copyright
- `dem/14_*.png`: Terrain Tiles (terrarium encoding, zoom 14) from the AWS Open Data registry,
  https://registry.opendata.aws/terrain-tiles/ . Elevation for this area comes from SRTM (NASA, public domain).
  height = R*256 + G + B/256 - 32768 m.

`tools/city/plan_korostyshiv.py` turns these into the game plan; `tools/city/build_city_meshes.py` builds the meshes.
