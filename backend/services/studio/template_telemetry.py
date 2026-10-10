"""Enumerable facts for HTML template renders.

Only enums, booleans, counts and random telemetry ids leave this helper.
Paths, titles, captions and free-text reasons are dropped.
"""
from __future__ import annotations

import re

TEMPLATES = ('editorial', 'street', 'classic', 'interview_zh', 'podcast_en', 'landscape', 'none')
ENCODERS = ('libx264', 'h264_nvenc', 'h264_qsv', 'h264_amf', 'h264_videotoolbox')
DOWNGRADE_REASONS = ('none', 'over_budget', 'missing_runtime', 'intel_mac_unverified', 'rank', 'flag_off')
FAILURE_REASONS = ('none', 'capture', 'encode', 'runtime', 'timeout', 'unknown')
OPERATING_SYSTEMS = ('darwin', 'win32', 'linux')
OUTCOMES = ('completed', 'downgraded', 'failed')
OVERRIDE_STAGES = ('pre_import', 'results_chip', 'editor')
_TOKEN = re.compile(r'^t-[a-z0-9-]{10,100}$')


def _enum(value: object, allowed: tuple[str, ...]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


def _count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0 or value > 1024:
        return None
    return value


def _millis(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0 or value > 3_600_000:
        return None
    return value


def render_event(payload: dict | None) -> dict:
    """`studio_template_render_finished` properties. Unknown keys never pass through."""
    raw = payload or {}
    event = {
        'template': _enum(raw.get('template'), TEMPLATES),
        'encoder': _enum(raw.get('encoder'), ENCODERS),
        'downgraded': raw.get('downgraded') if isinstance(raw.get('downgraded'), bool) else None,
        'downgrade_reason': _enum(raw.get('downgrade_reason'), DOWNGRADE_REASONS),
        'os': _enum(raw.get('os'), OPERATING_SYSTEMS),
        'cpu_count': _count(raw.get('cpu_count')),
        'duration_ms': _millis(raw.get('duration_ms')),
        'failure_reason': _enum(raw.get('failure_reason'), FAILURE_REASONS),
        'outcome': _enum(raw.get('outcome'), OUTCOMES),
        'strategy_id': _enum(raw.get('strategy_id'), (
            'douyin', 'tiktok', 'instagram_reels', 'youtube_shorts', 'youtube_long',
            'bilibili', 'xiaohongshu', 'original',
        )),
    }
    flow_id = raw.get('flow_id')
    if isinstance(flow_id, str) and _TOKEN.match(flow_id):
        event['flow_id'] = flow_id
    return {key: value for key, value in event.items() if value is not None}


def override_event(payload: dict | None) -> dict:
    """`studio_template_overridden` properties."""
    raw = payload or {}
    event = {
        'from_template': _enum(raw.get('from_template'), TEMPLATES),
        'to_template': _enum(raw.get('to_template'), TEMPLATES),
        'stage': _enum(raw.get('stage'), OVERRIDE_STAGES),
    }
    flow_id = raw.get('flow_id')
    if isinstance(flow_id, str) and _TOKEN.match(flow_id):
        event['flow_id'] = flow_id
    return {key: value for key, value in event.items() if value is not None}
