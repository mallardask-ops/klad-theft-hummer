import bpy
from pathlib import Path

root = Path(__file__).resolve().parents[1]
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(root / 'assets/source/rock_face_01/rock_face_01.gltf'))
before = 0
after = 0
for obj in list(bpy.context.scene.objects):
    if obj.type != 'MESH':
        continue
    before += sum(len(poly.vertices)-2 for poly in obj.data.polygons)
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new('Retro silhouette', 'DECIMATE')
    modifier.ratio = .13
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    after += sum(len(poly.vertices)-2 for poly in obj.data.polygons)
    for mat in obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        principled = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        principled.inputs['Roughness'].default_value = 1
        principled.inputs['Metallic'].default_value = 0
        for name in ['Normal','Roughness','Metallic']:
            for link in list(principled.inputs[name].links):
                mat.node_tree.links.remove(link)
bpy.ops.wm.save_as_mainfile(filepath=str(root / 'assets/source/rock_face_retro.blend'))
bpy.ops.export_scene.gltf(filepath=str(root / 'assets/models/rock_face_retro.glb'),export_format='GLB',export_yup=True)
print(f'ROCK_MODEL_READY triangles_before={before} triangles_after={after}')
