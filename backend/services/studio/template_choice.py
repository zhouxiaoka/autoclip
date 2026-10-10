"""Which clips use an HTML template.

Only the three highest-scored clips are eligible. Intel (x86_64) Macs stay on
classic: that path is unverified until a real Intel Mac runs the overlay.
The downgrade reason is ``intel_mac_unverified``.
"""
from __future__ import annotations

import platform
import sys

from backend.services.studio.features import flag_enabled, resolve_features

HTML_CLIP_LIMIT = 3
HTML_TEMPLATES = ('editorial', 'street')
_INTEL = {'x86_64', 'amd64', 'i386'}


def _resolved(features: dict | None) -> dict:
    """Apply the kill switch. A raw snapshot with safe mode on is off."""
    return resolve_features(features if isinstance(features, dict) else None)


def intel_mac_unverified(system: str | None = None, machine: str | None = None) -> bool:
    """x86_64 macOS has not been timed. Those machines render classic."""
    system = sys.platform if system is None else system
    machine = platform.machine() if machine is None else machine
    return system == 'darwin' and machine.lower() in _INTEL


def selected_template(generation: dict | None) -> str | None:
    """The import choice, when the flag is on and it is editorial or street."""
    if not isinstance(generation, dict):
        return None
    if not flag_enabled(_resolved(generation.get('features')), 'pkg_templates_v1'):
        return None
    name = generation.get('html_template')
    return name if name in HTML_TEMPLATES else None


def style_for_request(template: str | None, features: dict | None = None) -> dict[str, str]:
    """The style a request will actually use. Unsupported names raise ValueError."""
    if template not in (None, 'editorial', 'street', 'classic'):
        raise ValueError('不支持的剪辑风格')
    requested = template or 'classic'
    applied = requested if requested in HTML_TEMPLATES and flag_enabled(_resolved(features), 'pkg_templates_v1') else 'classic'
    return {'template': applied, 'requested_template': requested}


def recorded_style(html_template: str | None, requested_template: str | None = None, features: dict | None = None) -> dict[str, str]:
    """What an export job should say it used. The flag-off path stays classic."""
    requested = requested_template if requested_template in ('editorial', 'street', 'classic') else None
    if requested is None and html_template in ('editorial', 'street', 'classic'):
        requested = html_template
    return style_for_request(requested, features)


def style_from_generation(generation: dict | None) -> dict[str, str]:
    """The style already stored for this run, or classic when the flag left the request unused."""
    if isinstance(generation, dict):
        stored = generation.get('template')
        requested = generation.get('requested_template')
        if stored in ('editorial', 'street', 'classic') and requested in ('editorial', 'street', 'classic'):
            return {'template': stored, 'requested_template': requested}
    requested = None
    if isinstance(generation, dict):
        raw = generation.get('requested_template') or generation.get('html_template')
        if raw in ('editorial', 'street', 'classic'):
            requested = raw
    applied = selected_template(generation) or 'classic'
    return {'template': applied, 'requested_template': requested or 'classic'}


def _score(draft: dict) -> float:
    try:
        return float(draft.get('_auto_score'))
    except (TypeError, ValueError):
        return 0.0


def html_candidate_ids(drafts, limit: int = HTML_CLIP_LIMIT) -> set[str]:
    """Ids of the highest-scored clips. Unscored clips are not eligible."""
    scored = [draft for draft in drafts if isinstance(draft, dict) and '_auto_score' in draft and draft.get('id')]
    ordered = sorted(scored, key=_score, reverse=True)
    return {draft['id'] for draft in ordered[: max(0, limit)]}


def blocking_reason(features: dict | None, *, system: str | None = None, machine: str | None = None, runtime_ready: bool | None = None) -> str | None:
    """Why this render must stay on classic. None means the overlay may be captured."""
    if not flag_enabled(_resolved(features), 'pkg_templates_v1'):
        return 'flag_off'
    if intel_mac_unverified(system, machine):
        return 'intel_mac_unverified'
    if runtime_ready is None:
        runtime_ready = runtime_is_ready()
    if not runtime_ready:
        return 'missing_runtime'
    return None


def runtime_is_ready() -> bool:
    try:
        from backend.services.packaging_runtime import is_installed
        return bool(is_installed())
    except Exception:
        return False
