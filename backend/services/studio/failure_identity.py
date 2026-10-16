"""1.5.8 terminal-event identity: provider slug + config_source enum, never URL/key/custom names.

``provider`` is a catalog slug (or ``other``); ``config_source`` is ``preset`` when the role's
connection uses the catalog base URL and a catalog model id, else ``customized``.
"""
from __future__ import annotations

from backend.core.llm_telemetry import CONFIG_SOURCES  # noqa: F401 - one enum, re-exported


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


ROLES = ('analysis', 'vision')


def provider_identity(role: str = 'analysis') -> dict:
    """R20 #136: provider slug + config_source of the connection the given role actually runs on; {} when
    unknown. One resolver (llm_emit.configured_connection_fields) for start identity, run snapshot and
    request events; callers freeze it at attempt start (store.attempt_identity: first source wins)."""
    if role not in ROLES:
        return {}
    from backend.core.llm_emit import configured_connection_fields
    fields = configured_connection_fields(role=role)
    if not fields:
        return {}
    return {'provider': fields.get('provider') or 'other', 'config_source': fields.get('config_source') or 'customized'}


def role_for(phase: str, plan: dict | None = None, goals=None) -> str:
    """R21 #194: the role whose connection a phase actually calls. One rule for every start/terminal.

    - screening: its only model call is the quick visual screening -> ``vision``.
    - production / rendering: the visual route runs the vision model unless every goal is ``content``
      (content is always cut from subtitles by the text model) -> ``vision``; else ``analysis``.
    - anything else -> ``analysis``.
    Telemetry/attribution only: routing never reads this."""
    if phase == 'screening':
        return 'vision'
    if phase in ('production', 'rendering'):
        plan = plan if isinstance(plan, dict) else {}
        route = plan.get('confirmed_analysis') or plan.get('recommended_analysis')
        selected = list(goals or plan.get('selected_goals') or [(plan.get('preferences') or {}).get('goal')])
        if route == 'visual' and any(goal != 'content' for goal in selected):
            return 'vision'
    return 'analysis'


def phase_identity(phase: str, plan: dict | None = None, goals=None) -> dict:
    """provider + config_source frozen at a phase start, from the role that phase runs on (#194)."""
    return provider_identity(role_for(phase, plan, goals))
