extends SceneTree

const OUTPUT := "res://artifacts/validation/driving-route"
var game
var started_at := 0
var distance_driven := 0.0
var previous := Vector3.ZERO

func _initialize() -> void:
	call_deferred("run")

func reset_inputs() -> void:
	for action in ["forward", "back", "left", "right", "jump"]:
		Input.action_release(action)

func capture(label: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(OUTPUT)
	root.get_texture().get_image().save_png(OUTPUT + "/" + label + ".png")

func run() -> void:
	game = load("res://scenes/main.tscn").instantiate()
	game.verification_started = true
	root.add_child(game)
	await process_frame
	await physics_frame
	game.start_game(false)
	game.player.global_position = game.city.location("cafe") + Vector3(0, .3, 0)
	await physics_frame
	game.missions.near = true
	game.missions.interact()
	assert(game.mode == "dialogue", "First mission must open at cafe.")
	game.finish_dialogue()
	assert(game.missions.active and game.missions.step().type == "drive", "First objective must require driving.")
	game.starter_car.global_position = game.starter_spot()
	game.starter_car.rotation.y = game.city.locations["start"]["car_heading"]
	game.player.enter_car(game.starter_car)
	game.camera_yaw = 0
	game.update_camera(1)
	await create_timer(.35).timeout
	await capture("01-cafe-departure")
	previous = game.starter_car.global_position
	started_at = Time.get_ticks_msec()
	# The real streets from the cafe to the garage co-op.
	var waypoints: Array[Vector3] = game.city.road_route(game.starter_car.global_position, game.city.locations["garages"]["car"])
	waypoints.remove_at(0)
	for i in waypoints.size():
		var waypoint := waypoints[i]
		var radius := 2.1 if i == waypoints.size() - 1 else 3.5
		while true:
			await physics_frame
			var car = game.starter_car
			distance_driven += car.global_position.distance_to(previous)
			previous = car.global_position
			var direction: Vector3 = waypoint - car.global_position
			direction.y = 0
			if direction.length() < radius:
				print("DRIVING_ROUTE waypoint=", i + 1, " position=", car.global_position, " speed=", car.speed, " health=", car.health)
				break
			if game.mode != "play" or Time.get_ticks_msec() - started_at > 90000:
				reset_inputs()
				await capture("failure")
				push_error("Continuous driving route failed: mode=%s waypoint=%d position=%s" % [game.mode, i + 1, car.global_position])
				quit(1)
				return
			var desired := atan2(-direction.x, -direction.z)
			var error := angle_difference(car.rotation.y, desired)
			var steer := clampf(error * 2.8, -1, 1)
			var target_speed := 10.0 if absf(error) < .22 and direction.length() > 12 else 5.0
			if i == waypoints.size() - 1 and direction.length() < 9:
				target_speed = 3.8
			reset_inputs()
			Input.action_press("left" if steer > 0 else "right", absf(steer))
			if car.speed < target_speed - .25:
				Input.action_press("forward")
			elif car.speed > target_speed + .6:
				Input.action_press("jump")
		if i == 2:
			await capture("02-crossroads")
	reset_inputs()
	Input.action_press("jump")
	while absf(game.starter_car.speed) > .15:
		await physics_frame
	reset_inputs()
	await create_timer(.3).timeout
	assert(game.missions.step().type == "pickup", "Continuous driving must reach the garage objective.")
	assert(game.player.exit_car(), "Car must provide a free exit at garage.")
	await physics_frame
	await create_timer(.15).timeout
	await capture("03-garage-pickup")
	assert(game.missions.near, "Exit position must be within pickup radius.")
	game.missions.interact()
	assert(game.missions.step_index == 2 and game.missions.step().type == "drive", "E must collect the box and advance to market.")
	await create_timer(.2).timeout
	await capture("04-box-collected")
	print("CONTINUOUS_DRIVING_PASS distance=", distance_driven, " elapsed_seconds=", (Time.get_ticks_msec() - started_at) / 1000.0, " car_health=", game.starter_car.health, " objective_step=", game.missions.step_index)
	quit()
