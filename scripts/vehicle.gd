extends CharacterBody3D
class_name KVehicle

var pitch := 0.0
var headlights: Array[MeshInstance3D] = []
var bank := 0.0
var game
var driver
var model: Node3D
var kind := "sedan"
var car_name := "ЖИГУЛЬ / 2106"
var speed := 0.0
var health := 100.0
var traffic := false
var police := false
var route: Array[Vector3] = []
var route_index := 0
var wheels: Array[Node3D] = []
var roll := 0.0
var crash_cooldown := 0.0
var siren_time := 0.0
var red_light: MeshInstance3D
var blue_light: MeshInstance3D
var chase_route: Array[Vector3] = []
var chase_index := 0
var chase_refresh := 0.0
var paint_index := 0
var skid_amount := 0.0

func _ready() -> void:
	collision_layer = 2
	collision_mask = 3
	floor_snap_length = .6
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(1.65,1.15,3.95 if kind != "minibus" else 4.8)
	shape.shape = box
	shape.position.y = .7
	add_child(shape)
	var path := "res://assets/models/%s.glb" % kind
	if ResourceLoader.exists(path):
		model = load(path).instantiate()
		add_child(model)
		for label in ["Wheel_FL","Wheel_FR","Wheel_RL","Wheel_RR"]:
			var wheel = model.find_child(label,true,false)
			if wheel: wheels.append(wheel)
		if kind == "sedan": tint_paint(model)
		tune_visual(model)
	else:
		model = Node3D.new()
		add_child(model)
		var body := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(1.85,1.4,4.2)
		body.mesh = bm
		body.position.y = .75
		model.add_child(body)
	if police:
		car_name = "МІЛІЦІЯ / 102"
		red_light = light_cube(Vector3(-.38,1.58,0),Color(1,.02,.01))
		blue_light = light_cube(Vector3(.38,1.58,0),Color(.02,.25,1))
	if kind == "minibus": car_name = "МАРШРУТКА / КОРОСТИШІВ"
	KLighting.blob_shadow(self,Vector2(2.4,4.8 if kind != "minibus" else 5.6),.7)
	for side in [-.6,.6]:
		var lamp := MeshInstance3D.new()
		var quad := QuadMesh.new(); quad.size = Vector2(.75,.75)
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED; mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA; mat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
		mat.albedo_texture = KLighting.blob_texture(); mat.albedo_color = Color(1,.95,.8)
		quad.material = mat; lamp.mesh = quad
		lamp.position = Vector3(side,.75,-(2.05 if kind != "minibus" else 2.45))
		lamp.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(lamp); headlights.append(lamp)

func tint_paint(node: Node) -> void:
	# Soviet factory paints: «липа», «коррида», «балтика», «сафарі», «білий», «баклажан»
	var palette := [Color("5f8a4c"),Color("b0302a"),Color("3f6f9c"),Color("d6c79a"),Color("e2e0d6"),Color("5a2f4a")]
	if node is MeshInstance3D and node.mesh:
		for i in node.mesh.get_surface_count():
			var original = node.mesh.surface_get_material(i)
			if original is StandardMaterial3D and original.resource_name == "Sedan_Paint":
				var tinted: StandardMaterial3D = original.duplicate()
				tinted.albedo_color = palette[paint_index%palette.size()]
				tinted.metallic = 0.0
				tinted.roughness = .35
				tinted.metallic_specular = .6
				node.set_surface_override_material(i,tinted)
	for child in node.get_children(): tint_paint(child)

func tune_visual(node: Node) -> void:
	if node is MeshInstance3D:
		node.visibility_range_end = 160
		if not String(node.name).contains("Vehicle_Body"):
			node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for child in node.get_children(): tune_visual(child)

func light_cube(at: Vector3, color: Color) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	var cube := BoxMesh.new()
	cube.size = Vector3(.32,.14,.32)
	mesh.mesh = cube
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mesh.material_override = mat
	mesh.position = at
	add_child(mesh)
	return mesh

func _physics_process(delta: float) -> void:
	if game and game.city and global_position.y < game.city.ground_height(global_position.x,global_position.z)-1.2 and not game.city.is_underwater(global_position):
		global_position.y = game.city.ground_height(global_position.x,global_position.z)+.4; velocity = Vector3.ZERO
	if game.mode != "play": skid_amount = 0; return
	crash_cooldown = maxf(0,crash_cooldown-delta)
	var throttle := 0.0
	var steer := 0.0
	var braking := false
	if driver:
		throttle = Input.get_axis("back","forward")
		steer = Input.get_axis("right","left")
		braking = Input.is_action_pressed("jump")
	elif police and game.wanted > 0:
		var target: Vector3 = game.actor_position()
		chase_refresh -= delta
		if chase_refresh <= 0 or chase_route.is_empty():
			chase_route = game.city.road_route(global_position,target)
			chase_index = 0; chase_refresh = 2.5
		while chase_index < chase_route.size()-1 and global_position.distance_to(chase_route[chase_index]) < 7:
			chase_index += 1
		var goal: Vector3 = chase_route[chase_index] if not chase_route.is_empty() else target
		var delta_pos := target-global_position
		var aim := goal-global_position
		var desired := atan2(-aim.x,-aim.z)
		steer = clampf(angle_difference(rotation.y,desired)*1.6,-1,1)
		throttle = .75 if delta_pos.length() > 7 else .1
		if absf(steer) > .7 and absf(speed) > 7: braking = true
		if delta_pos.length() < 5 and not game.player.vehicle:
			game.player.damage(8)
	elif traffic and not route.is_empty():
		var goal: Vector3 = route[route_index]
		if global_position.distance_to(goal) < 8:
			route_index = (route_index+1)%route.size()
			goal = route[route_index]
		var aim := goal-global_position
		steer = clampf(angle_difference(rotation.y,atan2(-aim.x,-aim.z))*2.3,-1,1)
		throttle = .55
		if absf(steer) > .8 and speed > 8: braking = true
		var ahead := PhysicsRayQueryParameters3D.create(global_position+Vector3(0,.65,0),global_position+Vector3(0,.65,0)-global_basis.z*7,6,[get_rid()])
		if not get_world_3d().direct_space_state.intersect_ray(ahead).is_empty(): braking = true
	if health <= 0: throttle = 0; braking = true
	skid_amount = clampf((absf(speed)-7)/10,0,1) if braking or (absf(steer)>.7 and absf(speed)>13) else 0.0
	if throttle != 0:
		var accel := 10.5 if speed*throttle >= 0 else 20.0
		speed = move_toward(speed,throttle*(24.0 if kind != "minibus" else 18.0),accel*delta)
	else:
		speed = move_toward(speed,0,delta*2.7)
	if braking: speed = move_toward(speed,0,delta*27)
	rotation.y += steer*delta*1.65*clampf(absf(speed)/8,0,1)*(1 if speed >= 0 else -1)
	var forward := -global_basis.z
	velocity.x = forward.x*speed
	velocity.z = forward.z*speed
	velocity.y = -3 if is_on_floor() else velocity.y-24*delta
	var before := speed
	move_and_slide()
	if get_slide_collision_count() > 0 and absf(before) > 4 and crash_cooldown <= 0:
		for i in get_slide_collision_count():
			var hit := get_slide_collision(i)
			if absf(hit.get_normal().y) < .45:
				health -= absf(before)*.6
				speed *= -.18
				crash_cooldown = .8
				if driver:
					game.sound("crash" if absf(before)>10 else "crash_light",clampf(absf(before)/24,.3,.9))
					game.camera_shake = .22
				break
	roll = lerpf(roll,-steer*speed*.0025,delta*5)
	# Body follows the hills of the Teteriv valley.
	var ground_normal := get_floor_normal() if is_on_floor() else Vector3.UP
	pitch = lerpf(pitch,-asin(clampf(ground_normal.dot(-global_basis.z),-.5,.5)),delta*8)
	bank = lerpf(bank,asin(clampf(ground_normal.dot(global_basis.x),-.5,.5)),delta*8)
	model.rotation.x = pitch
	var lit: bool = game.lighting and game.lighting.night > .1 and (driver or traffic or police)
	for lamp in headlights: lamp.visible = lit
	model.rotation.z = roll+bank
	for wheel in wheels:
		wheel.rotation.x -= speed*delta*2.7
	if police:
		siren_time += delta
		red_light.visible = sin(siren_time*15)>0
		blue_light.visible = not red_light.visible
	global_position.x = clampf(global_position.x,game.city.playable_bounds.position.x,game.city.playable_bounds.end.x)
	global_position.z = clampf(global_position.z,game.city.playable_bounds.position.y,game.city.playable_bounds.end.y)
	if driver and health <= 0:
		game.fail_mission("ЖИГУЛЬ ПРИЇХАВ", "Після такого навіть молоток не допоможе.")
	if game.city.is_underwater(global_position) or global_position.y < -40:
		if driver:
			game.fail_mission("ЖИГУЛЬ У ТЕТЕРЕВІ", "Подро переплутав дорогу з водою. ENTER: повтор.")
		elif not route.is_empty():
			global_position = route[0]; speed = 0; velocity = Vector3.ZERO
		return
	if absf(speed) > 5:
		for person in game.people:
			if is_instance_valid(person) and person.alive and global_position.distance_to(person.global_position)<2:
				person.hit(80 if absf(speed)>12 else 35,global_position)
				if driver: game.crime(1)
