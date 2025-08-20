"""
设置API路由
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os
import json
from pathlib import Path

router = APIRouter()

class SettingsRequest(BaseModel):
    """设置请求模型"""
    dashscope_api_key: Optional[str] = None
    model_name: Optional[str] = None
    chunk_size: Optional[int] = None
    min_score_threshold: Optional[float] = None
    max_clips_per_collection: Optional[int] = None

class ApiKeyTestRequest(BaseModel):
    """API密钥测试请求"""
    api_key: str

class ApiKeyTestResponse(BaseModel):
    """API密钥测试响应"""
    success: bool
    error: Optional[str] = None

def get_settings_file_path() -> Path:
    """获取设置文件路径"""
    from core.path_utils import get_settings_file_path as get_settings_path
    return get_settings_path()

def load_settings() -> Dict[str, Any]:
    """加载设置"""
    settings_file = get_settings_file_path()
    default_settings = {
        "dashscope_api_key": "",
        "model_name": "qwen-plus",
        "chunk_size": 5000,
        "min_score_threshold": 0.7,
        "max_clips_per_collection": 5
    }
    
    if settings_file.exists():
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                saved_settings = json.load(f)
                # 合并默认设置和保存的设置
                default_settings.update(saved_settings)
        except Exception as e:
            print(f"加载设置文件失败: {e}")
    
    return default_settings

def save_settings(settings: Dict[str, Any]):
    """保存设置"""
    settings_file = get_settings_file_path()
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存设置失败: {e}")

@router.get("/")
async def get_settings():
    """获取系统设置"""
    try:
        settings = load_settings()
        # 直接返回完整的设置，不隐藏API key
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载设置失败: {e}")

@router.post("/")
async def update_settings(request: SettingsRequest):
    """更新系统设置"""
    try:
        settings = load_settings()
        
        # 更新提供的设置
        if request.dashscope_api_key is not None:
            settings["dashscope_api_key"] = request.dashscope_api_key
            # 同时设置环境变量
            os.environ["DASHSCOPE_API_KEY"] = request.dashscope_api_key
        
        if request.model_name is not None:
            settings["model_name"] = request.model_name
        
        if request.chunk_size is not None:
            settings["chunk_size"] = request.chunk_size
        
        if request.min_score_threshold is not None:
            settings["min_score_threshold"] = request.min_score_threshold
        
        if request.max_clips_per_collection is not None:
            settings["max_clips_per_collection"] = request.max_clips_per_collection
        
        # 保存设置
        save_settings(settings)
        
        return {"message": "设置更新成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新设置失败: {e}")

@router.post("/test-api-key")
async def test_api_key(request: ApiKeyTestRequest) -> ApiKeyTestResponse:
    """测试API密钥"""
    try:
        # 临时设置API密钥
        original_key = os.getenv("DASHSCOPE_API_KEY", "")
        os.environ["DASHSCOPE_API_KEY"] = request.api_key
        
        # 尝试导入并测试LLM客户端
        try:
            import sys
            from pathlib import Path
            
            # 添加项目根目录到Python路径
            project_root = Path(__file__).parent.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            from shared.utils.llm_client import LLMClient
            
            llm_client = LLMClient()
            # 发送一个简单的测试请求
            test_prompt = "请回复'测试成功'"
            response = llm_client.call(test_prompt)
            
            if "测试成功" in response or "success" in response.lower():
                return ApiKeyTestResponse(success=True)
            else:
                return ApiKeyTestResponse(success=False, error="API响应异常")
                
        except Exception as e:
            return ApiKeyTestResponse(success=False, error=str(e))
        finally:
            # 恢复原始API密钥
            if original_key:
                os.environ["DASHSCOPE_API_KEY"] = original_key
            else:
                os.environ.pop("DASHSCOPE_API_KEY", None)
                
    except Exception as e:
        return ApiKeyTestResponse(success=False, error=str(e)) 