extends Node
class_name KMissions

var game
var missions: Array = []
var index := 0
var step_index := -1
var active := false
var completed := false
var enemies: Array = []
var marker: Node3D
var ring: MeshInstance3D
var arrow: MeshInstance3D
var checkpoint_money := 350
var objective := "Зайди у жовтий маркер біля кав'ярні."
var near := false
var target := Vector3.ZERO
var escape_raised := false
var pulse := 0.0
var item_prop: Node3D

func _ready() -> void:
	var file := FileAccess.open("res://data/missions.json",FileAccess.READ)
	if file:
		var parsed = JSON.parse_string(file.get_as_text())
		if parsed is Dictionary: missions = parsed.get("missions",[])
	create_marker()
	update_objective()

func create_marker() -> void:
	marker = Node3D.new()
	game.world.add_child(marker)
	ring = MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = 1.7; mesh.bottom_radius = 1.7; mesh.height = 2.6
	mesh.radial_segments = 32
	ring.mesh = mesh; ring.position.y = 1.35
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(1,.72,.1,.22)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	ring.material_override = mat; marker.add_child(ring)
	var halo := MeshInstance3D.new()
	var torus := TorusMesh.new(); torus.inner_radius = 1.6; torus.outer_radius = 1.76
	halo.mesh = torus; halo.position.y = .16
	var solid := StandardMaterial3D.new(); solid.albedo_color = Color(1,.78,.05); solid.shading_mode = 0
	halo.material_override = solid; marker.add_child(halo)
	arrow = MeshInstance3D.new()
	var cone := CylinderMesh.new(); cone.top_radius = .5; cone.bottom_radius = 0; cone.height = .65
	arrow.mesh = cone; arrow.material_override = solid; arrow.position.y = 3.6
	marker.add_child(arrow)

func current() -> Dictionary:
	return missions[index] if index < missions.size() else {}

func step() -> Dictionary:
	var steps: Array = current().get("steps",[])
	return steps[step_index] if step_index >= 0 and step_index < steps.size() else {}

func update_objective() -> void:
	if index >= missions.size():
		completed = true; active = false; marker.visible = false
		objective = "Коростишів твій. Вільна гра. R: радіо, M: карта."
		return
	var data := step() if active else current()
	target = place(data.get("position",data.get("start","cafe")))
	marker.position = target
	marker.visible = true
	update_prop()
	objective = data.get("label","Зустрінь %s біля жовтого маркера." % current().get("giver","Едіка"))
	near = false
	if active and step().get("type","") == "combat":
		spawn_enemies()
	escape_raised = false
	if active and step().get("type","") == "escape":
		game.crime(int(step().get("wanted_on_start",2)))
		escape_raised = true

func update_prop() -> void:
	if item_prop: item_prop.queue_free(); item_prop = null
	if not active or step().get("type","") != "pickup": return
	item_prop = Node3D.new(); marker.add_child(item_prop)
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	var is_phone := String(step().get("item","")).contains("Телефон")
	box.size = Vector3(.27,.42,.09) if is_phone else Vector3(.85,.65,.6)
	mesh.mesh = box
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(.05,.06,.08) if is_phone else Color(.6,.41,.23)
	if not is_phone: mat.albedo_texture = load("res://assets/textures/wood.png")
	mesh.material_override = mat; item_prop.add_child(mesh)
	item_prop.position.y = .95
	var label := Label3D.new(); label.text = step().get("item","Голд"); label.font_size = 32
	label.pixel_size = .009; label.position.y = .65; label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate = Color(1,.85,.3); label.outline_size = 7
	item_prop.add_child(label)

func spawn_enemies() -> void:
	enemies.clear()
	var count := int(step().get("enemies",step().get("count",4)))
	for i in count:
		var person := KPerson.new()
		person.game = game; person.hostile = true; person.mission_enemy = true
		person.position = target + Vector3((i%2)*4-2,0,(i/2)*4-2)
		person.position.y = game.city.ground_height(person.position.x,person.position.z)+.3
		game.world.add_child(person)
		game.people.append(person); enemies.append(person)

func _process(delta: float) -> void:
	if not marker: return
	marker.visible = not completed and game.mode != "dialogue"
	pulse += delta
	arrow.position.y = 3.45+sin(pulse*2.8)*.25
	arrow.rotation.y += delta
	if item_prop:
		item_prop.rotation.y += delta*.65
		item_prop.position.y = .95+sin(pulse*2)*.12
	if game.mode != "play" or completed: return
	var distance: float = game.actor_position().distance_to(target)
	var radius := float(step().get("radius",4.5)) if active else 4.5
	near = distance < radius
	if active:
		var type: String = step().get("type","")
		if type == "combat":
			var remaining := 0
			for enemy in enemies:
				if is_instance_valid(enemy) and enemy.alive: remaining += 1
			objective = "%s  (%d залишилось)" % [step().get("label","Розберися з наїздниками."),remaining]
			if remaining == 0: advance()
		elif type == "drive" and near and game.player.vehicle:
			advance()
		elif type == "escape":
			objective = "Скинь розшук і дістанься схованки." if game.wanted > 0 else "Міліція відстала. Їдь у схованку."
			if near and game.wanted == 0: advance()

func interact() -> bool:
	if completed or not near: return false
	if not active:
		checkpoint_money = game.money
		game.open_dialogue(current().get("title",""),current().get("giver",""),current().get("intro",[]),start_mission)
		return true
	var type: String = step().get("type","")
	if type == "pickup" or type == "talk":
		if game.player.vehicle and type == "pickup":
			game.hud.message("Вийди з машини.",2)
			return true
		if type == "talk":
			game.open_dialogue(current().get("title",""),step().get("speaker",current().get("giver","")),step().get("lines",["Почув. Далі за жовтим маркером."]),advance)
		else:
			game.sound("pickup",.85)
			game.hud.message(step().get("item","Коробка"),2)
			if int(step().get("wanted_level",0)) > 0: game.crime(int(step().get("wanted_level",0)))
			advance()
		return true
	return false

func start_mission() -> void:
	active = true; step_index = 0
	game.hud.banner(current().get("title",""),4)
	game.sound("mission_start",.7)
	update_objective()

func advance() -> void:
	step_index += 1
	if step_index >= current().get("steps",[]).size():
		var reward := int(current().get("reward",500))
		game.money += reward
		checkpoint_money = game.money
		game.hud.pass_text = "МІСІЮ ПРОЙДЕНО"
		game.hud.pass_detail = "+%d ₴" % reward
		game.hud.pass_time = 5
		game.sound("mission_pass",.9)
		game.hud.message("\n".join(current().get("outro",[])),6)
		active = false; step_index = -1; index += 1
		game.save_game()
		if index == missions.size():
			game.hud.pass_detail = "ЕПІЗОД 01 ЗАКІНЧЕНО / КОРОСТИШІВ ПАМ'ЯТАЄ"
		update_objective()
	else:
		update_objective()

func retry() -> void:
	for enemy in game.people.duplicate():
		if is_instance_valid(enemy) and enemy.mission_enemy: game.people.erase(enemy); enemy.queue_free()
	enemies.clear()
	game.money = checkpoint_money
	game.player.health = 100
	game.clear_wanted()
	if game.player.vehicle:
		game.player.vehicle.driver = null
		game.player.vehicle = null
	game.player.visible = true; game.player.collision_layer = 4
	game.player.global_position = game.city.location("start")+Vector3(0,.3,0)
	game.player.velocity = Vector3.ZERO
	game.camera_yaw = 0
	game.starter_car.global_position = game.starter_spot()
	game.starter_car.speed = 0; game.starter_car.health = 100; game.starter_car.rotation.y = game.city.locations["start"]["car_heading"]
	active = false; step_index = -1
	update_objective()

# Mission places are names of real Korostyshiv locations (data/city/korostyshiv.json); [x, z] still works.
func place(spot: Variant) -> Vector3:
	if spot is String:
		return game.city.location(spot)
	var at := Vector3(float(spot[0]),0,float(spot[1]))
	at.y = game.city.ground_height(at.x,at.z)
	return at
