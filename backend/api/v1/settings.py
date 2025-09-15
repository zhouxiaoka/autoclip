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
    # 多提供商支持
    llm_provider: Optional[str] = None
    dashscope_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    siliconflow_api_key: Optional[str] = None
    model_name: Optional[str] = None
    chunk_size: Optional[int] = None
    min_score_threshold: Optional[float] = None
    max_clips_per_collection: Optional[int] = None

class ApiKeyTestRequest(BaseModel):
    """API密钥测试请求"""
    provider: str
    api_key: str
    model_name: str

class ApiKeyTestResponse(BaseModel):
    """API密钥测试响应"""
    success: bool
    error: Optional[str] = None

def get_settings_file_path() -> Path:
    """获取设置文件路径"""
    from ...core.path_utils import get_settings_file_path as get_settings_path
    return get_settings_path()

def load_settings() -> Dict[str, Any]:
    """加载设置"""
    settings_file = get_settings_file_path()
    default_settings = {
        "llm_provider": "dashscope",
        "dashscope_api_key": "",
        "openai_api_key": "",
        "gemini_api_key": "",
        "siliconflow_api_key": "",
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
        
        # 更新多提供商设置
        if request.llm_provider is not None:
            settings["llm_provider"] = request.llm_provider
        
        if request.dashscope_api_key is not None:
            settings["dashscope_api_key"] = request.dashscope_api_key
            # 同时设置环境变量（保持兼容性）
            os.environ["DASHSCOPE_API_KEY"] = request.dashscope_api_key
        
        if request.openai_api_key is not None:
            settings["openai_api_key"] = request.openai_api_key
        
        if request.gemini_api_key is not None:
            settings["gemini_api_key"] = request.gemini_api_key
        
        if request.siliconflow_api_key is not None:
            settings["siliconflow_api_key"] = request.siliconflow_api_key
        
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
        
        # 更新LLM管理器
        try:
            from ...core.llm_manager import get_llm_manager
            llm_manager = get_llm_manager()
            llm_manager.update_settings(settings)
        except Exception as e:
            print(f"更新LLM管理器失败: {e}")
        
        return {"message": "设置更新成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新设置失败: {e}")

@router.post("/test-api-key")
async def test_api_key(request: ApiKeyTestRequest) -> ApiKeyTestResponse:
    """测试API密钥"""
    try:
        # 导入LLM管理器
        from ...core.llm_manager import get_llm_manager
        from ...core.llm_providers import ProviderType
        
        # 验证提供商类型
        try:
            provider_type = ProviderType(request.provider)
        except ValueError:
            return ApiKeyTestResponse(success=False, error=f"不支持的提供商类型: {request.provider}")
        
        # 测试连接
        llm_manager = get_llm_manager()
        success = llm_manager.test_provider_connection(provider_type, request.api_key, request.model_name)
        
        if success:
            return ApiKeyTestResponse(success=True)
        else:
            return ApiKeyTestResponse(success=False, error="API连接测试失败")
                
    except Exception as e:
        return ApiKeyTestResponse(success=False, error=str(e))

@router.get("/available-models")
async def get_available_models():
    """获取所有可用模型"""
    try:
        from ...core.llm_manager import get_llm_manager
        llm_manager = get_llm_manager()
        return llm_manager.get_all_available_models()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取可用模型失败: {e}")

@router.get("/current-provider")
async def get_current_provider():
    """获取当前提供商信息"""
    try:
        from ...core.llm_manager import get_llm_manager
        llm_manager = get_llm_manager()
        return llm_manager.get_current_provider_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取当前提供商信息失败: {e}") 