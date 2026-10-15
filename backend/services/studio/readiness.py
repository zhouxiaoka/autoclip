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
        if getattr(connection, 'validation_status', 'unchecked') == 'failed':
            return _check(False, 'validation_failed', 'settings_ai')
        return _check(True, 'configured')
    return _check(False, 'not_configured', 'settings_ai')


def ensure_analysis_usable() -> None:
    """Block broken saved assignments, failed connection validation, and visual
    capability misses before dispatch or any provider request.

    An absent settings document stays on the first-run readiness path; unreadable
    settings and missing saved connections require repair before generation.
    """
    try:
        settings = ai_models.load()
    except Exception:
        # Validation errors may contain private settings values. Expose only this message.
        raise ValueError('已保存的模型配置需要修复，请到「设置 → 模型」重新选择服务和模型并保存后再生成。') from None
    if settings is None:
        return
    ai_models.require_analysis(settings)
    check = _analysis(settings)
    if check['code'] == 'validation_failed':
        raise ValueError('当前模型连接未通过校验。请到「设置 → 模型」按提示改密钥或地址后再生成。')
    if ai_models.vision_follow_lacks_capability(settings):
        from backend.services.provider_validation import VISION_BLOCK_MESSAGE
        raise ValueError(VISION_BLOCK_MESSAGE)


def _transcription(settings: ai_models.ModelSettings) -> dict:
    choice = settings.transcription or ai_models.Transcription()
    if choice.provider == 'whisper_local':
        from backend.services import whisper_runtime
        status = whisper_runtime.get_status().get('status')
        if status == 'installed':
            return _whisper_model(choice.model or 'base')
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


def _whisper_model(name: str) -> dict:
    """The runtime alone cannot transcribe: the selected model must be on disk (RC156 Win QA #5).

    Reads the local cache and in-process download state only; never contacts the Hub.
    """
    from backend.services.whisper_model_manager import canonical_model_name, get_model_manager
    manager = get_model_manager()
    model = canonical_model_name(name)
    if model not in manager.model_configs or manager.get_local_model_path(model) is not None:
        return _check(True, 'whisper_installed')
    state = manager.download_status(model)
    if state == 'downloaded':
        # The download thread verified a complete snapshot under the same cache dir; trust it so
        # readiness flips right after the download instead of waiting on a disk re-scan (W157 IA).
        return _check(True, 'whisper_installed')
    if state == 'downloading':
        return {**_check(False, 'whisper_model_downloading'), 'model': model}
    if state == 'error':
        return {**_check(False, 'whisper_model_failed', 'install_whisper'), 'model': model}
    return {**_check(False, 'whisper_model_missing', 'install_whisper'), 'model': model}


def _visual(settings: ai_models.ModelSettings) -> dict:
    mode = settings.analysis_mode
    if mode == 'subtitle':
        return _check(True, 'not_required')
    binding = ai_models.vision_follow_binding(settings)
    connection = next((item for item in settings.connections if binding and item.id == binding.connection_id), None)
    if connection and connection.validation_status == 'failed':
        return _check(False, 'validation_failed', 'settings_vision')
    if ai_models.vision_follow_lacks_capability(settings):
        return _check(False, 'vision_unsupported', 'settings_vision')
    if mode != 'visual':
        return _check(True, 'optional')
    # Same answer as the pipeline (vision_endpoint): capability=auto resolves through
    # provider metadata and supports_vision, not only a literal 'multimodal'.
    try:
        if ai_models.vision_endpoint(settings) is not None:
            return _check(True, 'configured')
    except ValueError:
        return _check(False, 'settings_invalid', 'settings_vision')
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


def transcription_check() -> dict:
    """Saved transcription settings and local runtimes only. Does not migrate legacy LLM config."""
    try:
        settings = ai_models.load()
    except Exception:  # noqa: BLE001 - a corrupt document must not skip the Whisper gate
        settings = None
    return _transcription(settings or ai_models.ModelSettings())


def needs_transcription(*, srt_available: bool, analysis_mode: str | None = None) -> bool:
    """The subtitle/content pipeline needs ASR when there is no SRT. Visual-only does not.

    `analysis_mode is None` means the caller is the content/API/MCP path, which is never visual-only.
    """
    if srt_available:
        return False
    return analysis_mode != 'visual'


def require_transcription(*, stage: str = 'SUBTITLE', srt_available: bool = False, analysis_mode: str | None = None) -> None:
    """Block before any paid call when the subtitle route still needs a local/cloud ASR."""
    if not needs_transcription(srt_available=srt_available, analysis_mode=analysis_mode):
        return
    check = transcription_check()
    if check.get('ok'):
        return
    from backend.pipeline.failures import transcription_not_ready_failure
    raise transcription_not_ready_failure(check, stage)
