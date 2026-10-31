"""Import-time readiness: saved settings and local runtimes only. No paid calls."""
from __future__ import annotations

from backend.core.failure_codes import UserFacingError
from pathlib import Path

from backend.core.local_presets import LOCAL_PRESETS
from backend.services import ai_model_settings as ai_models


def _check(ok: bool, code: str, repair: str = 'none', **extras) -> dict:
    payload = {'ok': ok, 'code': code, 'repair': repair}
    for key, value in extras.items():
        if value is not None:
            payload[key] = value
    return payload


def _connection_ready(connection) -> bool:
    if connection is None:
        return False
    if connection.provider in LOCAL_PRESETS:
        return True
    if connection.provider == 'compatible' and connection.base_url:
        return True
    return bool(connection.api_key)


def _trial_ok(connection) -> bool | None:
    """F2 saved trial result for the F5 readiness line. None = never run."""
    status = getattr(connection, 'trial_status', 'unchecked') if connection else 'unchecked'
    if status == 'passed':
        return True
    if status == 'failed':
        return False
    return None


def _analysis(settings: ai_models.ModelSettings) -> dict:
    """Distinguish why analysis cannot run.

    ``not_configured`` — nothing saved. ``no_model`` — a usable connection exists
    but no analysis model is chosen. ``invalid_connection`` — a connection is
    present or referenced but cannot serve requests (missing key or endpoint).
    ``validation_failed`` stays separate: the user already saved a model and the
    check failed, so the import zone must not turn into the first-run card.

    F5 adds ``label`` (model id) and ``trial_ok`` (F2 trial_status on the connection).
    """
    if getattr(settings, '_migration_warnings', None):
        return _check(False, 'settings_invalid', 'settings_ai')
    binding = settings.analysis
    connection = next((item for item in settings.connections if binding and item.id == binding.connection_id), None)
    label = (binding.model or '').strip() if binding else ''
    trial = _trial_ok(connection)
    if binding is None:
        if any(_connection_ready(item) for item in settings.connections):
            return _check(False, 'no_model', 'settings_ai', trial_ok=trial)
        if settings.connections:
            return _check(False, 'invalid_connection', 'settings_ai', trial_ok=trial)
        return _check(False, 'not_configured', 'settings_ai')
    if connection is None or not _connection_ready(connection):
        return _check(False, 'invalid_connection', 'settings_ai', label=label or None, trial_ok=trial)
    if not label:
        return _check(False, 'no_model', 'settings_ai', trial_ok=trial)
    if getattr(connection, 'validation_status', 'unchecked') == 'failed':
        return _check(False, 'validation_failed', 'settings_ai', label=label, trial_ok=trial)
    return _check(True, 'configured', label=label, trial_ok=trial)


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
        raise UserFacingError('已保存的模型配置需要修复，请到「设置 → 服务商与模型」重新选择服务和模型并保存后再生成。') from None
    if settings is None:
        return
    ai_models.require_analysis(settings)
    check = _analysis(settings)
    if check['code'] == 'validation_failed':
        raise UserFacingError('当前模型连接未通过校验。请到「设置 → 服务商与模型」按提示改密钥或地址后再生成。')
    if ai_models.vision_follow_lacks_capability(settings):
        from backend.services.provider_validation import VISION_BLOCK_MESSAGE
        raise UserFacingError(VISION_BLOCK_MESSAGE)


def _transcription(settings: ai_models.ModelSettings) -> dict:
    choice = settings.transcription or ai_models.Transcription()
    if choice.provider == 'whisper_local':
        from backend.services import whisper_runtime
        model = choice.model or 'base'
        label = f'本地 {model}'
        status = whisper_runtime.get_status().get('status')
        if status == 'installed':
            return {**_whisper_model(model), 'label': label}
        if status == 'installing':
            return _check(False, 'whisper_installing', label=label)
        if status == 'error':
            return _check(False, 'whisper_install_failed', 'install_whisper', label=label)
        return _check(False, 'whisper_not_installed', 'install_whisper', label=label)
    if choice.provider == 'sensevoice_local':
        from backend.services import sensevoice_runtime
        label = '本地 SenseVoice'
        if sensevoice_runtime.status().get('status') == 'ready':
            return _check(True, 'sensevoice_ready', label=label)
        return _check(False, 'sensevoice_not_ready', 'settings_transcription', label=label)
    connection = next((item for item in settings.connections if item.id == choice.connection_id), None)
    label = f'云端 {choice.model}'.strip() if choice.model else '云端转写'
    trial = _trial_ok(connection)
    if choice.model and _connection_ready(connection):
        return _check(True, 'cloud_configured', label=label, trial_ok=trial)
    return _check(False, 'cloud_not_configured', 'settings_transcription', label=label, trial_ok=trial)


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


def _visual(settings: ai_models.ModelSettings, mode: str | None = None) -> dict:
    mode = mode or settings.analysis_mode
    binding = ai_models.vision_follow_binding(settings)
    vision_label = (binding.model or '').strip() if binding else ''
    if mode == 'subtitle':
        return _check(True, 'not_required', label='未启用')
    connection = next((item for item in settings.connections if binding and item.id == binding.connection_id), None)
    if connection and connection.validation_status == 'failed':
        if mode == 'auto':
            return _check(True, 'optional', label='未启用')
        return _check(False, 'validation_failed', 'settings_vision', label=vision_label or None)
    if ai_models.vision_follow_lacks_capability(settings):
        return _check(False, 'vision_unsupported', 'settings_vision', label=vision_label or None)
    if mode != 'visual':
        return _check(True, 'optional', label='未启用')
    # Same answer as the pipeline (vision_endpoint): capability=auto resolves through
    # provider metadata and supports_vision, not only a literal 'multimodal'.
    try:
        if ai_models.vision_endpoint(settings) is not None:
            return _check(True, 'configured', label=vision_label or None)
    except ValueError:
        return _check(False, 'settings_invalid', 'settings_vision', label=vision_label or None)
    return _check(False, 'not_configured', 'settings_vision', label=vision_label or None)


def _ffmpeg() -> dict:
    try:
        from backend.utils.ffmpeg_utils import get_ffmpeg_path
        path = get_ffmpeg_path()
        if path and Path(path).exists():
            return _check(True, 'available', label='FFmpeg')
    except Exception:
        pass
    return _check(False, 'missing', label='FFmpeg')


def report() -> dict:
    settings = ai_models.for_editing()
    from backend.services.studio import planning
    # One analysis-mode source for every field the preference planning and the gate read
    # (analysis_preferences.load, legacy file included), read once. Unreadable -> the document's own mode.
    mode = planning.preferred_analysis_mode() or settings.analysis_mode
    transcription = _transcription(settings)
    if not transcription.get('ok') and planning.transcription_may_be_skipped(mode):
        # Visual route possible: the desktop does not block; the import gate decides per file (code health).
        transcription = {**transcription, 'skippable': True}
    checks = {
        'analysis': _analysis(settings),
        'transcription': transcription,
        'visual': _visual(settings, mode),
        'ffmpeg': _ffmpeg(),
    }
    return {
        'analysis_mode': mode,
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


LOCAL_TRANSCRIPTION_REQUIRED = '需要先安装本地转写：视频没有字幕，所选的本地 Whisper 还没装好。请到「设置 → 默认模型 → 语音转字幕」一键安装，或改用云端转写后再导入。'
LOCAL_TRANSCRIPTION_INSTALLING = '等待安装完成：本地 Whisper 正在安装，装好后再开始。'
LOCAL_TRANSCRIPTION_DOWNLOADING = '等待下载完成：转写模型正在下载，下完后再开始。'
LOCAL_TRANSCRIPTION_MODEL = '需要先下载转写模型：视频没有字幕，所选的本地 Whisper 模型还没下载。请一键安装（会下载模型），或改用云端转写后再导入。'


# Waiting states keep their own code end to end never reported as whisper_not_installed.
WAITING_CODES = ('whisper_installing', 'whisper_model_downloading')
# #281: a missing / failed model is repaired by the same install prompt (runtime -> model download).
GATE_CODES = ('whisper_not_installed', 'whisper_install_failed', 'whisper_model_missing', 'whisper_model_failed') + WAITING_CODES


class TranscriptionNotReady(ValueError):
    """1.5.7 gate refusal. Callers map exactly this (not any ValueError) to ``invalid_input``.

    ``code`` is the transcription check code (one of ``GATE_CODES``); HTTP callers send ``detail``
    so the desktop maps the prompt from the code, never from the Chinese text."""
    error_code = 'invalid_input'

    def __init__(self, code: str):
        self.code = code
        super().__init__({'whisper_installing': LOCAL_TRANSCRIPTION_INSTALLING,
                          'whisper_model_downloading': LOCAL_TRANSCRIPTION_DOWNLOADING,
                          'whisper_model_missing': LOCAL_TRANSCRIPTION_MODEL,
                          'whisper_model_failed': LOCAL_TRANSCRIPTION_MODEL}.get(code, LOCAL_TRANSCRIPTION_REQUIRED))

    @property
    def detail(self) -> dict:
        return {'code': self.code, 'message': str(self)}


def _gate_settings():
    """Same settings view as the runtime ``transcription_check``: a missing or unreadable document
    falls back to defaults (local Whisper), so the gate cannot pass what the pipeline will refuse."""
    try:
        settings = ai_models.load()
    except Exception:  # noqa: BLE001
        settings = None
    return settings or ai_models.ModelSettings()


def transcription_gate_code() -> str | None:
    """The gate code when ASR is not ready in a way the install prompt handles, else None."""
    code = transcription_check().get('code')
    return code if code in GATE_CODES else None
