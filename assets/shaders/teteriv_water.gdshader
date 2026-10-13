shader_type spatial;
render_mode blend_mix, cull_disabled, depth_draw_always;

uniform sampler2D ripples : source_color, filter_linear_mipmap, repeat_enable;
uniform vec3 deep = vec3(0.07, 0.11, 0.10);
uniform vec3 shallow = vec3(0.24, 0.30, 0.25);

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = world_pos.xz / 9.0;
	vec3 a = texture(ripples, uv + vec2(TIME * 0.021, TIME * 0.013)).rgb;
	vec3 b = texture(ripples, uv * 1.7 - vec2(TIME * 0.015, -TIME * 0.006)).rgb;
	float r = (a.g + b.g) * 0.5;
	ALBEDO = mix(deep, shallow, r);
	ALPHA = 0.84;
	ROUGHNESS = 0.12;
	SPECULAR = 0.7;
}
