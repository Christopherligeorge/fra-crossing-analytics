"""Download and verify the pinned public data archive; never overwrite a vintage."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request
from build import verify_sources

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=ROOT / 'data/frozen-2026-09-06')
    parser.add_argument('--archive', type=Path, help='Already-downloaded archive for offline verification')
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination.exists():
        raise FileExistsError('Destination exists; reuse it or choose another path')
    info = json.loads((ROOT / 'provenance/frozen_archive.json').read_text())
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix='fra-download-') as temp:
        archive = args.archive or Path(temp) / 'release.tar.gz'
        if args.archive is None:
            with urllib.request.urlopen(info['url'], timeout=120) as response, archive.open('wb') as stream:
                shutil.copyfileobj(response, stream)
        with archive.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != info['sha256'] or archive.stat().st_size != info['bytes']:
            raise ValueError('Archive checksum/size mismatch; no data extracted')
        extracted = Path(temp) / 'extracted'
        with tarfile.open(archive, 'r:gz') as bundle:
            members = bundle.getmembers()
            if len(members) != info['member_count'] or any(not m.isfile() for m in members):
                raise ValueError('Unexpected archive members')
            bundle.extractall(extracted, filter='data')
        verify_sources(extracted)
        extracted.rename(destination)
    print(f'Frozen vintage verified at {destination}')


if __name__ == '__main__':
    main()
