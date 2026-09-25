"""One entry point for fixture CI and hash-verified frozen-source dbt builds."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from make_fixture import make_fixture

ROOT = Path(__file__).resolve().parents[1]


def verify_sources(release):
    manifest = json.loads((release / 'data_manifest.json').read_text())
    frozen = json.loads((ROOT / 'provenance/frozen_data_manifest.json').read_text())
    if manifest != frozen:
        raise ValueError('This project reproduces the checked-in September 6 manifest, not a new vintage')
    for source in manifest['sources']:
        expected_pages = {release / page['path'] for page in source['pages']}
        actual_pages = set((release / 'sources' / source['dataset_id']).glob('page_*.csv'))
        if actual_pages != expected_pages:
            raise ValueError(f"Unexpected or missing CSV pages in {source['dataset_id']}")
        for item in source['pages'] + [{'path': source['metadata_path'], 'sha256': source['metadata_sha256']}]:
            with (release / item['path']).open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != item['sha256']:
                raise ValueError(f"Frozen source hash mismatch: {item['path']}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fixture', action='store_true')
    mode.add_argument('--release', type=Path)
    args = parser.parse_args()
    if args.fixture:
        sources = ROOT / 'data/fixture/sources'
        make_fixture(sources)
        label = 'fixture'
    else:
        release = args.release.resolve()
        verify_sources(release)
        sources = release / 'sources'
        label = 'full'
    database = ROOT / 'warehouse' / f'{label}.duckdb'
    database.parent.mkdir(exist_ok=True)
    if not args.fixture:
        # Prevent an interrupted/failed rebuild from leaving an old success certificate.
        for receipt in ['parity.json', 'evaluation/verification.json']:
            (ROOT / 'artifacts' / receipt).unlink(missing_ok=True)
    profiles = ROOT / '.profiles'
    profiles.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'profiles.example.yml', profiles / 'profiles.yml')
    env = {**os.environ, 'FRA_SOURCES': str(sources), 'CROSSING_DB': str(database),
           'DBT_PROFILES_DIR': str(profiles), 'DO_NOT_TRACK': '1'}
    dbt = str(Path(sys.executable).parent / 'dbt')
    variables = json.dumps({'full_release': not args.fixture})
    subprocess.run([dbt, 'build', '--vars', variables], cwd=ROOT, env=env, check=True)
    shutil.copyfile(ROOT / 'target/run_results.json', ROOT / 'target/build_run_results.json')
    shutil.copyfile(ROOT / 'target/run_results.json', ROOT / f'target/{label}_build_run_results.json')
    subprocess.run([dbt, 'docs', 'generate', '--vars', variables], cwd=ROOT, env=env, check=True)
    if args.fixture:
        subprocess.run([sys.executable, 'scripts/check_fixture.py'], cwd=ROOT, check=True)
    else:
        subprocess.run([sys.executable, 'scripts/check_parity.py', '--release', str(release)],
                       cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
