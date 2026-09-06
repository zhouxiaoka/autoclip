"""
本地模型预设（Ollama / LM Studio）。

底层都是 OpenAI 兼容接口（provider=openai + base_url），这里只是把「provider 名 → 默认地址 /
默认模型 / 显示名」固化下来，让设置页、CLI、MCP 都能用 `--provider ollama` 这种说法，
而不用记 `http://localhost:11434/v1`。

设置文件里允许把 `api_provider` 直接写成 `ollama` / `lmstudio`；`LLMManager` 加载时通过
`resolve_provider()` 还原成 openai + base_url。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class LocalPreset:
    key: str
    display_name: str
    base_url: str
    default_model: str
    docs_url: str
    hint: str


LOCAL_PRESETS: Dict[str, LocalPreset] = {
    "ollama": LocalPreset(
        key="ollama",
        display_name="Ollama（本地）",
        base_url="http://localhost:11434/v1",
        default_model="qwen2.5:7b",
        docs_url="https://ollama.com/download",
        hint="本机运行 Ollama 后即可用，无需密钥。推荐 `ollama pull qwen2.5:7b`（中文字幕分析效果稳定）。",
    ),
    "lmstudio": LocalPreset(
        key="lmstudio",
        display_name="LM Studio（本地）",
        base_url="http://localhost:1234/v1",
        default_model="",
        docs_url="https://lmstudio.ai",
        hint="在 LM Studio 里加载模型并启动 Local Server（默认端口 1234），模型名以服务端列出的为准。",
    ),
}

# 兼容常见写法
_ALIASES = {"lm-studio": "lmstudio", "lm_studio": "lmstudio", "local": "ollama"}


def normalize_preset_key(name: Optional[str]) -> Optional[str]:
    """返回规范化的预设 key；不是预设则返回 None。"""
    if not name:
        return None
    key = name.strip().lower()
    key = _ALIASES.get(key, key)
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
        }
        for p in LOCAL_PRESETS.values()
    ]
