"""Podro for Klad Theft Hummer: GTA III style ped built on a CC0 human base.

Inputs (CC0, Quaternius, vendored in assets/source/third_party/, see README.md there):
  Universal Base Characters  -> Superhero_Male_FullBody.gltf (anatomy, UE-style 65 bone rig)
  Universal Animation Library -> UAL1_Standard.glb (same rig; idle, jog, sprint, sword swing ...)
Texture: assets/source/reference/podro_texture_sheet.png (outfit + face sheet from the author).

Pipeline: weld UV-split verts, close the eye sockets, smooth the muscles away, slim the limbs,
inflate a cloth layer, swap bare feet for boots, add collar and hammer, decimate to ~2.3k tris,
project UVs onto the sheet panels, transfer the animations, export one GLB.

Run from the workspace root:
  blender --background -noaudio --factory-startup --python tools/build_podro.py [-- --preview]
"""

import json
import math
import struct
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets/source"
OUT = ROOT / "assets/models"
SHEET_PATH = SRC / "reference/podro_texture_sheet.png"
THIRD = SRC / "third_party"
ATLAS = 512
SHEET = 1254
TARGET_TRIS = 2300
MODEL_SCALE = .95  # 1.82 m base -> 1.73 m, Podro is not tall

CLIPS = {  # exported name: library action
    "idle": "Idle_Loop",
    "walk": "Jog_Fwd_Loop",
    "run": "Sprint_Loop",
    "stroll": "Walk_Loop",
    "attack": "Sword_Attack",
    "punch": "Punch_Cross",
    "hit": "Hit_Chest",
    "death": "Death01",
    "drive": "Driving_Loop",
    "jump_start": "Jump_Start",
    "jump_air": "Jump_Loop",
    "jump_land": "Jump_Land",
    "talk": "Idle_Talking_Loop",
    "pickup": "PickUp_Table",
    "interact": "Interact",
}
FIST_FROM = "Sword_Idle"

P = {  # panels on the texture sheet (x0, y0, x1, y1)
    "jacket_front": (141, 320, 490, 735),
    "jacket_back": (490, 332, 891, 740),
    "sleeve": (10, 366, 156, 724),
    "pants_side": (11, 744, 202, 1244),
    "pants_front": (290, 744, 441, 1246),
    "pants_back_l": (452, 744, 610, 1245),
    "pants_back_r": (628, 744, 789, 1245),
    "boot_r": (987, 986, 1184, 1222),
    "boot_l": (795, 985, 983, 1221),
    "sole": (931, 854, 1033, 1112),
    "hand": (4, 163, 166, 346),
    "face": (588, 2, 1252, 465),
    "head_back": (1040, 335, 1248, 570),
    "hammer": (1026, 578, 1248, 737),
}

PART_BODY, PART_COLLAR, PART_BOOT, PART_HAMMER = range(4)
XV, YV, ZV = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


def arg(name, default=None):
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return a[a.index(name) + 1] if name in a else default


def px_uv(px, py):
    return (px / SHEET, 1 - py / SHEET)


SKIN_MASK = None  # sheet pixels that are skin, filled in by load_skin_mask()


def load_skin_mask():
    import numpy as np
    global SKIN_MASK
    img = bpy.data.images.load(str(SHEET_PATH))
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3]
    bpy.data.images.remove(img)
    SKIN_MASK = (a[..., 0] > .30) & (a[..., 0] - a[..., 2] > .08)


def on_cloth(px, py, box):
    """Slide a cloth sample down (and toward the panel centre) off any neighbouring skin."""
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    for _ in range(80):
        if not SKIN_MASK[int(min(max(py, 0), SHEET - 1)), int(min(max(px, 0), SHEET - 1))]:
            break
        py = min(py + 3, y1 - 2)
        px += (cx - px) * .02
    return px, py


def clamp_box(px, py, box, pad=2):
    x0, y0, x1, y1 = box
    return min(max(px, x0 + pad), x1 - pad), min(max(py, y0 + pad), y1 - pad)


def interp(x, xs, ys):
    if x <= xs[0]:
        return ys[0]
    for i in range(len(xs) - 1):
        if x <= xs[i + 1]:
            return ys[i] + (ys[i + 1] - ys[i]) * (x - xs[i]) / (xs[i + 1] - xs[i])
    return ys[-1]


# ---------------------------------------------------------------- base character

def import_base(path):
    bpy.ops.import_scene.gltf(filepath=path)
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = None
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o.parent == rig and len(o.data.polygons) > 5000:
            body = o
        elif o.type == "MESH":
            bpy.data.objects.remove(o)  # eyebrows, eyeballs, helper sphere
    rig.name = "PodroRig"
    body.name = "Podro"
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    return rig, body


def dominant(v, deform, names):
    best, bw = None, 0
    for gi, w in v[deform].items():
        if w > bw:
            best, bw = names[gi], w
    return best or ""


def group_weight(v, deform, names, prefixes):
    return sum(w for gi, w in v[deform].items() if names[gi].startswith(prefixes))


HEAD_LIKE = ("Head", "neck_01")
HAND_LIKE = ("hand_", "index_", "middle_", "ring_", "pinky_", "thumb_")


def reshape_body(body):
    """Muscle suit -> a slim man in a softshell and cargos."""
    names = [g.name for g in body.vertex_groups]
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    deform = bm.verts.layers.deform.active
    # Eye sockets are the only holes left after welding.
    edges = [e for e in bm.edges if e.is_boundary]
    print("HOLE_EDGES", len(edges), flush=True)
    bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])

    cloth = [v for v in bm.verts if not dominant(v, deform, names).startswith(HEAD_LIKE + HAND_LIKE)]
    for _ in range(10):
        bmesh.ops.smooth_vert(bm, verts=cloth, factor=.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)

    for v in bm.verts:
        p = v.co
        arm = group_weight(v, deform, names, ("upperarm", "lowerarm"))
        if arm > 0:  # T-pose: arms lie along X at y=.069, z=1.456
            k = 1 - .14 * arm
            p.y = .069 + (p.y - .069) * k
            p.z = 1.456 + (p.z - 1.456) * k
        leg = group_weight(v, deform, names, ("thigh", "calf"))
        if leg > 0:
            cx, cy = leg_center(p)
            k = 1 - .10 * leg
            p.x = cx + (p.x - cx) * k
            p.y = cy + (p.y - cy) * k
        chest = group_weight(v, deform, names, ("spine_02", "spine_03", "clavicle"))
        if chest > 0:
            p.x *= 1 - .07 * chest
            p.y = .01 + (p.y - .01) * (1 - .06 * chest)

    bm.normal_update()
    offsets = {}
    for v in bm.verts:
        dom = dominant(v, deform, names)
        if dom.startswith(HEAD_LIKE + HAND_LIKE):
            continue
        if dom.startswith(("foot", "ball")):
            d = .0
        elif dom.startswith(("upperarm", "lowerarm")):
            d = .020
        elif dom.startswith(("thigh", "calf")):
            d = .022 + (.008 if v.co.z < .45 else 0)  # cargo legs bag around the shins
        else:
            d = .024
        offsets[v] = v.normal * d
    for v, o in offsets.items():
        v.co += o

    feet = [v for v in bm.verts if dominant(v, deform, names).startswith(("foot", "ball")) and v.co.z < .125]
    bmesh.ops.delete(bm, geom=feet, context="VERTS")
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()


def decimate(body, target):
    tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
    mod = body.modifiers.new("Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = target / tris
    mod.use_symmetry = True
    mod.symmetry_axis = "X"
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_move_to_index(modifier="Decimate", index=0)
    bpy.ops.object.modifier_apply(modifier="Decimate")


# ---------------------------------------------------------------- added parts (collar, boots, hammer)

def ring_points(center, a1, a2, rx, ry, n, power=2.0, shape=None):
    pts = []
    for k in range(n):
        t = 2 * math.pi * k / n
        c, s = math.cos(t), math.sin(t)
        e = 2 / power
        x = math.copysign(abs(c) ** e, c) * rx
        y = math.copysign(abs(s) ** e, s) * ry
        dz = 0.0
        if shape:
            x, y, dz = shape(t, x, y)
        pts.append(Vector(center) + a1 * x + a2 * y + Vector((0, 0, dz)))
    return pts


class PartBuilder:
    def __init__(self, rig, name):
        self.bm = bmesh.new()
        self.deform = self.bm.verts.layers.deform.new()
        self.groups = [b.name for b in rig.data.bones]
        self.name = name

    def vert(self, co, weights):
        v = self.bm.verts.new(co)
        total = sum(weights.values())
        for bone, w in weights.items():
            v[self.deform][self.groups.index(bone)] = w / total
        return v

    def face(self, verts, outward, part):
        f = self.bm.faces.new(verts)
        f.normal_update()
        if f.normal.dot(outward) < 0:
            f.normal_flip()
        f.material_index = part
        return f

    def loft(self, rings, n, a1, a2, part, power=2.0, cap_start=None, cap_end=None):
        rows = [[self.vert(p, r["w"]) for p in ring_points(r["c"], a1, a2, r["rx"], r["ry"], n, r.get("power", power), r.get("shape"))]
                for r in rings]
        for i in range(len(rings) - 1):
            c0, c1 = Vector(rings[i]["c"]), Vector(rings[i + 1]["c"])
            axis = (c1 - c0).normalized()
            for k in range(n):
                vs = [rows[i][k], rows[i][(k + 1) % n], rows[i + 1][(k + 1) % n], rows[i + 1][k]]
                mid = sum((v.co for v in vs), Vector()) / 4
                self.face(vs, mid - (c0 + axis * (mid - c0).dot(axis)), part)
        for cap, row, ring, other in ((cap_start, 0, rings[0], rings[1]), (cap_end, -1, rings[-1], rings[-2])):
            if cap is None:
                continue
            axis = (Vector(ring["c"]) - Vector(other["c"])).normalized()
            tip = self.vert(Vector(ring["c"]) + axis * cap, ring["w"])
            for k in range(n):
                self.face([rows[row][k], rows[row][(k + 1) % n], tip], axis, part)

    def to_object(self, rig, mat_count):
        mesh = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.collection.objects.link(obj)
        for g in self.groups:
            obj.vertex_groups.new(name=g)
        obj.parent = rig
        for _ in range(mat_count):
            mesh.materials.append(None)
        return obj


def lerp_w(a, b, t):
    out = {}
    for k, v in a.items():
        out[k] = out.get(k, 0) + v * (1 - t)
    for k, v in b.items():
        out[k] = out.get(k, 0) + v * t
    return out


def build_collar(B):
    S3, N = {"spine_03": 1}, {"neck_01": 1}

    def shape(drop, bulge):
        def f(t, x, y):
            front = max(0.0, -math.sin(t)) ** 2  # sin<0 is -Y, the front
            back = max(0.0, math.sin(t))
            return x, y * (1 + bulge * back), -drop * front
        return f

    spec = [  # z, rx, ry, cy, weights, front drop, back bulge (hood rolled on the back)
        (1.455, .135, .118, .030, S3, 0, 0),
        (1.530, .108, .100, .036, lerp_w(S3, N, .5), .01, .30),
        (1.612, .090, .087, .034, N, .045, .22),
        (1.560, .066, .066, .030, N, .030, 0),
    ]
    rings = [dict(c=(0, cy, z), rx=rx, ry=ry, w=w, shape=shape(d, b)) for z, rx, ry, cy, w, d, b in spec]
    B.loft(rings, 14, XV, YV, PART_COLLAR, power=2.3)


def boot_frame(s):
    """s=+1 left (+X), -1 right. Toes point -Y, turned out a little."""
    yaw = math.radians(9) * s
    fwd = Vector((math.sin(yaw), -math.cos(yaw), 0))
    out = Vector((math.cos(yaw), math.sin(yaw), 0)) * s
    base = Vector((s * .114, .072, 0))
    return fwd, out, base


def build_boot(B, s):
    side = "l" if s > 0 else "r"
    F, Bl, C = {f"foot_{side}": 1}, {f"ball_{side}": 1}, {f"calf_{side}": 1}
    fwd, out, base = boot_frame(s)
    shaft = [dict(c=base + Vector((0, 0, .215)), rx=.060, ry=.064, w=lerp_w(C, F, .3)),
             dict(c=base + Vector((0, 0, .125)), rx=.058, ry=.066, w=F)]
    B.loft(shaft, 9, out, fwd, PART_BOOT, power=2.4)
    spec = [  # along, z centre, rx, ry, weights
        (-.090, .060, .050, .060, F), (-.060, .084, .058, .084, F), (.000, .082, .061, .082, F),
        (.070, .062, .063, .062, F), (.140, .048, .062, .048, lerp_w(F, Bl, .5)),
        (.190, .041, .054, .041, Bl), (.214, .031, .035, .029, Bl),
    ]
    rings = [dict(c=base + fwd * a + Vector((0, 0, z)), rx=rx, ry=ry, w=w) for a, z, rx, ry, w in spec]
    B.loft(rings, 9, out, ZV, PART_BOOT, power=3.2, cap_start=.006, cap_end=.008)


def hammer_frame(rig):
    """Grip in the T-pose right fist: handle along the knuckle line, head forward."""
    hb = rig.data.bones["hand_r"]
    head = rig.matrix_world @ hb.head_local
    along = (rig.matrix_world.to_3x3() @ (hb.tail_local - hb.head_local)).normalized()
    grip = head + along * .085 + Vector((0, 0, -.018))
    # Tilted toward the fingers, so the hanging hand carries it forward-down, not like a knife.
    hdir = (Vector((0, -1, 0)) * math.cos(math.radians(40)) + along * math.sin(math.radians(40))).normalized()
    return grip, hdir


def build_hammer(B, rig):
    H = {"hand_r": 1}
    grip, hdir = hammer_frame(rig)
    side = ZV.cross(hdir).normalized()
    perp = hdir.cross(side).normalized()  # head long axis, perpendicular to the handle
    start, end = grip - hdir * .05, grip + hdir * .34
    handle = [dict(c=start, rx=.015, ry=.016, w=H), dict(c=grip + hdir * .2, rx=.013, ry=.014, w=H),
              dict(c=end, rx=.016, ry=.017, w=H)]
    B.loft(handle, 6, side, perp, PART_HAMMER, cap_start=.006)
    head_c = end + hdir * .012
    spec = [(-.085, .025, .025), (-.062, .029, .029), (-.036, .023, .023), (.018, .022, .026), (.055, .012, .023), (.083, .004, .019)]
    rings = [dict(c=head_c + perp * d, rx=rx, ry=ry, w=H) for d, rx, ry in spec]
    B.loft(rings, 6, side, hdir, PART_HAMMER, power=3.5, cap_start=0, cap_end=0)


# ---------------------------------------------------------------- UV projection onto the sheet

class Landmarks:
    def __init__(self, body):
        names = [g.name for g in body.vertex_groups]
        verts = body.data.vertices
        head = [v.co for v in verts if any(names[g.group] == "Head" and g.weight > .5 for g in v.groups)]
        self.top = max(p.z for p in head)
        front = [p for p in head if abs(p.x) < .015 and p.y < -.03]
        self.chin = min(p.z for p in front)
        self.eye = self.chin + (self.top - self.chin) * .556  # sheet: eyes 209 px over chin, 167 under top
        band = [p for p in head if abs(p.z - self.eye) < .015]
        self.head_cy = (max(p.y for p in band) + min(p.y for p in band)) / 2
        torso = [v.co for v in verts if any(names[g.group].startswith("spine_0") and g.weight > .5 for g in v.groups)]
        self.chest_hw = max(abs(p.x) for p in torso if abs(p.z - 1.25) < .04)
        print("LANDMARKS", dict(top=round(self.top, 3), chin=round(self.chin, 3), eye=round(self.eye, 3),
                                head_cy=round(self.head_cy, 3), chest_hw=round(self.chest_hw, 3)), flush=True)


# The sheet's face unwrap borders the right shoulder of the jacket back: stay clear of it.
BACK_SAFE = (505, 332, 838, 740)
HEM_Z = .87
SHOULDER_Z = 1.47
COLLAR_Z = 1.63


def face_class(f, deform, names):
    acc = {}
    for v in f.verts:
        for gi, w in v[deform].items():
            n = names[gi]
            key = ("head" if n in HEAD_LIKE else
                   "hand" if n.startswith(HAND_LIKE) else
                   "arm" if n.startswith(("upperarm", "lowerarm")) else
                   "leg" if n.startswith(("thigh", "calf")) else
                   "torso")
            acc[key] = acc.get(key, 0) + w
    return max(acc, key=acc.get) if acc else "torso"


def uv_torso(n, co, L):
    if co.z < HEM_Z:
        return uv_pants(n, co, L, pelvis=True)
    if n.y <= .05:
        px = 315.5 + co.x * (174 / (L.chest_hw + .01))
        py = interp(co.z, [HEM_Z, SHOULDER_Z, COLLAR_Z], [735, 395, 322])
        return px_uv(*on_cloth(*clamp_box(px, py, P["jacket_front"]), P["jacket_front"]))
    px = 690 - co.x * (150 / (L.chest_hw + .01))
    py = interp(co.z, [HEM_Z, SHOULDER_Z, COLLAR_Z], [740, 400, 334])
    return px_uv(*on_cloth(*clamp_box(px, py, BACK_SAFE), BACK_SAFE))


def uv_collar(n, co, L):
    if n.y <= 0:
        px = 315.5 + co.x * 760
        py = interp(co.z, [1.45, COLLAR_Z], [395, 322])
        return px_uv(*on_cloth(*clamp_box(px, py, P["jacket_front"]), P["jacket_front"]))
    px = 690 - co.x * 820
    py = interp(co.z, [1.45, COLLAR_Z], [445, 336])
    return px_uv(*on_cloth(*clamp_box(px, py, BACK_SAFE), BACK_SAFE))


def sleeve_u(co):
    a = math.degrees(math.atan2(-(co.y - .069), co.z - 1.456))  # 0 top (outer when hanging), +90 front
    return .5 + a / 360


def uv_arm(n, co, L, u):
    x0, y0, x1, y1 = P["sleeve"]
    t = (abs(co.x) - .19) / (.70 - .19)
    px = x0 + u * (x1 - x0) if co.x < 0 else x1 - u * (x1 - x0)
    py = y0 + t * (y1 - y0)
    return px_uv(*on_cloth(*clamp_box(px, py, P["sleeve"], 1), P["sleeve"]))


def uv_hand(n, co, L):
    x0, y0, x1, y1 = P["hand"]
    t = (abs(co.x) - .70) / (.95 - .70)
    lat = (co.y - .065) * (1 if co.x > 0 else -1)
    px = (x0 + x1) / 2 + lat * 1300
    py = y0 + 6 + t * (y1 - y0 - 10)
    return px_uv(*clamp_box(px, py, P["hand"]))


def leg_center(co):
    cx = .114 if co.x > 0 else -.114
    cy = .036 if co.z > .54 else .036 + (.54 - co.z) / .456 * .052
    return cx, cy


def uv_pants(n, co, L, pelvis=False):
    cx, cy = leg_center(co)
    s = 1 if co.x > 0 else -1  # +1 character left
    py = interp(co.z, [1.02, .17], [746, 1244])
    o = (co.x - cx) * s  # + outward
    fwd = -(co.y - cy)
    if not pelvis and n.x * s > .6:
        px = 106 + fwd * 950 * (-s)
        return px_uv(*clamp_box(px, py, P["pants_side"]))
    if n.y <= 0:
        return px_uv(*clamp_box(365.5 + o * 820, py, P["pants_front"]))
    if s > 0:
        return px_uv(*clamp_box(531 - o * 860, py, P["pants_back_l"]))
    return px_uv(*clamp_box(708 + o * 860, py, P["pants_back_r"]))


def head_px(co, L):
    phi = math.degrees(math.atan2(-co.x, -(co.y - L.head_cy)))  # 0 front, +90 character right
    if phi >= 0:
        px = interp(phi, [0, 55, 90, 112], [961, 815, 640, 592])
    else:
        px = interp(-phi, [0, 55, 90, 112], [961, 1100, 1205, 1250])
    py = interp(co.z, [L.chin - .045, L.chin, L.eye, L.top - .03, L.top], [460, 380, 171, 30, 4])
    return px, py


def head_front(cen, L):
    phi = abs(math.degrees(math.atan2(-cen.x, -(cen.y - L.head_cy))))
    return phi < 110 and cen.z < L.top - .006


def uv_head_back(co, L):
    px = 1144 - co.x * 1250
    py = interp(co.z, [L.chin - .02, L.top], [568, 338])
    return px_uv(*clamp_box(px, py, P["head_back"]))


def uv_boot(n, co, s):
    fwd, out, base = boot_frame(s)
    rel = co - base
    along = rel.dot(fwd)
    if n.z < -.75:
        px = 982 + rel.dot(out) * 900 * s
        py = 1110 - (along + .09) / .305 * 254
        return px_uv(*clamp_box(px, py, P["sole"]))
    py = interp(co.z, [0, .22], [1215, 992])
    t = .05 + .9 * (along + .09) / .305
    if s < 0:  # character right boot, seen from its outside: toe to the right
        return px_uv(*clamp_box(990 + t * 192, py, P["boot_r"]))
    return px_uv(*clamp_box(980 - t * 183, py, P["boot_l"]))


def project_uvs(obj, L, grip, hdir):
    names = [g.name for g in obj.vertex_groups]
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    deform = bm.verts.layers.deform.active
    uvl = bm.loops.layers.uv.verify()
    hx0, hy0, hx1, hy1 = P["hammer"]
    hmid = (hy0 + hy1) / 2
    for f in bm.faces:
        n = f.normal
        cen = f.calc_center_median()
        part = f.material_index
        if part == PART_HAMMER:
            wood = (cen - grip).dot(hdir) < .33
            for i, l in enumerate(f.loops):
                u = (i + 1) / len(f.loops)
                l[uvl].uv = px_uv(hx0 + 20 + u * 150, (hy0 + 10 + u * 50) if wood else (hmid + 10 + u * 50))
        elif part == PART_COLLAR:
            for l in f.loops:
                l[uvl].uv = uv_collar(n, l.vert.co, L)
        elif part == PART_BOOT:
            s = 1 if cen.x > 0 else -1
            for l in f.loops:
                l[uvl].uv = uv_boot(n, l.vert.co, s)
        else:
            cls = face_class(f, deform, names)
            side_neck = abs(math.degrees(math.atan2(-cen.x, -(cen.y - L.head_cy)))) > 62 and cen.z < L.chin + .03
            if cls == "head" and (cen.z < L.chin - .012 or side_neck):
                # neck under the collar: dark jacket lining, never skin
                for l in f.loops:
                    l[uvl].uv = uv_collar(n, l.vert.co, L)
            elif cls == "head":
                front = head_front(cen, L)
                for l in f.loops:
                    l[uvl].uv = px_uv(*clamp_box(*head_px(l.vert.co, L), P["face"])) if front else uv_head_back(l.vert.co, L)
            elif cls == "arm":
                us = [sleeve_u(l.vert.co) for l in f.loops]
                if max(us) - min(us) > .5:  # face straddles the seam under the arm
                    us = [u + 1 if u < .5 else u for u in us]
                    us = [min(u, 1.0) for u in us]
                for l, u in zip(f.loops, us):
                    l[uvl].uv = uv_arm(n, l.vert.co, L, u)
            elif cls == "hand":
                for l in f.loops:
                    l[uvl].uv = uv_hand(n, l.vert.co, L)
            elif cls == "leg":
                for l in f.loops:
                    l[uvl].uv = uv_pants(n, l.vert.co, L)
            else:
                for l in f.loops:
                    l[uvl].uv = uv_torso(n, l.vert.co, L)
        f.material_index = 0
    bm.to_mesh(obj.data)
    bm.free()


# ---------------------------------------------------------------- atlas

def build_atlas_image():
    """Sheet -> 512 px atlas: fill black gaps from panel edges (no dark seams), paint the hammer."""
    import numpy as np
    src = bpy.data.images.load(str(SHEET_PATH))
    w, h = src.size
    a = np.array(src.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3].copy()
    bpy.data.images.remove(src)
    known = a.mean(-1) > 9 / 255
    x0, y0, x1, y1 = P["hammer"]
    rng = np.random.default_rng(5)
    mid = (y0 + y1) // 2
    ww = x1 - x0
    wood = np.ones((mid - y0, ww, 3), np.float32) * np.array([.46, .30, .17])
    wood += (np.sin(np.arange(ww) * .45)[None, :, None] * .04) + rng.normal(0, .02, (mid - y0, ww, 1))
    steel = np.ones((y1 - mid, ww, 3), np.float32) * np.array([.36, .37, .39]) + rng.normal(0, .03, (y1 - mid, ww, 1))
    steel[rng.random((y1 - mid, ww)) < .05] = (.42, .23, .12)
    a[y0:mid, x0:x1] = wood
    a[mid:y1, x0:x1] = steel
    known[y0:y1, x0:x1] = True
    # Gaps inside cloth panels are cloth, not whatever skin panel sits next door.
    for name in ("jacket_front", "jacket_back", "sleeve", "pants_side", "pants_front", "pants_back_l",
                 "pants_back_r", "boot_r", "boot_l", "sole"):
        bx0, by0, bx1, by1 = P[name]
        region = a[by0:by1, bx0:bx1]
        gap = ~known[by0:by1, bx0:bx1]
        region[gap] = np.median(region[~gap], axis=0) * .8
        known[by0:by1, bx0:bx1] = True
    levels = []
    ca, cw = a * known[..., None], known.astype(np.float32)
    while min(ca.shape[:2]) > 2:
        levels.append((ca, cw))
        hh, wd = ca.shape[0] // 2 * 2, ca.shape[1] // 2 * 2
        ca = ca[:hh:2, :wd:2] + ca[1:hh:2, :wd:2] + ca[:hh:2, 1:wd:2] + ca[1:hh:2, 1:wd:2]
        cw = cw[:hh:2, :wd:2] + cw[1:hh:2, :wd:2] + cw[:hh:2, 1:wd:2] + cw[1:hh:2, 1:wd:2]
    fill = ca / np.maximum(cw, 1e-6)[..., None]
    for la, lw in reversed(levels):
        ys = np.minimum(np.arange(la.shape[0]) // 2, fill.shape[0] - 1)
        xs = np.minimum(np.arange(la.shape[1]) // 2, fill.shape[1] - 1)
        up = fill[ys][:, xs]
        here = la / np.maximum(lw, 1e-6)[..., None]
        t = np.clip(lw, 0, 1)[..., None]
        fill = here * t + up * (1 - t)
    a = np.where(known[..., None], a, fill)
    a = np.clip(a, 0, 1) ** .82  # lift the black cloth for 2001-style vertex lighting
    img = bpy.data.images.new("podro_atlas", w, h, alpha=False)
    img.pixels = np.concatenate([a[::-1], np.ones((h, w, 1), np.float32)], -1).ravel()
    img.scale(ATLAS, ATLAS)
    img.filepath_raw = str(SRC / "podro_atlas.png")
    img.file_format = "PNG"
    img.save()
    img.pack()
    return img


def atlas_material():
    mat = bpy.data.materials.new("Podro_Atlas")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = .9
    bsdf.inputs["Specular IOR Level"].default_value = .12
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = build_atlas_image()
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


# ---------------------------------------------------------------- animation

def channelbag(action):
    from bpy_extras import anim_utils
    return anim_utils.action_get_channelbag_for_slot(action, action.slots[0])


def import_clips(rig, path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    for o in set(bpy.data.objects) - before:
        bpy.data.objects.remove(o)
    lib = {a.name: a for a in bpy.data.actions}
    fist_src = lib[FIST_FROM]
    fist = {}
    for fc in channelbag(fist_src).fcurves:
        bone = fc.data_path.split('"')[1] if '"' in fc.data_path else ""
        if bone.endswith("_r") and bone.startswith(("index", "middle", "ring", "pinky", "thumb")) and "rotation" in fc.data_path:
            fist[(fc.data_path, fc.array_index)] = fc.evaluate(fist_src.frame_range[0])
    rig.animation_data_create()
    for clip, src_name in CLIPS.items():
        act = lib[src_name]
        act.name = clip
        cb = channelbag(act)
        # The right hand grips the hammer in every clip.
        for (path, idx), value in fist.items():
            fc = cb.fcurves.find(path, index=idx)
            if fc:
                cb.fcurves.remove(fc)
            fc = cb.fcurves.new(path, index=idx)
            fc.keyframe_points.insert(act.frame_range[0], value)
            fc.keyframe_points.insert(act.frame_range[1], value)
        track = rig.animation_data.nla_tracks.new()
        track.name = clip
        strip = track.strips.new(clip, int(act.frame_range[0]), act)
        if hasattr(strip, "action_slot") and act.slots:
            strip.action_slot = act.slots[0]
    for a in list(bpy.data.actions):
        if a.name not in CLIPS:
            bpy.data.actions.remove(a)


# ---------------------------------------------------------------- export / preview

def export(rig, tris):
    bpy.ops.wm.save_as_mainfile(filepath=str(SRC / "podro.blend"))
    path = OUT / "podro.glb"
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_yup=True,
                              export_animations=True, export_animation_mode="NLA_TRACKS",
                              export_anim_slide_to_zero=True, export_force_sampling=True,
                              export_cameras=False, export_lights=False, export_materials="EXPORT")
    b = path.read_bytes()
    size = struct.unpack_from("<I", b, 12)[0]
    doc = json.loads(b[20:20 + size])
    clips = [a["name"] for a in doc.get("animations", [])]
    assert all(c in clips for c in CLIPS), clips
    out = dict(asset="podro", triangles=tris, joints=len(doc["skins"][0]["joints"]), animations=clips,
               textures=len(doc.get("images", [])), bytes=len(b))
    (SRC / "podro_manifest.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("PODRO_EXPORTED", json.dumps(out), flush=True)


def preview(rig):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 480, 640
    world = bpy.data.worlds.new("W")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (.32, .33, .35, 1)
    scene.world = world
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.2
    sun.rotation_euler = (math.radians(50), 0, math.radians(150))
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    tracks = rig.animation_data.nla_tracks

    def solo(name):
        for tr in tracks:
            tr.mute = tr.name != name

    def shot(fname, loc, target, lens=60):
        cam.location = loc
        cam.data.lens = lens
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(SRC / fname)
        bpy.ops.render.render(write_still=True)

    # Preview in Blender space: the character faces -Y here.
    solo("idle")
    scene.frame_set(1)
    shot("podro_preview_front.png", (0, -4.6, 1.0), (0, 0, .9))
    shot("podro_preview_three.png", (-2.9, -3.4, 1.3), (0, 0, .9))
    shot("podro_preview_back.png", (1.2, 4.4, 1.1), (0, 0, .9))
    shot("podro_preview_face.png", (-.25, -1.05, 1.6), (0, 0, 1.52), 50)
    for clip, frames in (("walk", (1, 6, 11)), ("run", (1, 5, 9)), ("attack", (1, 12, 18, 24))):
        solo(clip)
        for f in frames:
            scene.frame_set(f)
            shot(f"podro_anim_{clip}_{f:02d}.png", (-3.6, -1.2, 1.0), (0, 0, .9), 55)
    for tr in tracks:
        tr.mute = False


def main():
    ubc = arg("--ubc", str(THIRD / "Superhero_Male_FullBody.gltf"))
    ual = arg("--ual", str(THIRD / "UAL1_Standard.glb"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 30
    rig, body = import_base(ubc)
    reshape_body(body)
    decimate(body, TARGET_TRIS - 520)
    L = Landmarks(body)

    B = PartBuilder(rig, "PodroParts")
    build_collar(B)
    build_boot(B, 1)
    build_boot(B, -1)
    build_hammer(B, rig)
    grip, hdir = hammer_frame(rig)
    parts = B.to_object(rig, 4)
    for _ in range(3):
        body.data.materials.append(None)
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    parts.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    load_skin_mask()
    project_uvs(body, L, grip, hdir)
    body.data.materials.clear()
    body.data.materials.append(atlas_material())
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(55))
    tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
    print("PODRO_TRIS", tris, flush=True)

    import_clips(rig, ual)
    if "--preview" in sys.argv:
        preview(rig)
    # Faces -Y in Blender (+Z in Godot); the game expects -Z forward, so turn the root around.
    rig.rotation_mode = "XYZ"  # the glTF importer leaves objects in quaternion mode
    rig.rotation_euler = (0, 0, math.pi)
    rig.scale = (MODEL_SCALE,) * 3
    export(rig, tris)


main()
