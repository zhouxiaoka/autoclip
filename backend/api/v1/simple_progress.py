"""
简化的进度API - 提供快照查询接口
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging

from backend.services.simple_progress import get_multiple_progress_snapshots, get_progress_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simple-progress", tags=["simple-progress"])


@router.get("/snapshot")
def get_progress_snapshots(project_ids: List[str] = Query(..., description="项目ID列表")):
    """
    批量获取项目进度快照
    
    Args:
        project_ids: 项目ID列表
        
    Returns:
        进度快照列表
    """
    try:
        if not project_ids:
            return []
            
        snapshots = get_multiple_progress_snapshots(project_ids)
        logger.info(f"获取进度快照: {len(snapshots)} 个项目")
        return snapshots
        
    except Exception as e:
        logger.error(f"获取进度快照失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取进度快照失败: {str(e)}")


@router.get("/snapshot/{project_id}")
def get_single_progress_snapshot(project_id: str):
    """
    获取单个项目进度快照
    
    Args:
        project_id: 项目ID
        
    Returns:
        进度快照数据
    """
    try:
        snapshot = get_progress_snapshot(project_id)
        if snapshot is None:
            # 返回默认状态
            return {
                "project_id": project_id,
                "stage": "INGEST",
                "percent": 0,
                "message": "等待开始",
                "ts": 0
            }
            
        return snapshot
        
    except Exception as e:
        logger.error(f"获取项目进度快照失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目进度快照失败: {str(e)}")


@router.get("/stages")
def get_available_stages():
    """
    获取可用的处理阶段信息
    
    Returns:
        阶段配置信息
    """
    from backend.services.simple_progress import STAGES, STAGE_NAMES
    
    stages_info = []
    for stage, weight in STAGES:
        stages_info.append({
            "stage": stage,
            "weight": weight,
            "display_name": STAGE_NAMES.get(stage, stage)
        })
    
    return {
        "stages": stages_info,
        "total_weight": sum(weight for _, weight in STAGES)
    }
