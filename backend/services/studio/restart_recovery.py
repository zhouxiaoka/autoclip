"""Close Studio runs that a previous process left unfinished (RC156 Win QA #13).

Studio workers run in this process's thread pools. When the app is killed during
screening, the content (LLM) pipeline or a render, nothing ever finishes that run:
the generation stayed in production and the project index showed processing (or
completed, before #8) with no reason. At startup every such project is read with
recovery, which persists a failed terminal with 「服务已重启，请重新生成」, and the
project index is synced so the home card shows failed and a way back in.
"""
import json
import logging

logger = logging.getLogger(__name__)


def reconcile_interrupted_projects(session_factory=None) -> list[str]:
    from backend.models.project import Project, ProjectStatus
    from backend.services.studio import store
    from backend.services.studio.project_completion import sync_project_completion
    if session_factory is None:
        from backend.core.database import SessionLocal as session_factory
    recovered = []
    with session_factory() as db:
        rows = [(str(row.id), row.status) for row in db.query(Project).all() if (row.processing_config or {}).get('smart_import')]
    for project_id, status in rows:
        try:
            path = store.directory(project_id) / 'metadata' / 'studio.json'
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or not store.interrupted_run(data):
                continue
            data = store.read(project_id)  # owned recovery: persists the failed terminal
            generation = data.get('generation') or {}
            if generation.get('auto_start'):
                sync_project_completion(project_id)
            elif status == ProjectStatus.PROCESSING and (data.get('analysis') or {}).get('status') == 'failed':
                _fail_manual(session_factory, project_id, data['analysis'])
            recovered.append(project_id)
        except Exception as error:  # noqa: BLE001 - one bad project must not block startup
            logger.warning('Studio restart recovery skipped a project: %s', type(error).__name__)
    if recovered:
        logger.info('Studio restart recovery closed %d interrupted run(s): %s', len(recovered), ', '.join(recovered))
    return recovered


def _fail_manual(session_factory, project_id, analysis):
    from backend.models.project import Project, ProjectStatus
    with session_factory() as db:
        project = db.get(Project, project_id)
        if project is None or project.status != ProjectStatus.PROCESSING:
            return
        project.status = ProjectStatus.FAILED
        project.project_metadata = {**(project.project_metadata or {}), 'last_error': analysis.get('error'),
                                    'last_error_code': analysis.get('error_code')}
        db.commit()
