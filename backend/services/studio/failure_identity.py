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
IDENTITY_KEYS = ('provider', 'config_source')


def connection_identity(connection, model: str | None) -> dict:
    """THE identity rule (R22 code health): provider slug + config_source of one saved connection and
    the model bound on it. Phase starts, request starts, run snapshots and Sentry all go through here."""
    if connection is None:
        return {}
    from backend.core.llm_telemetry import sanitize_provider
    provider = getattr(connection, 'provider', None)
    try:
        source = config_source(provider, getattr(connection, 'base_url', None), model)
    except Exception:  # noqa: BLE001 - attribution only
        source = 'customized'
    return {'provider': sanitize_provider(str(provider or '').strip().lower()) or 'other', 'config_source': source}


def settings_identity(settings, role: str = 'analysis') -> dict:
    """Identity of the connection ``role`` runs on in this settings object (vision falls back to analysis)."""
    if not settings or role not in ROLES:
        return {}
    binding = getattr(settings, 'vision', None) if role == 'vision' else None
    binding = binding or getattr(settings, 'analysis', None)
    if not binding:
        return {}
    connection = next((c for c in settings.connections if c.id == binding.connection_id), None)
    return connection_identity(connection, binding.model)


def provider_identity(role: str = 'analysis') -> dict:
    """Identity of the connection ``role`` runs on right now; {} when unknown. Callers freeze it at the
    START of a phase or request (never re-read at the end)."""
    if role not in ROLES:
        return {}
    try:
        from backend.services import ai_model_settings as ai
        return settings_identity(ai.load(), role)
    except Exception:  # noqa: BLE001 - settings must not break a start write
        return {}


def frozen(*sources) -> dict:
    """provider + config_source recorded at attempt start; first source that has them wins."""
    out = {}
    for source in sources:
        if isinstance(source, dict):
            for key in IDENTITY_KEYS:
                if key not in out and isinstance(source.get(key), str) and source[key]:
                    out[key] = source[key]
    return out


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


SCREENING_KEY = 'screening_identity'


def screening_identity(analysis, generation=None) -> dict:
    """R22 #220: the screening phase's own identity. It is stored apart from ``analysis.provider`` so
    production re-freezing by its route never rewrites what screening ran on."""
    analysis = analysis if isinstance(analysis, dict) else {}
    generation = generation if isinstance(generation, dict) else {}
    return frozen(analysis.get(SCREENING_KEY), analysis if analysis.get('phase') == 'screening' else None,
                  generation.get(SCREENING_KEY))


def carry_screening(analysis, generation=None) -> dict:
    """``{screening_identity: ...}`` to keep on a rewritten analysis record of the same run, or {}."""
    screening = screening_identity(analysis, generation)
    return {SCREENING_KEY: screening} if screening else {}
