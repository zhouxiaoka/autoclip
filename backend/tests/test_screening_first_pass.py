"""B3: the first screening pass names the source, and a thumbnail miss does not fail it.

A locked or unreadable file used to be stored as screening / unexpected. The retry then
probed the same file and reported source_no_audio or source_unreadable.
"""
import subprocess
from pathlib import Path

import pytest

from backend.core import sentry_setup
from backend.core.failure_codes import sentence, user_visible_error
from backend.pipeline import media_precheck
from backend.pipeline.failures import PipelineFailure
from backend.services.studio.models import ImportOptions

pytestmark = pytest.mark.real_media_probe


class _Row:
    def __init__(self):
        self.id = 'p1'
        self.video_path = None
        self.thumbnail = None
        self.status = None
        self.processing_config = {}
        self.completed_at = None
        self.committed = False


class _Query:
    def __init__(self, row):
        self._row = row

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._row


class _DB:
    def __init__(self, row):
        self.row = row
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def query(self, model):
        return _Query(self.row)

    def commit(self):
        self.row.committed = True


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"crash_reports":false}', encoding='utf-8')
    from backend.services.studio import jobs, store
    row = _Row()
    monkeypatch.setattr('backend.core.database.SessionLocal', lambda: _DB(row))
    monkeypatch.setattr(jobs, '_ensure_source_resolution', lambda *a, **k: 0)
    monkeypatch.setattr(jobs, '_fetch_platform_subtitles', lambda *a, **k: False)

    def land(url, options):
        folder = Path(options['outtmpl']).parent
        (folder / 'input.mp4').write_bytes(b'\x00\x00\x00\x18ftypmp42')
        (folder / 'input.info.json').write_text('{"title":"t","channel":"c"}', encoding='utf-8')

    monkeypatch.setattr('backend.utils.download_recovery.download_with_recovery', land)
    store.directory('p1').mkdir(parents=True, exist_ok=True)
    return jobs, store, row


def _seed(store, auto_start=False):
    store.write('p1', {
        'schema_version': 2,
        'drafts': [],
        'events': [],
        'jobs': [],
        'output_variants': [],
        'generation': {'status': 'screening', 'auto_start': auto_start, 'requested_platforms': ['douyin']},
        'analysis': {'status': 'running', 'phase': 'screening', 'run_id': 'run-1', 'instance': store.INSTANCE},
    })


def test_local_io_codes_are_not_unexpected():
    sharing = OSError('synthetic sharing violation')
    sharing.winerror = 32
    locked = OSError('synthetic lock violation')
    locked.winerror = 33
    denied = PermissionError('private-local-file')
    denied.winerror = 32
    plain = PermissionError('controlled metadata read denial')
    ffmpeg = subprocess.CalledProcessError(1, ['ffmpeg', 'private-input'])
    assert sentry_setup.studio_error_code(sharing) == 'file_locked'
    assert sentry_setup.studio_error_code(locked) == 'file_locked'
    assert sentry_setup.studio_error_code(denied) == 'file_locked'
    assert sentry_setup.studio_error_code(plain) == 'unexpected'
    assert sentry_setup.studio_error_code(ffmpeg) == 'frame_extract_failed'
    assert sentry_setup.studio_error_code(OSError('unrelated io')) == 'unexpected'
    assert 'file_locked' in sentry_setup.UNREPORTED_STUDIO_ERROR_CODES
    visible = user_visible_error(denied)
    assert visible == sentence('file_locked')
    assert 'private-local-file' not in visible and 'WinError' not in visible
    assert user_visible_error(ffmpeg) == sentence('frame_extract_failed')
    assert 'private-input' not in user_visible_error(ffmpeg)


def test_thumbnail_raise_does_not_fail_download_or_screening(monkeypatch, tmp_path):
    jobs, store, row = _isolate(monkeypatch, tmp_path)
    _seed(store)
    calls = []

    def boom(*args, **kwargs):
        calls.append('thumbnail')
        raise RuntimeError('thumbnail exploded')

    monkeypatch.setattr(media_precheck, 'probe', lambda video: {'duration': 45.0, 'audio': True})
    monkeypatch.setattr('backend.utils.thumbnail_generator.generate_project_thumbnail', boom)
    monkeypatch.setattr(
        'backend.services.studio.planning.recommend',
        lambda video, options: {
            'preferences': {'goal': 'highlight', 'language': 'source', 'aspect': 'original', 'duration': 30},
            'recommended_analysis': 'subtitle',
        },
    )
    jobs._inspect('p1', ImportOptions(auto_start=False), 'https://www.bilibili.com/video/BV1synthetic', None)
    state = store.read('p1')
    assert state['analysis']['status'] == 'awaiting_confirmation'
    assert 'error_code' not in state['analysis']
    assert row.committed and row.video_path and row.thumbnail is None
    assert calls == ['thumbnail']


def test_probe_after_download_maps_no_audio_before_recommend(monkeypatch, tmp_path):
    jobs, store, row = _isolate(monkeypatch, tmp_path)
    _seed(store, auto_start=True)
    monkeypatch.setattr(media_precheck, 'probe', lambda video: {'duration': 45.0, 'audio': False})
    monkeypatch.setattr('backend.services.studio.planning.recommend', lambda *a, **k: pytest.fail('recommend must not run'))
    monkeypatch.setattr('backend.utils.thumbnail_generator.generate_project_thumbnail', lambda *a, **k: pytest.fail('thumbnail must not run'))
    jobs._inspect('p1', ImportOptions(auto_start=True, goal='content'), 'https://www.bilibili.com/video/BV1synthetic', None)
    state = store.read('p1')
    assert state['analysis']['status'] == 'failed'
    assert state['analysis']['phase'] == 'screening'
    assert state['analysis']['error_code'] == 'source_no_audio'
    assert state['analysis']['error'] == media_precheck.NO_AUDIO_MESSAGE
    assert state['generation']['error_code'] == 'source_no_audio'
    assert row.video_path is None  # refused before the project row is updated


def test_probe_after_download_maps_unreadable(monkeypatch, tmp_path):
    jobs, store, row = _isolate(monkeypatch, tmp_path)
    _seed(store)
    monkeypatch.setattr(media_precheck, 'probe', lambda video: {'duration': None, 'audio': None})
    monkeypatch.setattr(media_precheck, 'ffmpeg_decode_duration', lambda video: (None, 'synthetic decode failure'))
    monkeypatch.setattr('backend.services.studio.planning.recommend', lambda *a, **k: pytest.fail('recommend must not run'))
    jobs._inspect('p1', ImportOptions(), 'https://www.bilibili.com/video/BV1synthetic', None)
    state = store.read('p1')
    assert state['analysis']['error_code'] == 'source_unreadable'
    assert state['analysis']['error'] == media_precheck.UNREADABLE_MESSAGE
    assert 'synthetic' not in state['analysis']['error']
    assert row.video_path is None


def test_silent_visual_route_is_not_refused_at_landing(monkeypatch, tmp_path):
    jobs, store, row = _isolate(monkeypatch, tmp_path)
    video = store.directory('p1') / 'raw' / 'input.mp4'
    video.parent.mkdir(parents=True)
    video.write_bytes(b'\x00\x00\x00\x18ftypmp42')
    from backend.services.studio import analysis_preferences, intelligence
    monkeypatch.setattr(analysis_preferences, 'load', lambda: analysis_preferences.AnalysisPreferences(
        analysis_mode='visual', allow_visual_screening=True))
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(media_precheck, 'probe', lambda path: {'duration': 45.0, 'audio': False})
    jobs._classify_landed_source(video, ImportOptions(auto_start=True))
    assert row.video_path is None


def test_attached_srt_keeps_a_silent_download(monkeypatch, tmp_path):
    jobs, store, _row = _isolate(monkeypatch, tmp_path)
    video = store.directory('p1') / 'raw' / 'input.mp4'
    video.parent.mkdir(parents=True)
    video.write_bytes(b'\x00\x00\x00\x18ftypmp42')
    (video.parent / 'input.srt').write_text('1\n00:00:00,000 --> 00:00:30,000\n你好\n', encoding='utf-8')
    monkeypatch.setattr(media_precheck, 'probe', lambda path: {'duration': 45.0, 'audio': False})
    jobs._classify_landed_source(video, ImportOptions(auto_start=True, goal='content'))


def _sharing_permission():
    error = PermissionError('synthetic output permission')
    error.winerror = 32
    return error


@pytest.mark.parametrize('error,code', [
    (_sharing_permission(), 'file_locked'),
    (subprocess.CalledProcessError(1, ['ffprobe']), 'frame_extract_failed'),
])
def test_inspect_records_io_failures_instead_of_unexpected(monkeypatch, tmp_path, error, code):
    jobs, store, _row = _isolate(monkeypatch, tmp_path)
    _seed(store)

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(jobs, 'download', fail)
    jobs._inspect('p1', ImportOptions(), 'https://www.bilibili.com/video/BV1synthetic', None)
    state = store.read('p1')
    assert state['analysis']['status'] == 'failed'
    assert state['analysis']['error_code'] == code
    assert state['analysis']['error_code'] != 'unexpected'
    assert 'synthetic' not in state['analysis']['error']
    assert 'ffprobe' not in state['analysis']['error']


def test_inspect_records_winerror_32_as_file_locked(monkeypatch, tmp_path):
    jobs, store, _row = _isolate(monkeypatch, tmp_path)
    _seed(store, auto_start=True)
    sharing = OSError('synthetic sharing violation')
    sharing.winerror = 32

    def fail(*args, **kwargs):
        raise sharing

    monkeypatch.setattr(jobs, 'download', fail)
    jobs._inspect('p1', ImportOptions(auto_start=True), 'https://www.bilibili.com/video/BV1synthetic', None)
    state = store.read('p1')
    assert state['analysis']['error_code'] == 'file_locked'
    assert state['generation']['error_code'] == 'file_locked'
    assert state['analysis']['error'] == sentence('file_locked')
    assert isinstance(sharing, OSError) and not isinstance(sharing, PermissionError)


def test_download_raises_the_probe_failure_itself(monkeypatch, tmp_path):
    jobs, _store, row = _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(media_precheck, 'probe', lambda video: {'duration': 45.0, 'audio': False})
    with pytest.raises(PipelineFailure) as caught:
        jobs.download('p1', 'https://www.bilibili.com/video/BV1synthetic', None, ImportOptions(goal='content'))
    assert caught.value.code == 'source_no_audio'
    assert sentry_setup.studio_error_code(caught.value) == 'source_no_audio'
    assert row.committed is False
