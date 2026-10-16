"""R21 #194-#202 for #415: each test fails on c6938ff8 and passes after the fix."""
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from backend.core import llm_emit
from backend.services import ai_model_settings as ai
from backend.services.studio import failure_identity, shutdown_marker, store

ROOT = Path(__file__).resolve().parents[2]
OLD = 'f' * 32
TEXT = {'provider': 'deepseek', 'config_source': 'preset'}
EYES = {'provider': 'kimi', 'config_source': 'customized'}
VISUAL_PLAN = {'recommended_analysis': 'visual', 'confirmed_analysis': 'visual', 'preferences': {'goal': 'highlight'}}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.delenv('AUTOCLIP_SHUTDOWN_MARKER_DIR', raising=False)
    shutdown_marker._consumed.clear()


@pytest.fixture
def two_connections(monkeypatch):
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


def _project(pid, data):
    meta = store.directory(pid) / 'metadata'
    meta.mkdir(parents=True, exist_ok=True)
    (meta / 'studio.json').write_text(json.dumps(data), encoding='utf-8')
    return meta / 'studio.json'


def _vision_failure():
    llm_emit.emit_vision_request(config={'model': 'private-vision-model', 'base_url': 'https://vision.fixture.example/v1'},
                                 started=time.monotonic(), error=RuntimeError('fixture'))


# --- #194 -------------------------------------------------------------------------------------

@pytest.mark.parametrize('phase,plan,goals,role', [
    ('screening', None, None, 'vision'),
    ('production', VISUAL_PLAN, None, 'vision'),
    ('production', VISUAL_PLAN, ['content'], 'analysis'),
    ('production', VISUAL_PLAN, ['content', 'promo'], 'vision'),
    ('production', {'recommended_analysis': 'subtitle', 'preferences': {'goal': 'content'}}, None, 'analysis'),
    ('analysis', None, None, 'analysis'),
])
def test_194_role_follows_phase_and_route(phase, plan, goals, role):
    assert failure_identity.role_for(phase, plan, goals) == role


def test_194_screening_and_visual_production_freeze_the_vision_identity(two_connections):
    assert failure_identity.phase_identity('screening') == EYES
    assert failure_identity.phase_identity('production', VISUAL_PLAN, ['highlight']) == EYES
    assert failure_identity.phase_identity('production', VISUAL_PLAN, ['content']) == TEXT


def test_194_every_studio_start_and_terminal_uses_the_phase_resolver():
    import inspect
    from backend.services.studio import jobs
    src = inspect.getsource(jobs)
    assert 'provider_identity()' not in src                       # no default-analysis identity left
    assert "phase_identity('screening')" in inspect.getsource(jobs.inspect_project) and "phase_identity('screening')" in inspect.getsource(jobs._inspect)
    assert "phase_identity('production', plan, body.goals)" in inspect.getsource(jobs.confirm_project)
    assert "phase_identity('production', plan)" in inspect.getsource(jobs._inspect)
    assert "phase_identity('production', plan)" in inspect.getsource(jobs._auto_generate)


def test_194_visual_production_start_request_terminal_all_name_the_vision_connection(two_connections):
    start = failure_identity.phase_identity('production', VISUAL_PLAN, ['highlight'])
    _project('p194', {'id': 'p194', 'analysis': {**start, 'status': 'running', 'phase': 'production', 'run_id': 'r'}})
    with llm_emit.track_run():
        _vision_failure()
        snap = llm_emit.run_snapshot()
        store.change('p194', lambda d: d['analysis'].update(status='failed', error_code='timeout', failure_stage='production'))
    analysis = store.read('p194')['analysis']
    assert {k: analysis.get(k) for k in EYES} == EYES
    assert {k: snap.get(k) for k in EYES} == EYES


# --- #195 -------------------------------------------------------------------------------------

def test_195_snapshot_provider_and_config_source_come_from_one_connection(two_connections):
    with llm_emit.track_run():
        _vision_failure()
        snap = llm_emit.run_snapshot()
    assert (snap.get('provider'), snap.get('config_source')) == ('kimi', 'customized')


def test_195_mid_run_settings_change_does_not_split_the_snapshot_identity(two_connections):
    with llm_emit.track_run():
        _vision_failure()
        settings = ai.load()
        ai.save(settings.model_copy(update={'vision': ai.Assignment(connection_id='text', model='deepseek-flash', capability='multimodal')}))
        snap = llm_emit.run_snapshot()
    assert (snap.get('provider'), snap.get('config_source')) == ('kimi', 'customized')


# --- #196 -------------------------------------------------------------------------------------

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


def test_202_mark_on_the_quit_path_never_scans_projects(monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 1)
    _records(shutdown_marker._root(), [f'{i:032x}' for i in range(1, 30)])
    scans = []
    monkeypatch.setattr(store, 'reference_index', lambda: scans.append(1) or (set(), None))
    started = time.monotonic()
    assert shutdown_marker.mark('user_quit', 'e' * 32)
    assert scans == [] and time.monotonic() - started < 1


def test_202_prune_scans_projects_once_however_many_records(monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 1)
    root = shutdown_marker._root()
    _records(root, [f'{i:032x}' for i in range(1, 30)])
    real, scans = store.reference_index, []
    monkeypatch.setattr(store, 'reference_index', lambda: scans.append(1) or real())
    shutdown_marker.prune()
    assert scans == [1]
    assert len(list(root.iterdir())) == 1


# --- #198 -------------------------------------------------------------------------------------

def test_198_one_unreadable_project_only_protects_records_it_could_reference(monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 0)
    root = shutdown_marker._root()
    old, newer = OLD, 'a' * 32
    _records(root, [old, newer], base=1000)
    bad = _project('broken', {})
    bad.write_text('{not json', encoding='utf-8')
    os.utime(bad, (1000.5, 1000.5))                                            # written after `old` ended
    shutdown_marker.prune()
    left = {p.name for p in root.iterdir()}
    assert old not in left                                                     # cannot be the broken file's
    assert newer in left                                                       # might be: keep


def test_198_release_is_not_blocked_by_an_unrelated_unreadable_project(tmp_path):
    root = shutdown_marker._root()
    _records(root, [OLD], base=2000)
    bad = _project('broken', {})
    bad.write_text('{not json', encoding='utf-8')
    os.utime(bad, (3000, 3000))
    assert shutdown_marker.shutdown_kind(OLD) == 'unknown'
    shutdown_marker.release(OLD)
    assert not (root / OLD).exists()


# --- #199 -------------------------------------------------------------------------------------

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
def test_201_every_reference_branch_keeps_the_record(data, monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 0)
    root = shutdown_marker._root()
    _records(root, [OLD])
    _project('ref', {'id': 'ref', **data})
    shutdown_marker.prune()
    assert (root / OLD).exists()


@pytest.mark.parametrize('data', [
    {'jobs': [{'status': 'completed', 'instance': OLD}]},
    {'output_variants': [{'status': 'failed', 'instance': OLD, 'render_dispatch_instance': OLD}]},
])
def test_201_settled_state_does_not_keep_the_record(data, monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 0)
    root = shutdown_marker._root()
    _records(root, [OLD])
    _project('ref', {'id': 'ref', **data})
    shutdown_marker.prune()
    assert not (root / OLD).exists()


def test_201_preset_provider_survives_the_real_request_sender(monkeypatch):
    from backend.core.provider_presets import iter_providers
    sent = []
    monkeypatch.setattr(llm_emit, '_post_event', lambda event, props: sent.append(props))
    for preset in [p.id for p in iter_providers()]:
        llm_emit.request_finished(provider=preset, model='m', kind='text', outcome='success')
    assert [p['provider'] for p in sent] == [p.id for p in iter_providers()]
