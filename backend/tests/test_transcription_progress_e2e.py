"""RC156 Win QA #22: transcription progress has to reach what the user actually sees.

#301 unit-tested `TranscriptionProgress` but the acceptance run still showed the project bar
stuck at 14% → 15% → 16% for a 35-minute transcription. This drives the packaged app's real
path end to end:

    studio.jobs.run_content
      → tasks.processing.process_video_pipeline.apply(clips_only=True).get()
        → SimplePipelineAdapter.process_project_sync → _generate_subtitle_automatically
          → speech_recognizer.generate_subtitle_for_video → transcription_progress.report
            → simple_progress.emit_progress (real SQLite progress store) + Studio store

and reads the result back through the two endpoints the UI polls while transcribing:
`GET /api/v1/simple-progress/snapshot` (home card / project bar) and `GET /api/v1/studio/{id}`
(Studio 「正在生成字幕 · N%」).
"""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.models.base import Base
from backend.models.project import Project, ProjectStatus

TOTAL = 2125.0  # the 35:25 source from the acceptance run
SRT = "1\n00:00:00,000 --> 00:00:05,000\n第一句\n\n2\n00:00:05,000 --> 00:00:10,000\n第二句\n"


@pytest.fixture
def app_path(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.delenv('AUTOCLIP_LLM_CACHE_DIR', raising=False)
    from backend.core import llm_manager, path_utils
    from backend.pipeline import media_precheck
    from backend.services import simple_pipeline_adapter as adapter
    from backend.services import simple_progress
    from backend.services.studio import store
    from backend.tasks import processing

    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    @contextmanager
    def scope():
        session = sessions()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    monkeypatch.setattr(processing, 'session_scope', scope)
    monkeypatch.setattr('backend.core.database.SessionLocal', sessions)
    monkeypatch.setattr(processing, 'run_async_notification', lambda coro: coro.close())
    with sessions() as session:
        session.add(Project(id='p', name='long talk', status=ProjectStatus.PROCESSING))
        session.commit()

    # Real progress store (the desktop app uses SQLite), real Studio store.
    monkeypatch.setattr(simple_progress, 'store', simple_progress.SqliteProgressStore(str(tmp_path / 'progress.db')))
    project_dir = store.directory('p')
    (project_dir / 'metadata').mkdir(parents=True)
    monkeypatch.setattr(path_utils, 'get_project_directory', lambda pid: store.directory(pid))
    store.write('p', {'generation': {'status': 'production', 'auto_start': True}, 'drafts': [], 'jobs': [], 'output_variants': [],
                      'analysis': {'status': 'running', 'phase': 'production', 'message': adapter.STUDIO_PRODUCTION_MESSAGE,
                                   'instance': store.INSTANCE}})

    monkeypatch.setattr(media_precheck, 'subtitle_route_failure', lambda *a, **k: None)
    monkeypatch.setattr(adapter.SimplePipelineAdapter, '_prompt_files', lambda self, project_dir: {})
    info = {'provider': 'dashscope', 'model': 'qwen-plus', 'available': True, 'display_name': '通义千问'}
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: SimpleNamespace(get_current_provider_info=lambda: info))
    clips = [{'id': '1', 'start_time': '00:00:00,000', 'end_time': '00:00:30,000', 'generated_title': 't', 'final_score': 0.9}]
    monkeypatch.setattr(adapter.SimplePipelineAdapter, '_find_clips_in_one_pass', lambda *a: clips)
    monkeypatch.setattr(adapter.TranscriptionProgress.__init__, '__defaults__', (0.0,))  # no wall-clock throttle in the test

    video = project_dir / 'input.mp4'
    video.write_bytes(b'video')
    return SimpleNamespace(video=video, sessions=sessions)


def _what_the_ui_polls(sessions):
    from backend.api.v1 import simple_progress as progress_api
    from backend.api.v1 import studio as studio_api
    [snapshot] = progress_api.get_progress_snapshots(project_ids=['p'])
    with sessions() as db:
        analysis = studio_api.workspace('p', db=db)['analysis']
    return snapshot['stage'], snapshot['percent'], analysis.get('message'), analysis.get('percent')


def test_transcription_progress_reaches_the_project_bar_and_studio_through_run_content(app_path, monkeypatch):
    from backend.services.studio import jobs
    from backend.utils import speech_recognizer, transcription_progress
    seen = []

    def fake_transcribe(video_path, output_path=None, **kwargs):
        for processed in (0.0, 0.25 * TOTAL, 0.5 * TOTAL, 0.75 * TOTAL, TOTAL):
            transcription_progress.report(processed, TOTAL)
            seen.append(_what_the_ui_polls(app_path.sessions))
        Path(output_path).write_text(SRT, encoding='utf-8')
        return Path(output_path)

    monkeypatch.setattr(speech_recognizer, 'generate_subtitle_for_video', fake_transcribe)

    clips = jobs.run_content('p', app_path.video)

    assert clips and clips[0]['generated_title'] == 't'
    stages = {stage for stage, *_ in seen}
    bar = [percent for _, percent, _, _ in seen]
    assert stages == {'SUBTITLE'}
    # The project bar visibly follows the audio: strictly rising, across most of the subtitle band
    # (the acceptance run only ever showed 14 → 16).
    assert bar == sorted(bar) and len(set(bar)) == len(bar), bar
    assert bar[0] <= 11 and bar[-1] >= 24, bar
    # Studio shows 「正在生成字幕 · N%」 with N = share of the audio transcribed.
    assert [(message, percent) for _, _, message, percent in seen] == [
        ('正在生成字幕', 0), ('正在生成字幕', 25), ('正在生成字幕', 50), ('正在生成字幕', 75), ('正在生成字幕', 100)]
    # Afterwards Studio goes back to the production wording without a stale percentage.
    from backend.services.studio import store
    analysis = store.read('p')['analysis']
    assert analysis['message'] == '正在制作可发布成片' and 'percent' not in analysis


def test_progress_bar_never_moves_backwards_across_the_subtitle_steps():
    """Every SUBTITLE checkpoint the adapter emits stays monotonic with the transcription band."""
    from backend.services.simple_progress import compute_percent
    from backend.services import simple_pipeline_adapter as adapter
    start = compute_percent('SUBTITLE', adapter.TRANSCRIBE_START_SUBPERCENT)
    first = compute_percent('SUBTITLE', adapter.transcription_subpercent(0.0))
    last = compute_percent('SUBTITLE', adapter.transcription_subpercent(1.0))
    done = compute_percent('SUBTITLE', adapter.TRANSCRIBE_DONE_SUBPERCENT)
    analyze = compute_percent('ANALYZE')
    assert compute_percent('SUBTITLE') <= start <= first < last <= done <= analyze
    assert last - first >= 12  # most of the 15-point SUBTITLE band, not 2 points
