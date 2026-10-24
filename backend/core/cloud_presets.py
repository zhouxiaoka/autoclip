"""
云端 OpenAI 兼容预设：DeepSeek / Seed / Kimi / GLM / Grok / Infistar / 88API / APIMart（赞助）。

底层仍是 openai + 官方 base_url，和 Ollama 预设同一套路，但必须带各家自己的 key，
不能复用用户的 OpenAI key。设置页、CLI、MCP 都用 `--provider deepseek` 这种名字。

产品语义（地址、默认模型、显示名）来自 ``backend/presets/provider_presets.json``。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from backend.core.provider_presets import get_catalog, get_provider, resolve_provider_id


@dataclass(frozen=True)
class CloudPreset:
    key: str
    display_name: str
    base_url: str
    default_model: str
    api_key_setting: str
    docs_url: str
    hint: str


def _cloud_presets() -> Dict[str, CloudPreset]:
    return {
        item.id: CloudPreset(
            key=item.id,
            display_name=item.display_name,
            base_url=item.base_url,
            default_model=item.default_model,
            api_key_setting=item.api_key_setting,
            docs_url=item.docs_url,
            hint=item.cloud_hint,
        )
        for item in get_catalog().providers.values()
        if item.openai_compat_remap
    }


CLOUD_PRESETS: Dict[str, CloudPreset] = _cloud_presets()

# Official 88API host lives in the JSON catalog. Saved configs may still use the
# previous host; both stay valid. Do not rewrite a stored URL to the new host.
_api88 = get_provider("api88")
API88_HOSTS = frozenset(_api88.accepted_hosts if _api88 else ())


def is_api88_host(host: Optional[str]) -> bool:
    return (host or "").lower() in API88_HOSTS


def normalize_cloud_preset_key(name: Optional[str]) -> Optional[str]:
    key = resolve_provider_id(name)
    return key if key in CLOUD_PRESETS else None


def resolve_cloud_preset(provider: Optional[str], base_url: Optional[str] = None) -> Optional[Tuple[str, str, CloudPreset]]:
    """
    若 provider 是 deepseek / seed / kimi / glm / grok / infistar / api88（或别名），返回 (openai, base_url, preset)。
    不是云端预设则返回 None。
    """
    key = normalize_cloud_preset_key(provider)
    if not key:
        return None
    preset = CLOUD_PRESETS[key]
    return "openai", (base_url or "").strip() or preset.base_url, preset


def cloud_preset_display_name(key: Optional[str]) -> Optional[str]:
    p = CLOUD_PRESETS.get(key or "")
    return p.display_name if p else None
