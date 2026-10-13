extends Node3D
class_name KCity

# Korostyshiv from OpenStreetMap + SRTM, baked by tools/city/*.py (see docs/city.md).
# The heavy geometry comes from assets/city/korostyshiv.glb; gameplay data from data/city/korostyshiv.json.

const PLAN_PATH := "res://data/city/korostyshiv.json"
const HEIGHT_PATH := "res://data/city/heightfield.bin"
const WATER_PATH := "res://data/city/waterlevel.bin"
const DISTRICT_PATH := "res://data/city/districts.png"
const SCENE_PATH := "res://assets/city/korostyshiv.glb"
const TREES_PATH := "res://assets/city/trees.glb"
const TEX_DIR := "res://assets/city/tex/"
const VIEW_RANGE := {"terrain": 0.0, "water": 0.0, "roads": 560.0, "walks": 300.0, "buildings": 620.0, "fences": 260.0, "bridges": 0.0}
const TREE_CELL := 250.0
const TREE_RANGE := 430.0
const WATER_STRIDE := 4

var map_blocks: Array[Rect2] = []
var road_segments: Array[PackedVector3Array] = []
var road_widths: Array[float] = []
var pedestrian_spawns: Array[Vector3] = []
var pedestrian_goals: Array[Vector3] = []
var playable_bounds := Rect2(-880.0, -1280.0, 2560.0, 2360.0)
var terrain_bounds := Rect2()
var river_points: Array[Vector3] = []
var building_count: int = 0
var locations: Dictionary = {}
var traffic_routes: Array = []
var district_names: Array = []
var plaza := Vector3.ZERO
var radar_texture: Texture2D
var radar_rect := Rect2()
var lamp_heads: Array[Vector3] = []

var _plan: Dictionary = {}
var _heights := PackedFloat32Array()
var _water := PackedFloat32Array()
var _water_dist := PackedFloat32Array()
var _wd_size := Vector2i.ZERO
var _nx: int = 0
var _nz: int = 0
var _step: float = 5.0
var _origin := Vector2.ZERO
var _districts: Image
var _district_step: float = 10.0
var _graph := AStar3D.new()
var _seg_grid: Dictionary = {}
var _tex_manifest: Dictionary = {}
var _city_mats: Dictionary = {}
var _rng := RandomNumberGenerator.new()
var _mats: Dictionary = {}
var _batches: Dictionary = {}
var _quads: Dictionary = {}
var _solid: StaticBody3D
var _built: bool = false

func build() -> void:
	if _built:
		return
	_built = true
	_rng.seed = 199810
	_solid = StaticBody3D.new()
	_solid.name = "CityCollision"
	_solid.collision_layer = 1
	add_child(_solid)
	_load_data()
	_materials()
	_terrain_collision()
	_load_scene()
	_trees()
	_street_furniture()
	_story_places()
	_flush_geometry()

# ------------------------------------------------------------------ data

func _load_data() -> void:
	_plan = JSON.parse_string(FileAccess.get_file_as_string(PLAN_PATH))
	var meta: Dictionary = _plan["meta"]
	_step = float(meta["step"])
	_nx = int(meta["nx"])
	_nz = int(meta["nz"])
	var terr: Array = meta["terrain"]
	_origin = Vector2(float(terr[0]), float(terr[1]))
	terrain_bounds = Rect2(_origin, Vector2(float(terr[2]) - float(terr[0]), float(terr[3]) - float(terr[1])))
	var play: Array = meta["play"]
	playable_bounds = Rect2(float(play[0]), float(play[1]), float(play[2]) - float(play[0]), float(play[3]) - float(play[1]))
	_heights = FileAccess.get_file_as_bytes(HEIGHT_PATH).to_float32_array()
	_water = FileAccess.get_file_as_bytes(WATER_PATH).to_float32_array()
	var district_tex := load(DISTRICT_PATH) as Texture2D
	_districts = district_tex.get_image() if district_tex else null
	if _districts and _districts.is_compressed():
		_districts.decompress()
	_district_step = float(meta["district_step"])
	district_names = _plan["districts"]
	var p: Array = _plan["plaza"]
	plaza = Vector3(float(p[0]), float(p[1]), float(p[2]))
	for key in _plan["locations"]:
		var loc: Dictionary = _plan["locations"][key]
		var pos: Array = loc["pos"]
		var car: Array = loc["car"]
		var anchor: Array = loc["anchor"]
		locations[key] = {
			"pos": Vector3(float(pos[0]), ground_height(float(pos[0]), float(pos[2])), float(pos[2])),
			"car": Vector3(float(car[0]), ground_height(float(car[0]), float(car[2])), float(car[2])),
			"car_heading": float(loc["car_heading"]),
			"anchor": Vector3(float(anchor[0]), ground_height(float(anchor[0]), float(anchor[1])), float(anchor[1]))
		}
	for loop in _plan["traffic"]:
		var route: Array[Vector3] = []
		for q in loop:
			route.append(Vector3(float(q[0]), ground_height(float(q[0]), float(q[2])) + .3, float(q[2])))
		traffic_routes.append(route)
	var nodes: Dictionary = _plan["graph"]["nodes"]
	for key in nodes:
		var q: Array = nodes[key]
		_graph.add_point(int(key), Vector3(float(q[0]), 0.0, float(q[2])))
	for e in _plan["graph"]["edges"]:
		var a := int(e[0])
		var b := int(e[1])
		if _graph.has_point(a) and _graph.has_point(b):
			_graph.connect_points(a, b)
	for r in _plan["roads"]:
		var pts: Array = r["pts"]
		for i in range(pts.size() - 1):
			var a := Vector3(float(pts[i][0]), 0.0, float(pts[i][2]))
			var b := Vector3(float(pts[i + 1][0]), 0.0, float(pts[i + 1][2]))
			a.y = ground_height(a.x, a.z)
			b.y = ground_height(b.x, b.z)
			road_segments.append(PackedVector3Array([a, b]))
			road_widths.append(float(r["w"]))
			_index_segment(road_segments.size() - 1, a, b)
	_water_field()
	for pair in _plan["pedestrians"]:
		var a := Vector3(float(pair[0][0]), 0.0, float(pair[0][1]))
		var b := Vector3(float(pair[1][0]), 0.0, float(pair[1][1]))
		a.y = ground_height(a.x, a.z) + .2
		b.y = ground_height(b.x, b.z) + .2
		pedestrian_spawns.append(a)
		pedestrian_goals.append(b)
	_tex_manifest = JSON.parse_string(FileAccess.get_file_as_string(TEX_DIR + "manifest.json"))
	radar_texture = load("res://assets/city/radar.png") as Texture2D
	radar_rect = Rect2(_origin, Vector2(float(terr[2]) - float(terr[0]), float(terr[3]) - float(terr[1])))

func _index_segment(index: int, a: Vector3, b: Vector3) -> void:
	for cx in range(int(floor(minf(a.x, b.x) / 50.0)), int(floor(maxf(a.x, b.x) / 50.0)) + 1):
		for cz in range(int(floor(minf(a.z, b.z) / 50.0)), int(floor(maxf(a.z, b.z) / 50.0)) + 1):
			var key := Vector2i(cx, cz)
			if not _seg_grid.has(key):
				_seg_grid[key] = PackedInt32Array()
			var list: PackedInt32Array = _seg_grid[key]
			list.append(index)
			_seg_grid[key] = list

# ------------------------------------------------------------------ queries

func ground_height(x: float, z: float) -> float:
	if _heights.is_empty():
		return 0.0
	var gx: float = clampf((x - _origin.x) / _step, 0.0, _nx - 1.001)
	var gz: float = clampf((z - _origin.y) / _step, 0.0, _nz - 1.001)
	var x0 := int(gx)
	var z0 := int(gz)
	var fx: float = gx - x0
	var fz: float = gz - z0
	var h00: float = _heights[z0 * _nx + x0]
	var h10: float = _heights[z0 * _nx + x0 + 1]
	var h01: float = _heights[(z0 + 1) * _nx + x0]
	var h11: float = _heights[(z0 + 1) * _nx + x0 + 1]
	if fx >= fz:
		return h00 + (h10 - h00) * fx + (h11 - h10) * fz
	return h00 + (h11 - h01) * fx + (h01 - h00) * fz

func water_level(x: float, z: float) -> float:
	var gx := int(round((x - _origin.x) / _step))
	var gz := int(round((z - _origin.y) / _step))
	if gx < 0 or gz < 0 or gx >= _nx or gz >= _nz:
		return -INF
	var level: float = _water[gz * _nx + gx]
	return level if level > -999.0 else -INF

func is_underwater(pos: Vector3) -> bool:
	return pos.y < water_level(pos.x, pos.z) - .4

func distance_to_water(pos: Vector3) -> float:
	var cx := clampi(int((pos.x - _origin.x) / (_step * WATER_STRIDE)), 0, _wd_size.x - 1)
	var cz := clampi(int((pos.z - _origin.y) / (_step * WATER_STRIDE)), 0, _wd_size.y - 1)
	return _water_dist[cz * _wd_size.x + cx] if not _water_dist.is_empty() else INF

func _water_field() -> void:
	# Coarse distance-to-water field (chamfer transform) and deep-water sample points.
	var cell: float = _step * WATER_STRIDE
	_wd_size = Vector2i(int(ceil(float(_nx) / WATER_STRIDE)), int(ceil(float(_nz) / WATER_STRIDE)))
	_water_dist.resize(_wd_size.x * _wd_size.y)
	_water_dist.fill(1e9)
	for j in _nz:
		for i in _nx:
			var level: float = _water[j * _nx + i]
			if level <= -999.0:
				continue
			_water_dist[(j / WATER_STRIDE) * _wd_size.x + i / WATER_STRIDE] = 0.0
			if i % (WATER_STRIDE * 2) == 0 and j % (WATER_STRIDE * 2) == 0 and level - _heights[j * _nx + i] > 1.2:
				river_points.append(Vector3(_origin.x + i * _step, level, _origin.y + j * _step))
	var diag: float = cell * 1.4142
	for pass_index in 2:
		var ys: Array = range(_wd_size.y) if pass_index == 0 else range(_wd_size.y - 1, -1, -1)
		var xs: Array = range(_wd_size.x) if pass_index == 0 else range(_wd_size.x - 1, -1, -1)
		var d := -1 if pass_index == 0 else 1
		for z in ys:
			for x in xs:
				var k: int = z * _wd_size.x + x
				var best: float = _water_dist[k]
				if x + d >= 0 and x + d < _wd_size.x:
					best = minf(best, _water_dist[k + d] + cell)
				if z + d >= 0 and z + d < _wd_size.y:
					best = minf(best, _water_dist[k + d * _wd_size.x] + cell)
					if x + d >= 0 and x + d < _wd_size.x:
						best = minf(best, _water_dist[k + d * _wd_size.x + d] + diag)
					if x - d >= 0 and x - d < _wd_size.x:
						best = minf(best, _water_dist[k + d * _wd_size.x - d] + diag)
				_water_dist[k] = best

func get_district(pos: Vector3) -> String:
	if _districts == null or district_names.is_empty():
		return "КОРОСТИШІВ"
	var dx := int((pos.x - _origin.x) / _district_step)
	var dz := int((pos.z - _origin.y) / _district_step)
	if dx < 0 or dz < 0 or dx >= _districts.get_width() or dz >= _districts.get_height():
		return "ОКОЛИЦІ"
	var index := int(round(_districts.get_pixel(dx, dz).r * 255.0))
	return String(district_names[index]) if index < district_names.size() else "КОРОСТИШІВ"

func location(key: String) -> Vector3:
	return (locations[key]["pos"] as Vector3) if locations.has(key) else plaza

func nearest_road(point: Vector3) -> Vector3:
	var best := Vector3.ZERO
	var distance: float = INF
	var cx := int(floor(point.x / 50.0))
	var cz := int(floor(point.z / 50.0))
	for ring in range(0, 6):
		for i in range(-ring, ring + 1):
			for j in range(-ring, ring + 1):
				if maxi(absi(i), absi(j)) != ring or not _seg_grid.has(Vector2i(cx + i, cz + j)):
					continue
				for index in _seg_grid[Vector2i(cx + i, cz + j)]:
					var seg: PackedVector3Array = road_segments[index]
					var candidate: Vector3 = _segment_projection(point, seg[0], seg[1])
					var d: float = Vector2(point.x - candidate.x, point.z - candidate.z).length_squared()
					if d < distance:
						distance = d
						best = candidate
		if distance < INF and sqrt(distance) < ring * 50.0:
			break
	best.y = ground_height(best.x, best.z)
	return best

func river_center(z: float) -> float:
	var best: float = INF
	var x: float = 600.0
	for p in river_points:
		if absf(p.z - z) < best:
			best = absf(p.z - z)
			x = p.x
	return x

func river_half_width(_z: float) -> float:
	return 21.0

func road_route(from: Vector3, to: Vector3) -> Array[Vector3]:
	var waypoints: Array[Vector3] = []
	if not from.is_finite() or not to.is_finite():
		return waypoints
	if Vector2(from.x - to.x, from.z - to.z).length_squared() < 0.0025:
		return [to]
	var a: int = _graph.get_closest_point(Vector3(from.x, 0.0, from.z))
	var b: int = _graph.get_closest_point(Vector3(to.x, 0.0, to.z))
	_route_append(waypoints, from)
	if a >= 0 and b >= 0 and a != b:
		for p in _graph.get_point_path(a, b):
			_route_append(waypoints, Vector3(p.x, ground_height(p.x, p.z), p.z))
	_route_append(waypoints, to)
	waypoints[-1] = to
	return waypoints

func _route_append(route: Array[Vector3], point: Vector3) -> void:
	if not route.is_empty() and Vector2(route[-1].x - point.x, route[-1].z - point.z).length_squared() < 4.0:
		return
	route.append(point)

func _segment_projection(point: Vector3, a: Vector3, b: Vector3) -> Vector3:
	var delta: Vector3 = b - a
	var t: float = clampf(Vector2(point.x - a.x, point.z - a.z).dot(Vector2(delta.x, delta.z)) / maxf(Vector2(delta.x, delta.z).length_squared(), 0.0001), 0.0, 1.0)
	return a + delta * t

func _road_heading(point: Vector3) -> float:
	var best: float = INF
	var heading: float = 0.0
	var key := Vector2i(int(floor(point.x / 50.0)), int(floor(point.z / 50.0)))
	for i in range(-1, 2):
		for j in range(-1, 2):
			var k := key + Vector2i(i, j)
			if not _seg_grid.has(k):
				continue
			for index in _seg_grid[k]:
				var seg: PackedVector3Array = road_segments[index]
				var q: Vector3 = _segment_projection(point, seg[0], seg[1])
				var d: float = Vector2(point.x - q.x, point.z - q.z).length_squared()
				if d < best:
					best = d
					heading = atan2(seg[1].x - seg[0].x, seg[1].z - seg[0].z)
	return heading

# ------------------------------------------------------------------ materials

func _pixel_texture(path: String) -> Texture2D:
	var original := load(path) as Texture2D
	if not original:
		return null
	var pixels: Image = original.get_image()
	if pixels.is_compressed():
		pixels.decompress()
	if not pixels.has_mipmaps():
		pixels.generate_mipmaps()
	return ImageTexture.create_from_image(pixels)

func _city_texture(name: String) -> Texture2D:
	return load(TEX_DIR + name + ".png") as Texture2D

func _city_material(name: String) -> Material:
	if _city_mats.has(name):
		return _city_mats[name]
	var material: Material
	if name == "terrain":
		var shader := ShaderMaterial.new()
		shader.shader = load("res://assets/shaders/terrain_splat.gdshader")
		shader.set_shader_parameter("grass", _city_texture("grass"))
		shader.set_shader_parameter("dirt", _city_texture("dirt"))
		shader.set_shader_parameter("rock", _city_texture("rock_granite"))
		shader.set_shader_parameter("forest", _city_texture("forest_floor"))
		shader.set_shader_parameter("grass_dry", _city_texture("grass_dry"))
		material = shader
	elif name == "water":
		var shader := ShaderMaterial.new()
		shader.shader = load("res://assets/shaders/teteriv_water.gdshader")
		shader.set_shader_parameter("ripples", load("res://assets/textures/water.png"))
		material = shader
	elif name == "gold":
		var gold := StandardMaterial3D.new()
		gold.albedo_color = Color("d8b04a")
		gold.metallic = .75
		gold.roughness = .35
		material = gold
	else:
		var mat := StandardMaterial3D.new()
		var info: Dictionary = _tex_manifest.get(name, {})
		mat.albedo_texture = _city_texture(name)
		mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		mat.vertex_color_use_as_albedo = true
		mat.roughness = 1.0
		mat.metallic_specular = .15
		var kind: String = info.get("kind", "")
		if info.get("alpha", false):
			mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
			mat.alpha_scissor_threshold = .45
		if kind in ["fence", "gable", "tree", "sign"] or info.get("alpha", false):
			mat.cull_mode = BaseMaterial3D.CULL_DISABLED
		if kind == "tree":
			mat.diffuse_mode = BaseMaterial3D.DIFFUSE_LAMBERT_WRAP
		material = mat
	_city_mats[name] = material
	return material

func _apply_city_materials(mesh_instance: MeshInstance3D) -> void:
	var mesh: Mesh = mesh_instance.mesh
	for s in mesh.get_surface_count():
		var m: Material = mesh.surface_get_material(s)
		var key: String = m.resource_name.trim_prefix("m_") if m else ""
		if key != "":
			mesh_instance.set_surface_override_material(s, _city_material(key))

# ------------------------------------------------------------------ world geometry

func _terrain_collision() -> void:
	# Uniform scale keeps the heightmap valid for every physics backend.
	var shape := HeightMapShape3D.new()
	shape.map_width = _nx
	shape.map_depth = _nz
	var scaled := PackedFloat32Array()
	scaled.resize(_heights.size())
	for i in _heights.size():
		scaled[i] = _heights[i] / _step
	shape.map_data = scaled
	var collider := CollisionShape3D.new()
	collider.name = "TerrainHeightmap"
	collider.shape = shape
	collider.scale = Vector3.ONE * _step
	collider.position = Vector3(_origin.x + (_nx - 1) * _step * .5, 0.0, _origin.y + (_nz - 1) * _step * .5)
	_solid.add_child(collider)

func _load_scene() -> void:
	var packed := load(SCENE_PATH) as PackedScene
	if packed == null:
		push_error("Korostyshiv scene missing: run tools/city/build_city_meshes.py")
		return
	var scene: Node3D = packed.instantiate()
	scene.name = "Korostyshiv"
	add_child(scene)
	var meshes: Array[Node] = scene.find_children("*", "MeshInstance3D", true, false)
	for node in meshes:
		var mi := node as MeshInstance3D
		var kind: String = String(mi.name).get_slice("__", 0)
		if kind == "col":
			var body := StaticBody3D.new()
			body.name = "Solid_" + String(mi.name)
			body.collision_layer = 1
			var collider := CollisionShape3D.new()
			var shape := ConcavePolygonShape3D.new()
			shape.set_faces(mi.mesh.get_faces())
			shape.backface_collision = true
			collider.shape = shape
			body.add_child(collider)
			add_child(body)
			body.global_transform = mi.global_transform
			mi.queue_free()
			continue
		_apply_city_materials(mi)
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if kind in ["terrain", "water", "roads", "walks"] else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		var range_end: float = VIEW_RANGE.get(kind, 0.0)
		if range_end > 0.0:
			mi.visibility_range_end = range_end
			mi.visibility_range_end_margin = 40.0
			mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		if kind == "buildings":
			building_count += 1
	var count := 0
	for b in _plan.get("trees", []):
		count += 1
	building_count = maxi(building_count, 1)

func _trees() -> void:
	var packed := load(TREES_PATH) as PackedScene
	if packed == null:
		return
	var source: Node = packed.instantiate()
	var meshes: Dictionary = {}
	for node in source.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var mesh: Mesh = mi.mesh.duplicate()
		for s in mesh.get_surface_count():
			var m: Material = mesh.surface_get_material(s)
			if m:
				mesh.surface_set_material(s, _city_material(m.resource_name.trim_prefix("m_")))
		meshes[String(mi.name)] = mesh
	source.free()
	var cells: Dictionary = {}
	var trunk_bodies: Dictionary = {}
	var trunk_shape := CylinderShape3D.new()
	trunk_shape.radius = .3
	trunk_shape.height = 5.0
	for t in _plan.get("trees", []):
		var pos := Vector3(float(t[0]), 0.0, float(t[2]))
		pos.y = ground_height(pos.x, pos.z) - .1
		var kind: String = String(t[3])
		var scale: float = float(t[4])
		var model := "tree_deciduous"
		match kind:
			"pine":
				model = "tree_pine" if _rng.randf() < .8 else "tree_spruce"
			"poplar":
				model = "tree_poplar"
			"fruit":
				model = "tree_fruit"
			_:
				model = "tree_birch" if _rng.randf() < .28 else "tree_deciduous"
		if not meshes.has(model):
			continue
		var key := "%s|%d|%d" % [model, int(floor(pos.x / TREE_CELL)), int(floor(pos.z / TREE_CELL))]
		if not cells.has(key):
			cells[key] = []
		var basis := Basis(Vector3.UP, _rng.randf() * TAU).scaled(Vector3.ONE * scale * _rng.randf_range(.85, 1.15))
		(cells[key] as Array).append(Transform3D(basis, pos))
		if playable_bounds.has_point(Vector2(pos.x, pos.z)) and model != "tree_fruit":
			# one body per cell keeps broadphase pairs local
			var cell := Vector2i(int(floor(pos.x / 100.0)), int(floor(pos.z / 100.0)))
			if not trunk_bodies.has(cell):
				var body := StaticBody3D.new()
				body.name = "TreeTrunks_%d_%d" % [cell.x, cell.y]
				add_child(body)
				trunk_bodies[cell] = body
			var trunks: StaticBody3D = trunk_bodies[cell]
			var owner_id := trunks.create_shape_owner(trunks)
			trunks.shape_owner_add_shape(owner_id, trunk_shape)
			trunks.shape_owner_set_transform(owner_id, Transform3D(Basis(), pos + Vector3(0, 2.5, 0)))
	for key in cells:
		var transforms: Array = cells[key]
		var multimesh := MultiMesh.new()
		multimesh.transform_format = MultiMesh.TRANSFORM_3D
		multimesh.mesh = meshes[String(key).get_slice("|", 0)]
		multimesh.instance_count = transforms.size()
		for i in transforms.size():
			multimesh.set_instance_transform(i, transforms[i])
		var instance := MultiMeshInstance3D.new()
		instance.name = "Trees_" + String(key).replace("|", "_")
		instance.multimesh = multimesh
		instance.visibility_range_end = TREE_RANGE
		instance.visibility_range_end_margin = 40.0
		instance.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(instance)

# ------------------------------------------------------------------ props

func _materials() -> void:
	for texture_name in ["asphalt", "concrete", "roof", "grass", "stone", "rust", "wood", "plaster", "brick", "facade_slab", "facade_redbrick", "facade_blue", "water"]:
		var mat := StandardMaterial3D.new()
		mat.albedo_texture = _pixel_texture("res://assets/textures/%s.png" % texture_name)
		mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST_WITH_MIPMAPS
		mat.roughness = 1.0
		mat.metallic_specular = 0.0
		_mats[texture_name] = mat
	for key in ["cafe", "kodlo", "grocery", "beer", "market", "sawmill", "granite", "garage", "safehouse", "phone", "town", "stop", "pizzeria", "hammer", "repair", "district", "billboard", "wanted", "yard", "quarry"]:
		var mat := StandardMaterial3D.new()
		mat.albedo_texture = _pixel_texture("res://assets/textures/sign_%s.png" % key)
		mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST_WITH_MIPMAPS
		mat.roughness = 1.0
		mat.metallic_specular = 0.0
		mat.cull_mode = BaseMaterial3D.CULL_DISABLED
		_mats["sign_" + key] = mat
	for key in ["sign_station", "sign_sanatorium", "sign_gastronom", "kiosk_yellow", "bus_stop_wall", "quarry_cliff", "planks", "rubble_granite"]:
		_mats[key] = _city_material(key)
	_color("curb", Color("98927a"))
	_color("paint", Color("beb794"))
	_color("dark", Color("333c34"))
	_color("glass", Color("718879"))
	_color("wood_dark", Color("5d503c"))
	_color("bark", Color("5b5541"))
	_color("leaf", Color("5f7146"))
	_color("metal", Color("727869"))
	_color("red", Color("864d39"))
	_color("blue", Color("416165"))
	_color("cream", Color("b9ae85"))
	_color("sand", Color("a59e77"))
	_color("lamp", Color("ecd29a"))
	var photos: Dictionary = {"asphalt":"asphalt_04", "plaster":"grey_plaster_03", "brick":"brick_wall_09", "stone":"quarry_wall", "rust":"corrugated_iron_02", "wood":"wooden_garage_door", "grass":"grass_ground", "concrete":"concrete_floor_damaged_01"}
	for key in photos:
		var path: String = "res://assets/materials/%s.jpg" % photos[key]
		if ResourceLoader.exists(path):
			(_mats[key] as StandardMaterial3D).albedo_texture = _pixel_texture(path)
			(_mats[key] as StandardMaterial3D).texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	(_mats["rust"] as StandardMaterial3D).cull_mode = BaseMaterial3D.CULL_DISABLED
	(_mats["lamp"] as StandardMaterial3D).emission_enabled = true
	(_mats["lamp"] as StandardMaterial3D).emission = Color("ddb976")
	(_mats["lamp"] as StandardMaterial3D).emission_energy_multiplier = 0.35

func _color(key: String, color: Color) -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 1.0
	mat.metallic_specular = 0.0
	_mats[key] = mat

func _street_furniture() -> void:
	for l in _plan.get("lamps", []):
		var pos := Vector3(float(l[0]), 0.0, float(l[2]))
		pos.y = ground_height(pos.x, pos.z)
		_lamp(pos, float(l[3]))
	var previous := Vector3.INF
	for p in _plan.get("poles", []):
		var pole := Vector3(float(p[0]), 0.0, float(p[2]))
		pole.y = ground_height(pole.x, pole.z)
		_cylinder(pole + Vector3(0, 4.4, 0), 0.14, 8.8, "bark")
		_box(pole + Vector3(0, 8.15, 0), Vector3(1.8, 0.12, 0.14), "wood_dark", false, float(p[3]))
		if previous.is_finite() and previous.distance_to(pole) < 48.0:
			_wire(previous + Vector3(0, 8.3, 0), pole + Vector3(0, 8.3, 0))
		previous = pole
	for s in _plan.get("stops", []):
		var pos := Vector3(float(s[0]), 0.0, float(s[2]))
		var road := nearest_road(pos)
		var heading := _road_heading(pos)
		var side := Vector3(sin(heading + PI * .5), 0, cos(heading + PI * .5))
		if side.dot(pos - road) < 0:
			side = -side
		var at: Vector3 = road + side * 7.0
		at.y = ground_height(at.x, at.z)
		_bus_stop(at, atan2(-side.x, -side.z))
	for i in mini(pedestrian_spawns.size(), 40):
		if i % 4 == 0:
			var p: Vector3 = pedestrian_spawns[i] + Vector3(_rng.randf_range(-2, 2), -.2, _rng.randf_range(-2, 2))
			_bench(p, _rng.randf() * TAU)
			_bin(p + Vector3(1.6, 0, 0))

func _facing(key: String) -> Dictionary:
	# A spot two metres off the kerb towards the real place, facing the street.
	var loc: Dictionary = locations[key]
	var kerb: Vector3 = loc["pos"]
	var anchor: Vector3 = loc["anchor"]
	var inward := Vector3(anchor.x - kerb.x, 0, anchor.z - kerb.z)
	if inward.length() < .5:
		inward = Vector3(sin(loc["car_heading"] + PI * .5), 0, cos(loc["car_heading"] + PI * .5))
	inward = inward.normalized()
	return {"kerb": kerb, "in": inward, "angle": atan2(inward.x, inward.z) + PI}

func _ground(p: Vector3) -> Vector3:
	return Vector3(p.x, ground_height(p.x, p.z), p.z)

func _signpost(at: Vector3, angle: float, key: String, size: Vector2, height: float = 3.2) -> void:
	var right := Vector3(cos(angle), 0, -sin(angle))
	for side in [-1.0, 1.0]:
		var foot := _ground(at + right * side * size.x * .42)
		_cylinder(foot + Vector3(0, height * .5, 0), 0.12, height + 0.3, "metal")
	_sign(_ground(at) + Vector3(0, height + size.y * .5 - .2, 0), size, key, angle)

func _story_places() -> void:
	if locations.is_empty():
		return
	# Cafe "Kodlo" sign and terrace
	var f := _facing("cafe")
	var at: Vector3 = f["kerb"] + f["in"] * 3.5
	_signpost(at, f["angle"], "cafe", Vector2(7.0, 1.6))
	_signpost(at + Vector3(sin(f["angle"] + PI * .5), 0, cos(f["angle"] + PI * .5)) * 5.5, f["angle"], "kodlo", Vector2(2.8, 1.6), 4.2)
	for i in 3:
		var t := _ground(at + f["in"] * 2.5 + Vector3(cos(f["angle"]), 0, -sin(f["angle"])) * (i * 2.4 - 2.4))
		_box(t + Vector3(0, .72, 0), Vector3(1.2, .08, 1.2), "wood", true)
		_cylinder(t + Vector3(0, .36, 0), .06, .72, "metal")
	# Central market: stalls on the real marketplace
	f = _facing("market")
	_signpost(f["kerb"] + f["in"] * 2.5, f["angle"], "market", Vector2(10.0, 2.0), 3.6)
	var right := Vector3(cos(f["angle"]), 0, -sin(f["angle"]))
	for row in 2:
		for i in 4:
			var pos: Vector3 = f["kerb"] + f["in"] * (9.0 + row * 9.0) + right * (i * 9.0 - 13.5)
			pos = _ground(pos)
			building_count += 1
			_box(pos + Vector3(0, 1.2, 0), Vector3(7.5, 2.4, 5.0), "wood", true, f["angle"])
			_box(pos + Vector3(0, 2.6, 0), Vector3(8.4, 0.25, 6.0), "blue" if (i + row) % 2 == 0 else "red", false, f["angle"])
			_box(pos - f["in"] * 2.9 + Vector3(0, 0.85, 0), Vector3(7.0, 0.12, 1.1), "wood", false, f["angle"])
			for j in 3:
				_box(pos - f["in"] * 2.9 + right * (j * 2.2 - 2.2) + Vector3(0, 1.05, 0), Vector3(1.3, 0.3, 0.8), "sand", false, f["angle"])
	# Garages co-op sign
	f = _facing("garages")
	_signpost(f["kerb"] + f["in"] * 2.0, f["angle"], "garage", Vector2(8.0, 1.4), 3.4)
	# Sawmill: log piles, sign, chimney
	f = _facing("sawmill")
	_signpost(f["kerb"] + f["in"] * 2.0, f["angle"], "sawmill", Vector2(12.0, 1.6), 4.0)
	right = Vector3(cos(f["angle"]), 0, -sin(f["angle"]))
	for row in 3:
		for col in 6:
			var log_pos := _ground(f["kerb"] + f["in"] * 9.0 + right * (8.0 + col * 1.3))
			_cylinder(log_pos + Vector3(0, .6 + row * 1.1, 0), .55, 10.0, "wood", PI * .5)
	# Quarry: granite boulders and the warning signs
	f = _facing("quarry")
	_signpost(f["kerb"] + f["in"] * 2.0, f["angle"], "granite", Vector2(9.0, 1.6), 3.0)
	_signpost(f["kerb"] + f["in"] * 2.0 + Vector3(sin(f["angle"] + PI * .5), 0, cos(f["angle"] + PI * .5)) * 6.0, f["angle"], "quarry", Vector2(2.6, 1.3), 1.6)
	for i in 9:
		var rock := _ground(f["kerb"] + f["in"] * _rng.randf_range(4, 12) + Vector3(_rng.randf_range(-8, 8), 0, _rng.randf_range(-8, 8)))
		_queue("canopy", "stone", Transform3D(Basis.from_scale(Vector3(_rng.randf_range(.7, 1.9), _rng.randf_range(.5, 1.2), _rng.randf_range(.7, 1.4))), rock + Vector3(0, .3, 0)))
	# Dorm / safehouse sign
	f = _facing("dorm")
	_signpost(f["kerb"] + f["in"] * 2.5, f["angle"], "safehouse", Vector2(8.0, 1.5), 2.6)
	# Cathedral square: the granite monument, benches, lamp ring
	var centre := _ground(plaza)
	var monument_scene := load("res://assets/models/stone_monument.glb") as PackedScene
	_box(centre + Vector3(0, .35, 0), Vector3(8.0, .7, 8.0), "stone", true)
	if monument_scene:
		var monument := monument_scene.instantiate() as Node3D
		monument.name = "BlenderGraniteMonument"
		monument.position = centre + Vector3(0, .7, 0)
		monument.scale = Vector3.ONE * 1.55
		add_child(monument)
	for i in 8:
		var a: float = i * TAU / 8.0
		var p := _ground(centre + Vector3(cos(a), 0, sin(a)) * 16.0)
		_bench(p, -a + PI * .5)
		if i % 2 == 0:
			_lamp(_ground(centre + Vector3(cos(a + .4), 0, sin(a + .4)) * 22.0), -a)
	_signpost(_ground(centre + Vector3(0, 0, 30)), 0.0, "wanted", Vector2(9.0, 2.6), 3.2)

func _lamp(pos: Vector3, rotation: float) -> void:
	_cylinder(pos + Vector3(0.0, 3.3, 0.0), 0.12, 6.6, "metal")
	_cylinder(pos + Vector3(0.0, 0.35, 0.0), 0.21, 0.7, "concrete")
	var arm: Vector3 = Vector3(0.0, 6.45, 0.95).rotated(Vector3.UP, rotation)
	_box(pos + arm, Vector3(0.14, 0.13, 2.0), "metal", false, rotation)
	var head: Vector3 = Vector3(0.0, 6.4, 1.8).rotated(Vector3.UP, rotation)
	_box(pos + head, Vector3(0.45, 0.16, 0.9), "dark", false, rotation)
	_box(pos + head - Vector3(0.0, 0.1, 0.0), Vector3(0.36, 0.06, 0.7), "lamp", false, rotation)
	lamp_heads.append(pos + head - Vector3(0.0, 0.3, 0.0))

func _bench(pos: Vector3, rotation: float) -> void:
	_box(pos + Vector3(0.0, 0.53, 0.0), Vector3(2.0, 0.13, 0.65), "wood", false, rotation)
	var back: Vector3 = Vector3(0.0, 0.95, -0.31).rotated(Vector3.UP, rotation)
	_box(pos + back, Vector3(2.0, 0.57, 0.12), "wood", false, rotation)
	for side in [-0.75, 0.75]:
		var foot: Vector3 = Vector3(side, 0.3, 0.0).rotated(Vector3.UP, rotation)
		_box(pos + foot, Vector3(0.1, 0.6, 0.65), "metal", false, rotation)

func _bin(pos: Vector3) -> void:
	_box(pos + Vector3(0.0, 0.47, 0.0), Vector3(0.65, 0.94, 0.65), "blue")
	_box(pos + Vector3(0.0, 0.98, 0.0), Vector3(0.73, 0.1, 0.73), "metal")

func _bus_stop(pos: Vector3, rotation: float) -> void:
	# Soviet concrete shelter, walls from the Teteriv stop photo
	var r := func(v: Vector3) -> Vector3: return pos + v.rotated(Vector3.UP, rotation)
	_box(r.call(Vector3(0.0, 0.07, 0.0)), Vector3(7.0, 0.14, 3.2), "concrete", false, rotation)
	_box(r.call(Vector3(0.0, 1.5, -1.45)), Vector3(6.4, 3.0, 0.25), "bus_stop_wall", true, rotation)
	for side in [-3.1, 3.1]:
		_box(r.call(Vector3(side, 1.5, -0.3)), Vector3(0.25, 3.0, 2.5), "bus_stop_wall", true, rotation)
	_box(r.call(Vector3(0.0, 3.1, -0.2)), Vector3(7.0, 0.25, 3.2), "concrete", false, rotation)
	_box(r.call(Vector3(0.0, 0.5, -1.0)), Vector3(5.0, 0.12, 0.5), "wood", false, rotation)
	_sign(r.call(Vector3(0.0, 2.75, 1.42)), Vector2(3.4, 0.7), "stop", rotation)

func _wire(start: Vector3, end: Vector3) -> void:
	var previous: Vector3 = start
	for i in range(1, 7):
		var t: float = float(i) / 6.0
		var next: Vector3 = start.lerp(end, t) - Vector3(0.0, sin(t * PI) * 1.4, 0.0)
		var diff: Vector3 = next - previous
		var transform := Transform3D()
		transform.origin = (previous + next) * 0.5
		transform.basis = Basis.looking_at(diff.normalized(), Vector3.UP) * Basis.from_scale(Vector3(0.035, 0.035, diff.length()))
		_queue("box", "dark", transform)
		previous = next

func _box(pos: Vector3, size: Vector3, key: String, collision: bool = false, rotation: float = 0.0) -> void:
	var transform := Transform3D(Basis(Vector3.UP, rotation) * Basis.from_scale(size), pos)
	_queue("box", key, transform)
	if collision:
		var shape := BoxShape3D.new()
		shape.size = size
		var collider := CollisionShape3D.new()
		collider.shape = shape
		collider.position = pos
		collider.rotation.y = rotation
		_solid.add_child(collider)

func _cylinder(pos: Vector3, radius: float, height: float, key: String, rotation: float = 0.0) -> void:
	var transform := Transform3D(Basis(Vector3.RIGHT, rotation) * Basis.from_scale(Vector3(radius, height, radius)), pos)
	_queue("cylinder", key, transform)

func _queue(shape: String, material: String, transform: Transform3D) -> void:
	var key: String = shape + ":" + material
	if not _batches.has(key):
		_batches[key] = {"shape": shape, "material": material, "transforms": []}
	(_batches[key]["transforms"] as Array).append(transform)

func _wall(pos: Vector3, size: Vector2, angle: float, key: String, uv_size: Vector2) -> void:
	var basis := Basis(Vector3.UP, angle)
	var points: Array[Vector3] = [pos + basis * Vector3(-size.x * 0.5, -size.y * 0.5, 0.0), pos + basis * Vector3(size.x * 0.5, -size.y * 0.5, 0.0), pos + basis * Vector3(size.x * 0.5, size.y * 0.5, 0.0), pos + basis * Vector3(-size.x * 0.5, size.y * 0.5, 0.0)]
	_quad(key, points, basis * Vector3(0.0, 0.0, 1.0), uv_size)

func _sign(pos: Vector3, size: Vector2, key: String, angle: float = 0.0) -> void:
	_wall(pos, size, angle, "sign_" + key if _mats.has("sign_" + key) else key, Vector2.ONE)

func _quad(key: String, points: Array[Vector3], normal: Vector3, uv_size: Vector2) -> void:
	if not _quads.has(key):
		_quads[key] = {"vertices": [], "normals": [], "uvs": [], "indices": []}
	var data: Dictionary = _quads[key]
	var index: int = (data["vertices"] as Array).size()
	(data["vertices"] as Array).append_array(points)
	for i in range(4):
		(data["normals"] as Array).append(normal)
	(data["uvs"] as Array).append_array([Vector2(0.0, uv_size.y), uv_size, Vector2(uv_size.x, 0.0), Vector2.ZERO])
	var orientation: float = (points[2]-points[0]).cross(points[1]-points[0]).dot(normal)
	if orientation > 0.0:
		(data["indices"] as Array).append_array([index,index+1,index+2,index,index+2,index+3])
	else:
		(data["indices"] as Array).append_array([index,index+2,index+1,index,index+3,index+2])

func _flush_geometry() -> void:
	for key in _batches:
		var data: Dictionary = _batches[key]
		var mesh: Mesh
		if data["shape"] == "box":
			var box := BoxMesh.new()
			box.size = Vector3.ONE
			mesh = box
		elif data["shape"] == "canopy":
			var sphere := SphereMesh.new()
			sphere.radius = 1.0
			sphere.height = 2.0
			sphere.radial_segments = 9
			sphere.rings = 4
			mesh = sphere
		else:
			var cylinder := CylinderMesh.new()
			cylinder.top_radius = 1.0
			cylinder.bottom_radius = 1.0
			cylinder.height = 1.0
			cylinder.radial_segments = 8
			cylinder.rings = 1
			mesh = cylinder
		mesh.surface_set_material(0, _mats[data["material"]])
		var multimesh := MultiMesh.new()
		multimesh.transform_format = MultiMesh.TRANSFORM_3D
		multimesh.mesh = mesh
		var transforms: Array = data["transforms"]
		multimesh.instance_count = transforms.size()
		for i in range(transforms.size()):
			multimesh.set_instance_transform(i, transforms[i])
		var instance := MultiMeshInstance3D.new()
		instance.name = "Batch_" + String(key).replace(":", "_")
		instance.multimesh = multimesh
		add_child(instance)
	for key in _quads:
		var data: Dictionary = _quads[key]
		var arrays: Array = []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array(data["vertices"])
		arrays[Mesh.ARRAY_NORMAL] = PackedVector3Array(data["normals"])
		arrays[Mesh.ARRAY_TEX_UV] = PackedVector2Array(data["uvs"])
		arrays[Mesh.ARRAY_INDEX] = PackedInt32Array(data["indices"])
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		mesh.surface_set_material(0, _mats[key])
		var instance := MeshInstance3D.new()
		instance.name = "Painted_" + String(key)
		instance.mesh = mesh
		add_child(instance)
	_batches.clear()
	_quads.clear()
