"""
LLM管理器 - 统一管理多个模型提供商
"""
import hashlib
import json
import os
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path

from .llm_providers import (
    LLMProvider, LLMProviderFactory, ProviderType, 
    ModelInfo, LLMResponse
)
from ..services.config_sync_service import config_sync_service
from .llm_telemetry import hostname_of_base_url, sanitize_exception_text, sanitize_model, log_safe_exception
from .failure_logging import failure_logger

logger = failure_logger(__name__)

# Serialize refresh/snapshot only; network calls remain concurrent.
_settings_lock = threading.RLock()


@dataclass(frozen=True, repr=False)
class _CallRoute:
    provider: Optional[LLMProvider]
    settings: Dict[str, Any]
    info: Dict[str, Any]
    # provider + config_source of the connection this route was resolved from
    # (failure_identity.connection_identity), frozen with the route; never re-read from settings.
    identity: Dict[str, Any] = field(default_factory=dict)


class LLMManager:
    """LLM管理器"""
    
    def __init__(self, settings_file: Optional[Path] = None):
        # 在初始化前先同步配置
        self._sync_config_if_needed()
        
        self.settings_file = settings_file or self._get_default_settings_file()
        self.current_provider: Optional[LLMProvider] = None
        self._settings_mtime: Optional[float] = None
        self._settings_hash = None
        self.settings = self._load_settings()
        self._initialize_provider()

    def _current_settings_mtime(self):
        from backend.services.ai_model_settings import path as ai_path
        def stamp(path):
            try:
                return path.stat().st_mtime_ns
            except OSError:
                return None
        return (stamp(self.settings_file), stamp(ai_path()))

    def _current_settings_hash(self):
        from backend.services.ai_model_settings import path as ai_path
        def digest(path):
            try:
                return hashlib.sha256(path.read_bytes()).digest()
            except OSError:
                return None
        return (digest(self.settings_file), digest(ai_path()))

    def _reload_if_settings_changed(self) -> None:
        """设置页保存后 settings.json 会变；API 进程与 Celery worker 都要在下一次调用时拿到新配置，
        而不是等重启。"""
        with _settings_lock:
            mtime = self._current_settings_mtime()
            content_hash = self._current_settings_hash()
            if mtime != self._settings_mtime or content_hash != self._settings_hash:
                logger.info("检测到 settings.json 变化，重新加载 LLM 配置")
                self.current_provider = None
                self.settings = self._load_settings()
                self._initialize_provider()

    def _snapshot_call_route(self) -> _CallRoute:
        """Refresh before candidate selection, then pin this run's connection."""
        with _settings_lock:
            self._reload_if_settings_changed()
            try:
                info = self.get_current_provider_info() or {}
            except Exception:  # identity is optional; a configured provider can still run
                info = {}
            settings = self.settings if isinstance(getattr(self, "settings", None), dict) else {}
            identity = dict(getattr(self, "_route_identity", None) or {})
            return _CallRoute(getattr(self, "current_provider", None), dict(settings), dict(info), identity)
    
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
            logger.warning(f"无法通过 path_utils 定位 settings.json，回退到旧逻辑: {sanitize_exception_text(e)}")
        
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
            logger.error(f"配置同步检查失败: {sanitize_exception_text(e)}")
    
    def _load_settings(self) -> Dict[str, Any]:
        """加载设置"""
        default_settings = {
            "llm_provider": "dashscope",
            "dashscope_api_key": "",
            "openai_api_key": "",
            # OpenAI 兼容接口地址；空 = 官方。环境变量 OPENAI_BASE_URL 作为兜底
            "openai_base_url": os.getenv("OPENAI_BASE_URL", ""),
            # 通义千问国际站（dashscope-intl）；空 = 中国站。Docker 用 DASHSCOPE_BASE_URL
            "dashscope_base_url": os.getenv("DASHSCOPE_BASE_URL", ""),
            "gemini_api_key": "",
            "siliconflow_api_key": "",
            "deepseek_api_key": "",
            "kimi_api_key": "",
            "glm_api_key": "",
            "grok_api_key": "",
            "infistar_api_key": "",
            "api88_api_key": "",
            "apimart_api_key": "",
            "seed_api_key": "",
            "model_name": "qwen-plus",
            "chunk_size": 5000,
            "min_score_threshold": 0.7,
            "max_clips_per_collection": 5
        }
        
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
                            "deepseek_api_key": api_keys.get("deepseek", ""),
                            "kimi_api_key": api_keys.get("kimi", ""),
                            "glm_api_key": api_keys.get("glm", ""),
                            "grok_api_key": api_keys.get("grok", ""),
                            "infistar_api_key": api_keys.get("infistar", ""),
                            "api88_api_key": api_keys.get("api88", ""),
                            "apimart_api_key": api_keys.get("apimart", ""),
                            "seed_api_key": api_keys.get("seed", ""),
                            "model_name": api.get("api_model", "qwen-plus")
                        })
                        # 设置页保存的提供商；旧版 settings.json 没有这个字段，保持 dashscope
                        if api.get("api_provider"):
                            default_settings["llm_provider"] = api["api_provider"]
                        if api.get("api_base_url"):
                            # 同一个字段：openai 系是兼容接口地址，dashscope 是国际站地址（#45）
                            if default_settings["llm_provider"] == "dashscope":
                                default_settings["dashscope_base_url"] = api["api_base_url"]
                            else:
                                default_settings["openai_base_url"] = api["api_base_url"]
                        # 设置页「切片参数」：以前只在 API 进程内存里改一下，流水线（worker / 本地线程）从没读过
                        processing = saved_settings.get("processing") or {}
                        for src, dst in (("processing_min_score", "min_score_threshold"),
                                         ("processing_chunk_size", "chunk_size"),
                                         ("processing_max_clips", "max_clips_per_collection")):
                            if processing.get(src) is not None:
                                default_settings[dst] = processing[src]
                    else:
                        # 处理旧的配置格式（直接平铺）
                        default_settings.update(saved_settings)
                        
            except Exception as e:
                logger.warning(f"加载设置文件失败: {sanitize_exception_text(e)}")
        
        self._apply_env_fallbacks(default_settings)
        self._apply_local_preset(default_settings)
        self._apply_cloud_preset(default_settings)
        route_identity: Dict[str, Any] = {}
        from backend.services import ai_model_settings as ai
        try:
            configured = ai.load()
        except Exception:
            raise ValueError('已保存的模型配置需要修复，请到「设置 → 服务商与模型」修复并保存后再生成。') from None
        if configured is not None:
            binding = ai.require_analysis(configured)
            connection = ai.connection_for(configured, binding)
            endpoint = ai.chat_endpoint(connection, binding.model)
            from backend.services.studio.failure_identity import connection_identity
            route_identity = connection_identity(connection, binding.model)
            source = getattr(binding, 'model_source', None) or getattr(binding, 'source', None)
            if source not in ('preset', 'user'):
                source = 'user'
            default_settings.update(llm_provider='openai', cloud_preset=None, llm_provider_preset=None,
                                    openai_api_key=endpoint['api_key'], openai_base_url=endpoint['base_url'],
                                    model_name=binding.model, connection_provider=connection.provider,
                                    connection_name=connection.name, model_source=source,
                                    chunk_size=configured.chunk_size,
                                    min_score_threshold=configured.min_score_threshold,
                                    max_clips_per_collection=configured.max_clips_per_collection)
        self._route_identity = route_identity  # kept off settings: settings.json is saved verbatim
        # Failed loads must remain retryable; never mark a broken assignment as loaded.
        self._settings_mtime = self._current_settings_mtime()
        self._settings_hash = self._current_settings_hash()
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

    def _apply_cloud_preset(self, settings: Dict[str, Any]) -> None:
        """deepseek / seed / kimi / glm / grok / infistar → openai + 官方地址，用各家自己的 key。"""
        from backend.core.cloud_presets import resolve_cloud_preset
        from backend.core.model_catalog import curated_models, default_model_for

        resolved = resolve_cloud_preset(settings.get("llm_provider"), settings.get("openai_base_url"))
        settings["cloud_preset"] = None
        if not resolved:
            return
        _provider, base_url, preset = resolved
        settings["llm_provider"] = "openai"
        settings["cloud_preset"] = preset.key
        settings["openai_base_url"] = base_url
        current = (settings.get("model_name") or "").strip()
        own = curated_models(preset.key)
        if not own:
            # 多模型网关（infistar）：gpt / deepseek / gemini 都是合法型号，用户选什么就用什么
            if not current and preset.default_model:
                settings["model_name"] = preset.default_model
            return
        known = set(curated_models())
        if not current or current == "qwen-plus" or (current in known and current not in own):
            settings["model_name"] = preset.default_model or default_model_for(preset.key)

    # Docker / 本地脚本模式没有设置页可用，只能靠环境变量（env.example 里也是这么写的），
    # 但此前这里只读 settings.json，导致 API_DASHSCOPE_API_KEY 等变量形同虚设。
    _ENV_KEY_FALLBACKS = {
        "dashscope_api_key": ("API_DASHSCOPE_API_KEY", "DASHSCOPE_API_KEY"),
        "openai_api_key": ("API_OPENAI_API_KEY", "OPENAI_API_KEY"),
        "gemini_api_key": ("API_GEMINI_API_KEY", "GEMINI_API_KEY"),
        "siliconflow_api_key": ("API_SILICONFLOW_API_KEY", "SILICONFLOW_API_KEY"),
        "deepseek_api_key": ("API_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"),
        "kimi_api_key": ("API_KIMI_API_KEY", "MOONSHOT_API_KEY", "KIMI_API_KEY"),
        "glm_api_key": ("API_GLM_API_KEY", "ZHIPU_API_KEY", "GLM_API_KEY"),
        "grok_api_key": ("API_GROK_API_KEY", "XAI_API_KEY", "GROK_API_KEY"),
        "infistar_api_key": ("API_INFISTAR_API_KEY", "INFISTAR_API_KEY"),
        "api88_api_key": ("API_API88_API_KEY", "API88_API_KEY"),
        "apimart_api_key": ("API_APIMART_API_KEY", "APIMART_API_KEY"),
        "seed_api_key": ("API_SEED_API_KEY", "ARK_API_KEY", "VOLCENGINE_API_KEY", "DOUBAO_API_KEY"),
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
            logger.error(f"保存设置失败: {sanitize_exception_text(e)}")
            raise
    
    def _initialize_provider(self):
        """初始化当前提供商"""
        try:
            provider_type = ProviderType(self.settings.get("llm_provider", "dashscope"))
            model_name = self.settings.get("model_name", "qwen-plus")
            
            # 本地预设不需要 key，也不要把用户的 OpenAI key 发给本地服务；
            # seed / kimi / glm / grok 用各家自己的 key，不要误用 openai_api_key
            cloud_preset = self.settings.get("cloud_preset")
            if self.settings.get("llm_provider_preset"):
                api_key = ""
            elif cloud_preset:
                from backend.core.cloud_presets import CLOUD_PRESETS
                api_key = self.settings.get(CLOUD_PRESETS[cloud_preset].api_key_setting, "")
            else:
                api_key = self._get_api_key_for_provider(provider_type)
            provider_kwargs = self._get_provider_kwargs(provider_type)

            # 自建 OpenAI 兼容服务（Ollama / vLLM 等）常常不需要 key，有 base_url 就够
            if api_key or (provider_type == ProviderType.OPENAI and provider_kwargs.get("base_url")):
                self.current_provider = LLMProviderFactory.create_provider(
                    provider_type, api_key or "", model_name, **provider_kwargs
                )
                logger.info("已初始化%s提供商，模型: %s, base_url_host: %s",
                            provider_type.value, sanitize_model(model_name),
                            hostname_of_base_url(provider_kwargs.get("base_url")))
            else:
                logger.warning(f"未找到{provider_type.value}的API密钥")
                self.current_provider = None
                
        except Exception as e:
            logger.error("初始化提供商失败: %s", sanitize_exception_text(e))
            self.current_provider = None

    def _get_provider_kwargs(self, provider_type: ProviderType) -> Dict[str, Any]:
        """提供商构造参数：OpenAI 兼容接口的 base_url；通义千问国际站也复用同一个字段（走兼容模式）"""
        if provider_type == ProviderType.OPENAI:
            base_url = (self.settings.get("openai_base_url") or "").strip()
            if base_url:
                return {"base_url": base_url}
        if provider_type == ProviderType.DASHSCOPE:
            base_url = (self.settings.get("dashscope_base_url") or "").strip()
            if base_url:
                return {"base_url": base_url, "mode": "compatible"}
        return {}

    def get_processing_setting(self, name: str, default: Any = None) -> Any:
        """设置页「切片参数」（min_score_threshold / chunk_size / max_clips_per_collection），随 settings.json 热重载"""
        self._reload_if_settings_changed()
        value = self.settings.get(name)
        return default if value is None else value

    def openai_compatible_endpoint(self) -> Optional[Dict[str, str]]:
        """当前文本模型对应的 OpenAI 兼容 Chat Completions 地址、key、模型。

        视觉理解默认复用文本模型：大多数提供商（Infistar / OpenAI / Gemini / Seed / Kimi / 通义…）
        同一个 key 就能发图片消息。能不能看图由「测试图片理解」验证，这里只负责给出地址。
        """
        from backend.core.llm_providers import (
            DASHSCOPE_CN_COMPATIBLE_BASE_URL, OPENAI_OFFICIAL_BASE_URL, normalize_base_url,
        )
        self._reload_if_settings_changed()
        s = self.settings
        provider = s.get("llm_provider", "dashscope")
        model = (s.get("model_name") or "").strip()
        if provider == "openai":
            cloud_preset = s.get("cloud_preset")
            if s.get("llm_provider_preset"):
                key = ""
            elif cloud_preset:
                from backend.core.cloud_presets import CLOUD_PRESETS
                key = s.get(CLOUD_PRESETS[cloud_preset].api_key_setting, "")
            else:
                key = s.get("openai_api_key", "")
            base = normalize_base_url(s.get("openai_base_url")) or OPENAI_OFFICIAL_BASE_URL
        elif provider == "dashscope":
            key = s.get("dashscope_api_key", "")
            base = normalize_base_url(s.get("dashscope_base_url")) or DASHSCOPE_CN_COMPATIBLE_BASE_URL
        elif provider == "gemini":
            key = s.get("gemini_api_key", "")
            from backend.core.provider_endpoint import official_chat_url
            base = official_chat_url('gemini')
        elif provider == "siliconflow":
            from backend.core.model_catalog import SILICONFLOW_BASE_URL
            key = s.get("siliconflow_api_key", "")
            base = SILICONFLOW_BASE_URL
        else:
            return None
        if not model:
            return None
        return {"base_url": base, "api_key": key or "", "model": model}
    
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
        with _settings_lock:
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
            
            logger.info("已切换到%s提供商，模型: %s", provider_type.value, sanitize_model(model_name))
            
        except Exception as e:
            logger.error("设置提供商失败: %s", sanitize_exception_text(e))
            raise log_safe_exception(e) from None
    
    def _analysis_endpoint(self, route: _CallRoute) -> tuple[str, str, str]:
        """Catalog slug, base URL, and key for one text-model substitution. The key is not logged."""
        from backend.core.model_recovery import analysis_catalog
        provider = route.provider
        info = route.info if isinstance(route.info, dict) else {}
        settings = route.settings if isinstance(route.settings, dict) else {}
        base = str(
            info.get("base_url")
            or settings.get("openai_base_url")
            or settings.get("dashscope_base_url")
            or getattr(provider, "base_url", "")
            or ""
        )
        key = str(getattr(provider, "api_key", "") or "")
        catalog = analysis_catalog(
            identity=route.identity if isinstance(route.identity, dict) else {},
            base_url=base,
            named=(
                settings.get("connection_provider"),
                settings.get("cloud_preset"),
                settings.get("llm_provider_preset"),
                info.get("provider"),
            ),
        )
        return catalog, base, key

    def _invoke_text(self, route: _CallRoute, prompt: str, input_data: Any, model_override, kwargs) -> tuple[LLMResponse, str]:
        from backend.core import llm_telemetry
        from backend.core.llm_degrade import bind_request_model, bound_request_model
        provider, settings, info = route.provider, route.settings, route.info
        with bind_request_model(model_override):
            chosen = bound_request_model(
                str(info.get("model") or getattr(provider, "model_name", "") or "")
            )
            with llm_telemetry.bind_context(
                provider=str(info.get("provider") or ""),
                model=chosen,
                base_url=str(info.get("base_url") or settings.get("openai_base_url") or settings.get("dashscope_base_url") or ""),
                kind="text",
                identity=route.identity,
            ):
                response = provider.call(prompt, input_data, **kwargs)
        return response, chosen

    def _retry_missing_text_model(
        self, error: Exception, route: _CallRoute, prompt: str, input_data: Any, kwargs,
        *, asked: str, sent: str,
    ) -> tuple[LLMResponse, str]:
        """One substitute when the text model is gone. Does not write settings.

        The slot key is the id this call was asked to send (saved settings or
        ``API_MODEL_NAME``), matching vision recovery. A failed substitute is
        not remembered. Telemetry stays on the provider call: error codes and
        the model id that was actually sent.
        """
        from backend.core import llm_telemetry
        from backend.core.llm_degrade import consume_chunk_call
        from backend.core.model_recovery import remember_model, resolve_available_analysis_model
        from backend.core.upstream_errors import UpstreamErrorType, classify_exception
        if classify_exception(error).error_type is not UpstreamErrorType.MODEL_NOT_FOUND:
            raise error
        # The outer call already reserved its SDK retries. This resend does too.
        if not consume_chunk_call():
            raise error
        catalog, base, key = self._analysis_endpoint(route)
        failed = sent or asked
        alt = resolve_available_analysis_model(
            base_url=base, api_key=key, provider=catalog,
            failed_model=failed, exclude=(asked, sent),
        )
        if not alt or alt == failed:
            raise error
        token = llm_telemetry.set_retry_count(llm_telemetry.current_retry_count() + 1)
        try:
            response, chosen = self._invoke_text(route, prompt, input_data, alt, kwargs)
        except Exception:
            raise
        else:
            remember_model(catalog, base, key, asked, alt, purpose="analysis")
            return response, chosen
        finally:
            llm_telemetry.reset_retry_count(token)

    def call(self, prompt: str, input_data: Any = None, **kwargs) -> str:
        """调用LLM。设了 AUTOCLIP_LLM_CACHE_DIR 时按 sha1(prompt+input) 录制 / 回放，给回归集用。

        ``model`` is per-call candidate state. It is not written to
        ``settings`` or ``current_provider.model_name``. A retired text model
        is substituted once from the live list and remembered for this process.
        """
        from backend.core.model_recovery import remembered_model
        from backend.core.project_cancellation import checkpoint
        override = kwargs.pop("model", None)
        route = kwargs.pop("_route", None)
        checkpoint()  # 项目已删除，或这次制作已超过总时长：不再为它花钱
        route = route or self._snapshot_call_route()
        provider, info = route.provider, route.info
        cache_path = _llm_cache_path(prompt, input_data)
        if cache_path is not None and cache_path.exists():
            logger.info("LLM 缓存命中")
            return cache_path.read_text(encoding="utf-8")
        if not provider:
            raise ValueError("未配置LLM提供商，请自备 API Key 并到「设置 → 服务商与模型」填写")

        saved = str(info.get("model") or getattr(provider, "model_name", "") or "").strip()
        asked = str(override).strip() if isinstance(override, str) and str(override).strip() else saved
        catalog, base, key = self._analysis_endpoint(route)
        cached = remembered_model(catalog, base, key, asked) if asked else None
        if cached:
            override = cached
        sent = cached or asked
        try:
            try:
                response, chosen = self._invoke_text(route, prompt, input_data, override, kwargs)
            except Exception as error:
                response, chosen = self._retry_missing_text_model(
                    error, route, prompt, input_data, kwargs, asked=asked, sent=sent,
                )
            content = response.content
            from backend.core import llm_usage
            llm_usage.record(response.model or chosen, response.usage,
                             prompt_chars=len(provider._build_full_input(prompt, input_data)), completion_chars=len(content or ""))
            if cache_path is not None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(content, encoding="utf-8")
            return content
        except Exception as e:
            from backend.core.job_budget import promote_if_budget_spent
            from backend.core.llm_telemetry import sanitize_exception_text
            promote_if_budget_spent(e)
            logger.error("LLM调用失败: %s", sanitize_exception_text(e))
            raise log_safe_exception(e) from None

    def call_with_retry(self, prompt: str, input_data: Any = None, max_retries: int = 3, **kwargs) -> str:
        """Retry, then fall back to the next same-provider preset candidate.

        #358 / #365 budget is shared across candidates (not reset per model):
        at most 3 manager ``call()`` for a retryable type. Each ``call()``
        reserves ``1 + LLM_SDK_MAX_RETRIES`` HTTP attempts against the
        per-chunk cap of 6. OpenAI compatibility resends reserve their own
        attempts. An enclosing chunk keeps this budget across result-repair
        rounds. Candidate model is per-call state only.
        """
        from backend.core import llm_telemetry
        from backend.core.llm_degrade import (
            call_note_same_provider_degrade,
            candidates_for_call,
            chunk_call_budget,
            chunk_http_remaining,
            chunk_last_error,
            consume_chunk_call,
            http_attempts_per_call,
            remember_chunk_error,
            resolve_model_source,
            should_degrade_to_next,
        )
        from backend.core.llm_retry import (
            backoff_seconds,
            classify_for_retry as classify_http,
            max_attempts_for,
        )
        from backend.core.llm_telemetry import sanitize_model
        from backend.core.result_retry import classify_for_retry as classify_result
        from backend.core.upstream_errors import UpstreamErrorType
        import time

        route = self._snapshot_call_route()
        settings = route.settings
        source = resolve_model_source(settings)
        candidates = candidates_for_call(settings)
        last_error: Exception | None = None
        attempt = 0
        from backend.core.llm_emit import begin_logical_call
        begin_logical_call()  # E2: all attempts of this call share one retry peak
        with chunk_call_budget():
            for index, model in enumerate(candidates):
                while True:
                    from backend.core.job_budget import ensure_clip_job_budget
                    ensure_clip_job_budget()
                    if not consume_chunk_call():
                        raise last_error or chunk_last_error() or RuntimeError(
                            "llm chunk call budget exhausted"
                        )
                    token = llm_telemetry.set_retry_count(attempt)
                    try:
                        return self.call(prompt, input_data, model=model, _route=route, **kwargs)
                    except Exception as error:
                        from backend.core.job_budget import JobDurationExceeded, promote_if_budget_spent
                        if isinstance(error, JobDurationExceeded):
                            raise
                        promote_if_budget_spent(error)
                        last_error = error
                        remember_chunk_error(error)
                        info, status, retry_after = classify_http(error)
                        result_kind, result_retryable = classify_result(error)
                        if info.error_type is UpstreamErrorType.RATE_LIMITED:
                            from backend.pipeline.concurrency import note_rate_limited
                            note_rate_limited()
                        retryable = bool(info.retryable or result_retryable)
                        kind = result_kind if result_retryable else info.error_type.value
                        if result_retryable and not info.retryable:
                            from backend.core.result_retry import MAX_ATTEMPTS
                            budget = min(MAX_ATTEMPTS, max(1, max_retries))
                        else:
                            budget = max_attempts_for(info.error_type, max(1, max_retries))
                        more = index + 1 < len(candidates)
                        can_degrade = (
                            source == "preset"
                            and more
                            and should_degrade_to_next(error)
                            and chunk_http_remaining() >= http_attempts_per_call()
                        )
                        if can_degrade:
                            if retryable and attempt >= budget - 1:
                                if attempt:
                                    logger.error(
                                        "LLM调用在%s次后失败（%s，retryable=%s）。",
                                        attempt + 1, kind, retryable,
                                    )
                                raise
                            logger.warning(
                                "frequency rate limit on %s, trying next same-provider candidate",
                                sanitize_model(str(model or "")) or "model",
                            )
                            call_note_same_provider_degrade(self)
                            if retryable:
                                delay = backoff_seconds(retry_after, attempt) if info.retryable else (2 ** attempt)
                                logger.warning(
                                    "第%s次调用失败（%s，http=%s），%.1fs 后重试: %s",
                                    attempt + 1, kind, status, delay,
                                    llm_telemetry.sanitize_exception_text(error),
                                )
                                time.sleep(delay)
                                attempt += 1
                            break
                        if not retryable or attempt >= budget - 1:
                            if attempt:
                                logger.error(
                                    "LLM调用在%s次后失败（%s，retryable=%s）。",
                                    attempt + 1, kind, retryable,
                                )
                            raise
                        delay = backoff_seconds(retry_after, attempt) if info.retryable else (2 ** attempt)
                        logger.warning(
                            "第%s次调用失败（%s，http=%s），%.1fs 后重试: %s",
                            attempt + 1, kind, status, delay,
                            llm_telemetry.sanitize_exception_text(error),
                        )
                        time.sleep(delay)
                        attempt += 1
                    finally:
                        llm_telemetry.reset_retry_count(token)
            if last_error is not None:
                raise last_error
            raise RuntimeError("LLM candidate loop exhausted")
    
    def note_same_provider_degrade(self) -> int:
        """hook: increment ``degrade_count`` when switching to the next candidate.

        Isolated from ``call`` / ``call_with_retry`` so the fallback loop can
        rebase without touching emit plumbing. Only a non-negative count is
        recorded — no model name, URL, path, or user text.
        """
        return note_same_provider_degrade()

    def test_provider_connection(self, provider_type: ProviderType, api_key: str, model_name: str,
                                 **provider_kwargs) -> bool:
        """测试提供商连接"""
        try:
            provider = LLMProviderFactory.create_provider(provider_type, api_key, model_name, **provider_kwargs)
            return provider.test_connection()
        except Exception as e:
            logger.error(f"测试{provider_type.value}连接失败: {sanitize_exception_text(e)}")
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
        cloud_preset = self.settings.get("cloud_preset")
        info = {
            # 设置页 / CLI 看到的是用户选的名字（ollama / kimi），底层仍是 openai 兼容
            "provider": preset or cloud_preset or provider_type.value,
            "backend_provider": provider_type.value,
            "model": model_name,
            "available": self.current_provider is not None,
            "display_name": self._get_provider_display_name(provider_type),
        }
        if preset:
            from backend.core.local_presets import preset_display_name
            info["display_name"] = preset_display_name(preset) or info["display_name"]
        if cloud_preset:
            from backend.core.cloud_presets import cloud_preset_display_name
            info["display_name"] = cloud_preset_display_name(cloud_preset) or info["display_name"]
        base_url = self._get_provider_kwargs(provider_type).get("base_url")
        if base_url:
            info["base_url"] = base_url
        if self.settings.get('connection_provider'):
            info['provider'] = self.settings['connection_provider']
            info['display_name'] = self.settings['connection_name']
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

def note_same_provider_degrade() -> int:
    """Increment the run/request ``degrade_count``. Safe if telemetry is absent."""
    try:
        from backend.core import llm_telemetry
        return llm_telemetry.increment_degrade_count()
    except Exception:  # noqa: BLE001 - telemetry must not break fallback
        return 0


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
