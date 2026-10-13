"""Build the Korostyshiv texture set from photo scans and photos of the town.

Inputs  assets/source/city/scans/*   CC0 scans (Poly Haven, ambientCG), see sources.json
        assets/source/city/photos/*  photos of Korostyshiv and nearby villages (Wikimedia Commons), see credits.json
Outputs assets/city/tex/*.png and assets/city/tex/manifest.json

Every facade texture is a strip of `bays` window bays by one storey; the mesh builder maps one
texture repeat to that many bays so windows land whole. Textures marked tint=true are neutral and
take the building colour from vertex colours.

Run: python3 -I tools/city/build_city_textures.py [--sheet out.jpg]
"""

import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[2]
SCANS = ROOT / "assets/source/city/scans"
PHOTOS = ROOT / "assets/source/city/photos"
OUT = ROOT / "assets/city/tex"
FONT_BOLD = ROOT / "assets/fonts/head.ttf"
FONT_COND = "/usr/share/fonts/TTF/DejaVuSansCondensed-Bold.ttf"
rng = random.Random(1986)
manifest = {}


# ---------------------------------------------------------------- helpers

def scan(name, size=512):
    p = SCANS / (name + (".png" if (SCANS / (name + ".png")).exists() else ".jpg"))
    im = Image.open(p)
    im = im.convert("RGBA" if im.mode in ("RGBA", "LA") else "RGB")
    return im.resize((size, size), Image.LANCZOS) if im.size != (size, size) else im


def photo(name):
    return Image.open(PHOTOS / (name + ".jpg")).convert("RGB")


def warp(img, quad, size):
    """quad = TL, TR, BR, BL in source pixels -> rectified image of `size`."""
    tl, tr, br, bl = quad
    return img.transform(size, Image.QUAD, (*tl, *bl, *br, *tr), Image.BICUBIC)


def tileable(img, axis="xy", feather=0.22):
    """Hide seams by cross-fading with a half-offset copy near the borders."""
    w, h = img.size
    shifted = ImageChops.offset(img, w // 2 if "x" in axis else 0, h // 2 if "y" in axis else 0)
    mask = Image.new("L", (w, h), 0)
    px = mask.load()
    for y in range(h):
        for x in range(w):
            mx = min(x, w - 1 - x) / (w * feather) if "x" in axis else 1
            my = min(y, h - 1 - y) / (h * feather) if "y" in axis else 1
            px[x, y] = int(255 * max(0.0, min(1.0, min(mx, my))))
    return Image.composite(img, shifted, mask)


def level(img, mean=None, contrast=1.0, sat=1.0, bright=1.0):
    rgb = img.convert("RGB")
    if mean is not None:
        stat = sum(ImageOps.grayscale(rgb).resize((32, 32)).tobytes()) / 1024
        bright *= mean / max(stat, 1)
    out = ImageEnhance.Brightness(rgb).enhance(bright)
    out = ImageEnhance.Contrast(out).enhance(contrast)
    out = ImageEnhance.Color(out).enhance(sat)
    if img.mode == "RGBA":
        out.putalpha(img.getchannel("A"))
    return out


def neutral(img, mean=200):
    """Greyish, bright version for vertex-colour tinting."""
    g = ImageOps.grayscale(img.convert("RGB"))
    g = ImageOps.autocontrast(g, cutoff=1)
    g = level(Image.merge("RGB", (g, g, g)), mean=mean, contrast=0.8)
    warm = Image.new("RGB", g.size, (255, 250, 240))
    return ImageChops.multiply(g, warm)


def gta(img, size, colors=0):
    """Final downsample; optional palette reduction like the PS2-era TXDs."""
    out = img.resize(size, Image.LANCZOS)
    out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    if colors:
        alpha = out.getchannel("A") if out.mode == "RGBA" else None
        out = out.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
        if alpha:
            out.putalpha(alpha)
    return out


def save(name, img, **info):
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / f"{name}.png", optimize=True)
    info.setdefault("tint", False)
    info.setdefault("alpha", img.mode == "RGBA")
    info["size"] = list(img.size)
    manifest[name] = info


def font(size, cond=False):
    return ImageFont.truetype(str(FONT_COND if cond else FONT_BOLD), size)


def fit_text(draw, box, text, fill, cond=True, max_size=120):
    x0, y0, x1, y1 = box
    size = max_size
    while size > 8:
        f = font(size, cond)
        b = draw.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= (x1 - x0) * .92 and b[3] - b[1] <= (y1 - y0) * .78:
            break
        size -= 2
    b = draw.textbbox((0, 0), text, font=f)
    draw.text(((x0 + x1 - (b[2] - b[0])) / 2 - b[0], (y0 + y1 - (b[3] - b[1])) / 2 - b[1]), text, font=f, fill=fill)


def dirt_overlay(img, strength=0.35, streaks=True):
    """Rain streaks under windows and soot at the bottom, multiplied in."""
    w, h = img.size
    m = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(m)
    stain = ImageOps.grayscale(scan("concrete_wall_008" if (SCANS / "concrete_wall_008.jpg").exists() else "dirty_concrete" if (SCANS / "dirty_concrete.jpg").exists() else "cracked_concrete", 512).resize((w, h)))
    stain = ImageOps.autocontrast(stain).point(lambda v: 255 - int((255 - v) * strength))
    if streaks:
        for _ in range(int(w / 18)):
            x = rng.randrange(w)
            d.line([(x, rng.randrange(h // 2)), (x + rng.randint(-3, 3), h)], fill=int(255 - 60 * strength), width=rng.randint(2, 7))
        m = m.filter(ImageFilter.GaussianBlur(3))
    m = ImageChops.multiply(m, stain)
    rgb = ImageChops.multiply(img.convert("RGB"), Image.merge("RGB", (m, m, m)))
    if img.mode == "RGBA":
        rgb.putalpha(img.getchannel("A"))
    return rgb


# ---------------------------------------------------------------- windows and details

SKY_GLASS = [(88, 110, 122), (70, 86, 96), (110, 128, 136), (54, 62, 70)]
CURTAINS = [(196, 170, 120), (160, 70, 60), (210, 205, 190), (90, 120, 150), (180, 150, 170), (120, 140, 90), (230, 220, 200)]


def glass(draw, box, lit=False):
    x0, y0, x1, y1 = box
    base = rng.choice(SKY_GLASS)
    if lit:
        base = (220, 190, 120)
    for y in range(int(y0), int(y1)):
        t = (y - y0) / max(1, y1 - y0)
        c = tuple(int(v * (1.15 - .35 * t)) for v in base)
        draw.line([(x0, y), (x1, y)], fill=c)
    if rng.random() < .55:  # curtain or tulle
        cc = rng.choice(CURTAINS)
        side = rng.choice((0, 1))
        cw = (x1 - x0) * rng.uniform(.25, .5)
        cx0 = x0 if side == 0 else x1 - cw
        draw.rectangle([cx0, y0, cx0 + cw, y1], fill=cc)
        for k in range(int(cx0), int(cx0 + cw), 4):
            draw.line([(k, y0), (k, y1)], fill=tuple(max(0, v - 25) for v in cc))
    if rng.random() < .4:
        draw.rectangle([x0, y0, x1, y0 + (y1 - y0) * .18], fill=(225, 225, 215))  # tulle top


def window(draw, box, frame=(236, 234, 226), style="soviet", sill=(150, 150, 150), lit=False):
    """Soviet three-leaf window with transom, or a plastic two-leaf one."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    fw = max(2, int(w * .06))
    draw.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], fill=(60, 60, 58))  # reveal shadow
    glass(draw, (x0, y0, x1, y1), lit)
    draw.rectangle([x0, y0, x1, y1], outline=frame, width=fw)
    if style == "soviet":
        draw.line([(x0 + w * .38, y0), (x0 + w * .38, y1)], fill=frame, width=fw)
        draw.line([(x0 + w * .69, y0 + h * .28), (x0 + w * .69, y1)], fill=frame, width=fw)
        draw.line([(x0, y0 + h * .28), (x1, y0 + h * .28)], fill=frame, width=fw)
    elif style == "plastic":
        draw.line([(x0 + w * .5, y0), (x0 + w * .5, y1)], fill=frame, width=fw + 1)
    elif style == "arched":
        draw.line([(x0 + w * .5, y0), (x0 + w * .5, y1)], fill=frame, width=fw)
        draw.line([(x0, y0 + h * .35), (x1, y0 + h * .35)], fill=frame, width=fw)
    draw.rectangle([x0 - 6, y1, x1 + 6, y1 + max(4, h * .05)], fill=sill)


def balcony(draw, box, rail=(70, 90, 70), slab=(170, 168, 160), glazed=False):
    x0, y0, x1, y1 = box
    draw.rectangle([x0, y1 - 8, x1, y1], fill=slab)
    if glazed:
        draw.rectangle([x0 + 2, y0, x1 - 2, y1 - 8], fill=(200, 196, 186))
        n = rng.randint(3, 5)
        for k in range(n):
            gx0 = x0 + 4 + k * (x1 - x0 - 8) / n
            window(draw, (gx0 + 3, y0 + 6, gx0 + (x1 - x0 - 8) / n - 3, y0 + (y1 - y0) * .55), frame=(rng.choice([(235, 235, 230), (150, 110, 70)])), style="plastic", sill=(170, 170, 170))
        draw.rectangle([x0 + 2, y0 + (y1 - y0) * .6, x1 - 2, y1 - 8], fill=rng.choice([(190, 186, 176), (150, 160, 170), (180, 140, 110)]))
    else:
        top = y0 + (y1 - y0) * .55
        draw.rectangle([x0, top, x1, top + 4], fill=rail)
        for x in range(int(x0), int(x1), 7):
            draw.line([(x, top), (x, y1 - 8)], fill=rail, width=2)
        if rng.random() < .5:  # laundry
            for k in range(rng.randint(2, 5)):
                lx = rng.uniform(x0 + 6, x1 - 20)
                draw.rectangle([lx, top - 26, lx + rng.uniform(10, 22), top - 2], fill=rng.choice(CURTAINS))


def dish(draw, cx, cy, r=14):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(205, 205, 200), outline=(150, 150, 150), width=2)
    draw.line([(cx, cy), (cx + r * 1.1, cy + r * .4)], fill=(80, 80, 80), width=2)


def ac_unit(draw, cx, cy):
    draw.rectangle([cx - 18, cy - 12, cx + 18, cy + 12], fill=(228, 228, 224), outline=(160, 160, 160))
    for k in range(-8, 9, 4):
        draw.line([(cx - 14, cy + k), (cx + 14, cy + k)], fill=(170, 170, 170))


def door(draw, box, color=(110, 80, 50), metal=False):
    x0, y0, x1, y1 = box
    draw.rectangle([x0 - 4, y0 - 4, x1 + 4, y1], fill=(50, 50, 48))
    draw.rectangle([x0, y0, x1, y1], fill=color)
    if metal:
        for k in range(3):
            yy = y0 + (y1 - y0) * (k + 1) / 4
            draw.line([(x0 + 4, yy), (x1 - 4, yy)], fill=tuple(max(0, v - 30) for v in color), width=2)
        draw.rectangle([x1 - 16, (y0 + y1) / 2 - 3, x1 - 8, (y0 + y1) / 2 + 3], fill=(40, 40, 40))
        draw.rectangle([x0 - 26, (y0 + y1) / 2 - 22, x0 - 12, (y0 + y1) / 2 + 2], fill=(30, 30, 34))  # intercom
    else:
        draw.line([((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], fill=(60, 45, 30), width=2)


# ---------------------------------------------------------------- builders

def ground_textures():
    def g(name, src, size=256, mean=None, sat=1.0, contrast=1.0, mix=None, colors=0):
        im = scan(src)
        if mix:
            other = scan(mix[0])
            im = Image.blend(im.convert("RGB"), other.convert("RGB"), mix[1])
        im = level(im, mean=mean, sat=sat, contrast=contrast)
        save(name, gta(tileable(im), (size, size), colors), kind="ground")
    g("grass", "sparse_grass", mean=105, sat=1.1, mix=("leafy_grass", .35))
    g("grass_dry", "withered_grass", mean=120, sat=.9)
    g("forest_floor", "forest_leaves_02", mean=88, sat=.75, mix=("forest_floor", .4))
    g("dirt", "dirt", mean=118, sat=.6, mix=("park_dirt", .4))
    g("mud", "brown_mud_leaves_01", mean=95, sat=.7)
    g("rock_granite", "lichen_rock", mean=125, mix=("rock_face", .45))
    g("sand", "sandy_gravel", mean=150, sat=.6)
    g("riverbed", "river_small_rocks", mean=100)
    g("farm", "farm_soil", mean=95, sat=.65)
    g("gravel", "gravel_road", mean=130, sat=.45)
    g("dirt_track", "muddy_tracks", mean=110, sat=.55, mix=("stony_dirt_path", .3))
    g("asphalt", "road_damaged", mean=96, sat=.2, mix=("worn_asphalt", .35))
    g("asphalt_clean", "asphalt_02", mean=90, sat=.2)
    g("sidewalk_hex", "hexagonal_concrete_paving", mean=150, sat=.6)
    g("sidewalk_tiles", "square_concrete_pavers", mean=150, sat=.6)
    g("concrete", "cracked_concrete", mean=150, sat=.5)
    g("concrete_dirty", "damaged_concrete_floor", mean=130, sat=.6)
    g("paving_market", "pavement_02", mean=140, sat=.7)
    # Korostyshiv's own roads: Zarichchia patched asphalt and the bus stop corner
    p = photo("zarichchia_street")
    save("road_zarichchia", gta(tileable(level(warp(p, [(330, 560), (870, 560), (1010, 960), (0, 960)], (512, 768)), mean=118), "y"), (256, 384)), kind="ground", source="zarichchia_street")
    p = photo("bus_stop_teteriv")
    save("asphalt_patched", gta(tileable(level(warp(p, [(250, 640), (1130, 640), (1280, 960), (0, 960)], (768, 512)), mean=112)), (384, 256)), kind="ground", source="bus_stop_teteriv")


def road_textures():
    """u across the carriageway (0..1), v along it (one tile = 16 m)."""
    base = level(scan("road_damaged"), mean=92, sat=.18)
    worn = level(scan("worn_asphalt"), mean=100, sat=.2)
    for name, lanes, edge, dashes, w in (("road_2lane", 2, True, True, 256), ("road_main", 2, True, True, 256), ("road_town", 1, False, False, 256)):
        im = Image.new("RGB", (w, 512))
        for y in (0, 256):
            im.paste(Image.blend(base.resize((256, 256)), worn.resize((256, 256)), rng.uniform(.2, .5)).resize((w, 256)), (0, y))
        im = tileable(im, "y")
        d = ImageDraw.Draw(im, "RGBA")
        paint = (226, 222, 205, 205)
        if dashes:
            for y in range(0, 512, 128):
                d.rectangle([w / 2 - 3, y + 20, w / 2 + 3, y + 84], fill=paint)
        if edge:
            d.rectangle([10, 0, 15, 512], fill=(226, 222, 205, 170))
            d.rectangle([w - 16, 0, w - 11, 512], fill=(226, 222, 205, 170))
        if name == "road_main":  # solid centre line near the centre
            d.rectangle([w / 2 - 3, 0, w / 2 + 3, 512], fill=paint)
        # crumbled edges, patches, cracks
        for _ in range(9):
            x = rng.choice((rng.uniform(0, 18), rng.uniform(w - 18, w), rng.uniform(20, w - 20)))
            y = rng.uniform(0, 512)
            d.ellipse([x - rng.uniform(6, 30), y - rng.uniform(10, 40), x + rng.uniform(6, 30), y + rng.uniform(10, 40)], fill=(40, 40, 42, 120))
        for _ in range(14):
            x, y = rng.uniform(0, w), rng.uniform(0, 512)
            pts = [(x, y)]
            for k in range(6):
                x += rng.uniform(-14, 14)
                y += rng.uniform(4, 18)
                pts.append((x, y))
            d.line(pts, fill=(30, 30, 30, 140), width=1)
        save(name, gta(im, (w // 2 * 2 // 2, 256)), kind="road")
    # unpaved: dirt with ruts and grass in the middle
    dirt = level(scan("muddy_tracks"), mean=115, sat=.5)
    gr = level(scan("sparse_grass"), mean=100)
    im = Image.new("RGB", (256, 512))
    for y in (0, 256):
        im.paste(dirt.resize((256, 256)), (0, y))
    im = tileable(im, "y")
    mask = Image.new("L", (256, 512), 0)
    md = ImageDraw.Draw(mask)
    for x0, x1 in ((0, 26), (112, 144), (230, 256)):
        md.rectangle([x0, 0, x1, 512], fill=200)
    mask = mask.filter(ImageFilter.GaussianBlur(9))
    im = Image.composite(gr.resize((256, 512)), im, mask)
    save("road_dirt", gta(im, (128, 256)), kind="road")
    grv = level(scan("gravel_road"), mean=135, sat=.4)
    im = Image.new("RGB", (256, 512))
    for y in (0, 256):
        im.paste(grv.resize((256, 256)), (0, y))
    im = Image.composite(gr.resize((256, 512)), tileable(im, "y"), mask.point(lambda v: v // 2))
    save("road_gravel", gta(im, (128, 256)), kind="road")
    # kerb stone: granite blocks
    k = level(scan("granite_wall") if (SCANS / "granite_wall.jpg").exists() else scan("concrete_pavement"), mean=150, sat=.4)
    save("kerb", gta(tileable(k), (128, 128)), kind="road")


def wall_scans():
    def w(name, src, mean=170, tint=True, sat=1.0):
        im = scan(src)
        im = neutral(im, mean) if tint else level(im, mean=mean, sat=sat)
        save(name, gta(tileable(dirt_overlay(im, .25, False)), (256, 256)), kind="wall", tint=tint, bays=1, metres=[3.0, 3.0])
    w("plaster", "white_rough_plaster", 200)
    w("plaster_worn", "worn_cracked_plaster", 185)
    w("silicate_brick", "white_bricks", 190)
    w("red_brick", "red_brick", 125, tint=False)
    w("yellow_brick", "yellow_bricks", 160, tint=False)
    w("concrete_panel", "concrete_slab_wall", 175)
    w("concrete_block", "concrete_block_wall", 170)
    w("factory_wall", "factory_wall", 140, tint=False)
    w("profnastil", "box_profile_metal_sheet", 185)
    w("corrugated_rust", "rusty_corrugated_iron", 120, tint=False)
    w("planks", "weathered_planks", 120, tint=False)
    w("planks_painted", "wood_peeling_paint_weathered", 160, tint=False)
    w("rubble_granite", "granite_wall" if (SCANS / "granite_wall.jpg").exists() else "lichen_rock", 135, tint=False)


def facade(name, base_src, bays, draw_bay, mean=200, tint=True, size=(1024, 256), floors=1, grime=.3, base_img=None):
    W, H = size
    if base_img is None:
        b = scan(base_src)
        b = neutral(b, mean) if tint else level(b, mean=mean)
        tile = b.resize((H, H))
        base = Image.new("RGB", (W, H))
        for x in range(0, W, H):
            base.paste(tile, (x, 0))
    else:
        base = base_img
    d = ImageDraw.Draw(base)
    bw = W / bays
    for i in range(bays):
        for f in range(floors):
            draw_bay(d, i, i * bw, f * H / floors, bw, H / floors)
    base = dirt_overlay(base, grime)
    save(name, gta(base, (W // 2, H // 2) if W > 512 else (W, H)), kind="facade", tint=tint, bays=bays, floors=floors)


def facades():
    # khrushchovka: silicate brick, three-leaf windows, open balconies, dish, ac
    def khr_up(d, i, x, y, w, h):
        wx0, wx1 = x + w * .26, x + w * .74
        if i == 1:
            balcony(d, (x + w * .12, y + h * .18, x + w * .88, y + h * .98), glazed=False)
            door(d, (x + w * .62, y + h * .16, x + w * .8, y + h * .82), color=(200, 196, 186))
            window(d, (x + w * .2, y + h * .16, x + w * .56, y + h * .62))
        elif i == 3:
            balcony(d, (x + w * .1, y + h * .1, x + w * .9, y + h * .98), glazed=True)
        else:
            window(d, (wx0, y + h * .2, wx1, y + h * .74), frame=(236, 234, 226) if rng.random() < .6 else (240, 240, 240), style="soviet" if rng.random() < .55 else "plastic", lit=rng.random() < .1)
            if rng.random() < .35:
                ac_unit(d, x + w * .85, y + h * .4)
        if i == 2 and rng.random() < .8:
            dish(d, x + w * .12, y + h * .35)
        d.line([(x, y + 2), (x + w, y + 2)], fill=(150, 150, 146), width=3)  # floor slab joint
    facade("khrush_upper", "white_bricks", 4, khr_up, mean=200)

    def khr_ground(d, i, x, y, w, h):
        if i == 0:
            door(d, (x + w * .34, y + h * .3, x + w * .66, y + h), color=rng.choice([(80, 92, 104), (120, 60, 40), (60, 70, 60)]), metal=True)
            d.rectangle([x + w * .2, y + h * .2, x + w * .8, y + h * .27], fill=(160, 160, 150))  # canopy slab
            d.polygon([(x + w * .2, y + h * .27), (x + w * .8, y + h * .27), (x + w * .75, y + h * .31), (x + w * .25, y + h * .31)], fill=(90, 90, 86))
            fit_text(d, (x + w * .42, y + h * .08, x + w * .58, y + h * .18), str(rng.randint(1, 4)), (30, 40, 90))
        else:
            window(d, (x + w * .26, y + h * .2, x + w * .74, y + h * .72), style="soviet" if i != 2 else "plastic")
            if i == 3:  # bars on the ground floor
                for k in range(6):
                    xx = x + w * .26 + k * w * .48 / 5
                    d.line([(xx, y + h * .2), (xx, y + h * .72)], fill=(40, 40, 40), width=3)
        d.rectangle([x, y + h * .9, x + w, y + h], fill=(120, 116, 108))  # plinth
    facade("khrush_ground", "white_bricks", 4, khr_ground, mean=195)

    def panel_up(d, i, x, y, w, h):
        d.line([(x, y), (x, y + h)], fill=(140, 140, 136), width=3)
        d.line([(x, y + 1), (x + w, y + 1)], fill=(140, 140, 136), width=3)
        if i in (1, 2) and i == 1:
            balcony(d, (x + w * .06, y + h * .12, x + w * .94, y + h * .98), glazed=rng.random() < .5, rail=(150, 150, 150))
        else:
            window(d, (x + w * .22, y + h * .22, x + w * .78, y + h * .74), style="soviet" if rng.random() < .5 else "plastic")
    facade("panel9_upper", "concrete_slab_wall", 4, panel_up, mean=205)
    facade("panel9_ground", "concrete_slab_wall", 4, khr_ground, mean=200)

    def brick_up(d, i, x, y, w, h):
        window(d, (x + w * .27, y + h * .22, x + w * .73, y + h * .74), style="soviet" if rng.random() < .7 else "plastic", frame=(230, 226, 214))
        d.rectangle([x + w * .24, y + h * .16, x + w * .76, y + h * .22], fill=(186, 182, 172))  # concrete lintel
        if i == 2 and rng.random() < .6:
            balcony(d, (x + w * .1, y + h * .15, x + w * .9, y + h * .98), glazed=True)
    facade("brick_upper", "red_brick", 4, brick_up, mean=130, tint=False)
    facade("yellow_brick_upper", "yellow_bricks", 4, brick_up, mean=165, tint=False)

    def public_up(d, i, x, y, w, h):
        d.rectangle([x, y, x + w * .1, y + h], fill=(236, 232, 222))  # pilaster
        window(d, (x + w * .3, y + h * .14, x + w * .7, y + h * .8), style="arched", frame=(240, 240, 236))
        d.rectangle([x + w * .25, y + h * .08, x + w * .75, y + h * .14], fill=(236, 232, 222))
    facade("public_upper", "white_rough_plaster", 4, public_up, mean=190)

    def public_ground(d, i, x, y, w, h):
        d.rectangle([x, y, x + w * .1, y + h], fill=(236, 232, 222))
        if i == 1:
            door(d, (x + w * .3, y + h * .2, x + w * .7, y + h), color=(120, 84, 50))
            d.rectangle([x + w * .2, y + h * .12, x + w * .8, y + h * .2], fill=(220, 216, 206))
        else:
            window(d, (x + w * .3, y + h * .2, x + w * .7, y + h * .78), style="soviet")
        d.rectangle([x, y + h * .9, x + w, y + h], fill=(100, 98, 92))
    facade("public_ground", "white_rough_plaster", 4, public_ground, mean=190)

    def plain_up(d, i, x, y, w, h):
        window(d, (x + w * .28, y + h * .22, x + w * .72, y + h * .74), style="plastic" if rng.random() < .5 else "soviet")
    facade("plaster_upper", "worn_cracked_plaster", 4, plain_up, mean=190)

    # shops: procedural signs over shop windows, Ukrainian small-town names
    signs = [("ПРОДУКТИ", (200, 40, 40), (255, 255, 255)), ("АПТЕКА", (30, 140, 70), (255, 255, 255)), ("ПИВО  ВОДИ", (240, 190, 30), (40, 30, 20)),
             ("ГОСПТОВАРИ", (40, 70, 150), (255, 255, 255)), ("ОДЯГ  СЕКОНД", (120, 40, 120), (255, 240, 120)), ("М'ЯСО", (180, 30, 30), (255, 230, 200)),
             ("ЗАПЧАСТИНИ", (30, 30, 30), (250, 200, 20)), ("КАВА", (90, 50, 30), (250, 230, 200)), ("ЛОМБАРД", (250, 200, 0), (20, 20, 20)),
             ("БУДМАТЕРІАЛИ", (220, 110, 20), (255, 255, 255)), ("ЗООТОВАРИ", (40, 120, 160), (255, 255, 255)), ("ХЛІБ", (190, 140, 60), (60, 30, 10))]
    for v in range(3):
        picks = rng.sample(signs, 2)

        def shop(d, i, x, y, w, h, picks=picks):
            s = picks[0] if i < 2 else picks[1]
            if i in (0, 2):
                d.rectangle([x + 4, y + h * .06, x + w * 2 - 4, y + h * .28], fill=s[1])
                fit_text(d, (x + 10, y + h * .07, x + w * 2 - 10, y + h * .27), s[0], s[2])
            if i % 2 == 0:
                d.rectangle([x + w * .1, y + h * .34, x + w * .95, y + h * .9], fill=(40, 46, 50))
                glass(d, (x + w * .13, y + h * .37, x + w * .92, y + h * .87))
                for k in range(rng.randint(2, 5)):  # posters behind the glass
                    px = rng.uniform(x + w * .15, x + w * .8)
                    d.rectangle([px, y + h * .45, px + w * .12, y + h * .62], fill=rng.choice(CURTAINS))
            else:
                door(d, (x + w * .2, y + h * .34, x + w * .6, y + h * .98), color=rng.choice([(200, 200, 196), (90, 100, 110)]), metal=True)
                window(d, (x + w * .66, y + h * .4, x + w * .92, y + h * .8), style="plastic")
            d.rectangle([x, y + h * .93, x + w, y + h], fill=(110, 106, 100))
        facade(f"shopfront_{v}", "worn_cracked_plaster", 4, shop, mean=195, tint=True)

    # industrial: ribbon windows, brick base
    def ind(d, i, x, y, w, h):
        d.rectangle([x + w * .08, y + h * .18, x + w * .92, y + h * .42], fill=(60, 70, 72))
        for k in range(6):
            xx = x + w * .08 + k * w * .84 / 5
            d.line([(xx, y + h * .18), (xx, y + h * .42)], fill=(110, 110, 104), width=3)
        d.line([(x + w * .08, y + h * .3), (x + w * .92, y + h * .3)], fill=(110, 110, 104), width=3)
        if i == 2:
            d.rectangle([x + w * .15, y + h * .5, x + w * .85, y + h], fill=(70, 90, 80))
            for k in range(8):
                d.line([(x + w * .15, y + h * (.5 + k * .062)), (x + w * .85, y + h * (.5 + k * .062))], fill=(50, 66, 58), width=3)
    facade("industrial", "factory_wall", 4, ind, mean=140, tint=False, size=(1024, 512))

    # church side wall: white, tall arched windows
    def church(d, i, x, y, w, h):
        d.rectangle([x, y, x + w * .12, y + h], fill=(250, 250, 248))
        window(d, (x + w * .32, y + h * .25, x + w * .68, y + h * .75), style="arched", frame=(250, 250, 250))
        d.pieslice([x + w * .32, y + h * .15, x + w * .68, y + h * .35], 180, 360, fill=(70, 86, 96))
    facade("church_side", "white_rough_plaster", 4, church, mean=225, tint=False, size=(1024, 512))

    # garage box door: real rusted shutters, painted
    for k, src in enumerate(("rusty_metal_shutter", "painted_metal_shutter", "rusted_shutter")):
        im = level(scan(src), mean=120 + k * 10)
        im = im.resize((256, 256))
        frame = Image.new("RGB", (256, 256), (150, 146, 138))
        frame.paste(im.resize((216, 220)), (20, 36))
        d = ImageDraw.Draw(frame)
        fit_text(d, (60, 4, 200, 34), str(rng.randint(1, 180)), (240, 240, 240))
        save(f"garage_door_{k}", gta(dirt_overlay(frame, .3), (128, 128)), kind="facade", bays=1, floors=1, tint=False)


def photo_textures():
    """Rectified crops of real Korostyshiv buildings and yards."""
    P = {
        "house_wall_a": ("house_kmytiv_a", [(452, 448), (896, 446), (896, 655), (452, 665)], (512, 256), dict(kind="facade", bays=2, floors=1)),
        "house_wall_b": ("house_kmytiv_d", [(215, 413), (868, 418), (868, 646), (215, 646)], (768, 256), dict(kind="facade", bays=3, floors=1)),
        "house_wall_c": ("house_kmytiv_e", [(400, 462), (700, 470), (700, 600), (400, 598)], (512, 256), dict(kind="facade", bays=2, floors=1)),
        "house_end_ruin": ("house_kmytiv_a", [(222, 455), (410, 455), (410, 645), (222, 640)], (256, 256), dict(kind="facade", bays=1, floors=1)),
        "roof_shifer": ("house_kmytiv_a", [(300, 207), (875, 247), (1085, 445), (415, 440)], (512, 256), dict(kind="roof", tile="xy")),
        "roof_shifer_b": ("house_kmytiv_e", [(425, 262), (930, 190), (705, 468), (355, 470)], (512, 256), dict(kind="roof", tile="xy")),
        "roof_shifer_c": ("railway_station_building", [(270, 115), (955, 225), (955, 318), (420, 285)], (512, 256), dict(kind="roof", tile="xy")),
        "gable_blue": ("house_kmytiv_c", [(290, 330), (520, 330), (540, 440), (270, 445)], (256, 128), dict(kind="gable")),
        "gable_wood": ("house_kmytiv_b", [(720, 300), (1000, 300), (1000, 395), (720, 395)], (256, 128), dict(kind="gable")),
        "gable_red": ("house_kmytiv_d", [(520, 232), (830, 232), (860, 390), (510, 390)], (256, 128), dict(kind="gable")),
        "gable_green": ("house_kmytiv_e", [(740, 292), (1000, 292), (1040, 450), (720, 455)], (256, 128), dict(kind="gable")),
        "fence_picket": ("house_kmytiv_b", [(110, 548), (880, 513), (880, 742), (110, 782)], (512, 160), dict(kind="fence", metres=[6.0, 1.5], tile="x")),
        "fence_picket_b": ("house_kmytiv_c", [(10, 560), (560, 545), (560, 770), (10, 845)], (512, 192), dict(kind="fence", metres=[5.0, 1.6], tile="x")),
        "fence_blue": ("house_kmytiv_c", [(1018, 432), (1280, 432), (1280, 600), (1018, 605)], (256, 192), dict(kind="fence", metres=[2.6, 1.9], tile="x")),
        "fence_planks_grey": ("zarichchia_street", [(1052, 452), (1280, 440), (1280, 600), (1052, 525)], (256, 160), dict(kind="fence", metres=[3.0, 1.8], tile="x")),
        "gate_blue": ("house_kmytiv_d", [(0, 585), (345, 580), (345, 920), (0, 905)], (256, 256), dict(kind="fence", metres=[3.0, 2.0])),
        "postal_station": ("kyivska30_postal_station", [(178, 468), (1046, 468), (1046, 690), (178, 690)], (1024, 256), dict(kind="facade", bays=6, floors=1, landmark=True)),
        "shops_row": ("kyivska_shops_bus_station", [(20, 325), (392, 343), (392, 492), (20, 487)], (512, 192), dict(kind="facade", bays=3, floors=1, landmark=True)),
        "bistro_kiosk": ("kyivska_shops_bus_station", [(430, 370), (726, 372), (726, 495), (430, 495)], (512, 192), dict(kind="facade", bays=3, floors=1, landmark=True)),
        "postal_station_side": ("kyivska_shops_bus_station", [(728, 352), (1080, 380), (1080, 500), (728, 500)], (512, 192), dict(kind="facade", bays=4, floors=1, landmark=True)),
        "khrush_photo": ("miners_square_gastronom", [(700, 92), (986, 92), (986, 392), (700, 392)], (256, 256), dict(kind="facade", bays=2, floors=4)),
        "sign_gastronom": ("miners_square_gastronom", [(802, 393), (1029, 393), (1029, 428), (802, 428)], (512, 80), dict(kind="sign")),
        "kiosk_yellow": ("miners_square_gastronom", [(175, 385), (400, 388), (400, 515), (175, 512)], (256, 160), dict(kind="facade", bays=1, floors=1)),
        "bus_stop_wall": ("bus_stop_teteriv", [(655, 252), (864, 300), (860, 505), (655, 526)], (256, 256), dict(kind="facade", bays=1, floors=1)),
        "sign_sanatorium": ("bus_stop_teteriv", [(865, 330), (975, 352), (972, 378), (865, 356)], (256, 64), dict(kind="sign")),
        "station_wall": ("railway_station_building", [(445, 305), (955, 322), (955, 560), (445, 600)], (512, 256), dict(kind="facade", bays=2, floors=1, landmark=True)),
        "sign_station": ("railway_station_sign", [(205, 350), (1125, 320), (1128, 595), (200, 610)], (512, 160), dict(kind="sign")),
        "quarry_cliff": ("granite_quarry_wall", [(290, 300), (1040, 300), (1040, 532), (290, 532)], (512, 160), dict(kind="rock", tile="x")),
        "rda_front": ("district_administration", [(132, 300), (1150, 300), (1150, 645), (132, 645)], (1024, 384), dict(kind="facade", bays=9, floors=2, landmark=True)),
        "college_wall": ("pedagogical_college", [(730, 345), (1100, 380), (1100, 745), (730, 768)], (512, 512), dict(kind="facade", bays=4, floors=2, landmark=True)),
        "ruin_wattle": ("abandoned_hut", [(440, 320), (840, 300), (840, 680), (440, 640)], (256, 256), dict(kind="facade", bays=1, floors=1)),
        "fachwerk": ("olizar_servants_house", [(120, 392), (400, 357), (400, 780), (120, 690)], (256, 256), dict(kind="facade", bays=1, floors=1, landmark=True)),
    }
    for name, (src, quad, size, info) in P.items():
        im = warp(photo(src), quad, (size[0] * 2, size[1] * 2))
        im = level(im, contrast=1.05, sat=1.05)
        if info.get("tile"):
            im = tileable(im, info["tile"])
        info["source"] = src
        save(name, gta(im, size), **info)
    # church front with sky keyed out above the cornice
    p = photo("church_nativity_front")
    im = warp(p, [(250, 80), (998, 80), (998, 806), (250, 806)], (1024, 1024)).convert("RGBA")
    sil = [(250, 806), (250, 440), (300, 440), (300, 208), (330, 200), (375, 172), (388, 132), (400, 172), (442, 205), (440, 400), (470, 222),
           (470, 192), (520, 160), (558, 145), (560, 95), (600, 82), (640, 82), (678, 95), (678, 145), (720, 160), (770, 192), (770, 222),
           (800, 400), (800, 205), (842, 172), (856, 128), (868, 172), (940, 205), (942, 440), (998, 440), (998, 806)]
    mask = Image.new("L", (1280, 853), 0)
    ImageDraw.Draw(mask).polygon(sil, fill=255)
    im.putalpha(warp(mask, [(250, 80), (998, 80), (998, 806), (250, 806)], (1024, 1024)))
    save("church_front", gta(im, (512, 512)), kind="facade", landmark=True, source="church_nativity_front", alpha=True)


def roofs_and_props():
    def r(name, src, mean, tint, size=256):
        im = scan(src)
        im = neutral(im, mean) if tint else level(im, mean=mean)
        save(name, gta(tileable(im), (size, size)), kind="roof", tint=tint)
    r("roof_flat", "tarred_gravel", 90, False)
    r("roof_bitumen", "bitumen", 70, False)
    r("roof_metal", "grey_roof_01", 175, True)
    r("roof_corrugated", "corrugated_iron_03", 180, True)
    # concrete panel fence (ПО-2): diamonds
    base = neutral(scan("precast_concrete_wall"), 175).resize((512, 256))
    d = ImageDraw.Draw(base)
    for cx in range(32, 512, 64):
        for cy in (64, 192):
            d.polygon([(cx, cy - 46), (cx + 30, cy), (cx, cy + 46), (cx - 30, cy)], outline=(120, 120, 116), width=4)
            d.polygon([(cx, cy - 40), (cx + 25, cy), (cx, cy + 40), (cx - 25, cy)], fill=(196, 194, 188))
    save("fence_concrete", gta(dirt_overlay(base, .35), (256, 128)), kind="fence", tint=True, metres=[4.0, 2.2], tile="x")
    pr = neutral(scan("box_profile_metal_sheet"), 190).rotate(90)
    save("fence_profnastil", gta(tileable(pr, "x"), (256, 128)), kind="fence", tint=True, metres=[3.0, 1.9], tile="x")
    br = level(scan("red_brick"), mean=120)
    save("fence_brick", gta(tileable(br), (256, 128)), kind="fence", metres=[3.0, 1.9], tile="x")
    # chain-link (рабиця) with posts
    m = scan("Fence003", 1024).resize((512, 512))
    out = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
    out.alpha_composite(m.crop((0, 0, 512, 256)))
    out.alpha_composite(m.crop((0, 0, 512, 256)), (0, 0))
    d = ImageDraw.Draw(out)
    d.rectangle([0, 0, 12, 256], fill=(90, 96, 92, 255))
    d.line([(0, 6), (512, 6)], fill=(90, 96, 92, 255), width=5)
    save("fence_mesh", gta(out, (256, 128)), kind="fence", alpha=True, metres=[3.0, 1.6], tile="x")
    # trees: leaf clusters on alpha cards from real leaf scans
    for name, srcs, scale, n in (("leaves_card", ["LeafSet004", "LeafSet024", "LeafSet010"], .14, 900), ("leaves_card_b", ["LeafSet017", "LeafSet024"], .12, 900)):
        card = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        sprites = []
        for s in srcs:
            sheet = scan(s, 1024)
            bbox = sheet.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
            # split the sheet into its leaves (2-3 rows x 2-3 cols)
            cols, rows = (3, 2) if s in ("LeafSet004",) else (3, 3) if s == "LeafSet024" else (2, 2) if s == "LeafSet010" else (2, 3)
            for i in range(cols):
                for j in range(rows):
                    c = sheet.crop((i * 1024 // cols, j * 1024 // rows, (i + 1) * 1024 // cols, (j + 1) * 1024 // rows))
                    if c.getchannel("A").getbbox():
                        sprites.append(c.crop(c.getchannel("A").getbbox()))
        for k in range(n):
            ang = rng.uniform(0, math.tau)
            rad = math.sqrt(rng.random()) * 230
            x, y = 256 + math.cos(ang) * rad, 256 + math.sin(ang) * rad * .9
            sp = rng.choice(sprites)
            sz = int(512 * scale * rng.uniform(.6, 1.1))
            sp = sp.resize((sz, int(sz * sp.height / sp.width))).rotate(rng.uniform(0, 360), expand=True)
            shade = .55 + .45 * (1 - rad / 240) * (.6 + .4 * (y < 256))
            sp = level(sp, bright=shade * rng.uniform(.85, 1.1))
            card.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height / 2)))
        save(name, gta(card, (256, 256)), kind="tree", alpha=True)
    pine = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    needles = scan("PineNeedles001", 1024)
    strands = [needles.crop((0, j * 128, 1024, (j + 1) * 128)) for j in range(8)]
    for k in range(1100):
        y = rng.uniform(20, 500)
        half = 30 + (y / 512) * 220  # triangle silhouette
        x = 256 + rng.uniform(-half, half)
        s = rng.choice(strands)
        if not s.getchannel("A").getbbox():
            continue
        s = s.crop(s.getchannel("A").getbbox())
        s = s.resize((int(90 + rng.uniform(0, 80)), 40)).rotate(rng.uniform(-35, 35) + (180 if x < 256 else 0), expand=True)
        s = level(s, bright=rng.uniform(.5, .95), sat=.8)
        g = Image.new("RGB", s.size, (70, 150, 60))
        rgb = ImageChops.multiply(ImageOps.grayscale(s.convert("RGB")).convert("RGB"), g)
        rgb.putalpha(s.getchannel("A"))
        s = rgb
        pine.alpha_composite(s, (int(x - s.width / 2), int(y - s.height / 2)))
    save("pine_card", gta(pine, (256, 256)), kind="tree", alpha=True)
    save("bark_pine", gta(tileable(level(scan("pine_bark"), mean=95)), (128, 256)), kind="tree")
    save("bark", gta(tileable(level(scan("bark_brown_01"), mean=90)), (128, 256)), kind="tree")
    # birch bark: white with black lenticels (every Ukrainian yard has one)
    bb = Image.new("RGB", (128, 256), (226, 224, 214))
    d = ImageDraw.Draw(bb)
    for _ in range(60):
        y = rng.uniform(0, 256)
        x = rng.uniform(0, 128)
        d.line([(x, y), (x + rng.uniform(8, 40), y + rng.uniform(-2, 2))], fill=(40, 38, 34), width=rng.randint(1, 4))
    save("bark_birch", gta(dirt_overlay(bb, .25, False), (64, 128)), kind="tree")


def contact_sheet(path):
    names = sorted(manifest)
    cols = 10
    tw = 150
    sheet = Image.new("RGB", (cols * tw, ((len(names) + cols - 1) // cols) * (tw + 18)), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT_COND, 11)
    for i, n in enumerate(names):
        im = Image.open(OUT / f"{n}.png").convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 0, 255, 255))
        bg.alpha_composite(im)
        t = bg.convert("RGB")
        t.thumbnail((tw - 4, tw - 4))
        x, y = (i % cols) * tw, (i // cols) * (tw + 18)
        sheet.paste(t, (x + 2, y + 2))
        d.text((x + 2, y + tw), n, fill=(255, 255, 0), font=f)
    sheet.save(path, quality=88)


def main():
    ground_textures()
    road_textures()
    wall_scans()
    facades()
    photo_textures()
    roofs_and_props()
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print("TEXTURES_OK", len(manifest))
    if "--sheet" in sys.argv:
        contact_sheet(sys.argv[sys.argv.index("--sheet") + 1])


if __name__ == "__main__":
    main()
