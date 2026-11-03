"""Infer and persist ``preset`` / ``user`` sources on model settings.

First-party AutoClip logic. Catalog product data comes from
``backend/presets/provider_presets.json`` via ``provider_presets``; this module does
not vendor third-party code.

Telemetry and public notices use only stable codes. They never include keys,
full URLs, paths, titles, transcripts, or user-written text.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from pydantic import ValidationError

Source = str  # 'preset' | 'user'
NOTICE_PURPOSE_RESET = 'purpose_reset_to_recommended'
NOTICE_PRESET_UPDATED = 'preset_catalog_updated'
KNOWN_NOTICES = frozenset({
    NOTICE_PURPOSE_RESET,
    NOTICE_PRESET_UPDATED,
    'cover_configuration_invalid',
    'analysis_configuration_invalid',
    'vision_configuration_invalid',
    'transcription_configuration_invalid',
    'settings_configuration_invalid',
})
_PURPOSE_ROLES = ('analysis', 'vision', 'cover')
_PURPOSE_CANDIDATE = {'analysis': 'analysis', 'vision': 'vision', 'cover': 'image'}


def current_catalog_version() -> int:
    try:
        from backend.core.provider_presets import get_catalog
        return int(get_catalog().version)
    except Exception:
        return 0


def preset_base_url(provider: str) -> str:
    try:
        from backend.core.provider_presets import get_provider
        item = get_provider(provider)
        return (item.base_url if item else '') or ''
    except Exception:
        return ''


def recommended_model(provider: str, purpose: str) -> str:
    key = _PURPOSE_CANDIDATE.get(purpose, purpose)
    try:
        from backend.core.provider_presets import candidates_for, get_provider, image_catalog_map
        candidates = candidates_for(provider, key)
        if candidates:
            return candidates[0]
        if key == 'image':
            images = image_catalog_map().get(provider) or []
            if images:
                return images[0]
        item = get_provider(provider)
        if item and item.default_model and key in {'analysis', 'vision'}:
            return item.default_model
        if key == 'vision':
            return recommended_model(provider, 'analysis')
    except Exception:
        return ''
    return ''


def urls_match(left: str, right: str, provider: str) -> bool:
    from backend.core.provider_url import normalize_provider_base_url
    a = normalize_provider_base_url(left, provider)
    b = normalize_provider_base_url(right, provider)
    return bool(a) and a == b


def infer_base_url_source(provider: str, base_url: str) -> str:
    if (provider or '').strip().lower() == 'compatible':
        return 'user'
    url = (base_url or '').strip()
    if not url:
        return 'preset'
    official = preset_base_url(provider)
    if official and urls_match(url, official, provider):
        return 'preset'
    return 'user'


def infer_model_source(model: str, explicit: Optional[str] = None) -> str:
    if explicit in ('preset', 'user'):
        return explicit
    return 'user' if usable_model(model) else 'preset'


def usable_model(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value.strip()) <= 200


def usable_api_key(value: Any) -> Optional[str]:
    if value is None:
        return ''
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) > 2000:
        return None
    return text


def known_notices(values: Iterable[Any]) -> List[str]:
    return [item for item in values if isinstance(item, str) and item in KNOWN_NOTICES]


def is_legacy_source_document(data: Mapping[str, Any]) -> bool:
    if 'acked_catalog_version' in data or 'seen_notices' in data:
        return False
    for item in data.get('connections') or []:
        if isinstance(item, Mapping) and 'base_url_source' in item:
            return False
    for role in _PURPOSE_ROLES:
        binding = data.get(role)
        if isinstance(binding, Mapping) and 'model_source' in binding:
            return False
    return True


def binding_unmigratable(binding: Mapping[str, Any], connection_ids: Sequence[str]) -> bool:
    if binding.get('connection_id') not in connection_ids:
        return True
    return not usable_model(binding.get('model'))


def try_connection(**kwargs: Any) -> Any:
    """Build a Connection; if the URL is invalid, keep the key and drop the URL."""
    from backend.services.ai_model_settings import Connection
    try:
        return Connection(**kwargs)
    except (ValidationError, ValueError, TypeError):
        key = usable_api_key(kwargs.get('api_key'))
        if key is None:
            return None
        try:
            return Connection(
                id=kwargs.get('id'),
                name=kwargs.get('name') or kwargs.get('provider') or 'connection',
                provider=kwargs.get('provider') or 'openai',
                base_url='',
                api_key=key,
                base_url_source='preset',
                image_api=kwargs.get('image_api') or 'auto',
                image_base_url='',
            )
        except (ValidationError, ValueError, TypeError):
            return None


def _reset_binding(data: Dict[str, Any], role: str, binding: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    connections = data.get('connections') or []
    conn = next((item for item in connections if item.get('id') == binding.get('connection_id')), None)
    # Missing connection: mark needs-repair. Never borrow connections[0] (that switches provider).
    if not isinstance(conn, dict):
        return None
    model = recommended_model(conn.get('provider') or 'openai', role)
    if not model:
        return None
    capability = binding.get('capability') if binding.get('capability') in ('auto', 'multimodal', 'text') else 'auto'
    if role == 'vision':
        capability = 'multimodal'
    return {
        'connection_id': conn['id'],
        'model': model,
        'capability': capability,
        'model_source': 'preset',
    }


def annotate_document(data: Mapping[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Fill source fields on a raw settings dict. Legacy filled models become ``user``."""
    if not isinstance(data, Mapping):
        return dict(data) if data else {}, []
    connections = data.get('connections')
    if not isinstance(connections, list):
        return dict(data), []
    if connections and not isinstance(connections[0], dict):
        return dict(data), []
    out: Dict[str, Any] = {**data, 'connections': [dict(item) for item in connections]}
    warnings: List[str] = []
    legacy = is_legacy_source_document(data)
    catalog_version = current_catalog_version()
    for item in out['connections']:
        if 'base_url_source' not in item:
            item['base_url_source'] = infer_base_url_source(item.get('provider') or 'openai', item.get('base_url') or '')
        if legacy and not item.get('preset_version'):
            item['preset_version'] = catalog_version
    ids = [item.get('id') for item in out['connections'] if isinstance(item.get('id'), str)]
    for role in _PURPOSE_ROLES:
        binding = out.get(role)
        if not isinstance(binding, dict):
            continue
        binding = dict(binding)
        out[role] = binding
        if 'model_source' not in binding:
            # Q16: a filled model with no source is user (legacy files and omitted saves).
            binding['model_source'] = infer_model_source(binding.get('model') or '')
        if legacy and binding_unmigratable(binding, ids):
            reset = _reset_binding(out, role, binding)
            if reset:
                out[role] = reset
                warnings.append(NOTICE_PURPOSE_RESET)
            else:
                out[role] = None
                if role == 'cover':
                    out['cover_enabled'] = False
                    warnings.append('cover_configuration_invalid')
                else:
                    warnings.append(f'{role}_configuration_invalid')
    if legacy and 'acked_catalog_version' not in out:
        out['acked_catalog_version'] = catalog_version
    return out, warnings


def prepare_connections_for_save(connections: Sequence[Any]) -> List[Any]:
    """Snapshot empty preset URLs and stamp catalog version. Never rewrite a saved URL."""
    from backend.services.ai_model_settings import chat_endpoint
    version = current_catalog_version()
    prepared = []
    for connection in connections:
        updates: Dict[str, Any] = {}
        if getattr(connection, 'base_url_source', 'preset') == 'preset' and not connection.base_url:
            url = chat_endpoint(connection, '')['base_url']
            if url:
                updates['base_url'] = url
        if not getattr(connection, 'preset_version', 0) and version:
            updates['preset_version'] = version
        prepared.append(connection.model_copy(update=updates) if updates else connection)
    return prepared


def preset_update_available(settings: Any) -> bool:
    catalog_version = current_catalog_version()
    if not catalog_version or catalog_version <= int(getattr(settings, 'acked_catalog_version', 0) or 0):
        return False
    return any(0 < int(getattr(item, 'preset_version', 0) or 0) < catalog_version for item in settings.connections)
