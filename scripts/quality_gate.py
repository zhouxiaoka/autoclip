#!/usr/bin/env python3
"""Run the offline source checks in an isolated data directory. Never releases."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def checks(group: str, python: str):
    groups = {
        'contracts': [
            ('versions', [python, 'scripts/bump_version.py', '--check'], ROOT),
            ('readmes', [python, 'scripts/check_readmes.py'], ROOT),
            ('tracking_inventory', [python, 'scripts/check_tracking_inventory.py'], ROOT),
            ('ci_guards', [python, 'scripts/ci_guards.py'], ROOT),
            ('release_gate_tests', [python, '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', 'test_*.py'], ROOT),
        ],
        'redline': [
            ('redline_backend', [python, '-m', 'pytest', '-c', 'backend/pytest.ini', '-o', 'addopts=', 'backend/tests/redline', '-q', '-r', 's'], ROOT),
            # Same strict setup as `npm test` (#273): swallowed errors fail the redline tests too.
            ('redline_frontend', ['node', '--require', './frontend/tests/setup.cjs', '--test', *[str(path.relative_to(ROOT)) for path in sorted((ROOT / 'frontend/tests').glob('redline-*.test.cjs'))]], ROOT),
        ],
        'backend': [
            ('media_test_dependencies', [python, '-c', "import cv2, numpy, shutil; assert shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg/ffprobe required'"], ROOT),
            # Correctness rules are blocking; existing style debt is reported separately in CI.
            ('python_correctness', [python, '-m', 'ruff', 'check', '--no-cache', '--select', 'E9,F63,F7,F82', 'backend', 'scripts/quality_gate.py', 'scripts/ci_guards.py', 'scripts/release_acceptance.py', 'scripts/internal_acceptance.py', 'scripts/provider_e2e', 'scripts/tests'], ROOT),
            # Run the order-sensitive regression in a fresh process as well as the full suite.
            ('llm_hot_reload_tests', [python, '-m', 'pytest', '-c', 'backend/pytest.ini', '-o', 'addopts=', 'backend/tests/test_llm_hot_reload.py', '-q', '-r', 's'], ROOT),
            ('backend_tests', [python, '-m', 'pytest', '-c', 'backend/pytest.ini', '-o', 'addopts=', 'backend/tests', '-q', '-r', 's'], ROOT),
            ('editorial_fixtures', [python, '-m', 'backend.eval'], ROOT),
        ],
        'frontend': [
            (f'frontend_{name}', ['npm', 'run', name], ROOT / 'frontend')
            for name in ('lint', 'typecheck', 'test', 'build')
        ],
    }
    return [check for name, items in groups.items() if group in ('all', name) for check in items]


def pytest_skips(path: Path):
    """Only an external opt-in probe, a foreign-platform test, and the optional hub comparison may skip."""
    rows = []
    for case in ET.parse(path).iter('testcase'):
        if case.find('skipped') is None:
            continue
        name = case.get('name', '').split('[', 1)[0]
        module = case.get('classname', '')
        allowed = (module.endswith('test_upload_post_publisher') and name == 'test_live_upload_post_rejects_unknown_key') or (
            module.endswith('test_windows_asyncio') and name == 'test_windows_real_reset_and_subprocess' and os.name != 'nt') or (
            module.endswith('test_whisper_snapshot_repair') and name == 'test_real_hub_copy_layout_does_not_replace_an_existing_file')
        rows.append({'test': name, 'allowed': allowed})
    return rows


def pytest_coverage(path: Path, expected_modules: set[str]):
    """Require execution evidence for every backend test module and both reload cases."""
    cases = list(ET.parse(path).iter('testcase'))
    modules = {part for case in cases for part in case.get('classname', '').split('.')}
    reload_names = {case.get('name') for case in cases
                    if 'test_llm_hot_reload' in case.get('classname', '').split('.')}
    required = {
        'test_reload_pins_connection_model_and_candidates[False]',
        'test_reload_pins_connection_model_and_candidates[True]',
        'test_reload_false_then_true_with_coarse_write_times',
    }
    return {'test_count': len(cases), 'module_count': len(expected_modules & modules),
            'missing_modules': sorted(expected_modules - modules),
            'missing_reload_cases': sorted(required - reload_names)}


def run(group: str, report_path: Path, python: str) -> int:
    report_path = report_path.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip())
    report = {'schema_version': 1, 'commit': commit, 'tracked_changes': dirty,
              'group': group, 'status': 'running', 'checks': []}
    with tempfile.TemporaryDirectory(prefix='autoclip-quality-') as temp:
        data = Path(temp) / 'data'
        data.mkdir()
        (data / 'privacy.json').write_text('{"analytics":false,"crash_reports":false}', encoding='utf-8')
        env = os.environ.copy()
        # Developer selectors/plugins must not silently narrow the blocking suite.
        env.pop('PYTEST_ADDOPTS', None)
        env.pop('PYTEST_PLUGINS', None)
        # Empty inherited credentials and known dotenv keys before application imports.
        # Fixtures may set their own fake credentials inside individual tests.
        for key in tuple(env):
            if key.endswith(('_API_KEY', '_TOKEN')):
                env[key] = ''
        for provider in ('DASHSCOPE', 'OPENAI', 'GEMINI', 'DEEPSEEK', 'SEED', 'ARK',
                         'KIMI', 'GLM', 'GROK', 'INFISTAR', 'API88', 'SILICONFLOW', 'IMAGE', 'UPLOAD_POST'):
            env[provider + '_API_KEY'] = ''
            env['API_' + provider + '_API_KEY'] = ''
        # Never reset or write a developer's real database/settings, or report synthetic failures.
        env.update(AUTOCLIP_DATA_DIR=str(data), AUTOCLIP_APP_DIR=str(data),
                   DATABASE_URL='sqlite:///' + str(Path(temp) / 'test.sqlite').replace('\\', '/'),
                   SENTRY_DSN='', VITE_PUBLIC_SENTRY_DSN='', VITE_PUBLIC_POSTHOG_KEY='',
                   SENTRY_UPLOAD_SOURCEMAPS='false', PYTHONDONTWRITEBYTECODE='1',
                   AUTOCLIP_LIVE_NETWORK_TESTS='0',
                   REDIS_URL='redis://127.0.0.1:1/0', LOG_FILE=str(Path(temp) / 'tests.log'),
                   DASHSCOPE_API_KEY='test_api_key')
        failed = False
        for name, command, cwd in checks(group, python):
            print(f'Running {name}', flush=True)
            started = time.monotonic()
            skipped = []
            coverage = None
            is_pytest = name in ('backend_tests', 'llm_hot_reload_tests', 'redline_backend')
            if is_pytest:
                junit_path = Path(temp) / (name + '.xml')
                command = [*command, '--junitxml=' + str(junit_path)]
            try:
                result = subprocess.run(command, cwd=cwd, env=env, timeout=1800, check=False)
                code = result.returncode
            except (OSError, subprocess.TimeoutExpired) as error:
                print(f'{name}: {type(error).__name__}', file=sys.stderr)
                code = 1
            if is_pytest:
                try:
                    skipped = pytest_skips(junit_path)
                    if name == 'redline_backend':
                        expected = {p.stem for p in (ROOT / 'backend/tests/redline').glob('test_*.py')}
                        cases = list(ET.parse(junit_path).iter('testcase'))
                        executed = {part for case in cases for part in case.get('classname', '').split('.')}
                        coverage = {'test_count': len(cases), 'module_count': len(expected & executed),
                                    'missing_modules': sorted(expected - executed), 'missing_reload_cases': []}
                    else:
                        expected = ({p.stem for p in (ROOT / 'backend/tests').rglob('test_*.py')}
                                    if name == 'backend_tests' else {'test_llm_hot_reload'})
                        coverage = pytest_coverage(junit_path, expected)
                    if coverage['missing_modules'] or coverage['missing_reload_cases']:
                        print('BLOCKED: backend test execution evidence incomplete', file=sys.stderr)
                        code = 1
                    if any(not row['allowed'] for row in skipped):
                        print('BLOCKED: unexpected skipped regression; inspect local pytest output', file=sys.stderr)
                        code = 1
                except (OSError, ET.ParseError):
                    print('BLOCKED: pytest result evidence missing or invalid', file=sys.stderr)
                    code = 1
            entry = {'name': name, 'status': 'passed' if code == 0 else 'failed',
                     'exit_code': code, 'duration_sec': round(time.monotonic() - started, 2)}
            if is_pytest:
                entry['skipped_tests'] = skipped
                entry['coverage'] = coverage
            report['checks'].append(entry)
            failed = failed or code != 0
            report['status'] = 'failed' if failed else 'running'
            report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        report['status'] = 'failed' if failed else 'passed'
        report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return int(failed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=('all', 'contracts', 'redline', 'backend', 'frontend'), default='all')
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    return run(args.group, args.report, args.python)


if __name__ == '__main__':
    raise SystemExit(main())
