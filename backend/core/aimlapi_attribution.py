"""
AI/ML API 归因请求头。

网关只有在请求带上这几个头时才会把调用计到 AutoClip 名下，所以它们要跟着每一次
打到 api.aimlapi.com 的请求走 —— 也只跟着这些请求走：同一个 `OpenAIProvider`
还服务 OpenRouter、Ollama、vLLM，把 partner id 发给第三方既不对也没用。

判定按「最终目标地址的主机名」做，只认 `api.aimlapi.com` 本身，不做后缀匹配
（`api.aimlapi.com.evil.tld` 不是我们）。
"""
from __future__ import annotations

from typing import Dict, Optional
from urllib.parse import urlparse

AIMLAPI_HOST = "api.aimlapi.com"
AIMLAPI_BASE_URL = "https://api.aimlapi.com/v1"

# 归因来源标识；格式 `agent/<slug>`，与 AI/ML API 侧登记的一致。
AIMLAPI_SOURCE = "agent/autoclip"
# 合作伙伴 ID 由 AI/ML API 侧随机生成后登记。留空表示「还没有」——
# 留空时不发这个头，而不是发一个不存在的值（未知 id 会被静默忽略）。
AIMLAPI_PARTNER_ID = "part_qVR4oZesx5sRaPUBvUjDQf7p"

_REFERER = "https://github.com/zhouxiaoka/autoclip"
_TITLE = "AutoClip"


def is_aimlapi_url(base_url: Optional[str]) -> bool:
    """base_url 是否指向 AI/ML API 网关。"""
    url = (base_url or "").strip()
    if not url:
        return False
    if "://" not in url:
        url = f"https://{url}"
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host == AIMLAPI_HOST


def aimlapi_headers(base_url: Optional[str]) -> Dict[str, str]:
    """打 AI/ML API 时返回归因请求头；其它地址返回空字典。"""
    if not is_aimlapi_url(base_url):
        return {}
    headers = {
        "HTTP-Referer": _REFERER,
        "X-Title": _TITLE,
        "X-AIMLAPI-Source": AIMLAPI_SOURCE,
    }
    if AIMLAPI_PARTNER_ID:
        headers["X-AIMLAPI-Partner-ID"] = AIMLAPI_PARTNER_ID
    return headers
