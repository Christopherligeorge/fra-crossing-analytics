"""Fail on unsafe staged/tracked paths, oversized files and common secret patterns."""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [rb'gh[pousr]_[A-Za-z0-9]{30,}', rb'AKIA[0-9A-Z]{16}',
            rb'sk-[A-Za-z0-9_-]{24,}', rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracked', action='store_true')
    args = parser.parse_args()
    command = ['git', 'ls-files', '-z'] if args.tracked else ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z']
    files = subprocess.check_output(command, cwd=ROOT).decode().split('\0')
    failures = []
    for name in filter(None, files):
        path = ROOT / name
        if path.is_symlink():
            failures.append((name, 'symlink not allowed in public package'))
            continue
        if path.name.startswith('.env') or path.name == 'profiles.yml' or any(p in path.parts for p in ['career', '.ai', '.profiles', '.venv']):
            failures.append((name, 'private path'))
        content = subprocess.check_output(['git', 'show', f':{name}'], cwd=ROOT)
        if len(content) > 50_000_000:
            failures.append((name, 'over 50 MB'))
        if any(re.search(pattern, content) for pattern in PATTERNS):
            failures.append((name, 'possible credential; value not printed'))
    if failures:
        raise SystemExit(str(failures))
    print('Public file check passed. Pattern scan is a safeguard, not proof that no secrets exist.')


if __name__ == '__main__':
    main()
