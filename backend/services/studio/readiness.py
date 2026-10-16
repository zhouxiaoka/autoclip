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
        if mode == 'auto':
            return _check(True, 'optional')
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
    from backend.services.studio import planning
    transcription = _transcription(settings)
    if not transcription.get('ok') and planning.transcription_may_be_skipped():
        # Visual route possible: the desktop does not block; the import gate decides per file (R21 code health).
        transcription = {**transcription, 'skippable': True}
    checks = {
        'analysis': _analysis(settings),
        'transcription': transcription,
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


LOCAL_TRANSCRIPTION_REQUIRED = '需要先安装本地转写：视频没有字幕，所选的本地 Whisper 还没装好。请到「设置 → 转写」一键安装，或改用云端转写后再导入。'
LOCAL_TRANSCRIPTION_INSTALLING = '等待安装完成：本地 Whisper 正在安装，装好后再开始。'


GATE_CODES = ('whisper_not_installed', 'whisper_install_failed', 'whisper_installing')


class TranscriptionNotReady(ValueError):
    """1.5.8 gate refusal. Callers map exactly this (not any ValueError) to ``invalid_input``.

    ``code`` is the transcription check code (one of ``GATE_CODES``); HTTP callers send ``detail``
    so the desktop maps the prompt from the code, never from the Chinese text (R20 #168)."""
    error_code = 'invalid_input'

    def __init__(self, code: str):
        self.code = code
        super().__init__(LOCAL_TRANSCRIPTION_INSTALLING if code == 'whisper_installing' else LOCAL_TRANSCRIPTION_REQUIRED)

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


def ensure_local_transcription_for_import(*, srt_available: bool, video=None, route: str = 'studio', goal: str | None = 'auto') -> None:
    """1.5.8 import gate for a local file: local Whisper selected, runtime missing/installing, no SRT -> block.

    ``route='studio'`` asks planning (``planning.route_before_screening``) which route the job will take;
    that needs the file, so without ``video`` the gate refuses and the caller stages and asks again.
    ``route='content'`` is the CLI / MCP / legacy content pipeline, which always transcribes without an SRT.
    Never switches provider (no silent cloud fallback) and never installs anything.
    Links are not gated here: platform captions are tried first after download.
    """
    if srt_available:
        return
    settings = _gate_settings()  # missing / unreadable settings -> defaults on every route (R19 #115)
    choice = settings.transcription or ai_models.Transcription()
    if choice.provider != 'whisper_local':
        return
    code = _transcription(settings).get('code')
    if code not in GATE_CODES:
        return
    if route == 'studio' and video is not None:
        from backend.services.studio import planning
        if planning.route_before_screening(goal, Path(video)) != 'subtitle':
            return  # visual, or planning stops first with its own code (source_unreadable, R22 #207)
    if video is not None and _source_cannot_take_subtitle_route(video, srt_available):
        return  # too short / no audio needs no Whisper: the pipeline reports the real source_* code
    raise TranscriptionNotReady(code)


def ensure_local_transcription_for_paths(video, srt=None, *, sibling_srt: bool = True, route: str = 'content', goal: str | None = 'auto') -> None:
    """Same gate for entry points that already have files on disk (process / retry / submit / CLI / MCP).
    Defaults to the content route: those paths run SimplePipelineAdapter, which ignores analysis_mode.

    ``sibling_srt`` counts ``input.srt`` beside the video as subtitles. Only true when the video already
    lives in a project raw dir (the pipeline reads that file); a user's source folder is never copied.
    A missing video is not gated here: those paths re-download or fail with their own error."""
    if not video or not Path(video).is_file():
        return
    if srt:
        srt_ok = Path(srt).is_file()
    else:
        srt_ok = sibling_srt and (Path(video).parent / 'input.srt').is_file()
    ensure_local_transcription_for_import(srt_available=srt_ok, video=Path(video), route=route, goal=goal)


def ensure_local_transcription_for_project(project_id: str) -> None:
    from backend.core.path_utils import get_project_raw_directory
    raw = get_project_raw_directory(project_id)
    video = next((raw / f'input{ext}' for ext in ('.mp4', '.mov', '.mkv', '.webm', '.avi') if (raw / f'input{ext}').is_file()), None)
    ensure_local_transcription_for_paths(video)


def _source_cannot_take_subtitle_route(video, srt_available: bool) -> bool:
    from backend.pipeline import media_precheck
    try:
        return media_precheck.subtitle_route_failure(video, srt_available=srt_available) is not None
    except Exception:  # noqa: BLE001 - unreadable source: let the pipeline classify it
        return True
