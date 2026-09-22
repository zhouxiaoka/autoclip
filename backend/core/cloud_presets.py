"""
云端 OpenAI 兼容预设：DeepSeek / Kimi / GLM / Grok。

底层仍是 openai + 官方 base_url，和 Ollama 预设同一套路，但必须带各家自己的 key，
不能复用用户的 OpenAI key。设置页、CLI、MCP 都用 `--provider deepseek` 这种名字。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class CloudPreset:
    key: str
    display_name: str
    base_url: str
    default_model: str
    api_key_setting: str
    docs_url: str
    hint: str


CLOUD_PRESETS: Dict[str, CloudPreset] = {
    "deepseek": CloudPreset(
        key="deepseek",
        display_name="DeepSeek",
        base_url="https://api.deepseek.com",
        default_model="deepseek-flash",
        api_key_setting="deepseek_api_key",
        docs_url="https://platform.deepseek.com/api_keys",
        hint="DeepSeek 官方。国内直连，deepseek-flash 是当前 V4.1。",
    ),
    "kimi": CloudPreset(
        key="kimi",
        display_name="Kimi（月之暗面）",
        base_url="https://api.moonshot.cn/v1",
        default_model="kimi-k2.6",
        api_key_setting="kimi_api_key",
        docs_url="https://platform.moonshot.cn/console/api-keys",
        hint="月之暗面 Kimi。国内直连，适合长字幕分析。",
    ),
    "glm": CloudPreset(
        key="glm",
        display_name="智谱 GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-5.3",
        api_key_setting="glm_api_key",
        docs_url="https://open.bigmodel.cn/usercenter/apikeys",
        hint="智谱开放平台。国内直连，glm-5.3 是当前旗舰。",
    ),
    "grok": CloudPreset(
        key="grok",
        display_name="Grok（xAI）",
        base_url="https://api.x.ai/v1",
        default_model="grok-4.6",
        api_key_setting="grok_api_key",
        docs_url="https://console.x.ai",
        hint="xAI Grok。需要 xAI 账号。",
    ),
}

_ALIASES = {
    "deepseek-ai": "deepseek",
    "moonshot": "kimi",
    "moonshotai": "kimi",
    "kimi-k2": "kimi",
    "zhipu": "glm",
    "zhipuai": "glm",
    "bigmodel": "glm",
    "xai": "grok",
    "x-ai": "grok",
}


def normalize_cloud_preset_key(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    key = name.strip().lower()
    key = _ALIASES.get(key, key)
    return key if key in CLOUD_PRESETS else None


def resolve_cloud_preset(provider: Optional[str], base_url: Optional[str] = None) -> Optional[Tuple[str, str, CloudPreset]]:
    """
    若 provider 是 deepseek / kimi / glm / grok（或别名），返回 (openai, base_url, preset)。
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
