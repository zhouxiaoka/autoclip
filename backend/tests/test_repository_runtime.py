"""Regression checks for checkout ownership, stale PIDs and Compose selection."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from unittest.mock import Mock

import psutil
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('local_services', ROOT / 'scripts/local_services.py')
services = importlib.util.module_from_spec(spec)
spec.loader.exec_module(services)


def sleeper(root):
    return subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)',
                             'uvicorn', 'backend.main:app'], cwd=root)


def dispose(process):
    if process.poll() is None:
        process.terminate()
    process.wait(timeout=10)


def test_stop_refuses_other_checkout_even_with_matching_command(tmp_path):
    other = tmp_path / 'other'
    other.mkdir()
    child = sleeper(other)
    (tmp_path / 'backend.pid').write_text(str(child.pid))
    try:
        with pytest.raises(RuntimeError, match='another service or checkout'):
            services.stop(tmp_path, 'backend')
        assert child.poll() is None
        assert (tmp_path / 'backend.pid').exists()
    finally:
        dispose(child)


def test_pid_reuse_is_refused(tmp_path):
    child = sleeper(tmp_path)
    try:
        services.record(tmp_path, 'backend', child.pid)
        identity_file = tmp_path / 'backend.pid.json'
        identity = json.loads(identity_file.read_text())
        identity['created'] -= 1
        identity_file.write_text(json.dumps(identity))
        with pytest.raises(RuntimeError, match='identity changed'):
            services.stop(tmp_path, 'backend')
        assert child.poll() is None
    finally:
        dispose(child)


def test_stopping_recorded_process_preserves_unregistered_sibling(tmp_path):
    child = sleeper(tmp_path)
    sibling = sleeper(tmp_path)
    try:
        services.record(tmp_path, 'backend', child.pid)
        services.stop(tmp_path, 'backend')
        assert not psutil.pid_exists(child.pid)
        assert sibling.poll() is None
        assert not (tmp_path / 'backend.pid').exists()
        assert not (tmp_path / 'backend.pid.json').exists()
    finally:
        dispose(child)
        dispose(sibling)


def test_stop_without_pid_record_is_idempotent(tmp_path):
    services.stop(tmp_path, 'backend')
    services.stop(tmp_path, 'backend')


def test_invalid_pid_is_not_signalled(tmp_path):
    (tmp_path / 'backend.pid').write_text('0')
    with pytest.raises(RuntimeError, match='invalid PID'):
        services.stop(tmp_path, 'backend')


@pytest.mark.parametrize('args', [['npm run dev --host 0.0.0.0'], ['node', '/usr/bin/npm', 'run', 'dev'],
                                 ['node', '/app/frontend/node_modules/vite/bin/vite.js']])
def test_npm_process_title_and_vite_are_recognized(tmp_path, args):
    process = Mock()
    process.cwd.return_value = str(tmp_path / 'frontend')
    process.cmdline.return_value = args
    assert services.matches_service(process, tmp_path, 'frontend')


def test_running_service_is_not_reported_healthy_when_http_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(services, 'owned_process', lambda *_: Mock(pid=123))
    monkeypatch.setattr(services, 'redis_check', lambda: None)
    monkeypatch.setattr(services.urllib.request, 'urlopen', Mock(side_effect=OSError('unreachable')))
    assert services.status(tmp_path) is False


@pytest.fixture
def docker_cli(tmp_path):
    binary = tmp_path / 'bin'
    binary.mkdir()
    capture = tmp_path / 'calls'
    (binary / 'docker').write_text('''#!/usr/bin/env python3
import json, os, sys
args=sys.argv[1:]
with open(os.environ['CAPTURE'], 'a') as f: f.write(json.dumps(args)+'\\n')
if args[:2] == ['compose', 'version']: sys.exit(0)
if args[0] == 'inspect':
    print(os.getenv('CONTAINER_STATE', 'running healthy')); sys.exit(0)
if args[-2:] == ['config', '--services']: print('redis\\nautoclip')
if 'ps' in args and '-q' in args:
    if not (os.getenv('MISSING_SERVICE') and args[-1]=='autoclip'): print('abc123')
''')
    (binary / 'docker').chmod(0o755)
    env = dict(os.environ, PATH=f'{binary}:{os.environ["PATH"]}', CAPTURE=str(capture))
    return env, capture


def run_docker(action, env, *args):
    # Run from another directory; the wrapper must still select this checkout.
    return subprocess.run(['bash', str(ROOT / f'docker-{action}.sh'), *args],
                          cwd='/tmp', env=env, capture_output=True, text=True)


def test_docker_dev_stop_is_scoped_and_retains_volumes(docker_cli):
    env, capture = docker_cli
    result = run_docker('stop', env, 'dev', '--cleanup')
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in capture.read_text().splitlines()]
    assert calls[-1] == ['compose', '-f', str(ROOT / 'docker-compose.dev.yml'), 'down']
    assert not any('prune' in call or '--volumes' in call for call in calls)


@pytest.mark.parametrize('state', ['exited ', 'running unhealthy', 'running starting'])
def test_docker_unhealthy_returns_failure(docker_cli, state):
    env, _ = docker_cli
    assert run_docker('status', dict(env, CONTAINER_STATE=state)).returncode == 1


def test_docker_missing_service_returns_failure(docker_cli):
    env, _ = docker_cli
    assert run_docker('status', dict(env, MISSING_SERVICE='1')).returncode == 1


def test_docker_force_is_rejected_before_mutation(docker_cli):
    env, capture = docker_cli
    assert run_docker('stop', env, '--force').returncode == 2
    assert not capture.exists()


def test_database_init_is_idempotent_and_preserves_existing_data(tmp_path):
    database = tmp_path / 'test.db'
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE existing_data (value TEXT)')
        connection.execute("INSERT INTO existing_data VALUES ('keep me')")
    env = dict(os.environ, DATABASE_URL=f'sqlite:///{database}')
    for _ in range(2):
        result = subprocess.run([sys.executable, str(ROOT / 'init_database.py')],
                                cwd=tmp_path, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr + result.stdout
    with sqlite3.connect(database) as connection:
        assert connection.execute('SELECT value FROM existing_data').fetchone() == ('keep me',)
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='projects'").fetchone()


def test_database_failure_returns_nonzero(tmp_path):
    env = dict(os.environ, DATABASE_URL=f'sqlite:///{tmp_path}/missing/test.db')
    result = subprocess.run([sys.executable, str(ROOT / 'init_database.py')],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode != 0


def test_importing_database_helper_does_not_change_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location('init_database_helper', ROOT / 'init_database.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert Path.cwd() == tmp_path
