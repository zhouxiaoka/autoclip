"""
LLM管理器 - 统一管理多个模型提供商
"""
import json
import logging
import os
from typing import Dict, Any, Optional, List
from pathlib import Path

from .llm_providers import (
    LLMProvider, LLMProviderFactory, ProviderType, 
    ModelInfo, LLMResponse
)
from ..services.config_sync_service import config_sync_service

logger = logging.getLogger(__name__)

class LLMManager:
    """LLM管理器"""
    
    def __init__(self, settings_file: Optional[Path] = None):
        # 在初始化前先同步配置
        self._sync_config_if_needed()
        
        self.settings_file = settings_file or self._get_default_settings_file()
        self.current_provider: Optional[LLMProvider] = None
        self._settings_mtime: Optional[float] = None
        self.settings = self._load_settings()
        self._initialize_provider()

    def _current_settings_mtime(self) -> Optional[float]:
        try:
            return self.settings_file.stat().st_mtime
        except OSError:
            return None

    def _reload_if_settings_changed(self) -> None:
        """设置页保存后 settings.json 会变；API 进程与 Celery worker 都要在下一次调用时拿到新配置，
        而不是等重启。"""
        mtime = self._current_settings_mtime()
        if mtime != self._settings_mtime:
            logger.info("检测到 settings.json 变化，重新加载 LLM 配置")
            self.settings = self._load_settings()
            self._initialize_provider()
    
    def _get_default_settings_file(self) -> Path:
        """获取默认设置文件路径"""
        # 优先使用桌面模式应用目录（与前端保存一致）
        app_dir = os.getenv("AUTOCLIP_APP_DIR")
        if app_dir:
            return Path(app_dir) / "settings.json"

        # 与设置 API 写入的位置保持同一来源（path_utils.get_data_directory），
        # 否则设置页保存到 A、这里读 B，切换 provider 永远不生效
        try:
            from .path_utils import get_data_directory
            return get_data_directory() / "settings.json"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"无法通过 path_utils 定位 settings.json，回退到旧逻辑: {e}")
        
        # 优先使用默认的用户目录（macOS）- 客户端配置位置
        default_app_dir = Path.home() / "Library" / "Application Support" / "AutoClip"
        default_settings = default_app_dir / "settings.json"
        if default_settings.exists():
            return default_settings
            
        # 最后检查项目data目录下的settings.json（开发环境）
        project_data_dir = Path(__file__).parent.parent.parent / "data"
        project_settings = project_data_dir / "settings.json"
        if project_settings.exists():
            return project_settings
            
        # 如果都不存在，返回默认路径
        return default_settings
    
    def _sync_config_if_needed(self):
        """检查并同步配置"""
        try:
            if config_sync_service.is_sync_needed():
                logger.info("检测到客户端配置更新，开始同步...")
                if config_sync_service.sync_from_client():
                    logger.info("配置同步完成")
                else:
                    logger.warning("配置同步失败")
        except Exception as e:
            logger.error(f"配置同步检查失败: {e}")
    
    def _load_settings(self) -> Dict[str, Any]:
        """加载设置"""
        default_settings = {
            "llm_provider": "dashscope",
            "dashscope_api_key": "",
            "openai_api_key": "",
            # OpenAI 兼容接口地址；空 = 官方。环境变量 OPENAI_BASE_URL 作为兜底
            "openai_base_url": os.getenv("OPENAI_BASE_URL", ""),
            "gemini_api_key": "",
            "siliconflow_api_key": "",
            "model_name": "qwen-plus",
            "chunk_size": 5000,
            "min_score_threshold": 0.7,
            "max_clips_per_collection": 5
        }
        
        self._settings_mtime = self._current_settings_mtime()
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    
                    # 处理新的配置格式（客户端配置）
                    if "api" in saved_settings and "api_keys" in saved_settings["api"]:
                        api = saved_settings["api"]
                        api_keys = api["api_keys"]
                        default_settings.update({
                            "dashscope_api_key": api_keys.get("dashscope", ""),
                            "openai_api_key": api_keys.get("openai", ""),
                            "gemini_api_key": api_keys.get("gemini", ""),
                            "siliconflow_api_key": api_keys.get("siliconflow", ""),
                            "model_name": api.get("api_model", "qwen-plus")
                        })
                        # 设置页保存的提供商；旧版 settings.json 没有这个字段，保持 dashscope
                        if api.get("api_provider"):
                            default_settings["llm_provider"] = api["api_provider"]
                        if api.get("api_base_url"):
                            default_settings["openai_base_url"] = api["api_base_url"]
                    else:
                        # 处理旧的配置格式（直接平铺）
                        default_settings.update(saved_settings)
                        
            except Exception as e:
                logger.warning(f"加载设置文件失败: {e}")
        
        self._apply_env_fallbacks(default_settings)
        self._apply_local_preset(default_settings)
        return default_settings

    def _apply_local_preset(self, settings: Dict[str, Any]) -> None:
        """`ollama` / `lmstudio` 这类本地预设 → openai + 默认 base_url（见 core/local_presets.py）"""
        from backend.core.local_presets import resolve_provider, LOCAL_PRESETS
        provider, base_url, preset = resolve_provider(settings.get("llm_provider"), settings.get("openai_base_url"))
        settings["llm_provider"] = provider
        settings["llm_provider_preset"] = preset
        if preset:
            settings["openai_base_url"] = base_url
            if not settings.get("model_name") or settings.get("model_name") == "qwen-plus":
                # 预设有默认模型时替换掉 dashscope 的默认值，避免拿 qwen-plus 去问 Ollama
                default_model = LOCAL_PRESETS[preset].default_model
                if default_model:
                    settings["model_name"] = default_model

    # Docker / 本地脚本模式没有设置页可用，只能靠环境变量（env.example 里也是这么写的），
    # 但此前这里只读 settings.json，导致 API_DASHSCOPE_API_KEY 等变量形同虚设。
    _ENV_KEY_FALLBACKS = {
        "dashscope_api_key": ("API_DASHSCOPE_API_KEY", "DASHSCOPE_API_KEY"),
        "openai_api_key": ("API_OPENAI_API_KEY", "OPENAI_API_KEY"),
        "gemini_api_key": ("API_GEMINI_API_KEY", "GEMINI_API_KEY"),
        "siliconflow_api_key": ("API_SILICONFLOW_API_KEY", "SILICONFLOW_API_KEY"),
    }

    def _apply_env_fallbacks(self, settings: Dict[str, Any]) -> None:
        for setting_name, env_names in self._ENV_KEY_FALLBACKS.items():
            if settings.get(setting_name):
                continue
            for env_name in env_names:
                value = os.getenv(env_name, "").strip()
                if value:
                    settings[setting_name] = value
                    break

        # 只有 settings.json 没有明确指定提供商/模型时，才让环境变量决定
        file_has_provider = self._file_specifies("api_provider", "llm_provider")
        env_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        if env_provider and not file_has_provider:
            settings["llm_provider"] = env_provider
        env_model = os.getenv("API_MODEL_NAME", "").strip() or os.getenv("LLM_MODEL", "").strip()
        if env_model and not self._file_specifies("api_model", "model_name"):
            settings["model_name"] = env_model

    def _file_specifies(self, *field_names: str) -> bool:
        """settings.json（客户端嵌套格式或旧平铺格式）里是否显式写了某个字段"""
        try:
            if not self.settings_file.exists():
                return False
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return False
        api = data.get("api", {}) if isinstance(data, dict) else {}
        return any(bool(api.get(name)) or bool(data.get(name)) for name in field_names)
    
    def _save_settings(self):
        """保存设置"""
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            raise
    
    def _initialize_provider(self):
        """初始化当前提供商"""
        try:
            provider_type = ProviderType(self.settings.get("llm_provider", "dashscope"))
            model_name = self.settings.get("model_name", "qwen-plus")
            
            # 获取对应提供商的API密钥（本地预设不需要 key，也不要把用户的 OpenAI key 发给本地服务）
            api_key = "" if self.settings.get("llm_provider_preset") else self._get_api_key_for_provider(provider_type)
            provider_kwargs = self._get_provider_kwargs(provider_type)

            # 自建 OpenAI 兼容服务（Ollama / vLLM 等）常常不需要 key，有 base_url 就够
            if api_key or (provider_type == ProviderType.OPENAI and provider_kwargs.get("base_url")):
                self.current_provider = LLMProviderFactory.create_provider(
                    provider_type, api_key or "", model_name, **provider_kwargs
                )
                logger.info(f"已初始化{provider_type.value}提供商，模型: {model_name}"
                            + (f", base_url: {provider_kwargs['base_url']}" if provider_kwargs.get("base_url") else ""))
            else:
                logger.warning(f"未找到{provider_type.value}的API密钥")
                self.current_provider = None
                
        except Exception as e:
            logger.error(f"初始化提供商失败: {e}")
            self.current_provider = None

    def _get_provider_kwargs(self, provider_type: ProviderType) -> Dict[str, Any]:
        """提供商构造参数（目前只有 OpenAI 兼容接口的 base_url）"""
        if provider_type == ProviderType.OPENAI:
            base_url = (self.settings.get("openai_base_url") or "").strip()
            if base_url:
                return {"base_url": base_url}
        return {}
    
    def _get_api_key_for_provider(self, provider_type: ProviderType) -> Optional[str]:
        """获取指定提供商的API密钥"""
        key_mapping = {
            ProviderType.DASHSCOPE: "dashscope_api_key",
            ProviderType.OPENAI: "openai_api_key",
            ProviderType.GEMINI: "gemini_api_key",
            ProviderType.SILICONFLOW: "siliconflow_api_key",
        }
        
        key_name = key_mapping.get(provider_type)
        if key_name:
            return self.settings.get(key_name, "")
        return None
    
    def update_settings(self, new_settings: Dict[str, Any]):
        """更新设置"""
        self.settings.update(new_settings)
        self._save_settings()
        self._initialize_provider()
    
    def set_provider(self, provider_type: ProviderType, api_key: str, model_name: str,
                     base_url: Optional[str] = None):
        """设置提供商"""
        try:
            # 更新设置
            provider_settings = {
                "llm_provider": provider_type.value,
                "model_name": model_name
            }
            
            # 更新对应提供商的API密钥
            key_mapping = {
                ProviderType.DASHSCOPE: "dashscope_api_key",
                ProviderType.OPENAI: "openai_api_key",
                ProviderType.GEMINI: "gemini_api_key",
                ProviderType.SILICONFLOW: "siliconflow_api_key",
            }
            
            key_name = key_mapping.get(provider_type)
            if key_name:
                provider_settings[key_name] = api_key
            if provider_type == ProviderType.OPENAI and base_url is not None:
                provider_settings["openai_base_url"] = base_url

            # update_settings 会保存并重新初始化 current_provider
            self.update_settings(provider_settings)
            
            logger.info(f"已切换到{provider_type.value}提供商，模型: {model_name}")
            
        except Exception as e:
            logger.error(f"设置提供商失败: {e}")
            raise
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> str:
        """调用LLM。设了 AUTOCLIP_LLM_CACHE_DIR 时按 sha1(prompt+input) 录制 / 回放，给回归集用。"""
        self._reload_if_settings_changed()
        cache_path = _llm_cache_path(prompt, input_data)
        if cache_path is not None and cache_path.exists():
            logger.info(f"LLM 缓存命中: {cache_path.name}")
            return cache_path.read_text(encoding="utf-8")
        if not self.current_provider:
            raise ValueError("未配置LLM提供商，请在设置页面配置API密钥")
        
        try:
            response = self.current_provider.call(prompt, input_data, **kwargs)
            content = response.content
            if cache_path is not None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(content, encoding="utf-8")
            return content
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise
    
    def call_with_retry(self, prompt: str, input_data: Any = None, max_retries: int = 3, **kwargs) -> str:
        """带重试机制的LLM调用"""
        for attempt in range(max_retries):
            try:
                return self.call(prompt, input_data, **kwargs)
            except ValueError:  # 如果是API Key或参数错误，不重试
                raise
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"LLM调用在{max_retries}次重试后彻底失败。")
                    raise
                logger.warning(f"第{attempt + 1}次调用失败，准备重试: {str(e)}")
                import time
                time.sleep(2 ** attempt)  # 指数退避
        return ""
    
    def test_provider_connection(self, provider_type: ProviderType, api_key: str, model_name: str,
                                 **provider_kwargs) -> bool:
        """测试提供商连接"""
        try:
            provider = LLMProviderFactory.create_provider(provider_type, api_key, model_name, **provider_kwargs)
            return provider.test_connection()
        except Exception as e:
            logger.error(f"测试{provider_type.value}连接失败: {e}")
            return False
    
    def get_current_provider_info(self) -> Dict[str, Any]:
        """获取当前提供商信息"""
        self._reload_if_settings_changed()
        provider_value = self.settings.get("llm_provider", "dashscope")
        try:
            provider_type = ProviderType(provider_value)
        except ValueError:
            return {"provider": provider_value, "model": None, "available": False}
        model_name = self.settings.get("model_name", "qwen-plus")
        preset = self.settings.get("llm_provider_preset")
        info = {
            # 设置页 / CLI 看到的是用户选的名字（ollama / lmstudio），底层仍是 openai 兼容
            "provider": preset or provider_type.value,
            "backend_provider": provider_type.value,
            "model": model_name,
            "available": self.current_provider is not None,
            "display_name": self._get_provider_display_name(provider_type),
        }
        if preset:
            from backend.core.local_presets import preset_display_name
            info["display_name"] = preset_display_name(preset) or info["display_name"]
        base_url = self._get_provider_kwargs(provider_type).get("base_url")
        if base_url:
            info["base_url"] = base_url
        return info
    
    def _get_provider_display_name(self, provider_type: ProviderType) -> str:
        """获取提供商显示名称"""
        display_names = {
            ProviderType.DASHSCOPE: "阿里通义千问",
            ProviderType.OPENAI: "OpenAI / 兼容接口",
            ProviderType.GEMINI: "Google Gemini",
            ProviderType.SILICONFLOW: "硅基流动"
        }
        return display_names.get(provider_type, provider_type.value)
    
    def get_all_available_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有可用模型"""
        all_models = LLMProviderFactory.get_all_available_models()
        result = {}
        
        for provider_type, models in all_models.items():
            provider_name = provider_type.value
            result[provider_name] = [
                {
                    "name": model.name,
                    "display_name": model.display_name,
                    "max_tokens": model.max_tokens,
                    "description": model.description
                }
                for model in models
            ]
        
        return result
    
    def parse_json_response(self, response: str) -> Any:
        """解析JSON响应（保持与原LLMClient的兼容性）"""
        if not self.current_provider:
            raise ValueError("未配置LLM提供商")
        
        # 这里可以复用原LLMClient的JSON解析逻辑
        # 为了保持兼容性，我们创建一个临时的LLMClient实例
        from ..utils.llm_client import LLMClient
        temp_client = LLMClient()
        return temp_client.parse_json_response(response)

def _llm_cache_path(prompt: str, input_data: Any) -> Optional[Path]:
    """AUTOCLIP_LLM_CACHE_DIR 设了才启用；CI / eval 回放用。"""
    root = os.getenv("AUTOCLIP_LLM_CACHE_DIR")
    if not root:
        return None
    import hashlib
    payload = json.dumps({"p": prompt, "i": input_data}, ensure_ascii=False, sort_keys=True, default=str)
    return Path(root) / f"{hashlib.sha1(payload.encode('utf-8')).hexdigest()}.txt"


# 全局LLM管理器实例
_llm_manager: Optional[LLMManager] = None

def get_llm_manager() -> LLMManager:
    """获取全局LLM管理器实例"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager

def initialize_llm_manager(settings_file: Optional[Path] = None) -> LLMManager:
    """初始化LLM管理器"""
    global _llm_manager
    _llm_manager = LLMManager(settings_file)
    return _llm_manager
