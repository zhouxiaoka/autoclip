"""Remove leftover project directories that no longer have a database row (RC156 PR4 leftover).

Deleting a project used to leave its directory behind when a mid-run worker
recreated files after the delete (RC156 #12). After that fix, directories that
were already left behind from earlier releases still sit under the projects
root. At startup we remove only those directories whose id has no Project
row, never anything outside the projects root. A DB read failure removes
nothing.
"""
from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ID = re.compile(r'^[a-zA-Z0-9_-]{1,100}$')


def cleanup_orphan_project_directories(session_factory=None, projects_root: Path | None = None) -> list[str]:
    """Return the ids that were removed. Empty when the DB cannot be read."""
    from backend.core.path_utils import get_projects_directory
    from backend.models.project import Project
    root = Path(projects_root) if projects_root is not None else get_projects_directory()
    try:
        root = root.resolve()
    except OSError as error:
        logger.warning('Orphan project cleanup skipped: cannot resolve projects root (%s)', type(error).__name__)
        return []
    if not root.is_dir():
        return []
    if session_factory is None:
        from backend.core.database import SessionLocal as session_factory
    try:
        with session_factory() as db:
            known = {str(row.id) for row in db.query(Project.id).all()}
    except Exception as error:  # noqa: BLE001 - any DB failure: remove nothing
        logger.warning('Orphan project cleanup skipped: database read failed (%s)', type(error).__name__)
        return []
    if not known:
        # An empty table next to a populated projects root more likely means a fresh or
        # different database (DATABASE_URL / data dir mismatch) than real orphans.
        logger.info('Orphan project cleanup skipped: no project rows in the database')
        return []
    removed = []
    try:
        children = list(root.iterdir())
    except OSError as error:
        logger.warning('Orphan project cleanup skipped: cannot list projects root (%s)', type(error).__name__)
        return []
    for child in children:
        name = child.name
        if not child.is_dir() or not _PROJECT_ID.fullmatch(name) or name in known:
            continue
        try:
            resolved = child.resolve()
            if root not in resolved.parents and resolved != root:
                logger.warning('Orphan project cleanup refused a path outside the projects root: %s', name)
                continue
            shutil.rmtree(resolved)
            removed.append(name)
            logger.info('Removed leftover project directory with no database row: %s', name)
        except OSError as error:
            logger.warning('Could not remove leftover project directory %s: %s', name, type(error).__name__)
    if removed:
        logger.info('Orphan project cleanup removed %d leftover director%s', len(removed), 'y' if len(removed) == 1 else 'ies')
    return removed
