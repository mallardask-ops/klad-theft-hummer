"""Pack generated artwork into the exact delivery grid with ImageMagick."""

import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

BRIEF = Path(__file__).resolve().parent
ROOT = BRIEF.parent.parent
NATIVE = BRIEF / "generated_native"
OUTPUT = ROOT / "assets/ui/icons"


def bands(values, gap):
    result = []
    start = last = None
    for index, value in enumerate(values):
        if value < 2:
            continue
        if start is None:
            start = index
        elif index - last > gap:
            result.append((start, last + 1))
            start = index
        last = index
    if start is not None:
        result.append((start, last + 1))
    return result


def projection_boxes(source, expected_rows):
    with Image.open(source) as image:
        mask = image.getchannel("A").point(lambda value: 255 if value > 16 else 0)
        rows = bands(
            mask.resize((1, image.height), Image.Resampling.BOX).get_flattened_data(),
            12,
        )
        if len(rows) != len(expected_rows):
            raise ValueError(f"{source.name}: found {len(rows)} rows, expected {len(expected_rows)}")
        result = []
        for (top, bottom), expected_count in zip(rows, expected_rows):
            projection = tuple(
                mask.crop((0, top, image.width, bottom))
                .resize((image.width, 1), Image.Resampling.BOX)
                .get_flattened_data()
            )
            columns = None
            for gap in (12, 6, 2, 20):
                candidate = bands(projection, gap)
                if len(candidate) == expected_count:
                    columns = candidate
                    break
            if columns is None:
                raise ValueError(f"{source.name}: cannot separate {expected_count} icons")
            for left, right in columns:
                local = mask.crop((left, top, right, bottom)).getbbox()
                inner_left, inner_top, inner_right, inner_bottom = local
                result.append([
                    max(0, left + inner_left - 2),
                    max(0, top + inner_top - 2),
                    min(image.width, left + inner_right + 2),
                    min(image.height, top + inner_bottom + 2),
                ])
        return result


def run(*args):
    subprocess.run(["magick", *map(str, args)], check=True)


def main():
    specs = json.loads((BRIEF / "PROMPTS.json").read_text())["prompts"]
    manifest = {"sheet_size": [1024, 1024], "order": "left to right, top to bottom", "icons": []}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="klad-icon-export-") as directory:
        temporary = Path(directory)
        for spec in specs:
            source = NATIVE / spec["file"]
            columns, rows = spec["grid"]
            count = len(spec["ids"])
            expected_rows = [min(columns, count - row * columns) for row in range((count + columns - 1) // columns)]
            boxes = projection_boxes(source, expected_rows)
            cell = 1024 // columns
            limit = round(cell * (0.84 if columns == 1 else 0.80))
            blank = temporary / f"blank-{cell}.png"
            if not blank.exists():
                run("-size", f"{cell}x{cell}", "xc:none", f"PNG32:{blank}")
            tiles = []
            for index, identifier in enumerate(spec["ids"]):
                left, top, right, bottom = boxes[index]
                tile = temporary / f"{spec['prefix']}-{identifier}.png"
                run(
                    source, "-crop", f"{right-left}x{bottom-top}+{left}+{top}",
                    "+repage", "-resize", f"{limit}x{limit}", "-gravity", "center",
                    "-background", "none", "-extent", f"{cell}x{cell}", f"PNG32:{tile}",
                )
                tiles.append(tile)
                manifest["icons"].append({
                    "filename": "app_icon.png" if columns == 1 else f"{spec['prefix']}_{identifier}.png",
                    "sheet": spec["file"],
                    "cell": index + 1,
                    "rect": [(index % columns) * cell, (index // columns) * cell, cell, cell],
                    "target_size": spec["target_size"],
                    "native_source": str(source.relative_to(ROOT)),
                    "native_crop": [left, top, right-left, bottom-top],
                })
            tiles.extend([blank] * (columns * rows - count))
            run("montage", *tiles, "-background", "none", "-tile", f"{columns}x{rows}", "-geometry", "+0+0", f"PNG32:{OUTPUT / spec['file']}")
            print(f"{spec['file']}: {count} icons, {cell}px cells")
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Exported {len(manifest['icons'])} icons in {len(specs)} PNG files")


if __name__ == "__main__":
    main()
