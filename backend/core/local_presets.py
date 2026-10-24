"""
本地模型预设（Ollama / LM Studio）。

底层都是 OpenAI 兼容接口（provider=openai + base_url），这里只是把「provider 名 → 默认地址 /
默认模型 / 显示名」固化下来，让设置页、CLI、MCP 都能用 `--provider ollama` 这种说法，
而不用记本机默认端口。

设置文件里允许把 `api_provider` 直接写成 `ollama` / `lmstudio`；`LLMManager` 加载时通过
`resolve_provider()` 还原成 openai + base_url。

产品语义来自 ``backend/presets/provider_presets.json``。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from backend.core.provider_presets import get_catalog, resolve_provider_id


@dataclass(frozen=True)
class LocalPreset:
    key: str
    display_name: str
    base_url: str
    default_model: str
    docs_url: str
    hint: str
    context_hint: str = ""


def _local_presets() -> Dict[str, LocalPreset]:
    return {
        item.id: LocalPreset(
            key=item.id,
            display_name=item.display_name,
            base_url=item.base_url,
            default_model=item.default_model,
            docs_url=item.docs_url,
            hint=item.hint,
            context_hint=item.context_hint,
        )
        for item in get_catalog().providers.values()
        if item.local_compat_remap
    }


LOCAL_PRESETS: Dict[str, LocalPreset] = _local_presets()

# 本机 / 局域网的其它 OpenAI 兼容服务（vLLM、llama.cpp server …）用这条通用提示。
LOCAL_CONTEXT_HINT = get_catalog().local_context_hint


def normalize_preset_key(name: Optional[str]) -> Optional[str]:
    """返回规范化的预设 key；不是预设则返回 None。"""
    key = resolve_provider_id(name)
    return key if key in LOCAL_PRESETS else None


def resolve_provider(provider: Optional[str], base_url: Optional[str] = None) -> Tuple[str, str, Optional[str]]:
    """
    把用户写的 provider（可能是 `ollama` / `lmstudio`）还原为真正的 provider 与 base_url。

    返回 (provider_value, base_url, preset_key)。非预设时原样返回 (provider, base_url or "", None)。
    """
    preset_key = normalize_preset_key(provider)
    if not preset_key:
        return (provider or "dashscope").strip().lower(), (base_url or "").strip(), None
    preset = LOCAL_PRESETS[preset_key]
    return "openai", (base_url or "").strip() or preset.base_url, preset_key


def is_local_model(settings: Mapping[str, Any]) -> bool:
    """当前分析模型是否跑在本机 / 局域网（本地预设、ollama / lmstudio 连接，或指向本地地址的兼容接口）。

    本地服务的上下文通常很小，长字幕要切小块（pipeline/clip_finder.py）。云端服务一律返回 False。
    """
    if normalize_preset_key(settings.get("llm_provider_preset")) or normalize_preset_key(settings.get("connection_provider")):
        return True
    if str(settings.get("llm_provider") or "").lower() != "openai":
        return False
    from backend.core.llm_providers import is_local_url
    return is_local_url(settings.get("openai_base_url"))


def context_hint_for(settings: Mapping[str, Any]) -> str:
    """本地模型的上下文提示（预设自己的，或通用的一条）；云端返回空串。"""
    if not is_local_model(settings):
        return ""
    preset = LOCAL_PRESETS.get(normalize_preset_key(settings.get("llm_provider_preset"))
                               or normalize_preset_key(settings.get("connection_provider")) or "")
    return preset.context_hint if preset and preset.context_hint else LOCAL_CONTEXT_HINT


def preset_display_name(preset_key: Optional[str]) -> Optional[str]:
    p = LOCAL_PRESETS.get(preset_key or "")
    return p.display_name if p else None


def presets_as_dicts() -> list[dict]:
    return [
        {
            "key": p.key,
            "display_name": p.display_name,
            "base_url": p.base_url,
            "default_model": p.default_model,
            "docs_url": p.docs_url,
            "hint": p.hint,
            "context_hint": p.context_hint,
        }
        for p in LOCAL_PRESETS.values()
    ]
