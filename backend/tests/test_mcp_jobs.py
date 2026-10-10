"""Disk job records, the missing-job bug, and the gated MCP tools."""
import asyncio
import inspect
import json

import pytest

from backend.tests.test_cli import data_dir  # noqa: F401


def test_missing_record_stays_unknown_even_when_project_files_exist(data_dir):
    from backend.services import mcp_jobs
    from backend.tests.test_cli import _fake_project

    _fake_project(data_dir, 'p9', '磁盘项目')
    missing = mcp_jobs.lookup('p9')
    assert missing['ok'] is False and missing['status'] == 'unknown' and missing['error_code'] == 'unknown'
    assert 'result' not in missing
    assert missing['poll_after_sec'] == 0 and missing['eta'] == 0
    assert mcp_jobs.lookup('not a id')['error_code'] == 'invalid_input'


def test_completed_record_returns_result_without_project_files(data_dir):
    from backend.services import mcp_jobs

    mcp_jobs.write_job('p1', status='completed', progress=100, stage='done', error_code='none', result={'clips': 1})
    view = mcp_jobs.lookup('p1')
    assert view['ok'] is True and view['status'] == 'completed' and view['result'] == {'clips': 1}
    assert view['progress'] == 100 and view['stage'] == 'done' and view['eta'] == 0 and view['poll_after_sec'] == 0


def test_dead_worker_becomes_interrupted(data_dir):
    from backend.services import mcp_jobs

    mcp_jobs.write_job('p2', status='running', progress=40, stage='INGEST', pid=2_000_000_001,
                       pid_created_at=1.0, error_code='none')
    view = mcp_jobs.lookup('p2')
    assert view['ok'] is False and view['status'] == 'interrupted' and view['error_code'] == 'interrupted'
    assert view['stage'] == 'interrupted' and view['poll_after_sec'] == 0 and view['eta'] == 0
    stored = json.loads((data_dir / 'mcp-jobs' / 'p2.json').read_text(encoding='utf-8'))
    assert stored['status'] == 'interrupted'


def _process_gone(pid: int) -> bool:
    import psutil
    try:
        proc = psutil.Process(pid)
        status = proc.status()
    except psutil.NoSuchProcess:
        return True
    except psutil.Error:
        # Windows can deny a query while taskkill is still tearing the tree down.
        return False
    return status == psutil.STATUS_ZOMBIE


def _wait_until_gone(pid: int, timeout: float = 15) -> bool:
    import time
    deadline = time.time() + timeout
    while True:
        if _process_gone(pid):
            # A zombie still occupies the process table. Wait until it is reaped.
            import psutil
            try:
                psutil.Process(pid)
            except psutil.NoSuchProcess:
                return True
        if time.time() >= deadline:
            return False
        time.sleep(0.05)


def test_cancel_kills_the_process_group_and_clears_temporary_files(data_dir, tmp_path):
    """Start a real parent and grandchild, then cancel. Same path studio uses for ffmpeg."""
    import sys
    import threading
    import time
    from backend.core import project_cancellation as cancel
    from backend.services import mcp_jobs
    from backend.services.studio import store

    project = data_dir / 'projects' / 'pstop'
    studio = project / 'output' / 'studio'
    meta = project / 'metadata'
    studio.mkdir(parents=True)
    meta.mkdir(parents=True)
    finished = studio / 'done.mp4'
    finished.write_bytes(b'finished-video')
    partial = studio / 'done.part.mp4'
    partial.write_bytes(b'partial')
    scratch = project / 'scratch.tmp'
    marker = tmp_path / 'pids.txt'
    child = tmp_path / 'child.py'
    child.write_text(
        "import os, subprocess, sys, time\n"
        "from pathlib import Path\n"
        "scratch, marker = sys.argv[1:]\n"
        "Path(scratch).write_text('scratch', encoding='utf-8')\n"
        "grand = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        "Path(marker).write_text(f'{os.getpid()}\\n{grand.pid}\\n', encoding='utf-8')\n"
        "time.sleep(120)\n",
        encoding='utf-8',
    )
    (meta / 'studio.json').write_text(json.dumps({
        'schema_version': 2,
        'drafts': [],
        'jobs': [
            {'job_id': 'live', 'status': 'running', 'instance': store.INSTANCE},
            {'job_id': 'saved', 'status': 'completed', 'instance': store.INSTANCE},
        ],
        'output_variants': [
            {'id': 'running-variant', 'status': 'running'},
            {'id': 'saved-variant', 'status': 'completed'},
        ],
        'generation': {'status': 'rendering'},
        'analysis': None,
    }), encoding='utf-8')
    mcp_jobs.write_job('pstop', status='running', progress=30, stage='rendering', error_code='none')
    errors = []

    def worker():
        try:
            with cancel.bind('pstop'):
                cancel.note_temporary(scratch)
                cancel.run([sys.executable, str(child), str(scratch), str(marker)], timeout=30)
        except cancel.JobStopped:
            pass
        except Exception as error:  # noqa: BLE001 - the assertion below reports it
            errors.append(error)

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        deadline = time.time() + 15
        pids: list[int] = []
        while time.time() < deadline and len(pids) < 2:
            if marker.is_file():
                pids = [int(line) for line in marker.read_text(encoding='utf-8').split() if line.strip().isdigit()]
            time.sleep(0.05)
        assert len(pids) >= 2, errors
        parent_pid, grand_pid = pids
        cancelled = mcp_jobs.cancel('pstop')
        thread.join(timeout=20)
        assert not thread.is_alive()
        assert errors == []
        assert cancelled['status'] == 'cancelled' and cancelled['error_code'] == 'cancelled' and cancelled['ok'] is False
        assert not scratch.exists()
        assert not partial.exists()
        assert finished.read_bytes() == b'finished-video'
        assert _wait_until_gone(parent_pid)
        assert _wait_until_gone(grand_pid)
        saved = json.loads((meta / 'studio.json').read_text(encoding='utf-8'))
        jobs = {job['job_id']: job['status'] for job in saved['jobs']}
        variants = {item['id']: item['status'] for item in saved['output_variants']}
        assert jobs == {'live': 'cancelled', 'saved': 'completed'}
        assert variants == {'running-variant': 'cancelled', 'saved-variant': 'completed'}
        assert saved['generation']['status'] == 'cancelled'
    finally:
        cancel.stop('pstop')
        thread.join(timeout=5)
        cancel._stopped.discard('pstop')


def test_cancel_sticks_and_does_not_delete_files(data_dir):
    from backend.services import mcp_jobs

    project = data_dir / 'projects' / 'p3'
    project.mkdir(parents=True)
    (project / 'keep.txt').write_text('stay', encoding='utf-8')
    mcp_jobs.write_job('p3', status='running', progress=20, stage='screening', error_code='none')
    cancelled = mcp_jobs.cancel('p3')
    assert cancelled['status'] == 'cancelled' and cancelled['ok'] is False and cancelled['error_code'] == 'cancelled'
    mcp_jobs.write_job('p3', status='completed', progress=100, error_code='none', result={'ok': True})
    again = mcp_jobs.lookup('p3')
    assert again['status'] == 'cancelled' and again['ok'] is False and 'result' not in again
    assert (project / 'keep.txt').read_text(encoding='utf-8') == 'stay'


def test_job_file_strips_secrets_and_paths(data_dir):
    from backend.services import mcp_jobs

    mcp_jobs.write_job(
        'p4', status='completed', api_key='secret-token', video='/tmp/private/talk.mp4', error='failed at /tmp/private',
        result={'title': '成片', 'api_key': 'secret-token', 'apiKey': 'also-secret'},
    )
    raw = json.loads((data_dir / 'mcp-jobs' / 'p4.json').read_text(encoding='utf-8'))
    assert 'api_key' not in raw and 'video' not in raw and 'error' not in raw
    assert raw['result'] == {'title': '成片'}
    blob = json.dumps(raw)
    assert 'secret-token' not in blob and '/tmp/private' not in blob


def test_running_status_advertises_a_poll_interval(data_dir):
    from backend.services import mcp_jobs

    fields = mcp_jobs.progress_fields(status='running', progress=None, stage='screening', started_at=None)
    assert fields == {'status': 'running', 'progress': 0, 'stage': 'screening', 'eta': None, 'poll_after_sec': 10}


def test_new_tools_stay_hidden_until_the_flag_is_on(data_dir, monkeypatch):
    pytest.importorskip('mcp')
    from backend import mcp_server

    monkeypatch.delenv('AUTOCLIP_FLAGS', raising=False)
    assert mcp_server.list_styles()['error_code'] == 'disabled'
    assert mcp_server.cancel_job('p3')['error_code'] == 'disabled'
    hidden = {tool.name for tool in asyncio.run(mcp_server.server.list_tools())}
    assert 'list_styles' not in hidden and 'cancel_job' not in hidden

    monkeypatch.setenv('AUTOCLIP_FLAGS', 'mcp_v2_tools=on')
    visible = {tool.name: tool for tool in asyncio.run(mcp_server.server.list_tools())}
    assert 'list_styles' in visible and 'cancel_job' in visible
    styles = mcp_server.list_styles()
    assert styles['ok'] is True
    assert [row['id'] for row in styles['styles']] == ['editorial', 'street', 'classic']


def test_legacy_tools_are_deprecated_and_do_not_take_api_key(data_dir, monkeypatch):
    pytest.importorskip('mcp')
    from backend import mcp_server

    monkeypatch.delenv('AUTOCLIP_FLAGS', raising=False)
    for name in ('clip_video', 'start_clip_job', 'check_environment'):
        assert 'api_key' not in inspect.signature(getattr(mcp_server, name)).parameters
    tools = {tool.name: tool for tool in asyncio.run(mcp_server.server.list_tools())}
    clip = tools['clip_video']
    assert clip.description.startswith('deprecated:')
    assert clip.meta['deprecated'] is True
    assert 'api_key' not in clip.input_schema['properties']
    assert 'video_path' in clip.input_schema['properties']
    assert not (tools['get_version'].description or '').startswith('deprecated:')
    monkeypatch.setenv('AUTOCLIP_API_KEY', 'env-secret')
    override = mcp_server._make_override('openai', 'gpt-4o-mini', None)
    assert override.api_key == 'env-secret'
