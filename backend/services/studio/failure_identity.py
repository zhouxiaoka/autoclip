"""1.5.8 terminal-event identity: provider slug + config_source enum, never URL/key/custom names.

``provider`` is a catalog slug (or ``other``); ``config_source`` is ``preset`` when the analysis
connection uses the catalog base URL and a catalog model id, else ``customized``.
"""
from __future__ import annotations

CONFIG_SOURCES = ('preset', 'customized')


def _norm(url: str | None) -> str:
    return (url or '').strip().rstrip('/').lower()


def _preset_urls(provider: str, url: str) -> set[str]:
    """The catalog URL as stored and as a saved Connection normalizes it (e.g. Gemini's /openai)."""
    urls = {_norm(url)}
    try:
        from backend.services import ai_model_settings as ai
        urls.add(_norm(ai.Connection(id='preset', name='preset', provider=provider, base_url=url).base_url))
    except Exception:  # noqa: BLE001,S110 - normalization is optional; the raw catalog URL still counts
        return urls
    return urls


def config_source(provider: str | None, base_url: str | None, model: str | None) -> str:
    from backend.core.provider_presets import get_provider
    preset = get_provider(provider) if provider else None
    if preset is None or provider == 'compatible':
        return 'customized'
    base = _norm(base_url)
    if base and base not in _preset_urls(provider, preset.base_url):
        return 'customized'
    model_id = (model or '').strip()
    known = {preset.default_model, *(preset.catalog or ()), *(m for ids in preset.candidates.values() for m in ids)}
    if model_id and model_id not in known:
        return 'customized'
    return 'preset'


def provider_identity() -> dict:
    """Provider slug + config_source of the saved analysis connection; {} when unknown."""
    try:
        from backend.services import ai_model_settings as ai
        settings = ai.load()
        binding = getattr(settings, 'analysis', None) if settings else None
        connection = next((c for c in settings.connections if c.id == binding.connection_id), None) if binding else None
    except Exception:  # noqa: BLE001 - telemetry identity can never fail a run
        return {}
    if connection is None:
        return {}
    from backend.core.llm_telemetry import sanitize_provider
    slug = sanitize_provider(connection.provider) or 'other'
    try:
        source = config_source(connection.provider, connection.base_url, binding.model)
    except Exception:  # noqa: BLE001
        source = 'customized'
    return {'provider': slug, 'config_source': source}
