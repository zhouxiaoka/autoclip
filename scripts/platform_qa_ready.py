#!/usr/bin/env python3
"""Write a per-platform QA marker for one Desktop Build job.

The marker binds the packages produced by this job to this job's commit and
run id. It is not internal acceptance and it is not a release. A failed test,
upgrade smoke, or the other platform still blocks the final provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = 'platform-qa-ready'
OUTPUT_NAME = 'platform-qa-ready.json'
FORBIDDEN_OUTPUTS = {
    'internal-build-provenance.json',
    'build-provenance.json',
    'latest.json',
    'receipt.json',
}
PRIMARY = {
    'macos-arm64': '.dmg',
    'windows-x64': '-setup.exe',
}
INCLUDED_SUFFIXES = {
    'macos-arm64': ('.dmg', '.app.tar.gz', '.sig'),
    'windows-x64': ('-setup.exe', '.sig'),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def build_record(platform, commit, build_run_id, asset_dir: Path) -> dict:
    require(platform in PRIMARY, 'platform must be macos-arm64 or windows-x64')
    require(isinstance(commit, str) and re.fullmatch(r'[0-9a-f]{40}', commit), 'full lowercase commit SHA required')
    require(type(build_run_id) is int and build_run_id > 0, 'build_run_id required')
    require(asset_dir.is_dir(), 'platform asset directory required')
    assets = {}
    for path in sorted(asset_dir.rglob('*')):
        if not path.is_file():
            continue
        name = path.name
        if any(name.endswith(suffix) for suffix in INCLUDED_SUFFIXES[platform]):
            require(name.isascii() and '/' not in name and '\\' not in name, 'asset name must stay a single ASCII file name')
            require(name not in assets, f'duplicate asset name: {name}')
            assets[name] = digest(path)
    require(any(name.endswith(PRIMARY[platform]) for name in assets), f'platform package missing {PRIMARY[platform]}')
    return {
        'schema_version': 1,
        'stage': STAGE,
        'release_ready': False,
        'platform': platform,
        'commit': commit,
        'build_run_id': build_run_id,
        'assets': assets,
    }


def write_record(platform, commit, build_run_id, asset_dir: Path, output: Path) -> dict:
    require(output.name == OUTPUT_NAME, 'platform QA output must be named platform-qa-ready.json')
    require(output.name not in FORBIDDEN_OUTPUTS, 'platform QA cannot write a release or acceptance provenance')
    record = build_record(platform, commit, build_run_id, asset_dir)
    require(record['stage'] == STAGE and record['release_ready'] is False, 'platform QA marker drifted')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', required=True, choices=sorted(PRIMARY))
    parser.add_argument('--commit', required=True)
    parser.add_argument('--build-run-id', required=True)
    parser.add_argument('--assets', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        run_id = int(args.build_run_id)
    except ValueError as error:
        raise SystemExit('build_run_id required') from error
    try:
        write_record(args.platform, args.commit, run_id, args.assets, args.output)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
