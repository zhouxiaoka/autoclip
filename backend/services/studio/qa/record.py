"""Attach a shadow report after the file is already saved. Never rewrites it."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.core.sentry_setup import capture_studio_exception
from backend.services.studio.features import DEFAULTS
from backend.services.studio.qa import avsync, ending, face, jitter, loudness
from backend.services.studio.qa.report import CHECKERS, Context, QaCheckerError, SceneSpan, run_checks
from backend.services.studio.store import change, directory, read

logger = logging.getLogger(__name__)

RUNNERS = (
    ('avsync', avsync.check),
    ('face', face.check),
    ('loudness', loudness.check),
    ('jitter', jitter.check),
    ('ending', ending.check),
)


def effective_mode(features: dict | None) -> str:
    """off, or shadow. `block` is accepted and recorded as shadow."""
    data = features if isinstance(features, dict) else {}
    if data.get('autoclip_safe_mode') is True:
        return 'off'
    value = data.get('qa_gate_blocking', DEFAULTS['qa_gate_blocking'])
    if value == 'blocking':
        value = 'block'
    if value in ('shadow', 'block'):
        return 'shadow'
    return 'off'


def _num(value, default=0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _scenes(draft) -> list[SceneSpan]:
    raw = getattr(draft, 'scenes', None)
    if raw is None and isinstance(draft, dict):
        raw = draft.get('scenes') or []
    spans = []
    for scene in raw or []:
        if isinstance(scene, dict):
            start, end, points = scene.get('start'), scene.get('end'), scene.get('crop_track') or []
        else:
            start, end, points = getattr(scene, 'start', 0), getattr(scene, 'end', 0), getattr(scene, 'crop_track', None) or []
        parsed = []
        for point in points:
            if isinstance(point, dict):
                parsed.append((_num(point.get('start')), _num(point.get('crop_x'), 0.5)))
            else:
                parsed.append((_num(getattr(point, 'start', 0)), _num(getattr(point, 'crop_x', 0.5), 0.5)))
        spans.append(SceneSpan(_num(start), _num(end), parsed))
    return spans


def _flag(draft, name: str, default=False):
    if isinstance(draft, dict):
        return draft.get(name, default)
    return getattr(draft, name, default)


def _words(source: Path | None) -> list[dict] | None:
    if source is None:
        return None
    srt = source.parent / 'input.srt'
    if not srt.is_file():
        return None
    from backend.utils.word_timing import load_word_timing
    segments = load_word_timing(srt)
    if not segments:
        return None
    words = []
    for segment in segments:
        for word in segment.get('words') or []:
            text = word.get('text')
            if isinstance(text, str) and text.strip():
                words.append({'start': float(word['start']), 'end': float(word['end']), 'text': text.strip()})
    return words or None


def _source(project_id: str) -> Path | None:
    try:
        from backend.services.publish_export import find_source_video
        return find_source_video(project_id)
    except (OSError, FileNotFoundError, ValueError):
        return None


def _context(project_id: str, draft, result, strategy_id: str) -> Context:
    result = result if isinstance(result, dict) else {}
    packaging = _flag(draft, 'packaging', None)
    title_lines = []
    if packaging is not None:
        title_lines = packaging.get('title_lines', []) if isinstance(packaging, dict) else getattr(packaging, 'title_lines', [])
    hook = _flag(draft, 'hook', '') or ''
    source = _source(project_id)
    return Context(
        source=source,
        scenes=_scenes(draft),
        width=int(_num(result.get('width'), 0)),
        height=int(_num(result.get('height'), 0)),
        strategy_id=strategy_id or 'original',
        words=_words(source),
        captions=bool(_flag(draft, 'subtitles', False) or (packaging is not None)),
        title=bool(hook or title_lines),
        packaged=packaging is not None,
        title_y=_num(_flag(draft, 'title_y', 0.12), 0.12),
    )


def record_after_render(project_id: str, draft, job_id: str, result) -> dict | None:
    """Write OutputVariant.qa when the mode is shadow. Return the report, or None when off."""
    try:
        return _record(project_id, draft, job_id, result)
    except Exception as error:  # noqa: BLE001 - the video is already saved
        logger.warning('QA record failed: %s', type(error).__name__)
        capture_studio_exception(QaCheckerError('runner'), 'qa')
        return None


def _record(project_id: str, draft, job_id: str, result) -> dict | None:
    state = read(project_id)
    features = (state.get('generation') or {}).get('features')
    if effective_mode(features) != 'shadow':
        return None
    variants = [item for item in state.get('output_variants') or [] if item.get('render_job_id') == job_id]
    strategy = 'original'
    for item in variants:
        if item.get('strategy_id') in loudness.TARGETS:
            strategy = item['strategy_id']
            break
    ctx = _context(project_id, draft, result, strategy)
    output = directory(project_id) / 'output' / 'studio' / f'{job_id}.mp4'
    ctx.output = output if output.is_file() else None
    if ctx.width <= 0 or ctx.height <= 0:
        ctx.width = ctx.width or 1080
        ctx.height = ctx.height or 1920
    report = run_checks(ctx, RUNNERS)
    from backend.services.studio.models import QaReport
    clean = QaReport.model_validate(report).model_dump()
    if [row['checker'] for row in clean['checks']] != list(CHECKERS):
        raise RuntimeError('qa report shape')

    def attach(data):
        for variant in data.get('output_variants') or []:
            if variant.get('render_job_id') == job_id:
                variant['qa'] = clean
        for job in data.get('jobs') or []:
            if job.get('job_id') == job_id:
                job['qa'] = clean

    change(project_id, attach)
    _write_sidecar(output, clean)
    return clean


def _write_sidecar(output: Path, report: dict) -> None:
    try:
        if not output.parent.is_dir():
            return
        output.with_suffix('.qa.json').write_text(
            json.dumps(report, ensure_ascii=False, allow_nan=False), encoding='utf-8',
        )
    except OSError:
        capture_studio_exception(QaCheckerError('runner'), 'qa')
