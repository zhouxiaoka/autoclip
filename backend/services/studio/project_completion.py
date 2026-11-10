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
            failure = _failure(generation, analysis) if outcome != 'completed' else (None, None, None, None, None)
            billable = _billable_before_failure(generation, analysis) if outcome != 'completed' else None
            if db is not None:
                return _update_index(project_id, db, outcome, completed, len(drafts), failure, billable)
            from backend.core.database import SessionLocal
            with SessionLocal() as session:
                return _update_index(project_id, session, outcome, completed, len(drafts), failure, billable)
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


def _failure(generation, analysis):
    """The run's own reason. A placeholder generation must not hide the analysis cause (RC156 #13 4b)."""
    chosen = _choose_failure(generation, analysis)
    message = chosen.get('error') if isinstance(chosen, dict) else None
    code = chosen.get('error_code') if isinstance(chosen, dict) else None
    stage = None
    if isinstance(analysis, dict) and isinstance(analysis.get('failure_stage'), str) and analysis.get('failure_stage'):
        stage = analysis.get('failure_stage')
    elif isinstance(chosen, dict) and isinstance(chosen.get('failure_stage'), str):
        stage = chosen.get('failure_stage') or None
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
            code if isinstance(code, str) and code else None,
            stage,
            phase,
            calls)


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


def _update_index(project_id, db, outcome, completed, draft_count, failure=(None, None, None, None, None), billable=None):
    from backend.models.project import Project, ProjectStatus
    project = db.get(Project, project_id)
    if project is None or not (project.processing_config or {}).get('smart_import'):
        return False
    status = ProjectStatus.COMPLETED if outcome == 'completed' else ProjectStatus.FAILED
    config = {key: value for key, value in (project.processing_config or {}).items()
              if key not in ('studio_generation_error', 'studio_generation_error_code', 'billable_calls_before_failure',
                             'failure_stage', 'analysis_phase', 'llm_calls')}
    config.update(studio_completed_variant_count=completed, studio_draft_count=draft_count, studio_generation_status=outcome)
    message, code, stage, phase, calls = failure if len(failure) == 5 else (*failure, None, None, None)
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
