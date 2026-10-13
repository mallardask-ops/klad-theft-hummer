extends CharacterBody3D
class_name KPlayer

var game
var model: Node3D
var animator: AnimationPlayer
var health := 100.0
var attack_time := 0.0
var invulnerable := 0.0
var animation_name := ""
var footstep_time := 0.0
var enabled := true
var vehicle
# Clips that repeat; the rest (attack, hit, death, jumps, pickup ...) play once.
const LOOPED_CLIPS := ["idle", "walk", "run", "stroll", "drive", "talk", "jump_air"]
# Ground speed each locomotion clip was animated for, so feet don't skate.
const CLIP_SPEED := {"walk": 3.4, "run": 6.2, "stroll": 1.4}

func _ready() -> void:
	collision_layer = 4
	collision_mask = 3
	floor_snap_length = 0.45
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.32
	capsule.height = 1.65
	shape.shape = capsule
	shape.position.y = 0.85
	add_child(shape)
	if ResourceLoader.exists("res://assets/models/podro.glb"):
		model = load("res://assets/models/podro.glb").instantiate()
		add_child(model)
		animator = model.find_child("AnimationPlayer",true,false) as AnimationPlayer
		if animator:
			for clip in animator.get_animation_list():
				var looped := String(clip) in LOOPED_CLIPS
				animator.get_animation(clip).loop_mode = Animation.LOOP_LINEAR if looped else Animation.LOOP_NONE
	else:
		model = Node3D.new()
		add_child(model)
		var mesh := MeshInstance3D.new()
		var body := CapsuleMesh.new()
		body.height = 1.65
		body.radius = 0.37
		mesh.mesh = body
		mesh.position.y = .85
		model.add_child(mesh)
	print("PLAYER_ANIMATIONS ",animator.get_animation_list() if animator else [])
	KLighting.blob_shadow(self,Vector2(1.2,1.2),.6)

func _physics_process(delta: float) -> void:
	if game and game.city and global_position.y < game.city.ground_height(global_position.x,global_position.z)-1.2 and not game.city.is_underwater(global_position):
		global_position.y = game.city.ground_height(global_position.x,global_position.z)+.3; velocity = Vector3.ZERO
	if not enabled or game.mode != "play":
		return
	invulnerable = maxf(0,invulnerable-delta)
	if vehicle:
		global_position = vehicle.global_position
		return
	attack_time = maxf(0,attack_time-delta)
	var input := Input.get_vector("left","right","forward","back")
	var move := Vector3(input.x,0,input.y).rotated(Vector3.UP,game.camera_yaw)
	var speed := 6.6 if Input.is_action_pressed("sprint") else 3.8
	if attack_time > 0:
		speed *= 0.22
	velocity.x = move_toward(velocity.x,move.x*speed,delta*24)
	velocity.z = move_toward(velocity.z,move.z*speed,delta*24)
	if not is_on_floor():
		velocity.y -= 22*delta
	elif Input.is_action_just_pressed("jump") and attack_time <= 0:
		velocity.y = 7.0
	else:
		velocity.y = -0.5
	if move.length() > .1 and attack_time <= 0:
		rotation.y = lerp_angle(rotation.y,atan2(-move.x,-move.z),delta*14)
	move_and_slide()
	if Input.is_action_pressed("attack") and attack_time <= 0:
		attack_time = .65
		play_animation("attack",2.0)
		game.perform_attack()
	if attack_time <= 0:
		var gait := "run" if move.length() > .1 and speed > 4 else ("walk" if move.length() > .1 else "idle")
		var ground := Vector2(velocity.x,velocity.z).length()
		play_animation(gait, clampf(ground/CLIP_SPEED[gait],.6,1.5) if CLIP_SPEED.has(gait) else 1.0)
	if move.length() > .1 and is_on_floor():
		footstep_time -= delta
		if footstep_time <= 0:
			game.footstep()
			footstep_time = .27 if speed > 4 else .43
	global_position.x = clampf(global_position.x,game.city.playable_bounds.position.x,game.city.playable_bounds.end.x)
	global_position.z = clampf(global_position.z,game.city.playable_bounds.position.y,game.city.playable_bounds.end.y)
	if game.city.is_underwater(global_position+Vector3(0,1.2,0)) or global_position.y < -40:
		damage(120)

func play_animation(wanted: String, speed: float = 1.0) -> void:
	if not animator:
		return
	var found := ""
	for clip in animator.get_animation_list():
		if String(clip).to_lower().ends_with(wanted):
			found = clip
			break
	if found.is_empty():
		return
	if animation_name != found:
		animation_name = found
		animator.play(found,.12)
	animator.speed_scale = speed

func damage(amount: float) -> void:
	if invulnerable > 0 or game.mode != "play":
		return
	health = maxf(0,health-amount)
	invulnerable = .7
	game.hud.damage_flash = .32
	game.sound("hurt",.7)
	if health <= 0:
		game.fail_mission("ПОДРО ВІДКЛЮЧИВСЯ", "Молоток переживе. Подро теж, після повтору.")

func enter_car(car) -> void:
	vehicle = car
	car.driver = self
	car.traffic = false
	visible = false
	collision_layer = 0
	game.camera_yaw = car.rotation.y
	game.sound("door",.8)
	if absf(car.speed) < .5: game.sound("engine_start",.45)
	game.hud.banner(car.car_name,2.5)

func exit_car() -> bool:
	if not vehicle:
		return false
	var car = vehicle
	if absf(car.speed) > 4:
		game.hud.message("Спочатку загальмуй. Подро один.",2)
		return false
	var offsets := [Vector3(-1.8,0,0),Vector3(1.8,0,0),Vector3(0,0,3.2)]
	for offset in offsets:
		var spot: Vector3 = car.global_position + car.global_basis * offset
		var query := PhysicsShapeQueryParameters3D.new()
		var sphere := SphereShape3D.new()
		sphere.radius = .4
		query.shape = sphere
		query.transform = Transform3D(Basis(),spot+Vector3(0,.9,0))
		query.collision_mask = 3
		query.exclude = [car.get_rid()]
		if get_world_3d().direct_space_state.intersect_shape(query).is_empty():
			car.driver = null
			vehicle = null
			global_position = spot + Vector3(0,.3,0)
			visible = true
			collision_layer = 4
			game.sound("door",.8)
			return true
	game.hud.message("Двері затиснуло. Від'їдь від стіни.",2)
	return false
