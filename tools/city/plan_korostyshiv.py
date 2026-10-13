"""Plan the playable Korostyshiv from OpenStreetMap + SRTM.

Reads  assets/source/city/korostyshiv-overpass.json and assets/source/city/dem/*.png
Writes data/city/korostyshiv.json      gameplay plan for Godot (roads graph, locations, districts, traffic, props, trees)
       data/city/heightfield.bin       float32 terrain heights (row = z, column = x), metres, river ~ 0
       data/city/waterlevel.bin        float32 water surface per cell, -1000 where dry
       data/city/districts.png         district index per 10 m cell
       assets/city/radar.png           GTA III style radar / map texture
       assets/source/city/plan_meshes.json   everything tools/city/build_city_meshes.py needs

Run: python3 -I tools/city/plan_korostyshiv.py
Coordinates: x east, z south, metres from 50.3155 N 29.0600 E. Godot uses them directly.
"""

import glob
import heapq
import json
import math
import os
import random
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets/source/city"
DATA = ROOT / "data/city"
ASSETS = ROOT / "assets/city"

LAT0, LON0 = 50.3155, 29.0600
KX = 111320.0 * math.cos(math.radians(LAT0))
KZ = 110540.0
PLAY = (-880.0, -1280.0, 1680.0, 1080.0)      # x0, z0, x1, z1: where the player may go
TERR = (-1180.0, -1580.0, 1980.0, 1380.0)     # terrain/mesh extent (fogged margin around PLAY)
STEP = 5.0
BASE_ELEV = 150.0
SEED = 1986

rng = random.Random(SEED)
NX = int((TERR[2] - TERR[0]) / STEP) + 1
NZ = int((TERR[3] - TERR[1]) / STEP) + 1


def to_local(lon, lat):
    return ((lon - LON0) * KX, -(lat - LAT0) * KZ)


def in_rect(p, r, margin=0.0):
    return r[0] - margin <= p[0] <= r[2] + margin and r[1] - margin <= p[1] <= r[3] + margin


def grid_xy(p):
    """World (x, z) -> fractional grid column/row."""
    return ((p[0] - TERR[0]) / STEP, (p[1] - TERR[1]) / STEP)


def poly_area(poly):
    a = 0.0
    for i in range(len(poly)):
        x1, z1 = poly[i]
        x2, z2 = poly[(i + 1) % len(poly)]
        a += x1 * z2 - x2 * z1
    return a / 2


def centroid(poly):
    xs = [p[0] for p in poly]
    zs = [p[1] for p in poly]
    return (sum(xs) / len(xs), sum(zs) / len(zs))


def point_in_poly(p, poly):
    x, z = p
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def seg_dist(p, a, b):
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - az) * dz) / L))
    qx, qz = ax + dx * t, az + dz * t
    return math.hypot(p[0] - qx, p[1] - qz), (qx, qz), t


def densify(pts, step):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(math.ceil(d / step)))
        for k in range(1, n + 1):
            out.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
    return out


def arc_lengths(pts):
    s = [0.0]
    for a, b in zip(pts, pts[1:]):
        s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return s


def smooth_profile(values, s, window):
    out = []
    for i in range(len(values)):
        acc = wsum = 0.0
        for j in range(len(values)):
            d = abs(s[j] - s[i])
            if d < window:
                w = 1 - d / window
                acc += values[j] * w
                wsum += w
        out.append(acc / wsum)
    return out


def min_area_rect(poly):
    """Oriented bounding box: centre, angle (radians, of the long side), length, width."""
    best = None
    pts = poly
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


# ---------------------------------------------------------------- OSM

def load_osm():
    d = json.loads((SRC / "korostyshiv-overpass.json").read_text())
    nodes, ways, rels = {}, {}, []
    for e in d["elements"]:
        if e["type"] == "node":
            nodes[e["id"]] = e
        elif e["type"] == "way":
            ways[e["id"]] = e
        else:
            rels.append(e)
    return nodes, ways, rels


def way_pts(w, nodes):
    return [to_local(nodes[i]["lon"], nodes[i]["lat"]) for i in w["nodes"] if i in nodes]


def join_rings(segments):
    rings = []
    segs = [list(s) for s in segments if len(s) > 1]
    while segs:
        ring = segs.pop(0)
        changed = True
        while changed and ring[0] != ring[-1]:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == ring[-1]:
                    ring += s[1:]
                elif s[-1] == ring[-1]:
                    ring += s[::-1][1:]
                elif s[-1] == ring[0]:
                    ring = s[:-1] + ring
                elif s[0] == ring[0]:
                    ring = s[::-1][:-1] + ring
                else:
                    continue
                segs.pop(i)
                changed = True
                break
        if len(ring) > 3:
            rings.append(ring)
    return rings


def areas_from_osm(nodes, ways, rels):
    """Closed polygons with tags: closed ways plus multipolygon outers."""
    out = []
    for w in ways.values():
        t = w.get("tags", {})
        if len(w["nodes"]) > 3 and w["nodes"][0] == w["nodes"][-1]:
            out.append((t, way_pts(w, nodes)[:-1], w["id"]))
    for r in rels:
        t = r.get("tags", {})
        if t.get("type") != "multipolygon":
            continue
        outers = [ways[m["ref"]]["nodes"] for m in r.get("members", []) if m["type"] == "way" and m.get("role") == "outer" and m["ref"] in ways]
        for ring in join_rings(outers):
            pts = [to_local(nodes[i]["lon"], nodes[i]["lat"]) for i in ring if i in nodes]
            if len(pts) > 3:
                out.append((t, pts[:-1] if pts[0] == pts[-1] else pts, r["id"]))
    return out


# ---------------------------------------------------------------- terrain

def load_dem():
    tiles = {}
    for f in glob.glob(str(SRC / "dem/*.png")):
        z, x, y = (int(v) for v in os.path.basename(f)[:-4].split("_"))
        tiles[(x, y)] = f
    xs = sorted({k[0] for k in tiles})
    ys = sorted({k[1] for k in tiles})
    mos = np.zeros((len(ys) * 256, len(xs) * 256), np.float32)
    for (x, y), f in tiles.items():
        a = np.asarray(Image.open(f).convert("RGB"), np.float32)
        mos[(y - ys[0]) * 256:(y - ys[0] + 1) * 256, (x - xs[0]) * 256:(x - xs[0] + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
    return mos, z, xs[0], ys[0]


def sample_dem(mos, z, tx0, ty0):
    n = 2 ** z
    gx = TERR[0] + np.arange(NX) * STEP
    gz = TERR[1] + np.arange(NZ) * STEP
    GX, GZ = np.meshgrid(gx, gz)
    lon = LON0 + GX / KX
    lat = LAT0 - GZ / KZ
    px = ((lon + 180) / 360 * n - tx0) * 256
    lr = np.radians(lat)
    py = ((1 - np.log(np.tan(lr) + 1 / np.cos(lr)) / math.pi) / 2 * n - ty0) * 256
    x0 = np.clip(np.floor(px).astype(int), 0, mos.shape[1] - 2)
    y0 = np.clip(np.floor(py).astype(int), 0, mos.shape[0] - 2)
    fx = px - x0
    fy = py - y0
    h = (mos[y0, x0] * (1 - fx) * (1 - fy) + mos[y0, x0 + 1] * fx * (1 - fy)
         + mos[y0 + 1, x0] * (1 - fx) * fy + mos[y0 + 1, x0 + 1] * fx * fy)
    return h - BASE_ELEV


def blur(a, radius):
    """Separable gaussian blur of a float array (radius = sigma in cells), edges clamped."""
    r = max(1, int(math.ceil(radius * 3)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / radius) ** 2)
    k = (k / k.sum()).astype(np.float32)
    out = np.pad(a.astype(np.float32), ((0, 0), (r, r)), mode="edge")
    out = sum(k[i] * out[:, i:i + a.shape[1]] for i in range(len(k)))
    out = np.pad(out, ((r, r), (0, 0)), mode="edge")
    return sum(k[i] * out[i:i + a.shape[0], :] for i in range(len(k))).astype(np.float32)


def sample_grid(H, x, z):
    gx, gz = grid_xy((x, z))
    gx = min(max(gx, 0), NX - 1.001)
    gz = min(max(gz, 0), NZ - 1.001)
    x0, z0 = int(gx), int(gz)
    fx, fz = gx - x0, gz - z0
    return float(H[z0, x0] * (1 - fx) * (1 - fz) + H[z0, x0 + 1] * fx * (1 - fz)
                 + H[z0 + 1, x0] * (1 - fx) * fz + H[z0 + 1, x0 + 1] * fx * fz)


def canvas(mode="L", value=0):
    return Image.new(mode, (NX, NZ), value)


def to_px(pts):
    return [grid_xy(p) for p in pts]


# ---------------------------------------------------------------- roads

ROAD_W = {  # carriageway width, rank (higher drawn on top), paved default
    "trunk": (13.0, 9), "trunk_link": (7.5, 8), "primary": (11.0, 8), "secondary": (9.5, 7),
    "tertiary": (8.5, 6), "unclassified": (6.5, 4), "residential": (6.5, 4), "living_street": (5.5, 3),
    "service": (4.5, 2), "track": (4.0, 1),
}
FOOT = {"footway", "path", "pedestrian", "steps", "cycleway"}
UNPAVED = {"unpaved", "gravel", "ground", "dirt", "compacted", "sand", "grass", "fine_gravel", "earth", "mud"}


def build_roads(nodes, ways):
    roads, paths = [], []
    for w in ways.values():
        t = w.get("tags", {})
        hw = t.get("highway")
        if not hw or t.get("area") == "yes":
            continue
        pts = way_pts(w, nodes)
        ids = [i for i in w["nodes"] if i in nodes]
        if len(pts) < 2 or not any(in_rect(p, TERR) for p in pts):
            continue
        if hw in ROAD_W:
            if hw == "service" and t.get("service") in ("parking_aisle",):
                continue
            width, rank = ROAD_W[hw]
            if "lanes" in t:
                try:
                    width = max(width, float(t["lanes"].split(";")[0]) * 3.3)
                except ValueError:
                    pass
            paved = t.get("surface") not in UNPAVED and hw != "track"
            if hw in ("residential", "unclassified", "living_street", "service") and "surface" not in t:
                # unmapped surfaces in the private sector are mostly gravel and dirt
                paved = abs(sum(p[0] for p in pts) / len(pts) - 120) < 420 and abs(sum(p[1] for p in pts) / len(pts) + 60) < 520
            roads.append(dict(id=w["id"], hw=hw, name=t.get("name", ""), width=width, rank=rank, paved=paved,
                              bridge=t.get("bridge") in ("yes", "viaduct"), oneway=t.get("oneway") == "yes",
                              pts=pts, ids=ids))
        elif hw in FOOT:
            paths.append(dict(id=w["id"], hw=hw, pts=pts))
    return roads, paths


def road_graph(roads):
    """Nodes: OSM node ids. Edges along drivable roads (both ways)."""
    pos = {}
    adj = defaultdict(dict)
    for r in roads:
        if r["hw"] == "track" and not any(in_rect(p, PLAY) for p in r["pts"]):
            continue
        for (ia, pa), (ib, pb) in zip(zip(r["ids"], r["pts"]), zip(r["ids"][1:], r["pts"][1:])):
            if not (in_rect(pa, TERR) and in_rect(pb, TERR)):
                continue
            pos[ia], pos[ib] = pa, pb
            d = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
            cost = d * (1.0 if r["paved"] else 1.6) * (1.2 if r["hw"] in ("service", "track") else 1.0)
            adj[ia][ib] = cost
            adj[ib][ia] = cost
    # keep the biggest connected component
    seen, best = set(), []
    for n in pos:
        if n in seen:
            continue
        comp, stack = [], [n]
        seen.add(n)
        while stack:
            c = stack.pop()
            comp.append(c)
            for m in adj[c]:
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        if len(comp) > len(best):
            best = comp
    keep = set(best)
    pos = {k: v for k, v in pos.items() if k in keep}
    adj = {k: {m: c for m, c in v.items() if m in keep} for k, v in adj.items() if k in keep}
    return pos, adj


def astar(pos, adj, a, b):
    openh = [(0, a)]
    came, g = {a: None}, {a: 0.0}
    while openh:
        _, c = heapq.heappop(openh)
        if c == b:
            break
        for m, cost in adj[c].items():
            ng = g[c] + cost
            if ng < g.get(m, 1e18):
                g[m] = ng
                came[m] = c
                heapq.heappush(openh, (ng + math.dist(pos[m], pos[b]), m))
    if b not in came:
        return []
    path, c = [], b
    while c is not None:
        path.append(c)
        c = came[c]
    return path[::-1]


def nearest_node(pos, p, ok=None):
    best, bd = None, 1e18
    for k, q in pos.items():
        if ok and not ok(k):
            continue
        d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2
        if d < bd:
            best, bd = k, d
    return best


class SegIndex:
    """Spatial hash of road centre segments for distance queries."""

    def __init__(self, roads, cell=40.0):
        self.cell = cell
        self.grid = defaultdict(list)
        for ri, r in enumerate(roads):
            for a, b in zip(r["pts"], r["pts"][1:]):
                x0, x1 = sorted((a[0], b[0]))
                z0, z1 = sorted((a[1], b[1]))
                for cx in range(int(math.floor(x0 / cell)), int(math.floor(x1 / cell)) + 1):
                    for cz in range(int(math.floor(z0 / cell)), int(math.floor(z1 / cell)) + 1):
                        self.grid[(cx, cz)].append((a, b, ri))
        self.roads = roads

    def near(self, p, radius):
        c = self.cell
        out = []
        for cx in range(int(math.floor((p[0] - radius) / c)), int(math.floor((p[0] + radius) / c)) + 1):
            for cz in range(int(math.floor((p[1] - radius) / c)), int(math.floor((p[1] + radius) / c)) + 1):
                out.extend(self.grid.get((cx, cz), ()))
        return out

    def clearance(self, p, radius=40.0):
        """Smallest (distance - half width) to any road near p."""
        best = 1e9
        for a, b, ri in self.near(p, radius):
            d = seg_dist(p, a, b)[0] - self.roads[ri]["width"] / 2
            best = min(best, d)
        return best


class Occupancy:
    def __init__(self, cell=20.0):
        self.cell = cell
        self.grid = defaultdict(list)

    def add(self, poly):
        xs = [p[0] for p in poly]
        zs = [p[1] for p in poly]
        box = (min(xs), min(zs), max(xs), max(zs))
        for cx in range(int(box[0] // self.cell), int(box[2] // self.cell) + 1):
            for cz in range(int(box[1] // self.cell), int(box[3] // self.cell) + 1):
                self.grid[(cx, cz)].append((box, poly))

    def hits(self, poly):
        xs = [p[0] for p in poly]
        zs = [p[1] for p in poly]
        box = (min(xs), min(zs), max(xs), max(zs))
        for cx in range(int(box[0] // self.cell), int(box[2] // self.cell) + 1):
            for cz in range(int(box[1] // self.cell), int(box[3] // self.cell) + 1):
                for b, other in self.grid.get((cx, cz), ()):
                    if b[0] < box[2] and b[2] > box[0] and b[1] < box[3] and b[3] > box[1]:
                        if any(point_in_poly(p, other) for p in poly) or any(point_in_poly(p, poly) for p in other):
                            return True
                        if polys_cross(poly, other):
                            return True
        return False


def polys_cross(a, b):
    def inter(p1, p2, p3, p4):
        def ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
        return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)
    for i in range(len(a)):
        for j in range(len(b)):
            if inter(a[i], a[(i + 1) % len(a)], b[j], b[(j + 1) % len(b)]):
                return True
    return False


def rect_poly(c, ang, L, W):
    ca, sa = math.cos(ang), math.sin(ang)
    out = []
    for u, v in ((-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2)):
        out.append((c[0] + u * ca - v * sa, c[1] + u * sa + v * ca))
    return out


# ---------------------------------------------------------------- buildings

FACADES = {
    "panel5": dict(floor=2.8, texture="khrushchovka", ground="entrance", roof="flat"),
    "panel9": dict(floor=2.8, texture="panel9", ground="entrance", roof="flat"),
    "brick": dict(floor=3.2, texture="brick_soviet", ground="brick_soviet", roof="flat"),
    "public": dict(floor=3.4, texture="public_plaster", ground="public_door", roof="flat"),
    "shop": dict(floor=3.4, texture="plaster_upper", ground="shopfront", roof="flat"),
    "house": dict(floor=2.9, texture="house_plaster", ground="house_plaster", roof="gable"),
    "industrial": dict(floor=7.0, texture="industrial", ground="industrial", roof="flat"),
    "garage": dict(floor=2.6, texture="garage_row", ground="garage_row", roof="flat"),
    "church": dict(floor=9.0, texture="church_wall", ground="church_wall", roof="gable"),
    "ruin": dict(floor=2.5, texture="brick_soviet", ground="brick_soviet", roof="none"),
}
HOUSE_COLORS = ["#d8d2c0", "#e6d9a8", "#c9d6c4", "#b9c9d6", "#e8e2d6", "#d9b9a0", "#c8c0b0", "#e0cfa0", "#a9c0a4", "#d6c6d6"]
BLOCK_COLORS = ["#d9d6cc", "#cfcbc0", "#e2ddd0", "#c8c4bb", "#d7d0c1"]
ROOF_COLORS = ["#8a8c8a", "#7e8180", "#7b3a2e", "#5b3c2c", "#3f5a3c", "#3b4f66", "#90918c", "#6b2e2a"]
FENCE_STYLES = ["profnastil", "profnastil", "profnastil", "picket", "concrete", "brick", "mesh"]
FENCE_COLORS = ["#3f6a45", "#5a3b2b", "#2f4f7a", "#7a2f2a", "#8c8a80", "#6b5a3a", "#3a5560"]


def classify_building(t, poly, area, cen, near_trunk):
    b = t.get("building", "yes")
    levels = None
    try:
        levels = int(float(t.get("building:levels", "").split(";")[0]))
    except ValueError:
        pass
    amen = t.get("amenity", "")
    if b in ("church", "temple", "cathedral", "chapel") or amen == "place_of_worship":
        return "church", levels or 1
    if b in ("ruins",) or t.get("ruins") == "yes":
        return "ruin", 1
    if b in ("garage", "garages"):
        return "garage", 1
    if b in ("industrial", "warehouse", "manufacture", "hangar", "shed", "barn", "service", "roof"):
        return "industrial", 1
    if b in ("school", "hospital", "kindergarten", "university", "college", "public", "civic", "government", "train_station", "office") or amen in ("school", "hospital", "kindergarten", "townhall"):
        return "public", levels or (3 if area > 600 else 2)
    if b in ("commercial", "retail", "supermarket", "kiosk") or t.get("shop"):
        return "shop", levels or (1 if area < 250 else 2)
    if b == "apartments" or (b in ("residential", "yes", "dormitory") and area > 260):
        if levels is None:
            levels = 9 if area > 1100 and rng.random() < .35 else 5
        if levels >= 9:
            return "panel9", levels
        if levels <= 3:
            return "brick", levels
        return ("panel5" if rng.random() < .75 else "brick"), levels
    if b in ("house", "detached", "semidetached_house", "bungalow", "farm", "cabin", "residential", "yes") and area < 260:
        return "house", levels or (2 if area > 150 and rng.random() < .25 else 1)
    if area > 1500:
        return "industrial", 1
    return ("shop" if near_trunk else "brick"), levels or 2


def main():
    print("loading OSM and DEM", flush=True)
    nodes, ways, rels = load_osm()
    mos, dz, tx0, ty0 = load_dem()
    raw = sample_dem(mos, dz, tx0, ty0)
    H = blur(raw, 2.6)  # SRTM terraces out, valley shape in

    polys = [(t, p, i) for t, p, i in areas_from_osm(nodes, ways, rels) if any(in_rect(q, TERR, 300) for q in p)]
    roads, paths = build_roads(nodes, ways)
    print("roads", len(roads), "paths", len(paths), "areas", len(polys), flush=True)

    # ---------------- water
    water_polys = []
    for t, p, i in polys:
        if t.get("natural") == "water" or t.get("waterway") == "riverbank" or t.get("landuse") in ("reservoir", "basin"):
            water_polys.append(dict(pts=p, kind=t.get("water", "lake"), id=i))
    rivers = []
    for w in ways.values():
        t = w.get("tags", {})
        if t.get("waterway") in ("river", "stream", "canal", "ditch"):
            pts = way_pts(w, nodes)
            if len(pts) > 1 and any(in_rect(p, TERR, 200) for p in pts):
                rivers.append(dict(pts=densify(pts, 10), width=42.0 if t["waterway"] == "river" else 3.5,
                                   river=t["waterway"] == "river", name=t.get("name", "")))
    # river surface: running minimum downstream, then smoothed
    for r in rivers:
        lv = []
        for p in r["pts"]:
            vals = [sample_grid(H, p[0] + dx, p[1] + dz2) for dx in (-15, 0, 15) for dz2 in (-15, 0, 15)]
            lv.append(min(vals) - (0.6 if r["river"] else 0.3))
        for i in range(1, len(lv)):
            lv[i] = min(lv[i], lv[i - 1])
        s = arc_lengths(r["pts"])
        r["levels"] = smooth_profile(lv, s, 120.0) if len(lv) < 900 else lv
    level_img = canvas("F", -1000.0)
    water_mask = canvas("L", 0)
    ld = ImageDraw.Draw(level_img)
    wd = ImageDraw.Draw(water_mask)
    river_pts_all = [(p, lvl) for r in rivers if r["river"] for p, lvl in zip(r["pts"], r["levels"])]
    for wp in water_polys:
        if wp["kind"] in ("river", "riverbank", "stream"):
            c = centroid(wp["pts"])
            near = min(river_pts_all, key=lambda q: (q[0][0] - c[0]) ** 2 + (q[0][1] - c[1]) ** 2) if river_pts_all else None
            level = near[1] if near else min(sample_grid(H, *q) for q in wp["pts"]) - .5
        else:
            inside = [sample_grid(H, *q) for q in wp["pts"]]
            level = float(np.percentile(inside, 15)) - .4
        wp["level"] = level
        ld.polygon(to_px(wp["pts"]), fill=level)
        wd.polygon(to_px(wp["pts"]), fill=255)
    for r in rivers:
        wpx = max(1, int(round(r["width"] / STEP)))
        for (a, b), la in zip(zip(r["pts"], r["pts"][1:]), r["levels"]):
            ld.line(to_px([a, b]), fill=la, width=wpx, joint="curve")
            wd.line(to_px([a, b]), fill=255, width=wpx, joint="curve")
    level = np.asarray(level_img, np.float32).copy()
    wmask = np.asarray(water_mask, np.float32) / 255
    # spread levels a few cells beyond the edge so the banks know their water
    lvl_spread = level.copy()
    for _ in range(4):
        pad = np.pad(lvl_spread, 1, constant_values=-1000)
        nb = np.max(np.stack([pad[1:-1, :-2], pad[1:-1, 2:], pad[:-2, 1:-1], pad[2:, 1:-1]]), 0)
        lvl_spread = np.where(lvl_spread > -999, lvl_spread, nb)
    inside = blur(wmask, 1.6)
    near_bank = blur(wmask, 3.5)
    has = lvl_spread > -999
    depth = 0.8 + 2.6 * np.clip(inside * 1.6 - .4, 0, 1)
    carved = np.where(wmask > .5, np.minimum(H, lvl_spread - depth), H)
    bank = np.clip(near_bank * 2.2, 0, 1) * has * (wmask <= .5)
    carved = np.where(bank > 0, carved * (1 - bank) + np.minimum(carved, lvl_spread + .5 + (1 - bank) * 6) * bank, carved)
    H = carved

    # ---------------- roads into the terrain
    road_h = canvas("F", 0.0)
    road_core = canvas("L", 0)
    rh, rc = ImageDraw.Draw(road_h), ImageDraw.Draw(road_core)
    bridges = []
    for r in roads:
        dense = densify(r["pts"], 6)
        s = arc_lengths(dense)
        prof = [sample_grid(H, *p) for p in dense]
        if r["bridge"]:
            a, b = prof[0], prof[-1]
            lv = [lvl_spread[int(min(max(grid_xy(p)[1], 0), NZ - 1)), int(min(max(grid_xy(p)[0], 0), NX - 1))] for p in dense]
            top = max(lv) + 3.5 if max(lv) > -999 else max(a, b)
            prof = [max(a + (b - a) * (si / max(s[-1], 1)), top - 1.2 * 0) for si in s]
            prof = smooth_profile(prof, s, 25)
        else:
            prof = smooth_profile(prof, s, 70.0 if r["rank"] >= 8 else 45.0)
        r["dense"], r["prof"] = dense, prof
    for pass_wide in (True, False):
        for r in sorted(roads, key=lambda r: r["rank"]):
            if r["bridge"]:
                continue
            width = r["width"] + (14.0 if pass_wide else 3.0)
            for (a, b), ha, hb in zip(zip(r["dense"], r["dense"][1:]), r["prof"], r["prof"][1:]):
                rh.line(to_px([a, b]), fill=(ha + hb) / 2, width=max(1, int(round(width / STEP))), joint="curve")
                if not pass_wide:
                    rc.line(to_px([a, b]), fill=255, width=max(1, int(round(width / STEP))), joint="curve")
    for r in roads:
        if r["bridge"]:
            bridges.append(dict(pts=r["dense"], prof=r["prof"], width=r["width"] + 3.0, name=r["name"]))
    road_hn = np.asarray(road_h, np.float32)
    core = np.asarray(road_core, np.float32) / 255
    # normalised convolution: road heights spread smoothly into the verges, no ditches
    den = blur(core, 2.2)
    ext = np.where(den > 1e-3, blur(road_hn * core, 2.2) / np.maximum(den, 1e-3), H)
    ext = np.where(core > .5, road_hn, ext)
    wgt = np.maximum(core, np.clip(den * 2.0, 0, 1))
    H = np.where(wmask > .5, H, H * (1 - wgt) + ext * wgt)

    # ---------------- ground types (R grass, G dirt, B rock, A forest floor)
    types = {k: canvas("L", 0) for k in ("dirt", "rock", "forest", "paved")}
    td = {k: ImageDraw.Draw(v) for k, v in types.items()}
    landuse = []
    for t, p, i in polys:
        lu = t.get("landuse") or t.get("natural") or t.get("leisure") or t.get("amenity")
        if not lu:
            continue
        landuse.append(dict(kind=lu, pts=p, name=t.get("name", ""), tags=t, id=i))
        if lu in ("forest", "wood"):
            td["forest"].polygon(to_px(p), fill=255)
        elif lu in ("farmland", "allotments", "construction", "landfill", "brownfield", "industrial", "garages", "railway", "quarry"):
            td["dirt"].polygon(to_px(p), fill=200)
        elif lu in ("bare_rock", "scree", "cliff"):
            td["rock"].polygon(to_px(p), fill=255)
        elif lu in ("marketplace", "parking"):
            td["paved"].polygon(to_px(p), fill=255)
    for w in ways.values():
        t = w.get("tags", {})
        if t.get("natural") == "cliff":
            td["rock"].line(to_px(way_pts(w, nodes)), fill=255, width=4)
    for r in roads:
        if not r["paved"]:
            td["dirt"].line(to_px(r["pts"]), fill=255, width=max(1, int(r["width"] / STEP) + 2))
    gy, gx = np.gradient(H, STEP)
    slope = np.hypot(gx, gy)
    rock = np.clip((slope - .35) * 3.0, 0, 1)
    rock = np.maximum(rock, np.asarray(types["rock"], np.float32) / 255)
    rock = np.maximum(rock, np.clip(blur(wmask, 1.2) * 2 - .2, 0, 1) * np.clip((slope - .15) * 4, 0, 1))  # granite banks
    dirt = np.clip(blur(np.asarray(types["dirt"], np.float32) / 255, 1.0), 0, 1)
    dirt = np.maximum(dirt, np.clip(near_bank * 1.5, 0, 1) * (wmask < .5) * .8)
    forest = blur(np.asarray(types["forest"], np.float32) / 255, 1.0)

    # ---------------- buildings
    seg_index = SegIndex([r for r in roads if not r["bridge"]])
    trunk_roads = [r for r in roads if r["hw"] in ("trunk", "primary", "secondary")]
    trunk_index = SegIndex(trunk_roads) if trunk_roads else None
    occ = Occupancy()
    buildings = []
    for t, p, i in polys:
        if "building" not in t or not any(in_rect(q, TERR) for q in p):
            continue
        if poly_area(p) > 0:
            p = p[::-1]  # clockwise in x-east/z-south = counter-clockwise seen from above
        area = abs(poly_area(p))
        if area < 6:
            continue
        cen = centroid(p)
        near_trunk = trunk_index is not None and trunk_index.clearance(cen, 50) < 25
        style, levels = classify_building(t, p, area, cen, near_trunk)
        fac = FACADES[style]
        height = fac["floor"] * levels + (0.6 if style in ("panel5", "panel9", "brick", "public", "shop") else 0)
        if style == "industrial":
            height = 6.5 + min(6, area / 900)
        if style == "church":
            height = 9.0 + min(6, area / 120)
        ground = [sample_grid(H, *q) for q in p] + [sample_grid(H, *cen)]
        colors = BLOCK_COLORS if style in ("panel5", "panel9", "brick") else HOUSE_COLORS
        b = dict(id=i, style=style, levels=levels, pts=[(round(x, 2), round(z, 2)) for x, z in p],
                 floor_h=fac["floor"], height=round(height, 2), base=round(max(ground) + .15, 2), foot=round(min(ground) - .6, 2),
                 color=rng.choice(colors), roof_color=rng.choice(ROOF_COLORS), name=t.get("name", ""),
                 amenity=t.get("amenity", t.get("shop", "")), roof=fac["roof"], osm=True)
        if style == "house":
            cen2, ang, L, W = min_area_rect(p)
            b["obb"] = [round(cen2[0], 2), round(cen2[1], 2), round(ang, 4), round(L, 2), round(W, 2)]
        buildings.append(b)
        occ.add([(x, z) for x, z in p])
    print("osm buildings", len(buildings), flush=True)

    # ---------------- garage co-ops: rows of boxes inside landuse=garages
    for lu in landuse:
        if lu["kind"] != "garages" or not any(in_rect(q, TERR) for q in lu["pts"]):
            continue
        cen, ang, L, W = min_area_rect(lu["pts"])
        ca, sa = math.cos(ang), math.sin(ang)
        rows = max(1, int((W - 4) // 14))
        for row in range(rows):
            v = -W / 2 + 4 + row * 14 + 3
            n = int((L - 4) // 3.4)
            for k in range(n):
                u = -L / 2 + 2 + k * 3.4 + 1.7
                c = (cen[0] + u * ca - v * sa, cen[1] + u * sa + v * ca)
                box = rect_poly(c, ang, 3.2, 6.0)
                if not all(point_in_poly(q, lu["pts"]) for q in box) or occ.hits(box) or seg_index.clearance(c, 30) < 3:
                    continue
                g = [sample_grid(H, *q) for q in box]
                buildings.append(dict(id=0, style="garage", levels=1, pts=[(round(x, 2), round(z, 2)) for x, z in box[::-1]],
                                      floor_h=2.6, height=2.6, base=round(max(g) + .1, 2), foot=round(min(g) - .5, 2),
                                      color=rng.choice(["#9a9488", "#a8a090", "#8c8c84"]), roof_color="#4a4a48",
                                      name="", amenity="", roof="flat", osm=False, door=[round(-sa * (1 if row % 2 == 0 else -1), 3), round(ca * (1 if row % 2 == 0 else -1), 3)]))
                occ.add(box)

    # ---------------- private sector: houses, fences, gardens along residential streets
    blocked_landuse = [lu["pts"] for lu in landuse if lu["kind"] in (
        "industrial", "commercial", "retail", "forest", "wood", "cemetery", "garages", "quarry", "railway", "park",
        "pitch", "stadium", "school", "hospital", "kindergarten", "water", "wetland", "grass", "religious", "farmland",
        "landfill", "military", "marketplace", "parking", "allotments", "construction", "scrub", "heath", "meadow")]
    blocked_boxes = [(min(p[0] for p in q), min(p[1] for p in q), max(p[0] for p in q), max(p[1] for p in q), q) for q in blocked_landuse]

    def blocked(pt):
        for x0, z0, x1, z1, q in blocked_boxes:
            if x0 <= pt[0] <= x1 and z0 <= pt[1] <= z1 and point_in_poly(pt, q):
                return True
        gx, gz = grid_xy(pt)
        if not (0 <= gx < NX - 1 and 0 <= gz < NZ - 1):
            return True
        return wmask[int(gz), int(gx)] > .1 or lvl_spread[int(gz), int(gx)] > -999

    houses, fences, trees = [], [], []
    plaza = None
    for e in nodes.values():
        if e.get("tags", {}).get("place") == "square":
            plaza = to_local(e["lon"], e["lat"])
    plaza = plaza or (250.0, -480.0)
    for r in roads:
        if r["hw"] not in ("residential", "unclassified", "living_street", "track", "tertiary") or r["bridge"]:
            continue
        if r["hw"] == "track" and not any(in_rect(p, PLAY) for p in r["pts"]):
            continue
        dense = densify(r["pts"], 1.0)
        s = arc_lengths(dense)
        total = s[-1]
        for side in (-1, 1):
            pos = rng.uniform(4, 12)
            while pos < total - 6:
                i = min(range(len(s)), key=lambda k: abs(s[k] - pos)) if len(s) < 60 else int(pos)
                i = min(i, len(dense) - 2)
                a, b = dense[i], dense[i + 1]
                dx, dz2 = b[0] - a[0], b[1] - a[1]
                ln = math.hypot(dx, dz2) or 1
                tx, tz = dx / ln, dz2 / ln
                nx, nz = -tz * side, tx * side
                hw = r["width"] / 2
                wid = rng.uniform(8.0, 11.5)
                dep = rng.uniform(7.0, 9.5)
                setback = rng.uniform(4.0, 8.0)
                plot = rng.uniform(19.0, 27.0)
                c = (a[0] + nx * (hw + 1.5 + setback + dep / 2), a[1] + nz * (hw + 1.5 + setback + dep / 2))
                ang = math.atan2(tz, tx)
                box = rect_poly(c, ang, wid, dep)
                grow = rect_poly(c, ang, wid + 3.0, dep + 3.0)
                ok = in_rect(c, TERR, -20) and not blocked(c) and not occ.hits(grow)
                if ok:
                    ok = all(seg_index.clearance(q, 40) > 2.5 for q in box)
                if ok:
                    g = [sample_grid(H, *q) for q in box]
                    ok = max(g) - min(g) < 2.2
                if ok:
                    levels = 2 if rng.random() < .12 else 1
                    style_roof = "hip" if rng.random() < .3 else "gable"
                    houses.append(dict(style="house", levels=levels, pts=[(round(x, 2), round(z, 2)) for x, z in box[::-1]],
                                       floor_h=2.9, height=2.9 * levels, base=round(max(g) + .35, 2), foot=round(min(g) - .6, 2),
                                       color=rng.choice(HOUSE_COLORS), roof_color=rng.choice(ROOF_COLORS), roof=style_roof,
                                       obb=[round(c[0], 2), round(c[1], 2), round(ang, 4), round(wid, 2), round(dep, 2)], osm=False))
                    occ.add(grow)
                    # front fence on the plot line, gate in the middle
                    f0 = (a[0] + nx * (hw + 1.6) - tx * plot / 2, a[1] + nz * (hw + 1.6) - tz * plot / 2)
                    f1 = (a[0] + nx * (hw + 1.6) + tx * plot / 2, a[1] + nz * (hw + 1.6) + tz * plot / 2)
                    if all(seg_index.clearance(q, 40) > .9 for q in (f0, f1)) and not blocked(f0) and not blocked(f1):
                        style = rng.choice(FENCE_STYLES)
                        fences.append(dict(a=[round(f0[0], 2), round(f0[1], 2)], b=[round(f1[0], 2), round(f1[1], 2)],
                                           style=style, color=rng.choice(FENCE_COLORS), gate=.5,
                                           h=1.9 if style in ("profnastil", "concrete", "brick") else 1.3))
                    for _ in range(rng.randint(1, 3)):
                        back = hw + 1.5 + setback + dep + rng.uniform(3, 12)
                        along = rng.uniform(-plot / 2, plot / 2)
                        tp = (a[0] + nx * back + tx * along, a[1] + nz * back + tz * along)
                        if not blocked(tp) and seg_index.clearance(tp, 30) > 2:
                            trees.append((tp, "fruit" if rng.random() < .6 else "deciduous", rng.uniform(.7, 1.2)))
                pos += plot
    buildings += houses
    print("houses", len(houses), "fences", len(fences), flush=True)

    # ---------------- trees
    def scatter(poly, density, kind, cap):
        xs = [p[0] for p in poly]
        zs = [p[1] for p in poly]
        area = abs(poly_area(poly))
        n = min(cap, int(area * density))
        out = 0
        tries = 0
        while out < n and tries < n * 4:
            tries += 1
            p = (rng.uniform(min(xs), max(xs)), rng.uniform(min(zs), max(zs)))
            if not in_rect(p, TERR) or not point_in_poly(p, poly):
                continue
            gx, gz = grid_xy(p)
            if wmask[int(gz), int(gx)] > .1 or core[int(gz), int(gx)] > .1:
                continue
            trees.append((p, kind, rng.uniform(.75, 1.3)))
            out += 1
    for lu in landuse:
        k = lu["kind"]
        if not any(in_rect(q, TERR) for q in lu["pts"]):
            continue
        if k in ("forest", "wood"):
            scatter(lu["pts"], 1 / 55, "pine" if rng.random() < .75 else "deciduous", 4000)
        elif k in ("park", "cemetery", "grass", "garden", "religious"):
            scatter(lu["pts"], 1 / 160, "deciduous", 400)
        elif k in ("scrub", "heath", "meadow"):
            scatter(lu["pts"], 1 / 400, "deciduous", 200)
    for w in ways.values():
        if w.get("tags", {}).get("natural") == "tree_row":
            for p in densify(way_pts(w, nodes), 8):
                if in_rect(p, TERR):
                    trees.append((p, "poplar", rng.uniform(.9, 1.2)))
    for r in roads:
        if r["hw"] in ("residential", "tertiary", "secondary", "unclassified") and rng.random() < .55:
            for p in densify(r["pts"], 17)[1:-1]:
                if rng.random() < .35:
                    side = rng.choice((-1, 1))
                    i = r["pts"]
                    q = (p[0] + side * (r["width"] / 2 + 3.2) * .0, p[1])
                    near = min(zip(r["pts"], r["pts"][1:]), key=lambda ab: seg_dist(p, *ab)[0])
                    dx, dz2 = near[1][0] - near[0][0], near[1][1] - near[0][1]
                    ln = math.hypot(dx, dz2) or 1
                    q = (p[0] - dz2 / ln * side * (r["width"] / 2 + 3.4), p[1] + dx / ln * side * (r["width"] / 2 + 3.4))
                    if not blocked(q) and seg_index.clearance(q, 30) > 1.8 and not occ.hits(rect_poly(q, 0, 2, 2)):
                        trees.append((q, "poplar" if rng.random() < .25 else "deciduous", rng.uniform(.8, 1.25)))
    print("trees", len(trees), flush=True)

    # ---------------- sidewalks (town streets, cut back at junctions)
    sidewalks = []
    town = lambda p: math.dist(p, plaza) < 1350
    for r in roads:
        if r["hw"] not in ("trunk", "primary", "secondary", "tertiary", "residential", "living_street") or r["bridge"] or not r["paved"]:
            continue
        for side in (-1, 1):
            run = []
            dense = r["dense"]
            for i in range(len(dense) - 1):
                a, b = dense[i], dense[i + 1]
                dx, dz2 = b[0] - a[0], b[1] - a[1]
                ln = math.hypot(dx, dz2) or 1
                off = r["width"] / 2 + 1.25
                m = ((a[0] + b[0]) / 2 - dz2 / ln * side * off, (a[1] + b[1]) / 2 + dx / ln * side * off)
                good = town(m)
                if good:
                    for sa, sb, ri in seg_index.near(m, 30):
                        rr = seg_index.roads[ri]
                        if rr is r:
                            continue
                        if seg_dist(m, sa, sb)[0] < rr["width"] / 2 + 3.5:
                            good = False
                            break
                if good:
                    run.append(i)
                elif len(run) > 1:
                    sidewalks.append(dict(road=r["id"], side=side, idx=run[:], width=2.5))
                    run = []
                else:
                    run = []
            if len(run) > 1:
                sidewalks.append(dict(road=r["id"], side=side, idx=run[:], width=2.5))
    road_by_id = {r["id"]: r for r in roads}
    sw_out = []
    ped_points = []
    for sw in sidewalks:
        r = road_by_id[sw["road"]]
        pts = []
        for i in sw["idx"] + [sw["idx"][-1] + 1]:
            a = r["dense"][max(0, i - 1)]
            b = r["dense"][min(len(r["dense"]) - 1, i + 1)]
            dx, dz2 = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dz2) or 1
            off = r["width"] / 2 + 1.25
            p = r["dense"][i]
            pts.append((round(p[0] - dz2 / ln * sw["side"] * off, 2), round(p[1] + dx / ln * sw["side"] * off, 2), round(r["prof"][i], 2)))
        sw_out.append(dict(pts=pts, width=2.5))
        if in_rect(pts[0][:2], PLAY) and len(pts) > 6:
            ped_points.append([list(pts[0]), list(pts[-1])])

    # ---------------- story locations on real places
    def poi(pred):
        out = []
        for e in nodes.values():
            t = e.get("tags", {})
            if t and pred(t):
                out.append((to_local(e["lon"], e["lat"]), t))
        for t, p, i in polys:
            if pred(t):
                out.append((centroid(p), t))
        return out

    graph_pos, graph_adj = road_graph(roads)
    drivable_ok = {}
    for r in roads:
        for i in r["ids"]:
            drivable_ok[i] = r["hw"] not in ("trunk", "trunk_link", "track")

    def access(anchor, avoid_trunk=True):
        """Point on the kerb of the nearest suitable road, facing the anchor."""
        best = None
        for r in roads:
            if r["bridge"] or (avoid_trunk and r["hw"] in ("trunk", "trunk_link")) or r["hw"] == "track":
                continue
            if not any(r["ids"][k] in graph_pos for k in range(len(r["ids"]))):
                continue
            for a, b in zip(r["pts"], r["pts"][1:]):
                d, q, _ = seg_dist(anchor, a, b)
                if best is None or d < best[0]:
                    best = (d, q, r, a, b)
        d, q, r, a, b = best
        dx, dz2 = anchor[0] - q[0], anchor[1] - q[1]
        ln = math.hypot(dx, dz2) or 1
        off = min(r["width"] / 2 + 1.2, ln)
        kerb = (q[0] + dx / ln * off, q[1] + dz2 / ln * off)
        heading = math.atan2(-(b[0] - a[0]), -(b[1] - a[1]))
        lane = (q[0] + dx / ln * (r["width"] / 4), q[1] + dz2 / ln * (r["width"] / 4))
        return dict(pos=[round(kerb[0], 2), round(sample_grid(H, *kerb) + .05, 2), round(kerb[1], 2)],
                    car=[round(lane[0], 2), round(sample_grid(H, *lane) + .05, 2), round(lane[1], 2)],
                    car_heading=round(heading, 3), anchor=[round(anchor[0], 2), round(anchor[1], 2)])

    cafes = poi(lambda t: t.get("amenity") == "cafe")
    markets = poi(lambda t: t.get("amenity") == "marketplace")
    cafe = min(cafes, key=lambda c: math.dist(c[0], plaza))[0] if cafes else (plaza[0] + 60, plaza[1] + 40)
    market = min(markets, key=lambda c: math.dist(c[0], plaza))[0] if markets else (plaza[0] - 100, plaza[1] + 600)
    garage_lu = [lu for lu in landuse if lu["kind"] == "garages" and in_rect(centroid(lu["pts"]), PLAY)]
    garages = min((centroid(g["pts"]) for g in garage_lu), key=lambda c: math.dist(c, plaza)) if garage_lu else (plaza[0] + 300, plaza[1])
    industrial = [lu for lu in landuse if lu["kind"] == "industrial" and in_rect(centroid(lu["pts"]), PLAY)]
    saw = sorted(industrial, key=lambda lu: -abs(poly_area(lu["pts"])) if 350 < math.dist(centroid(lu["pts"]), plaza) < 1400 else 0)
    sawmill = centroid(saw[0]["pts"]) if saw else (plaza[0] - 500, plaza[1] - 200)
    quarry_mem = poi(lambda t: "кар" in t.get("name", "").lower() and "historic" in t)
    quarry_anchor = quarry_mem[0][0] if quarry_mem else (1150, -600)
    lakes = [wp for wp in water_polys if wp["kind"] not in ("river", "riverbank") and abs(poly_area(wp["pts"])) > 3000 and in_rect(centroid(wp["pts"]), PLAY)]
    quarry_lake = min(lakes, key=lambda wp: math.dist(centroid(wp["pts"]), quarry_anchor)) if lakes else None
    quarry = centroid(quarry_lake["pts"]) if quarry_lake else quarry_anchor
    apartments = [b for b in buildings if b["style"] in ("panel5", "panel9", "brick") and in_rect(centroid(b["pts"]), PLAY)]
    outlying = [b for b in apartments if 550 < math.dist(centroid(b["pts"]), plaza) < 1100 and in_rect(centroid(b["pts"]), PLAY, -150)]
    dorm = max(outlying or apartments, key=lambda b: abs(poly_area(b["pts"]))) if apartments else None
    dorm_c = centroid(dorm["pts"]) if dorm else (plaza[0] + 900, plaza[1] + 500)
    locations = {
        "cafe": access(cafe), "plaza": access(plaza), "market": access(market), "garages": access(garages),
        "sawmill": access(sawmill), "quarry": access(quarry_lake["pts"][0] if quarry_lake else quarry), "dorm": access(dorm_c),
    }
    locations["start"] = dict(locations["cafe"])

    # a garage co-op at the garages location if OSM has few boxes there
    ga = locations["garages"]
    near_boxes = [b for b in buildings if b["style"] == "garage" and math.dist(centroid(b["pts"]), ga["anchor"]) < 140]
    if len(near_boxes) < 12:
        q = ga["anchor"]
        made = 0
        for ring in range(0, 8):
            if made:
                break
            for k in range(16):
                ang = k * math.pi / 8
                c0 = (q[0] + math.cos(ang) * ring * 12, q[1] + math.sin(ang) * ring * 12)
                for rot in (0.0, math.pi / 2, math.pi / 4):
                    row = []
                    for side in (-1, 1):
                        for n in range(-6, 7):
                            c = (c0[0] + math.cos(rot) * n * 3.4 - math.sin(rot) * side * 6.5,
                                 c0[1] + math.sin(rot) * n * 3.4 + math.cos(rot) * side * 6.5)
                            row.append((c, rect_poly(c, rot, 3.2, 6.0), side))
                    hull = rect_poly(c0, rot, 46, 20)
                    if occ.hits(hull) or any(seg_index.clearance(p, 40) < 2 for p in hull) or any(blocked(p) and not any(point_in_poly(p, lu["pts"]) for lu in landuse if lu["kind"] == "garages") for p in hull):
                        continue
                    g = [sample_grid(H, *p) for p in hull]
                    if max(g) - min(g) > 2.5:
                        continue
                    for c, box, side in row:
                        gb = [sample_grid(H, *p) for p in box]
                        buildings.append(dict(id=0, style="garage", levels=1, pts=[(round(x, 2), round(z, 2)) for x, z in box[::-1]],
                                              floor_h=2.6, height=2.6, base=round(max(gb) + .1, 2), foot=round(min(gb) - .5, 2),
                                              color=rng.choice(["#9a9488", "#a8a090", "#8c8c84"]), roof_color="#4a4a48",
                                              name="", amenity="", roof="flat", osm=False, door=[round(math.sin(rot) * side, 3), round(-math.cos(rot) * side, 3)]))
                    occ.add(hull)
                    locations["garages"] = access(c0)
                    made = len(row)
                    break
                if made:
                    break
        print("garage co-op boxes", made, flush=True)
    for k, v in locations.items():
        print("LOC", k, v["pos"], flush=True)

    # ---------------- traffic loops on the real street graph
    def route_pts(seq):
        out = []
        for a, b in zip(seq, seq[1:]):
            na = nearest_node(graph_pos, a)
            nb = nearest_node(graph_pos, b)
            path = astar(graph_pos, graph_adj, na, nb)
            for n in path:
                p = graph_pos[n]
                if not out or math.dist(out[-1][::2], p) > 5:
                    out.append([round(p[0], 2), round(sample_grid(H, *p) + .3, 2), round(p[1], 2)])
        return out
    L = locations
    a2 = lambda k: tuple(L[k]["anchor"])
    loops = [
        route_pts([a2("plaza"), a2("market"), a2("garages"), a2("plaza")]),
        route_pts([a2("market"), a2("sawmill"), a2("cafe"), a2("market")]),
        route_pts([a2("plaza"), a2("quarry"), a2("dorm"), a2("plaza")]),
        route_pts([a2("cafe"), a2("dorm"), a2("market"), a2("cafe")]),
    ]
    loops = [l for l in loops if len(l) > 4]

    # ---------------- props
    lamps, poles, stops = [], [], []
    for r in roads:
        if r["bridge"]:
            continue
        if r["hw"] in ("trunk", "primary", "secondary", "tertiary") and any(town(p) for p in r["pts"]):
            for k, p in enumerate(densify(r["pts"], 34)[1:-1]):
                near = min(zip(r["pts"], r["pts"][1:]), key=lambda ab: seg_dist(p, *ab)[0])
                dx, dz2 = near[1][0] - near[0][0], near[1][1] - near[0][1]
                ln = math.hypot(dx, dz2) or 1
                side = 1 if k % 2 == 0 else -1
                q = (p[0] - dz2 / ln * side * (r["width"] / 2 + .9), p[1] + dx / ln * side * (r["width"] / 2 + .9))
                if not occ.hits(rect_poly(q, 0, 1, 1)) and town(q):
                    lamps.append([round(q[0], 2), round(sample_grid(H, *q), 2), round(q[1], 2), round(math.atan2(dz2 * side, -dx * side), 3)])
        elif r["hw"] in ("residential", "unclassified", "living_street"):
            for p in densify(r["pts"], 38)[1:-1]:
                near = min(zip(r["pts"], r["pts"][1:]), key=lambda ab: seg_dist(p, *ab)[0])
                dx, dz2 = near[1][0] - near[0][0], near[1][1] - near[0][1]
                ln = math.hypot(dx, dz2) or 1
                q = (p[0] - dz2 / ln * (r["width"] / 2 + .8), p[1] + dx / ln * (r["width"] / 2 + .8))
                poles.append([round(q[0], 2), round(sample_grid(H, *q), 2), round(q[1], 2), round(math.atan2(-dx, -dz2), 3)])
    for e in nodes.values():
        t = e.get("tags", {})
        if t.get("highway") == "bus_stop" or t.get("public_transport") == "platform" or t.get("amenity") == "bus_station":
            p = to_local(e["lon"], e["lat"])
            if in_rect(p, TERR):
                stops.append([round(p[0], 2), round(sample_grid(H, *p), 2), round(p[1], 2), 0.0])

    # ---------------- districts (10 m cells)
    DSTEP = 10.0
    dnx, dnz = int((TERR[2] - TERR[0]) / DSTEP) + 1, int((TERR[3] - TERR[1]) / DSTEP) + 1
    names = ["ПРИВАТНИЙ СЕКТОР", "ЦЕНТР КОРОСТИШЕВА", "СОБОРНА ПЛОЩА", "ЦЕНТРАЛЬНИЙ РИНОК", "КИЇВСЬКА ВУЛИЦЯ",
             "ЗАРІЧЧЯ", "КАР’ЄР І ТЕТЕРІВ", "ПРОМЗОНА", "ЛІС НАД ТЕТЕРЕВОМ", "П’ЯТИПОВЕРХІВКИ", "ГАРАЖІ", "ОКОЛИЦІ"]
    dimg = Image.new("L", (dnx, dnz), 11)
    dd = ImageDraw.Draw(dimg)
    sc = lambda pts: [((p[0] - TERR[0]) / DSTEP, (p[1] - TERR[1]) / DSTEP) for p in pts]
    for lu in landuse:
        if lu["kind"] == "residential":
            dd.polygon(sc(lu["pts"]), fill=0)
    river_main = [r for r in rivers if r["river"]]
    zar = [e for e in nodes.values() if e.get("tags", {}).get("name") == "Заріччя"]
    if zar:
        zc = to_local(zar[0]["lon"], zar[0]["lat"])
        dd.ellipse([((zc[0] - 520) - TERR[0]) / DSTEP, ((zc[1] - 650) - TERR[1]) / DSTEP, ((zc[0] + 650) - TERR[0]) / DSTEP, ((zc[1] + 650) - TERR[1]) / DSTEP], fill=5)
    dd.ellipse([((plaza[0] - 520) - TERR[0]) / DSTEP, ((plaza[1] - 420) - TERR[1]) / DSTEP, ((plaza[0] + 380) - TERR[0]) / DSTEP, ((plaza[1] + 560) - TERR[1]) / DSTEP], fill=1)
    for b in buildings:
        if b["style"] in ("panel5", "panel9"):
            c = centroid(b["pts"])
            dd.ellipse([(c[0] - 45 - TERR[0]) / DSTEP, (c[1] - 45 - TERR[1]) / DSTEP, (c[0] + 45 - TERR[0]) / DSTEP, (c[1] + 45 - TERR[1]) / DSTEP], fill=9)
    for lu in landuse:
        if lu["kind"] in ("industrial",):
            dd.polygon(sc(lu["pts"]), fill=7)
        if lu["kind"] in ("forest", "wood") and centroid(lu["pts"])[1] > 300:
            dd.polygon(sc(lu["pts"]), fill=8)
        if lu["kind"] == "garages":
            dd.polygon(sc(lu["pts"]), fill=10)
    for r in roads:
        if r["hw"] in ("trunk", "trunk_link") or r["name"] == "Київська вулиця":
            dd.line(sc(r["pts"]), fill=4, width=7)
    for r in river_main:
        dd.line(sc(r["pts"]), fill=6, width=14)
    if quarry_lake:
        qc = centroid(quarry_lake["pts"])
        dd.ellipse([(qc[0] - 260 - TERR[0]) / DSTEP, (qc[1] - 260 - TERR[1]) / DSTEP, (qc[0] + 260 - TERR[0]) / DSTEP, (qc[1] + 260 - TERR[1]) / DSTEP], fill=6)
    m = market
    dd.ellipse([(m[0] - 110 - TERR[0]) / DSTEP, (m[1] - 110 - TERR[1]) / DSTEP, (m[0] + 110 - TERR[0]) / DSTEP, (m[1] + 110 - TERR[1]) / DSTEP], fill=3)
    dd.ellipse([(plaza[0] - 95 - TERR[0]) / DSTEP, (plaza[1] - 95 - TERR[1]) / DSTEP, (plaza[0] + 95 - TERR[0]) / DSTEP, (plaza[1] + 95 - TERR[1]) / DSTEP], fill=2)
    DATA.mkdir(parents=True, exist_ok=True)
    dimg.save(DATA / "districts.png")

    # ---------------- terrain outputs
    H = H.astype(np.float32)
    (DATA / "heightfield.bin").write_bytes(H.astype("<f4").tobytes())
    lv_out = np.where(wmask > .5, lvl_spread, -1000).astype("<f4")
    (DATA / "waterlevel.bin").write_bytes(lv_out.tobytes())
    grass = np.clip(1 - dirt - rock - forest, 0, 1)
    weights = np.stack([grass, dirt, rock, forest], -1)
    weights /= np.maximum(weights.sum(-1, keepdims=True), 1e-4)
    Image.fromarray((weights * 255).astype(np.uint8), "RGBA").save(SRC / "ground_weights.png")

    # ---------------- radar texture (2 m per pixel)
    RS = 2.0
    rw, rhh = int((TERR[2] - TERR[0]) / RS), int((TERR[3] - TERR[1]) / RS)
    rad = Image.new("RGB", (rw, rhh), (46, 52, 44))
    rd = ImageDraw.Draw(rad)
    rp = lambda pts: [((p[0] - TERR[0]) / RS, (p[1] - TERR[1]) / RS) for p in pts]
    for lu in landuse:
        col = {"forest": (40, 64, 40), "wood": (40, 64, 40), "park": (52, 76, 48), "cemetery": (58, 66, 54), "grass": (54, 70, 50),
               "industrial": (62, 58, 60), "garages": (66, 62, 60), "residential": (54, 56, 50), "quarry": (82, 78, 72)}.get(lu["kind"])
        if col:
            rd.polygon(rp(lu["pts"]), fill=col)
    for wp in water_polys:
        rd.polygon(rp(wp["pts"]), fill=(42, 66, 98))
    for r in rivers:
        rd.line(rp(r["pts"]), fill=(42, 66, 98), width=max(1, int(r["width"] / RS)), joint="curve")
    for b in buildings:
        rd.polygon(rp(b["pts"]), fill=(92, 90, 84))
    for r in sorted(roads, key=lambda r: r["rank"]):
        col = (196, 192, 176) if r["paved"] else (150, 136, 112)
        if r["hw"] in ("trunk", "primary"):
            col = (222, 210, 150)
        rd.line(rp(r["pts"]), fill=col, width=max(2, int(r["width"] / RS)), joint="curve")
    ASSETS.mkdir(parents=True, exist_ok=True)
    rad.save(ASSETS / "radar.png")

    # ---------------- write plans
    def r3(p, h):
        return [round(p[0], 2), round(h, 2), round(p[1], 2)]
    graph_out = dict(nodes={str(k): [round(v[0], 2), round(sample_grid(H, *v), 2), round(v[1], 2)] for k, v in graph_pos.items()},
                     edges=sorted({tuple(sorted((str(a), str(b)))) for a, nb in graph_adj.items() for b in nb}))
    map_roads = [dict(pts=[r3(p, h) for p, h in zip(densify(r["pts"], 25), [0] * 9999)], w=r["width"], paved=r["paved"], hw=r["hw"])
                 for r in roads if any(in_rect(p, TERR) for p in r["pts"])]
    river_lines = [dict(pts=[[round(p[0], 2), round(l, 2), round(p[1], 2)] for p, l in zip(r["pts"][::3], r["levels"][::3])], width=r["width"])
                   for r in rivers if r["river"]]
    plan = dict(
        meta=dict(origin=[LAT0, LON0], step=STEP, terrain=list(TERR), play=list(PLAY), nx=NX, nz=NZ, base_elevation=BASE_ELEV,
                  district_step=DSTEP, district_size=[dnx, dnz], radar_step=RS,
                  attribution="Map data © OpenStreetMap contributors (ODbL). Elevation: SRTM via AWS Terrain Tiles."),
        districts=names, locations=locations, graph=graph_out, traffic=loops,
        roads=map_roads, rivers=river_lines,
        pedestrians=ped_points[:160],
        lamps=lamps, poles=poles, stops=stops,
        trees=[[round(p[0], 2), round(sample_grid(H, *p), 2), round(p[1], 2), k, round(s, 2)] for p, k, s in trees if in_rect(p, TERR)],
        plaza=[round(plaza[0], 2), round(sample_grid(H, *plaza), 2), round(plaza[1], 2)],
    )
    (DATA / "korostyshiv.json").write_text(json.dumps(plan, ensure_ascii=False, separators=(",", ":"), default=float))
    meshes = dict(
        meta=plan["meta"],
        roads=[dict(id=r["id"], hw=r["hw"], width=r["width"], rank=r["rank"], paved=r["paved"], bridge=r["bridge"],
                    pts=[[round(p[0], 2), round(h, 2), round(p[1], 2)] for p, h in zip(r["dense"], r["prof"])]) for r in roads],
        paths=[dict(pts=[[round(p[0], 2), round(p[1], 2)] for p in densify(pa["pts"], 6)], hw=pa["hw"]) for pa in paths],
        sidewalks=sw_out, buildings=buildings, fences=fences,
        water=[dict(pts=[[round(x, 2), round(z, 2)] for x, z in wp["pts"]], level=round(wp["level"], 2)) for wp in water_polys],
        rivers=[dict(pts=[[round(p[0], 2), round(l, 2), round(p[1], 2)] for p, l in zip(r["pts"], r["levels"])], width=r["width"]) for r in rivers],
        paved=[dict(pts=[[round(x, 2), round(z, 2)] for x, z in lu["pts"]], kind=lu["kind"]) for lu in landuse if lu["kind"] in ("marketplace", "parking") or (lu["tags"].get("highway") == "pedestrian")],
        bridges=bridges,
    )
    (SRC / "plan_meshes.json").write_text(json.dumps(meshes, ensure_ascii=False, separators=(",", ":"), default=float))
    print("PLAN_OK buildings", len(buildings), "trees", len(plan["trees"]), "loops", [len(l) for l in loops],
          "graph", len(graph_out["nodes"]), "height", float(H.min()), float(H.max()), flush=True)


if __name__ == "__main__":
    main()
