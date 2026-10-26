"""Download the user's existing public weights; verify against known SHA-256."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from urllib.request import urlopen


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / '.voice-assets')
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name('assets-manifest.json').read_text())
    for item in manifest:
        path = args.output / item['path']
        if path.is_file() and path.stat().st_size == item['size'] and sha256(path) == item['sha256']:
            print('Verified:', item['path'], flush=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.download')
        existing = Path(__file__).resolve().parents[2] / item['path']
        if existing.is_file() and existing.stat().st_size == item['size'] and sha256(existing) == item['sha256']:
            shutil.copyfile(existing, temporary)
            temporary.replace(path)
            print('Reused repository asset:', item['path'], flush=True)
            continue
        host = 'https://media.githubusercontent.com/media' if path.suffix in ('.bin', '.safetensors') else 'https://raw.githubusercontent.com'
        url = f"{host}/taninettty/rurino_ai/c081310843ec66a9a54586cd5528bd4606b6b3b8/{item['path']}"
        print('Downloading:', item['path'], f"({item['size'] / 1024**2:.1f} MB)", flush=True)
        with urlopen(url, timeout=90) as response, temporary.open('wb') as stream:
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                stream.write(chunk)
        if temporary.stat().st_size != item['size'] or sha256(temporary) != item['sha256']:
            temporary.unlink(missing_ok=True)
            raise RuntimeError('Downloaded file failed verification: ' + item['path'])
        temporary.replace(path)
    print('Voice and Japanese BERT assets verified.', flush=True)


if __name__ == '__main__':
    main()
