"""
处理API路由
提供项目处理相关的接口
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.services.processing_service import ProcessingService

router = APIRouter()


def get_processing_service(db: Session = Depends(get_db)) -> ProcessingService:
    """Dependency to get processing service."""
    return ProcessingService(db)


@router.post("/projects/{project_id}/process")
async def process_project(
    project_id: str,
    processing_service: ProcessingService = Depends(get_processing_service)
):
    """开始处理项目"""
    try:
        result = processing_service.process_project(project_id)
        return {
            "message": "项目处理已开始",
            "project_id": project_id,
            "result": result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"缺少必要文件: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.get("/projects/{project_id}/processing-status")
async def get_processing_status(
    project_id: str,
    processing_service: ProcessingService = Depends(get_processing_service)
):
    """获取项目处理状态"""
    try:
        status = processing_service.get_processing_status(project_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.post("/projects/{project_id}/process/step/{step_number}")
async def process_step(
    project_id: str,
    step_number: int,
    processing_service: ProcessingService = Depends(get_processing_service)
):
    """处理单个步骤"""
    if step_number < 1 or step_number > 6:
        raise HTTPException(status_code=400, detail="步骤编号必须在1-6之间")
    
    try:
        # 这里可以扩展为处理单个步骤
        result = processing_service.process_project(project_id)
        return {
            "message": f"步骤 {step_number} 处理完成",
            "project_id": project_id,
            "step": step_number,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"步骤处理失败: {str(e)}")