extends SceneTree

func _init() -> void:
	var names := ["menu_main.png", "menu_page.png", "loading_01.png", "loading_02.png", "loading_03.png", "loading_04.png", "portrait_podro.png", "cover.png", "cover_with_logo.png"]
	var failures := 0
	for file in names:
		var texture = load("res://assets/ui/" + file)
		var expected := Vector2i(1024, 1024) if file == "portrait_podro.png" else Vector2i(1920, 1080)
		if file in ["cover.png", "cover_with_logo.png"]:
			expected = Vector2i(1024, 1280)
		if texture == null or Vector2i(texture.get_size()) != expected:
			push_error("Invalid asset: " + file)
			failures += 1
		else:
			print("TEXTURE_OK ", file, " ", texture.get_size())
	var hud_script = load("res://scripts/hud.gd")
	if hud_script == null:
		push_error("HUD script could not load")
		failures += 1
	else:
		var hud = hud_script.new()
		hud.setup_frontend()
		if hud.menu_art == null or hud.page_art == null or hud.loading_art.size() != 4:
			push_error("Frontend did not find the two menus and four loading textures")
			failures += 1
		else:
			print("FRONTEND_OK menus=2 loading=4")
		hud.free()
	print("ASSET_CHECK failures=", failures)
	quit(1 if failures > 0 else 0)
