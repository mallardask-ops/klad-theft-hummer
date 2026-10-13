"""Trim licensed recordings into game WAVs; provenance lives beside the originals."""
from array import array
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
RECORDINGS = ROOT / "assets/audio/recorded"
OUT = ROOT / "assets/audio"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert(spec, original):
    rate = spec.get("rate", 22050)
    channels = spec.get("channels", 1)
    command = ["ffmpeg", "-v", "error", "-ss", str(spec["start"]), "-i", str(original),
               "-t", str(spec["duration"]), "-ac", str(channels), "-ar", str(rate)]
    if spec.get("filters"):
        command += ["-af", spec["filters"]]
    command += ["-f", "f32le", "-"]
    floats = array("f", subprocess.check_output(command))
    if sys.byteorder != "little":
        floats.byteswap()
    if not floats:
        raise ValueError(f"No audio decoded for {spec['name']}")
    for channel in range(channels):
        mean = sum(floats[channel::channels]) / (len(floats) // channels)
        for i in range(channel, len(floats), channels):
            floats[i] -= mean
    if spec.get("trim_lead"):
        threshold = max(abs(value) for value in floats) * 0.03
        onset = next(i // channels for i, value in enumerate(floats) if abs(value) > threshold)
        start = max(0, onset - int(rate * 0.004)) * channels
        floats = floats[start:]
    crossfade = int(spec.get("crossfade", 0) * rate)
    if crossfade:
        overlap = crossfade * channels
        tail = array("f")
        for frame in range(crossfade):
            t = frame / max(1, crossfade - 1)
            for channel in range(channels):
                i = frame * channels + channel
                tail.append(floats[-overlap + i] * (1 - t) + floats[i] * t)
        floats = floats[overlap:-overlap] + tail
    else:
        frames = len(floats) // channels
        fade_in = min(int(spec.get("fade_in", 0.005) * rate), frames // 3)
        fade_out = min(int(spec.get("fade_out", 0.03) * rate), frames // 3)
        for frame in range(fade_in):
            for channel in range(channels):
                floats[frame * channels + channel] *= frame / max(1, fade_in - 1)
        for frame in range(fade_out):
            for channel in range(channels):
                floats[-(fade_out - frame) * channels + channel] *= 1 - frame / max(1, fade_out - 1)
    peak = max(abs(value) for value in floats)
    if peak < 0.00001:
        raise ValueError(f"Silent audio for {spec['name']}")
    gain = spec.get("peak", 0.72) / peak
    pcm = array("h", (round(max(-0.95, min(0.95, value * gain)) * 32767) for value in floats))
    if sys.byteorder != "little":
        pcm.byteswap()
    target = RECORDINGS / "processed" / (spec["name"] + "." + spec.get("format", "wav"))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix == ".ogg":
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(rate),
                        "-ac", str(channels), "-i", "-", "-c:a", "libvorbis", "-q:a", "6",
                        str(target)], input=pcm.tobytes(), check=True)
    else:
        with wave.open(str(target), "wb") as wav:
            wav.setparams((channels, 2, rate, len(pcm) // channels, "NONE", "not compressed"))
            wav.writeframes(pcm.tobytes())
    shutil.copyfile(target, OUT / target.name)
    return {"path": str(target.relative_to(ROOT)), "sha256": digest(target),
            "duration": round(len(pcm) / channels / rate, 6), "rate": rate,
            "channels": channels, "peak": round(max(abs(v) for v in pcm) / 32767, 6)}


def main():
    manifest_path = RECORDINGS / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    count = 0
    for source in manifest["sources"]:
        original = RECORDINGS / "originals" / source["file"]
        if not original.is_file():
            raise FileNotFoundError(original)
        source["sha256"] = digest(original)
        for spec in source["outputs"]:
            spec["verification"] = convert(spec, original)
            print(f"RECORDED {spec['name']}: {spec['verification']}")
            count += 1
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"IMPORTED_RECORDED_AUDIO count={count}")


if __name__ == "__main__":
    main()
