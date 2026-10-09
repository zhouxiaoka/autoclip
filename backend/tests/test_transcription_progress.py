"""RC156 Win QA #14a: transcription progress advances by processed audio duration."""
import json
from types import SimpleNamespace

import pytest

from backend.services import simple_pipeline_adapter as adapter
from backend.services.studio import store
from backend.tests.test_whisper_local_subtitle import _install_fake_whisper, _recognizer
from backend.utils import transcription_progress
from backend.utils.speech_recognizer import SpeechRecognitionConfig


def test_report_clamps_and_needs_a_receiver():
    seen = []
    transcription_progress.report(10, 100)  # no receiver: no-op
    with transcription_progress.reporting(seen.append):
        transcription_progress.report(25, 100)
        transcription_progress.report(150, 100)
        transcription_progress.report(5, 0)       # unknown duration: ignored
        transcription_progress.report(None, None)
    transcription_progress.report(50, 100)
    assert seen == [0.25, 1.0]


def test_display_failure_never_stops_transcription_but_a_delete_does():
    def broken(_):
        raise RuntimeError('ui store busy')
    with transcription_progress.reporting(broken):
        transcription_progress.report(1, 2)
    from backend.core.project_cancellation import ProjectDeleted
    def deleted(_):
        raise ProjectDeleted('p')
    with transcription_progress.reporting(deleted), pytest.raises(ProjectDeleted):
        transcription_progress.report(1, 2)


def test_local_whisper_reports_each_decoded_segment_against_total_audio(tmp_path, monkeypatch):
    monkeypatch.delenv("AUTOCLIP_WHISPER_DEVICE", raising=False)
    total = 2125.0  # the 35:25 source from the acceptance run

    class FakeModel:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, path, **kwargs):
            def lazy():
                for end in (300.0, 900.0, 1500.0, 2125.0):
                    yield SimpleNamespace(start=end - 5, end=end, text='片段', words=[])
            return lazy(), SimpleNamespace(language='zh', duration=total)

    _install_fake_whisper(monkeypatch, FakeModel)
    video = tmp_path / 'long.mp4'
    video.write_bytes(b'video')
    seen = []
    with transcription_progress.reporting(seen.append):
        _recognizer()._generate_subtitle_whisper_local(video, tmp_path / 'long.srt', SpeechRecognitionConfig())
    assert seen[:4] == pytest.approx([300 / total, 900 / total, 1500 / total, 1.0])
    assert seen[-1] == 1.0


@pytest.fixture
def studio_project(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (store.directory('p') / 'metadata').mkdir(parents=True)
    store.write('p', {'generation': {'status': 'production', 'auto_start': True}, 'drafts': [], 'jobs': [], 'output_variants': [],
                      'analysis': {'status': 'running', 'phase': 'production', 'message': adapter.STUDIO_PRODUCTION_MESSAGE, 'instance': store.INSTANCE}})
    emitted = []
    monkeypatch.setattr(adapter, 'emit_progress', lambda pid, stage, message='', subpercent=None: emitted.append((stage, subpercent)))
    return emitted


def test_studio_shows_percent_of_audio_processed_and_restores_the_stage_message(studio_project, monkeypatch):
    clock = iter(range(0, 1000, 5))
    monkeypatch.setattr('time.monotonic', lambda: next(clock))
    progress = adapter.TranscriptionProgress('p')
    seen = []
    for fraction in (0.0, 0.141, 0.423, 0.706, 1.0):
        progress(fraction)
        analysis = store.read('p')['analysis']
        seen.append((analysis['message'], analysis['percent']))
    assert seen == [('正在生成字幕', 0), ('正在生成字幕', 14), ('正在生成字幕', 42), ('正在生成字幕', 70), ('正在生成字幕', 100)]
    # The project progress bar moves smoothly across most of SUBTITLE (5 → 95 sub-steps), monotonic.
    subs = [sub for stage, sub in studio_project]
    assert all(stage == 'SUBTITLE' for stage, _ in studio_project)
    assert subs == sorted(subs) and subs[0] == 5 and subs[-1] == 95 and len(set(subs)) == 5
    adapter.TranscriptionProgress.finish_studio('p')
    analysis = store.read('p')['analysis']
    assert analysis['message'] == adapter.STUDIO_PRODUCTION_MESSAGE and 'percent' not in analysis


def test_updates_are_throttled_to_whole_percent_steps(studio_project, monkeypatch):
    now = [0.0]
    monkeypatch.setattr('time.monotonic', lambda: now[0])
    progress = adapter.TranscriptionProgress('p', interval=2.0)
    progress(0.10)
    now[0] = 0.5
    progress(0.20)  # too soon
    now[0] = 3.0
    progress(0.205)  # same whole percent as last shown? no: 20 > 10, allowed
    progress(0.205)  # repeated percent: skipped
    now[0] = 3.1
    progress(1.0)    # completion always shows
    assert [sub for _, sub in studio_project] == pytest.approx([5 + 9.0, 5 + 90 * 0.205, 95])


def test_legacy_project_without_studio_state_is_never_given_one(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    store.directory('legacy').mkdir(parents=True)
    monkeypatch.setattr(adapter, 'emit_progress', lambda *a, **k: None)
    adapter.TranscriptionProgress('legacy')(0.5)
    adapter.TranscriptionProgress.finish_studio('legacy')
    assert not (store.directory('legacy') / 'metadata' / 'studio.json').exists()


def test_delete_during_transcription_stops_it(studio_project):
    from backend.core import project_cancellation
    project_cancellation.cancel('p')
    try:
        with pytest.raises(project_cancellation.ProjectDeleted):
            adapter.TranscriptionProgress('p')(0.3)
    finally:
        project_cancellation.restore('p')
