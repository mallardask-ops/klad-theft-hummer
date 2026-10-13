"""Fetch missing licensed originals listed in the audio manifest."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RECORDINGS = ROOT / "assets/audio/recorded"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "KladTheftHummer audio asset importer"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def main():
    manifest_path = RECORDINGS / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    pages = ROOT / "artifacts/audio_refresh/source-pages"
    pages.mkdir(parents=True, exist_ok=True)
    for source in manifest["sources"]:
        target = RECORDINGS / "originals" / source["file"]
        if target.exists():
            continue
        page = fetch(source["page_url"])
        if b"CC0" not in page:
            raise ValueError(f"Check the license before importing {source['title']}")
        (pages / (target.stem + ".html")).write_bytes(page)
        data = fetch(source["download_url"])
        if data.lstrip().startswith((b"<!DOCTYPE", b"<html")):
            raise ValueError(f"Expected audio, received HTML: {source['title']}")
        target.write_bytes(data)
        source["sha256"] = hashlib.sha256(data).hexdigest()
        print(f"FETCHED {target.name} bytes={len(data)}")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
