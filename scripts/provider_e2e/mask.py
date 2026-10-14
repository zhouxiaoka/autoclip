"""Redact secrets from logs, reports and workspace dumps before they leave the runner."""
from __future__ import annotations

import re
from typing import Any

_KEY = re.compile(
    r'(?i)(?:api[_-]?key|authorization|bearer|token|secret)["\s:=]+([^\s"\']{8,})'
)
_SK = re.compile(r'(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{8,}')
_BEARER = re.compile(r'(?i)bearer\s+[A-Za-z0-9._\-+/=]{8,}')


def redact_text(text: str, extras: list[str] | None = None) -> str:
    if not text:
        return text
    out = _BEARER.sub('Bearer ***', text)
    out = _SK.sub('sk-***', out)

    def hide(match: re.Match[str]) -> str:
        return match.group(0)[: match.start(1) - match.start(0)] + '***'

    out = _KEY.sub(hide, out)
    for extra in extras or []:
        if extra and extra not in ('sk-mock-e2e-not-a-secret',) and extra in out:
            out = out.replace(extra, '***')
    return out


def redact(value: Any, extras: list[str] | None = None) -> Any:
    if isinstance(value, str):
        return redact_text(value, extras)
    if isinstance(value, list):
        return [redact(item, extras) for item in value]
    if isinstance(value, dict):
        hidden = {}
        for key, item in value.items():
            if str(key).lower() in {'api_key', 'authorization', 'token', 'secret', 'password'}:
                hidden[key] = '***' if item else item
            else:
                hidden[key] = redact(item, extras)
        return hidden
    return value
