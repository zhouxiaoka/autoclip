"""Preference compatibility and cost boundaries; no provider calls."""
import json

import pytest
from pydantic import ValidationError

from backend.services.studio import analysis_preferences as prefs, vision_settings


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))


def test_missing_preference_keeps_subtitle_even_with_vision_configured(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_VISION_BASE_URL', 'https://example.test/v1')
    monkeypatch.setenv('AUTOCLIP_VISION_API_KEY', 'test-only-key')
    assert prefs.load() == prefs.AnalysisPreferences()
    vision_settings.save(vision_settings.VisionSettingsInput(base_url='https://example.test/v1', model='multimodal', api_key='test-only-key'))
    assert prefs.load().analysis_mode == 'subtitle'
    assert not prefs.visual_screening_allowed(prefs.load(), vision_configured=True)
    assert not prefs.settings_path().exists()  # Reading legacy defaults does not migrate data.


@pytest.mark.parametrize('mode', ['subtitle', 'auto', 'visual'])
@pytest.mark.parametrize('configured', [False, True])
def test_mode_selection_alone_does_not_authorize_paid_screening(mode, configured):
    value = prefs.AnalysisPreferences(analysis_mode=mode)
    assert not prefs.visual_screening_allowed(value, vision_configured=configured)


@pytest.mark.parametrize('mode', ['auto', 'visual'])
def test_paid_screening_requires_explicit_permission_and_capability(mode):
    value = prefs.AnalysisPreferences(analysis_mode=mode, allow_visual_screening=True)
    assert prefs.visual_screening_allowed(value, vision_configured=True)
    assert not prefs.visual_screening_allowed(value, vision_configured=False)


@pytest.mark.parametrize('data', [
    {'analysis_mode':'subtitle','allow_visual_screening':True},
    {'analysis_mode':'cheap'}, {'allow_visual_screening':'true'},
    {'allow_visual_screening':1}, {'model':'multimodal'},
])
def test_invalid_or_coerced_settings_are_rejected(data):
    with pytest.raises(ValidationError): prefs.AnalysisPreferences(**data)


def test_save_round_trip_does_not_change_model_configuration(tmp_path):
    model = tmp_path / 'vision-settings.json'
    model.write_text('{"model":"existing","api_key":"private-test"}')
    before = model.read_bytes()
    value = prefs.AnalysisPreferences(analysis_mode='auto', allow_visual_screening=True)
    assert prefs.save(value) == value
    assert prefs.load() == value
    assert model.read_bytes() == before
    assert json.loads(prefs.settings_path().read_text()) == value.model_dump()
    prefs.save(prefs.AnalysisPreferences())
    assert prefs.load().analysis_mode == 'subtitle'
    assert not prefs.load().allow_visual_screening


def test_failed_atomic_replace_preserves_previous_settings(tmp_path, monkeypatch):
    prefs.save(prefs.AnalysisPreferences())
    def fail(*args): raise OSError('simulated disk error')
    monkeypatch.setattr(prefs.os, 'replace', fail)
    with pytest.raises(OSError): prefs.save(prefs.AnalysisPreferences(analysis_mode='visual'))
    assert prefs.load().analysis_mode == 'subtitle'
    assert list(tmp_path.glob('analysis-preferences.*.tmp')) == []


@pytest.mark.parametrize('raw', ['{broken', '{"analysis_mode":"unknown"}', 'null'])
def test_corrupt_settings_do_not_silently_enable_a_model(raw):
    prefs.settings_path().write_text(raw)
    with pytest.raises(ValueError, match='尚未授权视觉调用'): prefs.load()
    assert prefs.settings_path().read_text() == raw
