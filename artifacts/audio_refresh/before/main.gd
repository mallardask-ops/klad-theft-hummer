extends Node

const SAVE_PATH := "user://korostyshiv-save.json"
const SETTINGS_PATH := "user://settings.json"
var world: Node3D
var city: KCity
var lighting: KLighting
var player: KPlayer
var starter_car: KVehicle
var cars: Array[KVehicle] = []
var people: Array[KPerson] = []
var police_cars: Array[KVehicle] = []
var camera: Camera3D
var viewport: SubViewport
var hud: KHud
var missions: KMissions
var mode := "menu"
var money := 350
var wanted := 0
var wanted_timer := 0.0
var crime_cooldown := 0.0
var clock_minutes := 20.0*60+42
var camera_yaw := 0.0
var camera_pitch := -.10
var camera_distance := 5.8
var camera_shake := 0.0
var mouse_sensitivity := 1.0
var shake_on := true
var radio_on := true
var volume := .7
var dialogue_title := ""
var dialogue_speaker := ""
var dialogue_lines: Array = []
var dialogue_index := 0
var dialogue_callback: Callable
var fail_title := ""
var fail_reason := ""
var menu_time := 0.0
var sfx: Array[AudioStreamPlayer] = []
var sfx_index := 0
var footstep_index := 0
var radio: AudioStreamPlayer
var engine_audio: AudioStreamPlayer
var siren_audio: AudioStreamPlayer
var ambience: AudioStreamPlayer
var nature_audio: Array[AudioStreamPlayer] = []
var verification_started := false
var givers: Dictionary = {}
var frame_samples: Array[float] = []
var evidence_dir := "res://artifacts/validation/current"

func _ready() -> void:
	if not OS.has_feature("editor"): evidence_dir = ProjectSettings.globalize_path("user://validation")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--evidence-dir="): evidence_dir = arg.trim_prefix("--evidence-dir=")
	setup_input()
	load_settings()
	var display := TextureRect.new()
	display.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	display.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	display.mouse_filter = Control.MOUSE_FILTER_IGNORE
	display.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	display.stretch_mode = TextureRect.STRETCH_SCALE
	add_child(display)
	viewport = SubViewport.new()
	viewport.size = Vector2i(896,504)
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.own_world_3d = true
	viewport.msaa_3d = Viewport.MSAA_DISABLED
	add_child(viewport)
	display.texture = viewport.get_texture()
	var post := ShaderMaterial.new(); post.shader = preload("res://assets/shaders/retro.gdshader")
	display.material = post
	world = Node3D.new(); viewport.add_child(world)
	setup_environment()
	city = KCity.new(); world.add_child(city); city.build()
	lighting.add_coronas(city.lamp_heads)
	player = KPlayer.new(); player.game = self; player.position = city.location("start")+Vector3(0,.3,0)
	world.add_child(player)
	camera = Camera3D.new(); camera.fov = 68; camera.far = 700; camera.near = .1
	world.add_child(camera)
	starter_car = spawn_car(starter_spot(),"sedan",false)
	starter_car.rotation.y = city.locations["start"]["car_heading"]
	populate_city()
	hud = KHud.new(); hud.game = self; add_child(hud)
	missions = KMissions.new(); missions.game = self; add_child(missions)
	setup_audio()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	get_window().focus_entered.connect(restore_mouse)
	get_window().focus_exited.connect(release_mouse)
	update_camera(1)
	print("KOROSTYSHIV_READY cars=",cars.size()," pedestrians=",people.size()," missions=",missions.missions.size())
	if "--verify" in OS.get_cmdline_user_args():
		call_deferred("run_verification")
	elif "--tour" in OS.get_cmdline_user_args():
		call_deferred("run_tour")

func setup_input() -> void:
	var bindings := {"forward":[KEY_W,KEY_UP],"back":[KEY_S,KEY_DOWN],"left":[KEY_A,KEY_LEFT],"right":[KEY_D,KEY_RIGHT],"sprint":[KEY_SHIFT],"jump":[KEY_SPACE],"vehicle":[KEY_F],"interact":[KEY_E,KEY_ENTER],"attack":[KEY_CTRL],"pause":[KEY_ESCAPE],"map":[KEY_M,KEY_TAB],"radio":[KEY_R],"camera":[KEY_V]}
	for action in bindings:
		if not InputMap.has_action(action): InputMap.add_action(action)
		for code in bindings[action]:
			var key := InputEventKey.new(); key.physical_keycode = code; InputMap.action_add_event(action,key)
	var click := InputEventMouseButton.new(); click.button_index = MOUSE_BUTTON_LEFT
	InputMap.action_add_event("attack",click)
	var controller := {"jump":JOY_BUTTON_A,"vehicle":JOY_BUTTON_Y,"interact":JOY_BUTTON_X,"pause":JOY_BUTTON_START,"attack":JOY_BUTTON_RIGHT_SHOULDER,"map":JOY_BUTTON_BACK,"sprint":JOY_BUTTON_LEFT_SHOULDER}
	for action in controller:
		var button := InputEventJoypadButton.new(); button.button_index = controller[action]; InputMap.action_add_event(action,button)
	for spec in [["left",JOY_AXIS_LEFT_X,-1],["right",JOY_AXIS_LEFT_X,1],["forward",JOY_AXIS_LEFT_Y,-1],["back",JOY_AXIS_LEFT_Y,1]]:
		var axis := InputEventJoypadMotion.new(); axis.axis = spec[1]; axis.axis_value = spec[2]; InputMap.action_add_event(spec[0],axis)

func setup_environment() -> void:
	lighting = KLighting.new(); lighting.game = self
	lighting.setup(world)

func spawn_car(at: Vector3, kind: String, traffic: bool) -> KVehicle:
	var car := KVehicle.new(); car.game = self; car.kind = kind; car.traffic = traffic; car.position = at
	car.paint_index = cars.size()
	car.police = kind == "police_sedan"
	world.add_child(car); cars.append(car)
	return car

func populate_city() -> void:
	# Traffic follows loops planned on the real street graph (tools/city/plan_korostyshiv.py).
	var routes: Array = city.traffic_routes
	for i in 14:
		if routes.is_empty(): break
		var route: Array = routes[i%routes.size()]
		var start: int = (i/routes.size()*7+i*3)%route.size()
		var at: Vector3 = route[start]
		var next: Vector3 = route[(start+1)%route.size()]
		var car := spawn_car(at,"minibus" if i%5 == 0 else "sedan",true)
		car.route.assign(route); car.route_index = (start+1)%route.size()
		var dir: Vector3 = next-at
		car.rotation.y = atan2(-dir.x,-dir.z)
	for key in ["cafe","garages","market","sawmill","dorm","plaza"]:
		var spot: Dictionary = city.locations[key]
		var heading: float = spot["car_heading"]
		var along := Vector3(-sin(heading),0,-cos(heading))*9.0
		var car := spawn_car(spot["car"]+along+Vector3(0,.3,0),"sedan",false); car.rotation.y = heading
	var rng := RandomNumberGenerator.new(); rng.seed = 2721027
	for i in 40:
		var person := KPerson.new(); person.game = self
		person.position = city.pedestrian_spawns[i%city.pedestrian_spawns.size()]+Vector3(0,.3,0)
		person.walk_end = city.pedestrian_goals[i%city.pedestrian_goals.size()]+Vector3(0,.3,0)
		world.add_child(person); people.append(person)
	for spec in [["edik","cafe",1.5],["serhiy","cafe",3.5],["cyber","garages",2.0],["podrina","quarry",2.0],["podrina_safe","dorm",2.0]]:
		var spot: Dictionary = city.locations[spec[1]]
		var inward: Vector3 = (spot["anchor"]-spot["pos"])*Vector3(1,0,1)
		var at: Vector3 = spot["pos"]+inward.normalized()*float(spec[2])
		at.y = city.ground_height(at.x,at.z)+.3
		var person := KPerson.new(); person.game = self; person.model_name = String(spec[0]).trim_suffix("_safe"); person.position = at; person.stationary = true
		world.add_child(person); people.append(person); givers[spec[0]] = person

func _process(delta: float) -> void:
	menu_time += delta
	if missions:
		for key in givers:
			givers[key].visible = key != "serhiy" or missions.index == 1
			if key == "edik": givers[key].visible = missions.index != 1
	if mode == "play":
		crime_cooldown = maxf(0,crime_cooldown-delta)
		if verification_started and delta < .2: frame_samples.append(delta)
		clock_minutes += delta  # GTA III: one game minute per real second
		camera_shake = maxf(0,camera_shake-delta)
		if wanted > 0:
			if police_near(): wanted_timer = maxf(wanted_timer,9)
			else:
				wanted_timer -= delta
				if wanted_timer <= 0:
					wanted -= 1; wanted_timer = 9
					if wanted == 0:
						clear_wanted()
	update_camera(delta)
	if radio:
		radio.volume_db = linear_to_db(maxf(.001,volume*.36)) if player.vehicle and radio_on and mode=="play" else -80
		engine_audio.volume_db = linear_to_db(maxf(.001,volume*.26)) if player.vehicle and mode=="play" else -80
		engine_audio.pitch_scale = .65+absf(player.vehicle.speed)*.065 if player.vehicle else .7
		siren_audio.volume_db = linear_to_db(maxf(.001,volume*.18)) if wanted>0 and mode=="play" and police_near(65) else -80
		ambience.volume_db = linear_to_db(maxf(.001,volume*.12))
		var pos := actor_position()
		var river_distance: float = city.distance_to_water(pos)
		var river_mix: float = 1-smoothstep(35,110,river_distance)
		var outskirts: float = smoothstep(450,1000,Vector2(pos.x-city.plaza.x,pos.z-city.plaza.z).length())
		ambience.volume_db = linear_to_db(maxf(.001,volume*.16*(1-outskirts*.9)))
		for i in nature_audio.size():
			var strength: float = [river_mix*.32,maxf(outskirts,river_mix*.65)*.15,.045+outskirts*.10][i]
			nature_audio[i].volume_db = linear_to_db(maxf(.001,volume*strength)) if mode in ["play","dialogue"] else -80

func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and mode == "play" and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		camera_yaw -= event.relative.x*.0027*mouse_sensitivity
		camera_pitch = clampf(camera_pitch-event.relative.y*.0025*mouse_sensitivity,-.65,.28)
	if event is InputEventKey and event.echo: return
	if event.is_action_pressed("pause"):
		if mode == "dialogue": finish_dialogue()
		elif mode == "map": set_mode("play")
		elif mode == "play": hud.choice = 0; set_mode("pause")
		elif mode == "failed": set_mode("menu")
		elif hud.settings: hud.settings = false; hud.choice = 0; save_settings()
		elif mode == "pause": set_mode("play")
		return
	if mode in ["menu","pause"]:
		var count := 5 if hud.settings or mode=="pause" else 4
		if event.is_action_pressed("ui_down") or event.is_action_pressed("ui_focus_next"): hud.choice = (hud.choice+1)%count; sound("ui",.25)
		if event.is_action_pressed("ui_up") or event.is_action_pressed("ui_focus_prev"): hud.choice = posmod(hud.choice-1,count); sound("ui",.25)
		if hud.settings and (event.is_action_pressed("ui_left") or event.is_action_pressed("ui_right")):
			change_setting(-1 if event.is_action_pressed("ui_left") else 1)
		if event.is_action_pressed("ui_accept") or event.is_action_pressed("interact"): menu_confirm()
		return
	if mode == "dialogue":
		if event.is_action_pressed("interact") or event.is_action_pressed("ui_accept"):
			dialogue_index += 1
			if dialogue_index >= dialogue_lines.size(): finish_dialogue()
		return
	if mode == "failed":
		if event.is_action_pressed("interact") or event.is_action_pressed("ui_accept"): retry_mission()
		return
	if event.is_action_pressed("map"):
		set_mode("play" if mode == "map" else "map")
		return
	if mode != "play": return
	if event.is_action_pressed("vehicle"): toggle_vehicle()
	if event.is_action_pressed("interact"): missions.interact()
	if event.is_action_pressed("radio"):
		radio_on = not radio_on; sound("radio_static",.45); save_settings()
	if event.is_action_pressed("camera"): camera_distance = 9 if camera_distance < 8 else 5.8

func set_mode(value: String) -> void:
	mode = value
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if value == "play" and not verification_started and get_window().has_focus() else Input.MOUSE_MODE_VISIBLE

func restore_mouse() -> void:
	if mode == "play" and not verification_started: Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func release_mouse() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if mode == "play" and not verification_started:
		hud.choice = 0; set_mode("pause")

func menu_confirm() -> void:
	sound("ui",.4)
	if hud.settings:
		if hud.choice == 4: hud.settings = false; hud.choice = 0; save_settings()
		else: change_setting(1)
		return
	if mode == "menu":
		match hud.choice:
			0: start_game(false)
			1: start_game(true)
			2: hud.settings = true; hud.choice = 0
			3: get_tree().quit()
	elif mode == "pause":
		match hud.choice:
			0: set_mode("play")
			1: set_mode("map")
			2: retry_mission()
			3: hud.settings = true; hud.choice = 0
			4: save_game(); hud.choice = 0; set_mode("menu")

func change_setting(direction: int) -> void:
	match hud.choice:
		0: radio_on = not radio_on
		1: shake_on = not shake_on
		2: mouse_sensitivity = clampf(mouse_sensitivity+direction*.2,.4,2)
		3: volume = clampf(volume+direction*.1,0,1)
	save_settings()

func start_game(continue_save: bool) -> void:
	if continue_save:
		if not FileAccess.file_exists(SAVE_PATH): hud.message("Збереження ще нема. Почни нову гру.",3); return
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(SAVE_PATH))
		if not parsed is Dictionary or not parsed.has("mission"):
			hud.message("Збереження пошкоджено. Доступна нова гра.",4); return
		missions.index = clampi(int(parsed.get("mission",0)),0,missions.missions.size())
		money = int(parsed.get("money",350))
	else:
		missions.index = 0; money = 350; missions.checkpoint_money = 350
	if not verification_started: hud.start_loading()
	reset_city_actors()
	missions.completed = false
	missions.checkpoint_money = money
	missions.retry()
	set_mode("play")
	hud.notice_time = 0
	hud.banner("КОРОСТИШІВ. МОЯ ЧЕРГА.",4)
	update_camera(1)

func reset_city_actors() -> void:
	clear_wanted()
	player.vehicle = null; player.visible = true; player.collision_layer = 4
	for car in cars:
		if is_instance_valid(car): car.queue_free()
	for person in people:
		if is_instance_valid(person): person.queue_free()
	cars.clear(); people.clear(); givers.clear(); missions.enemies.clear()
	starter_car = spawn_car(starter_spot(),"sedan",false)
	starter_car.rotation.y = city.locations["start"]["car_heading"]
	populate_city()

func retry_mission() -> void:
	missions.retry(); set_mode("play"); hud.pass_time = 0

func actor_position() -> Vector3:
	return player.vehicle.global_position if player.vehicle else player.global_position

func update_camera(delta: float) -> void:
	if not camera or not player: return
	var target := actor_position()+Vector3(0,1.35,0)
	if mode == "menu":
		var at := player.global_position
		camera.global_position = at+Vector3(5.9+sin(menu_time*.08)*1.2,3.0,6.0)
		camera.look_at(at+Vector3(-2,1.15,0),Vector3.UP)
		return
	if player.vehicle:
		if absf(player.vehicle.speed)>1 and not Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
			camera_yaw = lerp_angle(camera_yaw,player.vehicle.rotation.y,delta*1.6)
		target.y = player.vehicle.global_position.y+1.15
	var distance := camera_distance+2.0 if player.vehicle else camera_distance
	var offset := Vector3(0,1.65-camera_pitch*4,distance).rotated(Vector3.UP,camera_yaw)
	var desired := target+offset
	var ignore: Array[RID] = [player.get_rid()]
	if player.vehicle: ignore.append(player.vehicle.get_rid())
	var query := PhysicsRayQueryParameters3D.create(target,desired,1,ignore)
	var result := world.get_world_3d().direct_space_state.intersect_ray(query)
	if not result.is_empty(): desired = result.position+result.normal*.3
	camera.global_position = camera.global_position.lerp(desired,minf(1,delta*12))
	if camera.global_position.distance_to(target)<.1: camera.global_position.z += .2
	camera.look_at(target,Vector3.UP)
	if camera_shake > 0 and shake_on:
		camera.h_offset = sin(menu_time*95)*camera_shake*.2
		camera.v_offset = cos(menu_time*80)*camera_shake*.2
	else: camera.h_offset = 0; camera.v_offset = 0
	if mode == "play":
		var stick := Vector2(Input.get_joy_axis(0,JOY_AXIS_RIGHT_X),Input.get_joy_axis(0,JOY_AXIS_RIGHT_Y))
		if stick.length()>.2:
			camera_yaw -= stick.x*delta*2
			camera_pitch = clampf(camera_pitch-stick.y*delta,-.65,.28)

func nearest_car() -> KVehicle:
	var best: KVehicle
	var dist := 4.0
	for car in cars:
		if not is_instance_valid(car) or car.driver or car.health <= 0: continue
		var d := player.global_position.distance_to(car.global_position)
		if d<dist: best = car; dist = d
	return best

func toggle_vehicle() -> void:
	if player.vehicle: player.exit_car(); return
	var car := nearest_car()
	if car:
		if car.police: crime(2)
		if car.traffic: crime(1)
		player.enter_car(car)

func interaction_hint() -> String:
	if missions.near and not missions.completed:
		if not missions.active: return "E  Поговорити: "+missions.current().get("giver","Едік")
		match missions.step().get("type",""):
			"pickup": return "F  Вийти, потім E  Забрати" if player.vehicle else "E  Забрати предмет"
			"talk": return "E  Поговорити"
			"drive": return "Потрібна машина. F  Сісти" if not player.vehicle else "Їдь у жовтий маркер"
			"combat": return "ЛКМ  Молоток. Тримай дистанцію."
	if not player.vehicle and nearest_car(): return "F  Сісти в машину"
	return ""

func perform_attack() -> void:
	sound("swing",.65)
	var best: KPerson
	var nearest := 2.7
	for person in people:
		if not is_instance_valid(person) or not person.alive: continue
		var direction := person.global_position-player.global_position
		if direction.length()<nearest and (-player.global_basis.z).dot(direction.normalized()) > -.15:
			var ray := PhysicsRayQueryParameters3D.create(player.global_position+Vector3(0,1,0),person.global_position+Vector3(0,1,0),1)
			if world.get_world_3d().direct_space_state.intersect_ray(ray).is_empty():
				best = person; nearest = direction.length()
	if best:
		var aim := best.global_position-player.global_position
		player.rotation.y = atan2(-aim.x,-aim.z)
		best.hit(40,player.global_position)
		camera_shake = .16
	else:
		for car in cars:
			if is_instance_valid(car) and player.global_position.distance_to(car.global_position)<2.7:
				car.health = maxf(0,car.health-12)
				sound("impact",.7); camera_shake = .12
				crime(2 if car.police else 1)
				break

func crime(level: int) -> void:
	wanted = clampi(maxi(wanted+1 if wanted>0 and crime_cooldown<=0 else wanted,level),1,6)
	crime_cooldown = 3
	wanted_timer = 12
	while police_cars.size() < mini(wanted,3):
		var at := actor_position()
		var offset := 65.0+police_cars.size()*19
		var spawn: Vector3 = city.nearest_road(at+Vector3(0,0,offset if police_cars.size()%2==0 else -offset))+Vector3(0,.3,0)
		var cop := spawn_car(spawn,"police_sedan",false)
		cop.rotation.y = 0
		police_cars.append(cop)

func police_near(radius: float = 32) -> bool:
	for cop in police_cars:
		if not is_instance_valid(cop) or cop.driver == player or cop.health<=0 or cop.global_position.distance_to(actor_position())>radius: continue
		var query := PhysicsRayQueryParameters3D.create(cop.global_position+Vector3(0,1,0),actor_position()+Vector3(0,1,0),1)
		if world.get_world_3d().direct_space_state.intersect_ray(query).is_empty(): return true
	return false

func clear_wanted() -> void:
	wanted = 0; wanted_timer = 0; crime_cooldown = 0
	for cop in police_cars:
		if is_instance_valid(cop) and cop.driver == player:
			cop.police = false
			if cop.red_light: cop.red_light.visible = false; cop.blue_light.visible = false
			continue
		cars.erase(cop)
		if is_instance_valid(cop): cop.queue_free()
	police_cars.clear()

func open_dialogue(title: String,speaker: String,lines: Array,callback: Callable) -> void:
	dialogue_title = title; dialogue_speaker = speaker; dialogue_lines = lines; dialogue_index = 0; dialogue_callback = callback
	player.play_animation("idle")
	set_mode("dialogue")

func finish_dialogue() -> void:
	set_mode("play")
	if dialogue_callback.is_valid(): dialogue_callback.call()
	dialogue_callback = Callable()

func fail_mission(title: String,reason: String) -> void:
	fail_title = title; fail_reason = reason; sound("fail",.85); set_mode("failed")

func save_game() -> void:
	var file := FileAccess.open(SAVE_PATH,FileAccess.WRITE)
	if file: file.store_string(JSON.stringify({"version":1,"mission":missions.index,"money":money}))
	else: hud.message("Не вдалося записати прогрес. Перевір доступ до user://.",4)

func save_settings() -> void:
	var file := FileAccess.open(SETTINGS_PATH,FileAccess.WRITE)
	if file: file.store_string(JSON.stringify({"volume":volume,"radio":radio_on,"shake":shake_on,"mouse":mouse_sensitivity}))

func load_settings() -> void:
	if not FileAccess.file_exists(SETTINGS_PATH): return
	var settings_data = JSON.parse_string(FileAccess.get_file_as_string(SETTINGS_PATH))
	if settings_data is Dictionary:
		volume = clampf(float(settings_data.get("volume",.7)),0,1)
		radio_on = settings_data.get("radio",true); shake_on = settings_data.get("shake",true)
		mouse_sensitivity = clampf(float(settings_data.get("mouse",1)),.4,2)

func setup_audio() -> void:
	if DisplayServer.get_name() == "headless": return
	for i in 10:
		var audio := AudioStreamPlayer.new(); add_child(audio); sfx.append(audio)
	radio = loop_audio("radio",.25)
	engine_audio = loop_audio("engine",.1)
	siren_audio = loop_audio("siren",.1)
	ambience = loop_audio("ambience",.1)
	for label in ["river","birds","wind"]:
		nature_audio.append(loop_audio(label,0.001))

func loop_audio(label: String,loudness: float) -> AudioStreamPlayer:
	var audio := AudioStreamPlayer.new(); add_child(audio)
	var path := "res://assets/audio/%s.wav" % label
	if ResourceLoader.exists(path):
		var stream: AudioStreamWAV = load(path).duplicate()
		stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
		stream.loop_begin = 0; stream.loop_end = int(stream.get_length()*stream.mix_rate)
		audio.stream = stream; audio.volume_db = linear_to_db(loudness); audio.play()
	return audio

func sound(label: String,loudness: float = 1) -> void:
	if sfx.is_empty(): return
	var path := "res://assets/audio/%s.wav" % label
	if not ResourceLoader.exists(path): return
	var audio := sfx[sfx_index%sfx.size()]; sfx_index += 1
	audio.stream = load(path); audio.volume_db = linear_to_db(maxf(.001,loudness*volume*.7)); audio.play()

func footstep() -> void:
	footstep_index += 1
	var pos := player.global_position
	var gravel: bool = city.get_district(pos) in ["КАР’ЄР І ТЕТЕРІВ","ЛІС НАД ТЕТЕРЕВОМ","ПРИВАТНИЙ СЕКТОР","ЗАРІЧЧЯ","ОКОЛИЦІ","ГАРАЖІ"]
	var labels := ["step_gravel","step_gravel_2"] if gravel else ["step","step_concrete_2"]
	sound(labels[footstep_index%2],.34)

func _exit_tree() -> void:
	for audio in [radio,engine_audio,siren_audio,ambience]+nature_audio:
		if is_instance_valid(audio): audio.stop(); audio.stream = null
	for audio in sfx:
		if is_instance_valid(audio): audio.stop(); audio.stream = null

func capture(label: String) -> void:
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(evidence_dir)
	var status := get_viewport().get_texture().get_image().save_png(evidence_dir+"/"+label+".png")
	expect(status==OK,"screenshot saved: "+label)

func expect(condition: bool,label: String) -> void:
	if not condition:
		push_error("REPLAY_FAIL "+label)
		get_tree().quit(1)

func run_verification() -> void:
	verification_started = true
	await get_tree().create_timer(1.0).timeout
	await capture("01-menu")
	start_game(false)
	await get_tree().create_timer(.8).timeout
	await capture("02-street")
	var start := player.global_position
	Input.action_press("forward")
	await get_tree().create_timer(.65).timeout
	Input.action_release("forward")
	expect(player.global_position.distance_to(start)>1,"walking input must move Podro")
	print("REPLAY PASS walking ",player.global_position.distance_to(start))
	player.global_position = starter_car.global_position+Vector3(-1.7,.3,0)
	toggle_vehicle()
	expect(player.vehicle==starter_car,"F enters nearest car")
	var car_start := starter_car.global_position
	Input.action_press("forward")
	await get_tree().create_timer(1.7).timeout
	Input.action_release("forward")
	expect(starter_car.global_position.distance_to(car_start)>5,"throttle must drive car")
	print("REPLAY PASS vehicle ",starter_car.global_position.distance_to(car_start))
	await capture("03-driving")
	starter_car.speed = 0; toggle_vehicle()
	expect(player.vehicle==null,"F exits stopped car")
	set_mode("map"); await capture("04-map"); set_mode("play")
	player.global_position = missions.target+Vector3(0,.3,0)
	await get_tree().process_frame
	missions.near = true; missions.interact()
	expect(mode=="dialogue","E opens mission dialogue")
	await capture("05-dialogue")
	finish_dialogue()
	expect(missions.active,"dialogue starts mission")
	print("REPLAY PASS mission accepted")
	var initial_money := money
	var guard := 0
	while missions.index < missions.missions.size() and guard < 80:
		guard += 1
		if not missions.active:
			player.global_position = missions.target+Vector3(0,.3,0)
			missions.near = true; missions.interact(); finish_dialogue()
		var data := missions.step()
		var type: String = data.get("type","")
		if type in ["pickup","talk"]:
			if player.vehicle: player.vehicle.speed = 0; player.exit_car()
			player.global_position = missions.target+Vector3(0,.3,0)
			missions.near = true; missions.interact()
			if mode == "dialogue": finish_dialogue()
		elif type == "drive":
			if not player.vehicle:
				starter_car.global_position = player.global_position+Vector3(1.7,0,0); player.enter_car(starter_car)
			starter_car.speed = 0; starter_car.global_position = missions.target+Vector3(0,.3,0)
		elif type == "combat":
			if player.vehicle: player.vehicle.speed=0; player.exit_car()
			for enemy in missions.enemies:
				if not is_instance_valid(enemy) or not enemy.alive: continue
				enemy.set_physics_process(false)
				player.global_position = enemy.global_position+Vector3(0,0,1.4)
				player.rotation.y = 0
				perform_attack(); perform_attack()
				expect(not enemy.alive,"hammer hits must defeat enemy")
			print("REPLAY PASS hammer combat")
		elif type == "escape":
			var far := Vector3(city.playable_bounds.end.x-90,0,city.playable_bounds.end.y-90)
			player.global_position = Vector3(far.x,city.ground_height(far.x,far.z)+.3,far.z)
			if player.vehicle: player.vehicle.global_position = player.global_position
			for cop in police_cars: cop.set_physics_process(false)
			wanted_timer = .1
			await get_tree().create_timer(.4).timeout
			expect(wanted<2,"unseen wanted level must decay")
			clear_wanted()
			if player.vehicle: player.vehicle.global_position = missions.target+Vector3(0,.3,0)
			else: player.global_position = missions.target+Vector3(0,.3,0)
		await get_tree().create_timer(.12).timeout
	expect(missions.completed,"all four missions must finish")
	expect(money>initial_money,"missions grant rewards")
	await capture("06-passed")
	print("REPLAY PASS campaign missions=",missions.index," money=",money)
	player.health = 100; player.invulnerable = 0; player.damage(110)
	expect(mode=="failed","damage failure state")
	await capture("07-failure")
	var reward_money := money
	retry_mission(); expect(mode=="play" and player.health==100,"retry restores player")
	expect(money==reward_money,"retry preserves final reward")
	set_mode("pause"); hud.choice=3; menu_confirm(); expect(hud.settings,"settings opens")
	var old_radio := radio_on; hud.choice=0; menu_confirm(); expect(radio_on!=old_radio,"radio toggles")
	hud.choice=4; menu_confirm(); set_mode("play")
	save_game(); expect(FileAccess.file_exists(SAVE_PATH),"save written")
	var window_size := DisplayServer.window_get_size()
	DisplayServer.window_set_size(Vector2i(960,540))
	await get_tree().create_timer(.3).timeout
	await capture("08-small-window")
	DisplayServer.window_set_size(window_size)
	print("REPLAY PASS failure retry pause settings save")
	if not frame_samples.is_empty():
		var total := 0.0
		for frame_delta in frame_samples: total += frame_delta
		frame_samples.sort()
		print("FRAME_SAMPLE avg_fps=",snappedf(frame_samples.size()/total,.1)," p95_ms=",snappedf(frame_samples[int(frame_samples.size()*.95)]*1000,.1)," samples=",frame_samples.size())
	print("VERIFICATION_COMPLETE")
	get_tree().quit()

func run_tour() -> void:
	verification_started = true
	start_game(false)
	await get_tree().create_timer(2).timeout
	await capture("tour-start")
	player.global_position = city.location("plaza")+Vector3(0,.3,0); camera_yaw = -.7; update_camera(1)
	await get_tree().create_timer(1).timeout
	await capture("tour-square")
	player.global_position = city.location("quarry")+Vector3(0,.3,0); camera_yaw = -PI/2; update_camera(1)
	await get_tree().create_timer(1).timeout
	await capture("tour-quarry")
	player.global_position = city.location("market")+Vector3(0,.3,0); camera_yaw = .4; update_camera(1)
	await get_tree().create_timer(1).timeout
	await capture("tour-market")
	get_tree().quit()

func starter_spot() -> Vector3:
	return city.locations["start"]["car"]+Vector3(0,.4,0)
