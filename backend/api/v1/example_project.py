"""Example project endpoints: create the bundled, already-finished project on demand."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.services import example_project

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get('/example-project')
def example_project_info(db: Session = Depends(get_db)):
    existing = example_project.find_existing(db)
    return {'available': example_project.available(), 'project_id': existing.id if existing else None}


@router.post('/example-project/create')
def create_example_project(db: Session = Depends(get_db)):
    existing = example_project.find_existing(db)
    try:
        project = example_project.create(db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        logger.exception('创建示例项目失败')
        raise HTTPException(status_code=500, detail='创建示例项目失败，请稍后重试')
    return {'project_id': project.id, 'name': project.name, 'resolution': 'reused' if existing else 'created', 'example_version': (project.processing_config or {}).get('example_version', 1)}
