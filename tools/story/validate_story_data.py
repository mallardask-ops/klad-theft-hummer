#!/usr/bin/env python3
"""Validate story data produced from docs/story/missions/*.md.

    python3 -I tools/story/validate_story_data.py data/story/missions_act1.json
    python3 -I tools/story/validate_story_data.py data/story/ambient.json

Errors make the exit code 1. Lines whose text is not found verbatim in the
source markdown are reported as errors too: the data must quote the script,
not paraphrase it.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "docs" / "story" / "missions"
EXISTING_LOCATIONS = {"cafe", "plaza", "market", "garages", "sawmill", "quarry", "dorm", "start"}
STEP_TYPES = {"drive", "pickup", "talk", "combat", "escape", "chase", "timer", "stealth",
              "defend", "escort", "photo", "drone", "choice", "cutscene"}
CODE = re.compile(r"^(П|Е|С|Т|ТР|К|В|БВ|Б|ВП|ПП|БР|ПГ|Ф2|КЛ|ФІН|ЕП)(-\d+)?$")
ID = re.compile(r"^[a-z][a-z0-9_]*$")

errors: list[str] = []
warnings: list[str] = []


def norm(text: str) -> str:
    text = text.replace("’", "'").replace("ʼ", "'").replace("«", "\"").replace("»", "\"")
    text = re.sub(r"[*_]", "", text)
    return re.sub(r"\s+", " ", text).strip()


SOURCE_TEXT = norm("\n".join(p.read_text(encoding="utf-8") for p in sorted(SOURCES.glob("*.md"))))


def err(where: str, msg: str) -> None:
    errors.append(f"{where}: {msg}")


def check_quote(where: str, text: str) -> None:
    if not isinstance(text, str) or not text.strip():
        err(where, "порожній текст")
        return
    if norm(text) not in SOURCE_TEXT:
        err(where, f"текст не знайдено в джерелах дослівно: {text[:70]!r}")


def check_line(where: str, line: dict) -> None:
    if not isinstance(line, dict):
        err(where, "репліка має бути об'єктом")
        return
    if not line.get("speaker"):
        err(where, "немає speaker")
    check_quote(where, line.get("text", ""))
    if "direction" in line and line["direction"] is not None and not isinstance(line["direction"], str):
        err(where, "direction має бути рядком або null")


def check_missions(data: dict) -> None:
    locations = data.get("locations", {})
    if not isinstance(locations, dict):
        err("locations", "має бути об'єктом")
        locations = {}
    for key, loc in locations.items():
        if not ID.match(key):
            err(f"locations.{key}", "ключ має бути snake_case латиницею")
        for field in ("name", "district"):
            if not loc.get(field):
                err(f"locations.{key}", f"немає {field}")
    known = EXISTING_LOCATIONS | set(locations)
    missions = data.get("missions")
    if not isinstance(missions, list) or not missions:
        err("missions", "має бути непорожнім списком")
        return
    codes = {m.get("code") for m in missions}
    ids = set()
    for m in missions:
        w = f"missions[{m.get('code', '?')}]"
        for field in ("code", "id", "title", "giver", "start", "reward", "cutscenes", "steps"):
            if field not in m:
                err(w, f"немає {field}")
        if m.get("code") and not CODE.match(m["code"]):
            err(w, "code не схожий на код місії (Е-1, БВ-4, ФІН-2…)")
        if m.get("id"):
            if not ID.match(m["id"]):
                err(w, "id має бути snake_case латиницею")
            if m["id"] in ids:
                err(w, "id повторюється")
            ids.add(m["id"])
        if m.get("start") and m["start"] not in known and m["start"] != "auto":
            err(w, f"start {m['start']!r} немає в locations")
        if not isinstance(m.get("reward", 0), int) or m.get("reward", 0) < 0:
            err(w, "reward має бути цілим ≥ 0")
        for dep in m.get("unlock_after", []):
            if dep not in codes:
                warnings.append(f"{w}: unlock_after {dep} з іншого файлу або акту")
        for ci, scene in enumerate(m.get("cutscenes", [])):
            sw = f"{w}.cutscenes[{ci}]"
            if scene.get("when") not in {"intro", "mid", "outro"}:
                err(sw, "when має бути intro | mid | outro")
            if not scene.get("lines"):
                err(sw, "немає реплік")
            for li, line in enumerate(scene.get("lines", [])):
                check_line(f"{sw}.lines[{li}]", line)
        if not m.get("steps"):
            err(w, "немає steps")
        for si, step in enumerate(m.get("steps", [])):
            sw = f"{w}.steps[{si}]"
            if step.get("type") not in STEP_TYPES:
                err(sw, f"невідомий type {step.get('type')!r}")
            label = step.get("label", "")
            if not label:
                err(sw, "немає label")
            elif len(label) > 70:
                err(sw, f"label довший за 70 символів ({len(label)})")
            pos = step.get("position")
            if step.get("type") != "cutscene" and pos not in known:
                err(sw, f"position {pos!r} немає в locations")
        for li, line in enumerate(m.get("in_mission_lines", [])):
            check_line(f"{w}.in_mission_lines[{li}]", line)


def check_ambient(data: dict) -> None:
    for section in ("pedestrians", "police_chase", "brother_calls", "podroid_messages", "radio"):
        if section not in data:
            err("ambient", f"немає розділу {section}")
    for ped, situations in data.get("pedestrians", {}).items():
        for situation, lines in situations.items():
            for i, text in enumerate(lines):
                check_quote(f"pedestrians.{ped}.{situation}[{i}]", text)
    for i, text in enumerate(data.get("police_chase", [])):
        check_quote(f"police_chase[{i}]", text)
    for i, call in enumerate(data.get("brother_calls", [])):
        for li, line in enumerate(call.get("lines", [])):
            check_line(f"brother_calls[{i}].lines[{li}]", line)
    for i, msg in enumerate(data.get("podroid_messages", [])):
        check_quote(f"podroid_messages[{i}]", msg.get("text", ""))
    for station, body in data.get("radio", {}).items():
        for i, item in enumerate(body.get("dj_lines", [])):
            check_quote(f"radio.{station}.dj_lines[{i}]", item.get("text", ""))
            if item.get("from_mark") and not re.match(r"^М\d+$", item["from_mark"]):
                err(f"radio.{station}.dj_lines[{i}]", "from_mark має бути М0…М18")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ПОМИЛКА: не вдалося прочитати JSON: {exc}")
        return 1
    if "missions" in data:
        check_missions(data)
    else:
        check_ambient(data)
    for w in warnings:
        print("увага:", w)
    for e in errors:
        print("ПОМИЛКА:", e)
    print(f"{path.name}: помилок {len(errors)}, попереджень {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
