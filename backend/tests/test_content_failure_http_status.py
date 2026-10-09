"""RC156 Win QA #1 (retest): the provider HTTP status survives the Studio content path.

Studio runs the content pipeline through `process_video_pipeline.apply(...).get()`; that returns a
result dict, so the original exception chain (PipelineFailure ... from openai.InternalServerError)
is gone by the time `jobs.run_content` rebuilds a PipelineFailure. The status has to travel in
the dict: adapter -> processing outcome -> run_content -> studio_failure_context.
"""
import asyncio
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.base import Base
from backend.models.project import Project, ProjectStatus

SRT = "1\n00:00:00,000 --> 00:00:05,000\n第一句\n\n2\n00:00:05,000 --> 00:00:10,000\n第二句\n"


class ProviderError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.delenv('AUTOCLIP_LLM_CACHE_DIR', raising=False)
    from types import SimpleNamespace
    from backend.core import llm_manager, path_utils
    from backend.services import simple_pipeline_adapter as mod
    from backend.tasks import processing

    engine = create_engine('sqlite:///:memory:')
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
        session.add(Project(id='p', name='synthetic', status=ProjectStatus.PROCESSING))
        session.commit()

    monkeypatch.setattr(path_utils, 'get_project_directory', lambda pid: tmp_path / 'projects' / pid)
    monkeypatch.setattr(mod, 'clear_progress', lambda pid: None)
    monkeypatch.setattr(mod, 'emit_progress', lambda *a, **k: None)
    monkeypatch.setattr(mod.SimplePipelineAdapter, '_prompt_files', lambda self, project_dir: {})
    monkeypatch.setattr(mod.SimplePipelineAdapter, '_find_clips_in_one_pass', lambda *a: None)
    info = {'provider': 'dashscope', 'model': 'qwen-plus', 'available': True, 'display_name': '通义千问'}
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: SimpleNamespace(get_current_provider_info=lambda: info))
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'')
    (tmp_path / 'input.srt').write_text(SRT, encoding='utf-8')
    return mod, video


def _outline_raises(mod, monkeypatch, error):
    monkeypatch.setattr(mod, 'run_step1_outline', lambda *a, **k: (_ for _ in ()).throw(error))


def _wrapped_500():
    from backend.pipeline.failures import PipelineFailure
    try:
        try:
            raise ProviderError('Error code: 500 - internal (private body)', 500)
        except ProviderError as provider:
            raise PipelineFailure('ANALYZE', '大纲提取失败：1/1 个文本块调用模型都失败了。', code='') from provider
    except PipelineFailure as failure:
        return failure


def test_http_500_reaches_the_generation_failure_context_through_apply_get(pipeline, monkeypatch):
    from backend.core.sentry_setup import studio_failure_context
    from backend.pipeline.failures import PipelineFailure
    from backend.services.studio import jobs
    mod, video = pipeline
    _outline_raises(mod, monkeypatch, _wrapped_500())

    with pytest.raises(PipelineFailure) as raised:
        jobs.run_content('p', video)

    assert raised.value.http_status == 500
    assert studio_failure_context(raised.value, 'production') == {'failure_stage': 'analyze', 'http_status': 500}
    assert 'private body' not in str(raised.value)


def test_coded_failure_keeps_code_stage_and_status(pipeline, monkeypatch):
    from backend.core.sentry_setup import studio_failure_context
    from backend.pipeline.failures import PipelineFailure
    from backend.services.studio import jobs
    mod, video = pipeline
    failure = PipelineFailure('ANALYZE', '无法连接模型服务。', code='llm_connection')
    failure.__cause__ = ProviderError('boom', 503)
    _outline_raises(mod, monkeypatch, failure)

    with pytest.raises(PipelineFailure) as raised:
        jobs.run_content('p', video)

    assert (raised.value.stage, raised.value.code, raised.value.http_status) == ('ANALYZE', 'llm_connection', 503)
    assert studio_failure_context(raised.value, 'production')['http_status'] == 503


def test_unexpected_provider_error_keeps_its_status(pipeline, monkeypatch):
    from backend.core.sentry_setup import studio_failure_context
    from backend.services.studio import jobs
    mod, video = pipeline
    _outline_raises(mod, monkeypatch, ProviderError('Error code: 502', 502))

    with pytest.raises(RuntimeError) as raised:
        jobs.run_content('p', video)

    assert studio_failure_context(raised.value, 'production') == {'failure_stage': 'production', 'http_status': 502}


def test_failure_without_status_and_out_of_range_values_add_nothing(pipeline, monkeypatch):
    from types import SimpleNamespace
    import sys
    from backend.core.sentry_setup import studio_failure_context
    from backend.pipeline.failures import PipelineFailure
    from backend.services.studio import jobs
    mod, video = pipeline
    _outline_raises(mod, monkeypatch, PipelineFailure('ANALYZE', '字幕为空。', code='transcription_empty'))
    with pytest.raises(PipelineFailure) as raised:
        jobs.run_content('p', video)
    assert raised.value.http_status is None
    assert studio_failure_context(raised.value, 'production') == {'failure_stage': 'analyze'}

    for bad in (200, '500', 600, True, None):
        result = {'success': False, 'error': 'x', 'result': {'status': 'failed', 'stage': 'ANALYZE', 'http_status': bad}}
        fake = SimpleNamespace(apply=lambda **kw: SimpleNamespace(get=lambda: result))
        monkeypatch.setitem(sys.modules, 'backend.tasks.processing', SimpleNamespace(process_video_pipeline=fake))
        with pytest.raises(PipelineFailure) as raised:
            jobs.run_content('p', video)
        assert raised.value.http_status is None, bad
