"""Fixed asset and provider matrix for the release provider-e2e gate.

Videos are generated at runtime (lavfi + SRT). Specs stay in-repo so CI does not
store large binaries; sha256 is recorded after generation.

``LIVE_PROVIDERS`` is the live e2e default source (chat URL, fallback model,
secret env, tier). The product catalog is not that source: Gemini's product
row is ``gemini-3.8-flash`` at ``/v1beta`` (native models), while live chat
needs ``/v1beta/openai``. DashScope live default is ``qwen-plus``. When
``backend/presets/provider_presets.json`` exists, this module reads labels and
chat URL inputs only, preserving live default models. It never writes the
product JSON. ``*_MODEL`` still overrides at run time. Do not print secrets.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from backend.core.provider_endpoint import locked_chat_url
from backend.core.upstream_errors import UpstreamErrorType

from .presets import load_catalog_providers, reset_catalog_cache


def reset_live_catalog() -> None:
    reset_catalog_cache()

# Success clips must be >= short-tier min_clip_sec (20s). Live material stays 1–2 min.
SUCCESS_DURATION_SEC = 70
TOO_SHORT_DURATION_SEC = 8
LIVE_MODES = ('nightly', 'prerelease', 'verify', 'api88')
NIGHTLY_PROVIDER_IDS = ('deepseek', 'gemini')
NIGHTLY_CLIP_IDS = ('talk_zh', 'with_srt', 'too_short')
VERIFY_PAID_PROVIDER_IDS = ('api88', 'dashscope', 'infistar')
VERIFY_PROBE_CLIP_ID = 'talk_zh'

ASSETS: tuple[dict[str, Any], ...] = (
    {
        'id': 'talk_zh',
        'label': '中文口播',
        'expect': 'succeed',
        'duration_sec': SUCCESS_DURATION_SEC,
        'width': 640,
        'height': 360,
        'color': '0x2C4A6E',
        'tone_hz': 440,
        'language': 'zh',
        'lines': (
            '今天想跟大家讲一个很具体的工作方法。',
            '先把问题写清楚，再决定要不要开工。',
            '很多失败其实不是执行差，而是目标含糊。',
            '写下一句可验证的完成标准，会少走很多弯路。',
            '如果你只能改一件事，就先改这一句标准。',
        ),
    },
    {
        'id': 'interview_zh',
        'label': '中文访谈',
        'expect': 'succeed',
        'duration_sec': SUCCESS_DURATION_SEC,
        'width': 640,
        'height': 360,
        'color': '0x3D5A3D',
        'tone_hz': 392,
        'language': 'zh',
        'lines': (
            '主持人：你当时为什么决定换一条路线？',
            '嘉宾：因为原来的指标只看速度，不看出错成本。',
            '主持人：那后来你们怎么衡量进展？',
            '嘉宾：每周只看三个数字，其他先放下。',
            '嘉宾：访谈里最重要的是把取舍说清楚。',
        ),
    },
    {
        'id': 'podcast_en',
        'label': '英文播客',
        'expect': 'succeed',
        'duration_sec': SUCCESS_DURATION_SEC,
        'width': 640,
        'height': 360,
        'color': '0x4A3D5A',
        'tone_hz': 349,
        'language': 'en',
        'lines': (
            'Host: What changed after you shipped the first version?',
            'Guest: We stopped optimizing for more features.',
            'Host: So the metric became completion, not activity.',
            'Guest: Right. One finished clip beats ten half starts.',
            'Guest: That is the whole lesson from this episode.',
        ),
    },
    {
        'id': 'with_srt',
        'label': '带字幕',
        'expect': 'succeed',
        'duration_sec': SUCCESS_DURATION_SEC,
        'width': 640,
        'height': 360,
        'color': '0x5A4A2C',
        'tone_hz': 330,
        'language': 'zh',
        'lines': (
            '这段素材自带字幕，用来确认转写被跳过。',
            '字幕时间戳必须能对上画面，不能空文件。',
            '分析阶段应直接读取 SRT，而不是再跑语音识别。',
            '只要字幕完整，短口播也可以切出可用片段。',
            '最后一句用来压住结尾，避免切点落空。',
        ),
    },
    {
        'id': 'portrait',
        'label': '竖屏',
        'expect': 'succeed',
        'duration_sec': SUCCESS_DURATION_SEC,
        'width': 360,
        'height': 640,
        'color': '0x2C5A5A',
        'tone_hz': 523,
        'language': 'zh',
        'lines': (
            '这是竖屏口播，主体在画面中间。',
            '原画导出时应保持竖向比例。',
            '不要因为画幅特殊就走视觉初筛。',
            '字幕路线对竖屏同样有效。',
            '结尾再重复一次主题，方便切出完整句。',
        ),
    },
    {
        'id': 'gameplay',
        'label': '游戏',
        'expect': 'succeed',
        'duration_sec': SUCCESS_DURATION_SEC,
        'width': 640,
        'height': 360,
        'pattern': 'testsrc',
        'tone_hz': 587,
        'language': 'zh',
        'lines': (
            '这一段是游戏操作说明，不是纯画面高光。',
            '先看小地图，再决定要不要交技能。',
            '走位比伤害更重要，别贪刀。',
            '团战前先报点，队友才能跟上。',
            '这局的结论：信息比操作更值钱。',
        ),
    },
    {
        'id': 'sport',
        'label': '体育',
        'expect': 'succeed',
        'duration_sec': SUCCESS_DURATION_SEC,
        'width': 640,
        'height': 360,
        'pattern': 'smptebars',
        'tone_hz': 659,
        'language': 'zh',
        'lines': (
            '下半场开始后节奏明显加快。',
            '边路传中之前先观察后点。',
            '这一次反击打得非常完整。',
            '门将的站位救了至少两个危险球。',
            '全场最值得看的就是这次由守转攻。',
        ),
    },
    {
        'id': 'music',
        'label': '纯音乐',
        'expect': 'succeed',
        'duration_sec': SUCCESS_DURATION_SEC,
        'width': 640,
        'height': 360,
        'color': '0x1A1A2E',
        'tone_hz': 220,
        'language': 'zh',
        'lines': (
            '这是一段带说明字幕的音乐素材。',
            '前奏先铺气氛，不要急着切高潮。',
            '副歌进入时画面可以换一个机位。',
            '间奏用来过渡，不要切得太碎。',
            '结尾渐弱，给成片一个完整收束。',
        ),
    },
    {
        'id': 'too_short',
        'label': '太短',
        'expect': 'block',
        'block_code': 'source_too_short',
        'duration_sec': TOO_SHORT_DURATION_SEC,
        'width': 640,
        'height': 360,
        'color': '0x662222',
        'tone_hz': 180,
        'language': 'zh',
        'attach_srt': False,
        'lines': ('这段只有几秒，按字幕切不出完整片段。',),
    },
    {
        'id': 'no_audio',
        'label': '无音轨',
        'expect': 'block',
        'block_code': 'source_no_audio',
        'duration_sec': SUCCESS_DURATION_SEC,
        'width': 640,
        'height': 360,
        'color': '0x333333',
        'tone_hz': None,
        'language': 'zh',
        'attach_srt': False,
        'lines': ('无音轨视频不应走到付费调用。',),
    },
)

LIVE_PROVIDERS: tuple[dict[str, Any], ...] = (
    {
        'id': 'api88',
        'label': '88API',
        'kind': 'live',
        'provider': 'api88',
        'secret': 'API88_API_KEY',
        'model_env': 'API88_MODEL',
        'default_model': 'deepseek-v4-flash',
        'base_url': 'https://api.88api.ai/v1',
        'vision_model_env': 'API88_VISION_MODEL',
        'tier': 'paid',
    },
    {
        'id': 'deepseek',
        'label': 'DeepSeek',
        'kind': 'live',
        'provider': 'deepseek',
        'secret': 'DEEPSEEK_API_KEY',
        'model_env': 'DEEPSEEK_MODEL',
        'default_model': 'deepseek-flash',
        'base_url': 'https://api.deepseek.com',
        'vision_model_env': 'DEEPSEEK_VISION_MODEL',
        'tier': 'cheap',
    },
    {
        'id': 'gemini',
        'label': 'Gemini',
        'kind': 'live',
        'provider': 'gemini',
        'secret': 'GEMINI_API_KEY',
        'model_env': 'GEMINI_MODEL',
        'default_model': 'gemini-3.5-flash-lite',
        'base_url': 'https://generativelanguage.googleapis.com/v1beta/openai',
        'vision_model_env': 'GEMINI_VISION_MODEL',
        'tier': 'free',
    },
    {
        'id': 'dashscope',
        'label': 'DashScope',
        'kind': 'live',
        'provider': 'dashscope',
        'secret': 'DASHSCOPE_API_KEY',
        'model_env': 'DASHSCOPE_MODEL',
        'default_model': 'qwen-plus',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'vision_model_env': 'DASHSCOPE_VISION_MODEL',
        'tier': 'paid',
    },
    {
        'id': 'infistar',
        'label': 'Infistar',
        'kind': 'live',
        'provider': 'infistar',
        'secret': 'INFISTAR_API_KEY',
        'model_env': 'INFISTAR_MODEL',
        'default_model': 'gpt-4o-mini',
        'base_url': 'https://infistar.ai/v1',
        'vision_model_env': 'INFISTAR_VISION_MODEL',
        'tier': 'paid',
    },
)

FAULTS: tuple[dict[str, Any], ...] = (
    {
        'id': 'rate_limited_429',
        'label': '429 Retry-After',
        'fault': '429',
        'expect': 'succeed',
        'upstream_error_type': UpstreamErrorType.RATE_LIMITED.value,
    },
    {
        'id': 'unavailable_503',
        'label': '503',
        'fault': '503',
        'expect': 'succeed',
        'upstream_error_type': UpstreamErrorType.UPSTREAM_UNAVAILABLE.value,
    },
    {
        'id': 'disconnect',
        'label': '断线',
        'fault': 'disconnect',
        'expect': 'succeed',
        'upstream_error_type': UpstreamErrorType.CONNECTION.value,
    },
    {
        'id': 'kill_backend',
        'label': '中途杀后端',
        'fault': 'kill',
        'expect': 'service_restarted',
        'upstream_error_type': None,
    },
)

MOCK_PROVIDER = {
    'id': 'mock',
    'label': '本地 mock OpenAI',
    'kind': 'mock',
    'provider': 'compatible',
    'model': 'mock-gpt',
    'api_key': 'sk-mock-e2e-not-a-secret',
}


def assets(*, expect: str | None = None) -> list[dict[str, Any]]:
    rows = [dict(item) for item in ASSETS]
    if expect is None:
        return rows
    return [item for item in rows if item['expect'] == expect]


def live_chat_url(provider_id: str, catalog_url: str = '', fallback: str = '') -> str:
    """Live chat root. Product Gemini is ``/v1beta``; e2e needs ``/openai``."""
    fallback = (fallback or '').strip()
    catalog_url = (catalog_url or '').strip()
    if provider_id == 'gemini':
        locked = locked_chat_url('gemini', catalog_url or fallback)
        return (locked or fallback or catalog_url).rstrip('/')
    return (fallback or catalog_url).rstrip('/')


def live_providers() -> list[dict[str, Any]]:
    catalog = load_catalog_providers()
    if catalog:
        missing = [item['id'] for item in LIVE_PROVIDERS if item['id'] not in catalog]
        if missing:
            raise KeyError(f'provider presets missing live e2e entries: {", ".join(missing)}')
    rows = []
    for item in LIVE_PROVIDERS:
        row = dict(item)
        preset = catalog.get(item['id'])
        catalog_url = ''
        if preset:
            row['label'] = preset['label'] or row['label']
            catalog_url = preset['base_url']
        row['base_url'] = live_chat_url(item['id'], catalog_url, item['base_url'])
        if not row['base_url']:
            raise ValueError(f'provider e2e {item["id"]} missing live chat url')
        rows.append(row)
    return rows


def faults() -> list[dict[str, Any]]:
    return [dict(item) for item in FAULTS]


def current_iso_week(today: dt.date | None = None) -> int:
    return int((today or dt.date.today()).isocalendar().week)


def resolve_mode(env: dict[str, str] | None = None) -> str:
    source = env or {}
    explicit = (source.get('PROVIDER_E2E_MODE') or source.get('INPUT_LIVE_MODE') or '').strip()
    if explicit in LIVE_MODES:
        return explicit
    if (source.get('INPUT_FULL') or '').strip().lower() in {'true', '1', 'yes'}:
        return 'prerelease'
    ref = source.get('GITHUB_REF') or ''
    if ref.startswith('refs/tags/v'):
        return 'prerelease'
    if source.get('GITHUB_EVENT_NAME') == 'schedule':
        return 'nightly'
    return 'nightly'


def _by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item['id']: item for item in rows}


def _pair(provider: dict[str, Any], asset: dict[str, Any], role: str) -> dict[str, Any]:
    return {
        'provider': dict(provider),
        'asset': dict(asset),
        'provider_id': provider['id'],
        'clip_id': asset['id'],
        'expect': asset['expect'],
        'role': role,
        'model': provider.get('default_model'),
    }


def assignments(
    mode: str,
    *,
    week: int | None = None,
    providers: list[dict[str, Any]] | None = None,
    asset_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if mode not in LIVE_MODES:
        raise ValueError(f'unknown live mode {mode}')
    week = current_iso_week() if week is None else int(week)
    provider_rows = providers if providers is not None else live_providers()
    clip_rows = asset_rows if asset_rows is not None else assets()
    by_provider = _by_id(provider_rows)
    by_asset = _by_id(clip_rows)
    if mode == 'api88':
        if 'api88' not in by_provider or VERIFY_PROBE_CLIP_ID not in by_asset:
            return []
        return [_pair(by_provider['api88'], by_asset[VERIFY_PROBE_CLIP_ID], 'probe')]
    if mode == 'prerelease':
        pairs = []
        for index, asset in enumerate(clip_rows):
            provider = provider_rows[(index + week) % len(provider_rows)]
            pairs.append(_pair(provider, asset, 'rotate'))
        return pairs
    nightly = []
    nightly_providers = [by_provider[item] for item in NIGHTLY_PROVIDER_IDS if item in by_provider]
    nightly_clips = [by_asset[item] for item in NIGHTLY_CLIP_IDS if item in by_asset]
    for index, asset in enumerate(nightly_clips):
        provider = nightly_providers[(index + week) % len(nightly_providers)]
        nightly.append(_pair(provider, asset, 'nightly'))
    if mode == 'nightly':
        return nightly
    probes = list(nightly)
    probe = by_asset[VERIFY_PROBE_CLIP_ID]
    for ident in VERIFY_PAID_PROVIDER_IDS:
        if ident in by_provider:
            probes.append(_pair(by_provider[ident], probe, 'probe'))
    return probes


def provider_ids_for_mode(mode: str) -> tuple[str, ...]:
    if mode == 'nightly':
        return NIGHTLY_PROVIDER_IDS
    if mode == 'api88':
        return ('api88',)
    return tuple(item['id'] for item in LIVE_PROVIDERS)
