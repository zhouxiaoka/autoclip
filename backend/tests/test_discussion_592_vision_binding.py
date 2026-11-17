"""Discussion #592 — api88 / qwen3.8-flash vision binding across save, reread, and toggles.

The feedback has no screenshot, so this does not decide whether the reporter
saw the import line before generation or a missing vision result after it.
Both code paths are asserted, and they use different copy:

- before start, analysis_mode auto/subtitle: readiness label 「未启用」
- before start, analysis_mode visual with this model: the model id, not 「未启用」
- after start, a vision failure uses 「画面结果不可用，已改用字幕继续制作。」

qwen3.8-flash is an explicit catalog id in supports_vision. The name alone is
not the evidence; the catalog entry and vision_endpoint() are.
Saving does not rewrite the api88 key or base URL.
"""
import json

import pytest

from backend.services import ai_model_settings as ai
from backend.services.studio import analysis_preferences, intelligence, readiness


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    binary = tmp_path / 'ffmpeg'
    binary.write_bytes(b'ffmpeg')
    monkeypatch.setattr('backend.utils.ffmpeg_utils.get_ffmpeg_path', lambda: str(binary))
    monkeypatch.setattr('backend.services.whisper_runtime.get_status', lambda: {'status': 'installed'})
    from backend.services import whisper_model_manager
    monkeypatch.setattr(whisper_model_manager, '_model_manager', whisper_model_manager.WhisperModelManager())
    monkeypatch.setattr('backend.services.whisper_runtime.get_models_dir', lambda: tmp_path / 'whisper-models')
    snapshot = tmp_path / 'whisper-models' / 'hub' / 'models--Systran--faster-whisper-base' / 'snapshots' / 'complete'
    snapshot.mkdir(parents=True)
    for name in ('model.bin', 'config.json', 'tokenizer.json', 'vocabulary.json'):
        (snapshot / name).write_bytes(b'fixture')


def _document(mode, screening):
    return ai.ModelSettings(
        connections=[ai.Connection(
            id='api88', name='88API', provider='api88',
            api_key='sk-test-key', base_url='https://api.88api.ai/v1',
            validation_status='ok',
        )],
        analysis=ai.Assignment(connection_id='api88', model='qwen3.8-flash', capability='auto', model_source='user'),
        vision=None,
        transcription=ai.Transcription(),
        analysis_mode=mode,
        allow_visual_screening=screening,
    )


def _persist(settings):
    ai.save(settings)
    loaded = ai.load()
    assert loaded is not None
    connection = loaded.connections[0]
    assert connection.provider == 'api88'
    assert connection.api_key == 'sk-test-key'
    assert connection.base_url == 'https://api.88api.ai/v1'
    assert loaded.analysis.model == 'qwen3.8-flash'
    assert loaded.vision is None
    return loaded


def test_save_reread_keeps_api88_and_distinguishes_disabled_before_start(monkeypatch):
    import urllib.error
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError('offline')))
    auto = _persist(_document('auto', True))
    endpoint = ai.vision_endpoint(auto)
    assert endpoint is not None
    assert endpoint['model'] == 'qwen3.8-flash'
    assert endpoint['base_url'].rstrip('/') == 'https://api.88api.ai/v1'
    assert endpoint['api_key'] == 'sk-test-key'
    assert intelligence.ready() is True
    prefs = analysis_preferences.AnalysisPreferences(analysis_mode='auto', allow_visual_screening=True)
    assert analysis_preferences.visual_screening_allowed(prefs, vision_configured=True) is True
    monkeypatch.setattr(analysis_preferences, 'load', lambda: prefs)
    auto_report = readiness.report()
    # By design the import line says 未启用 in smart mode even though the endpoint exists.
    # The thread has no screenshot, so this is the before-start path, not a proven user bug.
    assert auto_report['checks']['visual']['code'] == 'optional'
    assert auto_report['checks']['visual']['label'] == '未启用'
    assert auto_report['checks']['visual']['ok'] is True
    assert 'sk-test-key' not in json.dumps(auto_report)

    visual = _persist(_document('visual', True))
    monkeypatch.setattr(
        analysis_preferences, 'load',
        lambda: analysis_preferences.AnalysisPreferences(analysis_mode='visual', allow_visual_screening=True),
    )
    visual_report = readiness.report()
    assert visual_report['checks']['visual']['code'] == 'configured'
    assert visual_report['checks']['visual']['label'] == 'qwen3.8-flash'
    assert visual_report['checks']['visual']['label'] != '未启用'
    assert ai.vision_endpoint(visual)['model'] == 'qwen3.8-flash'
    readiness.ensure_analysis_usable()

    subtitles = _persist(_document('subtitle', False))
    monkeypatch.setattr(
        analysis_preferences, 'load',
        lambda: analysis_preferences.AnalysisPreferences(analysis_mode='subtitle', allow_visual_screening=False),
    )
    subtitle_report = readiness.report()
    assert subtitle_report['checks']['visual']['code'] == 'not_required'
    assert subtitle_report['checks']['visual']['label'] == '未启用'
    prefs = analysis_preferences.load()
    assert analysis_preferences.visual_screening_allowed(
        prefs, vision_configured=ai.vision_endpoint(subtitles) is not None,
    ) is False
    # The binding is still there after the toggle. Subtitle mode does not wipe api88.
    assert subtitles.analysis.model == 'qwen3.8-flash'
    assert subtitles.connections[0].base_url == 'https://api.88api.ai/v1'


def test_after_start_vision_failure_copy_is_not_the_before_start_label():
    """No screenshot showed a result missing after generation. The copy is a different string."""
    from pathlib import Path
    locales = Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'i18n' / 'locales'
    degrade = '画面结果不可用，已改用字幕继续制作。'
    before = '未启用'
    assert degrade != before
    for name in ('zh', 'en', 'ja', 'ko', 'es', 'fr', 'pt', 'ru'):
        text = (locales / f'{name}.json').read_text(encoding='utf-8')
        assert degrade in text
        assert before in text
