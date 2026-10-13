extends SceneTree

const OUTPUT := "res://artifacts/validation/world-replay"
var game
var run_id := ""
var checks := 0
var stopped := false
var evidence: Dictionary = {"screenshots": [], "tour": [], "walk_samples": []}
var tour_stops: Array[Dictionary] = []
var slope_route: Array[Vector3] = []

func _initialize() -> void:
	call_deferred("run")

func reset_inputs() -> void:
	for action in ["forward", "back", "left", "right", "sprint", "jump", "attack"]:
		Input.action_release(action)

func log_line(message: String) -> void:
	print(message)
	var path := OUTPUT + "/" + run_id + "-events.log"
	var file := FileAccess.open(path, FileAccess.READ_WRITE)
	if not file:
		file = FileAccess.open(path, FileAccess.WRITE)
	if file:
		file.seek_end()
		file.store_line(message)

func check(condition: bool, label: String) -> bool:
	checks += 1
	if condition:
		return true
	log_line("WORLD_REPLAY_FAIL " + label)
	evidence["failure"] = label
	stopped = true
	reset_inputs()
	return false

func save_report(success: bool) -> void:
	evidence["result"] = "PASS" if success else "FAIL"
	evidence["checks"] = checks
	evidence["run_id"] = run_id
	var file := FileAccess.open(OUTPUT + "/" + run_id + "-report.json", FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(evidence, "\t"))
	var latest := FileAccess.open(OUTPUT + "/latest-run.txt", FileAccess.WRITE)
	if latest:
		latest.store_string(run_id + "\n")

func capture(label: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	var path := OUTPUT + "/" + run_id + "-" + label + ".png"
	var status := root.get_texture().get_image().save_png(path)
	if check(status == OK, "Screenshot saved: " + label):
		evidence["screenshots"].append(path)

func position_fixture(at: Vector3) -> bool:
	reset_inputs()
	game.player.enabled = true
	game.player.vehicle = null
	game.player.visible = true
	game.player.collision_layer = 4
	game.player.global_position = at
	game.player.velocity = Vector3.ZERO
	var deadline := Time.get_ticks_msec() + 3500
	while not game.player.is_on_floor() or game.player.global_position.distance_to(at) < 0.001:
		await physics_frame
		if game.mode != "play" or Time.get_ticks_msec() > deadline:
			return check(false, "Fixture did not settle on collision ground at %s; actor=%s mode=%s" % [at, game.player.global_position, game.mode])
	await physics_frame
	return check(game.player.is_on_floor(), "Fixture settled at " + str(at))

func support_below() -> Dictionary:
	var pos: Vector3 = game.player.global_position
	var query := PhysicsRayQueryParameters3D.create(pos + Vector3(0, 0.15, 0), pos - Vector3(0, 2.0, 0), 1, [game.player.get_rid()])
	return game.world.get_world_3d().direct_space_state.intersect_ray(query)

func run() -> void:
	run_id = Time.get_datetime_string_from_system().replace(":", "-")
	DirAccess.make_dir_recursive_absolute(OUTPUT)
	if not check(OS.get_environment("XDG_DATA_HOME").begins_with("/tmp/"), "Set XDG_DATA_HOME to an isolated /tmp directory before running."):
		save_report(false)
		quit(1)
		return
	var fixture_path := "res://tools/world_replay_fixtures.json"
	if not check(FileAccess.file_exists(fixture_path), "City-approved world tour fixture file exists."):
		save_report(false)
		quit(1)
		return
	var fixtures = JSON.parse_string(FileAccess.get_file_as_string(fixture_path))
	if not check(fixtures is Dictionary and fixtures.get("city_ready", false), "City agent confirmed map and fixture readiness."):
		save_report(false)
		quit(1)
		return
	for stop in fixtures["tour"]:
		tour_stops.append(stop)
	for point in fixtures["slope_route"]:
		slope_route.append(Vector3(point[0], 0, point[1]))
	game = load("res://scenes/main.tscn").instantiate()
	game.verification_started = true
	root.add_child(game)
	await process_frame
	await physics_frame
	game.start_game(false)
	game.hud.notice_time = 0
	game.hud.banner_time = 0
	game.shake_on = false
	var bounds: Rect2 = game.city.playable_bounds
	evidence["playable_bounds"] = [bounds.position.x, bounds.position.y, bounds.size.x, bounds.size.y]
	evidence["river_points"] = game.city.river_points.size()
	evidence["road_segments"] = game.city.road_segments.size()
	if not check(bounds.position.x < -230 and bounds.position.y < -230 and bounds.end.x > 230 and bounds.end.y > 230, "Terrain bounds extend beyond the old city boundary."):
		save_report(false)
		quit(1)
		return
	if not check(game.city.river_points.size() >= 20, "River has multiple landscape control points."):
		save_report(false)
		quit(1)
		return
	for stop in tour_stops:
		var point: Array = stop["player"]
		var x: float = float(point[0])
		var z: float = float(point[1])
		var height: float = game.city.ground_height(x, z)
		var settled: bool = await position_fixture(Vector3(x, height + 1.25, z))
		if not settled:
			await capture("failure-" + stop["id"])
			save_report(false)
			quit(1)
			return
		game.player.enabled = false
		game.set_process(false)
		var camera_position: Array = stop["camera"]
		var camera_target: Array = stop["look"]
		game.camera.global_position = Vector3(camera_position[0], camera_position[1], camera_position[2])
		game.camera.look_at(Vector3(camera_target[0], camera_target[1], camera_target[2]), Vector3.UP)
		game.camera.fov = float(stop.get("fov", 68))
		game.hud.banner(stop["label"], 3)
		await create_timer(0.25).timeout
		await capture(stop["id"])
		var actual: Vector3 = game.player.global_position
		var support := support_below()
		if not check(not support.is_empty(), "Tour actor has physical ground support at " + stop["id"]):
			save_report(false)
			quit(1)
			return
		var entry := {"id": stop["id"], "player": [actual.x, actual.y, actual.z], "ground_api": height, "district": game.city.get_district(actual)}
		evidence["tour"].append(entry)
		log_line("WORLD_TOUR " + JSON.stringify(entry))
		game.set_process(true)
	game.camera.fov = 68
	game.hud.banner_time = 0
	var walked: bool = await continuous_slope_walk()
	if not walked:
		await capture("failure-slope")
		save_report(false)
		quit(1)
		return
	await capture("08-slope-walk-finish")
	save_report(true)
	log_line("WORLD_REPLAY_COMPLETE checks=%d screenshots=%d walk_distance=%.2f elevation_range=%.2f" % [checks, evidence["screenshots"].size(), evidence["walk_distance"], evidence["walk_height_range"]])
	quit()

func continuous_slope_walk() -> bool:
	if not check(slope_route.size() >= 2, "Continuous slope route has at least two positions."):
		return false
	var first := slope_route[0]
	var fixture: bool = await position_fixture(Vector3(first.x, game.city.ground_height(first.x, first.z) + 1.25, first.z))
	if not fixture:
		return false
	game.camera_distance = 9
	game.camera_pitch = -0.35
	game.camera_yaw = 0
	game.update_camera(1)
	await capture("07-slope-walk-start")
	var started := Time.get_ticks_msec()
	var previous: Vector3 = game.player.global_position
	var min_y: float = previous.y
	var max_y: float = previous.y
	var distance := 0.0
	var frames := 0
	var floor_frames := 0
	var last_progress_at := started
	var progress_position := previous
	for i in range(1, slope_route.size()):
		var target := slope_route[i]
		while true:
			await physics_frame
			var at: Vector3 = game.player.global_position
			distance += at.distance_to(previous)
			previous = at
			min_y = minf(min_y, at.y)
			max_y = maxf(max_y, at.y)
			frames += 1
			if game.player.is_on_floor():
				floor_frames += 1
			var direction := target - at
			direction.y = 0
			if direction.length() < 1.0:
				log_line("WORLD_WALK_WAYPOINT i=%d actor=%s" % [i, at])
				break
			if not check(game.mode == "play" and at.is_finite() and at.y > -4, "Actor remains alive and finite during the continuous slope walk."):
				reset_inputs()
				return false
			if Time.get_ticks_msec() - started > 75000:
				return check(false, "Continuous slope walk timed out at %s targeting %s." % [at, target])
			if at.distance_to(progress_position) > 1.0:
				last_progress_at = Time.get_ticks_msec()
				progress_position = at
			elif Time.get_ticks_msec() - last_progress_at > 5000:
				return check(false, "Slope walk is obstructed or clamped at %s targeting %s." % [at, target])
			if frames % 30 == 0:
				var support := support_below()
				if not check(not support.is_empty(), "Collision support exists below the continuously walking actor."):
					return false
				var actual_ground: Vector3 = support["position"]
				if not check(absf(at.y - actual_ground.y) < 0.65, "Actor follows physical terrain height; actor=%s support=%s." % [at, actual_ground]):
					return false
				evidence["walk_samples"].append({"elapsed": (Time.get_ticks_msec() - started) / 1000.0, "position": [at.x, at.y, at.z], "api_height": game.city.ground_height(at.x, at.z), "collision_height": actual_ground.y, "on_floor": game.player.is_on_floor()})
			game.camera_yaw = atan2(-direction.x, -direction.z)
			reset_inputs()
			Input.action_press("forward")
	reset_inputs()
	await create_timer(0.2).timeout
	var finish: Vector3 = game.player.global_position
	evidence["walk_distance"] = distance
	evidence["walk_height_range"] = max_y - min_y
	evidence["walk_floor_fraction"] = float(floor_frames) / maxf(1, frames)
	evidence["walk_elapsed"] = (Time.get_ticks_msec() - started) / 1000.0
	evidence["walk_finish"] = [finish.x, finish.y, finish.z]
	return check(distance > 30, "Player physically walked over 30 metres without route teleports.") and check(max_y - min_y > 1.0, "Slope walk changes physical elevation by over one metre.") and check(maxf(absf(finish.x), absf(finish.z)) > 260, "Continuous walking reaches beyond the old ±230 boundary.") and check(float(floor_frames) / maxf(1, frames) > 0.85, "Actor remains grounded for most slope movement.")
