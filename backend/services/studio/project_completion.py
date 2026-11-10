"""Mirror durable automatic-generation terminals into the project index."""
from datetime import datetime, timezone
import json
import logging

from sqlalchemy.exc import SQLAlchemyError

from backend.services.studio import store

logger = logging.getLogger(__name__)


def sync_project_completion(project_id, db=None):
    # Serialize with re-screening so an old terminal cannot overwrite a new run.
    # A failed mirror must not turn an already saved video into a failed render;
    # project-list reads retry the mirror from the durable receipt.
    with store.lock:
        try:
            path = store.directory(project_id) / 'metadata' / 'studio.json'
            if not path.is_file():
                return False
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                return False
            generation = data.get('generation') or {}
            analysis = data.get('analysis') or {}
            raw_variants = data.get('output_variants') or []
            drafts = data.get('drafts') or []
            if not isinstance(generation, dict) or not isinstance(analysis, dict) or not isinstance(raw_variants, list):
                return False
            if any(not isinstance(item, dict) for item in raw_variants):
                return False
            if not isinstance(drafts, list) or any(not isinstance(item, dict) for item in drafts):
                return False
            if store.has_pending_receipts(project_id) or store.interrupted_run(data):
                # A run left by a previous process (RC156 #13) is closed by the owned
                # recovery read, which persists the failed terminal before mirroring.
                # Preserve the raw observer's shape guards before attempting the
                # owned receipt recovery needed by a list-first refresh.
                raw_jobs = data.get('jobs', [])
                if not isinstance(raw_jobs, list) or any(not isinstance(row, dict) or not row.get('job_id') or not row.get('status') for row in raw_jobs):
                    return False
                actual_variants = data.get('output_variants', [])
                if not isinstance(actual_variants, list) or any(not isinstance(row, dict) or not row.get('id') or not row.get('status') or (row.get('cover_job') and not isinstance(row['cover_job'], dict)) for row in actual_variants):
                    return False
                if analysis and not analysis.get('status'):
                    return False
                store.recover(project_id)
                data = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(data, dict):
                    return False
                generation = data.get('generation') or {}
                analysis = data.get('analysis') or {}
                raw_variants = data.get('output_variants') or []
                drafts = data.get('drafts') or []
                if not isinstance(generation, dict) or not isinstance(analysis, dict) or not isinstance(raw_variants, list) or not isinstance(drafts, list):
                    return False
                if any(not isinstance(row, dict) for row in [*raw_variants, *drafts]):
                    return False
            outcome = generation.get('status')
            variants = [item for item in raw_variants if item.get('status') != 'on_demand']
            if not generation.get('auto_start') or outcome not in ('completed', 'partial', 'failed'):
                return False
            # generation.status is the project-index source of truth. A terminal
            # receipt must leave SQLite even when analysis or variant rows lag.
            completed = sum(item.get('status') == 'completed' for item in variants)
            jobs = data.get('jobs') if isinstance(data.get('jobs'), list) else []
            attempts = data.get('attempts') if isinstance(data.get('attempts'), list) else []
            failure = _failure(generation, analysis, attempts) if outcome != 'completed' else (None, None, None, None, None, None, None)
            billable = _billable_before_failure(generation, analysis) if outcome != 'completed' else None
            if db is not None:
                return _update_index(project_id, db, outcome, completed, len(drafts), failure, billable, variants, jobs)
            from backend.core.database import SessionLocal
            with SessionLocal() as session:
                return _update_index(project_id, session, outcome, completed, len(drafts), failure, billable, variants, jobs)
        except (OSError, ValueError, SQLAlchemyError) as error:
            if db is not None and isinstance(error, SQLAlchemyError):
                db.rollback()
            logger.warning('Studio project completion mirror deferred: %s', type(error).__name__)
            return False


_PLACEHOLDER_CODES = {'validation', 'multiple', 'unknown'}
_EMPTY_VARIANT = '没有自动生成的成片，可选择备选片段继续生成'


def _specific(record):
    """A pipeline cause, not the empty-output placeholder settle_generation writes."""
    if not isinstance(record, dict):
        return False
    code = record.get('error_code')
    if not isinstance(code, str) or not code or code in _PLACEHOLDER_CODES:
        return False
    message = record.get('error')
    if message == _EMPTY_VARIANT:
        return False
    return True


def _choose_failure(generation, analysis):
    """Receipt fields are copied by the caller. Here, analysis wins a conflict with a placeholder generation."""
    analysis_specific = _specific(analysis)
    generation_specific = _specific(generation)
    if analysis_specific and not generation_specific:
        return analysis
    if generation_specific and not analysis_specific:
        return generation
    if analysis_specific and generation_specific and analysis.get('error_code') != generation.get('error_code'):
        return analysis
    if isinstance(generation, dict) and (generation.get('error') or generation.get('error_code')):
        return generation
    return analysis if isinstance(analysis, dict) else {}


def _text(value):
    return value if isinstance(value, str) and value else None


def _string_list(value):
    if not isinstance(value, list):
        return []
    return [item if isinstance(item, str) else '' for item in value]


def _same_run_causes(analysis, attempts):
    """Latest settled receipt only when its run_id is the analysis run. A different run is ignored."""
    run_id = _text(analysis.get('run_id')) if isinstance(analysis, dict) else None
    if not run_id or not isinstance(attempts, list):
        return None
    settled = [item for item in attempts if isinstance(item, dict) and item.get('state') in ('completed', 'partial', 'failed')]
    if not settled:
        return None
    latest = max(settled, key=lambda item: item.get('sequence') or 0)
    causes = latest.get('causes')
    if latest.get('run_id') != run_id or latest.get('state') == 'completed' or not isinstance(causes, list) or not causes:
        return None
    if not isinstance(causes[0], dict):
        return None
    return causes


def _failure(generation, analysis, attempts=None):
    """The run's own reason. Stage and upstream come from that chosen record.

    Analysis.failure_stage is not copied over a generation cause: a screening
    label left on the analysis row must not hide this attempt's render stage.
    A same-run receipt then replaces code, stage, upstream and secondaries.
    A receipt for another run is left untouched. Missing fields stay empty.
    """
    chosen = _choose_failure(generation, analysis)
    message = chosen.get('error') if isinstance(chosen, dict) else None
    code = _text(chosen.get('error_code')) if isinstance(chosen, dict) else None
    stage = _text(chosen.get('failure_stage')) if isinstance(chosen, dict) else None
    upstream = _text(chosen.get('upstream_error_type')) if isinstance(chosen, dict) else None
    secondary = (
        _string_list(chosen.get('secondary_error_codes')),
        _string_list(chosen.get('secondary_upstream_error_types')),
        _string_list(chosen.get('secondary_failure_stages')),
    ) if isinstance(chosen, dict) else ([], [], [])
    causes = _same_run_causes(analysis, attempts)
    if causes:
        primary = causes[0]
        code = _text(primary.get('code')) or code
        stage = _text(primary.get('stage')) or stage
        upstream = _text(primary.get('upstream')) or upstream
        rest = [item for item in causes[1:] if isinstance(item, dict)]
        secondary = (
            [_text(item.get('code')) or '' for item in rest],
            [_text(item.get('upstream')) or '' for item in rest],
            [_text(item.get('stage')) or '' for item in rest],
        )
    phase = analysis.get('phase') if isinstance(analysis, dict) and isinstance(analysis.get('phase'), str) else None
    calls = None
    for record in (analysis, generation):
        if not isinstance(record, dict):
            continue
        try:
            count = int(record.get('llm_calls'))
        except (TypeError, ValueError):
            continue
        if count > 0:
            calls = count if calls is None else max(calls, count)
    return (message[:700] if isinstance(message, str) and message else None,
            code,
            stage,
            phase,
            calls,
            upstream,
            secondary)


def preserved_result_count(drafts, variants, jobs, clips=0, collections=0):
    """Things the user can still open. A completed export already represented by a variant is not counted again."""
    draft_count = len(drafts) if isinstance(drafts, list) else 0
    variant_rows = [item for item in variants if isinstance(item, dict) and item.get('status') == 'completed'] if isinstance(variants, list) else []
    represented = {item.get('render_job_id') for item in variant_rows if item.get('render_job_id')}
    job_count = 0
    if isinstance(jobs, list):
        job_count = sum(1 for item in jobs if isinstance(item, dict) and item.get('status') == 'completed' and item.get('job_id') not in represented)
    return draft_count + len(variant_rows) + job_count + max(0, int(clips or 0)) + max(0, int(collections or 0))


def _billable_before_failure(generation, analysis):
    """Max positive billable_calls from analysis/generation so the home card can show 「本次已消耗」."""
    counts = []
    for record in (generation, analysis):
        if not isinstance(record, dict):
            continue
        try:
            count = int(record.get('billable_calls_before_failure'))
        except (TypeError, ValueError):
            continue
        if count > 0:
            counts.append(count)
    return max(counts) if counts else None


def _update_index(project_id, db, outcome, completed, draft_count, failure=(None, None, None, None, None, None, None), billable=None, variants=(), jobs=()):
    from backend.models.clip import Clip
    from backend.models.collection import Collection
    from backend.models.project import Project, ProjectStatus
    project = db.get(Project, project_id)
    if project is None or not (project.processing_config or {}).get('smart_import'):
        return False
    status = ProjectStatus.COMPLETED if outcome == 'completed' else ProjectStatus.FAILED
    dropped = ('studio_generation_error', 'studio_generation_error_code', 'billable_calls_before_failure',
               'failure_stage', 'analysis_phase', 'llm_calls', 'upstream_error_type',
               'secondary_error_codes', 'secondary_upstream_error_types', 'secondary_failure_stages',
               'preserved_result_count')
    config = {key: value for key, value in (project.processing_config or {}).items() if key not in dropped}
    clips = db.query(Clip).filter(Clip.project_id == project_id).count()
    collections = db.query(Collection).filter(Collection.project_id == project_id).count()
    config.update(
        studio_completed_variant_count=completed,
        studio_draft_count=draft_count,
        studio_generation_status=outcome,
        preserved_result_count=preserved_result_count([], variants, jobs, clips, collections) + draft_count,
    )
    fields = failure if len(failure) >= 7 else (*failure, *([None] * (7 - len(failure))))
    message, code, stage, phase, calls, upstream, secondary = fields[:7]
    if message:
        config['studio_generation_error'] = message
    if code:
        config['studio_generation_error_code'] = code
    if stage:
        config['failure_stage'] = stage
    if phase:
        config['analysis_phase'] = phase
    if isinstance(calls, int) and calls > 0:
        config['llm_calls'] = calls
    if upstream:
        config['upstream_error_type'] = upstream
    if isinstance(secondary, tuple) and any(secondary):
        config['secondary_error_codes'], config['secondary_upstream_error_types'], config['secondary_failure_stages'] = secondary
    if isinstance(billable, int) and billable > 0:
        config['billable_calls_before_failure'] = billable
    if project.status == status and project.processing_config == config:
        return False
    project.status = status
    project.processing_config = config
    if status is ProjectStatus.COMPLETED and project.completed_at is None:
        project.completed_at = datetime.now(timezone.utc)
    db.commit()
    return True
