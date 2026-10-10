"""MCP and CLI events stay anonymous and follow the analytics switch."""
import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
from pathlib import Path

import pytest

from backend.services import mcp_telemetry
from backend.services.studio.features import flag_enabled, resolve_features


@pytest.fixture(autouse=True)
def _reset():
    mcp_telemetry.reset_seen()
    yield
    mcp_telemetry.reset_seen()


def _capture(monkeypatch, tmp_path, *, analytics=True):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    monkeypatch.delenv('VITE_PUBLIC_POSTHOG_KEY', raising=False)
    monkeypatch.delenv('AUTOCLIP_FLAGS', raising=False)
    (tmp_path / 'privacy.json').write_text(json.dumps({'analytics': analytics, 'crash_reports': False}))
    (tmp_path / 'analytics.json').write_text('{"distinct_id":"018f6b2a-7c3d-7b2a-8c11-111111111111"}')
    captured = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def urlopen(req, timeout=0):
        captured.append(json.loads(req.data.decode()))
        return Resp()

    monkeypatch.setattr(mcp_telemetry.urllib.request, 'urlopen', urlopen)
    return captured


def test_analytics_off_sends_nothing(monkeypatch, tmp_path):
    captured = _capture(monkeypatch, tmp_path, analytics=False)
    mcp_telemetry.record('produce', 'cli', mcp_telemetry.time.perf_counter(), ok=True, error_code='none',
                         job_id='p1', terminal=True)
    mcp_telemetry.flush()
    assert captured == []


def test_properties_are_enums_and_job_finished_is_once(monkeypatch, tmp_path):
    captured = _capture(monkeypatch, tmp_path)
    started = mcp_telemetry.time.perf_counter()
    mcp_telemetry.record('produce', '/Users/private/Library/Cursor', started, ok=True, error_code='completed',
                         job_id='job-1', terminal=True)
    mcp_telemetry.record('produce', 'cli', started, ok=True, error_code='none', job_id='job-1', terminal=True)
    mcp_telemetry.flush()
    assert [row['event'] for row in captured] == ['mcp_tool_called', 'mcp_job_finished', 'mcp_tool_called']
    body = captured[1]
    assert body['distinct_id'] == '018f6b2a-7c3d-7b2a-8c11-111111111111'
    assert set(body['properties']) == {
        'tool', 'client', 'version', 'duration_ms', 'ok', 'error_code', '$feature/mcp_v2_tools',
    }
    assert body['properties']['tool'] == 'produce'
    assert body['properties']['client'] == 'unknown'
    assert body['properties']['ok'] is True
    assert body['properties']['error_code'] == 'none'
    assert body['properties']['$feature/mcp_v2_tools'] is False
    blob = json.dumps(body['properties'])
    assert 'phc_test' not in blob and 'private' not in blob and 'api_key' not in body['properties']
    assert flag_enabled(resolve_features({'autoclip_safe_mode': True, 'mcp_v2_tools': True}, env=''), 'mcp_v2_tools') is False


def test_paths_and_secrets_in_a_tool_result_are_not_properties():
    class Result:
        is_error = False
        structured_content = {
            'ok': False, 'project_id': '../secret/video.mp4', 'status': 'failed',
            'error': 'failed at /tmp/secret-video-path.mp4', 'api_key': 'super-secret-key',
        }

    ok, error_code, job_id, terminal = mcp_telemetry.outcome_from_result(Result())
    assert ok is False and error_code == 'failed' and job_id is None and terminal is True


def test_call_and_cli_do_not_copy_arguments(monkeypatch, tmp_path):
    pytest.importorskip('mcp')
    captured = _capture(monkeypatch, tmp_path)
    from backend import cli, mcp_server
    import asyncio

    asyncio.run(mcp_server.server.call_tool('get_version', {'api_key': 'super-secret-key', 'video': '/tmp/secret-video-path.mp4'}))
    args = cli.build_parser().parse_args(['produce', '/tmp/secret-video-path.mp4'])
    assert cli.cmd_produce(args) == 2
    mcp_telemetry.flush()
    blob = json.dumps(captured)
    assert 'super-secret-key' not in blob and 'secret-video-path' not in blob
    assert captured[0]['event'] == 'mcp_tool_called'
    assert captured[0]['properties']['tool'] in ('get_version', 'other')
    assert any(row['properties']['tool'] == 'produce' and row['properties']['error_code'] == 'invalid_input' for row in captured)


def test_record_does_not_block_the_caller_or_the_event_loop(monkeypatch, tmp_path):
    captured = _capture(monkeypatch, tmp_path)
    entered = threading.Event()
    release = threading.Event()

    def urlopen(req, timeout=0):
        entered.set()
        assert release.wait(2)
        captured.append(json.loads(req.data.decode()))
        return type('Resp', (), {'__enter__': lambda self: self, '__exit__': lambda self, *_args: False})()

    monkeypatch.setattr(mcp_telemetry.urllib.request, 'urlopen', urlopen)

    async def tick():
        await asyncio.sleep(0.05)
        return 'ticked'

    async def main():
        task = asyncio.create_task(tick())
        started = time.monotonic()
        mcp_telemetry.record('get_version', 'cli', time.perf_counter(), ok=True, error_code='none')
        elapsed = time.monotonic() - started
        assert elapsed < 0.2
        assert await asyncio.wait_for(task, 0.3) == 'ticked'
        return elapsed

    asyncio.run(main())
    release.set()
    mcp_telemetry.flush()
    assert entered.is_set()
    assert captured[0]['event'] == 'mcp_tool_called'


def test_job_finished_duration_is_the_task_and_restart_does_not_resend(monkeypatch, tmp_path):
    captured = _capture(monkeypatch, tmp_path)
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    from backend.services import mcp_jobs
    mcp_jobs.write_job('job-9', status='completed', progress=100, error_code='none', started_at=time.time() - 8)
    mcp_telemetry.record('get_quick_output_status', 'cli', time.perf_counter(), ok=True, error_code='none',
                         job_id='job-9', terminal=True)
    mcp_telemetry.flush()
    tool = next(row for row in captured if row['event'] == 'mcp_tool_called')
    finished = next(row for row in captured if row['event'] == 'mcp_job_finished')
    assert tool['properties']['duration_ms'] < 2000
    assert finished['properties']['duration_ms'] >= 7000
    marker = (tmp_path / 'mcp-events-seen.json').read_text(encoding='utf-8')
    assert 'job-9' not in marker
    mcp_telemetry.reset_seen()
    mcp_telemetry.record('get_quick_output_status', 'cli', time.perf_counter(), ok=True, error_code='none',
                         job_id='job-9', terminal=True)
    mcp_telemetry.flush()
    assert [row['event'] for row in captured].count('mcp_job_finished') == 1
    assert [row['event'] for row in captured].count('mcp_tool_called') == 2


def test_a_failed_post_is_not_marked_sent(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    monkeypatch.delenv('VITE_PUBLIC_POSTHOG_KEY', raising=False)
    (tmp_path / 'privacy.json').write_text(json.dumps({'analytics': True, 'crash_reports': False}))
    (tmp_path / 'analytics.json').write_text('{"distinct_id":"018f6b2a-7c3d-7b2a-8c11-111111111111"}')

    def fail(req, timeout=0):
        raise urllib.error.URLError('down')

    monkeypatch.setattr(mcp_telemetry.urllib.request, 'urlopen', fail)
    mcp_telemetry.record('get_quick_output_status', 'cli', time.perf_counter(), ok=False, error_code='failed',
                         job_id='job-fail', terminal=True)
    mcp_telemetry.flush()
    marker = tmp_path / 'mcp-events-seen.json'
    assert not marker.exists()

    captured = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def succeed(req, timeout=0):
        captured.append(json.loads(req.data.decode()))
        return Resp()

    monkeypatch.setattr(mcp_telemetry.urllib.request, 'urlopen', succeed)
    mcp_telemetry.record('get_quick_output_status', 'cli', time.perf_counter(), ok=False, error_code='failed',
                         job_id='job-fail', terminal=True)
    mcp_telemetry.flush()
    assert [row['event'] for row in captured].count('mcp_job_finished') == 1
    assert marker.is_file()
    assert 'job-fail' not in marker.read_text(encoding='utf-8')


def test_flush_returns_when_the_timeout_expires(monkeypatch, tmp_path):
    _capture(monkeypatch, tmp_path)
    release = threading.Event()

    def urlopen(req, timeout=0):
        release.wait(5)
        return type('Resp', (), {'__enter__': lambda self: self, '__exit__': lambda self, *_args: False})()

    monkeypatch.setattr(mcp_telemetry.urllib.request, 'urlopen', urlopen)
    mcp_telemetry.record('get_version', 'cli', time.perf_counter(), ok=True, error_code='none')
    started = time.monotonic()
    mcp_telemetry.flush(0.2)
    elapsed = time.monotonic() - started
    release.set()
    mcp_telemetry.flush(2)
    assert 0.15 <= elapsed < 1.0


def _exit_script(body: str) -> str:
    return (
        'import json, os, time\n'
        'from pathlib import Path\n'
        'app = Path(os.environ["APP"])\n'
        '(app / "privacy.json").write_text(json.dumps({"analytics": True, "crash_reports": False}))\n'
        '(app / "analytics.json").write_text(\'{"distinct_id":"018f6b2a-7c3d-7b2a-8c11-111111111111"}\')\n'
        'from backend.services import mcp_telemetry\n'
        + body
        + 'mcp_telemetry.record("get_version", "cli", mcp_telemetry.time.perf_counter(), ok=True, error_code="none")\n'
    )


def test_process_exit_flushes_the_queue(tmp_path):
    out = tmp_path / 'posted.json'
    script = _exit_script(
        'out = Path(os.environ["OUT"])\n'
        'def urlopen(req, timeout=0):\n'
        '    out.write_text(req.data.decode())\n'
        '    class R:\n'
        '        def __enter__(self): return self\n'
        '        def __exit__(self, *a): return False\n'
        '    return R()\n'
        'mcp_telemetry.urllib.request.urlopen = urlopen\n'
    )
    env = os.environ.copy()
    env.update(APP=str(tmp_path), OUT=str(out), AUTOCLIP_APP_DIR=str(tmp_path), AUTOCLIP_POSTHOG_KEY='phc_test')
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[2]) + os.pathsep + env.get('PYTHONPATH', '')
    completed = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(out.read_text(encoding='utf-8'))['event'] == 'mcp_tool_called'


def test_process_exit_stops_waiting_after_two_seconds(tmp_path):
    script = _exit_script(
        'def urlopen(req, timeout=0):\n'
        '    time.sleep(30)\n'
        '    class R:\n'
        '        def __enter__(self): return self\n'
        '        def __exit__(self, *a): return False\n'
        '    return R()\n'
        'mcp_telemetry.urllib.request.urlopen = urlopen\n'
    )
    env = os.environ.copy()
    env.update(APP=str(tmp_path), AUTOCLIP_APP_DIR=str(tmp_path), AUTOCLIP_POSTHOG_KEY='phc_test')
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[2]) + os.pathsep + env.get('PYTHONPATH', '')
    started = time.monotonic()
    completed = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=10)
    elapsed = time.monotonic() - started
    assert completed.returncode == 0, completed.stderr
    assert elapsed < 4
