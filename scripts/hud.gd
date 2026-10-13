extends Control
class_name KHud

var game
var head: Font = preload("res://assets/fonts/head.ttf")
var body: Font = preload("res://assets/fonts/body.ttf")
var script_font: Font = preload("res://assets/fonts/district.ttf")
var gold := Color("e9c866")
var ivory := Color("e7e4cf")
var aqua := Color("90c7d1")
var pink := Color("e5a3ad")
var green := Color("90b986")
var notice := ""
var notice_time := 0.0
var banner_text := ""
var banner_time := 0.0
var pass_text := ""
var pass_detail := ""
var pass_time := 0.0
var damage_flash := 0.0
var choice := 0
var settings := false
var mouse_rects: Array[Rect2] = []
var map_zoom := 1.0
const RADAR_SCALE := .5

func _ready() -> void:
	setup_frontend()
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP

var radio_time := 0.0
var _radio_state := ""

func _process(delta: float) -> void:
	loading_time = maxf(0,loading_time-delta)
	radio_time = maxf(0,radio_time-delta)
	var state := "%s%s" % [game.player.vehicle != null if game and game.player else false, game.radio_on if game else false]
	if state != _radio_state: _radio_state = state; radio_time = 3.0
	if game.mode == "play":
		notice_time = maxf(0,notice_time-delta)
		banner_time = maxf(0,banner_time-delta)
		pass_time = maxf(0,pass_time-delta)
		damage_flash = maxf(0,damage_flash-delta)
	queue_redraw()

func message(value: String, duration: float = 4) -> void:
	notice = value; notice_time = duration

func banner(value: String, duration: float = 4) -> void:
	banner_text = value; banner_time = duration

func text_line(value: String, at: Vector2, font_size: int, color: Color = Color.WHITE, font: Font = null, centered: bool = false, outline: int = 4) -> void:
	if not font: font = head
	var p := at
	if centered: p.x -= font.get_string_size(value,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size).x*.5
	elif at.x >= 1140: p.x -= font.get_string_size(value,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size).x
	draw_string_outline(font,p,value,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size,outline,Color(.025,.025,.028,.97))
	draw_string(font,p,value,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size,color)

func wrap_text(value: String, width: float, font_size: int, font: Font = null) -> Array[String]:
	if not font: font = body
	var lines: Array[String] = []
	for paragraph in value.split("\n"):
		var line := ""
		for word in paragraph.split(" "):
			var candidate := word if line.is_empty() else line+" "+word
			if font.get_string_size(candidate,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size).x > width and not line.is_empty():
				lines.append(line); line = word
			else: line = candidate
		lines.append(line)
	return lines

func _draw() -> void:
	if not game or not game.missions: return
	draw_set_transform(Vector2.ZERO,0,size/Vector2(1280,720))
	if damage_flash > 0: draw_rect(Rect2(0,0,1280,720),Color(.7,0,0,damage_flash*.45))
	if loading_time > 0 and not loading_art.is_empty(): draw_loading(); return
	if game.mode == "menu": draw_menu(); return
	if game.mode == "pause": draw_game_hud(); draw_pause(); return
	if game.mode == "map": draw_map(); return
	if game.mode == "failed": draw_game_hud(); draw_failure(); return
	if game.mode == "dialogue": draw_dialogue(); return
	draw_game_hud()

func draw_game_hud() -> void:
	var minutes := int(game.clock_minutes)%1440
	text_line("%02d:%02d" % [minutes/60,minutes%60],Vector2(1125,57),37,aqua,null,true)
	text_line("$%08d" % game.money,Vector2(1162,97),37,green,null,false)
	heart(Vector2(1065,130),pink)
	text_line("%03d" % int(game.player.health),Vector2(1090,143),35,pink)
	var box := Rect2(1183,24,68,120)
	draw_rect(box,Color(.015,.018,.021,.7))
	draw_rect(box,Color(.01,.01,.01),false,3)
	draw_line(Vector2(1198,119),Vector2(1232,51),Color(.02,.02,.02),13)
	draw_line(Vector2(1198,119),Vector2(1232,51),ivory,7)
	var hammer_points := PackedVector2Array([Vector2(1209,38),Vector2(1247,57),Vector2(1240,71),Vector2(1202,53)])
	draw_colored_polygon(hammer_points,ivory)
	draw_polyline(PackedVector2Array([hammer_points[0],hammer_points[1],hammer_points[2],hammer_points[3],hammer_points[0]]),Color.BLACK,3)
	for i in 6:
		star(Vector2(1050+i*34,189),13,gold if i < game.wanted else Color(.13,.14,.15,.88))
	draw_radar()
	text_line(game.city.get_district(game.actor_position()),Vector2(1216,658),35,green,script_font,false)
	if game.player.vehicle:
		if radio_time > 0:
			text_line("РАДІО КОДЛО" if game.radio_on else "РАДІО ВИМК",Vector2(640,44),30,aqua,head,true)
	var objective_lines := wrap_text(game.missions.objective,780,25)
	var base_y := 622-(objective_lines.size()-1)*29
	for line in objective_lines:
		text_line(line,Vector2(646,base_y),25,gold,body,true); base_y += 29
	var hint: String = game.interaction_hint()
	if not hint.is_empty() and game.mode == "play":
		draw_rect(Rect2(35,35,430,58),Color(.015,.016,.019,.84))
		text_line(hint,Vector2(52,71),22,ivory,body)
	if notice_time > 0:
		var lines := wrap_text(notice,740,23)
		var yy := 100
		for line in lines:
			text_line(line,Vector2(640,yy),23,ivory,body,true); yy += 27
	if banner_time > 0:
		text_line(banner_text,Vector2(640,558),44,gold,head,true,6)
	if pass_time > 0:
		text_line(pass_text,Vector2(640,295),65,gold,head,true,7)
		text_line(pass_detail,Vector2(640,340),27,ivory,body,true)

func heart(at: Vector2, color: Color) -> void:
	var points := PackedVector2Array([at+Vector2(-12,-3),at+Vector2(-10,-11),at+Vector2(-4,-12),at,at+Vector2(4,-12),at+Vector2(10,-11),at+Vector2(12,-3),at+Vector2(0,12)])
	draw_colored_polygon(points,color)
	draw_polyline(PackedVector2Array([points[0],points[1],points[2],points[3],points[4],points[5],points[6],points[7],points[0]]),Color.BLACK,3)

func star(at: Vector2, radius: float, color: Color) -> void:
	var points := PackedVector2Array()
	for i in 10:
		var angle := i*TAU/10-PI/2
		points.append(at+Vector2(cos(angle),sin(angle))*(radius if i%2 == 0 else radius*.45))
	draw_colored_polygon(points,color)
	points.append(points[0]); draw_polyline(points,Color.BLACK,2,true)

func radar_point(world: Vector2, center: Vector2, scale_value: float, origin: Vector2, angle: float) -> Vector2:
	return center+(world-origin).rotated(-angle)*scale_value

func draw_radar() -> void:
	var center := Vector2(122,586)
	var radius := 80.0
	draw_circle(center,radius+7,Color(.035,.035,.035))
	draw_circle(center,radius+3,Color(.74,.72,.62))
	draw_circle(center,radius,Color(.25,.29,.28))
	var pos: Vector3 = game.actor_position()
	var origin := Vector2(pos.x,pos.z)
	var angle: float = game.camera_yaw
	draw_world_disc(center,radius-1,origin,angle,RADAR_SCALE)
	if not game.missions.completed:
		var target: Vector3 = game.missions.target
		var blip := radar_point(Vector2(target.x,target.z),center,RADAR_SCALE,origin,angle)
		if blip.distance_to(center)>radius-7: blip=center+(blip-center).normalized()*(radius-7)
		draw_circle(blip,6,Color.BLACK); draw_circle(blip,4,gold)
	for officer in game.police_cars:
		if not is_instance_valid(officer): continue
		var blip := radar_point(Vector2(officer.position.x,officer.position.z),center,RADAR_SCALE,origin,angle)
		if blip.distance_to(center) < radius-5: draw_circle(blip,3,pink)
	var heading: float = game.player.vehicle.rotation.y if game.player.vehicle else game.player.rotation.y
	var triangle := PackedVector2Array()
	for p in [Vector2(0,-9),Vector2(-5,6),Vector2(0,3),Vector2(5,6)]: triangle.append(center+p.rotated(heading-angle))
	draw_colored_polygon(triangle,ivory); triangle.append(triangle[0]); draw_polyline(triangle,Color.BLACK,2)
	text_line("N",center+Vector2(0,-radius+15).rotated(-angle),17,ivory,head,true,2)
	if not game.missions.completed:
		text_line("%d м" % int(pos.distance_to(game.missions.target)),Vector2(122,691),18,gold,body,true)

func circle_line(a: Vector2,b: Vector2,center: Vector2,radius: float,color: Color,width: float) -> void:
	var d := b-a
	var f := a-center
	var aa := d.dot(d)
	if aa < .0001: return
	var bb := 2*f.dot(d)
	var cc := f.dot(f)-radius*radius
	var disc := bb*bb-4*aa*cc
	if disc < 0: return
	var lo := maxf(0,(-bb-sqrt(disc))/(2*aa))
	var hi := minf(1,(-bb+sqrt(disc))/(2*aa))
	if hi>lo: draw_line(a+d*lo,a+d*hi,color,width)

func rect_line(a: Vector2,b: Vector2,rect: Rect2,color: Color,width: float) -> void:
	var delta := b-a
	var low := 0.0
	var high := 1.0
	for axis in 2:
		if absf(delta[axis]) < .001:
			if a[axis] < rect.position[axis] or a[axis] > rect.end[axis]: return
		else:
			var entry: float = (rect.position[axis]-a[axis])/delta[axis]
			var leave: float = (rect.end[axis]-a[axis])/delta[axis]
			low = maxf(low,minf(entry,leave)); high = minf(high,maxf(entry,leave))
	if high > low: draw_line(a+delta*low,a+delta*high,color,width)

# ---------------------------------------------------------------- GTA III front end
# Full-screen artwork, page header top right, centred options in the frontend orange,
# the selected one on a green bar, bar-graph sliders. Colours from the GTA III frontend.
const FE_LABEL := Color8(235,170,50)
const FE_SELECTED := Color8(255,217,106)
const FE_BAR := Color8(25,130,70)
const FE_SLIDER_ON := Color8(97,194,247)
const FE_SLIDER_OFF := Color8(27,89,130)
const FE_X := 300.0
var menu_font: Font
var title_font: Font = preload("res://assets/fonts/menu_title.ttf")
var menu_art: Texture2D
var page_art: Texture2D
var loading_art: Array[Texture2D] = []
var loading_time := 0.0
var loading_index := 0
var menu_page_time := 0.0
var last_page := ""

func setup_frontend() -> void:
	var variation := FontVariation.new()
	variation.base_font = load("res://assets/fonts/menu.ttf")
	variation.variation_opentype = {TextServerManager.get_primary_interface().name_to_tag("wght"): 640}
	menu_font = variation
	menu_art = load("res://assets/ui/menu_main.png") if ResourceLoader.exists("res://assets/ui/menu_main.png") else null
	page_art = load("res://assets/ui/menu_page.png") if ResourceLoader.exists("res://assets/ui/menu_page.png") else menu_art
	for i in range(1,9):
		var path := "res://assets/ui/loading_%02d.png" % i
		if ResourceLoader.exists(path): loading_art.append(load(path))

func start_loading() -> void:
	if loading_art.is_empty(): return
	loading_index = randi()%loading_art.size()
	loading_time = 2.2

func fe_art(texture: Texture2D, dim: float = 0.0) -> void:
	if texture: draw_texture_rect(texture,Rect2(0,0,1280,720),false)
	else: draw_rect(Rect2(0,0,1280,720),Color(.04,.05,.07))
	if dim > 0: draw_rect(Rect2(0,0,1280,720),Color(0,0,0,dim))
	# keep the options readable over busy artwork
	var shade := Color(0,0,0,.62)
	draw_polygon(PackedVector2Array([Vector2(0,0),Vector2(640,0),Vector2(640,720),Vector2(0,720)]),
		PackedColorArray([shade,Color(0,0,0,0),Color(0,0,0,0),shade]))

func fe_text(value: String, at: Vector2, font_size: int, color: Color, font: Font, align: int = 0, shadow: float = 3.0) -> void:
	# GTA III frontend text: flat colour with a hard black drop shadow, no outline.
	var width := font.get_string_size(value,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size).x
	var p := at - Vector2(width*(.5 if align == 1 else (1.0 if align == 2 else 0.0)),0)
	draw_string(font,p+Vector2(shadow,shadow),value,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size,Color(0,0,0,.92*color.a))
	draw_string(font,p,value,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size,color)

func fe_header(value: String) -> void:
	if last_page != value: last_page = value; menu_page_time = 0.0
	menu_page_time += get_process_delta_time()
	var slide := 1.0-pow(1.0-clampf(menu_page_time/.25,0,1),3)
	fe_text(value,Vector2(1236+(1-slide)*80,98),64,Color(1,1,1,slide),title_font,2,4)

func fe_logo(at: Vector2) -> void:
	# lower-case strap line over a heavy block title, like the GTA III logo lock-up
	fe_text("klad theft hummer",at,27,Color(.96,.96,.93),menu_font,0,2)
	fe_text("КОРОСТИШІВ",at+Vector2(-4,80),86,Color(.96,.96,.93),title_font,0,5)
	draw_rect(Rect2(at+Vector2(0,100),Vector2(470,7)),FE_LABEL)

func draw_menu() -> void:
	fe_art(menu_art)
	if settings:
		draw_rect(Rect2(0,0,1280,720),Color(0,0,0,.35))
		fe_header("НАЛАШТУВАННЯ")
		draw_settings(Vector2(FE_X,250))
	else:
		last_page = ""
		fe_logo(Vector2(62,92))
		menu_items(["НОВА ГРА","ПРОДОВЖИТИ","НАЛАШТУВАННЯ","ВИЙТИ"],Vector2(FE_X,340),56)
	if notice_time > 0:
		var yy := 590
		for line in wrap_text(notice,520,18,menu_font):
			fe_text(line,Vector2(FE_X,yy),18,FE_SELECTED,menu_font,1,2); yy += 24

func menu_items(items: Array, at: Vector2, spacing: int = 56) -> void:
	mouse_rects.clear()
	for i in items.size():
		var yy := at.y+i*spacing
		var size_px := 30
		var width := menu_font.get_string_size(items[i],HORIZONTAL_ALIGNMENT_LEFT,-1,size_px).x
		var bar := Rect2(at.x-maxf(width*.5+34,190),yy-size_px-6,maxf(width+68,380),size_px+20)
		mouse_rects.append(bar)
		if i == choice:
			draw_rect(bar,Color(FE_BAR,.9))
			draw_rect(Rect2(bar.position,Vector2(bar.size.x,3)),Color(.45,.85,.55,.8))
		fe_text(items[i],Vector2(at.x,yy),size_px,FE_SELECTED if i == choice else FE_LABEL,menu_font,1)

func draw_pause() -> void:
	fe_art(page_art,.15)
	if settings:
		fe_header("НАЛАШТУВАННЯ")
		draw_settings(Vector2(FE_X,250))
	else:
		fe_header("ГРА")
		menu_items(["ПРОДОВЖИТИ","КАРТА МІСТА","ПОВТОРИТИ МІСІЮ","НАЛАШТУВАННЯ","В ГОЛОВНЕ МЕНЮ"],Vector2(FE_X,250),58)

func draw_settings(at: Vector2) -> void:
	var labels := ["РАДІО","ТРЯСКА КАМЕРИ","ЧУТЛИВІСТЬ МИШІ","ГУЧНІСТЬ","НАЗАД"]
	var values := [("УВІМК" if game.radio_on else "ВИМК"),("ТАК" if game.shake_on else "НІ"),inverse_lerp(.4,2.0,game.mouse_sensitivity),game.volume,null]
	mouse_rects.clear()
	for i in labels.size():
		var yy := at.y+i*62
		var row := Rect2(at.x-250,yy-36,530,52)
		mouse_rects.append(row)
		if i == choice:
			draw_rect(row,Color(FE_BAR,.9))
			draw_rect(Rect2(row.position,Vector2(row.size.x,3)),Color(.45,.85,.55,.8))
		var color := FE_SELECTED if i == choice else FE_LABEL
		if values[i] == null:
			fe_text(labels[i],Vector2(at.x+15,yy),28,color,menu_font,1)
			continue
		fe_text(labels[i],Vector2(at.x-230,yy),21,color,menu_font,0)
		if values[i] is String:
			fe_text(values[i],Vector2(at.x+262,yy),21,color,menu_font,2)
		else:
			slider(Vector2(at.x+60,yy),float(values[i]))

func slider(at: Vector2, value: float) -> void:
	# GTA III style: 16 rising bars, lit up to the value
	for k in 16:
		var h := 6.0+k*1.5
		var lit := float(k)/15.0 <= value+.001
		draw_rect(Rect2(at.x+k*12,at.y-h,8,h),FE_SLIDER_ON if lit else FE_SLIDER_OFF)

func draw_loading() -> void:
	var t := clampf(loading_time/2.2,0,1)
	draw_rect(Rect2(0,0,1280,720),Color.BLACK)
	draw_texture_rect(loading_art[loading_index],Rect2(0,0,1280,720),false,Color(1,1,1,clampf(t*5,0,1)))
	var bar := Rect2(880,668,330,16)
	draw_rect(bar.grow(3),Color.BLACK)
	draw_rect(Rect2(bar.position,Vector2(bar.size.x*(1-t),bar.size.y)),FE_LABEL)

func draw_dialogue() -> void:
	draw_rect(Rect2(0,0,1280,86),Color(.015,.017,.02,.94))
	draw_rect(Rect2(0,448,1280,272),Color(.015,.017,.02,.96))
	text_line(game.dialogue_title,Vector2(65,58),40,gold)
	text_line(game.dialogue_speaker,Vector2(65,491),23,aqua)
	var yy := 535
	for line in wrap_text(game.dialogue_lines[game.dialogue_index] if not game.dialogue_lines.is_empty() else "Почув.",1130,30):
		text_line(line,Vector2(65,yy),30,ivory,body); yy += 37

func draw_failure() -> void:
	draw_rect(Rect2(0,0,1280,720),Color(.04,0,0,.62))
	text_line(game.fail_title,Vector2(640,322),65,pink,head,true,7)
	text_line(game.fail_reason,Vector2(640,369),25,ivory,body,true)
	text_line("ENTER",Vector2(640,454),24,gold,head,true)

func draw_map() -> void:
	draw_rect(Rect2(0,0,1280,720),Color(.025,.032,.034,.97))
	text_line("КОРОСТИШІВ",Vector2(45,68),43,gold)
	var map_rect := Rect2(573,47,632,632)
	draw_rect(map_rect,Color(.21,.27,.25))
	var center := map_rect.get_center()
	var scale_value := map_zoom*.42
	var pos: Vector3 = game.actor_position()
	var bounds: Rect2 = game.city.playable_bounds
	var half := map_rect.size*.5/scale_value
	var view := Vector2(clampf(pos.x,bounds.position.x+half.x*.5,bounds.end.x-half.x*.5),clampf(pos.z,bounds.position.y+half.y*.5,bounds.end.y-half.y*.5))
	draw_world_rect(map_rect,view,scale_value)
	var to_screen := func(w: Vector2) -> Vector2: return center+(w-view)*scale_value
	var sites := {"cafe":"КАФЕ КОДЛО","garages":"ГАРАЖІ","market":"ЦЕНТРАЛЬНИЙ РИНОК","sawmill":"ПРОМЗОНА","quarry":"КАР'ЄР","dorm":"ГУРТОЖИТОК","plaza":"СОБОРНА ПЛОЩА"}
	for key in sites:
		if not game.city.locations.has(key): continue
		var w: Vector3 = game.city.locations[key]["pos"]
		var at: Vector2 = to_screen.call(Vector2(w.x,w.z))
		if map_rect.grow(-10).has_point(at):
			draw_circle(at,5,ivory); text_line(sites[key],at+Vector2(0,-10),14,ivory,body,true,2)
	var player_at: Vector2 = to_screen.call(Vector2(pos.x,pos.z))
	player_at = player_at.clamp(map_rect.position+Vector2(10,10),map_rect.end-Vector2(10,10))
	draw_circle(player_at,8,Color.BLACK); draw_circle(player_at,5,Color.WHITE)
	if not game.missions.completed:
		var tgt: Vector3 = game.missions.target
		var t_at: Vector2 = (to_screen.call(Vector2(tgt.x,tgt.z)) as Vector2).clamp(map_rect.position+Vector2(10,10),map_rect.end-Vector2(10,10))
		draw_circle(t_at,9,Color.BLACK)
		draw_circle(t_at,6,gold)
	var yy := 178
	for i in game.missions.missions.size():
		var mission: Dictionary = game.missions.missions[i]
		var prefix := "[+] " if i<game.missions.index else ("[>] " if i==game.missions.index else "[ ] ")
		text_line(prefix+mission.get("title",""),Vector2(45,yy),29,gold if i==game.missions.index else ivory)
		yy += 83
	var by := 563
	for line in wrap_text(game.missions.objective,480,22):
		text_line(line,Vector2(45,by),22,gold,body); by += 27

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and game.mode in ["menu","pause"]:
		var at: Vector2 = event.position*Vector2(1280,720)/size
		for i in mouse_rects.size():
			if mouse_rects[i].has_point(at): choice = i
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if game.mode in ["menu","pause"]:
			var at: Vector2 = event.position*Vector2(1280,720)/size
			for i in mouse_rects.size():
				if mouse_rects[i].has_point(at): choice = i; game.menu_confirm(); break
	elif game.mode == "map" and event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP: map_zoom = clampf(map_zoom*1.2,.5,4.0)
		if event.button_index == MOUSE_BUTTON_WHEEL_DOWN: map_zoom = clampf(map_zoom/1.2,.5,4.0)

# The radar and the map show assets/city/radar.png (OSM roads, buildings, the Teteriv).
func world_uv(w: Vector2) -> Vector2:
	var r: Rect2 = game.city.radar_rect
	return (w-r.position)/r.size

func draw_world_disc(center: Vector2, radius: float, origin: Vector2, angle: float, scale_value: float) -> void:
	if game.city.radar_texture == null: return
	var points := PackedVector2Array()
	var uvs := PackedVector2Array()
	for i in 40:
		var o := Vector2.from_angle(i*TAU/40)*radius
		points.append(center+o)
		uvs.append(world_uv(origin+o.rotated(angle)/scale_value))
	draw_polygon(points,PackedColorArray([Color.WHITE]),uvs,game.city.radar_texture)

func draw_world_rect(rect: Rect2, view: Vector2, scale_value: float) -> void:
	if game.city.radar_texture == null: return
	var points := PackedVector2Array([rect.position,Vector2(rect.end.x,rect.position.y),rect.end,Vector2(rect.position.x,rect.end.y)])
	var uvs := PackedVector2Array()
	for p in points: uvs.append(world_uv(view+(p-rect.get_center())/scale_value))
	draw_polygon(points,PackedColorArray([Color.WHITE]),uvs,game.city.radar_texture)
