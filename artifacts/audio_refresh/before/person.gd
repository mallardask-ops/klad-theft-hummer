extends CharacterBody3D
class_name KPerson

var game
var model: Node3D
var animator: AnimationPlayer
var hostile := false
var mission_enemy := false
var alive := true
var health := 70.0
var home := Vector3.ZERO
var goal := Vector3.ZERO
var walk_end := Vector3.ZERO
var panic := 0.0
var strike_cooldown := 0.0
var path_axis := 0
var anim_name := ""
var model_name := "npc_worker"
var stationary := false

func _ready() -> void:
	collision_layer = 8
	collision_mask = 1
	floor_snap_length = .4
	var collider := CollisionShape3D.new()
	var shape := CapsuleShape3D.new()
	shape.height = 1.65
	shape.radius = .3
	collider.shape = shape
	collider.position.y = .85
	add_child(collider)
	var model_path := "res://assets/models/%s.glb" % model_name
	if not ResourceLoader.exists(model_path): model_path = "res://assets/models/npc_worker.glb"
	if ResourceLoader.exists(model_path):
		model = load(model_path).instantiate()
		add_child(model)
		animator = model.find_child("AnimationPlayer",true,false) as AnimationPlayer
		if animator:
			for clip in animator.get_animation_list():
				if String(clip) != "attack": animator.get_animation(clip).loop_mode = Animation.LOOP_LINEAR
	else:
		model = Node3D.new(); add_child(model)
		var mesh := MeshInstance3D.new()
		var capsule := CapsuleMesh.new(); capsule.height = 1.7; capsule.radius = .3
		mesh.mesh = capsule; mesh.position.y = .85; model.add_child(mesh)
	if hostile:
		var marker := MeshInstance3D.new()
		var sphere := SphereMesh.new(); sphere.radius = .1; sphere.height = .2
		marker.mesh = sphere; marker.position.y = 2
		var mat := StandardMaterial3D.new(); mat.albedo_color = Color(1,.14,.07); mat.shading_mode = 0
		marker.material_override = mat; add_child(marker)
	tune_visual(model)
	KLighting.blob_shadow(self,Vector2(1.2,1.2),.55)
	home = global_position
	if walk_end == Vector3.ZERO: walk_end = home + Vector3(0,0,14)
	goal = walk_end

func tune_visual(node: Node) -> void:
	if node is MeshInstance3D:
		node.visibility_range_end = 75
		node.visibility_range_end_margin = 5
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for child in node.get_children(): tune_visual(child)

func _physics_process(delta: float) -> void:
	if game and game.city and global_position.y < game.city.ground_height(global_position.x,global_position.z)-1.2 and not game.city.is_underwater(global_position):
		global_position.y = game.city.ground_height(global_position.x,global_position.z)+.3; velocity = Vector3.ZERO
	if game.mode != "play" or not alive: return
	if stationary and not hostile:
		velocity = Vector3(0,-1,0); move_and_slide(); animate("idle"); return
	strike_cooldown = maxf(0,strike_cooldown-delta)
	panic = maxf(0,panic-delta)
	var target := goal
	var speed := 1.15
	if hostile:
		target = game.actor_position()
		var distance := global_position.distance_to(target)
		if distance > 45:
			target = home; speed = 0
		elif distance < 1.6:
			speed = 0
			if strike_cooldown <= 0 and not game.player.vehicle:
				var sight := PhysicsRayQueryParameters3D.create(global_position+Vector3(0,1,0),target+Vector3(0,1,0),1)
				if get_world_3d().direct_space_state.intersect_ray(sight).is_empty():
					game.player.damage(9)
					strike_cooldown = 1.1
					animate("attack")
		else: speed = 2.4
	elif panic > 0:
		target = global_position+(global_position-game.actor_position()).normalized()*10
		speed = 4
	elif global_position.distance_to(goal) < 1:
		goal = home if goal != home else walk_end
	var dir := target-global_position
	dir.y = 0
	if dir.length() > .2 and speed > 0:
		dir = dir.normalized()
		rotation.y = lerp_angle(rotation.y,atan2(-dir.x,-dir.z),delta*7)
		velocity.x = dir.x*speed
		velocity.z = dir.z*speed
		animate("run" if speed > 3 else "walk")
	else:
		velocity.x = 0; velocity.z = 0
		if strike_cooldown < .5: animate("idle")
	velocity.y = -1 if is_on_floor() else velocity.y-delta*20
	move_and_slide()

func animate(wanted: String) -> void:
	if not animator: return
	for clip in animator.get_animation_list():
		if String(clip).to_lower().ends_with(wanted) and String(clip) != anim_name:
			anim_name = clip
			animator.play(clip,.1)
			return

func hit(amount: float, from: Vector3) -> void:
	if not alive: return
	health -= amount
	panic = 7
	if not hostile:
		game.crime(1)
		game.hud.message("Міліція почула. Ні, не 'Почув'.",2)
	game.sound("impact",.8)
	global_position += (global_position-from).normalized()*.28
	if health <= 0:
		alive = false
		collision_layer = 0
		if animator: animator.stop()
		model.rotation.x = -PI/2
		model.position.y = .28
		if not mission_enemy: game.money += 20
