extends SceneTree

var game
var recorder := AudioEffectRecord.new()
var output := "res://artifacts/audio_refresh/validation/replay"
var phases: Array[Dictionary] = []

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--evidence-dir="): output = arg.trim_prefix("--evidence-dir=")
	call_deferred("run")

func check(condition: bool,label: String) -> void:
	if condition: print("AUDIO_REPLAY_PASS ",label)
	else:
		push_error("AUDIO_REPLAY_FAIL "+label)
		quit(1)

func begin() -> void:
	recorder.set_recording_active(true)

func finish(label: String) -> void:
	recorder.set_recording_active(false)
	var recording := recorder.get_recording()
	check(recording != null and recording.get_length() > .1,"mixed audio captured: "+label)
	var path := output+"/"+label+".wav"
	check(recording.save_to_wav(path) == OK,"audio saved: "+label)
	phases.append({"phase":label,"duration":recording.get_length(),"path":path})

func tap(action: String) -> void:
	var event := InputEventAction.new(); event.action = action; event.pressed = true
	Input.parse_input_event(event)
	await process_frame
	event = InputEventAction.new(); event.action = action; event.pressed = false
	Input.parse_input_event(event)

func run() -> void:
	check(DisplayServer.get_name() != "headless","graphical runtime with audio mixing")
	DirAccess.make_dir_recursive_absolute(output)
	game = load("res://scenes/main.tscn").instantiate()
	game.verification_started = true
	root.add_child(game)
	await create_timer(.7).timeout
	game.volume = 1.0
	await process_frame
	check(game.audio_streams.size() == 31,"all recorded streams loaded")
	check(game.radio.stream is AudioStreamOggVorbis and game.radio.stream.get_length() > 60,"full composed radio track")
	check(AudioServer.get_bus_index("Vehicle") >= 0 and AudioServer.get_bus_effect(0,0) is AudioEffectHardLimiter,"routed mix and limiter loaded")
	recorder.format = AudioStreamWAV.FORMAT_16_BITS
	AudioServer.add_bus_effect(0,recorder)
	begin()
	await tap("ui_down"); await create_timer(.25).timeout
	await tap("ui_up"); await create_timer(.25).timeout
	check(game.hud.choice == 0,"menu input selects and returns")
	await tap("ui_accept")
	check(game.mode == "play","menu confirmation starts game")
	await create_timer(.5).timeout
	finish("01-menu")
	begin()
	var start: Vector3 = game.player.global_position
	Input.action_press("forward")
	await create_timer(1.1).timeout
	Input.action_release("forward")
	check(game.player.global_position.distance_to(start) > 1,"walking moves and emits footsteps")
	await create_timer(.3).timeout
	finish("02-footsteps")
	begin()
	game.player.global_position = game.starter_car.global_position+Vector3(-1.7,.3,0)
	game.toggle_vehicle()
	check(game.player.vehicle == game.starter_car,"vehicle input enters starter sedan")
	await create_timer(1.6).timeout
	finish("03-door-and-idle")
	# A straight, empty test stretch avoids a parked car masking the brake sound.
	var route: Array[Vector3] = game.city.road_route(game.city.location("cafe"),game.city.location("garages"))
	var segment_start: Vector3 = route[0]
	var segment_end: Vector3 = route[1]
	var longest := 0.0
	for i in route.size()-1:
		var length := route[i].distance_to(route[i+1])
		if length > longest:
			longest = length; segment_start = route[i]; segment_end = route[i+1]
	var direction: Vector3 = (segment_end-segment_start).normalized()
	game.starter_car.global_position = segment_start+direction*longest*.25+Vector3(0,.4,0)
	game.starter_car.rotation.y = atan2(-direction.x,-direction.z)
	game.starter_car.speed = 0; game.starter_car.velocity = Vector3.ZERO
	for car in game.cars:
		if car != game.starter_car:
			car.set_physics_process(false); car.collision_layer = 0
	await create_timer(.4).timeout
	begin()
	var car_start: Vector3 = game.starter_car.global_position
	Input.action_press("forward")
	await create_timer(1.7).timeout
	Input.action_release("forward")
	check(game.starter_car.global_position.distance_to(car_start) > 5,"throttle drives the sedan")
	check(game.engine_load_audio.volume_linear > .05 and game.road_audio.volume_linear > .01,"engine load and road layers respond to driving")
	print("AUDIO_CAR_STATE acceleration speed=",game.starter_car.speed," health=",game.starter_car.health," position=",game.starter_car.global_position)
	await create_timer(.25).timeout
	finish("04-acceleration")
	begin()
	Input.action_press("jump")
	await create_timer(.10).timeout
	print("AUDIO_CAR_STATE braking speed=",game.starter_car.speed," skid=",game.starter_car.skid_amount," tire_gain=",game.tires_audio.volume_linear)
	check(game.tires_audio.volume_linear > .005,"handbrake produces a tire layer")
	await create_timer(.8).timeout
	Input.action_release("jump")
	check(absf(game.starter_car.speed) < .5,"handbrake stops the car")
	await create_timer(.3).timeout
	finish("05-braking")
	begin()
	game.sound("crash_light",.5)
	await create_timer(.8).timeout
	game.sound("crash",.9)
	await create_timer(1.2).timeout
	finish("06-collisions")
	check(game.player.exit_car(),"exit stopped sedan")
	begin()
	game.sound("impact",.8,game.player.global_position+Vector3(0,1,0))
	await create_timer(.45).timeout
	game.sound("hammer_metal",.7)
	await create_timer(.9).timeout
	finish("07-body-and-metal")
	var bus = game.spawn_car(game.starter_spot()+Vector3(5,0,0),"minibus",false)
	game.player.enter_car(bus)
	await create_timer(.4).timeout
	begin()
	check(game.audio_vehicle_kind == "diesel","minibus selects recorded diesel")
	await create_timer(1.5).timeout
	Input.action_press("forward")
	await create_timer(.65).timeout
	Input.action_release("forward")
	finish("08-diesel")
	begin()
	game.sound("mission_pass",.9)
	await create_timer(.15).timeout
	for i in 24: game.sound("impact",.8)
	check(game.cue_audio.playing,"mission result survives dense SFX playback")
	await create_timer(.45).timeout
	check(game.radio.volume_linear < .2,"mission jingle ducks the radio")
	await create_timer(4.0).timeout
	finish("09-mission-and-dense-mix")
	game.set_mode("pause")
	await create_timer(1.0).timeout
	begin(); await create_timer(.7).timeout; finish("10-pause")
	game.set_mode("play"); game.volume = 0
	await create_timer(.4).timeout
	check(AudioServer.is_bus_mute(game.volume_bus),"zero volume mutes every bus")
	begin(); game.sound("hurt",1.0)
	await create_timer(.7).timeout
	finish("11-muted")
	game.volume = .7; game.set_mode("play")
	await create_timer(.3).timeout
	bus.speed = 0
	game.player.exit_car()
	game.radio_on = false
	game.camera_yaw = 0
	var cop = game.spawn_car(game.player.global_position+Vector3(10,0,0),"police_sedan",false)
	cop.set_physics_process(false); game.police_cars.append(cop); game.wanted = 1
	begin(); await create_timer(1.6).timeout; finish("12-siren-right")
	game.set_mode("failed")
	await create_timer(.4).timeout
	begin(); game.sound("fail",.85)
	await create_timer(1.2).timeout; finish("13-failure")
	var file := FileAccess.open(output+"/phases.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(phases,"\t")); file.close()
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(output+"/runtime.png")
	AudioServer.remove_bus_effect(0,AudioServer.get_bus_effect_count(0)-1)
	recorder = null
	game.stop_audio()
	await create_timer(.2).timeout
	print("AUDIO_VERIFICATION_COMPLETE phases=",phases.size())
	quit()
