shader_type canvas_item;
uniform float grit = 0.003;
void fragment() {
 vec4 c = texture(TEXTURE, UV);
 float n = fract(sin(dot(floor(UV * vec2(896.0,504.0)),vec2(12.9898,78.233))) * 43758.5453);
 c.rgb = floor(clamp(c.rgb + (n-.5)*grit,vec3(0.0),vec3(1.0))*40.0)/40.0;
 COLOR = c;
}
