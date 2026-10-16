"""ASR readiness is enforced on the backend before any paid call, including screening."""
import asyncio

import pytest

from backend.pipeline.failures import PipelineFailure
from backend.services.studio import analysis_preferences as ap
from backend.services.studio import intelligence, planning
from backend.services.studio.models import ImportOptions


def _asr(monkeypatch, ok, code='whisper_not_installed'):
    monkeypatch.setattr(
        'backend.services.studio.readiness.transcription_check',
        lambda: {'ok': ok, 'code': code if not ok else 'whisper_installed', 'repair': 'none' if ok else 'install_whisper'},
    )


def _auto_ready(monkeypatch):
    monkeypatch.setattr(ap, 'load', lambda: ap.AnalysisPreferences(analysis_mode='auto', allow_visual_screening=True))
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(intelligence, '_probe', lambda _: {'duration': 120.0, 'width': 64, 'height': 36})
    monkeypatch.setattr(intelligence, 'sample', lambda *a, **k: pytest.fail('paid frame sample'))


def test_screening_is_blocked_when_whisper_is_not_ready(monkeypatch, tmp_path):
    video = tmp_path / 'raw' / 'input.mp4'
    video.parent.mkdir(parents=True)
    video.write_bytes(b'fixture')
    _auto_ready(monkeypatch)
    _asr(monkeypatch, False)
    paid = []
    monkeypatch.setattr(intelligence, 'vision_call', lambda *a, **k: paid.append('vision') or pytest.fail('paid vision'))
    monkeypatch.setattr(intelligence, 'sample', lambda *a, **k: paid.append('sample') or [])
    with pytest.raises(PipelineFailure) as caught:
        planning.recommend(video, ImportOptions())
    assert caught.value.code == 'whisper_not_installed'
    assert paid == []


def test_visual_only_skips_asr_and_may_call_vision(monkeypatch, tmp_path):
    video = tmp_path / 'raw' / 'input.mp4'
    video.parent.mkdir(parents=True)
    video.write_bytes(b'fixture')
    monkeypatch.setattr(ap, 'load', lambda: ap.AnalysisPreferences(analysis_mode='visual', allow_visual_screening=True))
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(intelligence, '_probe', lambda _: {'duration': 120.0, 'width': 64, 'height': 36})
    monkeypatch.setattr(intelligence, 'sample', lambda *a, **k: [])
    _asr(monkeypatch, False)
    monkeypatch.setattr(
        intelligence, 'vision_call',
        lambda *a, **k: {'content_type': 'gameplay', 'goal': 'highlight', 'reason': '画面', 'confidence': 0.8},
    )
    plan = planning.recommend(video, ImportOptions())
    assert plan['mode'] == 'ai'
    assert plan['recommended_analysis'] == 'visual'


def test_attached_srt_skips_asr_gate(monkeypatch, tmp_path):
    video = tmp_path / 'raw' / 'input.mp4'
    video.parent.mkdir(parents=True)
    video.write_bytes(b'fixture')
    (video.parent / 'input.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nHi\n', encoding='utf-8')
    _auto_ready(monkeypatch)
    _asr(monkeypatch, False)
    monkeypatch.setattr(intelligence, 'sample', lambda *a, **k: [])
    monkeypatch.setattr(
        intelligence, 'vision_call',
        lambda *a, **k: {'content_type': 'talk', 'goal': 'content', 'reason': '口播', 'confidence': 0.7},
    )
    plan = planning.recommend(video, ImportOptions())
    assert plan['mode'] == 'ai'


def test_adapter_makes_zero_paid_calls_when_asr_missing(tmp_path, monkeypatch):
    from backend.services import simple_pipeline_adapter as adapter_module
    from backend.pipeline import media_precheck

    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    adapter = adapter_module.SimplePipelineAdapter('p-asr', 't-asr')
    paid = []
    monkeypatch.setattr(adapter, '_preflight_llm', lambda: paid.append('llm') or pytest.fail('paid llm'))

    async def transcribe(*args, **kwargs):
        paid.append('asr')
        pytest.fail('transcription must not start')

    monkeypatch.setattr(adapter, '_generate_subtitle_automatically', transcribe)
    from backend.services.studio import preflight as _pf; monkeypatch.setattr(_pf, 'probe_material', lambda v: _pf.MaterialProbe(_pf.ProbeState.READABLE, v, 60.0, True))
    _asr(monkeypatch, False)
    video = tmp_path / 'talk.mp4'
    video.write_bytes(b'fixture')
    result = asyncio.run(adapter.process_project_sync(str(video), '', clips_only=True))
    assert result['status'] == 'failed'
    assert result['error_code'] == 'whisper_not_installed'
    assert paid == []


def test_needs_transcription_respects_srt_and_visual_mode():
    from backend.services.studio import readiness
    assert readiness.needs_transcription(srt_available=True, analysis_mode='auto') is False
    assert readiness.needs_transcription(srt_available=False, analysis_mode='visual') is False
    assert readiness.needs_transcription(srt_available=False, analysis_mode='auto') is True
    assert readiness.needs_transcription(srt_available=False, analysis_mode='subtitle') is True


def test_confirm_subtitle_route_makes_zero_paid_calls_when_asr_missing(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    from backend.pipeline import media_precheck
    from backend.services.studio import jobs, store
    from backend.services.studio.models import ConfirmPlan, Preferences

    _asr(monkeypatch, False)
    from backend.services.studio import preflight as _pf; monkeypatch.setattr(_pf, 'probe_material', lambda v: _pf.MaterialProbe(_pf.ProbeState.READABLE, v, 60.0, True))
    root = store.directory('p1')
    (root / 'raw').mkdir(parents=True)
    (root / 'raw' / 'input.mp4').write_bytes(b'fixture')
    store.write('p1', {
        'plan': {
            'id': 'plan1',
            'preferences': Preferences().model_dump(),
            'source_duration': 120,
            'recommended_analysis': 'subtitle',
        },
        'analysis': {'status': 'awaiting_confirmation'},
        'drafts': [],
        'events': [],
        'jobs': [],
    })
    paid = []

    class Reject:
        def submit(self, *args, **kwargs):
            paid.append('produce')
            raise AssertionError('production must not start')

    monkeypatch.setattr(jobs, 'executor', Reject())
    with pytest.raises(ValueError, match='Whisper'):
        jobs.confirm_project('p1', ConfirmPlan(plan_id='plan1', analysis_mode='subtitle', goals=['content']))
    assert paid == []
    assert store.read('p1')['analysis']['status'] == 'awaiting_confirmation'


def test_cli_mcp_path_makes_zero_paid_calls_when_asr_missing(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path / 'data'))
    from backend.pipeline import media_precheck
    from backend.services import local_runner
    from backend.services.simple_pipeline_adapter import SimplePipelineAdapter

    paid = []
    from backend.services.studio import preflight as _pf; monkeypatch.setattr(_pf, 'probe_material', lambda v: _pf.MaterialProbe(_pf.ProbeState.READABLE, v, 60.0, True))
    monkeypatch.setattr(
        SimplePipelineAdapter, '_preflight_llm',
        staticmethod(lambda: paid.append('llm') or pytest.fail('paid llm')),
    )

    async def transcribe(*args, **kwargs):
        paid.append('asr')
        pytest.fail('transcription must not start')

    monkeypatch.setattr(SimplePipelineAdapter, '_generate_subtitle_automatically', transcribe)
    _asr(monkeypatch, False)
    dest = tmp_path / 'data' / 'projects' / 'p-mcp' / 'raw' / 'input.mp4'
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b'fixture')
    result = local_runner.run_pipeline(
        local_runner.RunRequest(video=dest, register_db=False, project_id='p-mcp'), dest)
    assert result['status'] == 'failed'
    assert result['error_code'] == 'whisper_not_installed'
    assert paid == []
