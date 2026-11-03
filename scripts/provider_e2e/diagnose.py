"""Pull HTTP status and UpstreamErrorType from workspace/logs. Never keep bodies or keys."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.core.llm_telemetry import sanitize_upstream_error_type
from backend.core.upstream_errors import classify_upstream_error

from .mask import redact_text

_STATUS = re.compile(r'(?:Error code|status(?:[_ ]code)?|HTTP)\D+(\d{3})\b', re.I)
_FAIL_LINE = re.compile(r'(OpenAI调用失败|Gemini调用失败|API调用失败|Error code:\s*\d{3}).*', re.I)


def http_status_of(value: Any) -> int | None:
    try:
        status = int(value)
    except (TypeError, ValueError):
        return None
    if 400 <= status <= 599:
        return status
    return None


def classify_http(status: int | None, blob: str | None = None) -> str | None:
    if status is None and not blob:
        return None
    classified = classify_upstream_error(status, blob)
    return sanitize_upstream_error_type(classified.error_type.value)


def excerpt(text: str, limit: int = 180) -> str:
    clean = redact_text(text or '')
    clean = re.sub(r'https?://[^\s]+', lambda match: match.group(0).split('/')[2], clean)
    return clean[:limit]


def from_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    generation = workspace.get('generation') or {}
    analysis = workspace.get('analysis') or {}
    status = (
        http_status_of(generation.get('http_status'))
        or http_status_of(analysis.get('http_status'))
    )
    blob = excerpt(str(generation.get('error') or analysis.get('error') or ''))
    return {
        'http_status': status,
        'error_class': classify_http(status, blob or None),
        'log_excerpt': blob or None,
    }


def from_backend_log(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {'http_status': None, 'error_class': None, 'log_excerpt': None}
    text = redact_text(path.read_text(encoding='utf-8', errors='replace'))
    statuses = [http_status_of(item) for item in _STATUS.findall(text)]
    status = next((item for item in reversed(statuses) if item), None)
    lines = [line.strip() for line in text.splitlines() if _FAIL_LINE.search(line)]
    snippet = excerpt(lines[-1]) if lines else None
    return {
        'http_status': status,
        'error_class': classify_http(status, snippet),
        'log_excerpt': snippet,
    }


def merge_diagnosis(*parts: dict[str, Any]) -> dict[str, Any]:
    out = {'http_status': None, 'error_class': None, 'log_excerpt': None}
    for part in parts:
        if not part:
            continue
        if out['http_status'] is None:
            out['http_status'] = part.get('http_status')
        if out['error_class'] is None:
            out['error_class'] = part.get('error_class')
        if out['log_excerpt'] is None:
            out['log_excerpt'] = part.get('log_excerpt')
    if out['http_status'] and not out['error_class']:
        out['error_class'] = classify_http(out['http_status'])
    return out
