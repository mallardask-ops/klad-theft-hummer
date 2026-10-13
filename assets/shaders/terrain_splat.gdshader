shader_type spatial;
render_mode diffuse_lambert, specular_disabled;

// Vertex colour = grass, dirt, rock, forest weights from tools/city/plan_korostyshiv.py
uniform sampler2D grass : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D grass_dry : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D dirt : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D rock : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D forest : source_color, filter_linear_mipmap, repeat_enable;
uniform float tile = 7.0;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = world_pos.xz / tile;
	vec4 w = max(COLOR, vec4(0.0));
	w /= max(w.r + w.g + w.b + w.a, 0.001);
	// big lazy patches of burnt summer grass break the tiling
	float patches = smoothstep(0.50, 0.62, texture(dirt, world_pos.xz / 233.0).r) * 0.55;
	vec3 g = mix(texture(grass, uv).rgb * vec3(0.92, 1.06, 0.82), texture(grass_dry, uv * 0.8).rgb, patches);
	vec3 c = g * w.r + texture(dirt, uv * 0.9).rgb * w.g + texture(rock, uv * 0.45).rgb * w.b + texture(forest, uv).rgb * w.a;
	c *= mix(0.86, 1.08, texture(dirt, world_pos.xz / 97.0).g);
	ALBEDO = c;
	ROUGHNESS = 1.0;
}
