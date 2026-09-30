"""
云端 LLM 模型目录：内置常用名单 + 向服务商实时拉取。

设置页下拉以前写死在前端，型号过几个月就过时。这里把「常用别名」和
「账号此刻能用的型号」分开：没密钥时也能选到稳定别名；填了密钥就打
各家 `/models`，把最新列表合并进来。
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 各家仍在维护的稳定别名 / 旗舰型号。实时列表失败时用这份，也作为下拉靠前的常用项。
# 日期以 2026-09 公开文档为准；具体可用性以账号权限为准。
CURATED_MODELS: Dict[str, List[str]] = {
    "dashscope": [
        "qwen3.8-max",
        "qwen3.8-flash",
        "qwen3.7-plus",
        "qwen-plus",
        "qwen-plus-latest",
        "qwen-max",
        "qwen-max-latest",
        "qwen-flash",
        # 多模态：能看画面，视觉分析 / 封面校对用
        "qwen-vl-max",
        "qwen-vl-plus",
    ],
    "openai": [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
    ],
    "gemini": [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
    ],
    "deepseek": [
        "deepseek-flash",
        "deepseek-v4-pro",
    ],
    "seed": [
        "doubao-seed-2-1-lite-260915",
        "doubao-seed-2-1-pro-260915",
        "doubao-seed-2-1-turbo-260628",
        "doubao-seed-evolving",
    ],
    "kimi": [
        "kimi-k3",
        "kimi-k2.6",
        "kimi-k2.5",
        "kimi-k2.7-code",
    ],
    "glm": [
        "glm-5.3",
        "glm-5.2",
        "glm-4.7",
    ],
    "grok": [
        "grok-4.6",
        "grok-4.5",
        "grok-4.3",
    ],
    # 多模型网关，型号随账号而定：不内置名单，填好 key 后实时拉取
    "infistar": [],
    "api88": [],
}

DEFAULT_MODELS: Dict[str, str] = {
    "dashscope": "qwen-plus",
    "openai": "gpt-5-mini",
    "gemini": "gemini-3.8-flash",
    "deepseek": "deepseek-flash",
    "seed": "doubao-seed-2-1-lite-260915",
    "kimi": "kimi-k2.6",
    "glm": "glm-5.3",
    "grok": "grok-4.6",
    "infistar": "",
    "api88": "",
}

PROVIDER_LABELS: Dict[str, str] = {
    "dashscope": "通义千问",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "deepseek": "DeepSeek",
    "seed": "Seed",
    "kimi": "Kimi",
    "glm": "GLM",
    "grok": "Grok",
    "infistar": "Infistar",
    "api88": "88API",
}

CLOUD_PROVIDERS = frozenset(CURATED_MODELS)

# ---- 模型能力：设置页在下拉里标「多模态 / 仅文字」，视觉分析和封面校对据此决定能不能看画面 ----
# 只收录能确认支持图片输入的系列；认不出来的按仅文字处理（宁可少用视觉，也不在不支持的模型上白花钱报错）
_VISION_MARKERS = (
    "gpt-4o", "gpt-4.1", "gpt-5", "o3", "o4-",
    "gemini", "claude",
    "-vl", "vl-", "qvq", "qwen-omni", "qwen3-omni",
    "vision", "doubao-seed", "seed-1.6", "seed-2",
    "grok-4", "llava", "minicpm-v", "llama3.2-vision", "gemma3",
    "glm-4v", "glm-4.1v", "glm-4.5v", "glm-5v",
    "kimi-k2.6", "kimi-k3", "kimi-vl", "kimi-latest",
)
_TEXT_ONLY_MARKERS = ("deepseek", "-code", "coder", "embedding", "-instruct-text")


def supports_vision(model: str) -> bool:
    name = (model or "").strip().lower()
    # Explicitly verified official model IDs; these no longer carry a -vl suffix.
    if name in {'qwen3.8-max', 'qwen3.8-flash'}:
        return True
    if not name or any(m in name for m in _TEXT_ONLY_MARKERS):
        return False
    return any(m in name for m in _VISION_MARKERS)


# ---- 封面生图：跟着文本模型的服务商走，同一个 key ----
# 这里只是下拉的常用项；填好 key 后再合并账号 /models 里实时拉到的生图型号，用户也可以直接输入模型 ID。
# 不在表里的服务商（DeepSeek / Kimi / GLM / Grok / 本地）目前没有接入生图接口，封面用视频截帧。
IMAGE_MODELS: Dict[str, List[str]] = {
    "dashscope": ["wanx2.1-t2i-turbo", "wanx2.1-t2i-plus"],
    "seed": ["doubao-seedream-5-0-260128"],
    "openai": ["gpt-image-1"],
    "api88": ["gpt-image-1", "dall-e-3", "dall-e-2"],
    # Infistar 是多模型网关，主流生图模型都能调，具体以账号可用型号为准
    "infistar": ["gpt-image-1", "dall-e-3", "doubao-seedream-5-0-260128", "flux-1.1-pro", "imagen-4", "wanx2.1-t2i-turbo"],
}
_IMAGE_MARKERS = ("gpt-image", "dall-e", "seedream", "wanx", "flux", "imagen", "t2i", "midjourney", "ideogram",
                  "recraft", "stable-diffusion", "sdxl", "sd3", "kolors", "cogview", "hunyuan-image", "qwen-image")


def is_image_model(model: str) -> bool:
    name = (model or "").lower()
    return any(m in name for m in _IMAGE_MARKERS)

# 切片分析只要对话模型；嵌入 / 语音 / 图像 / 视频会把下拉撑得没法用
_SKIP_SUBSTR = (
    "embedding",
    "embed-",
    "-embed",
    "text-embedding",
    "rerank",
    "moderation",
    "whisper",
    "transcribe",
    "tts",
    "asr",
    "dall-e",
    "dalle",
    "gpt-image",
    "imagen",
    "image-",
    "wanx",
    "wan2",
    "video",
    "veo",
    "sora",
    "realtime",
    "live-audio",
    "audio-preview",
    "search-preview",
    "seedream",
    "seedance",
    "-image",
    "-live",
)

_OPENAI_CHAT_PREFIXES = (
    "gpt-",
    "o1",
    "o3",
    "o4",
    "chatgpt-",
)

_DATED_SNAPSHOT = re.compile(r"^(.+)-(?:\d{4}-\d{2}-\d{2}|\d{8})$")

SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_CACHE_TTL_SECONDS = 300.0
_cache: Dict[Tuple[str, str, str], Tuple[float, List[str]]] = {}


@dataclass
class ModelListResult:
    provider: str
    source: str  # catalog | live
    reachable: bool
    default_model: str
    models: List[str]
    catalog: Dict[str, List[str]] = field(default_factory=dict)
    error: Optional[str] = None
    image_models: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        payload = {
            "provider": self.provider,
            "source": self.source,
            "reachable": self.reachable,
            "default_model": self.default_model,
            "models": self.models,
            "catalog": self.catalog,
            # 下拉里哪些是多模态；没列出的按仅文字
            "vision_models": [m for m in self.models if supports_vision(m)],
            # 这个服务商能不能生封面、可选哪些生图模型（空 = 用视频截帧）
            "image_models": self.image_models,
        }
        if self.error:
            payload["error"] = self.error
        return payload


def curated_models(provider: Optional[str] = None) -> List[str]:
    if not provider:
        return [name for names in CURATED_MODELS.values() for name in names]
    return list(CURATED_MODELS.get(provider, []))


def default_model_for(provider: str) -> str:
    return DEFAULT_MODELS.get(provider, "qwen-plus")


def is_chat_model(name: str, provider: str = "", official: bool = True) -> bool:
    """过滤掉嵌入 / 语音 / 生图等非对话型号。自建兼容接口不过滤前缀，只去掉明显非文本项。"""
    raw = (name or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    if any(token in lowered for token in _SKIP_SUBSTR):
        return False
    if provider == "openai" and official:
        return lowered.startswith(_OPENAI_CHAT_PREFIXES)
    if provider == "gemini":
        return "gemini" in lowered
    return True


def drop_dated_snapshots(names: Iterable[str], known: Optional[Iterable[str]] = None) -> List[str]:
    """有 `gpt-5` 时丢掉 `gpt-5-2025-08-07` 这种日期快照，下拉更干净。"""
    items = [n for n in names if n]
    bases = set(items)
    if known:
        bases.update(n for n in known if n)
    kept: List[str] = []
    for name in items:
        match = _DATED_SNAPSHOT.match(name)
        if match and match.group(1) in bases:
            continue
        kept.append(name)
    return kept


def merge_models(curated: Iterable[str], live: Iterable[str]) -> List[str]:
    """常用别名靠前，实时多出来的型号接在后面（去掉日期快照）。"""
    seen = set()
    out: List[str] = []
    for name in curated:
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    extras = drop_dated_snapshots((name for name in live if name and name not in seen), known=seen)
    for name in extras:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _cache_key(provider: str, base_url: str, api_key: str) -> Tuple[str, str, str]:
    fingerprint = f"{len(api_key)}:{api_key[:4]}:{api_key[-2:]}" if api_key else ""
    return (provider, base_url, fingerprint)


def _cache_get(key: Tuple[str, str, str]) -> Optional[List[str]]:
    hit = _cache.get(key)
    if not hit:
        return None
    ts, models = hit
    if time.monotonic() - ts > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return list(models)


def _cache_set(key: Tuple[str, str, str], models: List[str]) -> None:
    _cache[key] = (time.monotonic(), list(models))


def clear_model_list_cache() -> None:
    _cache.clear()


def _extract_openai_model_ids(payload) -> List[str]:
    items = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []
    names = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("id") or item.get("name")
            if name:
                names.append(str(name))
        elif isinstance(item, str):
            names.append(item)
    return names


def _extract_gemini_model_ids(payload: dict) -> List[str]:
    names = []
    for item in payload.get("models") or []:
        if not isinstance(item, dict):
            continue
        methods = item.get("supportedGenerationMethods") or item.get("supported_generation_methods") or []
        if methods and "generateContent" not in methods:
            continue
        name = str(item.get("name") or "")
        if name.startswith("models/"):
            name = name[len("models/"):]
        if name:
            names.append(name)
    return names


async def _http_get_json(url: str, *, headers: Optional[dict] = None, params: Optional[dict] = None, trust_env: bool = True):
    import httpx
    async with httpx.AsyncClient(timeout=8.0, trust_env=trust_env) as client:
        resp = await client.get(url, headers=headers or {}, params=params)
        resp.raise_for_status()
        return resp.json()


async def fetch_openai_compatible_models(base_url: str, api_key: str) -> List[str]:
    from backend.core.llm_providers import OPENAI_COMPATIBLE_PLACEHOLDER_KEY, is_local_url, normalize_base_url

    url = normalize_base_url(base_url)
    if not url:
        raise ValueError("缺少 base_url")
    headers = {"Authorization": f"Bearer {api_key or OPENAI_COMPATIBLE_PLACEHOLDER_KEY}"}
    data = await _http_get_json(f"{url}/models", headers=headers, trust_env=not is_local_url(url))
    return _extract_openai_model_ids(data)


async def fetch_gemini_models(api_key: str) -> List[str]:
    if not api_key:
        raise ValueError("缺少 Gemini API Key")
    names: List[str] = []
    params: dict = {"key": api_key, "pageSize": 200}
    while True:
        data = await _http_get_json(GEMINI_MODELS_URL, params=params)
        if not isinstance(data, dict):
            break
        names.extend(_extract_gemini_model_ids(data))
        token = data.get("nextPageToken")
        if not token:
            break
        params = {**params, "pageToken": token}
    return names


def _official_base_url(provider: str, base_url: str) -> str:
    from backend.core.llm_providers import (
        DASHSCOPE_CN_COMPATIBLE_BASE_URL,
        OPENAI_OFFICIAL_BASE_URL,
        normalize_base_url,
    )

    url = normalize_base_url(base_url)
    if provider == "dashscope":
        return url or DASHSCOPE_CN_COMPATIBLE_BASE_URL
    if provider == "openai":
        return url or OPENAI_OFFICIAL_BASE_URL
    if provider == "siliconflow":
        return url or SILICONFLOW_BASE_URL
    from backend.core.cloud_presets import CLOUD_PRESETS
    if provider in CLOUD_PRESETS:
        return url or CLOUD_PRESETS[provider].base_url
    return url


def _is_official_openai(base_url: str) -> bool:
    from backend.core.llm_providers import OPENAI_OFFICIAL_BASE_URL, normalize_base_url
    url = normalize_base_url(base_url)
    return not url or url == OPENAI_OFFICIAL_BASE_URL


async def fetch_live_models(provider: str, api_key: str = "", base_url: str = "") -> List[str]:
    if provider == "gemini":
        return await fetch_gemini_models(api_key)
    url = _official_base_url(provider, base_url)
    return await fetch_openai_compatible_models(url, api_key)


def should_fetch_live(provider: str, api_key: str, base_url: str) -> bool:
    """官方接口没密钥就别打（会 401）；自建兼容地址可以空 key 试一下。"""
    if provider not in CLOUD_PROVIDERS:
        return False
    if api_key.strip():
        return True
    from backend.core.llm_providers import OPENAI_OFFICIAL_BASE_URL, normalize_base_url
    if provider == "openai":
        url = normalize_base_url(base_url)
        return bool(url) and url != OPENAI_OFFICIAL_BASE_URL
    return False


async def list_available_models(
    provider: str = "",
    api_key: str = "",
    base_url: str = "",
    refresh: bool = False,
) -> ModelListResult:
    """
    返回某个提供商的下拉名单。

    - 没密钥 / 拉取失败：内置常用名单（source=catalog）
    - 拉取成功：常用别名 + 账号实时型号（source=live）
    """
    key = (provider or "").strip().lower() or "dashscope"
    catalog = {name: list(models) for name, models in CURATED_MODELS.items()}
    curated = curated_models(key if key in CURATED_MODELS else None) if key in CURATED_MODELS else []
    result = ModelListResult(
        provider=key,
        source="catalog",
        reachable=False,
        default_model=default_model_for(key),
        # 已知提供商内置名单为空（如 infistar）时保持为空，别拿通义的型号冒充
        models=curated if key in CURATED_MODELS else curated_models("dashscope"),
        image_models=list(IMAGE_MODELS.get(key, [])),
        catalog=catalog,
    )

    if key not in CLOUD_PROVIDERS or not should_fetch_live(key, api_key, base_url):
        return result

    cache_key = _cache_key(key, base_url, api_key)
    official = key != "openai" or _is_official_openai(base_url)

    def apply(raw: List[str]) -> ModelListResult:
        # 缓存原始名单：对话模型进下拉，生图模型进封面生图选项
        if result.image_models:
            result.image_models = merge_models(result.image_models, [n for n in raw if is_image_model(n)])
        result.source = "live"
        result.reachable = True
        result.models = merge_models(curated, [n for n in raw if is_chat_model(n, key, official=official)])
        return result

    cached = None if refresh else _cache_get(cache_key)
    if cached is not None:
        return apply(cached)

    try:
        live = await fetch_live_models(key, api_key=api_key, base_url=base_url)
        _cache_set(cache_key, live)
        return apply(live)
    except Exception as exc:  # noqa: BLE001
        logger.info("拉取 %s 模型列表失败: %s", key, exc)
        result.error = str(exc)[:200]
        return result
