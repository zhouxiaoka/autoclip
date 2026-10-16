"""R19 #95/#97/#99/#100/#101 for #415: each test fails on 3f8863cd and passes after the fix."""
import json
import re
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services.studio import store

ROOT = Path(__file__).resolve().parents[2]
START = {'provider': 'deepseek', 'config_source': 'preset'}
LATER = {'provider': 'kimi', 'config_source': 'customized'}
OLD = 'f' * 32


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    from backend.services.studio import failure_identity, shutdown_marker
    monkeypatch.setattr(failure_identity, 'provider_identity', lambda *_a, **_k: dict(LATER))
    shutdown_marker._consumed.clear()


def _snapshot(monkeypatch, snap):
    # Patch only llm_emit: llm_telemetry resolves run_snapshot lazily via __getattr__ (patching it too
    # would pin the fake there for the rest of the session).
    from backend.core import llm_emit
    monkeypatch.setattr(llm_emit, 'run_snapshot', lambda project_id=None: dict(snap))


def _project(pid, data):
    meta = store.directory(pid) / 'metadata'
    meta.mkdir(parents=True, exist_ok=True)
    (meta / 'studio.json').write_text(json.dumps(data), encoding='utf-8')


# --- #95 (R16 #40) ---------------------------------------------------------------------------

def test_95_snapshot_provider_never_overwrites_start_identity(monkeypatch):
    _snapshot(monkeypatch, {'provider': 'kimi', 'llm_calls': 1})
    _project('p95', {'id': 'p95', 'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'r', **START}})
    store.change('p95', lambda d: d['analysis'].update(status='failed', error_code='timeout', failure_stage='production'))
    analysis = store.read('p95')['analysis']
    assert {k: analysis.get(k) for k in START} == START
    assert analysis['called_provider'] == 'kimi'
    history = store.read('p95')['analysis_history'][-1]['analysis']
    assert history['provider'] == 'deepseek' and history['config_source'] == 'preset'


def test_95_snapshot_still_fills_identity_when_start_had_none(monkeypatch):
    _snapshot(monkeypatch, {'provider': 'kimi'})
    _project('p95b', {'id': 'p95b', 'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'r'}})
    store.change('p95b', lambda d: d['analysis'].update(status='failed', error_code='timeout'))
    analysis = store.read('p95b')['analysis']
    assert analysis['provider'] == 'kimi' and 'called_provider' not in analysis


def _produce(monkeypatch, pid, fail):
    from backend.services.studio import jobs
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    if fail:
        monkeypatch.setattr(jobs, 'source', lambda *a, **k: (_ for _ in ()).throw(TimeoutError('slow')))
    else:
        monkeypatch.setattr(jobs, 'source', lambda *a, **k: 'video.mp4')
        monkeypatch.setattr(jobs, 'run_content', lambda *a, **k: [])
    _project(pid, {'id': pid, 'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'r', 'instance': store.INSTANCE, **START},
                   'generation': {'status': 'production', **START}})
    plan = {'selected_goals': ['content'], 'confirmed_preferences': {}, 'confirmed_analysis': 'subtitle'}
    jobs._produce_selected(pid, plan)
    return store.read(pid)['analysis']


@pytest.mark.parametrize('fail', [False, True], ids=['manual_success', 'manual_failure'])
def test_95_manual_production_terminals_keep_start_identity(monkeypatch, fail):
    analysis = _produce(monkeypatch, f'p95m{int(fail)}', fail)
    assert analysis['status'] == ('failed' if fail else 'completed')
    assert {k: analysis.get(k) for k in START} == START, analysis


# --- #97 (R16 #43) / #99: real store.read() on a project left mid-render by a dead process ------

def _mid_render(pid):
    _project(pid, {'id': pid,
                   'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'r', 'instance': OLD, **START},
                   'generation': {'status': 'rendering', 'auto_start': True, **START},
                   'jobs': [{'job_id': 'j1', 'status': 'running', 'instance': OLD}],
                   'output_variants': [{'id': 'a', 'status': 'completed'},
                                       {'id': 'b', 'status': 'running', 'render_job_id': 'j1'}]})


@pytest.mark.parametrize('marker,kind', [(None, 'crash'), ('user_quit', 'clean'), ('update', 'clean'), ('parent_lost', 'parent_lost')])
def test_97_restart_mid_render_records_shutdown_kind_through_store_read(marker, kind):
    from backend.services.studio.shutdown_marker import mark
    if marker:
        assert mark(marker, OLD)
    _mid_render('p97')
    state = store.read('p97')
    assert state['generation']['status'] == 'partial'
    assert state['generation']['error_code'] == store.RESTART_CODE
    assert state['generation']['shutdown_kind'] == kind
    assert state['analysis']['shutdown_kind'] == kind
    on_disk = json.loads((store.directory('p97') / 'metadata' / 'studio.json').read_text(encoding='utf-8'))
    assert on_disk['generation']['shutdown_kind'] == kind


def test_99_marker_survives_until_the_terminal_is_written(monkeypatch):
    from backend.services.studio import shutdown_marker
    assert shutdown_marker.mark('user_quit', OLD)
    marker = shutdown_marker._root() / OLD
    _mid_render('p99')
    real_write = store.write

    def broken(*a, **k):
        raise OSError('disk full')
    monkeypatch.setattr(store, 'write', broken)
    store.read('p99')                       # recovery write fails
    assert marker.exists()                  # ... so the marker must still be there
    shutdown_marker._consumed.clear()       # next process start
    monkeypatch.setattr(store, 'write', real_write)
    state = store.read('p99')
    assert state['generation']['shutdown_kind'] == 'clean'
    assert not marker.exists()              # released once the terminal is on disk


# --- #100: pop happens at `import backend`, before any child can be spawned -----------------

def test_100_backend_package_import_alone_strips_the_token(tmp_path):
    token = 'r19-child-token-' + os.urandom(8).hex()
    script = (
        "import os, subprocess, sys\n"
        "import backend\n"
        "assert 'backend.core.launch_token' in sys.modules, 'backend/__init__ must import launch_token'\n"
        "assert 'backend.app_factory' not in sys.modules\n"
        "out = subprocess.run([sys.executable, '-c', 'import os; print(os.environ.get(\"AUTOCLIP_SHUTDOWN_TOKEN\", \"<absent>\"))'],"
        " capture_output=True, text=True).stdout.strip()\n"
        "print('CHILD=' + out)\n"
        "print('PARENT_ENV=' + os.environ.get('AUTOCLIP_SHUTDOWN_TOKEN', '<absent>'))\n"
        "from backend.core import launch_token\n"
        "print('KEPT=' + str(launch_token.get() == os.environ['EXPECT']))\n"
    )
    env = {**os.environ, 'AUTOCLIP_SHUTDOWN_TOKEN': token, 'EXPECT': token,
           'AUTOCLIP_DATA_DIR': str(tmp_path), 'AUTOCLIP_APP_DIR': str(tmp_path), 'PYTHONPATH': str(ROOT)}
    done = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:].replace(token, '<token>')
    assert 'CHILD=<absent>' in done.stdout
    assert 'PARENT_ENV=<absent>' in done.stdout
    assert 'KEPT=True' in done.stdout
    assert token not in done.stdout


def test_100_package_init_imports_launch_token_statically():
    text = (ROOT / 'backend/__init__.py').read_text(encoding='utf-8')
    assert 'from backend.core import launch_token' in text


# --- #101: no token configured (web/docker) -> every request is 403 ----------------------------

@pytest.mark.parametrize('header', [None, '', 'anything', 'local-test-token-0123456789'])
def test_101_unconfigured_token_rejects_every_request(monkeypatch, header):
    from backend.api.internal import TOKEN_ENV, router
    from backend.core import launch_token
    monkeypatch.setattr(launch_token, '_token', '')
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    app = FastAPI()
    app.include_router(router)
    headers = {} if header is None else {'X-AutoClip-Local-Token': header}
    with TestClient(app, client=('127.0.0.1', 50123)) as client:
        response = client.post('/internal/shutdown-intent', json={'kind': 'user_quit'}, headers=headers)
    assert response.status_code == 403
    from backend.services.studio import shutdown_marker
    assert not (shutdown_marker._root() / store.INSTANCE).exists()


# --- #98: the shell got no 200 in time (timeout / non-200) -> unknown, never crash ----------------

def _unacked(tmp_path, instance):
    path = tmp_path / 'shutdown_markers' / instance  # R20 #134: same dir/record as the marker
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('unacked', encoding='ascii')
    return path


def test_98_unacknowledged_intent_without_marker_is_unknown_not_crash(tmp_path):
    from backend.services.studio import shutdown_marker
    _unacked(tmp_path, OLD)
    assert shutdown_marker.shutdown_kind(OLD) == 'unknown'


def test_98_slow_marker_write_that_landed_still_reads_clean(tmp_path):
    from backend.services.studio import shutdown_marker
    _unacked(tmp_path, OLD)                 # shell timed out first (record already there) ...
    assert shutdown_marker.mark('user_quit', OLD)  # ... the slow write finished before the kill
    assert shutdown_marker.shutdown_kind(OLD) == 'clean'


def test_98_no_record_at_all_is_still_crash():
    from backend.services.studio import shutdown_marker
    assert shutdown_marker.shutdown_kind(OLD) == 'crash'


def test_98_unacked_record_through_store_read_and_released(tmp_path):
    record = _unacked(tmp_path, OLD)
    _mid_render('p98')
    state = store.read('p98')
    assert state['generation']['shutdown_kind'] == 'unknown'
    assert not record.exists()


def test_98_backend_uses_and_pops_the_shell_instance_id(tmp_path):
    instance = 'ab' * 16
    script = ("import os, sys\n"
              "import backend\n"
              "print('ENV=' + os.environ.get('AUTOCLIP_INSTANCE_ID', '<absent>'))\n"
              "from backend.services.studio import store\n"
              "print('INSTANCE=' + store.INSTANCE)\n")
    env = {**os.environ, 'AUTOCLIP_INSTANCE_ID': instance, 'AUTOCLIP_DATA_DIR': str(tmp_path),
           'AUTOCLIP_APP_DIR': str(tmp_path), 'PYTHONPATH': str(ROOT)}
    env.pop('AUTOCLIP_SHUTDOWN_TOKEN', None)
    done = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    assert 'ENV=<absent>' in done.stdout and f'INSTANCE={instance}' in done.stdout
    env['AUTOCLIP_INSTANCE_ID'] = '../../etc'
    done = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert re.search(r'INSTANCE=[0-9a-f]{32}\n', done.stdout) and '../' not in done.stdout


# --- R20 #99 / #134: one record per instance, released only when no project references it ----------

def _two_projects_mid_render():
    _mid_render('pa')
    _mid_render('pb')


def test_r20_99_second_project_of_same_instance_keeps_clean_after_first_released(monkeypatch):
    from backend.services.studio import shutdown_marker
    assert shutdown_marker.mark('user_quit', OLD)
    _two_projects_mid_render()
    assert store.read('pa')['generation']['shutdown_kind'] == 'clean'   # A written, tries to release
    real_write = store.write

    def broken(*a, **k):
        raise OSError('disk full')
    monkeypatch.setattr(store, 'write', broken)
    store.read('pb')                        # B's recovery write fails
    shutdown_marker._consumed.clear()       # app restarts again
    monkeypatch.setattr(store, 'write', real_write)
    assert store.read('pb')['generation']['shutdown_kind'] == 'clean'   # was 'crash' on 6fbacce3
    assert not (shutdown_marker._root() / OLD).exists()                  # released after the last one


def test_r20_134_unacked_lives_in_the_single_marker_dir_and_is_released(tmp_path):
    from backend.services.studio import shutdown_marker
    record = _unacked(tmp_path, OLD)
    assert record.parent == shutdown_marker._root()
    _mid_render('p134')
    assert store.read('p134')['generation']['shutdown_kind'] == 'unknown'
    assert not record.exists()
    assert not (tmp_path / 'shutdown_unacked').exists()


def test_r20_134_prune_bounds_records_but_keeps_referenced_ones(monkeypatch, tmp_path):
    import os as _os
    from backend.services.studio import shutdown_marker
    monkeypatch.setattr(shutdown_marker, '_KEEP', 3)
    root = shutdown_marker._root()
    root.mkdir(parents=True, exist_ok=True)
    _mid_render('pkeep')                    # references OLD (oldest record)
    for i, name in enumerate([OLD] + [f'{i:032x}' for i in range(1, 8)]):
        (root / name).write_text('unacked', encoding='ascii')
        _os.utime(root / name, (1000 + i, 1000 + i))
    shutdown_marker.prune()                 # R21 #202: pruning moved from mark() to startup
    left = {p.name for p in root.iterdir()}
    assert OLD in left                      # still needed by an unrecovered project
    assert len(left) == 3 + 1               # newest _KEEP + the referenced one
