"""Preference compatibility and cost boundaries; no provider calls."""
import json

import pytest
from pydantic import ValidationError

from backend.services.studio import analysis_preferences as prefs, vision_settings


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))


def test_missing_preference_defaults_to_smart_selection(tmp_path, monkeypatch):
    # 没保存过：智能选择；视觉初筛随方式开启，但仍要有能看图的模型才会真的调用
    value = prefs.load()
    assert value.analysis_mode == 'auto' and value.allow_visual_screening is True
    assert prefs.visual_screening_allowed(value, vision_configured=True)
    assert not prefs.visual_screening_allowed(value, vision_configured=False)
    assert not prefs.settings_path().exists()  # Reading defaults does not write a file.


def test_saved_subtitle_choice_is_kept_and_never_screens(tmp_path):
    prefs.save(prefs.AnalysisPreferences(analysis_mode='subtitle'))
    value = prefs.load()
    assert value.analysis_mode == 'subtitle' and value.allow_visual_screening is False
    assert not prefs.visual_screening_allowed(value, vision_configured=True)


@pytest.mark.parametrize('mode', ['subtitle', 'auto', 'visual'])
@pytest.mark.parametrize('configured', [False, True])
def test_explicit_opt_out_never_authorizes_paid_screening(mode, configured):
    value = prefs.AnalysisPreferences(analysis_mode=mode, allow_visual_screening=False)
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
    prefs.save(prefs.AnalysisPreferences(analysis_mode='subtitle'))
    assert prefs.load().analysis_mode == 'subtitle'
    assert not prefs.load().allow_visual_screening


def test_failed_atomic_replace_preserves_previous_settings(tmp_path, monkeypatch):
    prefs.save(prefs.AnalysisPreferences(analysis_mode='subtitle'))
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


class _FakeManager:
    def __init__(self, endpoint):
        self.endpoint = endpoint

    def openai_compatible_endpoint(self):
        return self.endpoint


def _use_text_model(monkeypatch, endpoint):
    from backend.core import llm_manager
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: _FakeManager(endpoint))


def test_vision_defaults_to_text_model_without_saved_or_env(monkeypatch):
    # 不受本机 .env 里的 SEEDANCE_BASE_URL 影响
    monkeypatch.setattr(vision_settings, '_environment', lambda: None)
    _use_text_model(monkeypatch, {'base_url': 'https://infistar.cc/v1', 'api_key': 'sk-text', 'model': 'gemini-3.8-flash'})
    value = vision_settings.effective()
    assert value['mode'] == 'text_model' and value['source'] == 'default'
    assert (value['base_url'], value['api_key'], value['model']) == ('https://infistar.cc/v1', 'sk-text', 'gemini-3.8-flash')
    public = vision_settings.public()
    assert public['configured'] is True and public['verified'] is False and 'sk-text' not in json.dumps(public)


def test_legacy_saved_vision_config_stays_custom(tmp_path, monkeypatch):
    _use_text_model(monkeypatch, {'base_url': 'https://infistar.cc/v1', 'api_key': 'sk-text', 'model': 'gpt-5-mini'})
    (tmp_path / 'vision-settings.json').write_text(json.dumps({'base_url': 'https://ark.example/v3', 'model': 'seed-vision', 'api_key': 'ark-key', 'timeout': 180}))
    value = vision_settings.effective()
    assert value['mode'] == 'custom' and value['base_url'] == 'https://ark.example/v3' and value['api_key'] == 'ark-key'


def test_env_vision_config_still_wins_over_text_model(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_VISION_BASE_URL', 'https://ark.example/v3')
    _use_text_model(monkeypatch, {'base_url': 'https://infistar.cc/v1', 'api_key': 'sk-text', 'model': 'gpt-5-mini'})
    assert vision_settings.effective()['source'] == 'environment'


def test_text_model_mode_needs_no_endpoint_and_follows_text_changes(monkeypatch):
    _use_text_model(monkeypatch, {'base_url': 'https://infistar.cc/v1', 'api_key': 'sk-text', 'model': 'gpt-5-mini'})
    saved = vision_settings.save(vision_settings.VisionSettingsInput(mode='text_model'))
    assert saved['mode'] == 'text_model' and saved['model'] == 'gpt-5-mini'
    _use_text_model(monkeypatch, {'base_url': 'https://infistar.cc/v1', 'api_key': 'sk-text', 'model': 'claude-sonnet-5-5'})
    assert vision_settings.effective()['model'] == 'claude-sonnet-5-5'
    with pytest.raises(ValidationError):
        vision_settings.VisionSettingsInput(mode='custom', base_url='', model='')


def test_verified_only_for_the_tested_endpoint(monkeypatch):
    from backend.services.studio import intelligence
    _use_text_model(monkeypatch, {'base_url': 'https://infistar.cc/v1', 'api_key': 'sk-text', 'model': 'gpt-5-mini'})
    vision_settings.save(vision_settings.VisionSettingsInput(mode='text_model'))
    monkeypatch.setattr(intelligence, 'vision_call', lambda content, config: {'color': 'red'})
    vision_settings.test(vision_settings.VisionSettingsInput(mode='text_model'))
    assert vision_settings.public()['verified'] is True
    # 换了文本模型：验证失效，不再宣称能看图
    _use_text_model(monkeypatch, {'base_url': 'https://infistar.cc/v1', 'api_key': 'sk-text', 'model': 'qwen-plus'})
    assert vision_settings.public()['verified'] is False


def test_text_model_mode_without_endpoint_is_unconfigured(monkeypatch):
    # 不受本机 .env 里的 SEEDANCE_BASE_URL 影响
    monkeypatch.setattr(vision_settings, '_environment', lambda: None)
    _use_text_model(monkeypatch, None)
    assert vision_settings.public()['configured'] is False
    with pytest.raises(ValueError, match='另选视觉模型'):
        vision_settings.test(vision_settings.VisionSettingsInput(mode='text_model'))


def test_text_only_model_is_not_used_for_vision(monkeypatch):
    monkeypatch.setattr(vision_settings, '_environment', lambda: None)
    _use_text_model(monkeypatch, {'base_url': 'https://api.deepseek.com', 'api_key': 'sk-ds', 'model': 'deepseek-flash'})
    public = vision_settings.public()
    assert public['configured'] is False and public['text_only'] is True
    from backend.services.studio import intelligence
    assert intelligence.ready() is False
