"""Build the original low-poly cast and vehicles; run with Blender in background."""

import bpy
import json
import math
import random
import struct
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models"
SOURCE = ROOT / "assets/source"
OUT.mkdir(parents=True, exist_ok=True)
SOURCE.mkdir(parents=True, exist_ok=True)


def fresh():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablock in list(bpy.data.actions):
        bpy.data.actions.remove(datablock)
    bpy.context.scene.render.fps = 24
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 25


def material(name, color, grit=0.10, metal=0.0, emission=0.0):
    old = bpy.data.materials.get(name)
    if old:
        return old
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = 0.85 if metal == 0 else 0.52
    shader.inputs["Metallic"].default_value = metal
    if emission:
        shader.inputs["Emission Color"].default_value = (*color, 1)
        shader.inputs["Emission Strength"].default_value = emission
    if grit:
        rng = random.Random(name)
        im = bpy.data.images.new(name + "_64px", width=64, height=64)
        cells = [[rng.uniform(-grit, grit) for _ in range(16)] for _ in range(16)]
        pixels = []
        for y in range(64):
            for x in range(64):
                noise = cells[y // 4][x // 4] + rng.uniform(-grit * .45, grit * .45)
                if x % 19 == 0 and y % 23 < 13:
                    noise += grit * .9
                pixels.extend([max(.015, min(1, c * (1 + noise))) for c in color] + [1])
        im.pixels = pixels
        im.pack()
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = im
        tex.interpolation = "Closest"
        mat.node_tree.links.new(tex.outputs["Color"], shader.inputs["Base Color"])
    return mat


def attach(obj, parent):
    if parent:
        bpy.context.view_layer.update()
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
    return obj


def pivot(name, pos=(0, 0, 0), parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.empty_display_type = "PLAIN_AXES"
    obj.location = pos
    attach(obj, parent)
    return obj


def finish(obj, name, mat, parent=None):
    obj.name = name
    if mat:
        obj.data.materials.append(mat)
    attach(obj, parent)
    return obj


def box(name, loc, size, mat, parent=None, bevel=0.0, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.dimensions = size
    obj.rotation_euler = rot
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("Cut corners", "BEVEL")
        mod.width = bevel
        mod.segments = 1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return finish(obj, name, mat, parent)


def ico(name, loc, size, mat, parent=None, sub=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=1, location=loc)
    obj = bpy.context.object
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, mat, parent)


def cylinder(name, loc, radius, depth, mat, parent=None, vertices=12, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
    return finish(bpy.context.object, name, mat, parent)


def mesh(name, verts, faces, mat, parent=None):
    data = bpy.data.meshes.new(name + "_geometry")
    data.from_pydata(verts, [], faces)
    data.update()
    uv = data.uv_layers.new(name="UVMap")
    for poly in data.polygons:
        for i, loop_index in enumerate(poly.loop_indices):
            if len(poly.loop_indices)==4:
                uv.data[loop_index].uv = [(0,0),(1,0),(1,1),(0,1)][i]
            elif len(poly.loop_indices)==3:
                uv.data[loop_index].uv = [(0,0),(1,0),(.5,1)][i]
            else:
                a=i*math.tau/len(poly.loop_indices)
                uv.data[loop_index].uv = (.5+math.cos(a)*.5,.5+math.sin(a)*.5)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return finish(obj, name, mat, parent)


def taper(name, loc, lower, upper, height, mat, parent=None):
    lx, ly = lower
    ux, uy = upper
    x, y, z = loc
    ring = [(-.72,-1),(.72,-1),(1,-.60),(1,.60),(.72,1),(-.72,1),(-1,.60),(-1,-.60)]
    verts = [(x+sx*lx/2,y+sy*ly/2,z-height/2) for sx,sy in ring]
    verts += [(x+sx*ux/2,y+sy*uy/2,z+height/2) for sx,sy in ring]
    faces = [tuple(range(7,-1,-1)),tuple(range(8,16))]
    faces += [(k,(k+1)%8,(k+1)%8+8,k+8) for k in range(8)]
    return mesh(name, verts, faces, mat, parent)


def text(name, content, loc, size, mat, rot=(math.pi/2, 0, 0), parent=None):
    curve = bpy.data.curves.new(name, "FONT")
    curve.body = content
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = .0005
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = rot
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    obj.select_set(False)
    return finish(obj, name, mat, parent)


def consolidate(parent, label):
    children = [o for o in bpy.data.objects if o.parent == parent and o.type == "MESH"]
    if not children:
        return
    if len(children) == 1:
        children[0].name = label
        return
    bpy.ops.object.select_all(action="DESELECT")
    for obj in children:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = children[0]
    bpy.ops.object.join()
    children[0].name = label


def vehicle_groups(root):
    groups = {
        "Headlights": lambda n: "Headlight" in n,
        "Tail_Lights": lambda n: "Taillight" in n or "Reverse" in n,
        "Indicators": lambda n: "Indicator" in n,
        "Glass": lambda n: "Glass" in n or n == "Windshield",
        "Grille": lambda n: n.startswith("Grille") or n == "Badge",
        "License": lambda n: n.startswith("License_") or n.startswith("Plate"),
        "Exhaust": lambda n: n.startswith("Exhaust"),
        "Siren_Blue": lambda n: n.startswith("Lightbar_Blue"),
        "Siren_Red": lambda n: n.startswith("Lightbar_Red"),
    }
    for label,predicate in groups.items():
        parts=[o for o in bpy.data.objects if o.parent==root and o.type=="MESH" and predicate(o.name)]
        if not parts:
            continue
        group=pivot(label,(0,0,0),root)
        for obj in parts:
            world=obj.matrix_world.copy()
            obj.parent=group
            obj.matrix_parent_inverse=group.matrix_world.inverted()
            obj.matrix_world=world
        consolidate(group,label+"_Mesh")
        group.name=label
    consolidate(root,"Vehicle_Body")


M = {
    "jacket": material("Jacket_Black_Worn", (.105, .12, .105), .36),
    "seam": material("Jacket_Seams", (.225, .235, .195), .18),
    "shirt": material("Shirt_Dirty_Gray", (.42, .405, .32), .24),
    "jeans": material("Denim_Faded", (.14, .23, .32), .32),
    "patch": material("Denim_Abrasion", (.25, .34, .38), .32),
    "boot": material("Boots_Rubber", (.055, .065, .05), .25),
    "skin": material("Skin_Worker", (.64, .44, .29), .09),
    "skin_dark": material("Knuckles_Shadow", (.40, .27, .18), .09),
    "hair": material("Hair_Dark", (.07, .075, .055), .3),
    "white": material("Eye_White", (.62, .61, .52), .0),
    "eye": material("Eyes", (.055, .06, .045), .0),
    "wood": material("Hammer_Worn_Wood", (.35, .205, .09), .42),
    "metal": material("Hammer_Steel", (.29, .30, .265), .32, .58),
    "rust": material("Rust", (.30, .145, .065), .45),
    "black": material("Vehicle_Rubber", (.035, .045, .04), .32),
    "chrome": material("Dull_Chrome", (.40, .44, .42), .16, .65),
    "glass": material("Glass_Dark_Blue", (.075, .13, .16), .05, .24),
    "seat": material("Seats_Brown", (.14, .12, .08), .22),
    "plate": material("License_Plate", (.69, .71, .58), .12),
    "headlight": material("Headlights_Amber", (.87, .77, .42), .06, 0, .3),
    "red": material("Tail_Lights", (.51, .05, .025), .05, 0, .2),
    "orange": material("Indicator_Orange", (.76, .31, .035), .06, 0, .1),
    "blue": material("Siren_Blue", (.045, .17, .66), .04, 0, .4),
    "police_red": material("Siren_Red", (.74, .06, .035), .04, 0, .4),
    "granite": material("Granite_Cut", (.40, .39, .355), .48),
    "granite_dark": material("Granite_Grooves", (.22, .225, .20), .40),
}


def hammer(parent, origin=(0, 0, 0), scale=1.0):
    x,y,z = origin
    box("Hammer_Handle", (x,y,z-.19*scale), (.042*scale,.045*scale,.44*scale), M["wood"], parent, .006*scale)
    box("Hammer_Head", (x,y,z+.027*scale), (.24*scale,.08*scale,.095*scale), M["metal"], parent, .011*scale)
    box("Hammer_Poll", (x-.116*scale,y,z+.027*scale), (.025*scale,.097*scale,.105*scale), M["metal"], parent, .003*scale)
    mesh("Hammer_Claw", [(x+.075*scale,y-.042*scale,z+.062*scale),(x+.168*scale,y-.042*scale,z-.01*scale),(x+.168*scale,y-.01*scale,z-.01*scale),(x+.075*scale,y-.01*scale,z+.062*scale),
                          (x+.075*scale,y+.01*scale,z+.062*scale),(x+.168*scale,y+.01*scale,z-.01*scale),(x+.168*scale,y+.042*scale,z-.01*scale),(x+.075*scale,y+.042*scale,z+.062*scale)], [(0,1,2,3),(4,5,6,7)], M["metal"], parent)
    box("Hammer_Handle_Scuff", (x,y+.024*scale,z-.24*scale), (.023*scale,.005*scale,.06*scale), M["rust"], parent)


def make_hammer():
    root = pivot("Hammer")
    hammer(root)
    consolidate(root, "Hammer_Mesh")
    return root


def human(npc=False, variant=None):
    root = pivot(variant.title() if variant else ("NPC_Worker" if npc else "Podro"))
    body = pivot("Body", (0,-.025,.94), root)
    shirt = M["shirt"]
    jacket = material("NPC_Workcoat_Tobacco", (.30,.245,.135), .35) if npc else M["jacket"]
    pants = material("NPC_Trousers", (.25,.245,.17), .28) if npc else M["jeans"]
    skin = M["skin"]
    hair = M["hair"]
    boot = M["boot"]
    torso_lower,torso_upper=(.45,.275),(.61,.34)
    if variant == "edik":
        jacket=material("Edik_Blue_Tee",(.105,.27,.48),.22)
        pants=material("Edik_Jeans",(.21,.27,.37),.27)
        boot=material("Edik_Trainers",(.43,.45,.40),.18)
        torso_lower,torso_upper=(.42,.24),(.55,.29)
    elif variant == "serhiy":
        jacket=material("Serhiy_Brown_Jacket",(.35,.285,.18),.25)
        shirt=material("Serhiy_Undershirt",(.53,.51,.40),.19)
        pants=material("Serhiy_Trousers",(.11,.12,.115),.23)
        skin=material("Serhiy_Skin",(.58,.39,.25),.09)
        torso_lower,torso_upper=(.56,.35),(.66,.39)
    elif variant == "cyber":
        jacket=material("Cyber_Hoodie",(.075,.09,.105),.28)
        pants=material("Cyber_Jeans",(.13,.175,.215),.23)
        boot=material("Cyber_Trainers",(.14,.16,.18),.19)
        skin=material("Cyber_Pale_Skin",(.71,.56,.42),.07)
        torso_lower,torso_upper=(.48,.30),(.59,.35)
    elif variant == "podrina":
        jacket=material("Podrina_Olive_Jacket",(.26,.29,.19),.23)
        shirt=material("Podrina_Cream_Shirt",(.69,.60,.43),.16)
        pants=material("Podrina_Jeans",(.17,.235,.31),.25)
        hair=material("Podrina_Chestnut_Hair",(.22,.10,.045),.24)
        skin=material("Podrina_Skin",(.73,.52,.36),.07)
        boot=material("Podrina_Boots",(.17,.15,.10),.19)
        torso_lower,torso_upper=(.40,.26),(.53,.31)
    taper("Jacket_Torso", (0,-.015,1.17),torso_lower,torso_upper,.44,jacket,body)
    if variant == "edik":
        box("Tee_Hem",(0,0,.951),(.44,.26,.043),jacket,body,.011)
        cylinder("Tee_Collar",(0,.025,1.406),.096,.025,M["seam"],body,12)
        text("Edik_Shirt_Print","KODLO",(0,.161,1.262),.070,M["plate"],(math.pi/2,0,math.pi),body)
    elif variant == "cyber":
        box("Hoodie_Hem",(0,0,.949),(.50,.33,.060),M["jacket"],body,.012)
        box("Hoodie_Kangaroo_Pocket",(0,.167,1.085),(.295,.022,.12),M["jacket"],body,.022)
        for side in [-1,1]:
            box("Hoodie_Drawstring",(side*.043,.188,1.312),(.012,.013,.145),M["shirt"],body,.002)
        box("USB_Card_Badge",(.126,.197,1.214),(.069,.016,.088),M["chrome"],body,.005)
    else:
        box("Jacket_Waistband", (0,.0,.945), ((.42 if variant=="podrina" else .48),.32,.073), M["seam"], body, .018)
        box("Tshirt_V", (0,.176,1.31), (.18,.035,.22), shirt, body, .025)
        for side in [-1,1]:
            box("Jacket_Lapel", (side*.113,.175,1.35), (.065,.045,.20), jacket, body, .011, (0,side*.26,side*.16))
            box("Jacket_Pocket", (side*.17,.15,1.06), (.10,.022,.06), M["seam"], body, .006)
            box("Pocket_Flap", (side*.17,.165,1.09), (.102,.012,.019), jacket, body, .003)
            box("Jacket_Shoulder", (side*.25,.01,1.39), (.15,.29,.08), jacket, body, .03)
        box("Zip", (0,.175,1.055), (.014,.012,.16), M["chrome"], body)
    cylinder("Neck", (0,.025,1.435), .082,.16,skin,body,8)
    ico("Head", (0,.035,1.565), (.139,.125,.151), skin, body, 2)
    box("Jaw", (0,.035,1.49), (.181,.17,.067) if variant=="podrina" else (.211,.19,.082), skin,body,.028)
    for side in [-1,1]:
        ico("Ear", (side*.14,.02,1.582), (.027,.038,.046),skin,body,1)
        box("Eye_White", (side*.053,.142,1.612), (.040,.018,.022),M["white"],body,.003)
        box("Eye", (side*.049,.153,1.611), (.014,.008,.016),M["eye"],body)
        box("Brow", (side*.050,.151,1.635), (.052,.018,.010 if variant=="podrina" else .016),hair,body,.003,(0,side*.04,side*.08))
        if variant != "podrina":
            box("Sideburn", (side*.126,.048,1.627), (.014,.067,.058),hair,body)
    mesh("Nose", [(-.025,.143,1.611),(.025,.143,1.611),(-.027,.146,1.564),(.027,.146,1.564),(0,.196,1.576)],[(0,1,4),(1,3,4),(3,2,4),(2,0,4)],skin,body)
    lips=material("Podrina_Lips",(.40,.155,.115),0) if variant=="podrina" else M["skin_dark"]
    box("Mouth", (0,.145,1.535), (.068,.008,.012),lips,body,.002)
    if variant not in ["podrina","edik"]:
        box("Stubble", (0,.119,1.497), (.116,.041,.024),M["skin_dark"],body,.009)
    if variant == "serhiy":
        box("Moustache",(0,.153,1.550),(.108,.017,.020),hair,body,.005)
    hair_verts=[]
    for radius,height in [(1,1.655),(.85,1.700),(.32,1.725)]:
        for k in range(10):
            a=k*math.tau/10
            hair_verts.append((math.cos(a)*.139*radius,.021+math.sin(a)*.124*radius,height))
    hair_faces=[tuple(range(20,30))]
    for row in range(2):
        for k in range(10):
            hair_faces.append((row*10+k,row*10+(k+1)%10,(row+1)*10+(k+1)%10,(row+1)*10+k))
    mesh("Hair",hair_verts,hair_faces,hair,body)
    box("Hair_Back", (0,-.077,1.635),(.186,.042,.075),hair,body,.015)
    if variant == "podrina":
        taper("Long_Hair_Back",(0,-.095,1.478),(.23,.08),(.24,.12),.34,hair,body)
        for side in [-1,1]:
            taper("Hair_Lock",(side*.128,.067,1.490),(.045,.047),(.069,.072),.36,hair,body)
        ico("Ponytail",(0,-.183,1.510),(.063,.07,.175),hair,body,2)
    if variant == "cyber":
        ico("Hood_Back",(0,-.065,1.585),(.193,.144,.213),jacket,body,2)
        for side in [-1,1]:
            taper("Hood_Side",(side*.164,.068,1.602),(.059,.11),(.067,.10),.32,jacket,body)
            # Four bars retain visible glasses at game resolution.
            for z in [1.580,1.634]:
                box("Glasses_Horizontal",(side*.055,.173,z),(.093,.018,.012),M["black"],body,.002)
            for x in [side*.015,side*.101]:
                box("Glasses_Vertical",(x,.173,1.607),(.012,.018,.063),M["black"],body,.002)
            box("Glasses_Lens",(side*.055,.165,1.607),(.075,.008,.045),M["glass"],body)
        box("Glasses_Bridge",(0,.179,1.617),(.028,.012,.012),M["black"],body)
        box("Hood_Top",(0,.058,1.761),(.309,.139,.064),jacket,body,.021)
    # Each limb has a named pivot that Godot can also animate directly.
    limbs = {}
    for side,label in [(-1,"L"),(1,"R")]:
        leg = pivot("Leg_"+label, (side*.135,0,.895),body)
        limbs["Leg_"+label] = leg
        taper("Thigh_"+label,(side*.135,-.005,.68),(.18,.20),(.222,.238),.43,pants,leg)
        taper("Shin_"+label,(side*.14,.005,.335),(.135,.155),(.171,.195),.31,pants,leg)
        box("Knee_Patch_"+label,(side*.14,.104,.477),(.115,.015,.095),M["patch"],leg,.012)
        box("Rear_Pocket_"+label,(side*.135,-.125,.80),(.118,.018,.106),M["patch"],leg,.006)
        box("Boot_"+label,(side*.14,.067,.103),(.191,.328,.186),boot,leg,.034)
        box("Boot_Sole_"+label,(side*.14,.067,.034),(.207,.345,.068),M["black"],leg,.012)
        for k in range(3):
            box("Boot_Lace",(side*.14,.096+k*.031,.195),(.087,.014,.008),M["seam"],leg)
        arm = pivot("Arm_"+label,(side*.322,.01,1.345),body)
        limbs["Arm_"+label] = arm
        if variant == "edik":
            taper("Short_Sleeve_"+label,(side*.34,.018,1.263),(.149,.164),(.18,.197),.195,jacket,arm)
            taper("Upper_Arm_"+label,(side*.34,.023,1.102),(.132,.138),(.147,.15),.142,skin,arm)
        else:
            taper("Upper_Sleeve_"+label,(side*.34,.018,1.18),(.15,.17),(.191,.21),.30,jacket,arm)
        elbow = pivot("Forearm_"+label,(side*.34,.036,1.025),arm)
        limbs["Forearm_"+label] = elbow
        taper("Fore_Sleeve_"+label,(side*.35,.053,.924),(.125,.132),(.16,.17),.227,skin if variant=="edik" else jacket,elbow)
        if variant != "edik":
            box("Cuff_"+label,(side*.35,.058,.806),(.143,.148,.06),M["seam"],elbow,.012)
        box("Hand_"+label,(side*.35,.069,.75),(.132,.106,.109),skin,elbow,.016)
        for finger in range(4):
            box("Finger_"+label,(side*.35 + (finger-1.5)*.028,.082,.690),(.024,.064,.06),skin,elbow,.007)
            box("Knuckle_"+label,(side*.35 + (finger-1.5)*.028,.122,.74),(.023,.012,.021),M["skin_dark"],elbow,.004)
        ico("Thumb_"+label,(side*.409,.095,.752),(.037,.030,.049),skin,elbow,1)
        if label == "R" and not npc:
            hp = pivot("Hammer_Grip",(.35,.11,.74),elbow)
            hammer(hp,(.35,.11,1.04),.90)
            consolidate(hp,"Hammer_Mesh")
            hp.rotation_euler.x=math.pi
    if npc and not variant:
        box("Worker_Cap",(0,.014,1.705),(.261,.232,.073),pants,body,.016)
        box("Cap_Visor",(0,.146,1.69),(.251,.119,.025),pants,body,.006)
    for name,obj in limbs.items():
        consolidate(obj,name+"_Mesh")
    consolidate(body,"Body_Mesh")
    animate_human(body,limbs)
    if variant:
        scales={"edik":(.70,.86,1.04),"serhiy":(1.12,1.08,1.025),"cyber":(.85,.94,1.015),"podrina":(.78,.85,.973)}
        root.scale=scales[variant]
    return root


def add_clip(obj, name, values, frames):
    obj.animation_data_create()
    obj.animation_data.action = None
    base_loc = obj.location.copy()
    base_rot = obj.rotation_euler.copy()
    for frame,rot,offset in zip(frames,values[0],values[1]):
        obj.rotation_euler = (base_rot.x+rot[0],base_rot.y+rot[1],base_rot.z+rot[2])
        obj.location = base_loc + Vector(offset)
        obj.keyframe_insert(data_path="rotation_euler",frame=frame)
        obj.keyframe_insert(data_path="location",frame=frame)
    action = obj.animation_data.action
    action.name = name + "_" + obj.name
    track = obj.animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name,1,action)
    strip.action_frame_start = frames[0]
    strip.action_frame_end = frames[-1]
    obj.animation_data.action = None
    obj.location = base_loc
    obj.rotation_euler = base_rot


def animate_human(body, limbs):
    frames = [1,7,13,19,25]
    zeros = [(0,0,0)]*5
    for clip in ["idle","walk","run","attack"]:
        if clip == "idle":
            add_clip(body,clip,([(-.05,0,0),(-.065,0,0),(-.05,0,0),(-.035,0,0),(-.05,0,0)],[(0,0,0),(0,0,.008),(0,0,0),(0,0,-.003),(0,0,0)]),frames)
        elif clip in ["walk","run"]:
            bob = .018 if clip == "walk" else .038
            pitch = -.11 if clip == "walk" else -.22
            add_clip(body,clip,([(pitch,0,-.025),(pitch,0,.025),(pitch,0,-.025),(pitch,0,.025),(pitch,0,-.025)],[(0,0,0),(0,0,bob),(0,0,0),(0,0,bob),(0,0,0)]),frames)
        else:
            add_clip(body,clip,([(-.05,0,0),(.12,0,-.20),(-.32,0,.25),(-.15,0,.08),(-.05,0,0)],zeros),frames)
        for name,obj in limbs.items():
            is_leg = name.startswith("Leg")
            is_arm = name.startswith("Arm")
            sign = 1 if name.endswith("R") else -1
            if clip == "idle":
                rotations = [(0,0,0)]*5
                if is_arm:
                    rotations = [(.035,0,sign*-.035),(.06,0,sign*-.035),(.035,0,sign*-.035),(.01,0,sign*-.035),(.035,0,sign*-.035)]
            elif clip in ["walk","run"]:
                amp = (.38 if clip == "walk" else .70) if is_leg else (.28 if clip == "walk" else .55)
                phase = sign if is_leg else -sign
                rotations = [(amp*phase,0,0),(0,0,0),(-amp*phase,0,0),(0,0,0),(amp*phase,0,0)] if is_leg or is_arm else [(0.12,0,0)]*5
            elif name == "Arm_R":
                rotations = [(0,0,0),(-2.6,0,-.20),(1.1,0,.12),(.62,0,.03),(0,0,0)]
            elif name == "Forearm_R":
                rotations = [(0,0,0),(.8,0,0),(.15,0,0),(.02,0,0),(0,0,0)]
            elif name == "Arm_L":
                rotations = [(0,0,0),(.45,0,.25),(-.40,0,-.12),(-.05,0,0),(0,0,0)]
            else:
                rotations = zeros
            add_clip(obj,clip,(rotations,zeros),frames)
    bpy.context.scene.frame_set(1)
    for obj in [body]+list(limbs.values()):
        for track in obj.animation_data.nla_tracks:
            track.mute = True
        obj.animation_data.nla_tracks[0].mute = False


def side_prism(name, profile, halfwidth, mat, parent):
    verts = [(side*halfwidth,y,z) for side in [-1,1] for y,z in profile]
    n = len(profile)
    faces = [tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    for k in range(n):
        nxt=(k+1)%n
        faces.append((k,nxt,n+nxt,n+k))
    return mesh(name,verts,faces,mat,parent)


def wheel(name, x,y,z, radius, parent):
    p=pivot(name,(x,y,z),parent)
    cylinder(name+"_Tire",(x,y,z),radius,.23,M["black"],p,12,(0,math.pi/2,0))
    side = 1 if x>0 else -1
    cylinder(name+"_Rim",(x+side*.12,y,z),radius*.64,.012,M["chrome"],p,12,(0,math.pi/2,0))
    cylinder(name+"_Hub",(x+side*.132,y,z),radius*.23,.028,M["metal"],p,8,(0,math.pi/2,0))
    for a in range(6):
        rad=a*math.tau/6
        cylinder(name+"_Slot",(x+side*.13,y+math.sin(rad)*radius*.44,z+math.cos(rad)*radius*.44),radius*.07,.017,M["black"],p,6,(0,math.pi/2,0))
    consolidate(p,name+"_Mesh")


def sedan(police=False):
    root=pivot("Police_Sedan" if police else "Sedan")
    paint=material("Police_Paint" if police else "Sedan_Paint",(.71,.73,.67) if police else (.28,.36,.24),.11,.16)
    navy=material("Police_Navy",(.075,.115,.18),.20)
    side_prism("Body",[(-2.05,.36),(2.05,.36),(2.09,.61),(1.96,.77),(1.0,.81),(-1.50,.80),(-2.09,.68)],.90,paint,root)
    box("Lower_Trim",(0,0,.38),(1.85,4.08,.105),M["black"],root,.02)
    side_prism("Cabin",[(-1.22,.81),(.98,.81),(.61,1.39),(-.75,1.42)],.75,paint,root)
    # Front is Blender +Y, which GLB converts to Godot -Z.
    mesh("Windshield",[(-.706,.98,.85),(.706,.98,.85),(.676,.635,1.354),(-.676,.635,1.354)],[(0,1,2,3)],M["glass"],root)
    mesh("Rear_Glass",[(-.706,-1.225,.845),(.706,-1.225,.845),(.676,-.772,1.359),(-.676,-.772,1.359)],[(0,3,2,1)],M["glass"],root)
    for side in [-1,1]:
        x=side*.753
        mesh("Glass_Front_Side",[(x,.92,.864),(x,.606,1.348),(x,-.025,1.359),(x,-.025,.864)],[(0,1,2,3)],M["glass"],root)
        mesh("Glass_Rear_Side",[(x,-.09,.864),(x,-.09,1.359),(x,-.735,1.36),(x,-1.14,.864)],[(0,1,2,3)],M["glass"],root)
        box("Door_Seam",(side*.907,-.075,.685),(.007,.008,.263),M["black"],root)
        for y in [.31,-.66]:
            box("Door_Handle",(side*.915,y,.775),(.018,.14,.026),M["chrome"],root,.005)
        box("Side_Trim",(side*.917,0,.55),(.024,3.70,.049),M["chrome"],root,.004)
        box("Mirror_Stem",(side*.91,.60,.92),(.16,.027,.018),M["black"],root)
        box("Mirror",(side*1.00,.61,.95),(.079,.126,.087),paint,root,.015)
        for y,label in [(1.29,"F"),(-1.31,"R")]:
            wheel("Wheel_"+label+("R" if side>0 else "L"),side*.895,y,.32,.32,root)
        box("Front_Headlight",(side*.635,2.093,.655),(.354,.024,.15),M["headlight"],root,.007)
        box("Front_Indicator",(side*.835,2.07,.655),(.064,.047,.13),M["orange"],root,.005)
        box("Rear_Taillight",(side*.641,-2.099,.622),(.346,.028,.139),M["red"],root,.006)
        box("Rear_Reverse",(side*.478,-2.12,.622),(.064,.012,.115),M["plate"],root)
        # Hard dark cuts outline arches even at gameplay distance.
        for y in [1.29,-1.31]:
            mesh("Wheel_Arch",[(side*.912,y-.36,.4),(side*.912,y-.31,.62),(side*.912,y+.31,.62),(side*.912,y+.36,.4)],[(0,1,2,3)],M["black"],root)
    box("Front_Bumper",(0,2.135,.44),(1.84,.099,.112),M["chrome"],root,.018)
    box("Rear_Bumper",(0,-2.14,.43),(1.84,.105,.115),M["chrome"],root,.018)
    box("Grille",(0,2.108,.653),(.61,.032,.165),M["black"],root,.003)
    for n in range(8):
        box("Grille_Slat",(-.259+n*.074,2.132,.653),(.026,.012,.125),M["chrome"],root)
    box("Badge",(0,2.145,.65),(.046,.008,.052),M["plate"],root)
    for y in [2.19,-2.198]:
        box("License_Plate",(0,y,.438),(.427,.012,.073),M["plate"],root)
        text("License_Characters","AM 7 PK 2",(0,y+(.007 if y>0 else -.007),.438),.042,M["black"],(math.pi/2,0,math.pi if y>0 else 0),root)
    cylinder("Exhaust",(.58,-2.155,.302),.038,.205,M["metal"],root,8,(math.pi/2,0,0))
    cylinder("Exhaust_Hole",(.58,-2.26,.302),.027,.009,M["black"],root,8,(math.pi/2,0,0))
    for side in [-1,1]:
        box("Wiper",(side*.29,.905,.973),(.027,.24,.012),M["black"],root,.003,(.59,0,side*.11))
    box("Hood_Seam",(0,1.15,.817),(1.42,.018,.009),M["black"],root)
    box("Hood_Center_Scuff",(-.45,1.65,.796),(.21,.18,.009),M["rust"],root,.01)
    if police:
        box("Lightbar_Base",(0,-.035,1.459),(1.16,.22,.042),M["black"],root,.015)
        for side in [-1,1]:
            box("Lightbar_Blue" if side<0 else "Lightbar_Red",(side*.34,-.035,1.56),(.40,.213,.18),M["blue"] if side<0 else M["police_red"],root,.034)
            box("Police_Stripe",(side*.912,0,.704),(.02,3.69,.103),navy,root)
            text("Police_Door_Mark","POLICIA",(side*.929,.23,.676),.10,M["plate"],(math.pi/2,0,side*math.pi/2),root)
    vehicle_groups(root)
    return root


def minibus():
    root=pivot("Minibus")
    paint=material("Minibus_Paint_Faded",(.65,.56,.31),.14,.08)
    blue=material("Minibus_Belt",(.12,.19,.21),.24)
    box("Body",(0,0,1.21),(1.89,4.64,1.70),paint,root,.105)
    box("Roof",(0,-.12,2.104),(1.79,4.23,.23),paint,root,.07)
    box("Front_Hood",(0,2.28,.82),(1.78,.35,.58),paint,root,.05)
    box("Windshield",(0,2.329,1.65),(1.56,.014,.61),M["glass"],root,.015)
    box("Windshield_Divider",(0,2.347,1.65),(.04,.02,.63),paint,root)
    for side in [-1,1]:
        x=side*.952
        for y in [1.42,.38,-.68,-1.64]:
            box("Glass_Side",(x,y,1.70),(.018,.86,.60),M["glass"],root,.014)
            box("Window_Chrome",(x+side*.012,y,1.395),(.017,.86,.016),M["chrome"],root)
        box("Belt",(x,0,1.23),(.026,4.45,.16),blue,root)
        for y in [1.46,-1.46]:
            wheel("Wheel_"+("F" if y>0 else "R")+("R" if side>0 else "L"),side*.904,y,.345,.345,root)
        for y in [1.82,.97]:
            box("Door_Seam",(x+side*.014,y,1.32),(.007,.015,1.43),M["black"],root)
        box("Door_Handle",(x+side*.018,1.03,1.31),(.028,.155,.04),M["black"],root,.006)
        box("Mirror_Stem",(side*1.045,2.11,1.65),(.23,.032,.027),M["black"],root)
        box("Mirror",(side*1.153,2.11,1.64),(.074,.15,.23),M["black"],root,.008)
        cylinder("Front_Headlight",(side*.63,2.47,.94),.112,.015,M["headlight"],root,12,(math.pi/2,0,0))
        box("Front_Indicator",(side*.803,2.436,.937),(.066,.02,.115),M["orange"],root,.005)
        box("Rear_Taillight",(side*.769,-2.345,.94),(.16,.025,.245),M["red"],root,.006)
        box("Rear_Glass",(side*.42,-2.329,1.73),(.699,.015,.563),M["glass"],root,.013)
        box("Rear_Door_Handle",(side*.17,-2.354,1.13),(.096,.019,.032),M["chrome"],root)
        for y in [-2.1,-1.05,0,1.08]:
            box("Vertical_Rib",(side*.958,y,.807),(.023,.03,.50),paint,root)
    box("Grille",(0,2.475,.71),(.91,.027,.227),M["black"],root)
    for n in range(4):
        box("Grille_Horizontal",(0,2.49,.627+n*.058),(.88,.015,.016),M["chrome"],root)
    box("Front_Bumper",(0,2.49,.47),(1.93,.13,.13),M["black"],root,.016)
    box("Rear_Bumper",(0,-2.38,.48),(1.93,.13,.13),M["black"],root,.016)
    box("Rear_Door_Seam",(0,-2.333,1.40),(.018,.018,1.45),M["black"],root)
    box("Route_Board",(0,2.345,2.035),(.84,.02,.136),M["plate"],root)
    text("Route_Number","7PK2",(0,2.362,2.035),.105,M["black"],(math.pi/2,0,math.pi),root)
    box("Plate",(0,2.57,.48),(.39,.018,.081),M["plate"],root)
    text("Plate_Characters","AM 160",(0,2.582,.48),.047,M["black"],(math.pi/2,0,math.pi),root)
    cylinder("Exhaust",(.53,-2.405,.337),.039,.18,M["metal"],root,8,(math.pi/2,0,0))
    for y in [-1.62,-.50,.64]:
        box("Roof_Rib",(0,y,2.23),(1.66,.021,.019),M["seam"],root)
    vehicle_groups(root)
    return root


def monument():
    root=pivot("Stone_Monument")
    box("Foundation",(0,0,.085),(2.4,1.7,.17),M["granite_dark"],root,.023)
    box("Lower_Step",(0,0,.227),(2.04,1.38,.17),M["granite"],root,.017)
    box("Plinth",(0,0,.65),(1.70,1.11,.75),M["granite_dark"],root,.028)
    box("Plinth_Cap",(0,0,1.07),(1.86,1.27,.19),M["granite"],root,.013)
    mesh("Granite_Shard",[(-.72,-.35,1.16),(.73,-.35,1.16),(.73,.35,1.16),(-.72,.35,1.16),(-.70,-.26,3.07),(.27,-.22,3.62),(.68,-.18,3.21),(.73,.20,3.18),(.24,.28,3.55),(-.70,.26,3.02)],[(0,1,2,3),(0,4,5,6,1),(1,6,7,2),(2,7,8,9,3),(3,9,4,0),(4,9,8,5),(5,8,7,6)],M["granite"],root)
    box("Relief_Hammer_Handle",(-.08,.365,2.15),(.13,.07,1.30),M["granite_dark"],root,.012,(0,-.20,0))
    box("Relief_Hammer_Head",(-.22,.38,2.775),(.87,.14,.33),M["granite_dark"],root,.037)
    box("Inscription_Plate",(0,.568,.69),(1.34,.015,.37),M["granite"],root,.003)
    text("Inscription","KOROSTYSHIV",(0,.583,.75),.113,M["granite_dark"],(math.pi/2,0,math.pi),root)
    text("Date","1899 / 2001",(0,.583,.595),.068,M["granite_dark"],(math.pi/2,0,math.pi),root)
    for x,y in [(-.73,.59),(.74,.57),(-.72,-.62)]:
        ico("Chipped_Stone",(x,y,.17),(.13,.16,.075),M["granite"],root,1)
    consolidate(root,"Monument_Mesh")
    return root


def export(name, root):
    bpy.context.scene.frame_set(1)
    # Export all named NLA tracks as four reusable clips.
    for obj in bpy.data.objects:
        if obj.animation_data:
            for track in obj.animation_data.nla_tracks:
                track.mute = False
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / (name+".blend")))
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+".glb")), export_format="GLB", use_selection=False,
        export_yup=True, export_animations=True, export_animation_mode="NLA_TRACKS",
        export_nla_strips=True, export_anim_slide_to_zero=True,
        export_force_sampling=True, export_optimize_animation_size=True,
        export_materials="EXPORT", export_cameras=False, export_lights=False)
    blob=(OUT/(name+".glb")).read_bytes()
    length,kind=struct.unpack_from("<II",blob,12)
    doc=json.loads(blob[20:20+length])
    clips=[a.get("name") for a in doc.get("animations",[])]
    stats={"asset":name,"nodes":len(doc.get("nodes",[])),"meshes":len(doc.get("meshes",[])),"animations":clips,
           "bytes":len(blob),"image_count":len(doc.get("images",[]))}
    print("ASSET_VERIFIED",json.dumps(stats),flush=True)
    if name in ["podro","npc_worker","edik","serhiy","cyber","podrina"]:
        assert set(["idle","walk","run","attack"]).issubset(set(clips)), clips
    return stats


def build(variants_only=False):
    manifest=SOURCE/"model_manifest.json"
    records=json.loads(manifest.read_text()) if variants_only and manifest.exists() else []
    # Podro is built by tools/build_podro.py.
    builders=[] if variants_only else [("npc_worker",lambda:human(True)),("hammer",make_hammer),("sedan",sedan),("police_sedan",lambda:sedan(True)),("minibus",minibus),("stone_monument",monument)]
    builders += [(name,lambda variant=name:human(True,variant)) for name in ["edik","serhiy","cyber","podrina"]]
    for name,builder in builders:
        fresh()
        root=builder()
        records=[record for record in records if record["asset"]!=name]
        records.append(export(name,root))
    manifest.write_text(json.dumps(records,indent=2)+"\n")


def preview(name):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE/(name+".blend")))
    scene = bpy.context.scene
    for obj in scene.objects:
        if obj.animation_data:
            for track in obj.animation_data.nla_tracks:
                track.mute = track.name != "idle"
    scene.frame_set(1)
    box("Preview_Ground",(0,0,-.045),(16,16,.08),material("Preview_Ground",(.17,.18,.15),.0))
    is_human = name in ["podro","npc_worker","edik","serhiy","cyber","podrina"]
    bpy.ops.object.camera_add(location=(3.5,5.5,2.7) if is_human else (5.6,7.2,4.3))
    camera=bpy.context.object
    target=Vector((0,0,.90 if is_human else 1.0))
    camera.rotation_euler=(target-camera.location).to_track_quat("-Z","Y").to_euler()
    camera.data.type="ORTHO"
    camera.data.ortho_scale=2.45 if is_human else 6.5
    scene.camera=camera
    bpy.ops.object.light_add(type="AREA",location=(-3,4,6))
    light=bpy.context.object
    light.data.energy=600
    light.data.size=5
    light.rotation_euler=(Vector((0,0,1))-light.location).to_track_quat("-Z","Y").to_euler()
    scene.world.color=(.22,.22,.22)
    scene.render.engine="CYCLES"
    scene.cycles.samples=24
    scene.render.resolution_x=640
    scene.render.resolution_y=640
    scene.render.resolution_percentage=100
    scene.view_settings.view_transform="Standard"
    scene.render.filepath=str(SOURCE/(name+"_preview.png"))
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    import sys
    if "--preview" in sys.argv:
        preview(sys.argv[sys.argv.index("--preview")+1])
    else:
        build(variants_only="--variants-only" in sys.argv)
