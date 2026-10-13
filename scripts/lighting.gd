extends Node3D
class_name KLighting

# GTA III style time cycle: per-hour colours for ambient, sun, sky gradient and a hard
# draw distance hidden in horizon-coloured fog; weather blends between tables.
# No real shadows: actors get blob shadows (blob_shadow()), lamps get coronas at night.

# hour: [ambient, sun, sky top, sky horizon, far clip, sun strength]
const SUNNY := {
	0: [Color8(62,66,96), Color8(70,76,112), Color8(4,8,28), Color8(28,34,64), 520.0, 0.0],
	5: [Color8(66,66,92), Color8(80,82,110), Color8(10,16,46), Color8(70,62,92), 560.0, 0.0],
	6: [Color8(86,74,74), Color8(214,146,104), Color8(42,70,122), Color8(214,152,112), 700.0, .5],
	7: [Color8(104,98,94), Color8(236,206,166), Color8(62,102,164), Color8(194,184,172), 820.0, .8],
	12: [Color8(118,118,114), Color8(255,246,226), Color8(54,100,176), Color8(178,196,212), 900.0, 1.0],
	18: [Color8(110,102,96), Color8(244,206,158), Color8(58,90,150), Color8(206,182,156), 860.0, .9],
	20: [Color8(108,88,92), Color8(226,124,82), Color8(40,46,92), Color8(232,124,82), 760.0, .6],
	21: [Color8(88,82,108), Color8(100,88,122), Color8(14,18,54), Color8(80,58,92), 620.0, .0],
	22: [Color8(64,66,96), Color8(72,76,110), Color8(5,9,30), Color8(32,36,66), 540.0, 0.0],
}
const CLOUDY := {
	0: [Color8(60,62,74), Color8(52,54,66), Color8(10,12,20), Color8(34,36,46), 440.0, 0.0],
	6: [Color8(84,84,86), Color8(120,116,112), Color8(70,76,86), Color8(130,128,128), 560.0, .2],
	12: [Color8(124,126,128), Color8(150,150,150), Color8(104,112,122), Color8(162,166,170), 640.0, .3],
	19: [Color8(104,100,100), Color8(140,128,120), Color8(86,90,100), Color8(150,140,136), 600.0, .2],
	21: [Color8(66,66,78), Color8(60,60,72), Color8(18,20,30), Color8(48,48,58), 480.0, 0.0],
}
const FOGGY := {
	0: [Color8(46,48,54), Color8(40,42,48), Color8(30,32,38), Color8(40,42,48), 150.0, 0.0],
	7: [Color8(110,110,112), Color8(110,110,110), Color8(150,152,154), Color8(160,162,164), 190.0, .1],
	12: [Color8(132,132,134), Color8(130,130,130), Color8(176,178,180), Color8(186,188,190), 230.0, .15],
	19: [Color8(110,106,106), Color8(110,104,100), Color8(140,136,136), Color8(150,146,144), 200.0, .1],
	21: [Color8(52,52,58), Color8(46,46,52), Color8(40,40,46), Color8(50,50,56), 160.0, 0.0],
}
const WEATHERS := {"sunny": SUNNY, "cloudy": CLOUDY, "foggy": FOGGY}
const WEATHER_ODDS := [["sunny", .6], ["cloudy", .3], ["foggy", .1]]

var game
var env: Environment
var sky_material: ProceduralSkyMaterial
var sun: DirectionalLight3D
var actor_fill: DirectionalLight3D
var weather := "sunny"
var next_weather := "sunny"
var weather_blend := 1.0
var weather_hour := -1
var night := 0.0
var _coronas: MultiMeshInstance3D
var _corona_material: StandardMaterial3D
static var _blob: Texture2D

func setup(world: Node3D) -> void:
	env = Environment.new()
	env.background_mode = Environment.BG_SKY
	sky_material = ProceduralSkyMaterial.new()
	sky_material.sky_curve = .18
	sky_material.sun_angle_max = 8.0
	sky_material.sun_curve = .08
	sky_material.use_debanding = false
	var sky := Sky.new()
	sky.sky_material = sky_material
	sky.radiance_size = Sky.RADIANCE_SIZE_32
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_depth_curve = 1.6
	env.fog_sky_affect = 0.0
	env.fog_light_energy = 1.0
	env.adjustment_enabled = true
	env.adjustment_saturation = .92
	var holder := WorldEnvironment.new()
	holder.environment = env
	world.add_child(holder)
	sun = DirectionalLight3D.new()
	sun.shadow_enabled = false
	sun.light_specular = .15
	world.add_child(sun)
	# GTA III lit peds and cars with their own directional+ambient pair, so actors never
	# sink into the dusk/night world. Here: a camera-side fill that only hits layer 2.
	actor_fill = DirectionalLight3D.new()
	actor_fill.shadow_enabled = false
	actor_fill.light_cull_mask = 2
	actor_fill.light_specular = .4
	world.add_child(actor_fill)
	world.add_child(self)

func _process(delta: float) -> void:
	if not game: return
	var minutes: float = fmod(game.clock_minutes, 1440.0)
	var hour := minutes / 60.0
	_update_weather(int(hour))
	weather_blend = minf(1.0, weather_blend + delta / 30.0)
	var a := _sample(WEATHERS[weather], hour)
	var b := _sample(WEATHERS[next_weather], hour)
	var c: Array = []
	for i in a.size():
		c.append(lerp(a[i], b[i], weather_blend))
	var ambient: Color = c[0]
	var sun_color: Color = c[1]
	var top: Color = c[2]
	var horizon: Color = c[3]
	var far_clip: float = c[4]
	var sun_strength: float = c[5]
	env.ambient_light_color = ambient
	env.ambient_light_energy = 1.55
	sky_material.sky_top_color = top
	sky_material.sky_horizon_color = horizon
	sky_material.ground_horizon_color = horizon
	sky_material.ground_bottom_color = horizon.darkened(.35)
	sky_material.sun_angle_max = 8.0 if sun_strength > .05 else 0.0
	env.fog_light_color = horizon
	env.fog_depth_end = far_clip
	env.fog_depth_begin = far_clip * .38
	if game.camera: game.camera.far = far_clip + 20.0
	# sun path: rises in the east at 6, sets in the west at 20; a dim moon light at night
	var day := clampf((hour - 6.0) / 14.0, 0.0, 1.0)
	var elevation := sin(day * PI) * 62.0 + 4.0
	var azimuth := lerpf(-100.0, 100.0, day)
	if sun_strength <= .01:
		elevation = 48.0; azimuth = 150.0
	sun.rotation_degrees = Vector3(-elevation, azimuth, 0)
	sun.light_color = sun_color
	sun.light_energy = .35 + .55 * sun_strength
	night = clampf(1.0 - (sun_strength * 4.0), 0.0, 1.0) if hour < 7 or hour > 19 else 0.0
	_update_actor_fill(ambient, sun_strength)
	_update_coronas()

func _update_actor_fill(ambient: Color, sun_strength: float) -> void:
	var cam: Camera3D = game.camera
	if cam:
		var forward := -cam.global_basis.z
		forward.y = 0.0
		if forward.length() < .01: forward = Vector3.FORWARD
		actor_fill.global_basis = Basis.looking_at((forward.normalized() + Vector3.DOWN * .8).normalized(), Vector3.UP)
	actor_fill.light_color = ambient.lerp(Color(1, 1, 1), .5)
	actor_fill.light_energy = lerpf(.75, .2, clampf(sun_strength, 0.0, 1.0))

func _sample(table: Dictionary, hour: float) -> Array:
	var keys: Array = table.keys()
	keys.sort()
	var prev: int = keys[-1]
	var next: int = keys[0]
	for k in keys:
		if k <= hour: prev = k
	for k in keys:
		if k > hour: next = k; break
	var span := fposmod(float(next) - float(prev), 24.0)
	var t := 0.0 if span == 0.0 else fposmod(hour - float(prev), 24.0) / span
	var out: Array = []
	for i in table[prev].size():
		out.append(lerp(table[prev][i], table[next][i], t))
	return out

func _update_weather(hour: int) -> void:
	if hour == weather_hour: return
	weather_hour = hour
	if hour % 4 != 0: return
	weather = next_weather
	var roll := randf()
	for entry in WEATHER_ODDS:
		roll -= entry[1]
		if roll <= 0:
			next_weather = entry[0]
			break
	weather_blend = 0.0 if next_weather != weather else 1.0

func force_weather(name: String) -> void:
	weather = name; next_weather = name; weather_blend = 1.0

# ---------------------------------------------------------------- coronas

func add_coronas(points: Array) -> void:
	_corona_material = StandardMaterial3D.new()
	_corona_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_corona_material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	_corona_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_corona_material.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	_corona_material.no_depth_test = false
	_corona_material.albedo_texture = blob_texture()
	_corona_material.albedo_color = Color(1, .82, .52)
	var quad := QuadMesh.new()
	quad.size = Vector2(2.6, 2.6)
	quad.material = _corona_material
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = quad
	mm.instance_count = points.size()
	for i in points.size():
		mm.set_instance_transform(i, Transform3D(Basis(), points[i]))
	_coronas = MultiMeshInstance3D.new()
	_coronas.name = "LampCoronas"
	_coronas.multimesh = mm
	_coronas.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_coronas.visibility_range_end = 380.0
	add_child(_coronas)

func _update_coronas() -> void:
	if game.city and game.city._mats.has("lamp"):
		(game.city._mats["lamp"] as StandardMaterial3D).emission_energy_multiplier = .2 + 3.0 * night
	if not _coronas: return
	_coronas.visible = night > .05
	_corona_material.albedo_color = Color(1, .82, .52, night)

static func blob_texture() -> Texture2D:
	if _blob == null:
		var gradient := Gradient.new()
		gradient.set_color(0, Color(1, 1, 1, 1))
		gradient.set_color(1, Color(1, 1, 1, 0))
		gradient.add_point(.45, Color(1, 1, 1, .7))
		var tex := GradientTexture2D.new()
		tex.gradient = gradient
		tex.fill = GradientTexture2D.FILL_RADIAL
		tex.fill_from = Vector2(.5, .5)
		tex.fill_to = Vector2(1, .5)
		tex.width = 64
		tex.height = 64
		_blob = tex
	return _blob

# GTA III had no real-time shadows, only a dark blob under every actor.
static func blob_shadow(owner: Node3D, size: Vector2, strength: float = .6) -> Decal:
	var decal := Decal.new()
	decal.name = "BlobShadow"
	decal.texture_albedo = blob_texture()
	decal.modulate = Color(0, 0, 0, strength)
	decal.size = Vector3(size.x, 2.0, size.y)
	decal.position = Vector3(0, .4, 0)
	decal.upper_fade = .3
	decal.lower_fade = .5
	decal.cull_mask = 1
	owner.add_child(decal)
	_actor_layer.call_deferred(owner)
	return decal

static func _actor_layer(node: Node) -> void:
	if not is_instance_valid(node): return
	if node is VisualInstance3D and not node is Decal:
		(node as VisualInstance3D).layers = 2
	for child in node.get_children():
		_actor_layer(child)
