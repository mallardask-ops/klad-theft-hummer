"""GTA III style front-end art: tilted postcards of real Korostyshiv plus Podro.

Inputs  assets/source/city/photos/*.jpg (Wikimedia Commons, see credits.json)
        assets/source/ui/podro_pose_idle.png (tools/ui/render_podro_pose.py)
Outputs assets/ui/menu_main.png, assets/ui/menu_page.png, assets/ui/menu_credits.txt
Run: python3 -I tools/ui/build_menu_art.py
"""
import json
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[2]
PHOTOS = ROOT / "assets/source/city/photos"
OUT = ROOT / "assets/ui"
W, H = 1280, 720
rng = random.Random(3)


def grade(im, shadows=(18, 30, 52), highlights=(255, 214, 150), sat=.55, contrast=1.25):
    """The washed, warm-over-blue look of the GTA III front end artwork."""
    im = ImageEnhance.Color(im.convert("RGB")).enhance(sat)
    im = ImageEnhance.Contrast(im).enhance(contrast)
    g = ImageOps.grayscale(im)
    duo = ImageOps.colorize(g, shadows, highlights)
    return Image.blend(im, duo, .55)


def postcard(name, size, angle):
    im = Image.open(PHOTOS / f"{name}.jpg").convert("RGB")
    im = ImageOps.fit(im, size, Image.LANCZOS)
    im = grade(im)
    card = Image.new("RGBA", (size[0] + 24, size[1] + 24), (236, 230, 214, 255))
    card.paste(im, (12, 12))
    shadow = Image.new("RGBA", card.size, (0, 0, 0, 170))
    return card.rotate(angle, Image.BICUBIC, expand=True), shadow.rotate(angle, Image.BICUBIC, expand=True)


def paste_card(base, name, size, at, angle):
    card, shadow = postcard(name, size, angle)
    blurred = shadow.filter(ImageFilter.GaussianBlur(10))
    base.alpha_composite(blurred, (at[0] + 14, at[1] + 18))
    base.alpha_composite(card, at)


def podro(base, height, at):
    p = Image.open(ROOT / "assets/source/ui/podro_pose_idle.png").convert("RGBA")
    p = p.crop(p.getchannel("A").getbbox())
    p = p.resize((int(p.width * height / p.height), height), Image.LANCZOS)
    rgb = grade(p, (10, 14, 24), (255, 226, 190), sat=.8, contrast=1.15)
    rgb.putalpha(p.getchannel("A"))
    outline = p.getchannel("A").filter(ImageFilter.MaxFilter(9))
    edge = Image.new("RGBA", p.size, (0, 0, 0, 255))
    edge.putalpha(outline)
    base.alpha_composite(edge.filter(ImageFilter.GaussianBlur(2)), at)
    base.alpha_composite(rgb, at)


def vignette(base, left_dark=.0):
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    for i in range(60):
        d.rectangle([i * 6, i * 4, W - i * 6, H - i * 4], outline=int(255 * (1 - i / 60) ** 2))
    m = m.filter(ImageFilter.GaussianBlur(30))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dark.putalpha(m.point(lambda v: int(v * .8)))
    base.alpha_composite(dark)
    if left_dark:
        g = Image.linear_gradient("L").rotate(90).resize((W, H))
        g = g.point(lambda v: int(min(255, max(0, (v - 70) * 1.5)) * left_dark))
        shade = Image.new("RGBA", (W, H), (6, 8, 12, 0))
        shade.putalpha(g)
        base.alpha_composite(shade)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    base = Image.new("RGBA", (W, H), (20, 26, 36, 255))
    sky = grade(ImageOps.fit(Image.open(PHOTOS / "granite_quarry_wall.jpg"), (W, H), Image.LANCZOS), sat=.4)
    base.alpha_composite(ImageEnhance.Brightness(sky).enhance(.45).convert("RGBA"))
    paste_card(base, "church_nativity_front", (420, 300), (720, 22), -6)
    paste_card(base, "kyivska_shops_bus_station", (440, 300), (430, 300), 5)
    paste_card(base, "miners_square_gastronom", (330, 230), (900, 420), -3)
    paste_card(base, "house_kmytiv_d", (300, 220), (520, 40), 8)
    podro(base, 690, (930, 40))
    vignette(base, left_dark=.95)
    base.convert("RGB").save(OUT / "menu_main.png")
    page = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    q = grade(ImageOps.fit(Image.open(PHOTOS / "zarichchia_street.jpg"), (W, H), Image.LANCZOS), (8, 16, 34), (150, 170, 190), sat=.3)
    page.alpha_composite(ImageEnhance.Brightness(q).enhance(.55).convert("RGBA"))
    paste_card(page, "railway_station_sign", (360, 250), (860, 380), -7)
    vignette(page, left_dark=.6)
    page.convert("RGB").save(OUT / "menu_page.png")
    credits = json.loads((PHOTOS / "credits.json").read_text())
    used = {"church_nativity_front", "kyivska_shops_bus_station", "miners_square_gastronom", "house_kmytiv_d", "granite_quarry_wall", "zarichchia_street", "railway_station_sign"}
    lines = [f"{c['title'][5:]} — {c['author']} — {c['license']} — {c['url']}" for c in credits if c["file"][:-4] in used]
    (OUT / "menu_credits.txt").write_text("Front-end photos (modified: graded, cropped, rotated):\n" + "\n".join(lines) + "\n")
    print("MENU_ART_OK")


main()
