"""Linux import/smoke/export/replay receipt for the recorded-audio update."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

from check_audio import samples, stats

ROOT = Path(__file__).resolve().parents[1]


def main():
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]
    output = ROOT/"artifacts/audio_refresh/validation"/("release-"+run_id)
    output.mkdir(parents=True)
    isolated = Path("/tmp")/("kth-audio-release-"+run_id)
    templates = Path(os.environ.get("XDG_DATA_HOME",str(Path.home()/".local/share")))/"godot/export_templates"
    template_link = isolated/"data/godot/export_templates"
    template_link.parent.mkdir(parents=True)
    template_link.symlink_to(templates,target_is_directory=True)
    env = dict(os.environ, XDG_DATA_HOME=str(isolated/"data"),
               XDG_CONFIG_HOME=str(isolated/"config"), XDG_CACHE_HOME=str(isolated/"cache"))
    checks = {}

    def run(name, args, timeout=90):
        log = output/(name+".log")
        with log.open("w") as stream:
            result = subprocess.run(args, cwd=ROOT, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=timeout)
        text = log.read_text()
        errors = [line for line in text.splitlines() if re.search(
            r"SCRIPT ERROR|Parse Error|ERROR:|Failed loading|Cannot open|WARNING:.*leaked",line)]
        checks[name] = {"command":args,"exit_code":result.returncode,"errors":errors,
                        "log":str(log.relative_to(ROOT)),
                        "status":"pass" if result.returncode == 0 and not errors else "fail"}
        print(name,checks[name]["status"],flush=True)
        if checks[name]["status"] != "pass": raise RuntimeError("Failed "+name)
        return text

    binary = ROOT/"builds/KladTheftHummer-audio.x86_64"
    binary.parent.mkdir(exist_ok=True)
    try:
        run("project-import",["godot","--headless","--editor","--path",str(ROOT),"--quit"])
        run("headless-runtime",["godot","--headless","--path",str(ROOT),"--quit-after","120"])
        run("export",["godot","--headless","--path",str(ROOT),"--export-release","Linux",str(binary)],180)
        replay = run("exported-replay",[str(binary),"--audio-driver","Dummy","--","--verify",
                    "--evidence-dir="+str(output/"screens"),
                    "--audio-record="+str(output/"exported-mix.wav")],120)
        if "REPLAY PASS recorded_audio streams=31" not in replay or "VERIFICATION_COMPLETE" not in replay:
            raise RuntimeError("Exported replay did not complete")
        mix = stats(samples(output/"exported-mix.wav"))
        if mix["peak"] > .895 or mix["full_scale_samples"] or mix["rms_db"] < -60:
            raise RuntimeError("Invalid exported audio mix")
        checks["exported-mix"] = dict(status="pass",**mix)
        status = "pass"
    except Exception as error:
        status = "fail"
        checks["failure"] = {"status":"fail","message":str(error)}
    receipt = {"run_id":run_id,"status":status,"checks":checks,
               "highest_evidence":"L4 EXPORTED_BLACK_BOX" if status == "pass" else "see individual checks",
               "binary":str(binary.relative_to(ROOT)),
               "binary_sha256":hashlib.sha256(binary.read_bytes()).hexdigest() if binary.exists() else None,
               "notes":["Native Linux equivalent of skill validation commands; PowerShell is unavailable.",
                        "Graphical/input replay and actual Godot software mix; Dummy audio driver, no hardware listening test.",
                        "Test saves/settings isolated under /tmp."]}
    (output/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    (ROOT/"artifacts/audio_refresh/validation/latest-release.json").write_text(json.dumps(
        {"receipt":str((output/"receipt.json").relative_to(ROOT)),"status":status},indent=2)+"\n")
    print("RELEASE_VALIDATION",status,"receipt",output/"receipt.json",flush=True)
    raise SystemExit(status != "pass")


if __name__ == "__main__":
    main()
