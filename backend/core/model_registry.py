"""Dynamic discovery plus independently refreshed capability metadata.

Never infer 'text only' from an unfamiliar ID. Provider metadata is scoped to
the actual endpoint; a community catalog supplements exact known IDs only.
"""
from __future__ import annotations

import asyncio
import re
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
from backend.core.provider_presets import candidates_for
from backend.core.path_utils import get_data_directory

_lock = threading.RLock()
_last_remote_attempt = 0.0
_remote_task = None
_CAPABILITY_VERSION = 3
_MODEL_PROVIDER = {'dashscope': 'alibaba', 'seed': 'volcengine', 'gemini': 'google', 'kimi': 'moonshotai', 'glm': 'zhipuai', 'grok': 'xai'}
# Verified against Alibaba's official text-generation documentation, 2026-09-29.
# https://www.alibabacloud.com/help/en/model-studio/text-generation
_VERIFIED = {('dashscope', name): 'multimodal' for name in ('qwen3.8-max', 'qwen3.8-flash')}
# Official model input modalities verified 2026-10-03; account lists may omit them.
# https://help.aliyun.com/zh/model-studio/qwen3-vl-flash
_VERIFIED.update({('dashscope', name): 'multimodal'
                  for name in ('qwen3-vl-flash', 'qwen3-vl-flash-2026-01-22')})
# Text, image and video input; text output. Scope this ID to Bailian.
# https://help.aliyun.com/zh/model-studio/qwen4-max
_VERIFIED[('dashscope', 'qwen4-max')] = 'multimodal'


# T3 local model gate: params < 7B or context < 8k → UI red warn (still selectable).
LOCAL_MIN_PARAMS_B = 7.0
LOCAL_MIN_CONTEXT_TOKENS = 8192
_PARAM_SIZE_RE = re.compile(r'([0-9]+(?:\.[0-9]+)?)\s*([KkMmBbTt])\b')
_NAME_PARAMS_RE = re.compile(r'\b([0-9]+(?:\.[0-9]+)?)[bB]\b')


def parse_parameter_size(value) -> float | None:
    """Ollama ``details.parameter_size`` → billions (e.g. ``7B`` → 7.0, ``3.8B`` → 3.8)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return number if number > 0 else None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    match = _PARAM_SIZE_RE.search(text.replace(',', ''))
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2).upper()
    if unit == 'B':
        return number
    if unit == 'M':
        return number / 1000.0
    if unit == 'K':
        return number / 1_000_000.0
    if unit == 'T':
        return number * 1000.0
    return None


def infer_params_b_from_name(name: str | None) -> float | None:
    """LM Studio / tag fallback: last ``\\b(\\d+)[bB]\\b`` in the model id."""
    if not isinstance(name, str) or not name.strip():
        return None
    matches = _NAME_PARAMS_RE.findall(name)
    if not matches:
        return None
    try:
        value = float(matches[-1])
    except ValueError:
        return None
    return value if value > 0 else None


def extract_context_tokens(model_info) -> int | None:
    """Ollama ``model_info['*.context_length']`` → int tokens."""
    if not isinstance(model_info, dict):
        return None
    for key, value in model_info.items():
        if not isinstance(key, str) or not key.endswith('.context_length'):
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            number = int(value)
            return number if number > 0 else None
        if isinstance(value, str) and value.strip().isdigit():
            number = int(value.strip())
            return number if number > 0 else None
    return None


def enrich_local_model_item(item: dict, *, provider: str) -> dict:
    """Attach ``params_b`` / ``context_tokens`` from Ollama show payload or name inference."""
    if not isinstance(item, dict):
        return item
    name = str(item.get('id') or item.get('name') or '')
    params = parse_parameter_size((item.get('details') or {}).get('parameter_size') if isinstance(item.get('details'), dict) else item.get('parameter_size'))
    if params is None:
        params = parse_parameter_size(item.get('parameter_size'))
    context = extract_context_tokens(item.get('model_info'))
    if context is None and isinstance(item.get('context_length'), (int, float)) and not isinstance(item.get('context_length'), bool):
        context = int(item['context_length']) if int(item['context_length']) > 0 else None
    if params is None:
        params = infer_params_b_from_name(name)
    # LM Studio OpenAI /v1/models rarely has size; name inference is the only signal.
    if provider == 'lmstudio' and params is None:
        params = infer_params_b_from_name(name)
    out = dict(item)
    if params is not None:
        out['params_b'] = round(float(params), 3)
    if context is not None:
        out['context_tokens'] = int(context)
    return out


def below_local_analysis_gate(params_b: float | None, context_tokens: int | None) -> bool:
    """True when the model is under the T3 analysis floor (still selectable)."""
    if params_b is not None and params_b < LOCAL_MIN_PARAMS_B:
        return True
    if context_tokens is not None and context_tokens < LOCAL_MIN_CONTEXT_TOKENS:
        return True
    return False




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
        temp = None
        try:
            data = _read()
            data[key] = value
            target = _path()
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_suffix('.' + uuid.uuid4().hex + '.tmp')
            temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            os.replace(temp, target)
        except OSError:
            # This optional cache must not discard a successful provider reply.
            # Atomic replacement leaves the previous cache intact on write failure.
            pass
        finally:
            if temp is not None:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    # Cleanup must not turn success into failure or mask another error.
                    pass


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
    architecture = item.get('architecture')
    modalities = item.get('modalities')

    def read(direction):
        key = f'{direction}_modalities'
        for container, field in ((item, key), (architecture, key), (modalities, direction)):
            if isinstance(container, dict) and isinstance(container.get(field), list):
                values = [v.strip().lower() for v in container[field] if isinstance(v, str) and v.strip()]
                if values:
                    return values
        return None

    return read('input'), read('output')


def _cap(inputs):
    if inputs and 'image' in inputs:
        return 'multimodal'
    if inputs and 'text' in inputs:
        return 'text'
    return None


def _custom_offers(connection):
    offers = list(getattr(connection, 'custom_models', None) or [])
    if offers or 'custom_models' in getattr(connection, 'model_fields_set', set()):
        return offers
    try:
        from backend.services import ai_model_settings as ai_models
        previous = ai_models.load()
    except Exception:
        return []
    ident = getattr(connection, 'id', None)
    old = next((item for item in previous.connections if item.id == ident), None) if previous and ident else None
    return list(old.custom_models) if old else []


def _record_from_offer(connection, offer):
    name = str(getattr(offer, 'id', '') or '').strip()
    if not name:
        return None
    types = set(getattr(offer, 'types', None) or ['language'])
    scenarios = set(getattr(offer, 'scenarios', None) or [])
    vision = bool(getattr(offer, 'vision', False) and 'language' in types)
    asr_metadata = asr_catalog.metadata(connection.provider, name)
    asr = 'asr' in types or 'transcription' in scenarios or asr_metadata['asr']
    return {
        'id': name,
        'capability': 'multimodal' if vision else ('text' if 'language' in types else None),
        'capability_source': 'custom',
        'kind': _model_kind({}, name, analysis='language' in types, image='image' in types, asr=asr, outputs=[]),
        'analysis': 'analysis' in scenarios or 'language' in types,
        'image': 'image' in types or 'cover' in scenarios,
        'asr': asr,
        'asr_supported': asr_metadata['asr_supported'],
        'asr_preview': False,
        'asr_note': asr_metadata['asr_note'],
    }


def _merge_custom_models(connection, value):
    """Keep user-authored custom_models in the picker. Live IDs are additive."""
    models = [item for item in (value.get('models') or []) if isinstance(item, dict)]
    by_id = {item.get('id'): index for index, item in enumerate(models)}
    for offer in _custom_offers(connection):
        if getattr(offer, 'enabled', True) is False:
            continue
        record = _record_from_offer(connection, offer)
        if not record:
            continue
        existing = by_id.get(record['id'])
        if existing is None:
            by_id[record['id']] = len(models)
            models.append(record)
        else:
            models[existing] = {**models[existing], **record}
    return {**value, 'models': models}


def lookup_capability(connection, model):
    for offer in _custom_offers(connection):
        if getattr(offer, 'id', None) != model or getattr(offer, 'enabled', True) is False:
            continue
        record = _record_from_offer(connection, offer)
        if record:
            return record.get('capability')
    if _VERIFIED.get((connection.provider, model)) == 'multimodal':
        return 'multimodal'
    data = _read()
    entry = next((m for m in data.get(_scope(connection), {}).get('models', []) if m['id'] == model), None)
    if entry and entry.get('capability_source') == 'provider':
        return entry.get('capability')
    return _catalog_capability(connection.provider, model, data) or _named_capability(connection.provider, model)


def _named_capability(provider, model):
    if provider != 'compatible' and model_catalog.catalog_vision_model(model):
        return 'multimodal'
    return None


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


def _model_kind(item, name, *, analysis, image, asr, outputs):
    """One display group per model: provider type metadata first, then capability flags."""
    endpoints = [str(e) for e in (item.get('supported_endpoint_types') or [])]
    lowered = name.lower()
    if any('video' in e for e in endpoints) or 'video' in outputs:
        return 'video'
    if asr:
        return 'asr'
    if any('audio' in e or 'speech' in e for e in endpoints) or 'audio' in outputs or any(t in lowered for t in ('tts', '-stt', 'speech', 'audio')):
        return 'audio'
    if image:
        return 'image'
    if analysis:
        return 'language'
    return 'other'


def _records(connection, raw, data):
    result = []
    seen = set()
    try:
        from backend.core.llm_providers import is_local_url
        local_provider = connection.provider in {'ollama', 'lmstudio'} or bool(
            getattr(connection, 'base_url', None) and is_local_url(connection.base_url)
        )
    except Exception:  # noqa: BLE001
        local_provider = connection.provider in {'ollama', 'lmstudio'}
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
        if inputs is None and isinstance(caps, list) and 'vision' in caps:
            inputs = ['text', 'image']
        reported = item.get('capability')
        capability = _cap(inputs) if inputs else reported if reported in ('text', 'multimodal') else None
        source = 'provider' if inputs or capability else 'catalog'
        if _VERIFIED.get((connection.provider, name)) == 'multimodal' and capability != 'multimodal':
            # Exact verified official allowlist IDs (e.g. dashscope/qwen4-max) must not be
            # downgraded to text-only by boilerplate OpenAI-compat input_modalities=['text'].
            capability, source = 'multimodal', 'catalog'
        if inputs is None and not capability:
            capability = _catalog_capability(connection.provider, name, data)
        if inputs is None and not capability and _named_capability(connection.provider, name):
            # Recognize known IDs only when the provider supplied no input restrictions.
            capability, source = 'multimodal', 'name'
        if getattr(connection, 'provider', None) == 'apimart':
            # Vision/Omni tags add multimodal. A Text tag leaves the name heuristic
            # in place. Non-chat families are dropped even when tagged Vision.
            from backend.core.provider_model_fetch import capability_from_tags
            category = str(item.get('category') or '').strip().lower()
            if category in {'image', 'video', 'audio'} or model_catalog.is_non_chat_family(name):
                continue
            tags = item.get('capability_tags')
            if isinstance(tags, list) and tags:
                lowered = {str(tag).strip().lower() for tag in tags if str(tag).strip()}
                if lowered and not (lowered & {'text', 'vision', 'omni'}):
                    continue
            tagged = capability_from_tags(tags)
            if tagged and inputs is None:
                capability, source = tagged, 'provider'
        if capability == 'multimodal' and model_catalog.known_text_only(name):
            capability, source = 'text', 'catalog'
        catalog = _catalog_record(connection.provider, name, data)
        known_image = (
            name in image_catalog.MODELS.get(connection.provider, ())
            or name in model_catalog.IMAGE_MODELS.get(connection.provider, ())
        )
        image = (
            'image' in outputs if outputs is not None else
            catalog.get('image_output', False) or known_image
        )
        if known_image and not image:
            image = True
        methods = item.get('supportedGenerationMethods') or []
        chat_evidence = (capability or name in model_catalog.CURATED_MODELS.get(connection.provider, ())
                         or name in candidates_for(connection.provider, 'analysis') or 'generateContent' in methods
                         or isinstance(caps, list) and 'completion' in caps or item.get('type') == 'llm'
                         or connection.provider == 'apimart' and item.get('category') in {'text', 'chat'})
        analysis = bool(('text' in outputs if outputs is not None else chat_evidence and not image)
                        and model_catalog.is_chat_model(name, '', official=False))
        if methods and 'generateContent' not in methods:
            analysis = False
            if connection.provider == 'gemini':
                image = False
        if item.get('supported_endpoint_types'):
            # Provider routing metadata distinguishes generation from editing.
            endpoints = [str(e) for e in (item['supported_endpoint_types'] or [])]
            multimodal_image = known_image and any('multimodal-generation' in e for e in endpoints)
            image = (
                'image-generation' in endpoints
                or '/v1/images/generations' in endpoints
                or multimodal_image
                or known_image
            )
            # new-api style gateways: video routes and async "task plugin" models are not chat models,
            # even when they also list the generic "openai" endpoint. The name guard drops TTS/STT/embedding.
            video = any('video' in e for e in endpoints)
            task = str(item.get('owned_by') or '').lower() == 'task plugin'
            analysis = (('openai' in endpoints or '/v1/chat/completions' in endpoints) and not image and not video and not task
                        and model_catalog.is_chat_model(name, '', official=False))
        asr = asr_catalog.metadata(connection.provider, name, item.get('supported_endpoint_types') or [])
        if name in image_catalog.UNSUPPORTED_ROUTES.get(connection.provider, ()) or name in image_catalog.EDIT_ONLY.get(connection.provider, ()):
            analysis = image = False
        if inputs and 'text' not in inputs and 'image' not in inputs:
            analysis = False
        if asr['asr']:
            analysis = False
        kind = _model_kind(item, name, analysis=analysis, image=image, asr=asr['asr'], outputs=outputs or [])
        record = {**asr, 'id': name, 'capability': capability, 'capability_source': source if capability or inputs else None,
                       'analysis': analysis, 'image': image, 'kind': kind, 'asr_preview': bool(item.get('asr_preview'))}
        if (kind == 'other' and not inputs and not outputs and not methods and not item.get('supported_endpoint_types')
                and not model_catalog.is_non_chat_family(name)
                and name not in image_catalog.UNSUPPORTED_ROUTES.get(connection.provider, ())
                and name not in image_catalog.EDIT_ONLY.get(connection.provider, ())):
            roles = [] if model_catalog.is_image_model(name) else ['analysis', 'vision']
            if model_catalog.known_text_only(name) and 'vision' in roles:
                roles.remove('vision')
            if connection.provider in image_catalog.MODELS or connection.provider in {'compatible', 'infistar'}:
                roles.append('cover')
            record['manual_roles'] = roles
        # T3: surface size/context for the settings picker + D1 chunk_size later.
        params_b = item.get('params_b')
        if params_b is None:
            params_b = infer_params_b_from_name(name) if connection.provider in {'ollama', 'lmstudio'} or local_provider else None
        context_tokens = item.get('context_tokens')
        if isinstance(params_b, (int, float)) and not isinstance(params_b, bool):
            record['params_b'] = float(params_b)
        if isinstance(context_tokens, (int, float)) and not isinstance(context_tokens, bool) and int(context_tokens) > 0:
            record['context_tokens'] = int(context_tokens)
        result.append(record)
    return result


def listed_chat_capabilities(provider, raw):
    """The same account-list classification powers the picker and smart recovery."""
    from types import SimpleNamespace
    rows = _records(SimpleNamespace(provider=provider), raw, _read())
    return {row['id']: (row['capability'] or 'chat') if row['analysis'] else 'unavailable' for row in rows}


def _upgrade_cached_models(connection, cached):
    """Older caches kept normalized rows only. Reclassify IDs using today's catalog
    and preserve positive provider evidence without treating old guesses as metadata.
    Keep the original timestamp so the next refresh still attempts discovery.
    """
    raw = []
    for row in cached.get('models', []):
        if not isinstance(row, dict) or not row.get('id'):
            continue
        item = {key: row[key] for key in ('id', 'params_b', 'context_tokens', 'asr_preview') if key in row}
        if row.get('capability_source') == 'provider' and row.get('capability'):
            item['capability'] = row['capability']
        if row.get('asr'):
            item['supported_endpoint_types'] = ['audio-transcription']
        if row.get('image'):
            item['output_modalities'] = ['image']
        elif row.get('kind') in {'audio', 'video'}:
            item['output_modalities'] = [row['kind']]
        raw.append(item)
    return _records(connection, raw, _read())


async def discover(connection, refresh=False):
    return _merge_custom_models(connection, await _discover_from_provider(connection, refresh))


async def _discover_from_provider(connection, refresh=False):
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
    if cached and cached.get('capability_version') == _CAPABILITY_VERSION and not refresh and time.time() - cached.get('updated_at', 0) < 300:
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
        params = {'expand': 'category'} if connection.provider == 'apimart' else None
        payload = await model_catalog._http_get_json(endpoint['base_url'] + '/models', headers=headers,
                                                      params=params,
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
                            payload = response.json()
                            shown = payload if isinstance(payload, dict) else {}
                            # T3: keep capabilities and also params_b / context_tokens from show.
                            merged = {
                                **item,
                                'capabilities': shown.get('capabilities', item.get('capabilities')),
                                'details': shown.get('details') or item.get('details'),
                                'model_info': shown.get('model_info') or item.get('model_info'),
                            }
                            return enrich_local_model_item(merged, provider='ollama')
                    except Exception:
                        return enrich_local_model_item(item, provider='ollama')
                raw = await asyncio.gather(*(details(item) for item in raw))
        elif connection.provider == 'lmstudio':
            raw = [
                enrich_local_model_item(item if isinstance(item, dict) else {'id': item}, provider='lmstudio')
                for item in raw
            ]
        elif local:
            # Compatible / openai pointed at a local host: still infer size from the name.
            raw = [
                enrich_local_model_item(item if isinstance(item, dict) else {'id': item}, provider=connection.provider or 'compatible')
                for item in raw
            ]
        return raw

    results = await asyncio.gather(fetch(), _ensure_metadata(), return_exceptions=True)
    raw = results[0]
    if isinstance(raw, BaseException):
        if cached:
            models = cached['models'] if cached.get('capability_version') == _CAPABILITY_VERSION else _upgrade_cached_models(connection, cached)
            return {**cached, 'models': models, 'capability_version': _CAPABILITY_VERSION, 'source': 'cache', 'warning': '模型列表刷新失败，正在使用上次成功的列表'}
        fallback = public['models'] if public else model_catalog.CURATED_MODELS.get(connection.provider, []) + image_catalog.MODELS.get(connection.provider, []) + asr_catalog.MODELS.get(connection.provider, [])
        return {'models': _records(connection, fallback, _read()), 'source': 'catalog', 'updated_at': None,
                'preview': True, 'warning': '账号模型列表获取失败，当前为参考目录；请检查密钥后刷新。'}
    if connection.provider == 'dashscope':
        # The OpenAI-compatible /models endpoint omits native ASR. The three adapted
        # sync models still transcribe, so they stay selectable. Unadapted ASR stays a preview.
        ids = {item if isinstance(item, str) else item.get('id') for item in raw}
        raw = [*raw, *(
            {'id': name, 'asr_preview': name not in asr_catalog.DASHSCOPE_SYNC}
            for name in asr_catalog.MODELS['dashscope'] if name not in ids
        )]
    value = {'models': _records(connection, _with_public_metadata(connection, raw, public), _read()),
             'source': 'live', 'updated_at': time.time(), 'capability_version': _CAPABILITY_VERSION}
    _update(scope, value)
    return value
