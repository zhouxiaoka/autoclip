#!/usr/bin/env python3
"""Fail-closed release acceptance. Uses only stdlib; no network or publishing."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlparse

PLATFORMS = ('windows-x64', 'macos-arm64')
CASES = ('clean_install', 'upgrade_legacy', 'model_settings', 'local_with_subtitles',
         'local_without_subtitles', 'link_import', 'visual_generation',
         'failure_recovery', 'output_delivery', 'privacy_telemetry')
BUILD_JOBS = ('candidate-gate', 'Backend tests', 'Frontend checks', 'Release contract checks',
              'Windows Proactor cleanup',
              'Windows media runtime regressions',
              'windows-recovery', 'real-transcription (ubuntu-latest)',
              'real-transcription (windows-latest)', 'real-transcription (macos-14)',
              'Docker compose smoke', 'Docker development compose smoke',
              'build-macos-arm64', 'build-windows-x64', 'smoke-windows-x64', 'release')


class GateError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


def identity(tag, commit):
    require(isinstance(tag, str) and re.fullmatch(r'v\d+\.\d+\.\d+', tag), 'invalid release tag')
    require(isinstance(commit, str) and re.fullmatch(r'[0-9a-f]{40}', commit), 'full commit SHA required')


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def assets_in(folder):
    return {path.name: digest(path) for path in sorted(folder.iterdir()) if path.is_file()}


def provenance(tag, commit, assets, build_run_id):
    identity(tag, commit)
    require(type(build_run_id) is int and build_run_id > 0, 'build_run_id required')
    hashes = assets_in(assets)
    hashes.pop('build-provenance.json', None)
    # GitHub normalizes uploaded asset names (the DMG build name contains spaces).
    # Use the same naming contract as scripts/write_updater_manifest.py.
    published = {name.replace(' ', '.'): value for name, value in hashes.items()}
    require(len(published) == len(hashes), 'release asset names collide after normalization')
    return {'schema_version': 1, 'tag': tag, 'commit': commit,
            'build_run_id': build_run_id, 'assets': published}


def evidence_file(folder, name):
    require(isinstance(name, str) and name.strip(), 'nonempty evidence path required')
    path = Path(name)
    require(not path.is_absolute() and '..' not in path.parts, 'evidence must stay inside its bundle')
    resolved = (folder / path).resolve()
    require(resolved.is_relative_to(folder.resolve()), 'evidence escapes its bundle')
    require(resolved.is_file() and resolved.stat().st_size > 0, f'missing evidence: {name}')
    return resolved


def timestamp(value):
    require(isinstance(value, str), 'timestamp required')
    try:
        result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise GateError('invalid timestamp') from error
    require(result.tzinfo is not None, 'timestamp must include timezone')
    return result


EVIDENCE_CONTRACT = 'impact-inheritance/v1'


def evidence_ref(folder, value, files):
    require(isinstance(value, dict), 'hashed evidence reference required')
    path = evidence_file(folder, value.get('path'))
    require(value.get('sha256') == digest(path), 'evidence SHA-256 mismatch')
    files.add(path)
    return path


def proof_json(folder, value, files):
    result = json.loads(evidence_ref(folder, value, files).read_text(encoding='utf-8'))
    require(isinstance(result, dict), 'evidence JSON object required')
    return result


def assertion_ids(value):
    require(isinstance(value, list) and value and all(isinstance(v, str) and v.strip() for v in value),
            'nonempty assertion IDs required')
    require(len(set(value)) == len(value), 'duplicate assertion IDs')
    return set(value)


def git_bytes(args, *, repo=None):
    # Commits and paths are separately validated; never execute a report's shell text.
    import subprocess
    try:
        return subprocess.check_output(['git', *args], cwd=repo or Path(__file__).resolve().parents[1],
                                       stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError) as error:
        raise GateError('source objects unavailable for impact review') from error


def row_evidence(row, label, platforms, manifest, folder, built_at, now, files, *, timed=True):
    """Return effective acceptance time; never replace the original execution time."""
    require(manifest.get('evidence_contract') in (None, EVIDENCE_CONTRACT), 'unknown evidence contract')
    require(isinstance(row, dict) and row.get('status') == 'passed', f'{label} not passed')
    files.add(evidence_file(folder, row.get('evidence')))
    mode = row.get('evidence_mode', 'execution')
    require(mode in ('execution', 'inherited'), 'unknown evidence mode')
    if mode == 'execution':
        require('reviewed_at' not in row, 'execution must not conceal an inheritance review')
        if not timed:
            return None  # Legacy release regression summaries retain their existing contract.
        at = timestamp(row.get('completed_at'))
        require(built_at <= at <= now, f'{label} evidence predates build or is in the future')
        return at
    require(manifest.get('evidence_contract') == EVIDENCE_CONTRACT, 'inheritance contract required')
    require(isinstance(platforms, list) and platforms and all(p in PLATFORMS for p in platforms)
            and len(set(platforms)) == len(platforms), 'inheritance platforms required')
    review = json.loads(evidence_file(folder, row['evidence']).read_text(encoding='utf-8'))
    require(isinstance(review, dict) and review.get('contract') == EVIDENCE_CONTRACT, 'impact review required')
    reviewed = timestamp(row.get('reviewed_at'))
    require(review.get('reviewed_at') == row['reviewed_at'] and built_at <= reviewed <= now,
            'impact review must follow current build and not be in the future')
    require(isinstance(review.get('reviewer'), str) and review['reviewer'].strip(), 'named impact reviewer required')
    require(isinstance(review.get('reason'), str) and review['reason'].strip(), 'impact scope reasoning required')
    target = {key: manifest[key] for key in ('commit', 'build_run_id', 'assets')}
    target.update(platforms=platforms, label=label)
    require(review.get('target') == target, 'impact review current target mismatch')
    origin = proof_json(folder, review.get('origin'), files)
    require(origin.get('status') == 'passed', 'original execution did not pass')
    identity('v0.0.0', origin.get('commit'))
    require(type(origin.get('build_run_id')) is int and origin['build_run_id'] > 0, 'original build ID required')
    hashes = origin.get('assets')
    require(isinstance(hashes, dict) and hashes and all(isinstance(k, str) and k and
            isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v) for k, v in hashes.items()),
            'original package hashes required')
    require(origin.get('platforms') == platforms and origin.get('label') == label, 'original assertion scope mismatch')
    require(origin.get('completed_at') == row.get('completed_at'), 'original execution time must be preserved')
    old_time = timestamp(origin.get('completed_at'))
    old_build = proof_json(folder, origin.get('build'), files)
    require(old_build.get('id') == origin['build_run_id'] and old_build.get('head_sha') == origin['commit']
            and old_build.get('path') == '.github/workflows/desktop-build.yml'
            and old_build.get('status') == 'completed' and old_build.get('conclusion') == 'success',
            'original successful Desktop Build identity mismatch')
    require(timestamp(old_build.get('updated_at')) <= old_time <= reviewed, 'original execution/build time mismatch')
    old_packages = proof_json(folder, origin.get('provenance'), files)
    require(old_packages.get('schema_version') == 1 and all(old_packages.get(k) == origin[k]
            for k in ('commit', 'build_run_id', 'assets')), 'original package provenance mismatch')
    evidence_ref(folder, origin.get('evidence'), files)
    evidence_ref(folder, review.get('runtime_evidence'), files)
    diff = proof_json(folder, review.get('diff'), files)
    require(diff.get('from_commit') == origin['commit'] and diff.get('to_commit') == manifest['commit'],
            'impact diff source mismatch')
    actual_diff = git_bytes(['diff', '--no-ext-diff', '--no-textconv', '--binary',
                             origin['commit'], manifest['commit'], '--'])
    require(diff.get('diff_sha256') == hashlib.sha256(actual_diff).hexdigest(), 'impact diff mismatch')
    dependencies = review.get('dependencies')
    require(isinstance(dependencies, list) and dependencies, 'unchanged assertion dependencies required')
    paths = set()
    for dep in dependencies:
        require(isinstance(dep, dict) and isinstance(dep.get('path'), str), 'dependency path required')
        path = Path(dep['path'])
        require(not path.is_absolute() and '..' not in path.parts and path.parts and dep['path'] not in paths,
                'unsafe or duplicate dependency path')
        paths.add(dep['path'])
        old = git_bytes(['show', f"{origin['commit']}:{dep['path']}"])
        new = git_bytes(['show', f"{manifest['commit']}:{dep['path']}"])
        require(old == new and dep.get('sha256') == hashlib.sha256(new).hexdigest(),
                'inherited assertion dependency changed')
    required = assertion_ids(review.get('required_assertions'))
    inherited = assertion_ids(review.get('inherited_assertions'))
    require(inherited <= assertion_ids(origin.get('assertions')), 'original passed assertions missing')
    affected = review.get('affected_assertions')
    require(isinstance(affected, list), 'affected assertion scope required')
    affected = assertion_ids(affected) if affected else set()
    require(not inherited & affected, 'affected assertions cannot be inherited')
    fresh = review.get('fresh')
    require(isinstance(fresh, list), 'fresh assertion evidence list required')
    covered = set(inherited)
    for ref in fresh:
        item = proof_json(folder, ref, files)
        require(item.get('status') == 'passed' and all(item.get(k) == v for k, v in target.items()),
                'fresh assertion/current target mismatch')
        require(built_at <= timestamp(item.get('completed_at')) <= reviewed,
                'affected assertion must be executed after current build and before review')
        ids = assertion_ids(item.get('assertions'))
        require(not covered & ids, 'duplicate inherited/fresh assertion coverage')
        covered.update(ids)
        evidence_ref(folder, item.get('evidence'), files)
    require(covered == required and affected <= covered - inherited,
            'incomplete required or affected assertion coverage')
    return reviewed


def validate_assets(manifest, assets, tag, repository):
    actual = assets_in(assets)
    require(manifest.get('assets') == actual, 'release assets changed or hashes do not match')
    require('build-provenance.json' in actual, 'build provenance missing')
    built = json.loads((assets / 'build-provenance.json').read_text(encoding='utf-8'))
    require(built == provenance(tag, manifest['commit'], assets, manifest['build_run_id']), 'assets do not match build provenance')
    for suffix in ('.dmg', 'setup.exe', '.app.tar.gz', '.whl', '-cli-mcp.zip'):
        require(any(name.endswith(suffix) for name in actual), f'release missing {suffix}')
    require('latest.json' in actual, 'latest.json missing')
    updater = json.loads((assets / 'latest.json').read_text(encoding='utf-8'))
    require(updater.get('version') == tag[1:], 'updater version mismatch')
    for platform, suffix in (('darwin-aarch64', '.app.tar.gz'), ('windows-x86_64', 'setup.exe')):
        row = updater.get('platforms', {}).get(platform, {})
        parsed = urlparse(row.get('url', ''))
        expected_prefix = f'/{repository}/releases/download/{tag}/'
        require(parsed.scheme == 'https' and parsed.netloc == 'github.com' and parsed.path.startswith(expected_prefix), 'updater URL points to a different release')
        name = unquote(parsed.path.removeprefix(expected_prefix))
        require(name in actual and name.endswith(suffix), f'updater asset missing for {platform}')
        signature = assets / (name + '.sig')
        require(signature.name in actual, f'updater signature missing for {platform}')
        require(bool(row.get('signature')) and signature.read_text(encoding='utf-8').strip() == row['signature'], 'updater signature mismatch')


def validate_build(manifest, build, jobs, commit):
    require(type(manifest.get('build_run_id')) is int and manifest['build_run_id'] > 0, 'build_run_id required')
    require(build.get('id') == manifest['build_run_id'], 'build run mismatch')
    require(build.get('path') == '.github/workflows/desktop-build.yml', 'evidence must use Desktop Build')
    require(build.get('event') == 'push' and build.get('head_branch') == manifest['tag'], 'build must originate from target tag')
    require(build.get('head_sha') == commit, 'build commit mismatch')
    require(build.get('status') == 'completed' and build.get('conclusion') == 'success', 'Desktop Build did not succeed')
    rows = jobs.get('jobs', [])
    for name in BUILD_JOBS:
        matches = [row for row in rows if row.get('name') == name or row.get('name', '').endswith(' / ' + name)]
        require(matches and all(row.get('conclusion') == 'success' for row in matches), f'required build check did not pass: {name}')


def template(tag, commit, assets, release_type, build_run_id):
    identity(tag, commit)
    return {'schema_version': 1, 'tag': tag, 'commit': commit, 'release_type': release_type,
            'build_run_id': build_run_id, 'assets': assets_in(assets),
            'platforms': {platform: {'os': '', 'machine': '', 'runtime': '',
                'checks': {case: {'status': 'pending', 'completed_at': None, 'evidence': ''} for case in CASES}}
                for platform in PLATFORMS},
            'regressions': [], 'blockers': [],
            'observation': {'status': 'pending', 'started_at': None, 'ended_at': None,
                'devices': {platform: 0 for platform in PLATFORMS},
                'completed_flows': {platform: 0 for platform in PLATFORMS}, 'evidence': ''},
            'approval': {'name': '', 'approved_at': None}}


def validate(manifest, folder, assets, tag, commit, repository, build, jobs, now=None):
    identity(tag, commit)
    require(manifest.get('schema_version') == 1, 'unsupported acceptance schema')
    require(manifest.get('evidence_contract') in (None, EVIDENCE_CONTRACT), 'unknown evidence contract')
    require(manifest.get('tag') == tag and manifest.get('commit') == commit, 'acceptance tag/commit mismatch')
    require(manifest.get('release_type') in ('hotfix', 'routine'), 'release_type required')
    require(manifest.get('blockers') == [], 'unresolved blockers prohibit promotion')
    validate_assets(manifest, assets, tag, repository)
    validate_build(manifest, build, jobs, commit)
    now = now or dt.datetime.now(dt.timezone.utc)
    built_at = timestamp(build.get('updated_at'))
    evidence = set()
    completed = []

    def passed(row, label):
        require(isinstance(row, dict) and row.get('status') == 'passed', f'{label} not passed')
        evidence.add(evidence_file(folder, row.get('evidence')))

    for platform in PLATFORMS:
        row = manifest.get('platforms', {}).get(platform, {})
        for field in ('os', 'machine', 'runtime'):
            require(isinstance(row.get(field), str) and row[field].strip(), f'{platform} missing {field}')
        for case in CASES:
            check = row.get('checks', {}).get(case, {})
            completed.append(row_evidence(check, f'{platform}/{case}', [platform], manifest,
                                          folder, built_at, now, evidence))
    regressions = manifest.get('regressions')
    require(isinstance(regressions, list) and regressions, 'explicit regression acceptance required')
    for row in regressions:
        require(isinstance(row.get('id'), str) and row['id'].strip(), 'regression id required')
        at = row_evidence(row, 'regression ' + row['id'], row.get('platforms'), manifest,
                          folder, built_at, now, evidence, timed=False)
        if at is not None:
            completed.append(at)
    observation = manifest.get('observation', {})
    require(observation.get('evidence_mode', 'execution') == 'execution' and 'reviewed_at' not in observation,
            'current observation cannot be inherited')
    passed(observation, 'observation')
    start, end = timestamp(observation.get('started_at')), timestamp(observation.get('ended_at'))
    hours = 4 if manifest['release_type'] == 'hotfix' else 24
    require(built_at <= start <= end <= now and end - start >= dt.timedelta(hours=hours), f'observation must cover {hours} hours after build')
    require(max(completed) <= end, 'acceptance finished after observation')
    for platform in PLATFORMS:
        for field in ('devices', 'completed_flows'):
            number = observation.get(field, {}).get(platform)
            require(type(number) is int and number > 0, f'no observed {field} for {platform}; silence is not evidence')
    approval = manifest.get('approval', {})
    require(isinstance(approval.get('name'), str) and approval['name'].strip(), 'named reviewer required')
    require(end <= timestamp(approval.get('approved_at')) <= now, 'approval must follow observation')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    check = commands.add_parser('validate')
    stamp = commands.add_parser('provenance')
    for command in (init, check, stamp):
        command.add_argument('--tag', required=True)
        command.add_argument('--commit', required=True)
        command.add_argument('--assets', type=Path, required=True)
    for command in (init, check):
        command.add_argument('--manifest', type=Path, required=True)
    stamp.add_argument('--build-run-id', type=int, required=True)
    init.add_argument('--release-type', choices=('hotfix', 'routine'), default='routine')
    init.add_argument('--build-run-id', type=int, required=True)
    check.add_argument('--repository', required=True)
    check.add_argument('--build-run', type=Path, required=True)
    check.add_argument('--build-jobs', type=Path, required=True)
    check.add_argument('--bundle', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'provenance':
            value = provenance(args.tag, args.commit, args.assets, args.build_run_id)
            (args.assets / 'build-provenance.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
            return 0
        if args.command == 'init':
            require(not args.manifest.exists(), 'refusing to overwrite acceptance evidence')
            value = template(args.tag, args.commit, args.assets, args.release_type, args.build_run_id)
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print('Pending acceptance created. It cannot pass until actual evidence is supplied.')
            return 0
        value = json.loads(args.manifest.read_text(encoding='utf-8'))
        build = json.loads(args.build_run.read_text(encoding='utf-8'))
        jobs = json.loads(args.build_jobs.read_text(encoding='utf-8'))
        files = validate(value, args.manifest.parent, args.assets, args.tag, args.commit, args.repository, build, jobs)
        if args.bundle:
            args.bundle.mkdir(parents=True, exist_ok=False)
            for path in files:
                target = args.bundle / path.relative_to(args.manifest.parent.resolve())
                require(target.name != 'acceptance.json', 'evidence must not replace the manifest')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
            (args.bundle / 'acceptance.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'PASS: {args.tag} acceptance matches code, assets, platform checks and observation.')
        return 0
    except (GateError, OSError, ValueError, TypeError, KeyError) as error:
        print(f'BLOCKED: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
