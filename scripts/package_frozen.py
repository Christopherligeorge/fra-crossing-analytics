"""Prepare public FRA data as a release asset, never as Git objects."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
from build import verify_sources

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, required=True)
    args = parser.parse_args()
    release = args.release.resolve()
    manifest = verify_sources(release)
    members = {'data_manifest.json', 'run_manifest.json', 'metrics.csv', 'predictions.parquet'}
    members.update(a['path'] for a in manifest['artifacts'])
    for source in manifest['sources']:
        members.add(source['metadata_path'])
        members.update(page['path'] for page in source['pages'])
    output = ROOT / 'artifacts/frozen-fra-2026-09-06.tar.gz'
    with tarfile.open(output, 'x:gz', compresslevel=6) as archive:
        for name in sorted(members):
            path = release / name
            if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(release):
                raise ValueError(f'Unsafe release member: {name}')
            archive.add(path, arcname=name, recursive=False)
    with output.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    info = {'url': 'https://github.com/Christopherligeorge/fra-crossing-analytics/releases/download/v1.0.0/' + output.name,
            'sha256': digest, 'bytes': output.stat().st_size, 'member_count': len(members),
            'contents': 'Frozen public FRA selected-field extracts and original panel/evaluation reference; no private platform files.'}
    (ROOT / 'provenance/frozen_archive.json').write_text(json.dumps(info, indent=2) + '\n')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
