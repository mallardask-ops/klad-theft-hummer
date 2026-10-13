import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
META = ROOT / 'docs/reference'
DEST = ROOT / 'assets/materials'
ASSETS = ['asphalt_04', 'grey_plaster_03', 'brick_wall_09', 'quarry_wall',
          'corrugated_iron_02', 'wooden_garage_door', 'tree_bark_03',
          'forest_ground_04', 'grass_ground', 'concrete_floor_damaged_01']

catalogue = json.loads((META / 'polyhaven-textures.json').read_text())
manifest = []
def fetch(url, target):
    subprocess.run(['curl', '-fL', '--retry', '2', '--max-time', '50', '-sS', '-o', str(target), url], check=True)

for asset in ASSETS:
    metadata = META / f'{asset}-files.json'
    if not metadata.exists():
        fetch(f'https://api.polyhaven.com/files/{asset}', metadata)
    files = json.loads(metadata.read_text())
    diffuse_key = next(k for k in files if k.lower() in ['diffuse', 'diff'])
    entry = files[diffuse_key]['1k']['jpg']
    target = DEST / f'{asset}.jpg'
    if not target.exists():
        fetch(entry['url'], target)
    digest = hashlib.md5(target.read_bytes()).hexdigest()
    assert digest == entry['md5'], f'Invalid download: {asset}'
    manifest.append({'id': asset, 'path': f'assets/materials/{asset}.jpg',
                     'source': f'https://polyhaven.com/a/{asset}', 'download': entry['url'],
                     'authors': catalogue[asset].get('authors', {}), 'license': 'CC0-1.0',
                     'license_url': 'https://polyhaven.com/license', 'md5': digest})
    print(asset, target.stat().st_size, flush=True)
(DEST / 'sources.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
