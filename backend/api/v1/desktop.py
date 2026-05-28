"""
桌面专用API端点
提供桌面应用需要的特殊功能
"""
import os
import psutil
import platform
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.core.desktop_config import get_desktop_config, is_desktop_mode

router = APIRouter()

# 检查桌面模式
def check_desktop_mode():
    if not is_desktop_mode():
        raise HTTPException(status_code=400, detail="此端点仅在桌面模式下可用")

class SystemInfo(BaseModel):
    """系统信息模型"""
    platform: str
    platform_version: str
    architecture: str
    processor: str
    memory_total: int
    memory_available: int
    memory_usage_percent: float
    disk_usage_percent: float
    python_version: str
    app_version: str

class ServiceStatus(BaseModel):
    """服务状态模型"""
    is_running: bool
    port: int
    uptime: str
    memory_usage: int
    cpu_usage: float
    last_health_check: str

@router.get("/system/info", response_model=SystemInfo)
async def get_system_info():
    """获取系统信息"""
    check_desktop_mode()
    
    try:
        # 获取系统信息
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return SystemInfo(
            platform=platform.system(),
            platform_version=platform.version(),
            architecture=platform.machine(),
            processor=platform.processor(),
            memory_total=memory.total,
            memory_available=memory.available,
            memory_usage_percent=memory.percent,
            disk_usage_percent=disk.percent,
            python_version=platform.python_version(),
            app_version=get_desktop_config().app_version
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统信息失败: {str(e)}")

@router.get("/service/status", response_model=ServiceStatus)
async def get_service_status():
    """获取服务状态"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        process = psutil.Process()
        
        return ServiceStatus(
            is_running=True,
            port=config.port,
            uptime=str(datetime.now() - datetime.fromtimestamp(process.create_time())),
            memory_usage=process.memory_info().rss,
            cpu_usage=process.cpu_percent(),
            last_health_check=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取服务状态失败: {str(e)}")

@router.get("/logs")
async def get_logs(lines: int = 100):
    """获取应用日志"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        log_file = config.data_dir / "logs" / "autoclip.log"
        
        if not log_file.exists():
            return {"logs": [], "message": "日志文件不存在"}
        
        # 读取最后N行日志
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "logs": [line.strip() for line in recent_lines],
            "total_lines": len(all_lines),
            "returned_lines": len(recent_lines)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志失败: {str(e)}")

@router.post("/service/restart")
async def restart_service():
    """重启服务（仅返回成功，实际重启由Tauri处理）"""
    check_desktop_mode()
    
    return {
        "message": "服务重启请求已发送",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/config")
async def get_config():
    """获取当前配置"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        return {
            "config": config.dict(),
            "paths": {
                "data_dir": str(config.paths.data_dir),
                "projects_dir": str(config.paths.data_dir / "projects"),
                "logs_dir": str(config.paths.data_dir / "logs")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")

@router.put("/config")
async def update_config(config_data: Dict[str, Any]):
    """更新配置"""
    check_desktop_mode()
    
    try:
        from backend.core.desktop_config import save_desktop_config, DesktopConfig
        
        # 验证配置数据
        config = DesktopConfig(**config_data)
        
        # 保存配置
        if save_desktop_config(config):
            return {"message": "配置更新成功", "config": config.dict()}
        else:
            raise HTTPException(status_code=500, detail="配置保存失败")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置更新失败: {str(e)}")

@router.get("/health/detailed")
async def detailed_health_check():
    """详细健康检查"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        
        # 检查数据库连接
        db_status = "healthy"
        try:
            from backend.core.database import get_db
            # 简单的数据库连接测试
            db_status = "healthy"
        except Exception:
            db_status = "unhealthy"
        
        # 检查Celery连接
        celery_status = "healthy"
        try:
            from backend.desktop_celery import celery_app
            celery_app.control.inspect().stats()
            celery_status = "healthy"
        except Exception:
            celery_status = "unhealthy"
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": config.app_version,
            "mode": "desktop",
            "components": {
                "database": db_status,
                "celery": celery_status,
                "api": "healthy"
            },
            "system": {
                "memory_usage": psutil.virtual_memory().percent,
                "cpu_usage": psutil.cpu_percent(),
                "disk_usage": psutil.disk_usage('/').percent
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")
