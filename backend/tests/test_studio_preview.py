import json
import subprocess
import pytest
from backend.tests.test_studio import root, source, client
from backend.services.studio import preview
from backend.utils.ffmpeg_utils import get_ffmpeg_path, get_ffprobe_path


class Immediate:
    def submit(self, fn, *args):
        fn(*args)


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setattr(preview, '_states', {})
    monkeypatch.setattr(preview, '_executor', Immediate())


def test_explicit_preview_transcodes_avi_preserves_source_and_serves_ranges(client, source):
    avi = source.with_suffix('.avi')
    subprocess.run([get_ffmpeg_path(), '-v', 'error', '-i', str(source), '-c:v', 'mpeg4',
                    '-c:a', 'pcm_s16le', '-y', str(avi)], check=True, capture_output=True)
    source.unlink()
    original = avi.read_bytes()
    assert client.get('/studio/p1/source-preview').json()['status'] == 'idle'
    assert client.get('/studio/p1/source-preview/video').status_code == 404
    response = client.post('/studio/p1/source-preview')
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'completed', response.text
    output = preview.ready_file('p1')
    streams = json.loads(subprocess.check_output([get_ffprobe_path(), '-v', 'error',
                        '-show_streams', '-of', 'json', str(output)]))['streams']
    assert [s['codec_name'] for s in streams] == ['h264', 'aac']
    assert streams[0]['pix_fmt'] == 'yuv420p'
    assert avi.read_bytes() == original
    modified = output.stat().st_mtime_ns
    assert client.post('/studio/p1/source-preview').json()['status'] == 'completed'
    assert output.stat().st_mtime_ns == modified
    response = client.get('/studio/p1/source-preview/video', headers={'Range': 'bytes=0-99'})
    assert response.status_code == 206 and len(response.content) == 100
    assert response.headers['content-type'] == 'video/mp4'
    output.unlink()
    assert client.get('/studio/p1/source-preview').json()['status'] == 'idle'
    assert client.post('/studio/p1/source-preview').json()['status'] == 'completed'
    avi.write_bytes(original + b'changed')
    assert client.get('/studio/p1/source-preview').json()['status'] == 'idle'


def test_timeout_is_retryable_and_partial_file_is_removed(source, monkeypatch):
    def fail(command, **kwargs):
        assert kwargs['timeout'] == 900
        from pathlib import Path
        Path(command[-1]).write_bytes(b'partial')
        raise subprocess.TimeoutExpired(command, 900)
    monkeypatch.setattr(preview.subprocess, 'run', fail)
    monkeypatch.setattr(preview, 'capture_studio_exception', lambda *a: None)
    assert preview.start('p1')['status'] == 'failed'
    assert not list((source.parent.parent / 'output' / 'preview').glob('*.mp4'))
    assert preview.start('p1')['status'] == 'failed'


def test_duplicate_start_and_global_capacity(source, monkeypatch):
    calls = []
    class Queued:
        def submit(self, *args): calls.append(args)
    monkeypatch.setattr(preview, '_executor', Queued())
    assert preview.start('p1')['status'] == 'queued'
    assert preview.start('p1')['status'] == 'queued'
    assert len(calls) == 1
    source.write_bytes(source.read_bytes() + b'changed')
    with pytest.raises(ValueError): preview.start('p1')


def test_dispatch_failure_does_not_leave_queued_state(source, monkeypatch):
    class Rejected:
        def submit(self, *args): raise RuntimeError('closed executor')
    monkeypatch.setattr(preview, '_executor', Rejected())
    with pytest.raises(ValueError): preview.start('p1')
    assert preview.status('p1')['status'] == 'idle'
