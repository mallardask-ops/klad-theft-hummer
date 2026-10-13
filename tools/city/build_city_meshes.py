"""Bake Korostyshiv into GLB scenes with Blender.

Inputs  assets/source/city/plan_meshes.json   (tools/city/plan_korostyshiv.py)
        data/city/heightfield.bin, data/city/waterlevel.bin, assets/source/city/ground_weights.png
        assets/city/tex/manifest.json         (tools/city/build_city_textures.py)
Outputs assets/city/korostyshiv.glb   chunks named <kind>__<cx>_<cz>; kinds: terrain water roads walks buildings fences bridges col
        assets/city/trees.glb         tree_* meshes for MultiMesh
        assets/source/city/korostyshiv.blend

Materials are named m_<texture> (assets/city/tex/<texture>.png); scripts/city.gd builds the real
materials. Vertex colour carries the building tint and baked shade; on terrain it carries the
grass/dirt/rock/forest splat weights.

Run: blender --background -noaudio --factory-startup --python tools/city/build_city_meshes.py
Coordinates are game coordinates (x east, y up, z south) and are converted to Blender at the end.
"""

import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets/source/city"
DATA = ROOT / "data/city"
OUT = ROOT / "assets/city"
TEX = OUT / "tex"
CHUNK = 400.0
rng = random.Random(4242)

plan = json.loads((SRC / "plan_meshes.json").read_text())
meta = plan["meta"]
TERR = meta["terrain"]
STEP = meta["step"]
NX, NZ = meta["nx"], meta["nz"]
H = np.fromfile(DATA / "heightfield.bin", "<f4").reshape(NZ, NX)
WL = np.fromfile(DATA / "waterlevel.bin", "<f4").reshape(NZ, NX)
TEXM = json.loads((TEX / "manifest.json").read_text())


def hgt(x, z):
    gx = min(max((x - TERR[0]) / STEP, 0), NX - 1.001)
    gz = min(max((z - TERR[1]) / STEP, 0), NZ - 1.001)
    x0, z0 = int(gx), int(gz)
    fx, fz = gx - x0, gz - z0
    # same split as the terrain triangles (diagonal from (0,0) to (1,1))
    h00, h10, h01, h11 = H[z0, x0], H[z0, x0 + 1], H[z0 + 1, x0], H[z0 + 1, x0 + 1]
    if fx >= fz:
        return float(h00 + (h10 - h00) * fx + (h11 - h10) * fz)
    return float(h00 + (h11 - h01) * fx + (h01 - h00) * fz)


def chunk_of(x, z):
    return (int((x - TERR[0]) // CHUNK), int((z - TERR[1]) // CHUNK))


def hexcol(h, k=1.0):
    h = h.lstrip("#")
    return tuple(min(1.0, int(h[i:i + 2], 16) / 255 * k) for i in (0, 2, 4)) + (1.0,)


class Buf:
    def __init__(self):
        self.v, self.f, self.uv, self.col, self.mat = [], [], [], [], []
        self.smooth = False

    def face(self, pts, uvs, mat, cols=None, normal=None):
        if normal is not None:
            a, b, c = pts[0], pts[1], pts[2]
            n = np.cross(np.subtract(b, a), np.subtract(c, a))
            if np.dot(n, normal) < 0:
                pts, uvs = pts[::-1], uvs[::-1]
                cols = cols[::-1] if cols else None
        i = len(self.v)
        self.v.extend(pts)
        self.f.append(tuple(range(i, i + len(pts))))
        self.uv.extend(uvs)
        self.col.extend(cols or [(1, 1, 1, 1)] * len(pts))
        self.mat.append(mat)


bufs = defaultdict(Buf)


def B(kind, x, z):
    cx, cz = chunk_of(x, z)
    return bufs[f"{kind}__{cx}_{cz}"]


# ---------------------------------------------------------------- terrain and water

def terrain():
    W = np.asarray(__import__("PIL.Image", fromlist=["Image"]).open(SRC / "ground_weights.png").convert("RGBA"), np.float32) / 255 if False else None
    from_png = bpy.data.images.load(str(SRC / "ground_weights.png"))
    px = np.array(from_png.pixels[:], np.float32).reshape(from_png.size[1], from_png.size[0], 4)[::-1]  # top row first
    per = int(CHUNK / STEP)
    for cz in range(math.ceil((NZ - 1) / per)):
        for cx in range(math.ceil((NX - 1) / per)):
            i0, i1 = cx * per, min((cx + 1) * per, NX - 1)
            j0, j1 = cz * per, min((cz + 1) * per, NZ - 1)
            buf = bufs[f"terrain__{cx}_{cz}"]
            buf.smooth = True
            buf.grid = (i0, i1, j0, j1, px)
            buf.mat.append("terrain")


def water():
    lv = WL.copy()
    for _ in range(3):  # spread the surface under the banks so the shore is where terrain crosses it
        pad = np.pad(lv, 1, constant_values=-1000)
        nb = np.max(np.stack([pad[1:-1, :-2], pad[1:-1, 2:], pad[:-2, 1:-1], pad[2:, 1:-1]]), 0)
        lv = np.where(lv > -999, lv, nb)
    for j in range(NZ - 1):
        for i in range(NX - 1):
            c = lv[j:j + 2, i:i + 2]
            if (c < -999).any() or not (WL[j:j + 2, i:i + 2] > -999).any() and (H[j:j + 2, i:i + 2] > c + .3).all():
                continue
            x0, z0 = TERR[0] + i * STEP, TERR[1] + j * STEP
            pts = [(x0, c[0, 0], z0), (x0, c[1, 0], z0 + STEP), (x0 + STEP, c[1, 1], z0 + STEP), (x0 + STEP, c[0, 1], z0)]
            B("water", x0, z0).face(pts, [(p[0] / 12, -p[2] / 12) for p in pts], "water", normal=(0, 1, 0))


# ---------------------------------------------------------------- roads, walks, paved areas

def ribbon(buf, pts, width, mat, lift, vlen=16.0, cols=None, side_skirt=0.0):
    """pts: [(x, z)] centreline. u across 0..1, v along every vlen metres."""
    if len(pts) < 2:
        return
    dense = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        d = math.dist(a, b)
        n = max(1, int(math.ceil(d / 3.0)))
        for k in range(1, n + 1):
            dense.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
    s = 0.0
    prev = None
    rows = []
    for i, p in enumerate(dense):
        a = dense[max(0, i - 1)]
        b = dense[min(len(dense) - 1, i + 1)]
        dx, dz = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dz) or 1
        nx, nz = -dz / ln, dx / ln
        if prev is not None:
            s += math.dist(prev, p)
        prev = p
        l = (p[0] + nx * width / 2, p[1] + nz * width / 2)
        r = (p[0] - nx * width / 2, p[1] - nz * width / 2)
        rows.append((l, r, s))
    for (l0, r0, s0), (l1, r1, s1) in zip(rows, rows[1:]):
        q = [(l0[0], hgt(*l0) + lift, l0[1]), (r0[0], hgt(*r0) + lift, r0[1]), (r1[0], hgt(*r1) + lift, r1[1]), (l1[0], hgt(*l1) + lift, l1[1])]
        buf.face(q, [(0, s0 / vlen), (1, s0 / vlen), (1, s1 / vlen), (0, s1 / vlen)], mat, cols, normal=(0, 1, 0))
        if side_skirt:
            for a, b in ((l0, l1), (r1, r0)):
                ha, hb = hgt(*a) + lift, hgt(*b) + lift
                sk = [(a[0], ha, a[1]), (b[0], hb, b[1]), (b[0], hb - side_skirt, b[1]), (a[0], ha - side_skirt, a[1])]
                buf.face(sk, [(0, 0), (1, 0), (1, .1), (0, .1)], "kerb", cols)


def road_material(r):
    if not r["paved"]:
        return "road_dirt" if r["hw"] in ("track", "service", "path") else "road_gravel"
    if r["hw"] in ("trunk", "primary", "secondary"):
        return "road_main"
    if r["hw"] == "tertiary":
        return "road_2lane"
    return "road_town"


def roads():
    node_use = defaultdict(list)
    for r in plan["roads"]:
        if r["bridge"]:
            continue
        pts = [(p[0], p[2]) for p in r["pts"]]
        mid = pts[len(pts) // 2]
        lift = .05 + r["rank"] * .004
        ribbon(B("roads", *mid), pts, r["width"], road_material(r), lift)
        for p in (pts[0], pts[-1]):
            node_use[(round(p[0], 1), round(p[1], 1))].append(r)
        for p in pts[1:-1]:
            node_use[(round(p[0], 1), round(p[1], 1))].append(r)
    # junction plates hide overlapping markings
    for key, rs in node_use.items():
        if len({id(r) for r in rs}) < 3 and not (len(rs) >= 2 and len({id(r) for r in rs}) == 2 and False):
            if len({id(r) for r in rs}) < 2:
                continue
        top = max(rs, key=lambda r: r["rank"])
        radius = max(r["width"] for r in rs) / 2 + .6
        mat = "asphalt" if top["paved"] else ("dirt_track" if top["hw"] == "track" else "gravel")
        lift = .05 + 9 * .004 + .01
        cx, cz = key
        ring = [(cx + math.cos(a) * radius, cz + math.sin(a) * radius) for a in np.linspace(0, math.tau, 13)[:-1]]
        pts = [(p[0], hgt(*p) + lift, p[1]) for p in ring]
        B("roads", cx, cz).face(pts, [(p[0] / 8, -p[2] / 8) for p in pts], mat, normal=(0, 1, 0))
    for sw in plan["sidewalks"]:
        pts = [(p[0], p[1]) for p in sw["pts"]]
        ribbon(B("walks", *pts[len(pts) // 2]), pts, sw["width"], "sidewalk_tiles", .17, vlen=2.5, side_skirt=.17)
    for pa in plan["paths"]:
        pts = [tuple(p) for p in pa["pts"]]
        mat = "sidewalk_hex" if pa["hw"] in ("pedestrian", "footway") else "dirt_track"
        ribbon(B("walks", *pts[len(pts) // 2]), pts, 2.2 if mat == "sidewalk_hex" else 1.6, mat, .04, vlen=3)
    # paved polygons (market, parking, the cathedral square) rasterised on the 5 m grid
    areas = [(pa["pts"], "paving_market" if pa["kind"] == "marketplace" else "asphalt") for pa in plan["paved"]]
    px, pz = plan_plaza
    areas.append(([(px + math.cos(a) * 42, pz + math.sin(a) * 42) for a in np.linspace(0, math.tau, 25)[:-1]], "sidewalk_hex"))
    for poly, mat in areas:
        xs = [p[0] for p in poly]
        zs = [p[1] for p in poly]
        g = 2.5
        x = math.floor(min(xs) / g) * g
        while x < max(xs):
            z = math.floor(min(zs) / g) * g
            while z < max(zs):
                if inside((x + g / 2, z + g / 2), poly):
                    q = [(x, hgt(x, z) + .045, z), (x, hgt(x, z + g) + .045, z + g), (x + g, hgt(x + g, z + g) + .045, z + g), (x + g, hgt(x + g, z) + .045, z)]
                    B("roads", x, z).face(q, [(p[0] / 6, -p[2] / 6) for p in q], mat, normal=(0, 1, 0))
                z += g
            x += g


def inside(p, poly):
    x, z = p
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi + 1e-12) + xi:
            c = not c
        j = i
    return c


def bridges():
    for br in plan["bridges"]:
        pts = [(p[0], p[1]) for p in br["pts"]]
        prof = br["prof"]
        w = br["width"]
        mid = pts[len(pts) // 2]
        buf = B("bridges", *mid)
        col = B("col", *mid)
        rows = []
        for i, (p, h) in enumerate(zip(pts, prof)):
            a = pts[max(0, i - 1)]
            b = pts[min(len(pts) - 1, i + 1)]
            dx, dz = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dz) or 1
            nx, nz = -dz / ln, dx / ln
            rows.append(((p[0] + nx * w / 2, p[1] + nz * w / 2), (p[0] - nx * w / 2, p[1] - nz * w / 2), h + .25, p))
        s = 0
        for (l0, r0, h0, p0), (l1, r1, h1, p1) in zip(rows, rows[1:]):
            s1 = s + math.dist(p0, p1)
            top = [(l0[0], h0, l0[1]), (r0[0], h0, r0[1]), (r1[0], h1, r1[1]), (l1[0], h1, l1[1])]
            buf.face(top, [(0, s / 16), (1, s / 16), (1, s1 / 16), (0, s1 / 16)], "road_2lane", normal=(0, 1, 0))
            col.face(top, [(0, 0)] * 4, "col", normal=(0, 1, 0))
            for a, b, ha, hb in ((l0, l1, h0, h1), (r1, r0, h1, h0)):
                side = [(a[0], ha, a[1]), (b[0], hb, b[1]), (b[0], hb - 1.1, b[1]), (a[0], ha - 1.1, a[1])]
                buf.face(side, [(0, 0), (s1 / 4 - s / 4, 0), (s1 / 4 - s / 4, .4), (0, .4)], "concrete")
                rail = [(a[0], ha + 1.1, a[1]), (b[0], hb + 1.1, b[1]), (b[0], hb, b[1]), (a[0], ha, a[1])]
                buf.face(rail, [(0, 1), (math.dist(a, b) / 3, 1), (math.dist(a, b) / 3, 0), (0, 0)], "fence_mesh")
                col.face(rail, [(0, 0)] * 4, "col")
            bot = [(l0[0], h0 - 1.1, l0[1]), (l1[0], h1 - 1.1, l1[1]), (r1[0], h1 - 1.1, r1[1]), (r0[0], h0 - 1.1, r0[1])]
            buf.face(bot, [(0, 0), (0, 1), (1, 1), (1, 0)], "concrete", normal=(0, -1, 0))
            s = s1
        for i in range(2, len(rows) - 2, 4):
            l, r, h, p = rows[i]
            g = hgt(*p) - 1.5
            if h - g < 3:
                continue
            for dxz in ((-1.2, -w / 2 + 1), (1.2, -w / 2 + 1)):
                pass
            box(buf, p, 2.4, w - 1.0, g, h - 1.1, math.atan2(r[1] - l[1], r[0] - l[0]), "concrete_dirty", (1, 1, 1, 1))


def box(buf, c, sx, sz, y0, y1, ang, mat, col, uvscale=3.0):
    ca, sa = math.cos(ang), math.sin(ang)
    corners = [(c[0] + u * ca - v * sa, c[1] + u * sa + v * ca) for u, v in ((-sx / 2, -sz / 2), (sx / 2, -sz / 2), (sx / 2, sz / 2), (-sx / 2, sz / 2))]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        L = math.dist(a, b)
        mid = ((a[0] + b[0]) / 2 - c[0], (a[1] + b[1]) / 2 - c[1])
        q = [(a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1, b[1]), (a[0], y1, a[1])]
        buf.face(q, [(0, 0), (L / uvscale, 0), (L / uvscale, (y1 - y0) / uvscale), (0, (y1 - y0) / uvscale)], mat, [col] * 4, normal=(mid[0], 0, mid[1]))
    top = [(p[0], y1, p[1]) for p in corners]
    buf.face(top, [(p[0] / uvscale, p[2] / uvscale) for p in top], mat, [col] * 4, normal=(0, 1, 0))


# ---------------------------------------------------------------- buildings

STYLE = {  # ground tex, upper tex, plain tex, bay width (m), tinted plain
    "panel5": ("khrush_ground", "khrush_upper", "silicate_brick", 3.2),
    "panel9": ("panel9_ground", "panel9_upper", "concrete_panel", 3.0),
    "brick": ("brick_upper", "brick_upper", "red_brick", 3.2),
    "public": ("public_ground", "public_upper", "plaster", 3.6),
    "shop": ("shopfront_0", "plaster_upper", "plaster_worn", 3.5),
    "industrial": ("industrial", "industrial", "factory_wall", 6.0),
    "church": ("church_side", "church_side", "plaster", 4.0),
    "garage": ("silicate_brick", "silicate_brick", "silicate_brick", 3.2),
    "ruin": ("house_end_ruin", "house_end_ruin", "ruin_wattle", 3.0),
    "house": ("house_wall_a", "house_wall_a", "plaster", 3.0),
}
HOUSE_WALLS = ["house_wall_a", "house_wall_b", "house_wall_c", "house_wall_a", "house_wall_b"]
GABLES = ["gable_blue", "gable_wood", "gable_red", "gable_green", "gable_wood"]
ROOFS = ["roof_shifer", "roof_shifer_b", "roof_shifer_c", "roof_shifer", "roof_metal", "roof_corrugated"]


def tex_bays(t):
    return TEXM.get(t, {}).get("bays", 1)


def tex_floors(t):
    return TEXM.get(t, {}).get("floors", 1)


def tinted(t):
    return TEXM.get(t, {}).get("tint", False)


def shade(col, y, y0, y1, facing):
    """Baked GTA-style prelight: darker at the foot, sun side brighter."""
    t = 0 if y1 <= y0 else (y - y0) / (y1 - y0)
    sun = .9 + .1 * max(0.0, facing[0] * .6 - facing[1] * .8)
    k = (.72 + .28 * min(1.0, t * 3)) * sun
    return (col[0] * k, col[1] * k, col[2] * k, 1.0)


def wall_quad(buf, a, b, y0, y1, tex, u0, u1, v0, v1, col, out_n):
    q = [(a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1, b[1]), (a[0], y1, a[1])]
    cols = [shade(col, p[1], y0 - .01, y1, out_n) for p in q]
    buf.face(q, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], tex, cols, normal=(out_n[0], 0, out_n[1]))


def signed_area(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2


def nearest_road_dist(p):
    best = 1e9
    for a, b in road_segs_near(p):
        best = min(best, seg_d(p, a, b))
    return best


def seg_d(p, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dz * dz
    t = 0 if L == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / L))
    return math.hypot(p[0] - a[0] - dx * t, p[1] - a[1] - dz * t)


road_grid = defaultdict(list)


def index_roads():
    for r in plan["roads"]:
        pts = [(p[0], p[2]) for p in r["pts"]]
        for a, b in zip(pts, pts[1:]):
            for cx in range(int(min(a[0], b[0]) // 50), int(max(a[0], b[0]) // 50) + 1):
                for cz in range(int(min(a[1], b[1]) // 50), int(max(a[1], b[1]) // 50) + 1):
                    road_grid[(cx, cz)].append((a, b))


def road_segs_near(p):
    cx, cz = int(p[0] // 50), int(p[1] // 50)
    out = []
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            out.extend(road_grid.get((cx + i, cz + j), ()))
    return out


def landmark_for(b):
    n = b.get("name", "")
    if b["id"] == 673887102 or "Коростишів-1" in n:
        return dict(front="postal_station", side="postal_station_side", height=6.0, roof="roof_shifer_c", gable=True)
    if b["id"] in LANDMARK_IDS:
        return LANDMARK_IDS[b["id"]]
    if "руїн" in n or "Закинута" in n:
        return dict(style="ruin")
    return None


LANDMARK_IDS = {}


def pick_landmarks():
    blds = plan["buildings"]
    churches = [b for b in blds if b["style"] == "church"]
    if churches:
        kostel = max(churches, key=lambda b: abs(signed_area(b["pts"])) if not b["name"] else 0)
        LANDMARK_IDS[kostel["id"]] = dict(front="church_front", side="church_side", height=13.0, kostel=True)
    px, pz = plan_plaza
    publics = [b for b in blds if b["style"] == "public" and math.dist(centroid(b["pts"]), (px, pz)) < 450]
    if publics:
        rda = max(publics, key=lambda b: abs(signed_area(b["pts"])))
        LANDMARK_IDS[rda["id"]] = dict(front="rda_front", side="public_upper", height=8.5)
    for b in blds:
        if b["style"] == "public" and b["id"] not in LANDMARK_IDS and ("Школа" in b["name"] or abs(signed_area(b["pts"])) > 900):
            LANDMARK_IDS[b["id"]] = dict(front="college_wall", side="college_wall", height=8.0)


def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def building(b):
    pts = [tuple(p) for p in b["pts"]]
    style = b["style"]
    lm = landmark_for(b) if b.get("osm") else None
    if lm and lm.get("style"):
        style = lm["style"]
        lm = None
    if style == "house" and b.get("obb"):
        return house(b)
    c = centroid(pts)
    buf = B("buildings", *c)
    col_buf = B("col", *c)
    F, base = b["foot"], b["base"]
    height = lm["height"] if lm and lm.get("height") else b["height"]
    if style == "ruin":
        height = 2.6
    T = base + height
    floor_h = b["floor_h"] if style not in ("industrial", "church") else height
    ground_t, upper_t, plain_t, bay = STYLE[style]
    if style == "shop":
        ground_t = rng.choice(["shopfront_0", "shopfront_1", "shopfront_2", "shopfront_0"])
    if style == "brick":
        ground_t = upper_t = rng.choice(["brick_upper", "yellow_brick_upper"])
        plain_t = "red_brick" if ground_t == "brick_upper" else "yellow_brick"
    tint = hexcol(b["color"])
    if signed_area(pts) < 0:
        pts = pts[::-1]
    edges = list(zip(pts, pts[1:] + pts[:1]))
    lens = [math.dist(a, bb) for a, bb in edges]
    front = None
    if lm or style in ("shop", "garage", "public"):
        cand = [i for i, L in enumerate(lens) if L >= max(lens) * .55]
        front = min(cand, key=lambda i: nearest_road_dist(((edges[i][0][0] + edges[i][1][0]) / 2, (edges[i][0][1] + edges[i][1][1]) / 2)))
    if style == "garage" and b.get("door"):
        dx, dz = b["door"]
        front = max(range(len(edges)), key=lambda i: (edges[i][1][1] - edges[i][0][1]) * dx - (edges[i][1][0] - edges[i][0][0]) * dz)
    parapet = .6 if style in ("panel5", "panel9", "brick", "public", "shop") and height > 4 else (.25 if style == "garage" else 0)
    for i, ((a, bb), L) in enumerate(zip(edges, lens)):
        dx, dz = bb[0] - a[0], bb[1] - a[1]
        n = (dz / (L or 1), -dx / (L or 1))
        wcol = tint if True else (1, 1, 1, 1)
        # plinth
        if base - F > .05:
            wall_quad(buf, a, bb, F, base, "concrete_block", 0, L / 3, 0, (base - F) / 3, (.8, .8, .78, 1), n)
        col_buf.face([(a[0], F, a[1]), (bb[0], F, bb[1]), (bb[0], T + parapet, bb[1]), (a[0], T + parapet, a[1])], [(0, 0)] * 4, "col", normal=(n[0], 0, n[1]))
        if lm and i == front:
            t = lm["front"]
            extra = 0
            if lm.get("kostel"):
                extra = height * 1.05  # towers and pediment stand above the roof, alpha cut
                q = [(a[0] + n[0] * .35, base, a[1] + n[1] * .35), (bb[0] + n[0] * .35, base, bb[1] + n[1] * .35),
                     (bb[0] + n[0] * .35, T + extra, bb[1] + n[1] * .35), (a[0] + n[0] * .35, T + extra, a[1] + n[1] * .35)]
                buf.face(q, [(0, 0), (1, 0), (1, 1), (0, 1)], t, [(1, 1, 1, 1)] * 4, normal=(n[0], 0, n[1]))
                wall_quad(buf, a, bb, base, T, "church_side", 0, 1, 0, 1, (1, 1, 1, 1), n)
            else:
                wall_quad(buf, a, bb, base, T, t, 0, 1, 0, 1, (1, 1, 1, 1), n)
            continue
        if lm and lm.get("side"):
            t = lm["side"]
            nb = max(1, round(L / 3.2))
            wall_quad(buf, a, bb, base, T, t, 0, nb / tex_bays(t), 0, 1, (1, 1, 1, 1), n)
            continue
        if style == "garage":
            if i == front:
                door = rng.choice(["garage_door_0", "garage_door_1", "garage_door_2"])
                wall_quad(buf, a, bb, base, T, door, 0, 1, 0, 1, (1, 1, 1, 1), n)
            else:
                wall_quad(buf, a, bb, base, T, plain_t, 0, L / 3, 0, height / 3, tint, n)
            continue
        nb = round(L / bay)
        if nb < 1 or (style not in ("industrial", "church") and L < bay * .8):
            wall_quad(buf, a, bb, base, T + parapet, plain_t, 0, L / 3, 0, (T + parapet - base) / 3, tint if tinted(plain_t) else (1, 1, 1, 1), n)
            continue
        gt = ground_t if (front is None or i == front or style != "shop") else "plaster_upper"
        tcol = tint if tinted(gt) else (1, 1, 1, 1)
        top_g = min(T, base + floor_h)
        wall_quad(buf, a, bb, base, top_g, gt, 0, nb / tex_bays(gt), 0, (top_g - base) / floor_h / tex_floors(gt), tcol, n)
        if T - top_g > .3:
            ucol = tint if tinted(upper_t) else (1, 1, 1, 1)
            wall_quad(buf, a, bb, top_g, T, upper_t, 0, nb / tex_bays(upper_t), 0, (T - top_g) / floor_h / tex_floors(upper_t), ucol, n)
        if parapet:
            wall_quad(buf, a, bb, T, T + parapet, plain_t, 0, L / 3, 0, parapet / 3, tint if tinted(plain_t) else (1, 1, 1, 1), n)
            wall_quad(buf, bb, a, T, T + parapet, plain_t, 0, L / 3, 0, parapet / 3, tint if tinted(plain_t) else (1, 1, 1, 1), (-n[0], -n[1]))
    # roof
    if style == "ruin":
        return
    if (lm and lm.get("gable")) or style == "church":
        cen, ang, L, W = obb(pts)
        gable_roof(buf, col_buf, cen, ang, L + .8, W + .8, T, W * (.45 if style == "church" else .3),
                   lm.get("roof", "roof_metal") if lm else "roof_metal", "plaster", hexcol(b["roof_color"]), tint, hip=False)
        if style == "church" and not (lm and lm.get("kostel")):
            dome(buf, cen, T + W * .45 - 1.0, max(2.2, W * .22))
        return
    roof_t = "roof_flat" if style in ("panel5", "panel9", "brick", "public", "shop", "industrial") else "roof_bitumen"
    if style == "garage":
        roof_t = "roof_bitumen"
    top = [(p[0], T + .02, p[1]) for p in pts]
    buf.face(top, [(p[0] / 4, -p[2] / 4) for p in top], roof_t, [(.9, .9, .9, 1)] * len(top), normal=(0, 1, 0))
    col_buf.face(top, [(0, 0)] * len(top), "col", normal=(0, 1, 0))
    if style in ("panel5", "panel9") and rng.random() < .8:  # stair-well head and TV antennas
        cx_, cz_ = c
        box(buf, (cx_ + rng.uniform(-3, 3), cz_ + rng.uniform(-2, 2)), 3.0, 3.0, T, T + 2.4, 0, "silicate_brick", tint)


def obb(pts):
    best = None
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        c, s = math.cos(ang), math.sin(ang)
        us = [p[0] * c + p[1] * s for p in pts]
        vs = [-p[0] * s + p[1] * c for p in pts]
        area = (max(us) - min(us)) * (max(vs) - min(vs))
        if best is None or area < best[0]:
            cu, cv = (max(us) + min(us)) / 2, (max(vs) + min(vs)) / 2
            best = (area, (cu * c - cv * s, cu * s + cv * c), ang, max(us) - min(us), max(vs) - min(vs))
    _, cen, ang, L, W = best
    if W > L:
        ang += math.pi / 2
        L, W = W, L
    return cen, ang, L, W


def gable_roof(buf, col_buf, cen, ang, L, W, y0, rise, roof_t, gable_t, roof_col, wall_col, hip=False):
    ca, sa = math.cos(ang), math.sin(ang)
    P = lambda u, v, y: (cen[0] + u * ca - v * sa, y, cen[1] + u * sa + v * ca)
    ridge = L / 2 - (W / 2 if hip else 0)
    rc = roof_col if tinted(roof_t) else (1, 1, 1, 1)
    slope = math.hypot(W / 2, rise)
    for side in (-1, 1):
        q = [P(-L / 2, side * W / 2, y0), P(L / 2, side * W / 2, y0), P(ridge, 0, y0 + rise), P(-ridge, 0, y0 + rise)]
        n = (-sa * side, rise, ca * side)
        cols = [(rc[0] * .85, rc[1] * .85, rc[2] * .85, 1)] * 2 + [rc] * 2
        uv = [(-L / 2 / 3, 0), (L / 2 / 3, 0), (ridge / 3, slope / 3), (-ridge / 3, slope / 3)]
        buf.face(q, uv, roof_t, cols, normal=n)
        col_buf.face(q, [(0, 0)] * 4, "col", normal=n)
    for end in (-1, 1):
        if hip:
            q = [P(end * L / 2, -W / 2, y0), P(end * L / 2, W / 2, y0), P(end * ridge, 0, y0 + rise)]
            buf.face(q, [(0, 0), (W / 3, 0), (W / 6, slope / 3)], roof_t, [rc] * 3, normal=(ca * end, rise, sa * end))
            col_buf.face(q, [(0, 0)] * 3, "col", normal=(ca * end, rise, sa * end))
        else:
            q = [P(end * (L / 2 - .4), -W / 2 + .4, y0), P(end * (L / 2 - .4), W / 2 - .4, y0), P(end * (L / 2 - .4), 0, y0 + rise - .2)]
            gc = wall_col if tinted(gable_t) else (1, 1, 1, 1)
            buf.face(q, [(0, 0), (1, 0), (.5, 1)], gable_t, [gc] * 3, normal=(ca * end, 0, sa * end))
            col_buf.face(q, [(0, 0)] * 3, "col", normal=(ca * end, 0, sa * end))


def dome(buf, c, y, r):
    """Onion dome on a drum, gold like the Holy Trinity church."""
    prof = [(r * .9, 0), (r * .9, r * 1.4), (r * 1.15, r * 1.75), (r * 1.2, r * 2.1), (r * .95, r * 2.6), (r * .45, r * 3.0), (r * .12, r * 3.3), (0.05, r * 3.9)]
    seg = 10
    for k in range(len(prof) - 1):
        (r0, h0), (r1, h1) = prof[k], prof[k + 1]
        mat = "plaster" if k == 0 else "gold"
        for s in range(seg):
            a0, a1 = s / seg * math.tau, (s + 1) / seg * math.tau
            q = [(c[0] + math.cos(a0) * r0, y + h0, c[1] + math.sin(a0) * r0), (c[0] + math.cos(a1) * r0, y + h0, c[1] + math.sin(a1) * r0),
                 (c[0] + math.cos(a1) * r1, y + h1, c[1] + math.sin(a1) * r1), (c[0] + math.cos(a0) * r1, y + h1, c[1] + math.sin(a0) * r1)]
            am = (a0 + a1) / 2
            buf.face(q, [(s / seg, h0 / 4), ((s + 1) / seg, h0 / 4), ((s + 1) / seg, h1 / 4), (s / seg, h1 / 4)], mat,
                     [(1, 1, 1, 1)] * 4, normal=(math.cos(am), .2, math.sin(am)))
    box(buf, c, .12, .12, y + r * 3.9, y + r * 3.9 + 2.2, 0, "gold", (1, 1, 1, 1))
    box(buf, (c[0], c[1]), 1.2, .12, y + r * 3.9 + 1.4, y + r * 3.9 + 1.55, 0, "gold", (1, 1, 1, 1))


def house(b):
    cx, cz, ang, L, W = b["obb"]
    cen = (cx, cz)
    buf = B("buildings", *cen)
    col_buf = B("col", *cen)
    F, base = b["foot"], b["base"]
    T = base + b["height"]
    tint = hexcol(b["color"])
    wall_t = rng.choice(HOUSE_WALLS)
    end_t = "house_end_ruin" if rng.random() < .12 else "plaster"
    ca, sa = math.cos(ang), math.sin(ang)
    corners = [(cx + u * ca - v * sa, cz + u * sa + v * ca) for u, v in ((-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2))]
    if signed_area(corners) < 0:
        corners = corners[::-1]
    for a, bb in zip(corners, corners[1:] + corners[:1]):
        Le = math.dist(a, bb)
        n = ((bb[1] - a[1]) / Le, -(bb[0] - a[0]) / Le)
        if base - F > .05:
            wall_quad(buf, a, bb, F, base, "concrete_block", 0, Le / 3, 0, (base - F) / 3, (.75, .75, .72, 1), n)
        col_buf.face([(a[0], F, a[1]), (bb[0], F, bb[1]), (bb[0], T, bb[1]), (a[0], T, a[1])], [(0, 0)] * 4, "col", normal=(n[0], 0, n[1]))
        long_side = Le > (L + W) / 2
        if long_side:
            nb = max(1, round(Le / 3.0))
            wall_quad(buf, a, bb, base, T, wall_t, 0, nb / tex_bays(wall_t), 0, (T - base) / 2.9, (1, 1, 1, 1), n)
        else:
            t = end_t
            wall_quad(buf, a, bb, base, T, t, 0, (Le / 3 if t == "plaster" else 1), 0, ((T - base) / 3 if t == "plaster" else 1), tint if tinted(t) else (1, 1, 1, 1), n)
    roof_t = rng.choice(ROOFS)
    hip = b.get("roof") == "hip"
    gable_roof(buf, col_buf, cen, ang, L + .7, W + .7, T, W * rng.uniform(.28, .42), roof_t, rng.choice(GABLES), hexcol(b["roof_color"]), tint, hip=hip)
    if rng.random() < .6:
        u = rng.uniform(-L / 4, L / 4)
        box(buf, (cx + u * ca, cz + u * sa), .5, .5, T + W * .2, T + W * .45 + .8, ang, "red_brick", (1, 1, 1, 1), uvscale=1.5)


def fences():
    for f in plan["fences"]:
        a, b = tuple(f["a"]), tuple(f["b"])
        L = math.dist(a, b)
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        buf = B("fences", *mid)
        col = B("col", *mid)
        style = f["style"]
        tex = {"profnastil": "fence_profnastil", "picket": rng.choice(["fence_picket", "fence_picket_b", "fence_planks_grey"]),
               "concrete": "fence_concrete", "brick": "fence_brick", "mesh": "fence_mesh"}[style]
        if style == "profnastil" and rng.random() < .3:
            tex = "fence_blue"
        metres = TEXM.get(tex, {}).get("metres", [3.0, 1.8])
        h = f["h"]
        tcol = hexcol(f["color"]) if tinted(tex) else (1, 1, 1, 1)
        if tex == "fence_concrete":
            tcol = (.86, .85, .82, 1)
        gap = 3.2
        ux, uz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        g0 = (mid[0] - ux * gap / 2, mid[1] - uz * gap / 2)
        g1 = (mid[0] + ux * gap / 2, mid[1] + uz * gap / 2)
        for p0, p1 in ((a, g0), (g1, b)):
            seg = math.dist(p0, p1)
            n = max(1, int(seg / 3))
            for k in range(n):
                q0 = (p0[0] + (p1[0] - p0[0]) * k / n, p0[1] + (p1[1] - p0[1]) * k / n)
                q1 = (p0[0] + (p1[0] - p0[0]) * (k + 1) / n, p0[1] + (p1[1] - p0[1]) * (k + 1) / n)
                h0, h1 = hgt(*q0) - .15, hgt(*q1) - .15
                s0 = math.dist(p0, q0) / metres[0]
                s1 = math.dist(p0, q1) / metres[0]
                q = [(q0[0], h0, q0[1]), (q1[0], h1, q1[1]), (q1[0], h1 + h, q1[1]), (q0[0], h0 + h, q0[1])]
                buf.face(q, [(s0, 0), (s1, 0), (s1, 1), (s0, 1)], tex, [tcol] * 4)
                col.face(q, [(0, 0)] * 4, "col")
        if rng.random() < .55:  # gate leafs, often the blue sunburst kind
            h0, h1 = hgt(*g0) - .1, hgt(*g1) - .1
            q = [(g0[0], h0, g0[1]), (g1[0], h1, g1[1]), (g1[0], h1 + 2.0, g1[1]), (g0[0], h0 + 2.0, g0[1])]
            gt = "gate_blue" if rng.random() < .6 else tex
            buf.face(q, [(0, 0), (1, 0), (1, 1), (0, 1)], gt, [tcol if tinted(gt) else (1, 1, 1, 1)] * 4)
            col.face(q, [(0, 0)] * 4, "col")


# ---------------------------------------------------------------- Blender output

def to_blender(v):
    return (v[0], -v[2], v[1])


materials = {}


def material(name):
    if name not in materials:
        m = bpy.data.materials.new("m_" + name)
        m.diffuse_color = (.8, .8, .8, 1)
        materials[name] = m
    return materials[name]


def flush(name, buf, coll):
    if hasattr(buf, "grid"):
        return flush_terrain(name, buf, coll)
    if not buf.f:
        return None
    me = bpy.data.meshes.new(name)
    verts = [to_blender(v) for v in buf.v]
    me.from_pydata(verts, [], buf.f)
    names = sorted(set(buf.mat))
    for n in names:
        me.materials.append(material(n))
    idx = {n: i for i, n in enumerate(names)}
    me.polygons.foreach_set("material_index", [idx[m] for m in buf.mat])
    uv = me.uv_layers.new(name="UVMap")
    # loops follow the face order of from_pydata, which follows buf.v order
    loop_v = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", loop_v)
    uvs = np.asarray(buf.uv, np.float32)[loop_v]
    uv.data.foreach_set("uv", uvs.ravel())
    ca = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    cols = np.asarray(buf.col, np.float32)[loop_v]
    ca.data.foreach_set("color", cols.ravel())
    me.color_attributes.active_color = ca
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def flush_terrain(name, buf, coll):
    i0, i1, j0, j1, px = buf.grid
    xs = np.arange(i0, i1 + 1)
    zs = np.arange(j0, j1 + 1)
    gx, gz = np.meshgrid(xs, zs)
    verts = np.stack([TERR[0] + gx * STEP, H[gz, gx], TERR[1] + gz * STEP], -1).reshape(-1, 3)
    nx = len(xs)
    faces = []
    for j in range(len(zs) - 1):
        for i in range(len(xs) - 1):
            a = j * nx + i
            # split (0,0)-(1,1) like hgt()
            faces.append((a, a + nx, a + nx + 1))
            faces.append((a, a + nx + 1, a + 1))
    me = bpy.data.meshes.new(name)
    bv = np.stack([verts[:, 0], -verts[:, 2], verts[:, 1]], -1)
    me.vertices.add(len(bv))
    me.vertices.foreach_set("co", bv.ravel())
    fa = np.asarray(faces, np.int32)
    me.loops.add(len(fa) * 3)
    me.loops.foreach_set("vertex_index", fa.ravel())
    me.polygons.add(len(fa))
    me.polygons.foreach_set("loop_start", np.arange(0, len(fa) * 3, 3, dtype=np.int32))
    me.update()
    me.validate()
    me.materials.append(material("terrain"))
    loop_v = fa.ravel()
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", np.stack([verts[loop_v, 0] / 8, -verts[loop_v, 2] / 8], -1).astype(np.float32).ravel())
    w = px[gz.ravel(), gx.ravel()]  # RGBA weights per vertex, linear floats so glTF keeps them as is
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    ca.data.foreach_set("color", w[loop_v].astype(np.float32).ravel())
    me.color_attributes.active_color = ca
    me.polygons.foreach_set("use_smooth", [True] * len(fa))
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


# ---------------------------------------------------------------- trees

def trees(coll):
    def mesh(name, faces):
        b = Buf()
        for pts, uvs, mat, col in faces:
            b.face(pts, uvs, mat, [col] * len(pts))
        return flush(name, b, coll)

    def trunk(r, h, mat, seg=6):
        out = []
        for s in range(seg):
            a0, a1 = s / seg * math.tau, (s + 1) / seg * math.tau
            q = [(math.cos(a0) * r, 0, math.sin(a0) * r), (math.cos(a0) * r * .6, h, math.sin(a0) * r * .6),
                 (math.cos(a1) * r * .6, h, math.sin(a1) * r * .6), (math.cos(a1) * r, 0, math.sin(a1) * r)]
            out.append((q[::-1], [(s / seg, 0), (s / seg, h / 3), ((s + 1) / seg, h / 3), ((s + 1) / seg, 0)][::-1], mat, (1, 1, 1, 1)))
        return out

    def cards(y0, y1, half, mat, n=3, col=(1, 1, 1, 1), flat=False):
        out = []
        for k in range(n):
            a = k / n * math.pi
            dx, dz = math.cos(a) * half, math.sin(a) * half
            q = [(-dx, y0, -dz), (dx, y0, dz), (dx, y1, dz), (-dx, y1, -dz)]
            out.append((q, [(0, 0), (1, 0), (1, 1), (0, 1)], mat, col))
        if flat:
            ym = (y0 + y1) * .55
            q = [(-half, ym, -half), (half, ym, -half), (half, ym, half), (-half, ym, half)]
            out.append((q, [(0, 0), (1, 0), (1, 1), (0, 1)], mat, col))
        return out

    mesh("tree_deciduous", trunk(.22, 4.5, "bark") + cards(2.2, 9.5, 3.8, "leaves_card", 3, flat=True) + cards(5.0, 10.5, 2.6, "leaves_card_b", 2))
    mesh("tree_fruit", trunk(.13, 1.8, "bark") + cards(1.2, 5.0, 2.3, "leaves_card_b", 3, flat=True))
    mesh("tree_poplar", trunk(.25, 6, "bark") + cards(3.0, 19.0, 2.2, "leaves_card", 3))
    mesh("tree_birch", trunk(.14, 7, "bark_birch") + cards(4.0, 12.0, 2.6, "leaves_card_b", 3))
    mesh("tree_pine", trunk(.25, 16, "bark_pine", 7) + cards(7.0, 20.0, 3.2, "pine_card", 3) + cards(3.0, 13.0, 4.0, "pine_card", 3))
    mesh("tree_spruce", trunk(.18, 3, "bark_pine") + cards(.4, 12.0, 3.4, "pine_card", 4))


# ---------------------------------------------------------------- main

def main():
    global plan_plaza
    bpy.ops.wm.read_factory_settings(use_empty=True)
    korostyshiv = json.loads((DATA / "korostyshiv.json").read_text())
    plan_plaza = (korostyshiv["plaza"][0], korostyshiv["plaza"][2])
    index_roads()
    pick_landmarks()
    print("terrain", flush=True)
    terrain()
    print("water", flush=True)
    water()
    print("roads", flush=True)
    roads()
    bridges()
    print("buildings", len(plan["buildings"]), flush=True)
    for b in plan["buildings"]:
        building(b)
    print("fences", flush=True)
    fences()
    coll = bpy.data.collections.new("Korostyshiv")
    bpy.context.scene.collection.children.link(coll)
    tris = 0
    for name in sorted(bufs):
        ob = flush(name, bufs[name], coll)
        if ob:
            tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    print("objects", len(coll.objects), "tris", tris, flush=True)
    for ob in coll.objects:
        ob.select_set(True)
    OUT.mkdir(parents=True, exist_ok=True)
    common = dict(export_format="GLB", use_selection=True, export_materials="EXPORT", export_image_format="NONE",
                  export_vertex_color="ACTIVE", export_normals=True, export_texcoords=True, export_apply=False, export_yup=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT / "korostyshiv.glb"), **common)
    for ob in coll.objects:
        ob.select_set(False)
    tc = bpy.data.collections.new("Trees")
    bpy.context.scene.collection.children.link(tc)
    trees(tc)
    for ob in tc.objects:
        ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(OUT / "trees.glb"), **common)
    bpy.ops.wm.save_as_mainfile(filepath=str(SRC / "korostyshiv.blend"), compress=True)
    print("MESHES_OK", flush=True)


plan_plaza = (0.0, 0.0)
main()
