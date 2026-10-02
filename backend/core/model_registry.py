"""Dynamic discovery plus independently refreshed capability metadata.

Never infer 'text only' from an unfamiliar ID. Provider metadata is scoped to
the actual endpoint; a community catalog supplements exact known IDs only.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path

from backend.core import asr_model_catalog as asr_catalog
from backend.core import model_catalog
from backend.core import image_model_catalog as image_catalog
from backend.core.path_utils import get_data_directory

_lock = threading.RLock()
_last_remote_attempt = 0.0
_remote_task = None
_MODEL_PROVIDER = {'dashscope': 'alibaba', 'seed': 'volcengine', 'gemini': 'google', 'kimi': 'moonshotai', 'glm': 'zhipuai', 'grok': 'xai'}
# Verified against Alibaba's official text-generation documentation, 2026-09-29.
# https://www.alibabacloud.com/help/en/model-studio/text-generation
_VERIFIED = {('dashscope', name): 'multimodal' for name in ('qwen3.8-max', 'qwen3.8-flash')}
# Official model input modalities verified 2026-10-03; account lists may omit them.
# https://help.aliyun.com/zh/model-studio/qwen3-vl-flash
_VERIFIED.update({('dashscope', name): 'multimodal'
                  for name in ('qwen3-vl-flash', 'qwen3-vl-flash-2026-01-22')})


def _path():
    return get_data_directory() / 'model-catalog-cache.json'


def _read():
    try:
        data = json.loads(_path().read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _update(key, value):
    with _lock:
        data = _read()
        data[key] = value
        target = _path()
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        try:
            temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)


def _scope(connection):
    from backend.services.ai_model_settings import chat_endpoint
    endpoint = chat_endpoint(connection, '')
    # Credentials never leave the provider, and are never stored in this cache.
    identity = '\0'.join((connection.provider, endpoint['base_url'], endpoint['api_key']))
    return 'connection:v4:' + hashlib.sha256(identity.encode()).hexdigest()


def _infistar_record(item):
    endpoints = item.get('supported_endpoint_types', [])
    return {'id': item.get('model_name') or item.get('id'),
            'supported_endpoint_types': endpoints,
            'capability': item.get('capability') or ('multimodal' if '图像理解' in item.get('tags', '').split(',') else None)}


async def _infistar_public(refresh=False):
    """Public Model Square, never account data or credentials. Store only routing metadata."""
    cached = _read().get('public:infistar', {})
    now = time.time()
    if not refresh and now - cached.get('attempted_at', 0) < (3600 if not cached.get('stale') else 300):
        return cached
    try:
        payload = await model_catalog._http_get_json('https://infistar.cc/api/pricing')
        raw = payload.get('data')
        if payload.get('success') is not True or not isinstance(raw, list) or not raw:
            raise ValueError('Invalid public catalog')
        models = [_infistar_record(item) for item in raw if isinstance(item, dict) and item.get('model_name')]
        if not models:
            raise ValueError('Empty public catalog')
        value = {'models': models, 'updated_at': now, 'attempted_at': now, 'stale': False}
    except Exception:
        models = cached.get('models') or json.loads(Path(__file__).with_name('infistar_models.json').read_text())['models']
        value = {'models': models, 'updated_at': cached.get('updated_at'), 'attempted_at': now, 'stale': True}
    _update('public:infistar', value)
    return value


def _is_infistar(connection):
    from urllib.parse import urlparse
    from backend.services.ai_model_settings import chat_endpoint
    return connection.provider == 'infistar' and urlparse(chat_endpoint(connection, '')['base_url']).hostname in {'infistar.cc', 'www.infistar.cc', 'infistar.ai', 'www.infistar.ai'}


def _with_public_metadata(connection, raw, public):
    if not public:
        return raw
    by_id = {item['id']: item for item in public['models']}
    # Exact ID intersection: never add a public-only model to an account's list.
    return [{**by_id.get(item if isinstance(item, str) else item.get('id'), {}),
             **({'id': item} if isinstance(item, str) else item)} for item in raw if isinstance(item, (str, dict))]


def _modalities(item):
    architecture = item.get('architecture') or {}
    modalities = item.get('modalities') or {}
    inputs = architecture.get('input_modalities', modalities.get('input'))
    outputs = architecture.get('output_modalities', modalities.get('output'))
    return inputs if isinstance(inputs, list) else None, outputs if isinstance(outputs, list) else None


def _cap(inputs):
    if inputs and 'image' in inputs:
        return 'multimodal'
    if inputs == ['text']:
        return 'text'
    return None


def lookup_capability(connection, model):
    data = _read()
    entry = next((m for m in data.get(_scope(connection), {}).get('models', []) if m['id'] == model), None)
    if entry and entry.get('capability_source') == 'provider' and entry.get('capability'):
        return entry['capability']
    return _catalog_capability(connection.provider, model, data)


def _catalog_record(provider, model, data):
    # Explicit provider+ID match only. Gateways can return modalities themselves;
    # arbitrary aliases must not be guessed from a substring of the model name.
    providers = data.get('metadata', {}).get('providers', {})
    return providers.get(_MODEL_PROVIDER.get(provider, provider), {}).get(model, {})


def _catalog_capability(provider, model, data):
    known = _VERIFIED.get((provider, model)) or _catalog_record(provider, model, data).get('capability')
    if not known and provider in {'infistar', 'api88'}:
        # Public gateway IDs can match original vendors exactly. Require agreement;
        # do not infer a capability from a name prefix or missing image tags.
        matches = {models[model]['capability'] for models in data.get('metadata', {}).get('providers', {}).values()
                   if model in models and models[model].get('capability')}
        if len(matches) == 1:
            known = matches.pop()
    return known


async def _refresh_metadata():
    global _last_remote_attempt
    existing = _read().get('metadata', {})
    now = time.time()
    if now - existing.get('updated_at', 0) < 86400 or now - _last_remote_attempt < 300:
        return
    _last_remote_attempt = now
    try:
        payload = await model_catalog._http_get_json('https://models.dev/api.json')
        providers = {}
        for provider, info in payload.items():
            if not isinstance(info, dict):
                continue
            models = {}
            for model_id, item in (info.get('models') or {}).items():
                if not isinstance(item, dict):
                    continue
                inputs, outputs = _modalities(item)
                models[model_id] = {'capability': _cap(inputs), 'image_output': bool(outputs and 'image' in outputs),
                                    'source': 'https://models.dev/api.json'}
            providers[provider] = models
        if providers:
            _update('metadata', {'updated_at': now, 'providers': providers})
    except Exception:
        # Metadata outages must not discard working lists or block custom models.
        pass


async def _ensure_metadata():
    global _remote_task
    if _remote_task is None or _remote_task.done():
        _remote_task = asyncio.create_task(_refresh_metadata())
    await asyncio.shield(_remote_task)


def _records(connection, raw, data):
    result = []
    seen = set()
    for item in raw:
        if isinstance(item, str):
            item = {'id': item}
        if not isinstance(item, dict):
            continue
        name = str(item.get('id') or item.get('name') or '').removeprefix('models/')
        if not name or name in seen:
            continue
        seen.add(name)
        inputs, outputs = _modalities(item)
        caps = item.get('capabilities')
        if isinstance(caps, list) and 'vision' in caps:
            inputs = ['text', 'image']
        capability = _cap(inputs) or item.get('capability')
        source = 'provider' if capability else 'catalog'
        capability = capability or _catalog_capability(connection.provider, name, data)
        catalog = _catalog_record(connection.provider, name, data)
        image = ('image' in outputs if outputs is not None else
                 catalog.get('image_output', False) or name in image_catalog.MODELS.get(connection.provider, []) or name in model_catalog.IMAGE_MODELS.get(connection.provider, []))
        if name in image_catalog.EDIT_ONLY.get(connection.provider, set()):
            image = False
        methods = item.get('supportedGenerationMethods', [])
        analysis = ('text' in outputs if outputs else model_catalog.is_chat_model(name, '', official=False) and not image)
        if methods and 'generateContent' not in methods:
            analysis = False
            if connection.provider == 'gemini':
                image = False
        if name in image_catalog.UNSUPPORTED_ROUTES.get(connection.provider, set()):
            analysis = image = False
        if 'supported_endpoint_types' in item:
            # Provider routing metadata distinguishes generation from editing.
            endpoints = item['supported_endpoint_types']
            image = 'image-generation' in endpoints or '/v1/images/generations' in endpoints
            analysis = 'openai' in endpoints or '/v1/chat/completions' in endpoints
        asr = asr_catalog.metadata(connection.provider, name, item.get('supported_endpoint_types', []))
        if asr['asr']:
            analysis = False
        result.append({**asr, 'id': name, 'capability': capability, 'capability_source': source if capability else None,
                       'analysis': analysis, 'image': image, 'asr_preview': bool(item.get('asr_preview'))})
    return result


async def discover(connection, refresh=False):
    from backend.services.ai_model_settings import chat_endpoint
    from backend.core.llm_providers import is_local_url
    endpoint = chat_endpoint(connection, '')
    public = await _infistar_public(refresh) if _is_infistar(connection) else None
    local = connection.provider in {'ollama', 'lmstudio'} or (connection.base_url and is_local_url(connection.base_url))
    if not endpoint['api_key'] and not local:
        if public:
            raw = public['models']
            updated_at = public['updated_at']
        else:
            await _ensure_metadata()
            data = _read()
            remote = data.get('metadata', {}).get('providers', {}).get(_MODEL_PROVIDER.get(connection.provider, connection.provider), {}) if not connection.base_url else {}
            raw = [name for name in dict.fromkeys(model_catalog.CURATED_MODELS.get(connection.provider, []) + image_catalog.MODELS.get(connection.provider, []) + asr_catalog.MODELS.get(connection.provider, []) + list(remote))
                   if name not in image_catalog.RETIRED.get(connection.provider, set())]
            updated_at = data.get('metadata', {}).get('updated_at')
        return {'models': _records(connection, raw, _read()), 'source': 'catalog', 'preview': True, 'updated_at': updated_at,
                'warning': '公开目录预览，填写 API Key 后确认账号可用模型。' + (' 当前展示缓存目录。' if public and public.get('stale') else '')}
    scope = _scope(connection)
    cached = _read().get(scope)
    if cached and not refresh and time.time() - cached.get('updated_at', 0) < 300:
        return {**cached, 'source': 'cache'}

    async def fetch():
        if connection.provider == 'gemini' and not connection.base_url:
            raw, token = [], None
            while True:
                params = {'key': endpoint['api_key'], 'pageSize': 200}
                if token:
                    params['pageToken'] = token
                payload = await model_catalog._http_get_json(model_catalog.GEMINI_MODELS_URL, params=params)
                raw.extend(payload.get('models', []))
                token = payload.get('nextPageToken')
                if not token:
                    return raw
        headers = {'Authorization': 'Bearer ' + endpoint['api_key']} if endpoint['api_key'] else {}
        payload = await model_catalog._http_get_json(endpoint['base_url'] + '/models', headers=headers,
                                                      trust_env=not is_local_url(endpoint['base_url']))
        raw = payload.get('data', []) if isinstance(payload, dict) else payload
        if not isinstance(raw, list):
            raise ValueError('Invalid model list')
        if connection.provider == 'ollama':
            import httpx
            root = endpoint['base_url'].removesuffix('/v1')
            semaphore = asyncio.Semaphore(4)
            async with httpx.AsyncClient(timeout=8, trust_env=not is_local_url(root)) as client:
                async def details(item):
                    if not isinstance(item, dict) or not item.get('id'):
                        return item
                    try:
                        async with semaphore:
                            response = await client.post(root + '/api/show', json={'model': item['id']}, headers=headers)
                            response.raise_for_status()
                            return {**item, 'capabilities': response.json().get('capabilities')}
                    except Exception:
                        return item
                raw = await asyncio.gather(*(details(item) for item in raw))
        return raw

    results = await asyncio.gather(fetch(), _ensure_metadata(), return_exceptions=True)
    raw = results[0]
    if isinstance(raw, BaseException):
        if cached:
            return {**cached, 'source': 'cache', 'warning': '模型列表刷新失败，正在使用上次成功的列表'}
        fallback = public['models'] if public else model_catalog.CURATED_MODELS.get(connection.provider, []) + image_catalog.MODELS.get(connection.provider, []) + asr_catalog.MODELS.get(connection.provider, [])
        return {'models': _records(connection, fallback, _read()), 'source': 'catalog', 'updated_at': None,
                'preview': True, 'warning': '账号模型列表获取失败，当前为参考目录；请检查密钥后刷新。'}
    if connection.provider == 'dashscope':
        # The OpenAI-compatible /models endpoint does not enumerate all native ASR APIs.
        # Keep native ASR references visibly unverified, rather than calling them account-entitled.
        ids = {item if isinstance(item, str) else item.get('id') for item in raw}
        raw = [*raw, *({'id': name, 'asr_preview': True} for name in asr_catalog.MODELS['dashscope'] if name not in ids)]
    value = {'models': _records(connection, _with_public_metadata(connection, raw, public), _read()), 'source': 'live', 'updated_at': time.time()}
    _update(scope, value)
    return value
