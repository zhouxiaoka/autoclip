"""
多模型提供商统一接口
支持OpenAI、Gemini、硅基流动、阿里DashScope等
"""
import json
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

from backend.core.llm_telemetry import hostname_of_base_url, sanitize_exception_text, sanitize_model, log_safe_exception
from backend.core.failure_logging import failure_logger

logger = failure_logger(__name__)

class ProviderType(Enum):
    """模型提供商类型"""
    DASHSCOPE = "dashscope"  # 阿里通义千问
    OPENAI = "openai"        # OpenAI
    GEMINI = "gemini"        # Google Gemini
    SILICONFLOW = "siliconflow"  # 硅基流动

@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    display_name: str
    provider: ProviderType
    max_tokens: int
    cost_per_token: Optional[float] = None
    description: Optional[str] = None

@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None

def _catalog_model_infos(provider_type: "ProviderType") -> List[ModelInfo]:
    """从 model_catalog 的内置名单生成 ModelInfo，避免各 provider 再手写一份过期列表。"""
    from backend.core.model_catalog import curated_models
    return [
        ModelInfo(name=name, display_name=name, provider=provider_type, max_tokens=128000)
        for name in curated_models(provider_type.value)
    ]


class LLMProvider(ABC):
    """LLM提供商抽象基类"""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        raw = cls.__dict__.get('call')
        if raw is None or getattr(raw, '_llm_telemetry', False):
            return

        def wrapped(self, prompt: str, input_data: Any = None, **call_kwargs):
            from backend.core.llm_telemetry import observe_provider_call
            return observe_provider_call(self, raw, prompt, input_data, **call_kwargs)

        wrapped._llm_telemetry = True  # type: ignore[attr-defined]
        cls.call = wrapped  # type: ignore[method-assign]
    
    def __init__(self, api_key: str, model_name: str, **kwargs):
        self.api_key = api_key
        self.model_name = model_name
        self.kwargs = kwargs

    def request_model(self) -> str:
        """Model for this request only. Never writes ``self.model_name``."""
        from backend.core.llm_degrade import bound_request_model
        return bound_request_model(self.model_name)
    
    @abstractmethod
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """
        调用模型API
        
        Args:
            prompt: 提示词
            input_data: 输入数据
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 模型响应
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        测试API连接
        
        Returns:
            bool: 连接是否成功
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[ModelInfo]:
        """
        获取可用模型列表
        
        Returns:
            List[ModelInfo]: 可用模型列表
        """
        pass
    
    def _build_full_input(self, prompt: str, input_data: Any = None) -> str:
        """构建完整的输入"""
        if input_data:
            if isinstance(input_data, (dict, list, tuple)):
                # Compact JSON: indentation adds ~10 tokens per subtitle row for no gain.
                return f"{prompt}\n\n输入内容：\n{json.dumps(input_data, ensure_ascii=False, default=str)}"
            else:
                return f"{prompt}\n\n输入内容：\n{input_data}"
        return prompt

class DashScopeProvider(LLMProvider):
    """阿里DashScope提供商"""
    
    def __init__(self, api_key: str, model_name: str = "qwen-plus", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        # 国际站（alibabacloud.com，#45）的 key 只能打 dashscope-intl 域名；native SDK 的地址是进程级全局变量，
        # 所以有自定义 base_url 时一律走 OpenAI 兼容模式，按实例隔离
        custom_base_url = normalize_base_url(kwargs.get("base_url") or os.getenv("DASHSCOPE_BASE_URL", ""))
        # 模式切换: native (SDK Generation.call) | compatible (OpenAI兼容)
        self.mode = (kwargs.get("mode") or os.getenv("DASHSCOPE_MODE") or ("compatible" if custom_base_url else "native")).lower()
        # 兼容模式 base_url
        self.base_url = custom_base_url or DASHSCOPE_CN_COMPATIBLE_BASE_URL
        self.is_international = self.base_url == DASHSCOPE_INTL_COMPATIBLE_BASE_URL
        # 原生模式 SDK
        self._ds_generation = None
        if self.mode == "native":
            try:
                from dashscope import Generation
                self._ds_generation = Generation
            except ImportError:
                raise ImportError("请安装dashscope: pip install dashscope")
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用DashScope API（mode: native|compatible）"""
        model = self.request_model()
        logger.info("[DashScope] mode=%s model=%s base_url_host=%s",
                    self.mode, sanitize_model(model),
                    hostname_of_base_url(self.base_url) if self.mode == "compatible" else "sdk-generation")
        if self.mode == "native":
            old_api_key = os.getenv("DASHSCOPE_API_KEY")
            os.environ["DASHSCOPE_API_KEY"] = self.api_key
            try:
                full_input = self._build_full_input(prompt, input_data)
                call_kwargs = {key: value for key, value in kwargs.items() if key != "stream"}
                if (model or "").strip().lower() in QWEN_HYBRID_THINKING_MODELS:
                    # 原生 SDK 只连百炼；清单内的混合思考模型关掉默认思考（见 QWEN_HYBRID_THINKING_MODELS）
                    call_kwargs.setdefault("enable_thinking", False)
                result = self._native_completion(model, full_input, call_kwargs)
                if isinstance(result, LLMResponse):
                    return result
                return _native_llm_response(result, model)
            except Exception as e:
                from backend.core.job_budget import promote_if_budget_spent
                promote_if_budget_spent(e)
                logger.error(f"DashScope(native)调用失败: {sanitize_exception_text(e)}")
                raise log_safe_exception(e) from None
            finally:
                if old_api_key is not None:
                    os.environ["DASHSCOPE_API_KEY"] = old_api_key
                elif "DASHSCOPE_API_KEY" in os.environ:
                    del os.environ["DASHSCOPE_API_KEY"]
        else:
            # compatible
            try:
                full_input = self._build_full_input(prompt, input_data)
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": full_input}],
                }
                payload.update({k: v for k, v in kwargs.items() if v is not None and k != "stream"})
                if disables_qwen_thinking(model, self.base_url):
                    payload.setdefault("enable_thinking", False)  # 原始 HTTP 请求：顶层参数
                url = f"{self.base_url}/chat/completions"
                # 以前读超时只有 30 秒：长字幕的挑片调用必然超时。与 OpenAIProvider 保持一致。
                # Streaming keeps the socket alive; the read timeout is still the idle cap,
                # shortened to whatever the clip job has left.
                from backend.core.llm_stream import post_chat_completion
                timeout = _http_timeout(LLM_READ_TIMEOUT_SEC)
                collected = post_chat_completion(
                    url, headers=headers, payload=payload, timeout=timeout,
                    refresh_timeout=lambda: _http_timeout(LLM_READ_TIMEOUT_SEC),
                )
                return LLMResponse(
                    content=collected.content, usage=collected.usage, model=model,
                    finish_reason=collected.finish_reason,
                )
            except Exception as e:
                from backend.core.job_budget import promote_if_budget_spent
                promote_if_budget_spent(e)
                logger.error(f"DashScope(compatible)调用失败: {sanitize_exception_text(e)}")
                raise log_safe_exception(e) from None

    def _native_completion(self, model: str, full_input: str, call_kwargs: dict) -> Any:
        """Prefer a live stream. A refusal or a single JSON response uses the old parser."""
        from backend.core.llm_degrade import consume_chunk_call
        from backend.core.llm_stream import StreamRejected, collect_sdk, is_chunk_stream, stream_rejected

        def issue(stream: bool) -> Any:
            return self._ds_generation.call(
                model=model,
                prompt=full_input,
                api_key=self.api_key,
                stream=stream,
                **call_kwargs,
            )

        resp = issue(True)
        if is_chunk_stream(resp):
            try:
                collected = collect_sdk(resp)
            except StreamRejected as rejected:
                if not consume_chunk_call():
                    raise rejected.error
                logger.info("上游不接受 stream，改回整包响应再试一次")
                resp = issue(False)
            else:
                usage = collected.usage or {}
                if not usage:
                    shaped = None
                elif "input_tokens" in usage or "output_tokens" in usage:
                    shaped = {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")}
                else:
                    shaped = usage
                return LLMResponse(
                    content=collected.content or "",
                    usage=shaped,
                    model=model,
                    finish_reason=collected.finish_reason,
                )
        status = getattr(resp, "status_code", None)
        body = {"code": getattr(resp, "code", None), "message": getattr(resp, "message", None)}
        if isinstance(status, int) and status != 200 and stream_rejected(status, body) and consume_chunk_call():
            logger.info("上游不接受 stream，改回整包响应再试一次")
            resp = issue(False)
        return resp
    
    def test_connection(self) -> bool:
        """测试DashScope连接"""
        try:
            # 首先验证API Key格式
            if not self.api_key or len(self.api_key.strip()) < 10:
                logger.error("API Key为空或过短")
                return False
            
            # 检查API Key格式（DashScope API Key通常是sk-开头）
            if not self.api_key.startswith("sk-"):
                logger.warning("API Key格式可能不正确，期望以'sk-'开头")
                # 不直接返回False，因为有些API Key可能格式不同
            
            # 使用简单的测试调用，避免复杂的API验证
            try:
                # 直接调用call方法进行测试
                response = self.call("测试", max_tokens=1)
                if response and str(response.content or "").strip():
                    logger.info("DashScope API连接测试成功")
                    return True
                else:
                    logger.error("DashScope API测试返回空响应")
                    return False
                    
            except Exception as e:
                logger.error(f"DashScope API测试失败: {sanitize_exception_text(e)}")
                return False
                
        except Exception as e:
            logger.error(f"DashScope连接测试失败: {sanitize_exception_text(e)}")
            return False
    
    def get_available_models(self) -> List[ModelInfo]:
        """获取DashScope可用模型（内置常用名单；设置页会再按账号实时拉取）"""
        return _catalog_model_infos(ProviderType.DASHSCOPE)

OPENAI_OFFICIAL_BASE_URL = "https://api.openai.com/v1"
# 本地/自建 OpenAI 兼容服务（Ollama、vLLM、LM Studio 等）通常不校验 key，但 SDK 要求非空
OPENAI_COMPATIBLE_PLACEHOLDER_KEY = "EMPTY"
# 通义千问 OpenAI 兼容接口：中国站 / 国际站（alibabacloud.com 开通的 key 只能打国际站，#45）
DASHSCOPE_CN_COMPATIBLE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_INTL_COMPATIBLE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


def normalize_base_url(base_url: Optional[str]) -> str:
    """去掉空白与结尾的 `/`，空值返回空串（表示使用官方地址）"""
    return (base_url or "").strip().rstrip("/")


def is_local_url(url: Optional[str]) -> bool:
    """
    是否指向本机 / 局域网（Ollama、LM Studio、vLLM 常见部署位置）。
    这类地址绝不该走系统代理：macOS 上 httpx 会读系统代理设置（Clash / Surge 等），
    把 localhost 请求也送进代理，结果就是 502 / 超时，用户完全摸不着头脑。
    """
    if not url:
        return False
    try:
        from urllib.parse import urlparse
        import ipaddress
        host = (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return False
    if host in ("localhost", "0.0.0.0", "host.docker.internal") or host.endswith(".local") or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private or ip.is_link_local
    except ValueError:
        return False


def make_openai_http_client(base_url: Optional[str]):
    """本地地址 → 不信任环境 / 系统代理的 httpx.Client；其它返回 None（用 SDK 默认）。"""
    if not is_local_url(base_url):
        return None
    try:
        import httpx
        return httpx.Client(trust_env=False)
    except Exception:  # noqa: BLE001
        return None


# DeepSeek 思考模式默认开启（effort 为 high），推理 token 按输出计费，单次输出上限 384K。
# 切片分析只要结构化结果。不关的话，几小时字幕、分块多步调用，账单会明显高于可见回答。
DEEPSEEK_COMPLETION_TOKEN_CAP = 16384


def is_deepseek_endpoint(base_url: Optional[str]) -> bool:
    return "api.deepseek.com" in (base_url or "").lower()


def deepseek_chat_kwargs(base_url: Optional[str], request: Dict[str, Any]) -> Dict[str, Any]:
    """关掉官方 DeepSeek 的默认思考模式，并给未指定的输出加上限。

    调用方已经传入的 max_tokens（例如连接测试的 1）保持不变。
    非 api.deepseek.com 的兼容接口不改请求体，避免把 thinking 字段发给不认识它的服务。
    """
    if not is_deepseek_endpoint(base_url):
        return request
    guarded = dict(request)
    extra = dict(guarded.get("extra_body") or {})
    extra.setdefault("thinking", {"type": "disabled"})
    guarded["extra_body"] = extra
    if guarded.get("max_tokens") is None:
        guarded["max_tokens"] = DEEPSEEK_COMPLETION_TOKEN_CAP
    return guarded


# 百炼（DashScope）上的 Qwen3.5–3.8 混合思考模型默认开启思考，推理 token 按输出计费，而且很慢：
# RC156 Win QA #18 里 qwen3.8-flash 一次挑片调用 43,055 个输出 token 只换来 255 个字的回答，用了 578 秒。
# 切片 / 边界 / 包装都只要结构化结果，所以和 DeepSeek 一样按请求关掉思考（enable_thinking=false）。
# 只对下面这张显式清单生效（来源：百炼文档「深度思考」https://help.aliyun.com/zh/model-studio/deep-thinking
# 的“混合思考模式，默认开启思考模式”各系列，以及「视觉理解」https://help.aliyun.com/zh/model-studio/vision）：
# - 仅思考模式的型号（qwen3.8-2.4t-a95b、qwen3.7-max-preview、qwen3.7-max-2026-05-17、qwq-plus、*-thinking*）
#   传 false 会被拒（400），不在清单里；
# - 默认就不思考的型号（qwen-plus / qwen-flash / qwen-turbo / qwen3-max、qwen3-vl-plus / qwen3-vl-flash）不需要，保持原样；
# - 开源 Qwen3（qwen3-32b 等）与 Omni 系列另有流式限制，不碰；
# - 不在清单里的型号、不是百炼地址的兼容接口（中转 / 代理 / 本地），请求体一律不变。
QWEN_HYBRID_THINKING_MODELS = frozenset({
    # Qwen3.8
    "qwen3.8-max", "qwen3.8-max-0902", "qwen3.8-flash", "qwen3.8-27b",
    # Qwen3.7（qwen3.7-max-preview / qwen3.7-max-2026-05-17 仅思考，不在这里）
    "qwen3.7-max", "qwen3.7-max-2026-05-20", "qwen3.7-max-2026-06-08",
    "qwen3.7-plus", "qwen3.7-plus-2026-05-26", "qwen3.7-flash", "qwen3.7-flash-2026-07-15",
    # Qwen3.6
    "qwen3.6-max-preview", "qwen3.6-plus", "qwen3.6-plus-2026-04-02", "qwen3.6-flash", "qwen3.6-flash-2026-04-16",
    # Qwen3.5
    "qwen3.5-plus", "qwen3.5-plus-2026-02-15", "qwen3.5-flash", "qwen3.5-flash-2026-02-23",
    "qwen3.5-397b-a17b", "qwen3.5-122b-a10b", "qwen3.5-27b", "qwen3.5-35b-a3b",
})


def is_dashscope_endpoint(base_url: Optional[str]) -> bool:
    """百炼官方地址：dashscope[-intl/-us…].aliyuncs.com 与业务空间专属的 *.maas.aliyuncs.com。

    空地址不算（OpenAIProvider 的空地址是 OpenAI 官方）；中转、代理、本地服务都不算。
    """
    from urllib.parse import urlparse
    raw = (base_url or "").strip()
    if not raw:
        return False
    host = (urlparse(raw if "://" in raw else "https://" + raw).hostname or "").lower()
    if host.endswith(".maas.aliyuncs.com"):
        return True
    return host.endswith(".aliyuncs.com") and host.split(".", 1)[0].startswith("dashscope")


def disables_qwen_thinking(model: Optional[str], base_url: Optional[str]) -> bool:
    """这次请求要不要带 enable_thinking=false：清单里的 Qwen 混合思考模型 + 百炼地址。"""
    return (model or "").strip().lower() in QWEN_HYBRID_THINKING_MODELS and is_dashscope_endpoint(base_url)


def dashscope_chat_kwargs(base_url: Optional[str], request: Dict[str, Any]) -> Dict[str, Any]:
    """OpenAI SDK 请求：清单内模型在 extra_body 里关掉思考；调用方自己给了 enable_thinking 就不改。"""
    if not disables_qwen_thinking(request.get("model"), base_url):
        return request
    guarded = dict(request)
    extra = dict(guarded.get("extra_body") or {})
    extra.setdefault("enable_thinking", False)
    guarded["extra_body"] = extra
    return guarded


def guarded_chat_kwargs(base_url: Optional[str], request: Dict[str, Any]) -> Dict[str, Any]:
    """所有 OpenAI 兼容文字请求都经过这里：DeepSeek 与百炼 Qwen 的思考开关。"""
    return dashscope_chat_kwargs(base_url, deepseek_chat_kwargs(base_url, request))


def http_chat_body(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Raw HTTP JSON. The OpenAI SDK merges ``extra_body``; httpx/requests do not.

    Connection probes and other direct posts must send ``enable_thinking`` /
    ``thinking`` at the top level, or Qwen and DeepSeek keep their default thinking.
    """
    body = {key: value for key, value in payload.items() if key != "extra_body"}
    extra = payload.get("extra_body")
    if isinstance(extra, dict):
        for key, value in extra.items():
            body.setdefault(key, value)
    return body


def _http_timeout(default_read: float):
    """``(connect, read)`` for one chat POST. The read shrinks to the job budget."""
    from backend.core.job_budget import clip_job_read_timeout
    read = clip_job_read_timeout(default_read)
    return (min(LLM_CONNECT_TIMEOUT_SEC, read), read)


def _native_llm_response(resp: Any, model: str) -> LLMResponse:
    if resp and getattr(resp, "status_code", 200) == 200:
        output = getattr(resp, "output", None)
        if output is not None and getattr(output, "text", None) is not None:
            usage = getattr(resp, "usage", None)
            return LLMResponse(
                content=output.text,
                usage={"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")} if usage else None,
                model=model,
                finish_reason=getattr(output, "finish_reason", None),
            )
        logger.warning("API请求成功，但输出为空。")
        return LLMResponse(content="")
    code = getattr(resp, "code", "N/A")
    message = getattr(resp, "message", "未知API错误")
    error = RuntimeError(str(message))
    error.status_code = getattr(resp, "status_code", None)
    error.body = {"code": code, "message": message}
    raise error


def _budget_request_timeout(default_read: float):
    """Per-request read timeout while a clip job is running. ``None`` outside a job."""
    from backend.core.job_budget import clip_job_active, clip_job_read_timeout
    if not clip_job_active():
        return None
    read = clip_job_read_timeout(default_read)
    try:
        import httpx
        return httpx.Timeout(read, connect=min(LLM_CONNECT_TIMEOUT_SEC, read))
    except ImportError:  # pragma: no cover
        return read


# OpenAI 官方的推理型号（o 系列、gpt-5 及以后）不认 max_tokens，返回 400 要求改用
# max_completion_tokens（#333）。官方地址上的已知型号直接改名；其它情况（中转、Azure 等）
# 等服务端 400 点名这个参数时再改名重试一次。DeepSeek / 百炼 / Ollama 等兼容接口请求体不变。
_COMPLETION_TOKEN_MODEL = re.compile(r"^(?:o\d+|gpt-(?:[5-9]|\d{2,}))(?:[.\-]|$)")


def is_official_openai(base_url: Optional[str]) -> bool:
    url = normalize_base_url(base_url)
    return not url or "api.openai.com" in url.lower()


def uses_max_completion_tokens(model: Optional[str], base_url: Optional[str]) -> bool:
    name = (model or "").strip().lower().split("/")[-1]
    return is_official_openai(base_url) and bool(_COMPLETION_TOKEN_MODEL.match(name))


def to_max_completion_tokens(request: Dict[str, Any]) -> Dict[str, Any]:
    """把请求里的 max_tokens 改名为 max_completion_tokens；没有 max_tokens 时原样返回。"""
    if request.get("max_tokens") is None:
        return request
    renamed = dict(request)
    value = renamed.pop("max_tokens")
    renamed.setdefault("max_completion_tokens", value)
    return renamed


def asks_for_max_completion_tokens(message: Any) -> bool:
    """400 的错误信息是否在说：不支持 max_tokens，请用 max_completion_tokens。"""
    text = str(message or "")
    return "max_tokens" in text and "max_completion_tokens" in text


def token_param_kwargs(model: Optional[str], base_url: Optional[str], request: Dict[str, Any]) -> Dict[str, Any]:
    return to_max_completion_tokens(request) if uses_max_completion_tokens(model, base_url) else request


# OpenAI SDK 默认读超时 600 秒、自动重试 2 次（超时也重试）。挑片外面还有一次「带原因重试」，
# 大纲走 call_with_retry 的 3 次，叠起来一个窗口最坏能等一个小时。这里写明超时，并把 SDK 自身的重试降到 1 次
# （保留对 429 / 5xx / 断线的一次退避重试），其余交给外层按业务语义重试。
LLM_READ_TIMEOUT_SEC = 600.0
LLM_CONNECT_TIMEOUT_SEC = 15.0
LLM_SDK_MAX_RETRIES = 1


class OpenAIProvider(LLMProvider):
    """OpenAI 及一切 OpenAI 兼容接口（智谱、DeepSeek、OpenRouter、Ollama、vLLM、LM Studio 等）

    通过 `base_url` 指向兼容服务即可复用；为空时走 OpenAI 官方地址。
    """
    
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        self.base_url = normalize_base_url(kwargs.get("base_url") or os.getenv("OPENAI_BASE_URL"))
        self.is_custom_endpoint = bool(self.base_url) and self.base_url != OPENAI_OFFICIAL_BASE_URL
        if not api_key and self.is_custom_endpoint:
            api_key = OPENAI_COMPATIBLE_PLACEHOLDER_KEY
            self.api_key = api_key
        try:
            import openai
            client_kwargs = {"api_key": api_key, "max_retries": LLM_SDK_MAX_RETRIES}
            try:
                import httpx
                client_kwargs["timeout"] = httpx.Timeout(LLM_READ_TIMEOUT_SEC, connect=LLM_CONNECT_TIMEOUT_SEC)
            except ImportError:  # pragma: no cover - httpx ships with openai
                client_kwargs["timeout"] = LLM_READ_TIMEOUT_SEC
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
                http_client = make_openai_http_client(self.base_url)
                if http_client is not None:
                    client_kwargs["http_client"] = http_client
            self.client = openai.OpenAI(**client_kwargs)
        except ImportError:
            raise ImportError("请安装openai: pip install openai")
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用OpenAI API"""
        try:
            model = self.request_model()
            full_input = self._build_full_input(prompt, input_data)
            payload = token_param_kwargs(model, self.base_url, guarded_chat_kwargs(self.base_url, {
                "model": model,
                "messages": [{"role": "user", "content": full_input}],
                **{key: value for key, value in kwargs.items() if key != "stream"},
            }))
            # A long think used to die on a silent socket. Stream when the host
            # can; a refusal or a single JSON body is assembled the same way.
            payload["stream"] = True
            from backend.core.llm_stream import collect_sdk, create_openai_chat
            request_timeout = _budget_request_timeout(LLM_READ_TIMEOUT_SEC)
            try:
                response = create_openai_chat(
                    self.client, payload, request_timeout, lambda: _budget_request_timeout(LLM_READ_TIMEOUT_SEC))
            except Exception as error:  # noqa: BLE001 - only the max_tokens 400 is retried
                if payload.get("max_tokens") is None or getattr(error, "status_code", None) != 400 \
                        or not asks_for_max_completion_tokens(error):
                    raise
                # The manager reserved the first SDK call, not this compatibility
                # resend. Reserve its SDK retries too before issuing another request.
                from backend.core.llm_degrade import consume_chunk_call
                if not consume_chunk_call():
                    raise
                logger.info("模型 %s 不支持 max_tokens，改用 max_completion_tokens 重试一次", sanitize_model(model))
                response = create_openai_chat(
                    self.client, to_max_completion_tokens(payload),
                    _budget_request_timeout(LLM_READ_TIMEOUT_SEC),
                    lambda: _budget_request_timeout(LLM_READ_TIMEOUT_SEC))
            collected = collect_sdk(response)
            usage = collected.usage
            if usage:
                logger.info(
                    "LLM usage model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s",
                    sanitize_model(model),
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    usage.get("total_tokens"),
                )
            
            return LLMResponse(
                content=collected.content,
                usage=usage,
                model=model,
                finish_reason=collected.finish_reason,
            )
            
        except Exception as e:
            from backend.core.job_budget import promote_if_budget_spent
            promote_if_budget_spent(e)
            logger.error("OpenAI调用失败: %s", sanitize_exception_text(e))
            raise log_safe_exception(e) from None
    
    def test_connection(self) -> bool:
        """测试OpenAI / 兼容接口连接"""
        try:
            # 官方 OpenAI 才校验 key 格式；兼容服务的 key 五花八门（甚至不需要）
            if not self.is_custom_endpoint:
                if not self.api_key or len(self.api_key.strip()) < 10:
                    logger.error("OpenAI API Key为空或过短")
                    return False
                if not self.api_key.startswith("sk-"):
                    logger.warning("OpenAI API Key格式可能不正确，期望以'sk-'开头")
            
            # 真实小请求：额度只剩一点时 max_tokens=1 也能通过。推理型号的输出上限也算推理 token。
            response = self.call("测试", max_tokens=256 if uses_max_completion_tokens(self.model_name, self.base_url) else 16)
            return bool(response and str(response.content or "").strip())
        except Exception as e:
            logger.error("OpenAI连接测试失败 (base_url_host=%s): %s",
                         hostname_of_base_url(self.base_url or OPENAI_OFFICIAL_BASE_URL),
                         sanitize_exception_text(e))
            return False
    
    def get_available_models(self) -> List[ModelInfo]:
        """获取OpenAI可用模型（内置常用名单；兼容接口的型号以服务端 `/models` 为准）"""
        return _catalog_model_infos(ProviderType.OPENAI)

class GeminiProvider(LLMProvider):
    """Google Gemini提供商"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-3.8-flash", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        try:
            # New unified Google GenAI SDK (replaces the deprecated
            # google-generativeai package).
            from google import genai
            self.client = genai.Client(api_key=api_key)
        except ImportError:
            raise ImportError("请安装google-genai: pip install google-genai")

    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用Gemini API"""
        try:
            full_input = self._build_full_input(prompt, input_data)

            # Map a max-tokens hint onto the new SDK's config object if present.
            config = None
            max_tokens = kwargs.get("max_tokens") or kwargs.get("max_output_tokens")
            if max_tokens:
                from google.genai import types
                config = types.GenerateContentConfig(max_output_tokens=max_tokens)

            model = self.request_model()
            from backend.core.llm_degrade import consume_chunk_call
            from backend.core.llm_stream import StreamRejected, collect_sdk, exception_rejects_stream
            method = getattr(self.client.models, "generate_content_stream", None)
            if method is not None:
                try:
                    collected = collect_sdk(method(model=model, contents=full_input, config=config))
                    return LLMResponse(
                        content=collected.content if collected.content is not None else "",
                        model=model,
                        finish_reason=collected.finish_reason,
                    )
                except StreamRejected as rejected:
                    if not consume_chunk_call():
                        raise rejected.error
                    logger.info("上游不接受 stream，改回整包响应再试一次")
                except Exception as error:  # noqa: BLE001 - only a stream refusal falls back
                    if not exception_rejects_stream(error):
                        raise
                    if not consume_chunk_call():
                        raise
                    logger.info("上游不接受 stream，改回整包响应再试一次")
            response = self.client.models.generate_content(
                model=model,
                contents=full_input,
                config=config,
            )

            return LLMResponse(
                content=response.text,
                model=model,
                finish_reason=getattr(response, 'finish_reason', None)
            )

        except Exception as e:
            from backend.core.job_budget import promote_if_budget_spent
            promote_if_budget_spent(e)
            logger.error(f"Gemini调用失败: {sanitize_exception_text(e)}")
            raise log_safe_exception(e) from None
    
    def test_connection(self) -> bool:
        """测试Gemini连接"""
        try:
            # 使用简单的测试提示
            response = self.call("测试", max_tokens=10)
            # 检查响应是否有效
            if response and str(response.content or "").strip():
                return True
            return False
        except Exception as e:
            logger.error(f"Gemini连接测试失败: {sanitize_exception_text(e)}")
            return False
    
    def get_available_models(self) -> List[ModelInfo]:
        """获取Gemini可用模型（内置常用名单；设置页会再按账号实时拉取）"""
        return _catalog_model_infos(ProviderType.GEMINI)

class SiliconFlowProvider(LLMProvider):
    """硅基流动提供商"""
    
    def __init__(self, api_key: str, model_name: str = "Qwen/Qwen2.5-7B-Instruct", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        self.base_url = "https://api.siliconflow.cn/v1"
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用硅基流动API"""
        try:
            full_input = self._build_full_input(prompt, input_data)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            model = self.request_model()
            data = {
                "model": model,
                "messages": [{"role": "user", "content": full_input}],
                **{key: value for key, value in kwargs.items() if key != "stream"},
            }
            # Same idle cap as the other text calls, shortened while a clip job is running.
            from backend.core.llm_stream import post_chat_completion
            timeout = _http_timeout(LLM_READ_TIMEOUT_SEC)
            collected = post_chat_completion(
                f"{self.base_url}/chat/completions",
                headers=headers,
                payload=data,
                timeout=timeout,
                refresh_timeout=lambda: _http_timeout(LLM_READ_TIMEOUT_SEC),
            )
            
            return LLMResponse(
                content=collected.content,
                usage=collected.usage,
                model=model,
                finish_reason=collected.finish_reason,
            )
            
        except Exception as e:
            from backend.core.job_budget import promote_if_budget_spent
            promote_if_budget_spent(e)
            logger.error(f"硅基流动调用失败: {sanitize_exception_text(e)}")
            raise log_safe_exception(e) from None
    
    def test_connection(self) -> bool:
        """测试硅基流动连接"""
        try:
            # 使用简单的测试提示
            response = self.call("测试", max_tokens=10)
            # 检查响应是否有效
            if response and str(response.content or "").strip():
                return True
            return False
        except Exception as e:
            logger.error(f"硅基流动连接测试失败: {sanitize_exception_text(e)}")
            return False
    
    def get_available_models(self) -> List[ModelInfo]:
        """获取硅基流动可用模型（内置常用名单；设置页会再按账号实时拉取）"""
        return _catalog_model_infos(ProviderType.SILICONFLOW)

class LLMProviderFactory:
    """LLM提供商工厂"""
    
    _providers = {
        ProviderType.DASHSCOPE: DashScopeProvider,
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.GEMINI: GeminiProvider,
        ProviderType.SILICONFLOW: SiliconFlowProvider,
    }
    
    @classmethod
    def create_provider(cls, provider_type: ProviderType, api_key: str, model_name: str, **kwargs) -> LLMProvider:
        """创建提供商实例"""
        if provider_type not in cls._providers:
            raise ValueError(f"不支持的提供商类型: {provider_type}")
        
        provider_class = cls._providers[provider_type]
        return provider_class(api_key, model_name, **kwargs)
    
    @classmethod
    def get_all_available_models(cls) -> Dict[ProviderType, List[ModelInfo]]:
        """获取所有提供商的可用模型"""
        models = {}
        for provider_type, provider_class in cls._providers.items():
            try:
                # 创建临时实例来获取模型列表
                temp_provider = provider_class("dummy_key", "dummy_model")
                models[provider_type] = temp_provider.get_available_models()
            except Exception as e:
                logger.warning(f"无法获取{provider_type.value}的模型列表: {sanitize_exception_text(e)}")
                models[provider_type] = []
        return models
