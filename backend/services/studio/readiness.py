"""Import-time readiness: saved settings and local runtimes only. No paid calls."""
from __future__ import annotations

from pathlib import Path

from backend.core.local_presets import LOCAL_PRESETS
from backend.services import ai_model_settings as ai_models


def _check(ok: bool, code: str, repair: str = 'none') -> dict:
    return {'ok': ok, 'code': code, 'repair': repair}


def _connection_ready(connection) -> bool:
    if connection is None:
        return False
    if connection.provider in LOCAL_PRESETS:
        return True
    if connection.provider == 'compatible' and connection.base_url:
        return True
    return bool(connection.api_key)


def _analysis(settings: ai_models.ModelSettings) -> dict:
    if getattr(settings, '_migration_warnings', None):
        return _check(False, 'settings_invalid', 'settings_ai')
    binding = settings.analysis
    connection = next((item for item in settings.connections if binding and item.id == binding.connection_id), None)
    if binding and binding.model and _connection_ready(connection):
        return _check(True, 'configured')
    return _check(False, 'not_configured', 'settings_ai')


def _transcription(settings: ai_models.ModelSettings) -> dict:
    choice = settings.transcription or ai_models.Transcription()
    if choice.provider == 'whisper_local':
        from backend.services import whisper_runtime
        status = whisper_runtime.get_status().get('status')
        if status == 'installed':
            return _check(True, 'whisper_installed')
        if status == 'installing':
            return _check(False, 'whisper_installing')
        if status == 'error':
            return _check(False, 'whisper_install_failed', 'install_whisper')
        return _check(False, 'whisper_not_installed', 'install_whisper')
    if choice.provider == 'sensevoice_local':
        from backend.services import sensevoice_runtime
        if sensevoice_runtime.status().get('status') == 'ready':
            return _check(True, 'sensevoice_ready')
        return _check(False, 'sensevoice_not_ready', 'settings_transcription')
    connection = next((item for item in settings.connections if item.id == choice.connection_id), None)
    if choice.model and _connection_ready(connection):
        return _check(True, 'cloud_configured')
    return _check(False, 'cloud_not_configured', 'settings_transcription')


def _visual(settings: ai_models.ModelSettings) -> dict:
    mode = settings.analysis_mode
    if mode == 'subtitle':
        return _check(True, 'not_required')
    if mode != 'visual':
        return _check(True, 'optional')
    binding = settings.analysis
    if binding and binding.model and binding.capability == 'multimodal':
        return _check(True, 'configured')
    return _check(False, 'not_configured', 'settings_vision')


def _ffmpeg() -> dict:
    try:
        from backend.utils.ffmpeg_utils import get_ffmpeg_path
        path = get_ffmpeg_path()
        if path and Path(path).exists():
            return _check(True, 'available')
    except Exception:
        pass
    return _check(False, 'missing')


def report() -> dict:
    settings = ai_models.for_editing()
    checks = {
        'analysis': _analysis(settings),
        'transcription': _transcription(settings),
        'visual': _visual(settings),
        'ffmpeg': _ffmpeg(),
    }
    return {
        'analysis_mode': settings.analysis_mode,
        'ready': all(item['ok'] for name, item in checks.items() if name != 'transcription') and checks['analysis']['ok'],
        'checks': checks,
    }
