"""MCP and CLI events stay anonymous and follow the analytics switch."""
import json

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
    assert captured == []


def test_properties_are_enums_and_job_finished_is_once(monkeypatch, tmp_path):
    captured = _capture(monkeypatch, tmp_path)
    started = mcp_telemetry.time.perf_counter()
    mcp_telemetry.record('produce', '/Users/private/Library/Cursor', started, ok=True, error_code='completed',
                         job_id='job-1', terminal=True)
    mcp_telemetry.record('produce', 'cli', started, ok=True, error_code='none', job_id='job-1', terminal=True)
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
    blob = json.dumps(captured)
    assert 'super-secret-key' not in blob and 'secret-video-path' not in blob
    assert captured[0]['event'] == 'mcp_tool_called'
    assert captured[0]['properties']['tool'] in ('get_version', 'other')
    assert any(row['properties']['tool'] == 'produce' and row['properties']['error_code'] == 'invalid_input' for row in captured)
