"""
设置管理API端点
为Desktop客户端提供设置管理功能
"""

import os
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

from backend.core.desktop_config import get_desktop_config, is_desktop_mode, DesktopConfig, save_desktop_config
from backend.services.config_sync_service import config_sync_service
from pathlib import Path

router = APIRouter(prefix="/settings", tags=["settings"])


class BasicSettings(BaseModel):
    """基础设置"""
    app_name: str = Field(default="AutoClip Desktop", description="应用名称")
    app_version: str = Field(default="1.0.0", description="应用版本")
    debug_mode: bool = Field(default=False, description="调试模式")
    auto_start: bool = Field(default=True, description="自动启动")


class ServiceSettings(BaseModel):
    """服务设置"""
    host: str = Field(default="127.0.0.1", description="服务主机")
    port: int = Field(default=8000, description="服务端口")
    max_memory_usage: int = Field(default=2048, description="最大内存使用(MB)")
    
    @validator('port')
    def validate_port(cls, v):
        if not 1024 <= v <= 65535:
            raise ValueError('端口号必须在1024-65535之间')
        return v
    
    @validator('max_memory_usage')
    def validate_memory(cls, v):
        if not 512 <= v <= 8192:
            raise ValueError('内存使用限制必须在512-8192MB之间')
        return v


class ApiKeys(BaseModel):
    """API密钥设置"""
    dashscope: str = Field(default="", description="通义千问API密钥")
    openai: str = Field(default="", description="OpenAI API密钥")
    gemini: str = Field(default="", description="Gemini API密钥")
    siliconflow: str = Field(default="", description="SiliconFlow API密钥（已不再作为独立提供商，仅兼容旧配置）")
    deepseek: str = Field(default="", description="DeepSeek 官方 API密钥")
    kimi: str = Field(default="", description="Kimi / 月之暗面 API密钥")
    glm: str = Field(default="", description="智谱 GLM API密钥")
    grok: str = Field(default="", description="xAI Grok API密钥")
    seed: str = Field(default="", description="火山方舟 Seed / 豆包 API密钥")
    jimeng_access: str = Field(default="", description="即梦AI访问密钥")
    jimeng_secret: str = Field(default="", description="即梦AI秘密密钥")


class ApiSettings(BaseModel):
    """API设置"""
    api_keys: ApiKeys = Field(default_factory=ApiKeys, description="API密钥")
    api_provider: str = Field(default="dashscope", description="当前 LLM 提供商（dashscope / openai / gemini / deepseek / seed / kimi / glm / grok，或本地预设 ollama / lmstudio）")
    api_base_url: str = Field(default="", description="OpenAI 兼容接口地址；provider=openai 时空为官方地址，本地预设为空时用预设默认地址")
    api_model: str = Field(default="qwen-plus", description="默认模型")
    api_max_tokens: int = Field(default=4096, description="最大Token数")
    api_timeout: int = Field(default=30, description="API超时时间(秒)")
    
    @validator('api_timeout')
    def validate_timeout(cls, v):
        if not 5 <= v <= 300:
            raise ValueError('API超时时间必须在5-300秒之间')
        return v


class ProcessingSettings(BaseModel):
    """处理设置"""
    processing_chunk_size: int = Field(default=5000, description="处理块大小")
    processing_min_score: float = Field(default=0.7, description="最小评分阈值")
    processing_max_clips: int = Field(default=5, description="合集最大切片数")
    processing_max_retries: int = Field(default=3, description="最大重试次数")
    
    @validator('processing_chunk_size')
    def validate_chunk_size(cls, v):
        if not 1000 <= v <= 10000:
            raise ValueError('处理块大小必须在1000-10000之间')
        return v
    
    @validator('processing_min_score')
    def validate_min_score(cls, v):
        if not 0.1 <= v <= 1.0:
            raise ValueError('最小评分阈值必须在0.1-1.0之间')
        return v


class LogSettings(BaseModel):
    """日志设置"""
    log_level: str = Field(default="INFO", description="日志级别")
    log_retention_days: int = Field(default=7, description="日志保留天数")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        if v not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            raise ValueError('日志级别必须是DEBUG、INFO、WARNING或ERROR')
        return v
    
    @validator('log_retention_days')
    def validate_retention_days(cls, v):
        if not 1 <= v <= 30:
            raise ValueError('日志保留天数必须在1-30天之间')
        return v


class PathSettings(BaseModel):
    """路径设置"""
    data_directory: str = Field(description="数据目录")
    cache_directory: str = Field(description="缓存目录")
    temp_directory: str = Field(description="临时目录")


class UpdateDataDirRequest(BaseModel):
    """更新数据目录请求"""
    new_data_directory: str = Field(description="新的数据目录路径")
    migrate: bool = Field(default=True, description="是否迁移旧目录数据")


class DesktopSettings(BaseModel):
    """完整的Desktop设置"""
    basic: BasicSettings = Field(default_factory=BasicSettings)
    service: ServiceSettings = Field(default_factory=ServiceSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    logs: LogSettings = Field(default_factory=LogSettings)
    paths: Optional[PathSettings] = Field(default=None, description="路径设置")


def check_desktop_mode(relaxed: bool = False):
    """检查是否在Desktop模式
    relaxed=True 时放宽限制，允许内测安装包/开发环境调用（返回告警但不阻断）。

    只有真正依赖桌面壳 / 本机文件系统的端点才需要它（数据目录迁移、备份恢复、导入导出、客户端配置同步）。
    读写 settings.json、测试连接、查询当前提供商这类配置端点在 Docker / 本地脚本模式下同样有效：
    settings.json 落在 `get_data_directory()`，API 进程与 Celery worker 都按 mtime 热重载。
    以前这些端点也被拦成 400，Docker 用户只能改 .env（issue #100）。
    """
    if not is_desktop_mode():
        if relaxed:
            return False
        raise HTTPException(status_code=400, detail="此端点仅在Desktop模式下可用")


class PrivacySettings(BaseModel):
    crash_reports: bool = True


@router.get("/privacy")
async def get_privacy():
    """崩溃报告等隐私开关（桌面数据目录 privacy.json）。"""
    from backend.core.sentry_setup import crash_reports_enabled
    return PrivacySettings(crash_reports=crash_reports_enabled())


@router.put("/privacy")
async def put_privacy(body: PrivacySettings):
    from backend.core.sentry_setup import write_privacy, crash_reports_enabled, init_sentry
    try:
        write_privacy(crash_reports=body.crash_reports)
        if body.crash_reports:
            init_sentry(os.getenv("AUTOCLIP_MODE", "web"))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PrivacySettings(crash_reports=crash_reports_enabled())


@router.get("/desktop-mode")
async def check_desktop_mode_endpoint():
    """检查是否在桌面模式 - 供前端调用"""
    return {
        "is_desktop_mode": is_desktop_mode(),
        "environment": {
            "AUTOCLIP_DESKTOP_MODE": os.getenv("AUTOCLIP_DESKTOP_MODE"),
            "AUTOCLIP_MODE": os.getenv("AUTOCLIP_MODE"),
            "TAURI_PLATFORM": os.getenv("TAURI_PLATFORM"),
        }
    }


def _effective_llm_settings() -> Dict[str, Any]:
    """LLM 管理器实际生效的 provider / model / base_url（settings.json 优先，其次环境变量）。
    取不到时返回空 dict，调用方回退到默认值。"""
    try:
        from backend.core.llm_manager import get_llm_manager
        return get_llm_manager().get_current_provider_info()
    except Exception as e:  # noqa: BLE001
        logger.debug(f"读取 LLM 管理器状态失败，设置页使用默认值: {e}")
        return {}


MASKED_SECRET = "********"


def _mask_settings(value, secret=False):
    if isinstance(value, dict):
        return {key: _mask_settings(item, secret or key == "api_keys" or key in {"api_key", "access_key", "secret_key", "aliyun_access_key", "aliyun_access_secret", "custom_api_key"}) for key, item in value.items()}
    if secret and isinstance(value, str) and value:
        return MASKED_SECRET
    return value


def _preserve_settings(value, saved):
    if isinstance(value, dict):
        return {key: _preserve_settings(item, saved.get(key) if isinstance(saved, dict) else None) for key, item in value.items()}
    return saved if value == MASKED_SECRET else value


@router.get("/", response_model=DesktopSettings)
async def get_settings():
    settings = await load_settings()
    return DesktopSettings(**_mask_settings(settings.model_dump()))


async def load_settings():
    """获取所有设置"""
    try:
        config = get_desktop_config()
        
        # 尝试从保存的设置文件中读取
        settings_file = config.paths.data_dir / "settings.json"
        logger.debug(f"设置文件路径: {settings_file} (存在: {settings_file.exists()})")
        
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                
                # 验证并返回保存的设置
                settings = DesktopSettings(**saved_settings)
                return settings
            except Exception as e:
                # 如果读取失败，回退到默认配置
                logger.warning(f"读取设置文件失败，回退到默认配置: {e}")

        # 还没保存过 settings.json：Docker / 脚本模式的提供商、模型、base_url 来自环境变量
        # （LLM_PROVIDER / API_MODEL_NAME / OPENAI_BASE_URL），设置页首屏应如实反映，而不是固定显示通义千问
        effective = _effective_llm_settings()
        
        # 构建路径设置
        paths = PathSettings(
            data_directory=str(config.paths.data_dir),
            cache_directory=str(config.paths.cache_dir),
            temp_directory=str(config.paths.temp_dir)
        )
        
        # 构建完整设置
        settings = DesktopSettings(
            basic=BasicSettings(
                app_name=config.app_name,
                app_version=config.app_version,
                debug_mode=config.debug_mode,
                auto_start=True  # 默认值
            ),
            service=ServiceSettings(
                host=config.host,
                port=config.port,
                max_memory_usage=config.max_memory_usage
            ),
            api=ApiSettings(
                api_keys=ApiKeys(
                    dashscope=config.dashscope_api_key,
                    openai=config.openai_api_key,
                    gemini=config.gemini_api_key,
                    siliconflow=config.siliconflow_api_key,
                    deepseek="",
                    kimi="",
                    glm="",
                    grok="",
                    seed="",
                    jimeng_access="",  # 默认值
                    jimeng_secret=""   # 默认值
                ),
                api_provider=effective.get("provider") or "dashscope",
                api_base_url=effective.get("base_url") or "",
                api_model=effective.get("model") or config.default_model,
                api_max_tokens=config.max_tokens,
                api_timeout=config.timeout
            ),
            processing=ProcessingSettings(
                processing_chunk_size=config.chunk_size,
                processing_min_score=config.min_score_threshold,
                processing_max_clips=config.max_clips_per_collection,
                processing_max_retries=config.max_retries
            ),
            logs=LogSettings(
                log_level=config.log_level,
                log_retention_days=config.log_retention_days
            ),
            paths=paths
        )
        
        return settings
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取设置失败: {str(e)}")


@router.post("/paths/data-directory")
async def update_data_directory(
    new_path: str,
    migrate_data: bool = True
):
    """更新数据目录"""
    check_desktop_mode()
    
    try:
        from backend.core.desktop_config import set_data_dir
        
        result = set_data_dir(new_path, migrate_data)
        
        if result["success"]:
            return {
                "message": result["message"],
                "new_path": result["new_path"],
                "migrated_files": result.get("migrated_files", []),
                "failed_files": result.get("failed_files", [])
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新数据目录失败: {str(e)}")

@router.get("/paths/data-directory")
async def get_data_directory_info():
    """获取数据目录信息"""
    check_desktop_mode()
    
    try:
        from backend.core.desktop_config import get_data_dir_info
        
        return get_data_dir_info()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据目录信息失败: {str(e)}")

@router.delete("/")
async def clear_settings(
    config: DesktopConfig = Depends(get_desktop_config)
):
    """清除所有设置"""
    try:
        # 重置配置为默认值
        config.dashscope_api_key = ""
        config.openai_api_key = ""
        config.gemini_api_key = ""
        config.siliconflow_api_key = ""
        config.jimeng_access_key = ""
        config.jimeng_secret_key = ""
        
        # 保存配置
        save_desktop_config(config)
        
        return {"message": "设置已清除", "success": True}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除设置失败: {str(e)}")

class TestApiRequest(BaseModel):
    provider: str
    api_key: str = ""
    base_url: Optional[str] = None   # 仅 openai：兼容接口地址
    model: Optional[str] = None      # 用哪个模型发测试请求（兼容接口必须是服务端真有的模型名）

@router.post("/test-api")
async def test_api_connection(request: TestApiRequest):
    """测试API连接"""
    try:
        from backend.core.llm_providers import normalize_base_url, OPENAI_OFFICIAL_BASE_URL
        from backend.core.local_presets import resolve_provider
        from backend.core.cloud_presets import resolve_cloud_preset
        # ollama / lmstudio 预设 → openai + 默认地址
        requested_provider = request.provider
        if request.api_key == MASKED_SECRET:
            from backend.core.model_catalog import _official_base_url
            saved = await load_settings()
            saved_base = saved.api.api_base_url if saved.api.api_provider == requested_provider else ""
            trusted = normalize_base_url(_official_base_url(requested_provider, saved_base))
            requested = normalize_base_url(_official_base_url(requested_provider, request.base_url or ""))
            if requested_provider != "gemini" and requested != trusted:
                raise HTTPException(status_code=400, detail="Supply a separate key for a different endpoint")
            request.api_key = _saved_provider_api_key(saved, requested_provider)
        cloud = resolve_cloud_preset(request.provider, request.base_url)
        if cloud:
            resolved_provider, resolved_base_url, _preset = cloud
        else:
            resolved_provider, resolved_base_url, _preset = resolve_provider(request.provider, request.base_url)
        request.provider = resolved_provider
        custom_base_url = normalize_base_url(resolved_base_url) if request.provider == "openai" else ""
        if custom_base_url == OPENAI_OFFICIAL_BASE_URL:
            custom_base_url = ""

        # 官方服务才做 key 格式校验；自建 OpenAI 兼容服务（Ollama / vLLM 等）常常不需要 key
        if not custom_base_url:
            if not request.api_key or len(request.api_key.strip()) < 10:
                return {
                    "success": False,
                    "error": "API Key为空或过短，请检查输入",
                    "provider": request.provider
                }
            if request.provider in ["dashscope", "openai"] and not request.api_key.startswith("sk-"):
                return {
                    "success": False,
                    "error": f"{request.provider} API Key格式可能不正确，通常以'sk-'开头",
                    "provider": request.provider
                }

        model_kwargs = {"model_name": request.model} if request.model else {}
        
        # 根据提供商测试API连接
        if request.provider == "dashscope":
            from backend.core.llm_providers import DashScopeProvider
            # 国际站地址走兼容模式（#45）；空 = 中国站 native SDK
            dashscope_base_url = normalize_base_url(request.base_url) or None
            provider_instance = DashScopeProvider(api_key=request.api_key, base_url=dashscope_base_url, **model_kwargs)
        elif request.provider == "openai":
            from backend.core.llm_providers import OpenAIProvider
            provider_instance = OpenAIProvider(api_key=request.api_key, base_url=custom_base_url or None, **model_kwargs)
        elif request.provider == "gemini":
            from backend.core.llm_providers import GeminiProvider
            provider_instance = GeminiProvider(api_key=request.api_key, **model_kwargs)
        elif request.provider == "siliconflow":
            from backend.core.llm_providers import SiliconFlowProvider
            provider_instance = SiliconFlowProvider(api_key=request.api_key, **model_kwargs)
        else:
            raise HTTPException(status_code=400, detail="不支持的API提供商")
        
        # 测试连接
        test_result = provider_instance.test_connection()
        
        if test_result:
            return {
                "success": True,
                "message": "API连接测试成功",
                "provider": requested_provider
            }
        else:
            # 提供更详细的错误信息
            error_msg = f"API连接测试失败"
            if request.provider == "dashscope":
                error_msg += "。请检查API Key是否正确，DashScope API Key通常以'sk-'开头"
            elif request.provider == "openai" and custom_base_url:
                error_msg += f"。请检查接口地址 {custom_base_url} 是否可达、模型名是否存在，以及该服务是否需要 API Key"
            elif request.provider == "openai":
                error_msg += "。请检查API Key是否正确，OpenAI API Key通常以'sk-'开头"
            elif request.provider == "gemini":
                error_msg += "。请检查API Key是否正确"
            elif request.provider == "siliconflow":
                error_msg += "。请检查API Key是否正确"
            
            return {
                "success": False,
                "error": error_msg,
                "provider": request.provider
            }
            
    except Exception as e:
        logger.error(f"API连接测试异常: {str(e)}")
        return {
            "success": False,
            "error": f"API连接测试失败: {str(e)}",
            "provider": request.provider
        }

@router.put("/", response_model=Dict[str, Any])
async def update_settings(settings: DesktopSettings):
    saved = await load_settings()
    settings = DesktopSettings(**_preserve_settings(settings.model_dump(), saved.model_dump()))
    """更新设置"""
    try:
        config = get_desktop_config()
        
        # 更新配置
        config.debug_mode = settings.basic.debug_mode
        config.host = settings.service.host
        config.port = settings.service.port
        config.max_memory_usage = settings.service.max_memory_usage
        
        # 更新API设置
        config.dashscope_api_key = settings.api.api_keys.dashscope
        config.openai_api_key = settings.api.api_keys.openai
        config.gemini_api_key = settings.api.api_keys.gemini
        config.siliconflow_api_key = settings.api.api_keys.siliconflow
        config.default_model = settings.api.api_model
        config.max_tokens = settings.api.api_max_tokens
        config.timeout = settings.api.api_timeout
        
        # 更新处理设置
        config.chunk_size = settings.processing.processing_chunk_size
        config.min_score_threshold = settings.processing.processing_min_score
        config.max_clips_per_collection = settings.processing.processing_max_clips
        config.max_retries = settings.processing.processing_max_retries
        
        # 更新日志设置
        config.log_level = settings.logs.log_level
        
        # 保存设置到文件
        settings_file = config.paths.data_dir / "settings.json"
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings.dict(), f, indent=2, ensure_ascii=False)

        # 让本进程的 LLM 管理器立刻切到新 provider / base_url / 模型（worker 进程靠 mtime 自动重载）
        try:
            from backend.core.llm_manager import get_llm_manager
            get_llm_manager()._reload_if_settings_changed()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"刷新 LLM 管理器失败（下次调用时会自动重载）: {e}")
        
        # 重要：保存主配置文件，确保API key等关键配置被持久化
        from backend.core.desktop_config import save_desktop_config
        if not save_desktop_config(config):
            raise HTTPException(status_code=500, detail="保存主配置文件失败")
        
        return {"message": "设置更新成功", "settings_file": str(settings_file)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新设置失败: {str(e)}")


@router.post("/reset")
async def reset_settings():
    """重置设置为默认值"""
    try:
        config = get_desktop_config()
        
        # 删除设置文件
        settings_file = config.paths.data_dir / "settings.json"
        if settings_file.exists():
            settings_file.unlink()
        
        # 重新加载默认配置
        config._settings = None
        config._paths = None
        
        return {"message": "设置已重置为默认值"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置设置失败: {str(e)}")


@router.post("/paths/data-directory", response_model=Dict[str, Any])
async def update_data_directory(payload: UpdateDataDirRequest):
    """更新数据目录（可选迁移数据）。供首次运行向导或设置页调用。"""
    is_desktop = check_desktop_mode(relaxed=True)
    try:
        config = get_desktop_config()
        result = config.set_data_dir(Path(payload.new_data_directory), migrate_from_old=payload.migrate)

        # 同步返回新的路径配置
        paths = {
            "data_directory": str(config.paths.data_dir),
            "cache_directory": str(config.paths.cache_dir),
            "temp_directory": str(config.paths.temp_dir),
            "database_url": config.paths.database_url,
        }

        resp = {"message": "数据目录更新成功", "result": result, "paths": paths}
        if not is_desktop:
            resp["warning"] = "当前非Desktop模式，但已更新路径配置"
        return resp
    except Exception as e:
        # 返回更详细的错误，帮助定位权限/路径/占用等问题
        return {
            "message": "更新数据目录失败，但已跳过（内测模式）",
            "error": str(e),
            "hint": "请确认目标目录可写且未被系统限制，必要时选择用户主目录下的路径",
        }


@router.post("/export")
async def export_settings():
    """导出设置"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        settings = await get_settings()
        
        # 创建导出文件
        export_file = config.paths.data_dir / "autoclip-settings-export.json"
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(settings.dict(), f, indent=2, ensure_ascii=False)
        
        return {
            "message": "设置导出成功",
            "export_file": str(export_file),
            "download_url": f"/api/v1/settings/download/{export_file.name}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出设置失败: {str(e)}")


@router.post("/import")
async def import_settings(file: UploadFile = File(...)):
    """导入设置"""
    check_desktop_mode()
    
    try:
        # 读取上传的文件
        content = await file.read()
        settings_data = json.loads(content.decode('utf-8'))
        
        # 验证设置格式
        settings = DesktopSettings(**settings_data)
        
        # 更新设置
        result = await update_settings(settings)
        
        return {
            "message": "设置导入成功",
            "imported_settings": settings.dict()
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="设置文件格式错误")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入设置失败: {str(e)}")


# 删除重复的test_api_connection函数


@router.get("/validation")
async def validate_settings():
    """验证当前设置"""
    try:
        config = get_desktop_config()
        validation_result = config.validate_config()
        
        return {
            "valid": validation_result["valid"],
            "errors": validation_result.get("errors", []),
            "warnings": validation_result.get("warnings", []),
            "recommendations": []
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置验证失败: {str(e)}")


@router.get("/backup")
async def backup_settings():
    """备份设置"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        backup_dir = config.paths.data_dir / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        # 创建备份
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"settings_backup_{timestamp}.json"
        
        settings = await get_settings()
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(settings.dict(), f, indent=2, ensure_ascii=False)
        
        return {
            "message": "设置备份成功",
            "backup_file": str(backup_file),
            "backup_time": timestamp
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"备份设置失败: {str(e)}")


@router.get("/backups")
async def list_backups():
    """列出所有备份"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        backup_dir = config.paths.data_dir / "backups"
        
        if not backup_dir.exists():
            return {"backups": []}
        
        backups = []
        for backup_file in backup_dir.glob("settings_backup_*.json"):
            stat = backup_file.stat()
            backups.append({
                "filename": backup_file.name,
                "path": str(backup_file),
                "size": stat.st_size,
                "created_time": stat.st_ctime,
                "modified_time": stat.st_mtime
            })
        
        # 按创建时间排序
        backups.sort(key=lambda x: x["created_time"], reverse=True)
        
        return {"backups": backups}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取备份列表失败: {str(e)}")


def _saved_provider_api_key(settings: DesktopSettings, provider: str) -> str:
    keys = settings.api.api_keys
    return {
        "dashscope": keys.dashscope,
        "openai": keys.openai,
        "gemini": keys.gemini,
        "siliconflow": keys.siliconflow,
        "deepseek": keys.deepseek,
        "kimi": keys.kimi,
        "glm": keys.glm,
        "grok": keys.grok,
        "seed": keys.seed,
    }.get((provider or "").strip().lower(), "") or ""


@router.get("/available-models")
async def get_available_models(
    provider: str = "",
    base_url: str = "",
    api_key: str = "",
    refresh: bool = False,
):
    """
    云端提供商的模型下拉。

    没密钥时返回内置常用名单；有密钥（请求参数或已保存的 settings）时
    打服务商 `/models`，把账号此刻能用的型号合并进来。`refresh=1` 跳过缓存。
    """
    try:
        from backend.core.model_catalog import list_available_models, _official_base_url
        from backend.core.llm_providers import normalize_base_url

        key = (api_key or "").strip()
        if key == MASKED_SECRET:
            key = ""
        if not key and provider:
            try:
                settings = await load_settings()
                selected_provider = provider.strip().lower()
                saved_base = (
                    settings.api.api_base_url
                    if settings.api.api_provider.strip().lower() == selected_provider
                    else ""
                )
                trusted_base = _official_base_url(selected_provider, saved_base)
                requested_base = _official_base_url(selected_provider, base_url)
                # A saved secret is usable only at its configured endpoint. Custom
                # discovery endpoints must supply their own credential explicitly.
                if selected_provider == "gemini" or normalize_base_url(requested_base) == normalize_base_url(trusted_base):
                    key = _saved_provider_api_key(settings, provider).strip()
            except Exception:  # noqa: BLE001
                key = ""
        result = await list_available_models(
            provider=provider,
            api_key=key,
            base_url=base_url,
            refresh=refresh,
        )
        # 旧调用方只认 {models: {provider: [{name, ...}]}}；新字段并排返回
        legacy = {
            name: [{"name": model, "display_name": model} for model in models]
            for name, models in result.catalog.items()
        }
        payload = result.as_dict()
        payload["models_by_provider"] = legacy
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")


@router.get("/local-presets")
async def get_local_presets():
    """本地模型预设（Ollama / LM Studio）：默认地址、默认模型、提示文案。"""
    from backend.core.local_presets import presets_as_dicts
    return {"presets": presets_as_dicts()}


@router.get("/compatible-models")
async def list_compatible_models(base_url: str = "", provider: str = "openai", api_key: str = ""):
    """
    列出一个 OpenAI 兼容服务（Ollama / LM Studio / vLLM…）实际提供的模型（GET {base_url}/models）。
    设置页选本地预设时用它填模型下拉，免得用户手敲 `qwen2.5:7b` 这种名字。
    """
    from backend.core.local_presets import resolve_provider
    from backend.core.llm_providers import normalize_base_url, is_local_url, OPENAI_COMPATIBLE_PLACEHOLDER_KEY
    _provider, resolved_base_url, _preset = resolve_provider(provider, base_url)
    url = normalize_base_url(resolved_base_url)
    if not url:
        raise HTTPException(status_code=400, detail="缺少 base_url")
    try:
        import httpx
        headers = {"Authorization": f"Bearer {api_key or OPENAI_COMPATIBLE_PLACEHOLDER_KEY}"}
        # 本地地址不走系统代理（否则 macOS 上开着 Clash 之类会 502）
        async with httpx.AsyncClient(timeout=5.0, trust_env=not is_local_url(url)) as client:
            resp = await client.get(f"{url}/models", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", data) if isinstance(data, dict) else data
        models = sorted({str(m.get("id") or m.get("name")) for m in items if isinstance(m, dict) and (m.get("id") or m.get("name"))})
        return {"reachable": True, "base_url": url, "models": models}
    except Exception as e:  # noqa: BLE001
        # 服务没起 / 地址不对：不算服务端错误，前端据此提示「服务未启动」
        return {"reachable": False, "base_url": url, "models": [], "error": str(e)[:200]}


@router.get("/current-provider")
async def get_current_provider():
    """获取当前提供商信息"""
    try:
        # 以 LLM 管理器的实际状态为准（它读的就是设置页保存的 settings.json），
        # 而不是固定返回 dashscope——那会让设置页每次打开都"跳回"通义千问。
        from backend.core.llm_manager import get_llm_manager
        info = get_llm_manager().get_current_provider_info()
        display_name = info.get("display_name") or info.get("provider") or "阿里通义千问"
        provider_info = {
            "provider": info.get("provider") or "dashscope",
            "model": info.get("model") or "qwen-plus",
            "available": bool(info.get("available")),
            "display_name": display_name,
            "description": f"{display_name} 模型服务",
        }
        if info.get("base_url"):
            provider_info["base_url"] = info["base_url"]
        
        return provider_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取当前提供商信息失败: {str(e)}")


@router.post("/restore/{backup_filename}")
async def restore_backup(backup_filename: str):
    """从备份恢复设置"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        backup_file = config.paths.data_dir / "backups" / backup_filename
        
        if not backup_file.exists():
            raise HTTPException(status_code=404, detail="备份文件不存在")
        
        # 读取备份文件
        with open(backup_file, 'r', encoding='utf-8') as f:
            settings_data = json.load(f)
        
        # 验证并恢复设置
        settings = DesktopSettings(**settings_data)
        result = await update_settings(settings)
        
        return {
            "message": "设置恢复成功",
            "restored_from": backup_filename,
            "restored_settings": settings.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复设置失败: {str(e)}")


@router.post("/sync-config")
async def sync_config():
    """手动同步客户端配置到后端"""
    check_desktop_mode()
    
    try:
        if config_sync_service.sync_from_client():
            return {
                "status": "success",
                "message": "配置同步成功"
            }
        else:
            return {
                "status": "error",
                "message": "配置同步失败"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"配置同步失败: {str(e)}"
        }


@router.get("/config-status")
async def get_config_status():
    """获取配置同步状态"""
    check_desktop_mode()
    
    try:
        client_time = config_sync_service.get_client_config_timestamp()
        backup_time = config_sync_service.get_backup_config_timestamp()
        sync_needed = config_sync_service.is_sync_needed()
        
        return {
            "client_config_exists": client_time is not None,
            "backup_config_exists": backup_time is not None,
            "client_config_time": client_time,
            "backup_config_time": backup_time,
            "sync_needed": sync_needed,
            "client_config_path": str(config_sync_service.client_config_path),
            "backup_config_path": str(config_sync_service.backup_config_path)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"获取配置状态失败: {str(e)}"
        }