extends SceneTree

var game
var checks := 0

func _initialize() -> void:
	call_deferred("run")

func check(value: bool, label: String) -> void:
	if not value:
		push_error("EDGE_CASE_FAIL " + label)
		quit(1)
		assert(value, label)
	checks += 1
	print("EDGE_CASE_PASS ", label)

func run() -> void:
	check(OS.get_environment("XDG_DATA_HOME").begins_with("/tmp/"), "Use isolated temporary user data for save tests.")
	game = load("res://scenes/main.tscn").instantiate()
	root.add_child(game)
	await process_frame
	await physics_frame
	game.start_game(false)
	game.set_mode("pause")
	var space = game.world.get_world_3d().direct_space_state
	var capsule := CapsuleShape3D.new()
	capsule.radius = .32
	capsule.height = 1.65
	var visited := {}
	for mission in game.missions.missions:
		for coord in [mission.start] + mission.steps.map(func(s): return s.position):
			var key := str(coord)
			if visited.has(key):
				continue
			visited[key] = true
			var query := PhysicsShapeQueryParameters3D.new()
			query.shape = capsule
			query.transform = Transform3D(Basis(), game.missions.place(coord) + Vector3(0, 1.15, 0))
			query.collision_mask = 1
			check(space.intersect_shape(query).is_empty(), "Mission location clear " + key)
		var title_width: float = game.hud.head.get_string_size(mission.title, HORIZONTAL_ALIGNMENT_LEFT, -1, 40).x
		check(title_width <= 1150, "Title fits dialogue " + mission.id)
		for line in mission.intro:
			check(game.hud.wrap_text(line, 1130, 30).size() <= 4, "Dialogue fits " + mission.id)
	game.set_mode("play")
	game.missions.start_mission()
	game.player.global_position = game.missions.target + Vector3(0, .3, 0)
	game.missions._process(.016)
	check(game.missions.step_index == 0, "Drive objective rejects arriving on foot.")
	game.starter_car.global_position = game.city.location("garages") + Vector3(0, .3, 0)
	game.player.enter_car(game.starter_car)
	game.missions._process(.016)
	check(game.missions.step_index == 1, "Drive objective accepts player vehicle.")
	game.missions.near = true
	game.missions.interact()
	check(game.missions.step_index == 1, "Pickup rejects collection from inside car.")
	check(game.player.exit_car(), "Garage permits safe car exit.")
	game.missions.near = true
	game.missions.interact()
	check(game.missions.step_index == 2, "Pickup advances after exit.")
	game.missions.step_index = 3
	game.missions.advance()
	check(game.money == 700 and game.missions.index == 1, "Mission reward delivered.")
	game.retry_mission()
	check(game.money == 700 and game.missions.index == 1, "Retry between missions preserves earned reward.")
	var saved = JSON.parse_string(FileAccess.get_file_as_string(game.SAVE_PATH))
	check(saved is Dictionary and saved.money == 700 and saved.mission == 1, "Completed mission reward saved.")
	game.start_game(false)
	game.crime(1)
	var cop = game.police_cars[0]
	cop.global_position = Vector3(0, .3, 0)
	game.player.enter_car(cop)
	check(not game.police_near(), "Stolen police vehicle cannot report its own driver.")
	game.wanted_timer = .02
	game._process(.05)
	check(game.wanted == 0, "Wanted level decays while driving stolen police vehicle.")
	await process_frame
	check(is_instance_valid(cop) and game.player.vehicle == cop, "Clearing wanted preserves occupied stolen vehicle.")
	check(not cop.police and game.police_cars.is_empty(), "Stolen vehicle leaves police tracking group.")
	cop.speed = 0
	check(game.player.exit_car() and game.player.visible and game.player.collision_layer == 4, "Driver exits retained police vehicle visibly.")
	game.start_game(false)
	var river: Vector3 = game.city.river_points[game.city.river_points.size() / 2]
	game.starter_car.global_position = river + Vector3(0, .3, 0)
	game.player.enter_car(game.starter_car)
	await create_timer(1.6).timeout
	check(game.mode == "failed" and game.fail_title == "ЖИГУЛЬ У ТЕТЕРЕВІ", "River fall reaches recoverable failure state.")
	game.retry_mission()
	check(game.mode == "play" and game.player.vehicle == null and game.player.health == 100, "Retry restores player after river fall.")
	check(game.starter_car.global_position.distance_to(game.starter_spot()) < .1 and game.starter_car.health == 100, "Retry restores starter vehicle after river fall.")
	game.missions.index = 3
	game.missions.active = true
	game.missions.step_index = 3
	game.missions.update_objective()
	game.starter_car.global_position = game.missions.target + Vector3(0, .3, 0)
	game.player.enter_car(game.starter_car)
	game.missions._process(.016)
	check(game.wanted == 2 and not game.missions.completed, "Escape rejects shelter arrival with active wanted level.")
	game.clear_wanted()
	game.missions._process(.016)
	check(game.missions.completed and game.missions.index == 4, "Escape completes only after wanted level clears.")
	var ending_money: int = game.money
	game.retry_mission()
	check(game.money == ending_money and game.missions.completed, "Freeplay retry preserves final mission reward.")
	print("EDGE_CASES_COMPLETE checks=", checks)
	game.queue_free()
	await process_frame
	await process_frame
	quit()
