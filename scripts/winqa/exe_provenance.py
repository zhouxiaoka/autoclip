#!/usr/bin/env python3
"""Write sha256 of each Windows installer for the acceptance machine to compare (E9).

Usage: exe_provenance.py <folder> <out.json> [--run-id N] [--commit SHA]
Output: {"schema_version": 1, "stage": "windows-build", "assets": {"<name>-setup.exe": "<sha256>"}}
Exits non-zero when no *-setup.exe is found.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def build(folder: Path, run_id: int | None = None, commit: str | None = None) -> dict:
    assets = {p.name: digest(p) for p in sorted(folder.rglob('*-setup.exe')) if p.is_file()}
    if not assets:
        raise SystemExit(f'no *-setup.exe under {folder.name}')
    return {'schema_version': 1, 'stage': 'windows-build', 'build_run_id': run_id, 'commit': commit, 'assets': assets}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--run-id', type=int)
    parser.add_argument('--commit')
    args = parser.parse_args(argv)
    args.out.write_text(json.dumps(build(args.folder, args.run_id, args.commit), indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
