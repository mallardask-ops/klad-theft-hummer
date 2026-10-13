"""Verify source hashes, installed PCM, loop boundaries and captured runtime mix."""
from array import array
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def samples(path):
    data = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path),
                                    "-f", "f32le", "-"])
    values = array("f", data)
    if sys.byteorder != "little":
        values.byteswap()
    return values


def stats(values):
    peak = max((abs(v) for v in values), default=0)
    rms = math.sqrt(sum(v*v for v in values)/max(1,len(values)))
    return {"peak":round(peak,6), "peak_db":round(20*math.log10(max(peak,1e-9)),2),
            "rms_db":round(20*math.log10(max(rms,1e-9)),2),
            "full_scale_samples":sum(abs(v) >= .9999 for v in values)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT/"assets/audio/recorded/manifest.json").read_text())
    errors = []
    assets = {}
    for source in manifest["sources"]:
        original = ROOT/"assets/audio/recorded/originals"/source["file"]
        if hashlib.sha256(original.read_bytes()).hexdigest() != source["sha256"]:
            errors.append("Source hash mismatch: "+source["file"])
        if not source["license"].startswith("CC0"):
            errors.append("Unverified license: "+source["file"])
        for spec in source["outputs"]:
            filename = spec["name"]+"."+spec.get("format","wav")
            path = ROOT/"assets/audio"/filename
            if hashlib.sha256(path.read_bytes()).hexdigest() != spec["verification"]["sha256"]:
                errors.append("Installed hash mismatch: "+filename)
            values = samples(path)
            result = stats(values)
            channels = spec.get("channels",1)
            rate = spec.get("rate",22050)
            result["duration"] = round(len(values)/channels/rate,4)
            threshold = result["peak"]*.03
            onset = next((i for i,v in enumerate(values) if abs(v)>threshold),len(values))
            result["onset_ms"] = round(onset/channels/rate*1000,2)
            if spec.get("crossfade"):
                result["loop_seam_step"] = round(max(abs(values[c]-values[-channels+c]) for c in range(channels)),6)
            assets[filename] = result
            if result["peak"] < .001 or result["peak"] > .95 or result["full_scale_samples"]:
                errors.append("Silent or clipped asset: "+filename)
            if spec["name"] in ["ui","ui_accept","impact","hammer_metal","crash","crash_light","door","engine_start","radio_static","mission_start","fail","pickup","swing","step","step_concrete_2","step_gravel","step_gravel_2"] and result["onset_ms"] > 75:
                errors.append("Late action transient: "+filename)
    installed = {p.name for p in (ROOT/"assets/audio").iterdir() if p.suffix in [".wav",".ogg"]}
    if installed != set(assets): errors.append("Runtime audio differs from licensed manifest")
    if manifest["procedural_runtime_assets"] or manifest["mixed_runtime_assets"]:
        errors.append("Procedural placeholders remain")
    phases = {}
    if args.replay_dir:
        phase_list = json.loads((args.replay_dir/"phases.json").read_text())
        if len(phase_list) != 13: errors.append("Incomplete audio replay")
        for phase in phase_list:
            path = args.replay_dir/(phase["phase"]+".wav")
            values = samples(path)
            result = stats(values)
            phases[phase["phase"]] = result
            if result["full_scale_samples"] or result["peak"] > .895:
                errors.append("Master exceeds -1 dB: "+phase["phase"])
            if phase["phase"] in ["10-pause","11-muted"]:
                if result["peak"] > .0001: errors.append("Sound remains during pause/mute: "+phase["phase"])
            elif result["rms_db"] < -60:
                errors.append("No runtime sound: "+phase["phase"])
            if phase["phase"] == "12-siren-right":
                left = stats(values[0::2])["rms_db"]
                right = stats(values[1::2])["rms_db"]
                result["left_rms_db"] = left; result["right_rms_db"] = right
                if right-left < 1: errors.append("Siren does not pan to its world position")
    receipt = {"status":"pass" if not errors else "fail", "assets":assets,
               "runtime_phases":phases, "errors":errors}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(f"AUDIO_CHECK status={receipt['status']} assets={len(assets)} phases={len(phases)}")
    for error in errors: print("FAIL",error)
    for name,result in assets.items():
        if result["onset_ms"] > 60: print("ONSET",name,result["onset_ms"])
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
