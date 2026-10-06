"""Global source-frame consent also covers automatic cover and caption helpers."""
from pathlib import Path

import pytest

from backend.services import ai_model_settings as ai
from backend.services.studio import cover_design, intelligence, jobs


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    settings = ai.ModelSettings(
        connections=[ai.Connection(id='existing', name='Existing account', provider='openai',
                                   base_url='https://fixture.example/v1', api_key='fixture-key')],
        analysis=ai.Assignment(connection_id='existing', model='text-only', capability='text'),
        vision=ai.Assignment(connection_id='existing', model='legacy-vision', capability='multimodal'),
        analysis_mode='subtitle', allow_visual_screening=False, cover_enabled=False,
    )
    ai.save(settings)
    assert intelligence.ready(), 'A configured legacy vision binding is not consent'
    calls = []
    def vision(content, _config):
        calls.append(content)
        return {'best': 1, 'language': 'en'}
    monkeypatch.setattr(intelligence, 'vision_call', vision)
    return settings, calls


def _exercise(helper, tmp_path, monkeypatch):
    sampled = []
    if helper == 'cover':
        def thumb(frame):
            sampled.append(frame)
            return 'data:image/jpeg;base64,fixture'
        monkeypatch.setattr(cover_design, '_thumb', thumb)
        result = cover_design._choose_with_vision([(b'frame', .5, 10, True)], 'Guest', 'Host')
    else:
        import subprocess
        from backend.services import publish_export
        monkeypatch.setattr(publish_export, '_probe', lambda _video: {'duration': 10})
        def extract(command, **_kwargs):
            sampled.append(command)
            Path(command[-1]).write_bytes(b'frame')
        monkeypatch.setattr(subprocess, 'run', extract)
        result = jobs._burned_caption_language(tmp_path / 'source.mp4', True, '这是一次关于人工智能发展的中文采访')
    return result, sampled


@pytest.mark.parametrize('helper', ['cover', 'captions'])
@pytest.mark.parametrize('mode', ['subtitle', 'auto', 'visual'])
def test_existing_vision_binding_does_not_override_opt_out(configured, tmp_path, monkeypatch, helper, mode):
    settings, calls = configured
    settings.analysis_mode = mode
    ai.save(settings)
    result, sampled = _exercise(helper, tmp_path, monkeypatch)
    assert calls == [], 'Source frames must not be transmitted after visual opt-out'
    assert sampled == [], 'Do not prepare provider images without consent'
    assert result == (None if helper == 'cover' else 'zh')


@pytest.mark.parametrize('helper', ['cover', 'captions'])
@pytest.mark.parametrize('mode', ['auto', 'visual'])
def test_explicit_consent_keeps_auxiliary_vision_working(configured, tmp_path, monkeypatch, helper, mode):
    settings, calls = configured
    settings.analysis_mode = mode
    settings.allow_visual_screening = True
    ai.save(settings)
    result, sampled = _exercise(helper, tmp_path, monkeypatch)
    assert len(calls) == 1 and len(sampled) == (1 if helper == 'cover' else 3)
    assert result == ((0, True) if helper == 'cover' else 'en')


@pytest.mark.parametrize('helper', ['cover', 'captions'])
def test_invalid_preferences_fail_closed_without_discarding_them(configured, tmp_path, monkeypatch, helper):
    _settings, calls = configured
    ai.path().write_text('{broken', encoding='utf-8')
    result, sampled = _exercise(helper, tmp_path, monkeypatch)
    assert result == (None if helper == 'cover' else 'zh')
    assert not calls and not sampled
    assert ai.path().read_text() == '{broken'


@pytest.mark.parametrize('helper', ['cover', 'captions'])
def test_consent_without_a_capable_model_does_not_send_frames(configured, tmp_path, monkeypatch, helper):
    settings, calls = configured
    settings.analysis_mode = 'auto'
    settings.allow_visual_screening = True
    settings.vision = None
    ai.save(settings)
    result, sampled = _exercise(helper, tmp_path, monkeypatch)
    assert result == (None if helper == 'cover' else 'zh')
    assert not calls and not sampled
