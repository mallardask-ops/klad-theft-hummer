"""Install verified recordings; missing assets fail instead of becoming beeps."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/audio"
RECORDED = OUT / "recorded/processed"


def main():
    manifest = json.loads((OUT / "recorded/manifest.json").read_text())
    outputs = [spec for source in manifest["sources"] for spec in source["outputs"]]
    names = set()
    for spec in outputs:
        name = spec["name"] + "." + spec.get("format", "wav")
        if name in names:
            raise ValueError(f"Duplicate runtime sound: {name}")
        names.add(name)
        recording = RECORDED / name
        if not recording.is_file():
            raise FileNotFoundError(f"{recording}: run tools/import_recorded_audio.py first")
        expected = spec["verification"]["sha256"]
        if hashlib.sha256(recording.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Recording changed since import: {name}")
        shutil.copyfile(recording, OUT / name)
    obsolete_radio = OUT / "radio.wav"
    if "radio.ogg" in names and obsolete_radio.exists():
        obsolete_radio.unlink()
    if "radio.ogg" in names:
        obsolete_radio.with_suffix(".wav.import").unlink(missing_ok=True)
    print(f"INSTALLED_AUDIO assets={len(outputs)} procedural=0")


if __name__ == "__main__":
    main()
