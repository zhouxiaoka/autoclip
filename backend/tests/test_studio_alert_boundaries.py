"""Synthetic media/typed-failure boundaries; no external services or user data."""
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.pipeline.failures import PipelineFailure
from backend.services.studio import analysis_preferences as ap, intelligence, jobs, planning
from backend.services.studio.models import ImportOptions


@pytest.mark.parametrize('error', [
    subprocess.CalledProcessError(1, ['ffmpeg', 'private-input']),
    subprocess.TimeoutExpired(['ffmpeg', 'private-input'], 30),
    FileNotFoundError('private-frame-path'),
])
def test_quick_screening_media_failure_keeps_fallback_and_skips_provider(monkeypatch, error):
    monkeypatch.setattr(ap, 'load', lambda: ap.AnalysisPreferences(analysis_mode='auto', allow_visual_screening=True))
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(intelligence, '_probe', lambda _: {'duration': 20})
    def fail_sample(*args, **kwargs):
        raise error
    captured = []
    monkeypatch.setattr(intelligence, 'sample', fail_sample)
    monkeypatch.setattr(intelligence, 'vision_call', lambda *args, **kwargs: pytest.fail('provider called without frames'))
    monkeypatch.setattr('backend.core.sentry_setup.capture_studio_exception', lambda error, phase, **kwargs: captured.append((error, phase)))
    plan = planning.recommend(Path('synthetic.mp4'), ImportOptions())
    assert plan['mode'] == 'fallback'
    assert plan['suggested_goals'] == []
    assert plan['recommended_analysis'] == 'subtitle'
    assert captured == [(error, 'screening')]
    assert 'private-' not in str(plan)


def test_content_boundary_retains_uncoded_pipeline_stage(monkeypatch):
    from backend.tasks import processing
    outcome = {'success': False, 'error': 'synthetic controlled failure',
               'result': {'status': 'failed', 'stage': 'ANALYZE'}}
    task = SimpleNamespace(apply=lambda **kwargs: SimpleNamespace(get=lambda: outcome))
    monkeypatch.setattr(processing, 'process_video_pipeline', task)
    with pytest.raises(PipelineFailure) as caught:
        jobs.run_content('synthetic-project', Path('synthetic.mp4'))
    assert caught.value.stage == 'ANALYZE'
    assert caught.value.message == outcome['error']


def test_pipeline_stage_survives_capture_and_scrubbing_without_private_values(monkeypatch, tmp_path):
    import sentry_sdk
    from backend.core import sentry_setup
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(sentry_setup, '_initialized', True)
    captured = []
    def capture(error):
        return captured.append(dict(sentry_sdk.get_current_scope()._tags))
    monkeypatch.setattr(sentry_sdk, 'capture_exception', capture)
    sentry_setup.capture_studio_exception(PipelineFailure('ANALYZE', 'private-subtitle', code='unexpected'), 'production')
    assert captured[0]['pipeline_stage'] == 'ANALYZE'
    tags = {**captured[0], 'input_path': 'private-file'}
    clean = sentry_setup.before_send({'tags': tags, 'exception': {'values': [{'type': 'PipelineFailure', 'value': 'private-subtitle'}]}})
    assert clean['tags']['pipeline_stage'] == 'ANALYZE'
    assert 'private-' not in str(clean)
    tags['pipeline_stage'] = 'private-subtitle'
    clean = sentry_setup.before_send({'tags': tags, 'exception': {'values': [{'type': 'PipelineFailure'}]}})
    assert 'pipeline_stage' not in clean['tags']
