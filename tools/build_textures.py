from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import random

ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'textures'
ROOT.mkdir(parents=True, exist_ok=True)
RNG = random.Random(1974)
FONT = '/usr/share/fonts/TTF/DejaVuSansCondensed-Bold.ttf'


def noise(name, base, size=64, rough=12):
    image = Image.new('RGB', (size, size))
    px = image.load()
    for y in range(size):
        for x in range(size):
            n = RNG.randint(-rough, rough)
            px[x, y] = tuple(max(0, min(255, c + n)) for c in base)
    return image


for name, base, rough in [
    ('asphalt', (65, 66, 61), 13), ('concrete', (141, 135, 116), 15),
    ('roof', (70, 74, 67), 14), ('grass', (78, 90, 60), 20),
    ('stone', (128, 126, 105), 26), ('rust', (119, 79, 58), 21),
    ('wood', (124, 104, 63), 14), ('plaster', (154, 142, 112), 16),
]:
    img = noise(name, base, rough=rough)
    draw = ImageDraw.Draw(img)
    if name == 'concrete':
        for y in range(0, 64, 16):
            draw.line((0, y, 64, y), fill=(111, 109, 99))
        for x in range(0, 64, 16):
            draw.line((x, 0, x, 64), fill=(125, 121, 106))
    if name == 'asphalt':
        draw.line((0, 28, 8, 31, 13, 42, 26, 49), fill=(45, 47, 43), width=1)
    if name == 'stone':
        for _ in range(14):
            x, y = RNG.randrange(64), RNG.randrange(64)
            draw.line((x, y, x+RNG.randrange(-10, 10), y+RNG.randrange(4, 15)), fill=(73, 77, 68))
    if name == 'wood':
        for x in range(2, 64, 8):
            draw.line((x, 0, x, 64), fill=(76, 68, 45))
    img.save(ROOT / f'{name}.png')

brick = noise('brick', (127, 93, 70), rough=12)
d = ImageDraw.Draw(brick)
for y in range(0, 64, 8):
    d.line((0, y, 64, y), fill=(83, 79, 68))
    for x in range((-8 if y % 16 else 0), 64, 16):
        d.line((x, y, x, y+8), fill=(85, 80, 69))
brick.save(ROOT / 'brick.png')

for style, base in [('slab', (151, 145, 120)), ('redbrick', (136, 103, 78)), ('blue', (111, 126, 122))]:
    img = noise(style, base, rough=9)
    d = ImageDraw.Draw(img)
    if style == 'redbrick':
        for y in range(0, 64, 5):
            d.line((0, y, 64, y), fill=(93, 84, 69))
            for x in range((0 if y % 10 else -5), 64, 10):
                d.line((x, y, x, y+5), fill=(97, 88, 72))
    else:
        d.line((0, 0, 63, 0), fill=(100, 102, 91), width=2)
        d.line((0, 0, 0, 63), fill=(112, 111, 98), width=2)
    d.rectangle((16, 10, 47, 47), fill=(59, 65, 59))
    d.rectangle((18, 12, 45, 44), fill=(77, 90, 84))
    d.rectangle((19, 13, 31, 42), fill=(99, 108, 92))
    d.rectangle((34, 13, 44, 42), fill=(61, 72, 72))
    d.line((32, 11, 32, 45), fill=(194, 187, 159), width=2)
    d.line((18, 25, 46, 25), fill=(178, 171, 146), width=1)
    d.rectangle((13, 46, 50, 49), fill=(189, 181, 149))
    d.rectangle((16, 51, 48, 56), fill=(105, 106, 93))
    for _ in range(24):
        x, y = RNG.randrange(64), RNG.randrange(57, 64)
        d.line((x, y, x+RNG.randrange(1, 4), y), fill=(99, 105, 87))
    img.save(ROOT / f'facade_{style}.png')

water = noise('water', (63, 94, 99), rough=7)
d = ImageDraw.Draw(water)
for y in range(2, 64, 7):
    x = RNG.randrange(20)
    d.line((x, y, x+RNG.randrange(15, 35), y), fill=(94, 125, 124))
water.save(ROOT / 'water.png')

signs = {
    'cafe': ('КАФЕ ПОДРО', (173, 145, 82), (40, 43, 35)),
    'kodlo': ('КОДЛО', (156, 163, 136), (44, 54, 42)),
    'grocery': ('ПРОДУКТИ', (202, 196, 156), (53, 68, 51)),
    'beer': ('ПИВО • КВАС', (194, 168, 95), (75, 53, 31)),
    'market': ('КОЛГОСПНИЙ РИНОК', (200, 190, 144), (85, 57, 41)),
    'sawmill': ('ЛІСОПИЛКА № 3', (200, 191, 151), (65, 78, 52)),
    'granite': ('КОРОСТИШІВ ГРАНІТ', (190, 181, 151), (59, 67, 60)),
    'garage': ('СТО ДІДА', (191, 177, 126), (71, 69, 47)),
    'safehouse': ('ГУРТОЖИТОК', (185, 173, 138), (58, 68, 63)),
    'phone': ('ТЕЛЕФОН', (202, 176, 131), (76, 73, 47)),
    'town': ('КОРОСТИШІВ', (196, 194, 166), (68, 86, 78)),
    'stop': ('АВТОБУСНА', (198, 184, 146), (61, 82, 73)),
    'pizzeria': ('ПІЦА У МІКІ', (205, 183, 135), (109, 54, 39)),
    'hammer': ('МОЛОТОК • ЛОМ • КИРКА', (193, 177, 125), (80, 56, 38)),
    'repair': ('РЕМОНТ ВЗУТТЯ', (183, 166, 131), (63, 65, 54)),
    'district': ('ВУЛ. ГЕРОЇВ КОДЛА', (185, 188, 170), (48, 80, 81)),
    'billboard': ('ГРАНІТ НА ВІКИ\nЗАПЛАТИ ЗА СВОЇ', (180, 169, 129), (80, 78, 51)),
    'wanted': ('ПОДРО\nВЖЕ В МІСТІ', (197, 181, 133), (88, 44, 37)),
    'yard': ('НЕ СТАВ МАШИНУ\nПІД БАЛКОНОМ', (188, 185, 155), (75, 78, 63)),
    'quarry': ('ОБЕРЕЖНО!\nКАР’ЄР', (191, 171, 79), (53, 47, 31)),
}
for name, (content, base, ink) in signs.items():
    img = noise(name, base, size=256, rough=8).resize((256, 64), Image.Resampling.NEAREST)
    d = ImageDraw.Draw(img)
    d.rectangle((1, 1, 254, 62), outline=ink, width=2)
    lines = content.split('\n')
    font_size = 30 if len(lines) == 1 else 22
    while True:
        f = ImageFont.truetype(FONT, font_size)
        if max(d.textbbox((0, 0), s, font=f)[2] for s in lines) < 236:
            break
        font_size -= 1
    line_h = font_size+2
    top = (64 - len(lines)*line_h)//2-2
    for i, line in enumerate(lines):
        box = d.textbbox((0, 0), line, font=f)
        width = box[2]-box[0]
        d.text(((256-width)//2, top+i*line_h), line, font=f, fill=ink)
    for _ in range(7):
        x, y = RNG.randrange(256), RNG.randrange(64)
        d.line((x, y, x+RNG.randrange(3, 10), y), fill=tuple(max(0,c-25) for c in base))
    img.save(ROOT / f'sign_{name}.png')
print(f'Built {len(list(ROOT.glob("*.png")))} native 64px surfaces and painted signs in {ROOT}')
