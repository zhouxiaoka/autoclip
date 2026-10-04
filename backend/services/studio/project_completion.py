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
            if store.has_pending_receipts(project_id):
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
                store.read(project_id)
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
            if analysis.get('status') not in ('completed', 'failed'):
                return False
            if any(item.get('status') not in ('completed', 'failed') for item in variants):
                return False
            completed = sum(item.get('status') == 'completed' for item in variants)
            if outcome == 'completed' and (not variants or completed != len(variants)):
                return False
            if db is not None:
                return _update_index(project_id, db, outcome, completed, len(drafts))
            from backend.core.database import SessionLocal
            with SessionLocal() as session:
                return _update_index(project_id, session, outcome, completed, len(drafts))
        except (OSError, ValueError, SQLAlchemyError) as error:
            if db is not None and isinstance(error, SQLAlchemyError):
                db.rollback()
            logger.warning('Studio project completion mirror deferred: %s', type(error).__name__)
            return False


def _update_index(project_id, db, outcome, completed, draft_count):
    from backend.models.project import Project, ProjectStatus
    project = db.get(Project, project_id)
    if project is None or not (project.processing_config or {}).get('smart_import'):
        return False
    status = ProjectStatus.COMPLETED if outcome == 'completed' else ProjectStatus.FAILED
    config = {**(project.processing_config or {}), 'studio_completed_variant_count': completed,
              'studio_draft_count': draft_count}
    if project.status == status and project.processing_config == config:
        return False
    project.status = status
    project.processing_config = config
    if status is ProjectStatus.COMPLETED and project.completed_at is None:
        project.completed_at = datetime.now(timezone.utc)
    db.commit()
    return True
