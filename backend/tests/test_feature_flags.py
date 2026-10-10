"""Feature snapshots stay enumerable and default off. No network."""
import json
from pathlib import Path

from backend.services.studio import jobs, store
from backend.services.studio.features import DEFAULTS, flag_enabled, resolve_features
from backend.services.studio.models import ImportOptions


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DEFAULTS = json.loads((ROOT / 'frontend/src/analytics/flags.defaults.json').read_text(encoding='utf-8'))


def test_frontend_and_backend_defaults_match_and_are_off():
    assert FRONTEND_DEFAULTS == DEFAULTS
    assert flag_enabled(DEFAULTS, 'remember_platforms') is False
    assert flag_enabled(DEFAULTS, 'one_click_paste_start') is False
    assert flag_enabled(DEFAULTS, 'render_top_first') is False
    assert flag_enabled(DEFAULTS, 'publish_pack_v2') is False
    assert flag_enabled(DEFAULTS, 'pkg_templates_v1') is False
    assert flag_enabled(DEFAULTS, 'pkg_template_picker_visual') is False
    assert resolve_features({'pkg_template_picker_visual': True, 'autoclip_safe_mode': True}, env='')['pkg_template_picker_visual'] is False


def test_qa_and_template_defaults_and_safe_mode():
    """qa_gate_blocking stays shadow and is forced off; pkg_templates_v1 stays off unless the operator names it."""
    assert DEFAULTS['qa_gate_blocking'] == 'shadow'
    assert DEFAULTS['pkg_templates_v1'] is False
    assert FRONTEND_DEFAULTS['qa_gate_blocking'] == 'shadow'
    assert FRONTEND_DEFAULTS['pkg_templates_v1'] is False
    killed = resolve_features({
        'autoclip_safe_mode': True,
        'qa_gate_blocking': 'block',
        'pkg_templates_v1': True,
    })
    assert killed['qa_gate_blocking'] == 'off'
    assert killed['pkg_templates_v1'] is False
    operator = resolve_features(
        {'autoclip_safe_mode': True, 'qa_gate_blocking': 'shadow', 'pkg_templates_v1': True},
        env='qa_gate_blocking=block,pkg_templates_v1=on',
    )
    assert operator['qa_gate_blocking'] == 'off'
    assert operator['pkg_templates_v1'] is True


def test_unknown_values_are_dropped_and_safe_mode_forces_the_safe_off_value():
    resolved = resolve_features({
        'remember_platforms': True,
        'render_top_first': 'top3',
        'one_click_paste_start': 'sometimes',
        'clip_reasons': 'true',
        'title': 'private title',
        'autoclip_safe_mode': True,
    })
    assert resolved['autoclip_safe_mode'] is True
    assert resolved['remember_platforms'] is False
    assert resolved['render_top_first'] == 'limit10'
    assert resolved['clip_reasons'] is False
    assert 'title' not in resolved
    assert 'private' not in json.dumps(resolved)


def test_operator_env_overrides_the_client_snapshot(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_FLAGS', 'render_top_first=top3,not_a_flag=on,notify_on_done=on')
    resolved = resolve_features({'render_top_first': 'limit10', 'remember_platforms': True})
    assert resolved['render_top_first'] == 'top3'
    assert resolved['notify_on_done'] is True
    assert resolved['remember_platforms'] is True
    forced = resolve_features({'autoclip_safe_mode': True, 'remember_platforms': True}, env='clip_reasons=on')
    assert forced['autoclip_safe_mode'] is True
    assert forced['remember_platforms'] is False
    assert forced['clip_reasons'] is True
    monkeypatch.setenv('AUTOCLIP_FLAGS', 'pkg_templates_v1=on')
    enabled = resolve_features({'pkg_templates_v1': False})
    assert enabled['pkg_templates_v1'] is True
    killed = resolve_features({'pkg_templates_v1': True, 'autoclip_safe_mode': True}, env='')
    assert killed['pkg_templates_v1'] is False
    operator = resolve_features({'autoclip_safe_mode': True}, env='pkg_templates_v1=on')
    assert operator['pkg_templates_v1'] is True


def test_import_records_the_resolved_snapshot_and_drops_text(monkeypatch):
    saved = {}
    monkeypatch.delenv('AUTOCLIP_FLAGS', raising=False)
    monkeypatch.setattr(store, 'read', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(store, 'write', lambda _pid, data, **_kwargs: saved.update(generation=data['generation']))
    monkeypatch.setattr(jobs.executor, 'submit', lambda *_args, **_kwargs: None)
    jobs.inspect_project('p1', ImportOptions(auto_start=False, platforms=['original']), features={
        'link_import_without_whisper': True,
        'url': 'https://private.example/watch',
        'render_top_first': 'top3',
    })
    features = saved['generation']['features']
    assert features['link_import_without_whisper'] is True
    assert features['render_top_first'] == 'top3'
    assert features['notify_on_done'] is False
    assert 'url' not in features
    assert 'private' not in json.dumps(features)
