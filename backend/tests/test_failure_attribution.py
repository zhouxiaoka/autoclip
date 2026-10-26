"""Behavior tests for failure attribution: one snapshot, one reader, one terminal record."""
import json
import re
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.pipeline.failures import PipelineFailure
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services.studio import store

from backend.core import llm_emit
from backend.core import llm_telemetry as schema
from backend.core.provider_presets import iter_providers
from backend.services import ai_model_settings as ai
from backend.services.studio import failure_identity
import time
from backend.services.studio import failure_identity, shutdown_marker, store
import urllib.error
from backend.services.studio import failure_identity, jobs, shutdown_marker, store
from backend.services.studio.models import ImportOptions
from backend.core.llm_manager import LLMManager
import threading
import textwrap
import types
from backend.services.studio import shutdown_marker, store
import httpx

from backend.core.failure_attribution import FailureKind, classify_failure
from backend.core.sentry_setup import studio_failure_context
from backend.tests.test_cloud_adapter_failure import cloud_adapter  # noqa: F401

from backend.core import sentry_setup
from backend.services.studio import intelligence
from backend.tests.test_studio import client, root, source  # noqa: F401

from backend.core import file_lock, llm_emit
from backend.core.sentry_setup import STUDIO_ERROR_CODES, studio_error_code
from backend.services.studio import failure_identity, store


# the only readers: guard (every snapshot field, .get and [] reads, any variable name)

import ast  # noqa: E402
import errno
import ast

import openai
from backend.core.sentry_setup import studio_error_code, studio_failure_context
from backend.tests.test_content_failure_http_status import _outline_raises, pipeline  # noqa: F401
import asyncio
import inspect
from types import SimpleNamespace
import requests

from backend.core import failure_attribution, llm_emit
from backend.pipeline.failures import PipelineFailure, http_status_of

from backend.services.studio import jobs, intelligence
from backend.tests.success_rate_sql import figure, run_sql  # noqa: E402
import socket
from backend.core.sentry_setup import studio_error_code
from backend.pipeline.failures import http_status_of

from backend.core import failure_attribution, llm_emit, sentry_setup
from backend.core.failure_attribution import AttributedError, FailureAttribution, SNAPSHOT_FIELDS, export_attribution
"""each test fails on 3f8863cd and passes after the fix."""

ROOT = Path(__file__).resolve().parents[2]
START = {'provider': 'deepseek', 'config_source': 'preset'}
LATER = {'provider': 'kimi', 'config_source': 'customized'}
OLD = 'f' * 32


@pytest.fixture
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
    monkeypatch.setattr(llm_emit, 'run_snapshot', lambda project_id=None, **_k: dict(snap))


def _project(pid, data):
    meta = store.directory(pid) / 'metadata'
    meta.mkdir(parents=True, exist_ok=True)
    (meta / 'studio.json').write_text(json.dumps(data), encoding='utf-8')



@pytest.mark.usefixtures('isolated')
def test_95_snapshot_provider_never_overwrites_start_identity(monkeypatch):
    _snapshot(monkeypatch, {'provider': 'kimi', 'llm_calls': 1})
    _project('p95', {'id': 'p95', 'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'r', **START}})
    store.change('p95', lambda d: d['analysis'].update(status='failed', error_code='timeout', failure_stage='production'))
    analysis = store.read('p95')['analysis']
    assert {k: analysis.get(k) for k in START} == START
    # an unpaired snapshot identity reads as empty and called_provider is no longer written.
    assert 'called_provider' not in analysis
    history = store.read('p95')['analysis_history'][-1]['analysis']
    assert history['provider'] == 'deepseek' and history['config_source'] == 'preset'


@pytest.mark.usefixtures('isolated')
def test_95_snapshot_still_fills_identity_when_start_had_none(monkeypatch):
    # the identity fills whole from ONE attribution (a lone provider would read as empty).
    # the store takes the snapshot from THE factory (llm_emit.attribution_snapshot), with the error in hand.
    from backend.core import llm_emit
    from backend.core.failure_attribution import build_attribution
    monkeypatch.setattr(llm_emit, 'attribution_snapshot', lambda *a, **k: build_attribution(
        PipelineFailure('ANALYZE', 'slow', code='timeout'), phase_identity={'provider': 'kimi', 'config_source': 'customized'}))
    # a live worker's run (its instance), not a stale one that read recovers as already failed
    # (service_restarted) before this write: the snapshot is stamped on the running -> failed transition.
    _project('p95b', {'id': 'p95b', 'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'r', 'instance': store.INSTANCE}})
    try:
        raise PipelineFailure('ANALYZE', 'slow', code='timeout')
    except PipelineFailure:
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
@pytest.mark.usefixtures('isolated')
def test_95_manual_production_terminals_keep_start_identity(monkeypatch, fail):
    analysis = _produce(monkeypatch, f'p95m{int(fail)}', fail)
    assert analysis['status'] == ('failed' if fail else 'completed')
    assert {k: analysis.get(k) for k in START} == START, analysis


# 97 (#43) / #99: real store.read on a project left mid-render by a dead process

def _mid_render(pid):
    _project(pid, {'id': pid,
                   'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'r', 'instance': OLD, **START},
                   'generation': {'status': 'rendering', 'auto_start': True, **START},
                   'jobs': [{'job_id': 'j1', 'status': 'running', 'instance': OLD}],
                   'output_variants': [{'id': 'a', 'status': 'completed'},
                                       {'id': 'b', 'status': 'running', 'render_job_id': 'j1'}]})


@pytest.mark.parametrize('marker,kind', [(None, 'crash'), ('user_quit', 'clean'), ('update', 'clean'), ('parent_lost', 'parent_lost')])
@pytest.mark.usefixtures('isolated')
def test_97_restart_mid_render_records_shutdown_kind_through_store_read(marker, kind):
    from backend.services.studio.shutdown_marker import mark
    if marker:
        assert mark(marker, OLD)
    _mid_render('p97')
    state = store.recover('p97')
    assert state['generation']['status'] == 'partial'
    assert state['generation']['error_code'] == store.RESTART_CODE
    assert state['generation']['shutdown_kind'] == kind
    assert state['analysis']['shutdown_kind'] == kind
    on_disk = json.loads((store.directory('p97') / 'metadata' / 'studio.json').read_text(encoding='utf-8'))
    assert on_disk['generation']['shutdown_kind'] == kind


@pytest.mark.usefixtures('isolated')
def test_99_marker_survives_until_the_terminal_is_written(monkeypatch):
    from backend.services.studio import shutdown_marker
    assert shutdown_marker.mark('user_quit', OLD)
    marker = shutdown_marker._root() / OLD
    _mid_render('p99')
    real_write = store.write

    def broken(*a, **k):
        raise OSError('disk full')
    monkeypatch.setattr(store, 'write', broken)
    store.recover('p99')                    # recovery write fails
    assert marker.exists()                  # ... so the marker must still be there
    shutdown_marker._consumed.clear()       # next process start
    monkeypatch.setattr(store, 'write', real_write)
    state = store.recover('p99')
    assert state['generation']['shutdown_kind'] == 'clean'
    assert not marker.exists()              # released once the terminal is on disk


# --- #100: pop happens at `import backend`, before any child can be spawned -----------------

@pytest.mark.usefixtures('isolated')
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


@pytest.mark.usefixtures('isolated')
def test_100_package_init_imports_launch_token_statically():
    text = (ROOT / 'backend/__init__.py').read_text(encoding='utf-8')
    assert 'from backend.core import launch_token' in text


# --- #101: no token configured (web/docker) -> every request is 403 ----------------------------

@pytest.mark.parametrize('header', [None, '', 'anything', 'local-test-token-0123456789'])
@pytest.mark.usefixtures('isolated')
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
    path = tmp_path / 'shutdown_markers' / instance  # same dir/record as the marker
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('unacked', encoding='ascii')
    return path


@pytest.mark.usefixtures('isolated')
def test_98_unacknowledged_intent_without_marker_is_unknown_not_crash(tmp_path):
    from backend.services.studio import shutdown_marker
    _unacked(tmp_path, OLD)
    assert shutdown_marker.shutdown_kind(OLD) == 'unknown'


@pytest.mark.usefixtures('isolated')
def test_98_slow_marker_write_that_landed_still_reads_clean(tmp_path):
    from backend.services.studio import shutdown_marker
    _unacked(tmp_path, OLD)                 # shell timed out first (record already there) ...
    assert shutdown_marker.mark('user_quit', OLD)  # ... the slow write finished before the kill
    assert shutdown_marker.shutdown_kind(OLD) == 'clean'


@pytest.mark.usefixtures('isolated')
def test_98_no_record_at_all_is_still_crash():
    from backend.services.studio import shutdown_marker
    assert shutdown_marker.shutdown_kind(OLD) == 'crash'


@pytest.mark.usefixtures('isolated')
def test_98_unacked_record_through_store_read_and_released(tmp_path):
    record = _unacked(tmp_path, OLD)
    _mid_render('p98')
    state = store.recover('p98')
    assert state['generation']['shutdown_kind'] == 'unknown'
    assert not record.exists()


@pytest.mark.usefixtures('isolated')
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


# 99 / #134: one record per instance, released only when no project references it

def _two_projects_mid_render():
    _mid_render('pa')
    _mid_render('pb')


@pytest.mark.usefixtures('isolated')
def test_r20_99_second_project_of_same_instance_keeps_clean_after_first_released(monkeypatch):
    from backend.services.studio import shutdown_marker
    assert shutdown_marker.mark('user_quit', OLD)
    _two_projects_mid_render()
    assert store.recover('pa')['generation']['shutdown_kind'] == 'clean'   # A written, tries to release
    real_write = store.write

    def broken(*a, **k):
        raise OSError('disk full')
    monkeypatch.setattr(store, 'write', broken)
    store.recover('pb')                     # B's recovery write fails
    shutdown_marker._consumed.clear()       # app restarts again
    monkeypatch.setattr(store, 'write', real_write)
    assert store.recover('pb')['generation']['shutdown_kind'] == 'clean'   # was 'crash' on 6fbacce3
    assert not (shutdown_marker._root() / OLD).exists()                  # released after the last one


@pytest.mark.usefixtures('isolated')
def test_r20_134_unacked_lives_in_the_single_marker_dir_and_is_released(tmp_path):
    from backend.services.studio import shutdown_marker
    record = _unacked(tmp_path, OLD)
    assert record.parent == shutdown_marker._root()
    _mid_render('p134')
    assert store.recover('p134')['generation']['shutdown_kind'] == 'unknown'
    assert not record.exists()
    assert not (tmp_path / 'shutdown_unacked').exists()


@pytest.mark.usefixtures('isolated')
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
    shutdown_marker.prune()                 # pruning moved from mark to startup
    left = {p.name for p in root.iterdir()}
    assert OLD in left                      # still needed by an unrecovered project
    assert len(left) == 3 + 1               # newest _KEEP + the referenced one
"""each test fails on 6fbacce3 and passes after the fix."""


@pytest.fixture
def two_connections(tmp_path, monkeypatch):
    """Text on DeepSeek preset, vision on a separate customized OpenAI-compatible endpoint."""
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    ai.save(ai.ModelSettings(
        connections=[
            ai.Connection(id='text', name='Text', provider='deepseek', base_url='https://api.deepseek.com', api_key='fixture-key'),
            ai.Connection(id='eyes', name='Eyes', provider='kimi', base_url='https://vision.fixture.example/v1', api_key='fixture-key'),
        ],
        analysis=ai.Assignment(connection_id='text', model='deepseek-flash', capability='text'),
        vision=ai.Assignment(connection_id='eyes', model='private-vision-model', capability='multimodal'),
        analysis_mode='visual', allow_send_frame=True,
    ))


def test_136_vision_attempt_identity_comes_from_the_vision_connection(two_connections):
    assert failure_identity.provider_identity('analysis') == {'provider': 'deepseek', 'config_source': 'preset'}
    assert failure_identity.provider_identity('vision') == {'provider': 'kimi', 'config_source': 'customized'}


def test_137_run_sanitizer_keeps_config_source_and_drops_garbage():
    assert schema.sanitize_run_properties({'config_source': 'preset'})['config_source'] == 'preset'
    assert schema.sanitize_run_properties({'config_source': 'customized'})['config_source'] == 'customized'
    assert 'config_source' not in schema.sanitize_run_properties({'config_source': 'https://x.example/v1'})


def test_137_run_snapshot_carries_config_source(two_connections):
    # inside a run the identity is the frozen phase connection (settings are never read).
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity(failure_identity.phase_identity('production', {'confirmed_analysis': 'subtitle'}))
        snap = llm_emit.run_snapshot()
    assert snap.get('config_source') == 'preset'
    assert set(snap) <= set(schema.RUN_LEVEL_FIELDS)


def test_137_frontend_send_path_keeps_config_source():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / 'frontend/src/analytics/workflow.ts').read_text(encoding='utf-8')
    assert "config_source: ['preset', 'customized']" in src


@pytest.mark.parametrize('preset', [p.id for p in iter_providers()])
def test_138_request_event_provider_is_the_catalog_id_for_every_preset(preset):
    assert llm_emit._provider_name(preset) == preset


def test_138_siliconflow_is_not_compatible_on_the_real_sender():
    class SiliconFlowProvider:
        base_url = 'https://api.siliconflow.cn/v1'
    assert llm_emit._provider_name('siliconflow') == 'siliconflow'
    assert llm_emit._provider_label(SiliconFlowProvider(), SiliconFlowProvider.base_url) == 'siliconflow'


def test_138_no_private_alias_table_in_llm_emit():
    assert not hasattr(llm_emit, '_PROVIDER_ALIASES')
    assert llm_emit._provider_name('88api') == 'api88'   # catalog alias still resolves
"""each test fails on c6938ff8 and passes after the fix."""


def _provider_down():
    """a provider failure is a request that was SENT and answered with an error (a status)."""
    return type('ProviderDown', (RuntimeError,), {'status_code': 500})('fixture')
TEXT = {'provider': 'deepseek', 'config_source': 'preset'}
EYES = {'provider': 'kimi', 'config_source': 'customized'}
VISUAL_PLAN = {'recommended_analysis': 'visual', 'confirmed_analysis': 'visual', 'preferences': {'goal': 'highlight'}}


@pytest.fixture

def isolated__r21_415(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.delenv('AUTOCLIP_SHUTDOWN_MARKER_DIR', raising=False)
    shutdown_marker._consumed.clear()


@pytest.fixture
def two_connections__r21_415(monkeypatch, isolated__r21_415):
    """Text on DeepSeek preset, vision on a customized Kimi endpoint (fixture values only)."""
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    ai.save(ai.ModelSettings(
        connections=[
            ai.Connection(id='text', name='Text', provider='deepseek', base_url='https://api.deepseek.com', api_key='fixture-key'),
            ai.Connection(id='eyes', name='Eyes', provider='kimi', base_url='https://vision.fixture.example/v1', api_key='fixture-key'),
        ],
        analysis=ai.Assignment(connection_id='text', model='deepseek-flash', capability='text'),
        vision=ai.Assignment(connection_id='eyes', model='private-vision-model', capability='multimodal'),
        analysis_mode='visual', allow_send_frame=True,
    ))


def _project__r21_415(pid, data):
    meta = store.directory(pid) / 'metadata'
    meta.mkdir(parents=True, exist_ok=True)
    (meta / 'studio.json').write_text(json.dumps(data), encoding='utf-8')
    return meta / 'studio.json'


def _vision_failure():
    # vision_call freezes the identity before it sends; the emitter only carries it.
    # a failure is attributed through the record its exception carries (not 'latest request').
    error = _provider_down()
    llm_emit.emit_vision_request(config={'model': 'private-vision-model', 'base_url': 'https://vision.fixture.example/v1'},
                                 started=time.monotonic(), error=error,
                                 identity=failure_identity.provider_identity('vision'))
    return error


def _handling(error, fn):
    try:
        raise error
    except type(error):
        return fn()


# --- #194 -------------------------------------------------------------------------------------

@pytest.mark.parametrize('phase,plan,goals,role', [
    ('screening', None, None, 'vision'),
    ('production', VISUAL_PLAN, None, 'vision'),
    ('production', VISUAL_PLAN, ['content'], 'analysis'),
    ('production', VISUAL_PLAN, ['content', 'promo'], 'vision'),
    ('production', {'recommended_analysis': 'subtitle', 'preferences': {'goal': 'content'}}, None, 'analysis'),
    ('analysis', None, None, 'analysis'),
])
@pytest.mark.usefixtures('isolated__r21_415')
def test_194_role_follows_phase_and_route(phase, plan, goals, role):
    assert failure_identity.role_for(phase, plan, goals) == role


def test_194_screening_and_visual_production_freeze_the_vision_identity(two_connections__r21_415):
    pair = failure_identity.frozen  # the phase also freezes model/host under phase_connection
    assert pair(failure_identity.phase_identity('screening')) == EYES
    assert pair(failure_identity.phase_identity('production', VISUAL_PLAN, ['highlight'])) == EYES
    assert pair(failure_identity.phase_identity('production', VISUAL_PLAN, ['content'])) == TEXT


@pytest.mark.usefixtures('isolated__r21_415')
def test_194_visual_production_start_request_terminal_all_name_the_vision_connection(two_connections__r21_415):
    start = failure_identity.phase_identity('production', VISUAL_PLAN, ['highlight'])
    _project__r21_415('p194', {'id': 'p194', 'analysis': {**start, 'status': 'running', 'phase': 'production', 'run_id': 'r'}})
    with llm_emit.track_run():
        error = _vision_failure()
        snap = llm_emit.run_snapshot(error=error)
        _handling(error, lambda: store.change('p194', lambda d: d['analysis'].update(status='failed', error_code='timeout', failure_stage='production')))
    analysis = store.read('p194')['analysis']
    assert {k: analysis.get(k) for k in EYES} == EYES
    assert {k: snap.get(k) for k in EYES} == EYES


# --- #195 -------------------------------------------------------------------------------------

@pytest.mark.usefixtures('isolated__r21_415')
def test_195_snapshot_provider_and_config_source_come_from_one_connection(two_connections__r21_415):
    with llm_emit.track_run():
        error = _vision_failure()
        snap = llm_emit.run_snapshot(error=error)
    assert (snap.get('provider'), snap.get('config_source')) == ('kimi', 'customized')


@pytest.mark.usefixtures('isolated__r21_415')
def test_195_mid_run_settings_change_does_not_split_the_snapshot_identity(two_connections__r21_415):
    with llm_emit.track_run():
        error = _vision_failure()
        settings = ai.load()
        ai.save(settings.model_copy(update={'vision': ai.Assignment(connection_id='text', model='deepseek-flash', capability='multimodal')}))
        snap = llm_emit.run_snapshot(error=error)
    assert (snap.get('provider'), snap.get('config_source')) == ('kimi', 'customized')


# --- #196 -------------------------------------------------------------------------------------

@pytest.mark.usefixtures('isolated__r21_415')
def test_196_backend_uses_the_marker_dir_the_shell_hands_it(tmp_path, monkeypatch):
    shell_dir = tmp_path / 'app' / 'shutdown_markers'
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path / 'app'))
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'moved-data'))   # user moved the data dir
    monkeypatch.setenv('AUTOCLIP_SHUTDOWN_MARKER_DIR', str(shell_dir))
    shell_dir.mkdir(parents=True)
    (shell_dir / OLD).write_text('unacked', encoding='ascii')                 # what the Rust shell writes
    assert shutdown_marker._root() == shell_dir
    assert shutdown_marker.shutdown_kind(OLD) == 'unknown'                   # not 'crash'
    assert shutdown_marker.mark('user_quit', 'e' * 32)
    assert (shell_dir / ('e' * 32)).read_text(encoding='ascii') == 'user_quit'


@pytest.mark.usefixtures('isolated__r21_415')
def test_196_shell_and_backend_share_the_env_name():
    rust = (ROOT / 'src-tauri/src/backend_manager.rs').read_text(encoding='utf-8')
    assert f'SHUTDOWN_MARKER_DIR_ENV: &str = "{shutdown_marker.MARKER_DIR_ENV}"' in rust
    assert 'cmd.env(SHUTDOWN_MARKER_DIR_ENV, dir)' in rust


# --- #197 / #202 ------------------------------------------------------------------------------

def _records(root, names, base=1000):
    root.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(names):
        (root / name).write_text('unacked', encoding='ascii')
        os.utime(root / name, (base + i, base + i))


@pytest.mark.usefixtures('isolated__r21_415')
def test_197_startup_prunes_consecutive_unacked_records_without_any_mark(monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 3)
    root = shutdown_marker._root()
    _records(root, [f'{i:032x}' for i in range(1, 9)])                       # 8 unacked exits, no mark()
    from backend.services.studio import restart_recovery

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def query(self, _model):
            return type('Q', (), {'all': staticmethod(lambda: [])})()
    threads = []
    real = shutdown_marker.prune_in_background
    monkeypatch.setattr(shutdown_marker, 'prune_in_background', lambda: threads.append(real()) or threads[-1])
    restart_recovery.reconcile_interrupted_projects(session_factory=_Session)
    assert threads, 'startup must prune'
    threads[0].join(5)
    assert len([p for p in root.iterdir()]) == 3


@pytest.mark.usefixtures('isolated__r21_415')
def test_202_mark_on_the_quit_path_never_scans_projects(monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 1)
    _records(shutdown_marker._root(), [f'{i:032x}' for i in range(1, 30)])
    scans = []
    monkeypatch.setattr(store, 'reference_index', lambda: scans.append(1) or frozenset())
    started = time.monotonic()
    assert shutdown_marker.mark('user_quit', 'e' * 32)
    assert scans == [] and time.monotonic() - started < 1


@pytest.mark.usefixtures('isolated__r21_415')
def test_202_prune_scans_projects_once_however_many_records(monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 1)
    root = shutdown_marker._root()
    _records(root, [f'{i:032x}' for i in range(1, 30)])
    real, scans = store.reference_index, []
    monkeypatch.setattr(store, 'reference_index', lambda: scans.append(1) or real())
    shutdown_marker.prune()
    assert scans == [1]
    assert len(list(root.iterdir())) == 1


# 198 (#221: the mtime rule is gone; see test_r22_415 for the reference ledger)

@pytest.mark.usefixtures('isolated__r21_415')
def test_198_release_is_not_blocked_by_an_unrelated_unreadable_project(tmp_path):
    root = shutdown_marker._root()
    _records(root, [OLD], base=2000)
    bad = _project__r21_415('broken', {})
    bad.write_text('{not json', encoding='utf-8')
    os.utime(bad, (3000, 3000))
    assert shutdown_marker.shutdown_kind(OLD) == 'unknown'
    shutdown_marker.release(OLD)
    assert not (root / OLD).exists()


# --- #199 -------------------------------------------------------------------------------------

@pytest.mark.usefixtures('isolated__r21_415')
def test_199_failed_write_leaves_no_tmp_and_startup_drops_old_orphans(monkeypatch):
    root = shutdown_marker._root()
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(shutdown_marker.os, 'replace', lambda *_a: (_ for _ in ()).throw(OSError('disk')))
    assert shutdown_marker.mark('user_quit', 'e' * 32) is False
    assert [p.name for p in root.iterdir()] == []
    monkeypatch.undo()
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(root.parent))
    orphan, fresh = root / f'.{OLD}.1.tmp', root / f'.{OLD}.2.tmp'
    orphan.write_text('x'); fresh.write_text('x')
    os.utime(orphan, (time.time() - 7200, time.time() - 7200))
    shutdown_marker.prune(root)
    assert not orphan.exists() and fresh.exists()


# --- #200 -------------------------------------------------------------------------------------

@pytest.mark.usefixtures('isolated__r21_415')
def test_200_no_runtime_marker_is_tracked_and_the_dir_is_ignored():
    tracked = subprocess.run(['git', 'ls-files', 'data/shutdown_markers'], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert tracked.strip() == ''
    ignored = subprocess.run(['git', 'check-ignore', '-q', 'data/shutdown_markers/' + OLD], cwd=ROOT)
    assert ignored.returncode == 0


# --- #201 -------------------------------------------------------------------------------------

@pytest.mark.parametrize('data', [
    {'jobs': [{'status': 'queued', 'instance': OLD}]},
    {'jobs': [{'status': 'running', 'instance': OLD}]},
    {'output_variants': [{'status': 'preparing', 'instance': OLD}]},
    {'output_variants': [{'status': 'queued', 'render_dispatch_instance': OLD}]},
    {'analysis': {'status': 'running', 'instance': OLD}},
])
@pytest.mark.usefixtures('isolated__r21_415')
def test_201_every_reference_branch_keeps_the_record(data, monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 0)
    root = shutdown_marker._root()
    _records(root, [OLD])
    _project__r21_415('ref', {'id': 'ref', **data})
    shutdown_marker.prune()
    assert (root / OLD).exists()


@pytest.mark.parametrize('data', [
    {'jobs': [{'status': 'completed', 'instance': OLD}]},
    {'output_variants': [{'status': 'failed', 'instance': OLD, 'render_dispatch_instance': OLD}]},
])
@pytest.mark.usefixtures('isolated__r21_415')
def test_201_settled_state_does_not_keep_the_record(data, monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 0)
    root = shutdown_marker._root()
    _records(root, [OLD])
    _project__r21_415('ref', {'id': 'ref', **data})
    shutdown_marker.prune()
    assert not (root / OLD).exists()


@pytest.mark.usefixtures('isolated__r21_415')
def test_201_preset_provider_survives_the_real_request_sender(monkeypatch):
    from backend.core.provider_presets import iter_providers
    sent = []
    monkeypatch.setattr(llm_emit, '_submit_event', lambda event, props: sent.append(props))
    for preset in [p.id for p in iter_providers()]:
        llm_emit.request_finished(provider=preset, model='m', kind='text', outcome='success')
    assert [p['provider'] for p in sent] == [p.id for p in iter_providers()]
"""Behavioural: every test drives the real entry point
(inspect_project -> _inspect -> _auto_generate, vision_call, observe_provider_call, store.write,
shutdown_marker.prune, the final _post_event exit). Each fails on 9f3d0b62."""
OTHER = {'provider': 'glm', 'config_source': 'customized'}
A, B, C = 'a' * 32, 'b' * 32, 'c' * 32


@pytest.fixture

def isolated__r22_415(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.delenv('AUTOCLIP_SHUTDOWN_MARKER_DIR', raising=False)
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    shutdown_marker._consumed.clear()


CONNECTIONS = [
    ai.Connection(id='text', name='Text', provider='deepseek', base_url='https://api.deepseek.com', api_key='fixture-key'),
    ai.Connection(id='eyes', name='Eyes', provider='kimi', base_url='https://vision.fixture.example/v1', api_key='fixture-key'),
    ai.Connection(id='other', name='Other', provider='glm', base_url='https://other.fixture.example/v1', api_key='fixture-key'),
]


def _settings(analysis='text', vision='eyes'):
    models = {'text': 'deepseek-flash', 'eyes': 'private-vision-model', 'other': 'private-other-model'}
    ai.save(ai.ModelSettings(
        connections=CONNECTIONS,
        analysis=ai.Assignment(connection_id=analysis, model=models[analysis], capability='text'),
        vision=ai.Assignment(connection_id=vision, model=models[vision], capability='multimodal'),
        analysis_mode='visual', allow_send_frame=True,
    ))


def _ident(record):
    return {k: (record or {}).get(k) for k in ('provider', 'config_source')}


# --- #222 / #194 / #220: the real automatic path ------------------------------------------------

@pytest.fixture
def automatic(monkeypatch):
    """inspect_project -> _inspect -> _auto_generate with only media/model work stubbed out."""
    _settings()
    store.directory('auto').mkdir(parents=True)
    submitted = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, **k: submitted.append((fn, a, k)))
    monkeypatch.setattr('backend.services.studio.readiness.ensure_analysis_usable', lambda: None)
    monkeypatch.setattr(jobs, '_prepare_speaker_framing', lambda *_: None)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda _pid: None)
    monkeypatch.setattr(jobs, 'ensure_project_thumbnail', lambda _pid: None)
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *a, **k: None)
    plan = {'mode': 'local', 'recommended_analysis': 'subtitle', 'preferences': {'goal': 'highlight'}, 'selected_goals': ['highlight']}
    monkeypatch.setattr('backend.services.studio.planning.recommend', lambda *_: dict(plan))

    def run(next_worker=True):
        jobs.inspect_project('auto', ImportOptions(auto_start=True, platforms=['douyin']))
        screening = store.read('auto')
        fn, args, kwargs = submitted.pop(0)
        assert fn is jobs._inspect
        fn(*args, **kwargs)
        return screening, submitted
    return run


@pytest.mark.usefixtures('isolated__r22_415')
def test_222_automatic_start_persists_the_production_route_identity(automatic):
    """#194 behaviour: screening runs on vision (Kimi); the subtitle route's production on text (DeepSeek)."""
    screening, _ = automatic()
    assert _ident(screening['analysis']) == EYES
    state = store.read('auto')
    assert state['analysis']['phase'] == 'production'
    assert _ident(state['analysis']) == TEXT                     # mutation 194-auto-start-screening-id
    assert _ident(state['generation']) == TEXT


@pytest.mark.usefixtures('isolated__r22_415')
def test_222_automatic_production_failure_keeps_the_identity_frozen_at_its_start(automatic, monkeypatch):
    _, submitted = automatic()
    fn, args, kwargs = submitted.pop(0)
    assert fn is jobs._auto_generate
    _settings(analysis='other')                                  # settings change after production started
    monkeypatch.setattr(jobs, '_content_drafts', lambda *_: (_ for _ in ()).throw(RuntimeError('fixture')))
    fn(*args, **kwargs)
    state = store.read('auto')
    assert state['generation']['status'] == 'failed'
    assert _ident(state['generation']) == TEXT and _ident(state['analysis']) == TEXT


@pytest.mark.usefixtures('isolated__r22_415')
def test_220_screening_identity_survives_production_refreeze(automatic):
    automatic()
    state = store.read('auto')
    assert state['analysis']['screening_identity'] == EYES       # screen_finished reads this
    assert state['generation']['screening_identity'] == EYES     # kept for the whole automatic run
    assert failure_identity.screening_identity(state['analysis']) == EYES


@pytest.mark.usefixtures('isolated__r22_415')
def test_220_screening_identity_reaches_the_terminal_history_receipt(automatic, monkeypatch):
    _, submitted = automatic()
    fn, args, kwargs = submitted.pop(0)
    monkeypatch.setattr(jobs, '_content_drafts', lambda *_: (_ for _ in ()).throw(RuntimeError('fixture')))
    fn(*args, **kwargs)
    receipt = store.read('auto')['analysis_history'][-1]['analysis']
    assert receipt['screening_identity'] == EYES and _ident(receipt) == TEXT


@pytest.mark.parametrize('plan,role', [
    ({'recommended_analysis': 'visual', 'confirmed_analysis': 'subtitle', 'preferences': {'goal': 'highlight'}}, 'analysis'),
    ({'recommended_analysis': 'subtitle', 'confirmed_analysis': 'visual', 'preferences': {'goal': 'highlight'}}, 'vision'),
])
@pytest.mark.usefixtures('isolated__r22_415')
def test_194_the_confirmed_route_wins_over_the_recommendation(plan, role):
    assert failure_identity.role_for('production', plan) == role  # mutation 194-confirmed-ignored


# --- #223: before any request the run reads the phase's frozen identity --------------------------

@pytest.mark.usefixtures('isolated__r22_415')
def test_223_snapshot_and_sentry_before_any_request_use_the_phase_identity(automatic, monkeypatch):
    _, submitted = automatic()
    fn, args, kwargs = submitted.pop(0)
    _settings(analysis='other')                                  # today's analysis connection differs
    seen = {}

    def no_request_yet(*_):
        seen['snapshot'] = llm_emit.run_snapshot()
        seen['tags'] = llm_emit.sentry_tags_for_error(None, 'production')
        raise _provider_down()
    monkeypatch.setattr(jobs, '_content_drafts', no_request_yet)
    fn(*args, **kwargs)
    assert _ident(seen['snapshot']) == TEXT
    assert seen['tags'].get('provider') == 'deepseek'


# --- #195: the request's identity is frozen when the request STARTS ------------------------------

@pytest.fixture
def posted(monkeypatch):
    events = []
    monkeypatch.setattr(llm_emit, '_submit_event', lambda event, props: events.append((event, props)))
    return events


def _vision_request(monkeypatch, during=None):
    from backend.services.studio import intelligence

    def urlopen(*_a, **_k):
        if during:
            during()
        raise urllib.error.URLError(TimeoutError())
    monkeypatch.setattr(intelligence.urllib.request, 'urlopen', urlopen)
    with pytest.raises(intelligence.VisionRequestError) as caught:
        intelligence.vision_call([{'type': 'text', 'text': 'fixture'}])
    return caught.value  # a failure is attributed through the record its exception carries (not 'latest request').


@pytest.mark.usefixtures('isolated__r22_415')
def test_195_settings_changed_while_a_vision_request_is_in_flight_do_not_move_it(monkeypatch, posted):
    _settings()
    with llm_emit.track_run():
        error = _vision_request(monkeypatch, during=lambda: _settings(vision='other'))
        snap = llm_emit.run_snapshot(error=error)
    assert _ident(snap) == EYES
    assert posted[-1][1]['provider'] == 'kimi'                   # the request event too


@pytest.mark.usefixtures('isolated__r22_415')
def test_195_each_request_freezes_its_own_identity_and_the_latest_request_is_named(monkeypatch, posted):
    # this used to assert "first request of the role wins" (EYES), which pinned the bug:
    # the second request really ran on GLM, so the run names GLM, with GLM's model/host.
    _settings()
    with llm_emit.track_run():
        _vision_request(monkeypatch)
        _settings(vision='other')
        error = _vision_request(monkeypatch)
        snap = llm_emit.run_snapshot(error=error)
    assert _ident(snap) == OTHER
    assert snap.get('base_url_host') == 'other.fixture.example' 


class _TextProvider:
    base_url = 'https://api.deepseek.com'
    model_name = 'deepseek-flash'


def _text_request():
    def impl(*_a, **_k):
        raise _provider_down()
    with llm_emit.bind_context(identity=TEXT), pytest.raises(RuntimeError) as caught:  # route identity
        llm_emit.observe_provider_call(_TextProvider(), impl, 'p')
    return caught.value


@pytest.mark.parametrize('order,expected', [(('vision', 'text'), TEXT), (('text', 'vision'), EYES)])
@pytest.mark.usefixtures('isolated__r22_415')
def test_195_snapshot_names_the_latest_requests_role(order, expected, monkeypatch, posted):
    _settings()
    with llm_emit.track_run():
        for kind in order:
            error = _vision_request(monkeypatch) if kind == 'vision' else _text_request()
        snap = llm_emit.run_snapshot(error=error)
    assert _ident(snap) == expected                              # mutation 195-role-not-latest


@pytest.mark.usefixtures('isolated__r22_415')
def test_195_text_identity_is_read_before_the_request_is_sent(posted):
    _settings()

    def impl(*_a, **_k):
        _settings(analysis='other')
        raise _provider_down()
    with llm_emit.track_run():
        with llm_emit.bind_context(identity=TEXT), pytest.raises(RuntimeError) as caught:
            llm_emit.observe_provider_call(_TextProvider(), impl, 'p')
        snap = llm_emit.run_snapshot(error=caught.value)
    assert _ident(snap) == TEXT


# --- #221 / #198 / #224: a reference ledger, not file times --------------------------------------

def _records__r22_415(names, base=1000):
    root = shutdown_marker._root()
    root.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(names):
        (root / name).write_text('unacked', encoding='ascii')
        os.utime(root / name, (base + i, base + i))
    return root


def _write_project(pid, instance):
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    store.write(pid, {'id': pid, 'analysis': {'status': 'running', 'phase': 'production', 'instance': instance}})
    return store.directory(pid) / 'metadata' / 'studio.json'


def _corrupt(path, mtime):
    path.write_text('{not json', encoding='utf-8')
    os.utime(path, (mtime, mtime))


@pytest.mark.usefixtures('isolated__r22_415')
def test_221_a_worker_write_after_the_marker_still_protects_the_record(monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 0)
    root = _records__r22_415([A], base=1000)                              # marker written at quit
    _corrupt(_write_project('late', A), 2000)                    # the worker wrote later, then the file broke
    shutdown_marker.prune()
    assert (root / A).exists()


@pytest.mark.usefixtures('isolated__r22_415')
def test_221_a_long_broken_project_does_not_pin_records_forever(monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 3)
    names = [f'{i:032x}' for i in range(1, 41)]
    root = _records__r22_415(names, base=5000)
    (store.directory('ancient') / 'metadata').mkdir(parents=True)
    _corrupt(store.directory('ancient') / 'metadata' / 'studio.json', 1)   # broken since long ago, no ledger
    shutdown_marker.prune()
    assert sorted(p.name for p in root.iterdir()) == names[-3:]


@pytest.mark.usefixtures('isolated__r22_415')
def test_224_every_unreadable_project_contributes_its_references(monkeypatch):
    """Replaces 198-floor-max: with several broken projects, each one's ledger counts (union)."""
    monkeypatch.setattr(shutdown_marker, '_KEEP', 0)
    root = _records__r22_415([A, B, C])
    _corrupt(_write_project('first', A), 10)
    _corrupt(_write_project('second', B), 99999)
    shutdown_marker.prune()
    assert sorted(p.name for p in root.iterdir()) == [A, B]


@pytest.mark.usefixtures('isolated__r22_415')
def test_221_ledger_follows_the_state_and_release_uses_it():
    root = _records__r22_415([A])
    assert shutdown_marker.shutdown_kind(A) == 'unknown'
    _write_project('p', A)
    ledger = store.directory('p') / 'metadata' / store.REFS_NAME
    assert json.loads(ledger.read_text()) == [A]
    shutdown_marker.release(A)
    assert (root / A).exists()                                   # still referenced
    store.write('p', {'id': 'p', 'analysis': {'status': 'failed', 'phase': 'production'}})
    assert json.loads(ledger.read_text()) == []
    shutdown_marker.release(A)
    assert not (root / A).exists()


# --- #201: the final send exit ------------------------------------------------------------------

@pytest.mark.usefixtures('isolated__r22_415')
def test_201_every_preset_provider_leaves_through_the_real_sender(monkeypatch):
    from backend.core.provider_presets import iter_providers
    from backend.services.studio.qa import telemetry as qa_telemetry
    bodies, warnings = [], []
    monkeypatch.setattr(qa_telemetry, '_key', lambda: 'phc_fixture')
    monkeypatch.setattr(qa_telemetry, '_analytics_allowed', lambda: True)

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def urlopen(request, timeout=None):
        bodies.append(json.loads(request.data))
        return _Response()
    monkeypatch.setattr(llm_emit.urllib.request, 'urlopen', urlopen)
    monkeypatch.setattr(llm_emit.logger, 'warning', lambda *a, **k: warnings.append(a))
    presets = [p.id for p in iter_providers()]
    for preset in presets:
        llm_emit.request_finished(provider=preset, model='m', kind='text', outcome='success')
    assert llm_emit.wait_until_idle()
    assert [b['properties']['provider'] for b in bodies] == presets
    assert {b['event'] for b in bodies} == {'llm_request_finished'}
    assert warnings == []                                        # catalog checks passed on the wire
""": a text request's identity is the connection of the route it was resolved on
(failure_identity.connection_identity, frozen with the route like vision), never settings re-read at
send time. Drives the real LLMManager route -> call -> provider.call -> observe_provider_call path.
Fails on f5921576 (observe_provider_call read settings before sending)."""


@pytest.fixture

def isolated__r23_415(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())


CONNECTIONS__r23_415 = [
    ai.Connection(id='text', name='Text', provider='deepseek', base_url='https://api.deepseek.com', api_key='fixture-key'),
    ai.Connection(id='other', name='Other', provider='glm', base_url='https://other.fixture.example/v1', api_key='fixture-key'),
]


def _settings__r23_415(analysis='text'):
    models = {'text': 'deepseek-flash', 'other': 'private-other-model'}
    ai.save(ai.ModelSettings(
        connections=CONNECTIONS__r23_415,
        analysis=ai.Assignment(connection_id=analysis, model=models[analysis], capability='text'),
    ))


def _failing_send(monkeypatch, provider, during=None):
    def create(**_k):
        if during:
            during()
        raise _provider_down()
    monkeypatch.setattr(provider.client.chat.completions, 'create', create)


def _run(manager, route):
    with llm_emit.track_run():
        with pytest.raises(Exception) as caught:
            manager.call('p', _route=route)
        # a failure is attributed through the record its exception carries (not 'latest request').
        return llm_emit.run_snapshot(error=caught.value), llm_emit.sentry_tags_for_error(caught.value, 'analyze')


@pytest.mark.usefixtures('isolated__r23_415')
def test_r23_settings_saved_after_route_before_send_keep_the_route_connection(monkeypatch, posted):
    _settings__r23_415()
    manager = LLMManager()
    route = manager._snapshot_call_route()
    _failing_send(monkeypatch, route.provider)
    _settings__r23_415(analysis='other')                       # saved between route resolution and send
    snap, tags = _run(manager, route)
    request = [p for e, p in posted if e == 'llm_request_finished'][-1]
    assert request['provider'] == 'deepseek'          # request event
    assert _ident(snap) == TEXT                       # run snapshot (generation / production)
    assert tags.get('provider') == 'deepseek'         # terminal Sentry tags


@pytest.mark.usefixtures('isolated__r23_415')
def test_r23_settings_saved_while_text_request_is_in_flight_do_not_move_it(monkeypatch, posted):
    _settings__r23_415()
    manager = LLMManager()
    route = manager._snapshot_call_route()
    _failing_send(monkeypatch, route.provider, during=lambda: _settings__r23_415(analysis='other'))
    snap, _tags = _run(manager, route)
    assert _ident(snap) == TEXT


@pytest.mark.usefixtures('isolated__r23_415')
def test_r23_route_carries_the_one_identity_rule():
    _settings__r23_415()
    route = LLMManager()._snapshot_call_route()
    assert route.identity == TEXT
    assert 'identity' not in route.settings and '_route_identity' not in route.settings  # never saved
"""the three design-retro invariants, each through the real entry point.
1) a failure names ONE request (#290/#224/#291); 2) provider + config_source are one pair from one
connection, never stitched, never re-read from settings (#296/#297); 3) the instance ledger releases a
reference only after studio.json is durable, under the writers' lock (#293/#294/#295). Plus #292.
Every test fails on 1ba867f9."""
A__r24_415, B__r24_415 = 'a' * 32, 'b' * 32
MODELS = {'text': 'deepseek-flash', 'eyes': 'private-vision-model', 'other': 'private-other-model'}


def _settings__r24_415(analysis='text', vision='eyes'):
    ai.save(ai.ModelSettings(
        connections=CONNECTIONS,
        analysis=ai.Assignment(connection_id=analysis, model=MODELS[analysis], capability='text'),
        vision=ai.Assignment(connection_id=vision, model=MODELS[vision], capability='multimodal'),
        analysis_mode='visual', allow_send_frame=True,
    ))


def _who(snap):
    return {k: snap.get(k) for k in ('provider', 'config_source', 'model', 'base_url_host', 'http_status')}


class _Status(Exception):
    def __init__(self, status):
        super().__init__('fixture')
        self.status_code = status


def _provider(base, model):
    return type('P', (), {'base_url': base, 'model_name': model})()


def _text(identity, base, model, status=None):
    def impl(*_a, **_k):
        if status:
            raise _Status(status)
        return None
    with llm_emit.bind_context(identity=identity):
        if status:
            with pytest.raises(_Status) as caught:
                llm_emit.observe_provider_call(_provider(base, model), impl, 'p')
            return caught.value
        llm_emit.observe_provider_call(_provider(base, model), impl, 'p')
        return None


# --- invariant 1: a failure names ONE request ----------------------------------------------------

@pytest.mark.usefixtures('isolated__r22_415')
def test_290_same_role_second_request_fails_snapshot_and_sentry_name_that_request_whole(posted):
    with llm_emit.track_run():
        _text(TEXT, 'https://api.deepseek.com', 'deepseek-flash')                       # DeepSeek OK
        error = _text(OTHER, 'https://other.fixture.example/v1', 'glm-4', status=503)  # GLM 503
        # the failure is read from the record its exception carries.
        snap = llm_emit.run_snapshot(error=error)
        tags = llm_emit.sentry_tags_for_error(error, 'analyze')
    assert _who(snap) == {**OTHER, 'model': 'glm-4', 'base_url_host': 'other.fixture.example', 'http_status': 503}
    assert tags.get('provider') == 'glm' and tags.get('model') == 'glm-4' and tags.get('http_status') == '503'


@pytest.mark.usefixtures('isolated__r22_415')
def test_290_a_later_success_clears_the_earlier_failure_of_another_connection(posted):
    with llm_emit.track_run():
        _text(OTHER, 'https://other.fixture.example/v1', 'glm-4', status=503)
        _text(TEXT, 'https://api.deepseek.com', 'deepseek-flash')
        snap = llm_emit.run_snapshot()
    # with no failure being handled the snapshot names no request at all (no phase frozen
    # here), so neither GLM's 503 nor a "latest request" identity can leak into it.
    assert _who(snap) == dict.fromkeys(('provider', 'config_source', 'model', 'base_url_host', 'http_status'))
    assert not snap.get('upstream_error_type')


def _vision(monkeypatch):
    from backend.services.studio import intelligence

    def urlopen(*_a, **_k):
        raise urllib.error.URLError(TimeoutError())
    monkeypatch.setattr(intelligence.urllib.request, 'urlopen', urlopen)
    with pytest.raises(intelligence.VisionRequestError) as caught:
        intelligence.vision_call([{'type': 'text', 'text': 'fixture'}])
    return caught.value


@pytest.mark.usefixtures('isolated__r22_415')
def test_224_same_role_vision_requests_on_two_connections_name_the_latest_one_whole(monkeypatch, posted):
    _settings__r24_415()
    with llm_emit.track_run():
        _vision(monkeypatch)
        _settings__r24_415(vision='other')                       # the NEXT request really runs on GLM
        error = _vision(monkeypatch)
        snap = llm_emit.run_snapshot(error=error)       # the failing request's record
    assert _who(snap)['provider'] == 'glm' and _who(snap)['config_source'] == 'customized'
    assert snap.get('model') == 'private-other-model' and snap.get('base_url_host') == 'other.fixture.example'


@pytest.mark.usefixtures('isolated__r22_415')
def test_291_failure_before_any_request_names_the_frozen_phase_connection_whole():
    _settings__r24_415()
    start = failure_identity.phase_identity('production', {'confirmed_analysis': 'subtitle'})
    _settings__r24_415(analysis='other')                         # today's settings differ
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity(start)
        snap = llm_emit.run_snapshot()
    assert _who(snap) == {**TEXT, 'model': 'deepseek-flash', 'base_url_host': 'api.deepseek.com', 'http_status': None}


@pytest.mark.usefixtures('isolated__r22_415')
def test_291_unknown_phase_connection_stays_empty_not_filled_from_settings():
    _settings__r24_415()
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({'provider': 'kimi'})   # incomplete -> unknown
        snap = llm_emit.run_snapshot()
    assert not snap.get('provider') and not snap.get('model') and not snap.get('base_url_host')


# --- invariant 2: one pair from one connection, never settings ----------------------------------

@pytest.mark.usefixtures('isolated__r22_415')
def test_296_frozen_takes_one_complete_source_never_stitches():
    assert failure_identity.frozen({'provider': 'kimi'}, {'provider': 'deepseek', 'config_source': 'preset'}) == TEXT
    assert failure_identity.frozen({'config_source': 'customized'}, {'provider': 'kimi'}) == {}
    assert failure_identity.screening_identity({'screening_identity': {'provider': 'kimi'}, 'phase': 'screening', **TEXT}) == TEXT


def _no_settings(monkeypatch):
    """Settings stay readable (a misattribution would then show up) but every read is recorded."""
    reads = []
    real = ai.load

    def load(*a, **k):
        reads.append(1)
        return real(*a, **k)
    monkeypatch.setattr(ai, 'load', load)
    return reads


@pytest.mark.usefixtures('isolated__r22_415')
def test_297_text_request_without_frozen_identity_uses_the_config_it_sent(monkeypatch, posted):
    _settings__r24_415(analysis='other')                         # saved analysis = GLM; the request sends DeepSeek
    reads = _no_settings(monkeypatch)
    with llm_emit.track_run():
        with pytest.raises(_Status) as caught:
            llm_emit.observe_provider_call(_provider('https://api.deepseek.com', 'deepseek-flash'),
                                           lambda *_a, **_k: (_ for _ in ()).throw(_Status(503)), 'p')
        snap = llm_emit.run_snapshot(error=caught.value)  
    assert {k: snap.get(k) for k in TEXT} == TEXT
    assert [p for e, p in posted if e == 'llm_request_finished'][-1]['provider'] == 'deepseek'
    assert reads == []


@pytest.mark.usefixtures('isolated__r22_415')
def test_297_vision_test_of_an_unsaved_form_is_attributed_to_the_form_not_saved_settings(monkeypatch, posted):
    _settings__r24_415()                                         # saved vision = kimi
    from backend.services.studio import intelligence

    def urlopen(*_a, **_k):
        raise urllib.error.URLError(TimeoutError())
    monkeypatch.setattr(intelligence.urllib.request, 'urlopen', urlopen)
    reads = _no_settings(monkeypatch)
    form = {'api_key': 'fixture-key', 'base_url': 'https://api.deepseek.com', 'model': 'deepseek-flash'}
    with llm_emit.track_run():
        with pytest.raises(intelligence.VisionRequestError) as caught:
            intelligence.vision_call([{'type': 'text', 'text': 'fixture'}], config=form)
        snap = llm_emit.run_snapshot(error=caught.value)  
    request = [p for e, p in posted if e == 'llm_request_finished'][-1]
    assert request['provider'] == 'deepseek'
    assert {k: snap.get(k) for k in TEXT} == TEXT
    assert reads == []


# --- #292: screening identity survives settle, restart recovery and history replay -------------

SCREEN = {'screening_identity': EYES}


@pytest.mark.usefixtures('isolated__r22_415')
def test_292_settle_generation_keeps_screening_identity():
    data = {'analysis': {**TEXT, **SCREEN, 'status': 'running', 'phase': 'rendering', 'run_id': 'r'},
            'generation': {'status': 'rendering', 'auto_start': True, **SCREEN},
            'output_variants': [{'id': 'v', 'status': 'completed'}]}
    store.settle_generation(data)
    assert data['analysis']['screening_identity'] == EYES


@pytest.mark.usefixtures('isolated__r22_415')
def test_292_restart_recovery_keeps_screening_identity():
    data = {'analysis': {**TEXT, **SCREEN, 'status': 'running', 'phase': 'production', 'run_id': 'r', 'instance': A__r24_415},
            'generation': {'status': 'production', 'auto_start': True, **SCREEN}, 'output_variants': [], 'jobs': []}
    assert store._recover_interrupted_run(data)
    assert data['analysis']['screening_identity'] == EYES


@pytest.mark.usefixtures('isolated__r22_415')
def test_220_history_receipt_of_a_settled_run_carries_its_own_screening_identity():
    store.directory('h').mkdir(parents=True)
    data = {'id': 'h', 'analysis': {**TEXT, **SCREEN, 'status': 'running', 'phase': 'rendering', 'run_id': 'r1'},
            'generation': {'status': 'rendering', 'auto_start': True, **SCREEN},
            'output_variants': [{'id': 'v', 'status': 'completed'}]}
    store.settle_generation(data)
    store.write('h', data)
    saved = json.loads((store.directory('h') / 'metadata' / 'studio.json').read_text(encoding='utf-8'))
    receipt = next(r for r in saved['analysis_history'] if r['run_id'] == 'r1')
    assert receipt['analysis']['screening_identity'] == EYES


# --- invariant 3: the ledger releases only after studio.json is durable ------------------------

def _project__r24_415(pid, instance):
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    store.write(pid, {'id': pid, 'analysis': {'status': 'running', 'phase': 'production', 'instance': instance}})
    meta = store.directory(pid) / 'metadata'
    return meta / 'studio.json', meta / store.REFS_NAME


@pytest.mark.usefixtures('isolated__r22_415')
def test_293_failed_studio_replace_keeps_the_ledger_protecting_the_surviving_state(monkeypatch):
    state, ledger = _project__r24_415('p', A__r24_415)
    real = store._replace_state

    def failing(tmp, dest):
        if dest.name == 'studio.json':
            raise OSError('fixture')
        return real(tmp, dest)
    monkeypatch.setattr(store, '_replace_state', failing)
    with pytest.raises(OSError):
        store.write('p', {'id': 'p', 'analysis': {'status': 'failed', 'phase': 'production'}})
    assert store._read_refs(ledger) == {A__r24_415}
    state.write_text('{not json', encoding='utf-8')     # studio.json briefly unreadable
    assert A__r24_415 in store.reference_index()


@pytest.mark.usefixtures('isolated__r22_415')
def test_293_failed_replace_rolls_the_ledger_back_to_exactly_what_the_surviving_state_needs(monkeypatch):
    _state, ledger = _project__r24_415('p', A__r24_415)
    real = store._replace_state

    def failing(tmp, dest):
        if dest.name == 'studio.json':
            raise OSError('fixture')
        return real(tmp, dest)
    monkeypatch.setattr(store, '_replace_state', failing)
    with pytest.raises(OSError):
        store.write('p', {'id': 'p', 'analysis': {'status': 'running', 'phase': 'production', 'instance': B__r24_415}})
    assert store._read_refs(ledger) == {A__r24_415}               # B never reached disk: it must not pin a record


@pytest.mark.usefixtures('isolated__r22_415')
def test_293_a_wrong_ledger_heals_on_the_next_write_even_if_references_did_not_change():
    state, ledger = _project__r24_415('p', A__r24_415)
    ledger.write_text('[]', encoding='ascii')           # e.g. an earlier failed ledger write
    store.write('p', json.loads(state.read_text(encoding='utf-8')))
    assert store._read_refs(ledger) == {A__r24_415}


@pytest.mark.usefixtures('isolated__r22_415')
def test_293_ledger_holds_old_and_new_references_while_studio_json_is_replaced(monkeypatch):
    _state, ledger = _project__r24_415('p', A__r24_415)
    seen = {}
    real = store._replace_state

    def spy(tmp, dest):
        if dest.name == 'studio.json':
            seen['ledger'] = store._read_refs(ledger)
        return real(tmp, dest)
    monkeypatch.setattr(store, '_replace_state', spy)
    store.write('p', {'id': 'p', 'analysis': {'status': 'running', 'phase': 'production', 'instance': B__r24_415}})
    assert seen['ledger'] == {A__r24_415, B__r24_415}
    assert store._read_refs(ledger) == {B__r24_415}


@pytest.mark.usefixtures('isolated__r22_415')
def test_294_prune_scans_and_deletes_under_the_writers_lock(monkeypatch):
    root = shutdown_marker._root()
    root.mkdir(parents=True, exist_ok=True)
    for i in range(shutdown_marker._KEEP + 2):
        (root / f'{i:032x}').write_text('unacked', encoding='ascii')
        os.utime(root / f'{i:032x}', (1000 + i, 1000 + i))
    owned = []
    real = store.index_protects
    monkeypatch.setattr(store, 'index_protects', lambda index, name: (owned.append(store.lock._is_owned()), real(index, name))[1])
    real_index = store._reference_index
    monkeypatch.setattr(store, '_reference_index', lambda: (owned.append(store.lock._is_owned()), real_index())[1])
    blocked = threading.Event()
    store.lock.acquire()
    worker = threading.Thread(target=lambda: (shutdown_marker.prune(root), blocked.set()))
    worker.start()
    try:
        assert not blocked.wait(0.3), 'prune ran while a writer held the store lock'
    finally:
        store.lock.release()
    worker.join(5)
    assert blocked.is_set() and owned and all(owned)


@pytest.mark.usefixtures('isolated__r22_415')
def test_295_state_and_ledger_are_fsynced_before_and_after_the_replace(monkeypatch):
    synced = []
    real = os.fsync

    def spy(fd):
        synced.append(fd)
        return real(fd)
    monkeypatch.setattr(store.os, 'fsync', spy)
    _project__r24_415('p', A__r24_415)
    expected = 4 if os.name != 'nt' else 2               # tmp studio + ledger tmp (+ their dirs)
    assert len(synced) >= expected
"""(design v2): one immutable record per request; a failure carries ITS record;
persistence, snapshots and Sentry read only it; identity is written whole or not at all; the ledger
never commits after a failed prepare or shrinks without durability; one cross-process store lock.
Every test fails on 156bc36a on an assertion (not an import)."""

KIMI = {'provider': 'kimi', 'config_source': 'customized'}
GLM = {'provider': 'glm', 'config_source': 'customized'}


def _call(identity, base, model, *, status=None, delay=0.0, started=None):
    def impl(*_a, **_k):
        if started:
            started.wait(2)
        time.sleep(delay)
        if status:
            raise _Status(status)
    with llm_emit.bind_context(identity=identity):
        return llm_emit.observe_provider_call(_provider(base, model), impl, 'p')


def _who__r25_415(record):
    return {k: record.get(k) for k in ('provider', 'config_source', 'model', 'base_url_host', 'http_status')}


KIMI_503 = {**KIMI, 'model': 'kimi-k2', 'base_url_host': 'kimi.fixture.example', 'http_status': 503}


def _project__r25_415(pid, analysis):
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    if analysis.get('status') == 'running':
        analysis = {'instance': store.INSTANCE, **analysis}           # a live worker, not a restart
    store.write(pid, {'id': pid, 'analysis': analysis})


# --- #331: concurrent map_chunks, A fails 503, B succeeds later ---------------------------------

@pytest.mark.usefixtures('isolated__r22_415')
def test_331_concurrent_chunk_failure_is_attributed_to_the_failing_request_everywhere(monkeypatch, posted):
    from backend.pipeline import concurrency
    monkeypatch.setenv('AUTOCLIP_LLM_CONCURRENCY', '2')
    concurrency.reset_limiter()
    _project__r25_415('p331', {'status': 'running', 'phase': 'production', 'run_id': 'r', **KIMI})
    gate = threading.Event()

    def chunk(name):
        if name == 'A':
            try:
                return _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
            finally:
                gate.set()                                   # B finishes AFTER A failed
        return _call(GLM, 'https://glm.fixture.example/v1', 'glm-4', started=gate, delay=0.05)

    with llm_emit.track_run():
        try:
            concurrency.map_chunks(chunk, ['A', 'B'])
        except _Status as error:
            tags = llm_emit.sentry_tags_for_error(error, 'production')
            store.change('p331', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    analysis = store.read('p331')['analysis']
    assert _who__r25_415(analysis) == KIMI_503
    assert (tags.get('provider'), tags.get('model'), tags.get('http_status')) == ('kimi', 'kimi-k2', '503')
    assert tags.get('base_url_host') == 'kimi.fixture.example'


@pytest.mark.usefixtures('isolated__r22_415')
def test_331_rewrapped_failure_keeps_its_request_record(posted):
    """a, : the record is found up the explicit __cause__ chain (raise from). ``from None``
cuts it: a boundary that cuts the chain must carry the snapshot itself (AttributedError)."""
    from backend.pipeline.failures import PipelineFailure
    _project__r25_415('pwrap', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    with llm_emit.track_run():
        try:
            try:
                try:
                    _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
                except _Status as inner:
                    _call(GLM, 'https://glm.fixture.example/v1', 'glm-4')   # a later success (fallback probe)
                    raise PipelineFailure('ANALYZE', 'fixture', code='provider_error') from inner
            except PipelineFailure as failure:
                raise RuntimeError('wrapped') from failure                  # explicit cause
        except RuntimeError as outer:
            tags = llm_emit.sentry_tags_for_error(outer, 'production')
            store.change('pwrap', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    assert _who__r25_415(store.read('pwrap')['analysis']) == KIMI_503
    assert tags.get('provider') == 'kimi' and tags.get('http_status') == '503'


@pytest.mark.usefixtures('isolated__r22_415')
def test_331_failure_without_request_record_falls_back_to_phase_and_says_so():
    from backend.services.studio import failure_identity
    phase = {**GLM, 'model': 'glm-4', 'base_url_host': 'glm.fixture.example'}
    _project__r25_415('pphase', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: phase, **GLM})
        from backend.pipeline.failures import PipelineFailure
        try:  # only a MODEL failure without a record falls back to the phase identity
            raise PipelineFailure('ANALYZE', 'model timed out before a record existed', code='timeout')
        except PipelineFailure:
            store.change('pphase', lambda d: d['analysis'].update(status='failed', error_code='timeout'))
    analysis = store.read('pphase')['analysis']
    assert {k: analysis.get(k) for k in phase} == phase
    assert analysis.get('attribution_source') == 'phase' and 'http_status' not in analysis


# --- #332: persisted identity is ONE record, never merged field by field -------------------------

@pytest.mark.usefixtures('isolated__r22_415')
def test_332_failure_write_never_stitches_attempt_identity_with_another_requests_fields(posted):
    _project__r25_415('p332', {'status': 'running', 'phase': 'production', 'run_id': 'r', 'provider': 'kimi', 'config_source': 'preset'})
    with llm_emit.track_run():
        try:
            _call(GLM, 'https://glm.fixture.example/v1', 'glm-4', status=503)
        except _Status:
            store.change('p332', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    data = store.read('p332')
    whole = {**GLM, 'model': 'glm-4', 'base_url_host': 'glm.fixture.example', 'http_status': 503}
    assert _who__r25_415(data['analysis']) == whole
    assert 'called_provider' not in data['analysis']
    row = data['analysis_history'][-1]['analysis']
    assert (row.get('provider'), row.get('config_source')) == ('glm', 'customized')


@pytest.mark.usefixtures('isolated__r22_415')
def test_332_unpaired_legacy_identity_reads_as_empty_not_half():
    _project__r25_415('plegacy', {'status': 'completed', 'phase': 'production', 'run_id': 'r',
                         'provider': 'kimi', 'model': 'glm-4', 'base_url_host': 'glm.fixture.example'})
    store.change('plegacy', lambda d: d.update(note=1))
    analysis = store.read('plegacy')['analysis']
    assert not any(analysis.get(k) for k in ('provider', 'config_source', 'model', 'base_url_host'))


# --- #333: a write without requests (render) never re-reads settings ----------------------------

@pytest.mark.usefixtures('isolated__r22_415')
def test_333_render_write_keeps_the_stored_failure_identity_when_settings_changed():
    ai.save(ai.ModelSettings(
        connections=[ai.Connection(id='g', name='G', provider='glm', base_url='https://glm.fixture.example/v1', api_key='fixture-key')],
        analysis=ai.Assignment(connection_id='g', model='glm-4', capability='text')))
    _project__r25_415('p333', {'status': 'failed', 'phase': 'production', 'run_id': 'r', 'error_code': 'provider_error', **KIMI_503})
    with llm_emit.track_run():                                    # the render worker: no request, no phase
        store.change('p333', lambda d: d.setdefault('jobs', []).append({'job_id': 'j', 'status': 'running'}))
    assert _who__r25_415(store.read('p333')['analysis']) == KIMI_503


# --- #334: a failed ledger prepare blocks the studio.json commit --------------------------------

@pytest.mark.usefixtures('isolated__r22_415')
def test_334_failed_ledger_prepare_does_not_commit_studio_json(monkeypatch):
    _project__r25_415('p334', {'status': 'running', 'phase': 'production', 'instance': A__r24_415})
    state = store.directory('p334') / 'metadata' / 'studio.json'
    real = store._publish

    def ledger_down(path, text, encoding):
        if path.name == store.REFS_NAME:
            raise OSError('fixture: ledger not writable')
        return real(path, text, encoding)
    monkeypatch.setattr(store, '_publish', ledger_down)
    with pytest.raises(OSError):
        store.write('p334', {'id': 'p334', 'analysis': {'status': 'running', 'phase': 'production', 'instance': B__r24_415}})
    assert json.loads(state.read_text(encoding='utf-8'))['analysis']['instance'] == A__r24_415
    ledger = store._read_refs(state.with_name(store.REFS_NAME))
    assert A__r24_415 in ledger and B__r24_415 not in ledger                         # every reference on disk is protected


# --- #335: the store lock excludes other processes (CLI / MCP children) -------------------------

def _hold_lock_in_child(tmp_path, seconds):
    ready = tmp_path / 'child-ready'
    code = textwrap.dedent(f'''
        import time, pathlib
        from backend.services.studio import store
        with store.lock:
            pathlib.Path({str(ready)!r}).write_text('1')
            time.sleep({seconds})
    ''')
    env = {**os.environ, 'PYTHONPATH': str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH', '')}
    child = subprocess.Popen([sys.executable, '-c', code], cwd=str(ROOT), env=env)
    deadline = time.monotonic() + 30
    while not ready.exists():
        assert child.poll() is None and time.monotonic() < deadline, 'child did not take the lock'
        time.sleep(0.02)
    return child


def _records__r25_415(root, count):
    root.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (root / f'{i:032x}').write_text('unacked', encoding='ascii')
        os.utime(root / f'{i:032x}', (1000 + i, 1000 + i))


# --- #336: the settings-page vision test carries the tested connection's identity ---------------

@pytest.mark.usefixtures('isolated__r22_415')
def test_336_settings_vision_test_uses_the_connection_identity_not_its_hostname(monkeypatch, posted):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.services import provider_validation
    from backend.services.studio import intelligence
    ok = types.SimpleNamespace(ok=True, normalized_base_url=None, as_api=lambda: {'ok': True, 'success': True})
    monkeypatch.setattr(provider_validation, 'validate_connection', lambda *a, **k: ok)

    def urlopen(*_a, **_k):
        raise urllib.error.URLError(TimeoutError())
    monkeypatch.setattr(intelligence.urllib.request, 'urlopen', urlopen)
    connection = ai.Connection(id='eyes', name='Eyes', provider='kimi', base_url='https://vision.fixture.example/v1', api_key='fixture-key')
    app = FastAPI()
    from backend.api.v1.settings import router
    app.include_router(router)
    with TestClient(app) as client:
        client.post('/settings/ai-models/test', json={'connection': connection.model_dump(), 'model': 'private-vision-model', 'vision': True})
    vision = [p for e, p in posted if e == 'llm_request_finished' and p.get('kind') == 'vision']
    assert vision and vision[-1]['provider'] == 'kimi'


# --- #337: unknown directory durability keeps the ledger union ----------------------------------

@pytest.mark.skipif(os.name == 'nt', reason='Windows has no directory fsync')
@pytest.mark.usefixtures('isolated__r22_415')
def test_337_dir_fsync_failure_keeps_the_ledger_union(monkeypatch):
    _project__r25_415('p337', {'status': 'running', 'phase': 'production', 'instance': A__r24_415})
    real_open = os.open

    def no_dir_fsync(path, flags, *args):
        if os.path.isdir(path):
            raise OSError('fixture: directory fsync unavailable')
        return real_open(path, flags, *args)
    monkeypatch.setattr(store.os, 'open', no_dir_fsync)
    store.write('p337', {'id': 'p337', 'analysis': {'status': 'running', 'phase': 'production', 'instance': B__r24_415}})
    monkeypatch.setattr(store.os, 'open', real_open)
    ledger = store._read_refs(store.directory('p337') / 'metadata' / store.REFS_NAME)
    assert ledger == {A__r24_415, B__r24_415}


# --- #338: the write-only accumulator fields and the old doc rule are gone ----------------------

@pytest.mark.usefixtures('isolated__r22_415')
def test_338_run_accumulator_has_no_write_only_identity_fields():
    fields = set(llm_emit._RunAcc.__dataclass_fields__)
    assert not fields & {'identities', 'provider', 'model', 'host', 'last_http_status', 'last_upstream', 'last_request'}


@pytest.mark.usefixtures('isolated__r22_415')
def test_338_tracking_plan_states_the_failing_request_rule():
    text = (ROOT / 'docs' / 'analytics' / 'TRACKING_PLAN.md').read_text(encoding='utf-8')
    assert '每个 role 以第一个请求为准' not in text and '取最近一次请求' not in text
    assert 'attribution_source=request' in text


# m4: Windows fsync needs a writable descriptor (platform independent check)

@pytest.mark.usefixtures('isolated__r22_415')
def test_295_file_fsync_opens_read_write(monkeypatch, tmp_path):
    seen = []
    real_open = os.open
    monkeypatch.setattr(store.os, 'open', lambda path, flags, *a: (seen.append(flags), real_open(path, flags, *a))[1])
    target = tmp_path / 'f'
    target.write_text('x')
    store._fsync_file(target)
    assert seen and seen[0] & os.O_RDWR


@pytest.mark.usefixtures('isolated__r22_415')
def test_331_an_outer_observed_layer_never_replaces_the_failing_requests_record(posted):
    """The same exception may pass through an outer observed call; the request that failed keeps it."""
    def outer(*_a, **_k):
        _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
    with llm_emit.track_run():
        with llm_emit.bind_context(identity=GLM), pytest.raises(_Status) as caught:
            llm_emit.observe_provider_call(_provider('https://glm.fixture.example/v1', 'glm-4'), outer, 'p')
        tags = llm_emit.sentry_tags_for_error(caught.value, 'analyze')
    assert (tags.get('provider'), tags.get('model'), tags.get('http_status')) == ('kimi', 'kimi-k2', '503')
"""the cloud-transcription redaction boundary builds the snapshot; the legacy import path
(import_processing) carries it instead of rebuilding from the safe text. Separate module: no store fixture."""

SECRET_BODY = 'r29-private-asr-body'


def test_import_subtitle_failure_keeps_the_transcription_snapshot(cloud_adapter):
    import pytest
    from backend.services import cloud_transcription as asr
    from backend.tasks.import_processing import import_subtitle_failure
    settings = cloud_adapter.configure('qwen-audio-3.0-asr-flash', lambda request: httpx.Response(
        503, json={'error': {'message': SECRET_BODY}}, request=request))
    with pytest.raises(asr.CloudTranscriptionError) as caught:
        asr.transcribe(cloud_adapter.video, cloud_adapter.tmp_path / 'out.srt', settings)
    assert caught.value.__cause__ is None and SECRET_BODY not in str(caught.value)
    assert classify_failure(caught.value).kind is FailureKind.MODEL
    failure = import_subtitle_failure(caught.value)
    assert studio_failure_context(failure, 'production').get('http_status') == 503
"""increment (11:09): the rewrite route's checks on the model's own reply (a missing key, a
Draft that fails validation) are ModelResponseInvalid -> MODEL / invalid_response, snapshot only; neither the
HTTP response nor the Sentry payload carries the raw model text. Fails on 0b6da07a on an assertion."""

RAW = 'r29-raw-model-reply-PRIVATE'


@pytest.mark.parametrize('reply', [
    {'title': RAW},                                  # hook missing -> KeyError
    {'title': {'nested': RAW}, 'hook': RAW},         # Draft.model_validate fails (title is not a string)
    [RAW],                                           # not an object at all
], ids=['missing_key', 'fails_validation', 'not_an_object'])
def test_rewrite_route_invalid_model_reply_is_model_invalid_response_without_raw_text(client, monkeypatch, reply):
    import sentry_sdk
    from sentry_sdk.utils import event_from_exception
    draft = client.post('/studio/p1/drafts', json={'clip_ids': ['c1'], 'title': 'Original'}).json()
    monkeypatch.setattr(intelligence, 'text_json', lambda *a, **k: reply)
    monkeypatch.setattr(sentry_setup, '_initialized', True)
    monkeypatch.setattr(sentry_setup, 'crash_reports_enabled', lambda: True)
    captured = []

    def capture(exc):
        options = {**sentry_sdk.get_client().options, 'include_local_variables': False, 'include_source_context': False}
        event, _ = event_from_exception(exc, client_options=options)
        event['tags'] = dict(sentry_sdk.get_current_scope()._tags)
        raw_event = json.dumps(event, default=str)  # what the SDK builds before our scrubber
        captured.append((exc, raw_event, sentry_setup.before_send(event, {}) or event))
    monkeypatch.setattr(sentry_sdk, 'capture_exception', capture)

    response = client.post('/studio/p1/rewrite', json={'draft': draft, 'instruction': 'shorter'})
    assert response.status_code == 502, response.text
    assert RAW not in response.text
    assert len(captured) == 1
    error, raw_event, event = captured[0]
    assert RAW not in raw_event  # the raw reply is not even in the chain the SDK walks
    assert len(json.loads(raw_event)['exception']['values']) == 1
    assert classify_failure(error).kind is FailureKind.MODEL
    assert sentry_setup.studio_error_code(error) == 'invalid_response'
    assert event['tags']['error_code'] == 'invalid_response' and event['tags']['phase'] == 'rewrite'
    assert RAW not in json.dumps(event, default=str)
"""settle_generation no longer writes 'multiple' (it entered the success-rate denominator:
llm_auth_invalid + authentication became a product failure). Primary via failure_attribution."""


def _data(*codes):
    return {'output_variants': [{'status': 'failed', 'error_code': c, 'render_job_id': f'j{i}'} for i, c in enumerate(codes)],
            'jobs': [], 'generation': {}, 'analysis': {'run_id': 'r'}}


def test_265_two_user_causes_stay_a_user_cause():
    d = _data('llm_auth_invalid', 'authentication')
    store.settle_generation(d)
    assert d['generation']['error_code'] == 'llm_auth_invalid' and d['analysis']['error_code'] == 'llm_auth_invalid', d
    assert d['generation']['secondary_error_codes'] == ['authentication']


def test_265_product_cause_wins_whatever_the_order():
    for codes in (('authentication', 'timeout'), ('timeout', 'authentication')):
        d = _data(*codes)
        store.settle_generation(d)
        assert d['generation']['error_code'] == 'timeout' and d['analysis']['error_code'] == 'timeout', d
        assert d['analysis']['secondary_error_codes'] == ['authentication']
"""(review #390-#394): without a request record only a MODEL failure takes the
phase identity, everything else is local; store_lock_timeout is its own product code; a
non-blocking lock attempt returns at once; a new phase-only failure replaces an older request
attribution. Every test fails on 6e11ce73 on an assertion."""
VISION = {**GLM, 'model': 'glm-4v', 'base_url_host': 'glm.fixture.example'}
IDENTITY = ('provider', 'config_source', 'model', 'base_url_host', 'http_status')


def _fail_with(pid, error, code):
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise error
        except Exception as caught:  # noqa: BLE001
            tags = llm_emit.sentry_tags_for_error(caught, 'production')
            store.change(pid, lambda d: d['analysis'].update(status='failed', error_code=code))
    return store.read(pid)['analysis'], tags


@pytest.mark.usefixtures('isolated__r22_415')
@pytest.mark.parametrize('error', [
    file_lock.LockTimeout(),                                               # #390 store lock
    subprocess.CalledProcessError(1, ['ffmpeg']),                          # ffmpeg
    subprocess.TimeoutExpired(['ffmpeg'], 5),                              # local render timeout
    ValueError('text step rejected its input before any request'),         # mixed goals, visual route
    PipelineFailure('EXPORT', 'render produced no file', code='timeline_empty'),
], ids=['lock', 'ffmpeg', 'render-timeout', 'text-before-request', 'local-pipeline-code'])
def test_392_non_model_failure_without_record_is_local(error):
    _project__r25_415('ploc', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    analysis, tags = _fail_with('ploc', error, 'unexpected')
    assert analysis.get('attribution_source') == 'local' and analysis.get('http_status') is None, analysis
    assert tags.get('attribution_source') == 'local' and 'http_status' not in tags


@pytest.mark.usefixtures('isolated__r22_415')
def test_392_local_failure_raised_while_handling_a_model_error_is_still_local():
    _project__r25_415('pctx', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            try:
                raise PipelineFailure('ANALYZE', 'slow', code='timeout')
            except PipelineFailure:
                raise file_lock.LockTimeout()      # saving the failure hit the store lock
        except file_lock.LockTimeout:
            store.change('pctx', lambda d: d['analysis'].update(status='failed', error_code='store_lock_timeout'))
    analysis = store.read('pctx')['analysis']
    assert analysis.get('attribution_source') == 'local' and analysis.get('http_status') is None


@pytest.mark.usefixtures('isolated__r22_415')
def test_392_model_failure_without_record_still_takes_phase_identity():
    _project__r25_415('pmod', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    analysis, tags = _fail_with('pmod', PipelineFailure('ANALYZE', 'slow', code='timeout'), 'timeout')
    assert analysis.get('attribution_source') == 'phase' and analysis.get('provider') == 'glm'
    assert tags.get('provider') == 'glm' and tags.get('attribution_source') == 'phase'


@pytest.mark.usefixtures('isolated__r22_415')
def test_390_store_lock_timeout_is_its_own_product_code_not_a_model_timeout():
    error = file_lock.LockTimeout()
    assert studio_error_code(error) == 'store_lock_timeout' and 'store_lock_timeout' in STUDIO_ERROR_CODES
    assert '模型' not in str(error) and '服务商' not in str(error) and '提供商' not in str(error)
    for path in ('backend/core/event_catalog.json', 'docs/analytics/event_catalog.json'):
        attr = json.loads((ROOT / path).read_text(encoding='utf-8'))['attribution']
        assert 'store_lock_timeout' in attr['product_error_codes'], path
        assert 'store_lock_timeout' not in attr['user_caused_error_codes'] + attr['environment_error_codes']
    assert 'store_lock_timeout' in (ROOT / 'docs/analytics/TRACKING_PLAN.md').read_text(encoding='utf-8')
    from backend.core.failure_codes import error_code_pattern
    assert error_code_pattern().fullmatch('store_lock_timeout')
    for path in ('frontend/src/analytics/feedbackDraft.ts', 'frontend/src/analytics/workflow.ts'):
        assert "failureCodes" in (ROOT / path).read_text(encoding='utf-8'), path
    assert 'error_code_pattern' in (ROOT / 'scripts/ingest_app_feedback.py').read_text(encoding='utf-8')


@pytest.mark.usefixtures('isolated__r22_415')
def test_394_new_phase_only_failure_replaces_older_request_attribution():
    _project__r25_415('p394', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        try:
            _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
        except Exception:  # noqa: BLE001
            store.change('p394', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    first = store.read('p394')['analysis']
    assert first['provider'] == 'kimi' and first['attribution_source'] == 'request'
    # no "same failure" inference; without an error in hand the snapshot stays.
    store.change('p394', lambda d: d['analysis'].update(message='no error in hand'))
    assert store.read('p394')['analysis']['provider'] == 'kimi'
    # (assertion changed from 'glm'): an unrelated write of an already-failed record
    # with another error in hand is NOT a new failure: the snapshot stays (overwrote it).
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise PipelineFailure('ANALYZE', 'again', code='provider_error')
        except PipelineFailure:
            store.change('p394', lambda d: d['analysis'].update(message='still failed'))
    assert store.read('p394')['analysis']['provider'] == 'kimi'
    # a NEW failure (retry run r2) with only the phase identity: the old request value must go
    store.change('p394', lambda d: d['analysis'].update(status='running', run_id='r2', error_code=None))
    analysis, _ = _fail_with('p394', PipelineFailure('ANALYZE', 'slow', code='timeout'), 'timeout')
    assert analysis['attribution_source'] == 'phase' and analysis['provider'] == 'glm'
    assert analysis.get('http_status') != 503


# second pass (-b): #393 P2, #397-#402, #394 status, #392 source surfaces

@pytest.mark.usefixtures('isolated__r22_415')
def test_394_new_local_failure_drops_the_old_request_status():
    _project__r25_415('p394l', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        try:
            _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
        except Exception:  # noqa: BLE001
            store.change('p394l', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    with llm_emit.track_run():  # the next run fails locally straight away (no running write between)
        try:
            raise file_lock.LockTimeout()
        except file_lock.LockTimeout:
            store.change('p394l', lambda d: d['analysis'].update(status='failed', run_id='r2', error_code='store_lock_timeout'))
    analysis = store.read('p394l')['analysis']
    assert analysis['attribution_source'] == 'local' and analysis.get('http_status') is None


@pytest.mark.usefixtures('isolated__r22_415')
def test_397_failed_goal_request_survives_a_later_successful_goal(monkeypatch):
    from backend.services.studio import intelligence, jobs
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda *a, **k: Path('video.mp4'))
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(jobs, 'analyze', lambda *a, **k: _call(GLM, 'https://glm.fixture.example/v1', 'glm-4v', status=503))
    monkeypatch.setattr(jobs, 'run_content', lambda *a, **k: (_call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2'), [])[1])
    _project__r25_415('p397', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    plan = {'selected_goals': ['highlight', 'content'], 'confirmed_preferences': {}, 'confirmed_analysis': 'visual'}
    with llm_emit.track_run():
        jobs._produce_selected('p397', plan)
    analysis = store.read('p397')['analysis']
    assert analysis['status'] == 'failed' and analysis['succeeded_goals'] == ['content']
    assert (analysis.get('provider'), analysis.get('http_status')) == ('glm', 503), analysis
    assert analysis.get('attribution_source') == 'request'


@pytest.mark.usefixtures('isolated__r22_415')
def test_398_r29_i500_record_on_the_implicit_context_only_is_not_this_failures():
    """: only the explicit __cause__ chain is walked; a record that is only on the
implicit __context__ belongs to an error that was merely being handled."""
    with llm_emit.track_run():
        try:
            _call(GLM, 'https://glm.fixture.example/v1', 'glm-4', status=503)
        except Exception as failed:  # noqa: BLE001
            try:
                raise RuntimeError('cleanup') from ValueError('unrelated cause')   # cause set, record on context
            except RuntimeError as outer:
                assert outer.__context__ is failed
                found = llm_emit.attribution(outer)
    assert found.get('provider') != 'glm' and found.get('attribution_source') == 'local', found


@pytest.mark.usefixtures('isolated__r22_415')
def test_399_half_identity_is_empty_on_read():
    store.directory('p399').mkdir(parents=True, exist_ok=True)
    path = store.directory('p399') / 'metadata' / 'studio.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'id': 'p399', 'analysis': {'status': 'completed', 'provider': 'kimi', 'model': 'kimi-k2'},
                                'generation': {'status': 'completed', 'config_source': 'preset'}}), encoding='utf-8')
    data = store.read('p399')
    for name in ('analysis', 'generation'):
        assert not any(data[name].get(k) for k in ('provider', 'config_source', 'model', 'base_url_host')), data[name]


@pytest.mark.usefixtures('isolated__r22_415')
def test_400_history_keeps_model_host_and_source():
    _project__r25_415('p400', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    with llm_emit.track_run():
        try:
            _call(GLM, 'https://glm.fixture.example/v1', 'glm-4', status=503)
        except Exception:  # noqa: BLE001
            store.change('p400', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    row = store.read('p400')['analysis_history'][-1]['analysis']
    assert (row.get('model'), row.get('base_url_host'), row.get('attribution_source')) == ('glm-4', 'glm.fixture.example', 'request')


@pytest.mark.usefixtures('isolated__r22_415')
def test_401_render_that_cannot_write_its_failure_leaves_a_receipt_not_a_queued_job(monkeypatch):
    from backend.services.studio import jobs
    store.directory('p401').mkdir(parents=True, exist_ok=True)
    store.write('p401', {'id': 'p401', 'jobs': [{'job_id': 'j1', 'status': 'queued', 'instance': store.INSTANCE}]})
    real_change = store.change
    monkeypatch.setattr(store, 'change', lambda *a, **k: (_ for _ in ()).throw(file_lock.LockTimeout()))
    with pytest.raises(file_lock.LockTimeout):
        with store.worker_read_scope('p401', ('render', 'j1')):
            jobs._render.__wrapped__('p401', {'id': 'd'}, 'j1') if hasattr(jobs._render, '__wrapped__') else jobs._render('p401', {'id': 'd'}, 'j1')
    monkeypatch.setattr(store, 'change', real_change)
    job = store.recover('p401')['jobs'][0]
    assert job['status'] == 'failed' and job['error_code'] == 'store_lock_timeout', job


@pytest.mark.usefixtures('isolated__r22_415')
def test_402_attribution_does_not_need_python_311():
    source = (ROOT / 'backend/core/llm_emit.py').read_text(encoding='utf-8')
    assert 'sys.exception()' not in source
    with llm_emit.track_run():
        try:
            _call(GLM, 'https://glm.fixture.example/v1', 'glm-4', status=503)
        except Exception:  # noqa: BLE001
            assert llm_emit.attribution().get('provider') == 'glm'
"""(design, 157/415-attribution-design.md): one classifier, one write-once snapshot,
one reader.,, + design points. Each test fails on 49575864 on an assertion
(module-not-found aside: the failure_attribution tests also pin the rule's behaviour through llm_emit/store)."""


def _kimi_503():
    try:
        _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
    except Exception as error:  # noqa: BLE001
        return error
    raise AssertionError('no 503')


# decision order local -> model -> request record

@pytest.mark.usefixtures('isolated__r22_415')
def test_i415_lock_timeout_raised_while_handling_a_model_503_is_local():
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        inner = _kimi_503()
        try:
            try:
                raise inner
            except Exception:  # noqa: BLE001
                raise file_lock.LockTimeout()
        except file_lock.LockTimeout as outer:
            found = llm_emit.attribution(outer)
    assert found['attribution_source'] == 'local', found
    assert 'http_status' not in found and 'upstream_error_type' not in found
    assert found.get('provider') != 'kimi'


@pytest.mark.usefixtures('isolated__r22_415')
def test_i415_classify_failure_order_and_request_record():
    from backend.core.failure_attribution import FailureKind, classify_failure
    with llm_emit.track_run():
        error = _kimi_503()
        verdict = classify_failure(error)
        assert verdict.kind is FailureKind.MODEL and verdict.record is not None
        wrapped = PipelineFailure('INGEST', 'site', code='source_blocked')
        wrapped.__cause__ = error
        assert classify_failure(wrapped).kind is FailureKind.LOCAL  # decisive local link outside wins
        assert classify_failure(wrapped).record is None
    assert classify_failure(None).kind is FailureKind.NONE
    assert classify_failure(ValueError('x')).kind is FailureKind.LOCAL
    assert classify_failure(PipelineFailure('ANALYZE', 'x', code='timeout')).kind is FailureKind.MODEL


@pytest.mark.usefixtures('isolated__r22_415')
def test_i416_no_type_name_strings_and_one_classifier():
    class PipelineFailure2(Exception):
        code = 'timeout'
    PipelineFailure2.__name__ = 'PipelineFailure'  # a look-alike by name is not a model error
    assert llm_emit.is_model_error(PipelineFailure2()) is False


@pytest.mark.usefixtures('isolated__r22_415')
def test_i416_studio_failure_context_gives_a_lock_timeout_no_inner_upstream():
    from backend.core.sentry_setup import studio_failure_context
    with llm_emit.track_run():
        inner = _kimi_503()
    outer = file_lock.LockTimeout()
    outer.__context__ = inner
    context = studio_failure_context(outer, 'production')
    assert 'upstream_error_type' not in context, context


# --- snapshot: write once, whole, local without http/upstream ------------------------------------------

@pytest.mark.usefixtures('isolated__r22_415')
def test_snapshot_local_with_upstream_fields_raises_explicitly():
    from backend.core.failure_attribution import FailureAttribution
    with pytest.raises(ValueError):
        FailureAttribution('local', provider='glm', config_source='customized', http_status=503)
    with pytest.raises(ValueError):
        FailureAttribution('local', upstream_error_type='upstream_unavailable')
    with pytest.raises(ValueError):
        FailureAttribution('phase', provider='glm')  # half identity
    built = FailureAttribution._make('local', {**GLM, 'model': 'glm-4'}, http_status=503, upstream_error_type='x')
    assert 'http_status' not in built.to_fields() and built.to_fields()['attribution_source'] == 'local'


@pytest.mark.usefixtures('isolated__r22_415')
def test_write_attribution_replaces_the_group_whole():
    from backend.core.failure_attribution import FailureAttribution, write_attribution
    record = {'status': 'failed', **KIMI, 'model': 'kimi-k2', 'http_status': 503,
              'upstream_error_type': 'upstream_unavailable', 'attribution_source': 'request', 'error_code': 'x'}
    write_attribution(record, FailureAttribution._make('phase', {**GLM}, failure_stage='analyze'))
    assert record == {'status': 'failed', 'error_code': 'x', **GLM, 'failure_stage': 'analyze',
                      'attribution_source': 'phase'}


# a new phase failure keeps nothing of an older request's status

@pytest.mark.usefixtures('isolated__r22_415')
def test_i417_new_phase_failure_drops_the_older_request_status():
    _project__r25_415('p417', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        error = _kimi_503()
        try:
            raise error
        except Exception:  # noqa: BLE001
            store.change('p417', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    assert store.read('p417')['analysis']['attribution_source'] == 'request'
    store.change('p417', lambda d: d['analysis'].update(status='running'))  # the retry starts (a real transition)
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise PipelineFailure('ANALYZE', 'slow', code='timeout')
        except PipelineFailure:
            store.change('p417', lambda d: d['analysis'].update(status='failed', error_code='timeout'))
    analysis = store.read('p417')['analysis']
    assert analysis['attribution_source'] == 'phase' and analysis['provider'] == 'glm'
    assert 'http_status' not in analysis and 'upstream_error_type' not in analysis, analysis


# lock-timeout receipt recovery writes local

@pytest.mark.usefixtures('isolated__r22_415')
def test_i418_receipt_recovery_writes_a_local_snapshot():
    _project__r25_415('p418', {'status': 'running', 'phase': 'production', 'run_id': 'r1', **GLM, 'model': 'glm-4',
                      'http_status': 503})
    path = store.directory('p418') / 'metadata' / 'studio.json'
    store._append_receipt(path, {'identity': ('analysis', 'r1', 'production'), 'pending': {},
                                 'message': file_lock.LOCK_TIMEOUT_MESSAGE, 'error_code': file_lock.LOCK_TIMEOUT_CODE})
    analysis = store.recover('p418')['analysis']
    assert analysis['status'] == 'failed' and analysis['error_code'] == 'store_lock_timeout'
    assert analysis['attribution_source'] == 'local' and analysis['provider'] == 'glm'
    assert 'http_status' not in analysis
    on_disk = json.loads(path.read_text(encoding='utf-8'))['analysis']
    assert on_disk['attribution_source'] == 'local'


# read-time cleanup, never written back

def _raw(pid, data):
    root = store.directory(pid) / 'metadata'
    root.mkdir(parents=True, exist_ok=True)
    (root / 'studio.json').write_text(json.dumps({'id': pid, **data}), encoding='utf-8')
    return root / 'studio.json'


@pytest.mark.usefixtures('isolated__r22_415')
def test_i421_history_half_identity_and_local_status_are_cleaned_on_read_only():
    legacy = {'run_id': 'r0', 'analysis': {'run_id': 'r0', 'status': 'failed', 'provider': 'kimi',
                                           'http_status': 503, 'attribution_source': 'local'}}
    path = _raw('p421', {'analysis': {'status': 'failed', 'run_id': 'r1', 'provider': 'glm',
                                      'attribution_source': 'local', 'upstream_error_type': 'invalid_key'},
                         'analysis_history': [legacy]})
    before = path.read_text(encoding='utf-8')
    state = store.read('p421')
    row = state['analysis_history'][0]['analysis']
    assert 'provider' not in row and 'http_status' not in row and row['attribution_source'] == 'local'
    assert 'provider' not in state['analysis'] and 'upstream_error_type' not in state['analysis']
    assert path.read_text(encoding='utf-8') == before, 'the read wrote the cleanup back'


@pytest.mark.usefixtures('isolated__r22_415')
def test_history_summary_comes_from_read_attribution():
    _project__r25_415('ph', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise file_lock.LockTimeout()
        except file_lock.LockTimeout:
            store.change('ph', lambda d: d['analysis'].update(status='failed', error_code='store_lock_timeout',
                                                              http_status=503))
    summary = store.read('ph')['analysis_history'][-1]['analysis']
    assert summary['attribution_source'] == 'local' and 'http_status' not in summary

SNAPSHOT = {'provider', 'config_source', 'model', 'base_url_host', 'http_status', 'upstream_error_type',
            'failure_stage', 'attribution_source'}
# Functions that read these names but are NOT readers of a failure-attribution snapshot, each with why.
# (Exempt by location, never by variable name.)
NOT_SNAPSHOT_READERS = {
    ('backend/core/llm_emit.py', '_remember_run'): 'builds the request record from the request event',
    ('backend/core/llm_emit.py', '_request_properties'): 'builds the llm_request_finished event',
    ('backend/core/llm_emit.py', 'request_finished'): 'request event context',
    ('backend/core/llm_emit.py', 'emit_vision_request'): 'request event context',
    ('backend/core/llm_emit.py', 'emit_asr_readiness_checked'): 'asr probe event',
    ('backend/core/llm_emit.py', 'sent_vision_identity'): 'vision settings -> sent identity',
    ('backend/core/llm_emit.py', '_provider_label'): 'provider object label',
    ('backend/core/llm_emit.py', 'run_snapshot'): 'sanitized pair check on the already built snapshot fields',
    ('backend/core/llm_emit.py', 'sentry_tags_for_error'): 'R31 I565: reads the output of export_attribution only',
    ('backend/core/sentry_setup.py', 'before_send'): 'Sentry tag sanitizer on outgoing tags',
    ('backend/services/studio/intelligence.py', 'vision_call'): 'vision settings model',
    ('backend/services/studio/intelligence.py', 'visual_config'): 'vision settings model',
    ('backend/services/studio/jobs.py', 'run_content'): "the adapter result's HTTP status -> PipelineFailure",
    ('backend/services/studio/jobs.py', '_produce_selected'): 'ranks multi-goal causes; does not assemble a snapshot',
    ('backend/services/studio/attempts.py', '_cause'): 'copies a settled cause onto the attempt receipt',
    ('backend/services/studio/attempts.py', 'settle'): 'writes the ranked cause onto the attempt receipt',
    ('backend/services/studio/attempts.py', '_terminal_event'): 'copies fields already stored on the settled receipt',
    ('backend/services/studio/store.py', 'settle_attempt'): 'writes the caller failure_stage onto the one terminal record',
    ('backend/services/studio/store.py', 'settle_generation'): 'ranks variant failures for the generation cause',
    ('backend/services/studio/store.py', '_ensure_failure_identity'): "normalizes the job's own error_code/stage",
    ('backend/services/studio/store.py', 'fill'): "normalizes the job's own error_code/stage",
    ('backend/services/studio/vision_settings.py', '*'): 'vision settings',
    ('backend/api/v1/settings.py', 'get_settings'): 'model settings page',
    ('backend/api/v1/settings.py', 'get_current_provider'): 'model settings page',
}


def _py_reads(path):
    rel = str(path.relative_to(ROOT))
    out = []
    for fn in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if (rel, fn.name) in NOT_SNAPSHOT_READERS or (rel, '*') in NOT_SNAPSHOT_READERS:
            continue
        for node in ast.walk(fn):
            key = None
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'get'
                    and node.args and isinstance(node.args[0], ast.Constant)):
                key = node.args[0].value
            elif (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load)
                  and isinstance(node.slice, ast.Constant)):
                key = node.slice.value
            if key in SNAPSHOT:
                out.append(f'{rel}:{node.lineno} {fn.name}: {key}')
    return sorted(set(out))


TS_EXEMPT = ('export function pickAttribution(', 'export function isFailedTerminal(',
             'export function safeStudioProperties(', 'export function screeningIdentity(',
             'export function receiptEventCauses(',              'export function pageFailureAction(',
             'export function analysisPageFailure(',
             'export function pageFailureText(',
             'export function presentedFailure(',
             'export function readableFailure(',
             'export function failureStep(')
_TS_READ = re.compile(r"""(\.\s*|\[\s*['"])(attribution_source|upstream_error_type|http_status|failure_stage|provider|config_source|base_url_host)\b(?!\s*[?]?:)""")


def _ts_reads(path):
    text = path.read_text(encoding='utf-8')
    for marker in TS_EXEMPT:
        if marker in text:
            start = text.index(marker)
            end = text.index('\n}\n', start)
            text = text[:start] + '\n' * text[start:end].count('\n') + text[end:]
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        code = line.split('//')[0]
        if code.lstrip().startswith(('*', '/*')):
            continue  # doc comments
        if re.match(r'\s*(type |export type |\w+\?: \{|  (analysis|generation)\?:)', code):
            continue  # type declarations
        if re.match(r'\s*(export )?const [A-Z_]+ = ', code):
            continue  # a key-list constant (ATTRIBUTION_KEYS) names keys, it reads no record
        if _TS_READ.search(code):
            out.append(f'{path.relative_to(ROOT)}:{no}: {line.strip()}')
    return out


@pytest.mark.usefixtures('isolated__r22_415')
def test_grep_no_attribution_reads_outside_the_one_reader():
    offenders = []
    for path in [*(ROOT / 'backend/services/studio').glob('*.py'), ROOT / 'backend/core/llm_emit.py',
                 ROOT / 'backend/core/sentry_setup.py', *(ROOT / 'backend/api').rglob('*.py')]:
        offenders += _py_reads(path)
    for path in [ROOT / 'frontend/src/analytics/workflow.ts', *(ROOT / 'frontend/src/features/studio').rglob('*.ts*')]:
        offenders += _ts_reads(path)
    assert offenders == [], '\n'.join(offenders)


@pytest.mark.usefixtures('isolated__r22_415')
def test_grep_guard_catches_direct_reads_of_every_field(tmp_path):
    probe = ROOT / 'backend/services/studio/_guard_probe_tmp.py'
    probe.write_text("def f(snapshot, found, record):\n    a = snapshot.get('http_status')\n"
                     "    b = found.get('attribution_source')\n    c = record.get('failure_stage')\n"
                     "    d = record['provider']\n    record['model'] = 1\n", encoding='utf-8')
    try:
        hits = _py_reads(probe)
    finally:
        probe.unlink()
    assert [h.rsplit(': ', 1)[1] for h in hits] == ['http_status', 'attribution_source', 'failure_stage', 'provider']
    assert _TS_READ.search('snapshot.analysis?.upstream_error_type')
    assert _TS_READ.search("run['failure_stage']")
    assert not _TS_READ.search('failure_stage?: string')



@pytest.mark.usefixtures('isolated__r22_415')
def test_i422_release_validation_splits_by_attribution_source():
    sql = (ROOT / 'docs/analytics/release_validation.sql').read_text(encoding='utf-8')
    block = sql[sql.index('1.5.7 成功率埋点'):sql.index('ORDER BY event, events DESC;')]
    assert 'properties.attribution_source AS attribution_source' in block
    assert "if(toString(properties.attribution_source) = 'local', NULL, properties.provider)" in block
    assert 'GROUP BY event, attribution_source, provider' in block


LOCALES = ('zh', 'en', 'ja', 'ko', 'es', 'fr', 'pt', 'ru')


@pytest.mark.usefixtures('isolated__r22_415')
def test_i424_lock_timeout_notice_in_all_8_locales():
    key = file_lock.LOCK_TIMEOUT_MESSAGE
    for lang in LOCALES:
        data = json.loads((ROOT / f'frontend/src/i18n/locales/{lang}.json').read_text(encoding='utf-8'))
        value = data.get(key)
        assert isinstance(value, str) and value.strip(), lang
        if lang != 'zh':
            assert value != key and '进程' not in value and '原素材已保留' not in value, lang  # translated, not the Chinese
    ts = (ROOT / 'frontend/src/utils/llmFailure.ts').read_text(encoding='utf-8')
    assert key in ts and "STORE_LOCK_TIMEOUT = 'store_lock_timeout'" in ts


@pytest.mark.usefixtures('isolated__r22_415')
def test_i415_a_non_decisive_wrapper_is_looked_through():
    """The walk goes INWARD past non-decisive links (unexpected/OSError) to the model failure."""
    from backend.core.failure_attribution import FailureKind, classify_failure
    with llm_emit.track_run():
        inner = _kimi_503()
    wrapper = PipelineFailure('ANALYZE', 'x', code='unexpected')
    wrapper.__cause__ = OSError('socket')
    wrapper.__cause__.__cause__ = inner
    verdict = classify_failure(wrapper)
    assert verdict.kind is FailureKind.MODEL and verdict.record is not None
    # a local error in ANY layer is judged first, even under a model-coded wrapper
    outer = PipelineFailure('ANALYZE', 'x', code='provider_error')
    outer.__cause__ = subprocess.CalledProcessError(1, ['ffmpeg'])
    assert classify_failure(outer).kind is FailureKind.LOCAL
""": model only when a request was sent and the provider answered with
an error; a local error in any layer first; one snapshot factory; no value inference; one-record readers;
completed+partial is a failure terminal; render receipts are local. Fail-before evidence: before-*.txt in
mut415-r28 (run against 9ce045c2)."""


def _attr(error):
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        return llm_emit.attribution(error)


class _NotAProvider(Exception):
    """Some library error that happens to carry an HTTP status (e.g. a 404 from a download)."""
    def __init__(self, status):
        super().__init__('fixture')
        self.status_code = status


# no "status code or record means model" fallback; local in any layer first

@pytest.mark.usefixtures('isolated__r22_415')
def test_i450_status_code_alone_is_not_a_model_failure():  # kills M1
    wrapped = PipelineFailure('ANALYZE', 'x', code='unexpected')
    wrapped.__cause__ = _NotAProvider(404)
    assert _attr(wrapped)['attribution_source'] == 'local'
    assert _attr(PipelineFailure('ANALYZE', 'x', code='unexpected', http_status=502))['attribution_source'] == 'local'


@pytest.mark.usefixtures('isolated__r22_415')
@pytest.mark.parametrize('local', [OSError(errno.ENOSPC, 'disk full'), PermissionError('denied'),
                                   FileNotFoundError('gone')], ids=['enospc', 'permission', 'not-found'])
def test_i450_local_error_raised_while_handling_a_model_503_is_local(local):
    with llm_emit.track_run():
        inner = _kimi_503()
        try:
            try:
                raise inner
            except Exception:  # noqa: BLE001
                raise local
        except OSError as outer:
            llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
            found = llm_emit.attribution(outer)
    assert found['attribution_source'] == 'local' and found.get('provider') != 'kimi', found
    assert 'http_status' not in found


@pytest.mark.usefixtures('isolated__r22_415')
def test_i450_request_record_without_a_provider_answer_is_local():
    """A PermissionError inside the provider call before any network I/O gets a request record too."""
    def impl(*_a, **_k):
        raise PermissionError('fixture: cannot read the prompt file')
    with llm_emit.track_run():
        try:
            with llm_emit.bind_context(identity=KIMI):
                llm_emit.observe_provider_call(_provider('https://kimi.fixture.example/v1', 'kimi-k2'), impl, 'p')
        except PermissionError as error:
            found = llm_emit.attribution(error)
    assert found['attribution_source'] == 'local' and found.get('provider') != 'kimi', found


@pytest.mark.usefixtures('isolated__r22_415')
def test_i450_answered_request_stays_model():
    with llm_emit.track_run():
        error = _kimi_503()
        found = llm_emit.attribution(error)
    assert found['attribution_source'] == 'request' and found['provider'] == 'kimi' and found['http_status'] == 503


# the chain skips layers that cannot decide (behaviour, through llm_emit)

@pytest.mark.usefixtures('isolated__r22_415')
def test_i460_walk_passes_non_deciding_layers_to_the_model_failure():
    inner = PipelineFailure('ANALYZE', 'slow', code='timeout')
    middle = RuntimeError('wrapped')
    middle.__cause__ = inner
    outer = PipelineFailure('ANALYZE', 'x', code='unexpected')
    outer.__cause__ = middle
    found = _attr(outer)
    assert found['attribution_source'] == 'phase' and found['provider'] == 'glm', found


@pytest.mark.usefixtures('isolated__r22_415')
def test_i460_store_lock_timeout_code_is_local_even_over_a_model_failure():  # kills M5
    outer = PipelineFailure('ANALYZE', 'lock', code='store_lock_timeout')
    outer.__cause__ = PipelineFailure('ANALYZE', 'slow', code='timeout')
    assert _attr(outer)['attribution_source'] == 'local'


@pytest.mark.usefixtures('isolated__r22_415')
def test_i460_record_without_status_keeps_its_failure_fields():  # kills M3
    from backend.core.failure_attribution import read_attribution
    row = {'attribution_source': 'phase', **GLM, 'http_status': 503, 'failure_stage': 'analyze'}
    assert read_attribution(row)['http_status'] == 503 and read_attribution(row)['failure_stage'] == 'analyze'


# completed + outcome=partial keeps its failure fields through read -> unrelated save

@pytest.mark.usefixtures('isolated__r22_415')
def test_i451_partial_survives_read_and_an_unrelated_save():
    partial = {'status': 'completed', 'outcome': 'partial', 'phase': 'rendering', 'run_id': 'r1', **GLM,
               'attribution_source': 'phase', 'failure_stage': 'render', 'http_status': 503,
               'upstream_error_type': 'upstream_unavailable', 'error_code': 'provider_error'}
    root = store.directory('p451') / 'metadata'
    root.mkdir(parents=True, exist_ok=True)
    (root / 'studio.json').write_text(json.dumps({'id': 'p451', 'analysis': partial, 'analysis_history': [
        {'run_id': 'r0', 'analysis': {**partial, 'run_id': 'r0'}}]}), encoding='utf-8')
    assert store.read('p451')['analysis']['failure_stage'] == 'render'
    store.change('p451', lambda d: d['jobs'].append({'job_id': 'j', 'status': 'completed'}))
    state = store.read('p451')
    for row in (state['analysis'], state['analysis_history'][0]['analysis']):
        assert row['failure_stage'] == 'render' and row['http_status'] == 503, row


# no inference from equal values; wholesale replacement only

@pytest.mark.usefixtures('isolated__r22_415')
def test_i452_a_new_phase_failure_keeps_its_own_503_after_an_old_kimi_503():
    _project__r25_415('p452', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        error = _kimi_503()
        try:
            raise error
        except Exception:  # noqa: BLE001
            store.change('p452', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    store.change('p452', lambda d: d['analysis'].update(status='running'))  # the retry starts (a real transition)
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise PipelineFailure('ANALYZE', 'glm down', code='rate_limited', http_status=503)
        except PipelineFailure:
            store.change('p452', lambda d: d['analysis'].update(status='failed', error_code='rate_limited'))
    analysis = store.read('p452')['analysis']
    assert analysis['provider'] == 'glm' and analysis['attribution_source'] == 'phase'
    assert analysis['http_status'] == 503, analysis


@pytest.mark.usefixtures('isolated__r22_415')
def test_i452_old_phase_503_is_replaced_by_a_new_failure_without_status():
    _project__r25_415('p452b', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise PipelineFailure('ANALYZE', 'glm 503', code='provider_error', http_status=503)
        except PipelineFailure:
            store.change('p452b', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
        assert store.read('p452b')['analysis']['http_status'] == 503
        store.change('p452b', lambda d: d['analysis'].update(status='running'))  # the retry starts (a real transition)
        try:
            raise PipelineFailure('ANALYZE', 'slow', code='timeout')
        except PipelineFailure:
            store.change('p452b', lambda d: d['analysis'].update(status='failed', error_code='timeout'))
    analysis = store.read('p452b')['analysis']
    assert 'http_status' not in analysis and 'upstream_error_type' not in analysis, analysis


# a render receipt is a local failure of the generation

@pytest.mark.usefixtures('isolated__r22_415')
def test_i454_render_lock_timeout_receipt_writes_local_on_the_generation():
    store.directory('p454').mkdir(parents=True, exist_ok=True)
    store.write('p454', {'id': 'p454', 'generation': {'status': 'rendering', **GLM, 'model': 'glm-4'},
                         'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'r1', 'instance': store.INSTANCE, **GLM},
                         'jobs': [{'job_id': 'j1', 'status': 'running', 'instance': store.INSTANCE}],
                         'output_variants': [{'id': 'v1', 'status': 'running', 'render_job_id': 'j1'}]})
    path = store.directory('p454') / 'metadata' / 'studio.json'
    store._append_receipt(path, {'identity': ('render', 'j1'), 'pending': {},
                                 'message': file_lock.LOCK_TIMEOUT_MESSAGE, 'error_code': file_lock.LOCK_TIMEOUT_CODE})
    state = store.recover('p454')
    generation = state['generation']
    assert generation['status'] == 'failed' and generation['error_code'] == 'store_lock_timeout'
    assert generation['attribution_source'] == 'local' and generation['provider'] == 'glm', generation
    assert state['analysis']['attribution_source'] == 'local'



@pytest.mark.usefixtures('isolated__r22_415')
def test_i455_local_context_has_no_http_status_either():
    with llm_emit.track_run():
        inner = _kimi_503()
    outer = file_lock.LockTimeout()
    outer.__context__ = inner
    context = studio_failure_context(outer, 'production')
    assert 'http_status' not in context and 'upstream_error_type' not in context, context


@pytest.mark.usefixtures('isolated__r22_415')
def test_i457_no_unreachable_code_after_the_return():
    import ast
    import inspect
    from backend.core import sentry_setup
    fn = ast.parse(inspect.getsource(sentry_setup.studio_failure_context)).body[0]
    assert isinstance(fn.body[-1], ast.Return), 'statements after the final return'
    assert 'classify_run_upstream' not in inspect.getsource(sentry_setup.studio_failure_context)


@pytest.mark.usefixtures('isolated__r22_415')
def test_i458_release_validation_comment_says_local_is_not_responsibility():
    sql = (ROOT / 'docs/analytics/release_validation.sql').read_text(encoding='utf-8')
    assert 'local = 产品原因' not in sql
    assert 'local = 非模型归因，统计责任仍按错误码判断' in sql


# --- design: one factory --------------------------------------------------------------------------------

@pytest.mark.usefixtures('isolated__r22_415')
def test_one_snapshot_factory():
    for path in ('backend/core/llm_emit.py', 'backend/core/sentry_setup.py', 'backend/services/studio/store.py'):
        text = (ROOT / path).read_text(encoding='utf-8')
        assert 'FailureAttribution(' not in text and 'FailureAttribution._make' not in text and '.build(' not in text, path
    assert 'build_attribution' in (ROOT / 'backend/core/sentry_setup.py').read_text(encoding='utf-8')
    assert 'build_attribution' in (ROOT / 'backend/core/llm_emit.py').read_text(encoding='utf-8')
    assert 'build_attribution' in (ROOT / 'backend/services/studio/store.py').read_text(encoding='utf-8')


@pytest.mark.usefixtures('isolated__r22_415')
def test_i450_record_of_a_request_that_got_no_answer_is_not_a_model_failure():
    """Not a local error type either: a plain RuntimeError raised inside the call (no status, no SDK error)."""
    def impl(*_a, **_k):
        raise RuntimeError('fixture: client bug before the answer')
    with llm_emit.track_run():
        try:
            with llm_emit.bind_context(identity=KIMI):
                llm_emit.observe_provider_call(_provider('https://kimi.fixture.example/v1', 'kimi-k2'), impl, 'p')
        except RuntimeError as error:
            found = llm_emit.attribution(error)
    assert found['attribution_source'] == 'local' and found.get('provider') != 'kimi', found


@pytest.mark.usefixtures('isolated__r22_415')
def test_factory_local_names_the_phase_identity_before_the_start_identity():
    from backend.core.failure_attribution import build_attribution
    snap = build_attribution(PermissionError('fixture'), phase_identity=GLM, start_identity=KIMI)
    assert (snap.attribution_source, snap.provider, snap.http_status) == ('local', GLM['provider'], None)
"""The redaction-boundary decision: the layer closest to the provider call,
where the exception chain is still intact, builds the attribution snapshot ONCE; dicts, threads, store
writes and events carry it unchanged. Every test here fails on 9ce045c2 on an assertion, or is proven by a
mutation (157/mut415-r29). Nothing here imports a symbol that only exists on the fixed side."""
SECRET_URL = 'https://kimi.fixture.example/v1/chat?api_key=sk-r29-SECRET-0000'
SECRET_BODY__r29_415 = 'r29-private-provider-body'


class ProviderError(openai.APIStatusError):
    """The SDK's status error (constructed without a live response)."""
    def __init__(self, message, status_code):
        Exception.__init__(self, message)
        self.status_code = status_code


def _status_error(status, message=f'Error code: 503 {SECRET_URL} {SECRET_BODY__r29_415}'):
    return ProviderError(message, status)


def _connection_error():
    import httpx
    return openai.APIConnectionError(message=f'Connection error. {SECRET_URL}', request=httpx.Request('POST', SECRET_URL))


def _timeout_error():
    import httpx
    return openai.APITimeoutError(request=httpx.Request('POST', SECRET_URL))


def _attr__r29_415(error, phase=GLM):
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: phase, **phase})
        return llm_emit.attribution(error)


# the adapter builds the snapshot; it crosses apply.get whole

def _wrapped(outer, inner):
    try:
        try:
            raise inner
        except BaseException as cause:
            raise outer from cause
    except BaseException as error:  # noqa: BLE001
        return error


@pytest.mark.usefixtures('isolated__r22_415')
def test_i501_uncoded_wrapper_over_a_provider_503_stays_model_across_run_content(pipeline, monkeypatch):
    """probe P2 ①: PipelineFailure('unexpected') from APIStatusError(503) was rebuilt as LOCAL."""
    from backend.services.studio import jobs
    mod, video = pipeline
    _outline_raises(mod, monkeypatch, _wrapped(PipelineFailure('ANALYZE', '大纲失败', code='unexpected'), _status_error(503)))
    with pytest.raises(PipelineFailure) as raised:
        jobs.run_content('p', video)
    assert classify_failure(raised.value).kind is FailureKind.MODEL
    assert studio_failure_context(raised.value, 'production').get('http_status') == 503


@pytest.mark.usefixtures('isolated__r22_415')
def test_i501_provider_error_code_over_a_local_permission_error_stays_local(pipeline, monkeypatch):
    """②: the adapter judged LOCAL on the live chain; the rebuilt error must not become MODEL."""
    from backend.services.studio import jobs
    mod, video = pipeline
    _outline_raises(mod, monkeypatch, _wrapped(PipelineFailure('ANALYZE', '写缓存失败', code='provider_error'), PermissionError(13, 'fixture')))
    with pytest.raises(PipelineFailure) as raised:
        jobs.run_content('p', video)
    assert classify_failure(raised.value).kind is FailureKind.LOCAL
    assert 'http_status' not in studio_failure_context(raised.value, 'production')


@pytest.mark.usefixtures('isolated__r22_415')
def test_i501_the_failing_requests_record_crosses_the_bridge(pipeline, monkeypatch):
    """③: Kimi's 503 record must not be swapped for GLM's phase identity after apply().get()."""
    from backend.services.studio import jobs
    mod, video = pipeline

    def outline(*_a, **_k):
        try:
            _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
        except Exception as error:  # noqa: BLE001
            raise PipelineFailure('ANALYZE', '大纲失败', code='') from error
    monkeypatch.setattr(mod, 'run_step1_outline', outline)
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: GLM, **GLM})
        with pytest.raises(PipelineFailure) as raised:
            jobs.run_content('p', video)
        found = llm_emit.attribution(raised.value)
    assert (found.get('attribution_source'), found.get('provider'), found.get('http_status')) == ('request', 'kimi', 503), found


@pytest.mark.usefixtures('isolated__r22_415')
def test_i501_restored_non_model_code_wrapping_a_503_is_model(pipeline, monkeypatch):
    """Restored (deleted it): a non-model code (llm_connection) over the SDK's 503 keeps model + 503."""
    from backend.services.studio import jobs
    mod, video = pipeline
    failure = PipelineFailure('ANALYZE', '无法连接模型服务。', code='llm_connection')
    failure.__cause__ = ProviderError('boom', 503)
    _outline_raises(mod, monkeypatch, failure)
    with pytest.raises(PipelineFailure) as raised:
        jobs.run_content('p', video)
    assert (raised.value.code, raised.value.http_status) == ('llm_connection', 503)
    assert classify_failure(raised.value).kind is FailureKind.MODEL
    assert studio_failure_context(raised.value, 'production') == {
        'failure_stage': 'analyze', 'http_status': 503, 'upstream_error_type': 'upstream_unavailable'}


@pytest.mark.usefixtures('isolated__r22_415')
def test_i501_no_model_failure_boolean_and_no_rebuild_in_run_content():
    adapter = (ROOT / 'backend/services/simple_pipeline_adapter.py').read_text(encoding='utf-8')
    jobs = (ROOT / 'backend/services/studio/jobs.py').read_text(encoding='utf-8')
    assert 'model_failure' not in adapter and 'model_failure' not in jobs
    assert "'provider_error' if" not in jobs


# only the explicit __cause__ chain

@pytest.mark.usefixtures('isolated__r22_415')
def test_i500_a_503_sent_while_handling_a_cache_miss_is_model():
    try:
        try:
            raise FileNotFoundError('cache miss')
        except FileNotFoundError:
            _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
    except Exception as error:  # noqa: BLE001
        assert isinstance(error.__context__, FileNotFoundError)
        verdict = classify_failure(error)
        found = _attr__r29_415(error)
    assert verdict.kind is FailureKind.MODEL
    assert (found.get('attribution_source'), found.get('provider'), found.get('http_status')) == ('request', 'kimi', 503)


@pytest.mark.usefixtures('isolated__r22_415')
def test_i500_an_explicit_local_cause_still_wins():
    error = _wrapped(RuntimeError('wrapper'), PermissionError(13, 'fixture'))
    assert classify_failure(error).kind is FailureKind.LOCAL


# no "same failure" inference in the store

@pytest.mark.usefixtures('isolated__r22_415')
def test_i503_a_new_local_error_in_the_same_run_with_the_same_code_replaces_the_old_503():
    _project__r25_415('p503', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        try:
            _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
        except Exception:  # noqa: BLE001
            store.change('p503', lambda d: d['analysis'].update(status='failed', error_code='unexpected'))
        assert store.read('p503')['analysis'].get('http_status') == 503
        # the retry of the same run starts (a real transition), then fails with the same code.
        store.change('p503', lambda d: d['analysis'].update(status='running'))
        try:
            raise PermissionError(13, 'fixture: a new local failure, same run, same code')
        except PermissionError:
            store.change('p503', lambda d: d['analysis'].update(status='failed', error_code='unexpected', error='new'))
    analysis = store.read('p503')['analysis']
    assert analysis.get('attribution_source') == 'local'
    assert analysis.get('http_status') is None and analysis.get('upstream_error_type') is None, analysis


@pytest.mark.usefixtures('isolated__r22_415')
def test_i503_store_has_no_same_failure_rule():
    text = (ROOT / 'backend/services/studio/store.py').read_text(encoding='utf-8')
    assert "prior.get('error_code') == record.get('error_code')" not in text
    assert 'same_failure' not in text and 'prior_snapshot' not in text


# --- redaction boundaries: the snapshot is built before ``from None`` and rides on the safe error ------

@pytest.mark.usefixtures('isolated__r22_415')
def test_guard_a_provider_error_wrapped_once_by_the_redaction_boundary_is_still_model():
    from backend.core.llm_telemetry import log_safe_exception
    try:
        try:
            raise _status_error(503)
        except ProviderError as original:
            raise log_safe_exception(original) from None
    except RuntimeError as safe:
        wrapped = safe
    assert wrapped.__cause__ is None and wrapped.__suppress_context__  # the raw chain is cut
    assert classify_failure(wrapped).kind is FailureKind.MODEL
    found = _attr__r29_415(wrapped)
    assert (found.get('attribution_source'), found.get('http_status')) == ('phase', 503), found
    assert SECRET_BODY__r29_415 not in json.dumps(found) and 'sk-r29' not in json.dumps(found)


@pytest.mark.usefixtures('isolated__r22_415')
def test_guard_a_connection_error_through_the_real_call_boundary_is_model_without_status():
    """+ boundary: openai APIConnectionError wrapped by log_safe_exception inside the observed call."""
    from backend.core.llm_telemetry import log_safe_exception

    def impl(*_a, **_k):
        try:
            raise _connection_error()
        except openai.APIConnectionError as original:
            raise log_safe_exception(original) from None
    with llm_emit.track_run():
        try:
            with llm_emit.bind_context(identity=KIMI):
                llm_emit.observe_provider_call(_provider('https://kimi.fixture.example/v1', 'kimi-k2'), impl, 'p')
        except RuntimeError as error:
            verdict = classify_failure(error)
            found = llm_emit.attribution(error)
    assert verdict.kind is FailureKind.MODEL
    assert (found.get('attribution_source'), found.get('provider')) == ('request', 'kimi'), found
    assert 'http_status' not in found  # no HTTP response, no status


@pytest.mark.usefixtures('isolated__r22_415')
def test_guard_sentry_event_of_a_wrapped_provider_error_has_no_message_or_url_and_is_model():
    import sentry_sdk
    from sentry_sdk.utils import event_from_exception
    from backend.core.llm_telemetry import log_safe_exception
    try:
        try:
            raise _status_error(503)
        except ProviderError as original:
            raise log_safe_exception(original) from None
    except RuntimeError as safe:
        wrapped = safe
    options = {**sentry_sdk.get_client().options, 'include_local_variables': False, 'include_source_context': False}
    event, _hint = event_from_exception(wrapped, client_options=options)
    text = json.dumps(event, default=str)
    assert SECRET_BODY__r29_415 not in text and 'sk-r29-SECRET' not in text and 'kimi.fixture.example/v1/chat' not in text
    assert len(event['exception']['values']) == 1  # no raw provider exception in the chain
    with llm_emit.track_run():
        tags = llm_emit.sentry_tags_for_error(wrapped, 'analyze')
    assert tags.get('http_status') == '503', tags


@pytest.mark.usefixtures('isolated__r22_415')
def test_cloud_transcription_http_failure_carries_a_model_snapshot_through_the_adapter(cloud_adapter):
    import asyncio
    import httpx
    case = cloud_adapter
    case.configure('qwen-audio-3.0-asr-flash', lambda request: httpx.Response(
        503, json={'error': {'message': SECRET_BODY__r29_415}}, request=request))
    result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    assert result['error_code'] == 'provider_error'
    carried = result.get('attribution') or {}
    assert (carried.get('attribution_source'), carried.get('http_status')) == ('phase', 503), result
    assert SECRET_BODY__r29_415 not in json.dumps(result, ensure_ascii=False)


@pytest.mark.usefixtures('isolated__r22_415')
def test_cloud_transcription_connection_failure_is_model_without_status(cloud_adapter):
    import asyncio
    import httpx
    case = cloud_adapter

    def reply(request):
        raise httpx.ConnectError('private-network-detail', request=request)
    case.configure('qwen-audio-3.0-asr-flash', reply)
    result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    carried = result.get('attribution') or {}
    assert carried.get('attribution_source') == 'phase' and 'http_status' not in carried, result


# --- ModelResponseInvalid: 200 + content failed our validation is MODEL (invalid_response) ---------------

_INVALID_SITES = {
    'backend/services/studio/intelligence.py': ('文字模型返回的内容不是有效 JSON', '视觉模型返回的候选格式无效', '模型返回重复候选标识',
                                               '模型选段超出期望时长', '模型复核边界超出采样区间', '模型未返回成片方案'),
    'backend/services/studio/subtitle_promo.py': ('推广方案格式无效', '推广方案引用了无效片段', '推广文案为空'),
    'backend/utils/llm_client.py': ('无法从响应中解析出有效的JSON',),
}


@pytest.mark.usefixtures('isolated__r22_415')
def test_model_response_invalid_raise_sites():
    """Every listed site raises the explicit type (intelligence 8 incl. refine + 2 duration sites, promo 3,
    llm_client 2). Subtitle translation no longer raises: a short reply is retried, then source lines fill the gap."""
    count = 0
    for rel, needles in _INVALID_SITES.items():
        tree = ast.parse((ROOT / rel).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
                continue
            text = ast.unparse(node.exc)
            if any(n in text for n in needles):
                name = node.exc.func.id if isinstance(node.exc.func, ast.Name) else ast.unparse(node.exc.func)
                assert name == 'ModelResponseInvalid', f'{rel}:{node.lineno}: {name}'
                count += 1
    assert count == 13, count


@pytest.mark.usefixtures('isolated__r22_415')
def test_model_response_invalid_is_model_with_invalid_response(monkeypatch):
    from backend.services.studio import intelligence
    with pytest.raises(ValueError) as dup:
        intelligence.select_highlights([{'id': 'a', 'label': 'x', 'start': 0, 'end': 2},
                                        {'id': 'a', 'label': 'y', 'start': 3, 'end': 5}], 10)
    assert classify_failure(dup.value).kind is FailureKind.MODEL
    assert studio_error_code(dup.value) == 'invalid_response'
    from backend.utils.llm_client import LLMClient
    with pytest.raises(ValueError) as unparsable:
        LLMClient.parse_json_response(object.__new__(LLMClient), 'no json here at all')
    assert classify_failure(unparsable.value).kind is FailureKind.MODEL
    assert studio_error_code(unparsable.value) == 'invalid_response'
    found = _attr__r29_415(unparsable.value)
    assert found.get('attribution_source') == 'phase' and 'http_status' not in found


@pytest.mark.usefixtures('isolated__r22_415')
def test_model_response_invalid_from_text_json(monkeypatch):
    from backend.services.studio import intelligence
    from backend.utils import llm_client
    fake = type('C', (), {'llm_manager': type('M', (), {'get_current_provider_info': lambda self: {'available': True}})(),
                          'call': lambda self, p, d: 'certainly! not json'})
    monkeypatch.setattr(llm_client, 'LLMClient', fake)
    with pytest.raises(ValueError) as caught:
        intelligence.text_json('p', {})
    assert classify_failure(caught.value).kind is FailureKind.MODEL
    assert studio_error_code(caught.value) == 'invalid_response'


# the single factory / single reader guard is an AST scan

# the variable-name reader heuristic (REC / READ_KEYS, ~60 lines) is deleted: the runtime
# payload tests (test_r31_415_payload.py, frontend failure-attribution.test.cjs) are the guarantee now. What
# stays here is the cheap structural part: one factory, one restore point.
FACTORY_NAMES = {'FailureAttribution', '_make', 'from_fields'}
RESTORE_ALLOWED = {('backend/services/studio/jobs.py', 'run_content')}


def py_offences(source, rel='<memory>'):
    tree = ast.parse(source)
    out = []
    funcs = {}
    for f in ast.walk(tree):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(f):
                funcs.setdefault(id(n), f.name)
    for n in ast.walk(tree):
        name = n.id if isinstance(n, ast.Name) else n.attr if isinstance(n, ast.Attribute) else \
            n.name if isinstance(n, ast.alias) else n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None
        if name in FACTORY_NAMES:
            out.append((getattr(n, 'lineno', 0), f'factory: {name}'))
        if name == 'restore_attribution' and isinstance(n, (ast.Name, ast.Attribute, ast.alias)) \
                and (rel, funcs.get(id(n))) not in RESTORE_ALLOWED:
            out.append((getattr(n, 'lineno', 0), 'restore outside its one restore point'))
    return out


@pytest.mark.usefixtures('isolated__r22_415')
def test_i502_ast_guard_backend_has_one_factory_and_one_reader():
    offenders = []
    for path in sorted((ROOT / 'backend').rglob('*.py')):
        rel = path.relative_to(ROOT).as_posix()
        if '/tests/' in rel or rel == 'backend/core/failure_attribution.py':
            continue
        offenders += [f'{rel}:{line}: {what}' for line, what in py_offences(path.read_text(encoding='utf-8'), rel)]
    assert not offenders, '\n'.join(offenders)


@pytest.mark.usefixtures('isolated__r22_415')
@pytest.mark.parametrize('source', [
    # D3 : a second constructor through an alias
    'from backend.core.failure_attribution import FailureAttribution as _FA\n_bypass = lambda **k: _FA._make(**k)\n',
    # astra/sol: an alias of the class, then a direct construction
    'from backend.core import failure_attribution as fa\nSnapshot = fa.FailureAttribution\nsnap = Snapshot("local")\n',
    # a dynamic getattr on the module
    'import importlib\nm = importlib.import_module("backend.core.failure_attribution")\nS = getattr(m, "FailureAttribution")\n',
    # a restore under an import alias, outside run_content (mutation G5)
    'from backend.core.failure_attribution import restore_attribution as _ra\n_y = lambda f: _ra(f)\n',
])
def test_i502_ast_guard_catches_every_bypass(source):
    assert py_offences(source), source


@pytest.mark.usefixtures('isolated__r22_415')
def test_i502_ast_guard_allows_plain_writes():
    assert not py_offences("def f(record, s):\n    record['http_status'] = s\n    record.pop('attribution_source', None)\n")



@pytest.mark.usefixtures('isolated__r22_415')
@pytest.mark.parametrize('make, code', [(_connection_error, 'connection'), (_timeout_error, 'timeout')])
def test_i505_connection_errors_and_timeouts_are_model_without_a_status(make, code):
    error = make()
    assert classify_failure(error).kind is FailureKind.MODEL
    assert studio_error_code(error) == code
    found = _attr__r29_415(error)
    assert found.get('attribution_source') == 'phase' and 'http_status' not in found


@pytest.mark.usefixtures('isolated__r22_415')
def test_i505_status_only_on_the_implicit_context_is_not_written():
    try:
        try:
            raise _status_error(503)
        except ProviderError:
            raise _connection_error()  # noqa: B904 - implicit context on purpose
    except openai.APIConnectionError as error:
        found = _attr__r29_415(error)
    assert 'http_status' not in found, found


@pytest.mark.usefixtures('isolated__r22_415')
def test_i506_monitoring_doc_says_source_blocked_keeps_no_site_status():
    text = (ROOT / 'docs/analytics/STUDIO_MONITORING.md').read_text(encoding='utf-8')
    assert '`failure_stage=ingest` 和 `http_status`' not in text
    assert '**不记录**站点状态码' in text


@pytest.mark.usefixtures('isolated__r22_415')
def test_redaction_boundary_returns_an_error_with_no_raw_chain():
    """log_safe_exception is also used without `raise … from None` (step1_outline), so the safe error itself
    must not link back to the raw provider error: no __cause__, and the formatted traceback has no raw text."""
    import traceback
    from backend.core.llm_telemetry import log_safe_exception
    try:
        raise _connection_error()
    except Exception as raw:
        safe = log_safe_exception(raw)
    assert safe.__cause__ is None
    text = ''.join(traceback.format_exception(type(safe), safe, safe.__traceback__))
    assert SECRET_URL not in text and 'Connection error' not in text
    assert classify_failure(safe).kind is FailureKind.MODEL
"""(NO-GO, plan 157/415-r30-plan.md + 3 binding amendments): (a store write
stamps a snapshot only on a record that became failed in THAT write), (one HTTP-status rule: the
status frozen at the redaction boundary, else the explicit ``__cause__`` chain; never ``__context__``),
(one classification: no ``sent`` override; the boundary classifies inside, raises ``from None``).
Each test fails on df53c89d on an assertion, or is proven by a mutation (157/mut415-r30). Nothing here
imports a symbol that only exists on the fixed side."""
SECRET_URL__r30_415 = 'https://kimi.fixture.example/v1/chat?api_key=sk-r30-SECRET-0000'
SECRET_BODY__r30_415 = 'r30-private-provider-body'
SNAPSHOT_KEYS = ('attribution_source', 'provider', 'config_source', 'model', 'base_url_host', 'http_status',
                 'upstream_error_type', 'failure_stage', 'error_code')


class ProviderError__r30_415(openai.APIStatusError):
    def __init__(self, message, status_code):
        Exception.__init__(self, message)
        self.status_code = status_code


def _snap(record):
    return {k: record.get(k) for k in SNAPSHOT_KEYS}


def _fail_with_kimi_503(pid, name='analysis', **extra):
    """A real failure: Kimi's request answers 503 and the record goes running -> failed in that write."""
    with llm_emit.track_run():
        try:
            _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
        except Exception:  # noqa: BLE001
            store.change(pid, lambda d: d[name].update(status='failed', error_code='provider_error', **extra))
    stored = store.read(pid)[name]
    assert (stored.get('attribution_source'), stored.get('provider'), stored.get('http_status')) == ('request', 'kimi', 503), stored
    return _snap(stored)


def _unrelated_write_while_handling(pid, error, mutate):
    """A store write inside an ``except`` that has nothing to do with the failed record (GLM phase)."""
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise error
        except BaseException:  # noqa: BLE001
            store.change(pid, mutate)


# only a record that became failed IN THIS WRITE gets a snapshot

@pytest.mark.usefixtures('isolated__r22_415')
def test_i560_an_unrelated_write_in_an_except_keeps_the_existing_failure_snapshot():
    _project__r25_415('p560a', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    before = _fail_with_kimi_503('p560a')
    _unrelated_write_while_handling('p560a', RuntimeError('local GLM failure'), lambda d: d.update(note='unrelated'))
    assert _snap(store.read('p560a')['analysis']) == before


@pytest.mark.usefixtures('isolated__r22_415')
def test_i560_a_permission_error_while_updating_something_else_keeps_the_snapshot():
    _project__r25_415('p560p', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    before = _fail_with_kimi_503('p560p')
    _unrelated_write_while_handling('p560p', PermissionError(13, 'fixture'), lambda d: d.update(jobs=[{'job_id': 'j', 'status': 'failed'}]))
    assert _snap(store.read('p560p')['analysis']) == before


@pytest.mark.usefixtures('isolated__r22_415')
def test_i560_a_partial_terminal_keeps_its_snapshot_on_an_unrelated_write():
    """completed + outcome=partial is a failed terminal : it is not 'non-failed' before the write."""
    _project__r25_415('p560q', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    _fail_with_kimi_503('p560q')
    store.change('p560q', lambda d: d['analysis'].update(status='completed', outcome='partial'))
    before = _snap(store.read('p560q')['analysis'])
    assert before['http_status'] == 503
    _unrelated_write_while_handling('p560q', RuntimeError('local'), lambda d: d.update(note='x'))
    assert _snap(store.read('p560q')['analysis']) == before


@pytest.mark.usefixtures('isolated__r22_415')
def test_i560_the_generation_snapshot_is_kept_too():
    store.directory('p560g').mkdir(parents=True, exist_ok=True)
    store.write('p560g', {'id': 'p560g', 'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'r1', 'instance': store.INSTANCE},
                          'generation': {'status': 'production', 'created_at': '2026-10-17T03:00:00Z'}})
    before = _fail_with_kimi_503('p560g', name='generation', finished_at='2026-10-17T03:01:00Z')
    _unrelated_write_while_handling('p560g', RuntimeError('local'), lambda d: d.update(note='x'))
    assert _snap(store.read('p560g')['generation']) == before


@pytest.mark.usefixtures('isolated__r22_415')
def test_i560_cover_dispatch_failure_does_not_rewrite_the_run_snapshot(monkeypatch):
    """jobs.request_ai_cover: cover_executor.submit fails -> _update_cover_job inside the except (jobs.py:952)."""
    from backend.services import cover
    from backend.services.studio import jobs
    _project__r25_415('p560c', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    store.change('p560c', lambda d: d.update(output_variants=[{'id': 'v1', 'status': 'completed'}]))
    before = _fail_with_kimi_503('p560c')
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=True, configured=True, allow_send_frame=True))

    class Refusing:
        def submit(self, *_a, **_k):
            raise RuntimeError('executor shut down')
    monkeypatch.setattr(jobs, 'cover_executor', Refusing())
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        jobs.request_ai_cover('p560c', 'v1')
    data = store.read('p560c')
    assert data['output_variants'][0]['cover_job']['status'] == 'failed'
    assert _snap(data['analysis']) == before


@pytest.mark.usefixtures('isolated__r22_415')
def test_i560_a_real_transition_still_stamps_the_snapshot():
    _project__r25_415('p560t', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    _fail_with_kimi_503('p560t')  # running -> failed with the 503 in hand: request/kimi/503


@pytest.mark.usefixtures('isolated__r22_415')
def test_i560_same_run_retry_goes_running_then_fails_again_replaces_the_snapshot():
    """amendment 3: same run_id fails, the retry goes to running, fails again -> the 2nd failure's."""
    _project__r25_415('p560r', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    _fail_with_kimi_503('p560r')
    store.change('p560r', lambda d: d['analysis'].update(status='running'))
    _unrelated_write_while_handling('p560r', PipelineFailure('ANALYZE', 'slow', code='timeout'),
                                    lambda d: d['analysis'].update(status='failed', error_code='timeout'))
    analysis = store.read('p560r')['analysis']
    assert (analysis.get('attribution_source'), analysis.get('provider'), analysis.get('run_id')) == ('phase', 'glm', 'r1'), analysis
    assert analysis.get('http_status') is None and analysis.get('error_code') == 'timeout', analysis


@pytest.mark.usefixtures('isolated__r22_415')
def test_i560_a_failure_of_another_run_replaces_the_snapshot_without_passing_running():
    _project__r25_415('p560n', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    _fail_with_kimi_503('p560n')
    _unrelated_write_while_handling('p560n', PipelineFailure('ANALYZE', 'slow', code='timeout'),
                                    lambda d: d['analysis'].update(status='failed', run_id='r2', error_code='timeout'))
    analysis = store.read('p560n')['analysis']
    assert (analysis.get('attribution_source'), analysis.get('provider'), analysis.get('http_status')) == ('phase', 'glm', None), analysis


# one status rule; an old 503 never leaks into a new request

def _connection_error_while_handling_a_503():
    try:
        try:
            raise ProviderError__r30_415(f'Error code: 503 {SECRET_BODY__r30_415}', 503)
        except ProviderError__r30_415:
            raise openai.APIConnectionError(message=f'Connection error. {SECRET_URL__r30_415}', request=httpx.Request('POST', SECRET_URL__r30_415))  # noqa: B904
    except openai.APIConnectionError as error:
        return error


@pytest.mark.usefixtures('isolated__r22_415')
def test_i563_http_status_of_never_reads_the_implicit_context():
    error = _connection_error_while_handling_a_503()
    assert isinstance(error.__context__, ProviderError__r30_415) and error.__cause__ is None
    assert http_status_of(error) is None


@pytest.mark.usefixtures('isolated__r22_415')
def test_i563_an_old_503_does_not_leak_into_the_new_requests_record(monkeypatch):
    posted = []
    monkeypatch.setattr(llm_emit, '_submit_event', lambda event, props: posted.append((event, props)))

    def impl(*_a, **_k):
        raise _connection_error_while_handling_a_503()
    with llm_emit.track_run():
        with pytest.raises(openai.APIConnectionError) as raised:
            with llm_emit.bind_context(identity=KIMI):
                llm_emit.observe_provider_call(type('P', (), {'base_url': 'https://kimi.fixture.example/v1', 'model_name': 'kimi-k2'})(), impl, 'p')
        found = llm_emit.attribution(raised.value)
    assert (found.get('attribution_source'), found.get('provider')) == ('request', 'kimi'), found
    assert 'http_status' not in found, found
    requests_posted = [props for event, props in posted if event == 'llm_request_finished']
    assert requests_posted and all(props.get('http_status') in (None, 0) for props in requests_posted), requests_posted


@pytest.mark.usefixtures('isolated__r22_415')
def test_i563_the_status_frozen_at_the_transcription_boundary_survives_from_none(cloud_adapter):
    case = cloud_adapter
    case.configure('qwen-audio-3.0-asr-flash', lambda request: httpx.Response(
        503, json={'error': {'message': SECRET_BODY__r30_415}}, request=request))
    result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    assert result.get('http_status') == 503, result  # the dict the run_content bridge reads (RC156 Win QA #1)
    assert SECRET_BODY__r30_415 not in json.dumps(result, ensure_ascii=False)


@pytest.mark.usefixtures('isolated__r22_415')
def test_i563_the_log_safe_boundary_freezes_the_status_and_cuts_the_chain():
    from backend.core.llm_telemetry import log_safe_exception
    try:
        try:
            raise ProviderError__r30_415(f'Error code: 429 {SECRET_BODY__r30_415}', 429)
        except ProviderError__r30_415 as original:
            raise log_safe_exception(original) from None
    except RuntimeError as safe:
        assert safe.__cause__ is None
        assert http_status_of(safe) == 429
        assert getattr(safe, 'http_status', None) == 429


# one classification; boundaries classify inside and raise from None

def _recording_factory(monkeypatch, module):
    # : the boundaries now reach THE factory through llm_emit.attribution_snapshot (to pass the
    # call's identity), which imports it from failure_attribution at call time: record it there.
    from backend.core import failure_attribution
    calls = []
    real = failure_attribution.build_attribution

    def record(error=None, **kwargs):
        calls.append((error, kwargs))
        return real(error, **kwargs)
    monkeypatch.setattr(failure_attribution, 'build_attribution', record)
    return calls


@pytest.mark.usefixtures('isolated__r22_415')
def test_i567_the_cover_boundary_lets_the_classifier_decide(monkeypatch):
    from backend.core import image_providers
    calls = _recording_factory(monkeypatch, image_providers)

    @image_providers._image_transport_errors
    def send():
        raise requests.exceptions.ConnectionError(f'HTTPSConnectionPool {SECRET_URL__r30_415}')
    with pytest.raises(image_providers.ImageError) as raised:
        send()
    (seen, kwargs), = calls
    assert 'sent' not in kwargs, kwargs  # no second judgement path in the factory
    assert classify_failure(seen).kind is FailureKind.MODEL  # THE classifier decides the boundary's view
    assert SECRET_URL__r30_415 not in str(seen) and raised.value.__cause__ is None
    assert raised.value.attribution.attribution_source == 'phase'


@pytest.mark.usefixtures('isolated__r22_415')
def test_i567_the_transcription_boundary_lets_the_classifier_decide(cloud_adapter, monkeypatch):
    from backend.services import cloud_transcription
    calls = _recording_factory(monkeypatch, cloud_transcription)
    case = cloud_adapter

    def reply(request):
        raise httpx.ConnectError(f'private-network-detail {SECRET_URL__r30_415}', request=request)
    case.configure('qwen-audio-3.0-asr-flash', reply)
    asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    assert calls, 'the transcription boundary did not build a snapshot'
    for seen, kwargs in calls:
        assert 'sent' not in kwargs, kwargs
        assert classify_failure(seen).kind is FailureKind.MODEL
        assert SECRET_URL__r30_415 not in str(seen)


@pytest.mark.usefixtures('isolated__r22_415')
def test_i567_build_attribution_has_no_sent_override_and_with_request_record_uses_the_factory():
    assert 'sent' not in inspect.signature(failure_attribution.build_attribution).parameters
    source = inspect.getsource(failure_attribution.with_request_record)
    assert '_make(' not in source and 'replace(' not in source
    assert 'replace(' not in inspect.getsource(failure_attribution.build_attribution)


class _Collect:
    """A fake Sentry transport: the envelopes stay in this process (no DSN, nothing is sent)."""
    def __init__(self, options=None):
        self.envelopes = []

    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)

    def flush(self, *_a, **_k):
        pass

    def kill(self):
        pass

    def is_healthy(self):
        return True

    def record_lost_event(self, *_a, **_k):
        pass


def _envelope_events(error, *, with_product_filter):
    import sentry_sdk
    from sentry_sdk.transport import Transport
    from backend.core import sentry_setup

    class Collect(_Collect, Transport):
        def __init__(self, options=None):
            Transport.__init__(self, options)
            _Collect.__init__(self)
    transport = Collect()
    client = sentry_sdk.Client(dsn='https://public@sentry.invalid/1', transport=transport, default_integrations=False,
                               include_local_variables=False, include_source_context=False,
                               before_send=sentry_setup.before_send if with_product_filter else None)
    with sentry_sdk.isolation_scope() as scope:
        scope.set_client(client)
        scope.capture_exception(error)
    client.flush(timeout=2)
    events = []
    for envelope in transport.envelopes:
        for item in envelope.items:
            if item.type == 'event':
                events.append(json.loads(item.payload.get_bytes()))
    return events


def _boundary_errors():
    from backend.core import image_providers
    from backend.core.llm_telemetry import log_safe_exception

    @image_providers._image_transport_errors
    def cover():
        raise requests.exceptions.ConnectionError(f'HTTPSConnectionPool {SECRET_URL__r30_415} {SECRET_BODY__r30_415}')
    out = []
    try:
        cover()
    except image_providers.ImageError as error:
        out.append(error)
    try:
        try:
            raise ProviderError__r30_415(f'Error code: 503 {SECRET_URL__r30_415} {SECRET_BODY__r30_415}', 503)
        except ProviderError__r30_415 as original:
            raise log_safe_exception(original) from None
    except RuntimeError as error:
        out.append(error)
    return out


@pytest.mark.usefixtures('isolated__r22_415')
@pytest.mark.parametrize('with_product_filter', [True, False])
def test_i567_sentry_envelope_of_a_boundary_error_has_no_message_url_or_key_in_any_exception(monkeypatch, with_product_filter):
    """amendment 1: classification inside the boundary, ``from None`` outward. Every exception in the
envelope, chained ones included, is checked; also with the SDK's raw serialization (no before_send)."""
    monkeypatch.delenv('SENTRY_DSN', raising=False)
    for error in _boundary_errors():
        events = _envelope_events(error, with_product_filter=with_product_filter)
        assert len(events) == 1
        values = events[0]['exception']['values']
        assert len(values) == 1, [v.get('type') for v in values]  # no raw exception chained in
        text = json.dumps(events[0], ensure_ascii=False, default=str)
        # The redacted text keeps only the bare host (the same value base_url_host carries); the product
        # filter omits even that. Never the URL, its path or query, the key, or the provider's body.
        secrets = [SECRET_URL__r30_415, 'kimi.fixture.example/v1', 'sk-r30-SECRET', SECRET_BODY__r30_415, 'api_key', 'Error code: 503']
        if with_product_filter:
            secrets.append('kimi.fixture.example')
        for secret in secrets:
            assert secret not in text, (type(error).__name__, secret)
"""(PM rule): a multi-goal failure is a product failure as soon as one cause is a product cause; it
leaves a denominator only when every cause is a user cause for it. The primary cause is the first failure
of the most product-like tier, the rest go along as secondary causes. Checked end to end: real
_produce_selected -> analysis record -> the real success_rate.sql. Fails on 1a518570 (order decided).
one SQL adapter for every success-rate test."""

pytest.importorskip('duckdb')
WINDOW = {'date_from': "'2026-10-01 00:00:00'", 'date_to': "'2026-11-01 00:00:00'", 'internal_cohort_id': '641509',
          'release_1_5_7': "'2026-10-01 00:00:00'"}


from backend.tests.test_cloud_asr import _asr_401, _on_disk, _real_store_jobs  # noqa: E402


def _produce__r23_419_attribution(monkeypatch, tmp_path, goals, visual_error):
    store = _real_store_jobs(monkeypatch, {'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'run-m'}}, tmp_path)
    def asr_fails(*a, **k):
        raise _asr_401()                       # content goal: speech key rejected -> llm_auth_invalid / invalid_key
    def vision_fails(*a, **k):
        raise visual_error                     # highlight goal (visual)
    monkeypatch.setattr(jobs, 'run_content', asr_fails)
    monkeypatch.setattr(jobs, 'analyze', vision_fails)
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    jobs._produce_selected('p', {'selected_goals': goals, 'confirmed_preferences': {}, 'confirmed_analysis': 'visual'})
    return _on_disk(store)['analysis']


def _denominators(analysis):
    from datetime import datetime
    props = {'attempt_id': 't-aaaaaaaaaaaa', 'flow_id': 't-ffffffffffff', 'outcome': 'error',
             'error_code': analysis.get('error_code'), 'upstream_error_type': analysis.get('upstream_error_type'),
             'failure_stage': analysis.get('failure_stage'), 'app_version': '1.5.7',
             'analytics_environment': 'production', 'runtime': 'desktop'}
    [row] = run_sql(figure(1, params=WINDOW), [('u1', 'studio_production_finished', 'person-1', datetime(2026, 10, 10, 10), props)])
    return row['q_all'], row['q_prod']


@pytest.mark.parametrize('goals', [['content', 'highlight'], ['highlight', 'content']])
def test_228_auth_plus_visual_timeout_is_a_product_failure_whatever_the_goal_order(monkeypatch, tmp_path, goals):
    a = _produce__r23_419_attribution(monkeypatch, tmp_path, goals, intelligence.VisionRequestError('timeout', '视觉模型请求超时'))
    assert a['status'] == 'failed' and sorted(a['failed_goals']) == ['content', 'highlight']
    assert a['error_code'] == 'timeout' and a['failure_stage'] == 'vision', a
    assert a.get('upstream_error_type') != 'invalid_key'
    assert a['secondary_error_codes'] == ['llm_auth_invalid'] and a['secondary_upstream_error_types'] == ['invalid_key']
    assert _denominators(a) == (1, 1)          # counted in both denominators (was 0 with content first)


@pytest.mark.parametrize('goals', [['content', 'highlight'], ['highlight', 'content']])
def test_228_all_user_causes_leave_the_product_denominator_only(monkeypatch, tmp_path, goals):
    """auth (user_hard) + vision connection (user_x): every cause is a user cause for the product view;
    the full view still counts it because connection is not a hard user cause."""
    a = _produce__r23_419_attribution(monkeypatch, tmp_path, goals, intelligence.VisionRequestError('connection', '视觉模型连接失败'))
    assert a['error_code'] == 'connection' and a['secondary_error_codes'] == ['llm_auth_invalid'], a
    assert _denominators(a) == (1, 0)


def test_228_same_tier_keeps_the_first_failure_and_lists_the_rest():
    from backend.core.failure_attribution import rank_failures
    ranked = rank_failures([{'error_code': 'authentication'}, {'error_code': 'timeout'}, {'error_code': 'render'},
                            {'error_code': 'connection'}])
    assert [f['error_code'] for f in ranked] == ['timeout', 'render', 'connection', 'authentication']


def test_228_tiers_are_the_ones_the_sql_uses():
    """Same priority on both sides: the tiers come from the catalog the SQL is pinned to (test_llm_auth_invalid_e2e)."""
    import re
    from backend.core.failure_attribution import USER_HARD, USER_X, cause_tier
    sql = (ROOT / 'docs/analytics/success_rate.sql').read_text(encoding='utf-8')
    hard = set(re.findall(r"'(\w+)'", re.search(r"OR ec IN \(([^)]*)\)\s*OR ue IN", sql).group(1)))
    hard_ue = set(re.findall(r"'(\w+)'", re.search(r"OR ue IN \(([^)]*)\)\) AS user_hard", sql).group(1)))
    extra = set(re.findall(r"'(\w+)'", re.search(r"user_hard OR ec IN \(([^)]*)\)\) AS user_x", sql).group(1)))
    assert all(cause_tier({'error_code': c}) == USER_HARD for c in hard)
    assert all(cause_tier({'error_code': 'timeout', 'upstream_error_type': u}) == USER_HARD for u in hard_ue)
    assert all(cause_tier({'error_code': c}) == USER_X for c in extra)
    assert cause_tier({'error_code': 'timeout'}) == 0


def test_229_one_sql_adapter():
    tests = ROOT / 'backend' / 'tests'
    users = [p for p in tests.glob('test_*.py') if p.name != Path(__file__).name and 'success_rate.sql' in p.read_text(encoding='utf-8') and 'duckdb' in p.read_text(encoding='utf-8')]
    assert users, 'no SQL test found'
    for p in users + [tests / 'success_rate_sql.py']:
        text = p.read_text(encoding='utf-8')
        assert 'sqlglot' not in text, f'{p.name}: second SQL adapter'
        if p.name != 'success_rate_sql.py':
            assert 'backend.tests.success_rate_sql import' in text, f'{p.name} must use the shared adapter'
            assert 'def to_duckdb' not in text and 'CREATE MACRO' not in text, f'{p.name}: own adapter'


@pytest.mark.parametrize('goals', [['content', 'highlight'], ['highlight', 'content']])
def test_r24_page_gets_the_user_cause_stage_while_event_primary_stays_product(monkeypatch, tmp_path, goals):
    """PM rule: page and stats are separate. The record keeps the product primary (timeout/vision) for the
event, and carries each secondary cause's stage so the page can send 「去设置」 to the right row."""
    a = _produce__r23_419_attribution(monkeypatch, tmp_path, goals, intelligence.VisionRequestError('timeout', '视觉模型请求超时'))
    assert a['error_code'] == 'timeout' and a['failure_stage'] == 'vision'
    assert a['secondary_error_codes'] == ['llm_auth_invalid'] and a['secondary_upstream_error_types'] == ['invalid_key']
    assert a['secondary_failure_stages'] == ['subtitle'], a


def test_267_history_row_keeps_the_secondary_causes(monkeypatch, tmp_path):
    """the analysis_history allow-list kept error_code but dropped the secondary causes."""
    _produce__r23_419_attribution(monkeypatch, tmp_path, ['content', 'highlight'], intelligence.VisionRequestError('timeout', '视觉模型请求超时'))
    from backend.services.studio import store as s
    data = _on_disk(s)
    [row] = [r for r in data['analysis_history'] if r['run_id'] == 'run-m']
    assert row['analysis']['error_code'] == 'timeout'
    assert row['analysis']['secondary_error_codes'] == ['llm_auth_invalid'], row
    assert row['analysis']['secondary_upstream_error_types'] == ['invalid_key']
"""full head (plan approval + 8f0e155c decisions).
Each fix test fails on 8f0e155c on an assertion (157/mut415-r30/before-8f0e155c-*.txt); tests marked LOCK
pass on 8f0e155c too and are proven by a targeted mutation instead (mut31.sh / mut30-dong.sh).
Nothing here imports a symbol that only exists on the fixed side at module level."""

SECRET_BODY__r31_415 = 'r31-private-provider-body sk-r31-SECRET-0000 /Users/someone/clip.mp4'
WHITELIST = {'provider', 'config_source', 'model', 'base_url_host', 'attribution_source', 'http_status',
             'upstream_error_type', 'failure_stage'}


def _frozen_code(error):
    return getattr(error, 'error_code', None)


# a boundary snapshot names the connection THIS call used

@pytest.mark.usefixtures('isolated__r22_415')
def test_i561_the_transcription_boundary_snapshot_carries_the_asr_connection_identity(cloud_adapter):
    case = cloud_adapter
    case.configure('qwen-audio-3.0-asr-flash', lambda request: httpx.Response(503, json={'error': {'message': SECRET_BODY__r31_415}}, request=request))
    result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    found = result['result']['attribution'] if 'attribution' in (result.get('result') or {}) else result.get('attribution') or {}
    assert found.get('attribution_source') == 'phase', result
    assert found.get('provider') and found.get('config_source'), found  # was: no identity at all
    assert found.get('model') == 'qwen-audio-3.0-asr-flash', found
    assert found.get('http_status') == 503 and found.get('failure_stage') == 'subtitle', found


def _cover_call(raise_error, **kwargs):
    from backend.core import image_providers

    @image_providers._image_transport_errors
    def call(**_kwargs):
        raise_error()
    with pytest.raises(image_providers.ImageError) as raised:
        call(**{'provider': 'openai', 'base_url': 'https://api.openai.com/v1', 'model': 'gpt-image-1', **kwargs})
    return raised.value


@pytest.mark.usefixtures('isolated__r22_415')
def test_i561_the_cover_boundary_snapshot_carries_the_image_config_it_sent():
    def boom():
        raise requests.exceptions.ConnectionError(f'HTTPSConnectionPool {SECRET_BODY__r31_415}')
    error = _cover_call(boom)
    snap = error.attribution
    assert (snap.attribution_source, snap.provider, snap.model, snap.base_url_host) == \
        ('phase', 'openai', 'gpt-image-1', 'api.openai.com'), snap


# the controlled code survives the redaction wrap

def _openai_timeout():
    return openai.APITimeoutError(request=httpx.Request('POST', 'https://kimi.fixture.example/v1/chat'))


def _openai_connection():
    return openai.APIConnectionError(message='Connection error.', request=httpx.Request('POST', 'https://kimi.fixture.example/v1/chat'))


@pytest.mark.usefixtures('isolated__r22_415')
@pytest.mark.parametrize('make, code', [(_openai_timeout, 'timeout'), (_openai_connection, 'connection')])
def test_i562_log_safe_keeps_timeout_and_connection_apart(make, code):
    from backend.core.llm_telemetry import log_safe_exception
    safe = log_safe_exception(make())
    assert studio_error_code(safe) == code  # was: 'unexpected' for both
    from backend.pipeline.failures import model_call_error_code
    assert model_call_error_code(safe) == code


@pytest.mark.usefixtures('isolated__r22_415')
@pytest.mark.parametrize('reply, code', [
    (lambda request: (_ for _ in ()).throw(httpx.ConnectError('private-network-detail', request=request)), 'connection'),
    (lambda request: (_ for _ in ()).throw(httpx.ReadTimeout('private-network-detail', request=request)), 'timeout'),
], ids=['connect', 'read_timeout'])
def test_i562_cloud_transcription_keeps_timeout_and_connection_apart(cloud_adapter, reply, code):
    case = cloud_adapter
    case.configure('qwen-audio-3.0-asr-flash', reply)
    result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    assert result['status'] == 'failed'
    assert result['error_code'] == code, result  # was: provider_error for both


@pytest.mark.usefixtures('isolated__r22_415')
def test_i562_lock_undecided_error_freezes_no_snapshot_and_no_code():
    """LOCK (X2): an error the chain cannot decide gets neither a snapshot nor a code at the boundary;
    the call boundary's request record decides it later."""
    from backend.core.llm_telemetry import log_safe_exception
    safe = log_safe_exception(RuntimeError('who knows'))
    assert safe.attribution is None
    assert _frozen_code(safe) is None


# 8f0e155c #1: the ASR user text depends only on error_code and status

@pytest.mark.usefixtures('isolated__r22_415')
def test_dong1_cloud_transcription_text_never_carries_upstream_text(cloud_adapter):
    """LOCK. Two 503s with different bodies give the same user text; a body that LOOKS like a key error
    ('invalid api key') never changes the code or hint. Only status and the frozen code decide."""
    from backend.pipeline.failures import cloud_transcription_failure
    from backend.services.cloud_transcription import CloudTranscriptionError
    texts = []
    for body in (SECRET_BODY__r31_415, 'invalid api key: Incorrect API key provided'):
        case = cloud_adapter
        case.configure('qwen-audio-3.0-asr-flash', lambda request, b=body: httpx.Response(503, text=b, request=request))
        result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
        assert result['error_code'] == 'provider_error', result
        assert body not in json.dumps(result, ensure_ascii=False, default=str)
        texts.append(result['error'])
    assert texts[0] == texts[1] and 'HTTP 503' in texts[0]
    safe = CloudTranscriptionError('云端转写请求失败（HTTP 503），请检查密钥、额度和模型权限。')
    failure_attribution.attributed(safe, None, http_status=503)
    failure = cloud_transcription_failure(str(safe), safe)
    assert failure.code == 'provider_error'
    assert 'invalid api key' not in failure.user_message().lower()


# 8f0e155c #2 + : the cover status is frozen; HTTP errors are not LOCAL

@pytest.mark.usefixtures('isolated__r22_415')
def test_dong2_lock_cover_freezes_the_status_the_library_response_carries():
    """LOCK (D2/D3): requests supplies a real Response; its status is frozen on the safe error AND in the
    snapshot, with the controlled code."""
    response = requests.Response()
    response.status_code = 503
    response._content = SECRET_BODY.encode()

    def boom():
        raise requests.exceptions.HTTPError(SECRET_BODY__r31_415, response=response)
    error = _cover_call(boom)
    assert error.http_status == 503 and http_status_of(error) == 503
    assert error.attribution.http_status == 503 and error.attribution.attribution_source == 'phase'
    assert classify_failure(error).kind is FailureKind.MODEL
    assert _frozen_code(error) in (None, 'provider_error')
    assert SECRET_BODY__r31_415 not in str(error) and error.__cause__ is None


@pytest.mark.usefixtures('isolated__r22_415')
def test_i621_cover_http_error_status_is_model_with_status_and_no_provider_body():
    from backend.core import image_providers
    resp = SimpleNamespace(status_code=503, json=lambda: {'error': {'message': SECRET_BODY__r31_415}}, text=SECRET_BODY__r31_415)
    with pytest.raises(image_providers.ImageError) as raised:
        image_providers._raise_for_status(resp)
    error = raised.value
    assert classify_failure(error).kind is FailureKind.MODEL  # was LOCAL (no snapshot)
    assert http_status_of(error) == 503
    assert error.attribution.http_status == 503 and error.attribution.failure_stage == 'cover'
    assert SECRET_BODY__r31_415 not in str(error) and 'HTTP 503' in str(error)


@pytest.mark.usefixtures('isolated__r22_415')
def test_i621_cover_unsupported_edit_is_still_detected_without_echoing_the_body():
    from backend.core import image_providers
    resp = SimpleNamespace(status_code=400, json=lambda: {'error': {'message': 'edits not supported for this model'}}, text='')
    with pytest.raises(image_providers.ImageError) as raised:
        image_providers._raise_for_status(resp, edit=True)
    assert raised.value.unsupported_edit is True
    assert 'not supported' not in str(raised.value)


@pytest.mark.usefixtures('isolated__r22_415')
def test_i621_a_2xx_that_is_not_an_object_is_an_invalid_model_response():
    from backend.core import image_providers
    resp = SimpleNamespace(status_code=200, json=lambda: [SECRET_BODY__r31_415], text='')
    with pytest.raises(image_providers.ImageError) as raised:
        image_providers._raise_for_status(resp)
    assert classify_failure(raised.value).kind is FailureKind.MODEL
    assert studio_error_code(raised.value) == 'invalid_response'


# X5 / X10: errors raised before anything was sent are LOCAL

@pytest.mark.usefixtures('isolated__r22_415')
@pytest.mark.parametrize('error', [
    requests.exceptions.InvalidHeader('Invalid leading whitespace in header value'),
    requests.exceptions.InvalidJSONError('Object of type bytes is not JSON serializable'),
    requests.exceptions.URLRequired('no url'),
    requests.exceptions.MissingSchema('no scheme'),       # X5 (LOCK)
    requests.exceptions.InvalidURL('bad url'),            # X5 (LOCK)
], ids=['InvalidHeader', 'InvalidJSONError', 'URLRequired', 'MissingSchema', 'InvalidURL'])
def test_x10_cover_request_never_sent_is_local(error):
    def boom():
        raise error
    safe = _cover_call(boom)
    assert safe.attribution.attribution_source == 'local'
    assert classify_failure(safe).kind is FailureKind.LOCAL
    assert safe.http_status is None and _frozen_code(safe) is None


@pytest.mark.usefixtures('isolated__r22_415')
def test_x10_a_response_that_failed_to_parse_is_the_models_side():
    def boom():
        raise requests.exceptions.JSONDecodeError('Expecting value', 'not json', 0)
    safe = _cover_call(boom)
    assert classify_failure(safe).kind is FailureKind.MODEL
    assert studio_error_code(safe) == 'invalid_response'


# X9: a request identity never lands on a LOCAL snapshot

@pytest.mark.usefixtures('isolated__r22_415')
def test_x9_lock_request_record_does_not_reidentify_a_local_snapshot():
    from backend.core.failure_attribution import AttributedError, FailureAttribution, attributed, with_request_record

    class Safe(AttributedError, RuntimeError):
        pass
    local = FailureAttribution._make('local', GLM, failure_stage='cover')
    error = attributed(Safe('x'), local)
    record = SimpleNamespace(attribution=lambda: {**KIMI, 'attribution_source': 'request', 'http_status': 503})
    with_request_record(error, record)
    assert error.attribution.attribution_source == 'local'
    assert error.attribution.provider == GLM['provider'] and error.attribution.http_status is None


# 8f0e155c #3: Retry-After and DNS kind follow only __cause__

class _RateLimited(Exception):
    def __init__(self):
        super().__init__('429')
        self.headers = {'retry-after': '7'}


@pytest.mark.usefixtures('isolated__r22_415')
def test_dong3_retry_after_never_comes_from_an_earlier_unrelated_429():
    from backend.core.llm_retry import retry_after_from_error
    try:
        try:
            raise _RateLimited()
        except _RateLimited:
            raise ConnectionError('new failure')  # noqa: B904 - the implicit context IS the case
    except ConnectionError as error:
        assert isinstance(error.__context__, _RateLimited)
        assert retry_after_from_error(error) is None  # was 7.0


@pytest.mark.usefixtures('isolated__r22_415')
def test_dong3_retry_after_still_follows_an_explicit_cause():
    from backend.core.llm_retry import retry_after_from_error
    try:
        try:
            raise _RateLimited()
        except _RateLimited as original:
            raise RuntimeError('wrapped') from original
    except RuntimeError as error:
        assert retry_after_from_error(error) == 7.0


@pytest.mark.usefixtures('isolated__r22_415')
def test_dong3_network_kind_never_comes_from_an_earlier_dns_failure():
    from backend.core.upstream_errors import network_kind_of
    try:
        try:
            raise socket.gaierror(-2, 'Name or service not known')
        except socket.gaierror:
            raise ConnectionRefusedError('refused')  # noqa: B904
    except ConnectionRefusedError as error:
        assert network_kind_of(error) == ''  # was 'dns'


@pytest.mark.usefixtures('isolated__r22_415')
def test_dong3_network_kind_real_httpx_dns_failure_is_still_dns(monkeypatch):
    """httpx/httpcore attach the gaierror as an explicit cause: the real library still reads as dns."""
    from backend.core.upstream_errors import network_kind_of

    def no_dns(*_a, **_k):
        raise socket.gaierror(-2, 'Name or service not known')
    monkeypatch.setattr(socket, 'getaddrinfo', no_dns)
    with httpx.Client(trust_env=False) as client:
        with pytest.raises(httpx.ConnectError) as raised:
            client.get('https://autoclip-r31.invalid/')
    assert network_kind_of(raised.value) == 'dns'


# only the reply's shape is the model's fault

@pytest.mark.usefixtures('isolated__r22_415')
def test_i568_our_own_type_error_in_the_rewrite_route_is_not_invalid_response(client, monkeypatch):
    from backend.api.v1 import studio as studio_api
    from backend.services.studio import intelligence
    draft = client.post('/studio/p1/drafts', json={'clip_ids': ['c1'], 'title': 'Original'}).json()
    seen = []
    monkeypatch.setattr(studio_api, 'capture_studio_exception', lambda error, phase: seen.append(error))
    monkeypatch.setattr(intelligence, 'text_json', lambda *a, **k: {'title': 'T', 'hook': 'H'})

    def broken(*_a, **_k):
        raise TypeError('a bug in our own code')
    monkeypatch.setattr(studio_api, 'Draft', SimpleNamespace(model_validate=broken))
    response = client.post('/studio/p1/rewrite', json={'draft': draft, 'instruction': 'shorter'})
    assert response.status_code == 502
    assert len(seen) == 1 and isinstance(seen[0], TypeError), seen  # was: ModelResponseInvalid
    assert classify_failure(seen[0]).kind is not FailureKind.MODEL
    assert studio_error_code(seen[0]) != 'invalid_response'


@pytest.mark.usefixtures('isolated__r22_415')
def test_i568_a_reply_that_is_not_an_object_is_still_invalid_response(client, monkeypatch):
    from backend.api.v1 import studio as studio_api
    from backend.services.studio import intelligence
    draft = client.post('/studio/p1/drafts', json={'clip_ids': ['c1'], 'title': 'Original'}).json()
    seen = []
    monkeypatch.setattr(studio_api, 'capture_studio_exception', lambda error, phase: seen.append(error))
    monkeypatch.setattr(intelligence, 'text_json', lambda *a, **k: 'just a string')
    assert client.post('/studio/p1/rewrite', json={'draft': draft, 'instruction': 'x'}).status_code == 502
    assert studio_error_code(seen[0]) == 'invalid_response'


# a rollback write is not a transition

def _refusing_executor(monkeypatch):
    from backend.services.studio import jobs

    class Refusing:
        def submit(self, *_a, **_k):
            raise RuntimeError('executor shut down')
    monkeypatch.setattr(jobs, 'executor', Refusing())


@pytest.mark.usefixtures('isolated__r22_415')
def test_i620_real_inspect_dispatch_rejection_keeps_the_previous_failure_snapshot(monkeypatch):
    from backend.services.studio import jobs, readiness
    _project__r25_415('p620i', {'status': 'running', 'phase': 'screening', 'run_id': 'r1'})
    before = _fail_with_kimi_503('p620i')
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda *a, **k: None)
    _refusing_executor(monkeypatch)
    options = SimpleNamespace(platforms=['douyin'], branding=SimpleNamespace(model_dump=lambda: {}), auto_start=False,
                              portrait_style=None, html_template=None, recommended_template=None)
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        with pytest.raises(ValueError):
            jobs.inspect_project('p620i', options)
    after = store.read('p620i')['analysis']
    assert after.get('run_id') == 'r1'
    assert _snap(after) == before  # was: overwritten with local/glm


@pytest.mark.usefixtures('isolated__r22_415')
def test_i620_real_confirm_dispatch_rejection_writes_the_previous_state_back_unchanged(monkeypatch):
    from backend.services.studio import intelligence, jobs, readiness
    from backend.services.studio.models import ConfirmPlan
    store.directory('p620c').mkdir(parents=True, exist_ok=True)
    store.write('p620c', {'id': 'p620c', 'analysis': {'status': 'awaiting_confirmation', 'run_id': 'r1', 'phase': 'screening'},
                          'plan': {'id': 'plan', 'recommended_analysis': 'visual', 'preferences': {}}})
    before = store.read('p620c')['analysis']
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda *a, **k: None)
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    _refusing_executor(monkeypatch)
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        with pytest.raises(ValueError):
            jobs.confirm_project('p620c', ConfirmPlan(plan_id='plan', goals=['highlight'], analysis_mode='visual'))
    after = store.read('p620c')['analysis']
    assert after.get('run_id') == 'r1' and after.get('status') == 'awaiting_confirmation'
    assert _snap(after) == _snap(before)  # was: the dispatch error's local/glm identity written onto it


# failed -> failed in the same attempt carries the STORED group forward

@pytest.mark.usefixtures('isolated__r22_415')
def test_i622_a_writer_that_rebuilds_the_failed_record_keeps_the_stored_snapshot():
    _project__r25_415('p622', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    before = _fail_with_kimi_503('p622')

    def rebuild(data):
        data['analysis'] = {'status': 'failed', 'phase': 'production', 'run_id': 'r1', 'error_code': 'provider_error'}
    store.change('p622', rebuild)
    assert _snap(store.read('p622')['analysis']) == before  # was: no snapshot at all


@pytest.mark.usefixtures('isolated__r22_415')
def test_i622_lock_same_attempt_error_code_change_keeps_the_snapshot_and_takes_the_new_code():
    """LOCK of the current rule (B/C): the snapshot stays the stored one; error_code is the
writer's. No inference reconciles them."""
    _project__r25_415('p622b', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    before = _fail_with_kimi_503('p622b')
    _unrelated_write_while_handling('p622b', RuntimeError('local'), lambda d: d['analysis'].update(error_code='timeout'))
    after = _snap(store.read('p622b')['analysis'])
    assert after == {**before, 'error_code': 'timeout'}


# one construction, one valid status range

@pytest.mark.usefixtures('isolated__r22_415')
def test_i623_cloud_transcription_failure_freezes_the_status_on_itself():
    from backend.pipeline.failures import cloud_transcription_failure
    from backend.services.cloud_transcription import CloudTranscriptionError
    safe = failure_attribution.attributed(CloudTranscriptionError('x'), None, http_status=503)
    failure = cloud_transcription_failure('x', safe)
    assert failure.__cause__ is None
    assert failure.http_status == 503  # was None (only reachable through a caller's ``from e``)


@pytest.mark.usefixtures('isolated__r22_415')
@pytest.mark.parametrize('status', [200, 302, 399, True])
def test_i623_a_non_error_status_is_never_frozen(status):
    from backend.core.failure_attribution import AttributedError, ProviderTransportError, attributed

    class Safe(AttributedError, RuntimeError):
        pass
    assert attributed(Safe('x'), None, http_status=status).http_status is None
    assert ProviderTransportError('HTTPStatus', http_status=status).http_status is None


@pytest.mark.usefixtures('isolated__r22_415')
def test_i623_run_content_freezes_the_adapter_status_through_attributed(monkeypatch, tmp_path):
    """LOCK (mut31 M623-2): run_content freezes through attributed(), so a 302 never lands."""
    from backend.services.studio import jobs
    from backend.tasks import processing
    result = {'success': False, 'error': '内容切片失败', 'result': {'http_status': 302, 'attribution': None}}
    monkeypatch.setattr(processing.process_video_pipeline, 'apply', lambda **_k: SimpleNamespace(get=lambda: result))
    video = tmp_path / 'input.mp4'
    video.write_bytes(b'')
    with pytest.raises(jobs.ContentRunError) as raised:
        jobs.run_content('p623', video)
    assert raised.value.http_status is None  # 302 is not an error status (was frozen by hand: 302)



@pytest.mark.usefixtures('isolated__r22_415')
def test_i624_d1_a_generation_failure_of_another_run_replaces_the_snapshot():
    """LOCK, kills D1."""
    store.directory('p624g').mkdir(parents=True, exist_ok=True)
    store.write('p624g', {'id': 'p624g', 'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'r1', 'instance': store.INSTANCE},
                          'generation': {'status': 'production', 'created_at': '2026-10-17T03:00:00Z'}})
    _fail_with_kimi_503('p624g', name='generation', finished_at='2026-10-17T03:01:00Z')
    _unrelated_write_while_handling('p624g', RuntimeError('local GLM'),
                                    lambda d: d['generation'].update(status='failed', created_at='2026-10-17T04:00:00Z'))
    generation = store.read('p624g')['generation']
    assert (generation.get('attribution_source'), generation.get('provider'), generation.get('http_status')) == ('local', 'glm', None), generation


@pytest.mark.usefixtures('isolated__r22_415')
def test_i624_d4_a_request_record_fills_its_own_failure_stage():
    """LOCK, kills D4."""
    from backend.core.failure_attribution import AttributedError, FailureAttribution, attributed, with_request_record

    class Safe(AttributedError, RuntimeError):
        pass
    error = attributed(Safe('x'), FailureAttribution._make('phase', None, http_status=503))
    record = SimpleNamespace(attribution=lambda: {**KIMI, 'attribution_source': 'request', 'failure_stage': 'analyze'})
    with_request_record(error, record)
    assert (error.attribution.attribution_source, error.attribution.failure_stage) == ('request', 'analyze')


@pytest.mark.usefixtures('isolated__r22_415')
def test_i562_the_pipeline_code_reader_takes_the_code_the_cover_boundary_froze():
    """model_call_error_code reads the frozen code first: the safe ImageError's own text/type says nothing."""
    from backend.pipeline.failures import model_call_error_code

    def boom():
        raise requests.exceptions.ReadTimeout(f'HTTPSConnectionPool read timed out {SECRET_BODY__r31_415}')
    error = _cover_call(boom)
    assert model_call_error_code(error) == 'timeout'  # was provider_error
    assert studio_error_code(error) == 'timeout'


@pytest.mark.usefixtures('isolated__r22_415')
def test_x4_lock_the_asr_pipeline_wrapper_carries_the_boundary_snapshot_itself():
    """LOCK (X4): the snapshot rides on the wrapper by THE construction, not via a caller's ``from e``."""
    from backend.core.failure_attribution import FailureAttribution
    from backend.pipeline.failures import cloud_transcription_failure
    from backend.services.cloud_transcription import CloudTranscriptionError
    snap = FailureAttribution._make('phase', {'provider': 'dashscope', 'config_source': 'preset', 'model': 'qwen-audio-3.0-asr-flash'},
                                    http_status=503, failure_stage='subtitle')
    safe = failure_attribution.attributed(CloudTranscriptionError('x'), snap, http_status=503)
    failure = cloud_transcription_failure('x', safe)
    assert failure.__cause__ is None
    assert failure.attribution == snap
    assert classify_failure(failure).kind is FailureKind.MODEL
""": runtime payload tests replace the reader AST heuristic as the primary guard.
A dirty record / snapshot (extra keys, a string status, a bool status, an unknown source, a URL-ish prose
value in a non-whitelisted key) goes through every exit: the store read projection, the history summary,
llm_emit.attribution / run_snapshot / sentry_tags_for_error, sentry_setup.studio_failure_context and the
real Sentry envelope (fake transport, nothing is sent). Only whitelisted keys with valid values come out."""

SECRET = 'sk-r31-SECRET-0000 https://user:pw@private.example/v1?key=x /Users/someone/clip.mp4'
DIRTY = {'attribution_source': 'request', 'provider': 'kimi', 'config_source': 'custom', 'model': 'kimi-k2',
         'base_url_host': 'kimi.fixture.example', 'http_status': '503;drop', 'upstream_error_type': 'upstream_unavailable',
         'failure_stage': 'analyze', 'raw_message': SECRET, 'api_key': SECRET, 'url': SECRET}
WHITELIST__r31_415_payload = set(SNAPSHOT_FIELDS)


def _no_secret(payload):
    text = json.dumps(payload, ensure_ascii=False, default=str)
    assert 'SECRET' not in text and 'private.example' not in text and '/Users/' not in text, text
    assert '503;drop' not in text, text


class _Safe(AttributedError, RuntimeError):
    pass


def _dirty_error():
    error = _Safe('safe text')
    # bypass the factory on purpose: a snapshot that a future writer could build wrong
    error.attribution = FailureAttribution('request', provider='kimi', config_source='custom', model='kimi-k2',
                                           base_url_host='kimi.fixture.example', http_status='503;drop',
                                           upstream_error_type='upstream_unavailable', failure_stage='analyze')
    return error


@pytest.mark.usefixtures('isolated__r22_415')
@pytest.mark.parametrize('status', ['503;drop', '503', True, 302, 600, 503.0])
def test_i565_the_serializer_copies_only_whitelisted_valid_fields(status):
    out = export_attribution({**DIRTY, 'status': 'failed', 'http_status': status})
    assert set(out) <= WHITELIST__r31_415_payload
    assert 'http_status' not in out
    assert out['provider'] == 'kimi' and out['attribution_source'] == 'request'
    assert export_attribution({**DIRTY, 'status': 'failed', 'http_status': 503})['http_status'] == 503


@pytest.mark.usefixtures('isolated__r22_415')
def test_i565_the_serializer_drops_an_unknown_source_and_a_half_identity():
    out = export_attribution({'status': 'failed', 'attribution_source': 'guess', 'provider': 'kimi', 'model': 'm'})
    assert out == {}


@pytest.mark.usefixtures('isolated__r22_415')
def test_i565_store_read_projection_and_history_summary_carry_only_whitelisted_fields():
    pid = 'p565'
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    store.write(pid, {'id': pid, 'analysis': {'status': 'running', 'run_id': 'r1', 'phase': 'screening'}})
    path = store.directory(pid) / 'metadata' / 'studio.json'
    raw = json.loads(path.read_text())
    raw['analysis'] = {**raw['analysis'], **DIRTY, 'status': 'failed', 'error_code': 'provider_error'}
    path.write_text(json.dumps(raw))
    read = store.read(pid)['analysis']
    assert read.get('http_status') is None and read.get('provider') == 'kimi'
    store.write(pid, {**store.read(pid), 'analysis': {'status': 'running', 'run_id': 'r2', 'phase': 'screening'}})
    row = next(r for r in store.read(pid).get('analysis_history', []) if r['run_id'] == 'r1')['analysis']
    assert set(row) & set(DIRTY) <= WHITELIST__r31_415_payload
    _no_secret(row)
    assert row.get('provider') == 'kimi' and 'http_status' not in row


@pytest.mark.usefixtures('isolated__r22_415')
def test_i565_llm_emit_exits_carry_only_whitelisted_valid_fields():
    error = _dirty_error()
    fields = llm_emit.attribution(error)
    assert set(fields) <= WHITELIST__r31_415_payload and 'http_status' not in fields
    with llm_emit.track_run():
        snap = llm_emit.run_snapshot(error=error)
    assert snap.get('http_status') is None
    _no_secret(snap)
    tags = llm_emit.sentry_tags_for_error(error, 'analyze')
    assert 'http_status' not in tags and tags.get('provider') == 'kimi'
    _no_secret(tags)


@pytest.mark.usefixtures('isolated__r22_415')
def test_i565_sentry_failure_context_and_envelope_carry_only_whitelisted_valid_fields():
    error = _dirty_error()
    context = sentry_setup.studio_failure_context(error, 'analyze')
    assert set(context) <= {'failure_stage', 'http_status', 'upstream_error_type'}
    assert 'http_status' not in context
    events = _envelope_events(error, with_product_filter=True)
    for event in events:
        _no_secret({k: event.get(k) for k in ('tags', 'contexts', 'extra')})


@pytest.mark.usefixtures('isolated__r22_415')
def test_i565_write_attribution_stores_only_whitelisted_valid_fields():
    record = {'status': 'failed', 'raw_message': 'kept, not an attribution field'}
    failure_attribution.write_attribution(record, _dirty_error().attribution)
    assert 'http_status' not in record
    assert set(record) - {'status', 'raw_message'} <= WHITELIST__r31_415_payload


@pytest.mark.usefixtures('isolated__r22_415')
def test_i565_sentry_tags_take_no_identity_from_a_snapshot_whose_pair_is_invalid():
    """THE serializer's pair rule: provider/config_source that are not strings -> no identity at all, so
    model and host (valid on their own) do not go out as somebody's identity."""
    error = _Safe('safe text')
    error.attribution = FailureAttribution('request', provider=8, config_source=7, model='kimi-k2',
                                           base_url_host='kimi.fixture.example', http_status=503, failure_stage='analyze')
    tags = llm_emit.sentry_tags_for_error(error, 'analyze')
    assert not {'provider', 'model', 'base_url_host'} & set(tags), tags
    assert tags.get('http_status') == '503'


@pytest.mark.usefixtures('isolated__r22_415')
def test_i565_history_summary_of_a_dirty_terminal_the_writer_hands_in():
    """A writer hands a dirty failed terminal to store.write (no error in hand: the group it carries stays);
    its history row is built through THE serializer, not copied."""
    pid = 'p565w'
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    store.write(pid, {'id': pid, 'analysis': {**DIRTY, 'status': 'failed', 'run_id': 'r1', 'phase': 'screening',
                                              'error_code': 'provider_error'}})
    stored = json.loads((store.directory(pid) / 'metadata' / 'studio.json').read_text())  # what is on disk
    for row in (next(r for r in store.read(pid).get('analysis_history', []) if r['run_id'] == 'r1')['analysis'],
                next(r for r in stored.get('analysis_history', []) if r['run_id'] == 'r1')['analysis']):
        _no_secret(row)
        assert set(row) & set(DIRTY) <= WHITELIST__r31_415_payload and 'http_status' not in row
