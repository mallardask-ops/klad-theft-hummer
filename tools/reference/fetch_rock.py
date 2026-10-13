import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'assets/source/rock_face_01'
SOURCE.mkdir(exist_ok=True)
files = json.loads((ROOT / 'docs/reference/rock_face_01-files.json').read_text())['gltf']['1k']['gltf']
entries = {'rock_face_01.gltf': files, **files['include']}
for name, entry in entries.items():
    target = SOURCE / name
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['curl', '-fL', '-sS', '--max-time', '45', '-o', str(target), entry['url']], check=True)
    assert hashlib.md5(target.read_bytes()).hexdigest() == entry['md5']
    print(name, target.stat().st_size, flush=True)
