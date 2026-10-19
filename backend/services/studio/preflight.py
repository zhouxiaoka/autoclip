"""The one preflight for every execution entry (1.5.7 #418 rewrite, design-retro.md).

One resolution gives ``ResolvedInputs + MaterialProbe + SettingsSnapshot``; ``preflight()`` decides from those three
values only, and every entry (HTTP / CLI / MCP / Celery import / pipelines / confirm) calls it and only converts
the result to its own protocol. HTTP entries call ``backend.api.v1.transcription_gate.run`` so the whole check (settings read, ffprobe,
ffmpeg decode fallback) runs in the threadpool, never on the event loop.

Invariants (each has an acceptance test in ``backend/tests/test_preflight.py``):

- The material probe is tri-state: ``not_probed`` / ``readable`` / ``unreadable``. "We did not look" is never
  confused with "we looked and could not read it".
- An unreadable source is decided before any install prompt and blocks before any paid call, SRT or not.
- Too short / no audio block only when the actual route is the subtitle route.
- The material probe runs one ffprobe; its ffmpeg decode fallback reuses that answer (no second ffprobe for the
  duration). This is not "one ffprobe in total": planning's subtitle-route ``has_audio`` check may run one more
  ffprobe for the audio stream (#374).
- A refusal is raised before the caller creates a project, changes state or keeps a staged file.
"""
from __future__ import annotations

from backend.core.failure_codes import UserFacingError
import enum
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, Optional

from backend.pipeline.failures import PipelineFailure

Entry = Literal['studio', 'content']


class ProbeState(str, enum.Enum):
    NOT_PROBED = 'not_probed'
    READABLE = 'readable'
    UNREADABLE = 'unreadable'


@dataclass(frozen=True)
class MaterialProbe:
    """What one ffprobe (plus at most one ffmpeg decode) found. ``audio`` None = could not tell (never blocks)."""
    state: ProbeState = ProbeState.NOT_PROBED
    source: Optional[Path] = None
    duration: Optional[float] = None
    audio: Optional[bool] = None
    width: Optional[int] = None
    height: Optional[int] = None
    ffprobe_runs: int = 0
    decode_runs: int = 0
    diagnostics: str = ''  # sanitized tool output (no paths); never sent to telemetry

    @property
    def probed(self) -> bool:
        return self.state is not ProbeState.NOT_PROBED


NOT_PROBED = MaterialProbe()


@dataclass(frozen=True)
class ResolvedInputs:
    video: Optional[Path]
    subtitle: Optional[Path] = None
    entry: Entry = 'content'
    goal: Optional[str] = 'auto'
    # Route already fixed by the caller (confirm page: the confirmed analysis), else derived from settings.
    route: Optional[Literal['subtitle', 'visual']] = None

    @property
    def srt_available(self) -> bool:
        return bool(self.subtitle and Path(self.subtitle).is_file())


@dataclass(frozen=True)
class SettingsSnapshot:
    transcription_provider: str
    transcription_code: Optional[str]
    transcription_ok: bool
    analysis_mode: Optional[str]
    vision_configured: bool


@dataclass(frozen=True)
class PreflightResult:
    inputs: ResolvedInputs
    probe: MaterialProbe
    settings: SettingsSnapshot
    route: Literal['subtitle', 'visual']
    route_certain: bool
    source_failure: Optional[PipelineFailure] = None
    transcription_code: Optional[str] = None  # one of readiness.GATE_CODES when the install prompt applies
    asr_failure: Optional[PipelineFailure] = None  # ASR not usable in a way the install prompt does not cover

    @property
    def ok(self) -> bool:
        return self.source_failure is None and self.transcription_code is None and self.asr_failure is None


class SourceRejected(ValueError):
    """Preflight refusal for the source itself (user cause). HTTP sends ``detail`` as the coded 422."""

    def __init__(self, failure: PipelineFailure):
        self.failure = failure
        self.code = failure.code
        super().__init__(failure.user_message())

    @property
    def detail(self) -> dict:
        return {'code': self.code, 'message': str(self)}


# ------------------------------------------------------------------------------------------------ probe ---
def probe_material(video) -> MaterialProbe:
    """One ffprobe; when it reads no duration, one ffmpeg decode that reuses its answer (never a second ffprobe)."""
    import json
    import subprocess
    from backend.pipeline import media_precheck
    path = Path(video)
    data = None
    try:
        from backend.utils.ffmpeg_utils import get_ffprobe_path
        result = subprocess.run(
            [get_ffprobe_path(), '-v', 'error', '-show_entries',
             'stream=codec_type,width,height:format=duration', '-of', 'json', str(path)],
            capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=30,
        )
        if result.returncode == 0:
            parsed = json.loads(result.stdout or '{}')
            data = parsed if isinstance(parsed, dict) else None
        stderr = '' if data is not None else (result.stderr or '')
    except Exception as error:  # noqa: BLE001 - a missing ffprobe is "could not tell", decided by the decode below
        stderr = type(error).__name__
    duration = audio = width = height = None
    if data is not None:
        streams = [row for row in data.get('streams') or [] if isinstance(row, dict)]
        try:
            duration = float((data.get('format') or {}).get('duration'))
        except (TypeError, ValueError, AttributeError):
            duration = None
        if streams:
            audio = any(row.get('codec_type') == 'audio' for row in streams)
            video_row = next((row for row in streams if row.get('codec_type') == 'video'), {})
            width, height = video_row.get('width'), video_row.get('height')
    return _after_ffprobe(path, duration, audio, width, height, stderr)


def _after_ffprobe(path: Path, duration, audio, width, height, stderr: str = '') -> MaterialProbe:
    """Finish a probe whose one ffprobe already ran: no duration -> one ffmpeg decode, never a second ffprobe."""
    from backend.pipeline import media_precheck
    if duration and duration > 0:
        return MaterialProbe(ProbeState.READABLE, path, duration, audio, width, height, ffprobe_runs=1)
    found, decode_err = media_precheck.ffmpeg_decode_duration(path)
    if found:
        return MaterialProbe(ProbeState.READABLE, path, found, audio, width, height, ffprobe_runs=1, decode_runs=1)
    detail = media_precheck.sanitize_tool_output(f'ffprobe: {stderr or "no duration"}\nffmpeg: {decode_err}', path)
    return MaterialProbe(ProbeState.UNREADABLE, path, None, audio, width, height,
                         ffprobe_runs=1, decode_runs=1, diagnostics=detail)


def probe_from_info(video, info: Optional[dict]) -> MaterialProbe:
    """#351: a caller that already ran its ffprobe (``info``) gets the same probe without a second ffprobe."""
    if info is None:
        return probe_material(video)
    try:
        duration = float(info.get('duration') or 0) or None
    except (TypeError, ValueError):
        duration = None
    return _after_ffprobe(Path(video), duration, info.get('audio'), info.get('width'), info.get('height'))


def classify_source(probe: MaterialProbe, *, srt_available: bool, subtitle_route: bool,
                    stage: str = 'INGEST') -> Optional[PipelineFailure]:
    """The one source classification. Unreadable / under 1 s block on every route; too short / no audio only
    on the subtitle route. A probe that did not run is a caller bug, never a pass."""
    from backend.pipeline import media_precheck
    if probe.state is ProbeState.NOT_PROBED:
        raise RuntimeError('classify_source needs a probed source')
    if probe.state is ProbeState.UNREADABLE:
        return media_precheck.SourceUnreadable(probe.diagnostics, stage)
    if probe.duration is not None and probe.duration < 1:
        return PipelineFailure(stage, media_precheck.TOO_SHORT_1S_MESSAGE, code=media_precheck.SOURCE_TOO_SHORT)
    if not subtitle_route:
        return None
    if media_precheck.too_short(probe.duration):
        return media_precheck.too_short_failure(stage)
    if not srt_available and probe.audio is False:
        return media_precheck.no_audio_failure(stage)
    return None


# --------------------------------------------------------------------------------------------- settings ---
def snapshot_settings() -> SettingsSnapshot:
    from backend.services import ai_model_settings as ai_models
    from backend.services.studio import planning, readiness
    settings = readiness._gate_settings()  # missing / unreadable -> defaults, same view as the runtime check
    choice = settings.transcription or ai_models.Transcription()
    check = readiness.transcription_check()  # the one runtime check the pipeline also reads
    mode = planning.preferred_analysis_mode()
    return SettingsSnapshot(
        transcription_provider=choice.provider,
        transcription_code=check.get('code'),
        transcription_ok=bool(check.get('ok')),
        analysis_mode=mode,
        vision_configured=planning.vision_configured(mode) if mode else False,
    )


# -------------------------------------------------------------------------------------------- preflight ---
def _route(inputs: ResolvedInputs, probe: MaterialProbe, settings: SettingsSnapshot) -> tuple[str, bool]:
    """(route assumed before screening, certain). The content entry always takes the subtitle route."""
    from backend.services.studio import planning
    if inputs.route:
        return inputs.route, True
    if inputs.entry == 'content' or settings.analysis_mode is None:
        return 'subtitle', True
    mode = settings.analysis_mode
    goal = planning.final_goal(inputs.goal, mode, settings.vision_configured)
    before = planning.resolve_route(mode, goal, probe.duration)
    # What screening could still change: a configured vision model may pick a visual goal for goal=auto.
    screened = planning.final_goal(inputs.goal, mode, settings.vision_configured, screened='highlight')
    after = planning.resolve_route(mode, screened, probe.duration, ai_screened=settings.vision_configured)
    return before, before == after


def preflight(inputs: ResolvedInputs, *, probe: MaterialProbe = NOT_PROBED,
              settings: Optional[SettingsSnapshot] = None, stage: str = 'INGEST') -> PreflightResult:
    from backend.services.studio import readiness
    if settings is None:
        settings = snapshot_settings()
    if not probe.probed:
        if inputs.video is None:
            raise FileNotFoundError('视频不存在')
        probe = probe_material(inputs.video)  # a missing file is simply unreadable here
    route, certain = _route(inputs, probe, settings)
    srt = inputs.srt_available
    # 1. the source: decided before any install prompt, on every entry, SRT or not.
    failure = classify_source(probe, srt_available=srt, subtitle_route=(route == 'subtitle' and certain), stage=stage)
    base = PreflightResult(inputs, probe, settings, route, certain)
    if failure is not None:
        return replace(base, source_failure=failure)
    # 2. transcription: only when the route transcribes and no SRT is attached.
    if srt or route != 'subtitle' or settings.transcription_ok:
        return base
    if settings.transcription_provider == 'whisper_local' and settings.transcription_code in readiness.GATE_CODES:
        return replace(base, transcription_code=settings.transcription_code)
    try:
        readiness.require_transcription(stage='SUBTITLE', srt_available=False, analysis_mode='subtitle')
    except PipelineFailure as missing:
        return replace(base, asr_failure=missing)
    return base


def enforce(result: PreflightResult) -> PreflightResult:
    """Entry-side conversion: raise the one refusal, source first."""
    from backend.services.studio import readiness
    if result.source_failure is not None:
        raise SourceRejected(result.source_failure)
    if result.transcription_code is not None:
        raise readiness.TranscriptionNotReady(result.transcription_code)
    if result.asr_failure is not None:
        raise UserFacingError(result.asr_failure.user_message())
    return result


def check(inputs: ResolvedInputs, **kwargs) -> PreflightResult:
    return enforce(preflight(inputs, **kwargs))


def project_inputs(project_id: str, *, entry: Entry = 'content', goal: Optional[str] = 'auto') -> Optional[ResolvedInputs]:
    """Inputs of a project already on disk (raw/input.* + raw/input.srt), or None when it has no local video."""
    from backend.core.path_utils import get_project_raw_directory
    raw = get_project_raw_directory(project_id)
    video = next((raw / f'input{ext}' for ext in ('.mp4', '.mov', '.mkv', '.webm', '.avi')
                  if (raw / f'input{ext}').is_file()), None)
    if video is None:
        return None
    return ResolvedInputs(video, raw / 'input.srt', entry=entry, goal=goal)


def path_inputs(video, srt=None, *, sibling_srt: bool = True, entry: Entry = 'content',
                goal: Optional[str] = 'auto') -> Optional[ResolvedInputs]:
    """Inputs for entries that have paths. ``sibling_srt`` counts ``input.srt`` beside the video (project raw dir
    only). A missing video is not this check's business (those paths re-download or fail on their own)."""
    if not video or not Path(video).is_file():
        return None
    subtitle = Path(srt) if srt else (Path(video).parent / 'input.srt' if sibling_srt else None)
    return ResolvedInputs(Path(video), subtitle, entry=entry, goal=goal)
