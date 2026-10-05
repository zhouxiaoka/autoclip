#!/usr/bin/env python3
"""Validate untagged desktop acceptance before allowing a release tag."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import release_acceptance as release

PROVENANCE = 'internal-build-provenance.json'
BUILD_JOBS = tuple(name for name in release.BUILD_JOBS if name != 'release') + ('internal-provenance',)


def identity(version, commit):
    release.identity('v' + version, commit)


def provenance(version, commit, assets, build_run_id):
    identity(version, commit)
    release.require(type(build_run_id) is int and build_run_id > 0, 'build_run_id required')
    hashes = release.assets_in(assets)
    hashes.pop(PROVENANCE, None)
    for suffix in ('.dmg', '.app.tar.gz', 'setup.exe', '.app.tar.gz.sig', 'setup.exe.sig'):
        release.require(any(name.endswith(suffix) for name in hashes), f'internal build missing {suffix}')
    return {'schema_version': 1, 'stage': 'internal', 'version': version,
            'commit': commit, 'build_run_id': build_run_id, 'assets': hashes}


def template(version, commit, assets, build_run_id):
    value = release.template('v' + version, commit, assets, 'hotfix', build_run_id)
    for field in ('tag', 'release_type', 'observation'):
        value.pop(field)
    value.update(stage='internal', version=version)
    return value


def validate(manifest, folder, assets, version, commit, build, jobs, now=None):
    identity(version, commit)
    release.require(manifest.get('schema_version') == 1 and manifest.get('stage') == 'internal', 'internal acceptance required')
    release.require(manifest.get('version') == version and manifest.get('commit') == commit, 'internal version/commit mismatch')
    release.require(manifest.get('blockers') == [], 'unresolved blockers prohibit tagging')
    release.require(manifest.get('evidence_contract') in (None, release.EVIDENCE_CONTRACT), 'unknown evidence contract')
    release.require(manifest.get('assets') == release.assets_in(assets), 'internal asset hashes do not match')
    built = json.loads((assets / PROVENANCE).read_text(encoding='utf-8'))
    release.require(built == provenance(version, commit, assets, manifest.get('build_run_id')), 'internal build provenance mismatch')
    release.require(build.get('id') == manifest['build_run_id'], 'build run mismatch')
    release.require(build.get('path') == '.github/workflows/desktop-build.yml', 'evidence must use Desktop Build')
    release.require(build.get('event') == 'workflow_dispatch' and not re.fullmatch(r'v\d+\.\d+\.\d+', build.get('head_branch', '')), 'internal build must originate from an untagged branch')
    release.require(build.get('head_sha') == commit, 'build commit mismatch')
    release.require(build.get('status') == 'completed' and build.get('conclusion') == 'success', 'internal Desktop Build did not succeed')
    for name in BUILD_JOBS:
        rows = [row for row in jobs.get('jobs', []) if row.get('name') == name or row.get('name', '').endswith(' / ' + name)]
        release.require(rows and all(row.get('conclusion') == 'success' for row in rows), f'required internal check did not pass: {name}')
    now = now or dt.datetime.now(dt.timezone.utc)
    built_at = release.timestamp(build.get('updated_at'))
    files, completed = set(), []

    def passed(row, label, platforms):
        completed.append(release.row_evidence(row, label, platforms, manifest, folder,
                                             built_at, now, files))

    for platform in release.PLATFORMS:
        row = manifest.get('platforms', {}).get(platform, {})
        for field in ('os', 'machine', 'runtime'):
            release.require(isinstance(row.get(field), str) and row[field].strip(), f'{platform} missing {field}')
        for case in release.CASES:
            passed(row.get('checks', {}).get(case), f'{platform}/{case}', [platform])
    regressions = manifest.get('regressions')
    release.require(isinstance(regressions, list) and regressions, 'explicit regression acceptance required')
    for row in regressions:
        release.require(isinstance(row, dict) and isinstance(row.get('id'), str) and row['id'].strip(), 'regression id required')
        platforms = row.get('platforms')
        release.require(isinstance(platforms, list) and platforms and all(p in release.PLATFORMS for p in platforms), 'regression platforms required')
        passed(row, 'regression ' + row['id'], platforms)
    approval = manifest.get('approval', {})
    release.require(isinstance(approval.get('name'), str) and approval['name'].strip(), 'named reviewer required')
    release.require(max(completed) <= release.timestamp(approval.get('approved_at')) <= now, 'approval must follow internal acceptance')
    return files


def tag_run(tag, annotation, object_type):
    release.identity(tag, '0' * 40)
    release.require(object_type.strip() == 'tag', 'release tag must be annotated with internal acceptance')
    rows = re.findall(r'^Internal-Acceptance-Run: ([1-9]\d*)$', annotation, re.MULTILINE)
    release.require(len(rows) == 1, 'one Internal-Acceptance-Run trailer required')
    return int(rows[0])


def check_receipt(receipt, version, commit, run):
    identity(version, commit)
    release.require(receipt.get('schema_version') == 1 and receipt.get('stage') == 'internal' and receipt.get('status') == 'passed', 'passed internal receipt required')
    release.require(receipt.get('version') == version and receipt.get('commit') == commit, 'accepted source differs from tag; rebuild and re-test first')
    release.require(type(receipt.get('acceptance_run_id')) is int and receipt['acceptance_run_id'] > 0 and run.get('id') == receipt['acceptance_run_id'], 'internal acceptance run mismatch')
    release.require(run.get('path') == '.github/workflows/internal-acceptance.yml' and run.get('event') == 'workflow_dispatch', 'receipt must originate from Internal Acceptance')
    release.require(run.get('status') == 'completed' and run.get('conclusion') == 'success', 'Internal Acceptance did not succeed')
    rows = receipt.get('assets', {})
    release.require(isinstance(rows, dict) and rows and all(isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v) for v in rows.values()), 'accepted package hashes required')
    release.timestamp(receipt.get('approved_at'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    stamp = commands.add_parser('provenance')
    check = commands.add_parser('validate')
    receipt = commands.add_parser('check-receipt')
    tag = commands.add_parser('tag-run')
    tag.add_argument('--tag', required=True)
    for command in (init, stamp, check, receipt):
        command.add_argument('--version', required=True)
        command.add_argument('--commit', required=True)
    for command in (init, stamp, check):
        command.add_argument('--assets', type=Path, required=True)
    for command in (init, stamp):
        command.add_argument('--build-run-id', type=int, required=True)
    for command in (init, check):
        command.add_argument('--manifest', type=Path, required=True)
    check.add_argument('--build-run', type=Path, required=True)
    check.add_argument('--build-jobs', type=Path, required=True)
    check.add_argument('--acceptance-run-id', type=int, required=True)
    check.add_argument('--bundle', type=Path, required=True)
    receipt.add_argument('--receipt', type=Path, required=True)
    receipt.add_argument('--acceptance-run', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'tag-run':
            ref = 'refs/tags/' + args.tag
            release.identity(args.tag, '0' * 40)
            kind = subprocess.check_output(['git', 'cat-file', '-t', ref], text=True)
            annotation = subprocess.check_output(['git', 'cat-file', '-p', ref], text=True)
            print(tag_run(args.tag, annotation, kind))
            return 0
        if args.command == 'provenance':
            value = provenance(args.version, args.commit, args.assets, args.build_run_id)
            (args.assets / PROVENANCE).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
            return 0
        if args.command == 'init':
            release.require(not args.manifest.exists(), 'refusing to overwrite acceptance evidence')
            value = template(args.version, args.commit, args.assets, args.build_run_id)
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print('Pending internal acceptance created. Do not create a tag yet.')
            return 0
        if args.command == 'check-receipt':
            check_receipt(json.loads(args.receipt.read_text(encoding='utf-8')), args.version, args.commit,
                          json.loads(args.acceptance_run.read_text(encoding='utf-8')))
            print('PASS: tag matches the source that passed internal desktop acceptance.')
            return 0
        value = json.loads(args.manifest.read_text(encoding='utf-8'))
        build = json.loads(args.build_run.read_text(encoding='utf-8'))
        jobs = json.loads(args.build_jobs.read_text(encoding='utf-8'))
        release.require(args.acceptance_run_id > 0, 'acceptance run ID required')
        files = validate(value, args.manifest.parent, args.assets, args.version, args.commit, build, jobs)
        args.bundle.mkdir(parents=True, exist_ok=False)
        for path in files:
            target = args.bundle / path.relative_to(args.manifest.parent.resolve())
            release.require(target.name not in ('acceptance.json', 'receipt.json'), 'evidence must not replace the manifest or receipt')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        (args.bundle / 'acceptance.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        proof = {'schema_version': 1, 'stage': 'internal', 'status': 'passed',
                 'version': args.version, 'commit': args.commit, 'build_run_id': value['build_run_id'],
                 'assets': value['assets'], 'acceptance_run_id': args.acceptance_run_id,
                 'reviewer': value['approval']['name'], 'approved_at': value['approval']['approved_at']}
        proof.update(evidence_contract=value.get('evidence_contract', 'execution/v1'),
                     manifest_sha256=release.digest(args.bundle / 'acceptance.json'),
                     validator_sha256={name: release.digest(Path(__file__).with_name(name))
                                       for name in ('internal_acceptance.py', 'release_acceptance.py')})
        if os.environ.get('GITHUB_SHA'):
            release.identity('v0.0.0', os.environ['GITHUB_SHA'])
            proof['validator_commit'] = os.environ['GITHUB_SHA']
        (args.bundle / 'receipt.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
        print('PASS: internal desktop acceptance complete. No tag or release was created.')
        return 0
    except (release.GateError, OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as error:
        print(f'BLOCKED: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
