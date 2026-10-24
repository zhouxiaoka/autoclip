"""Behavior tests for the shared provider enum."""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core import event_catalog, llm_telemetry
from backend.core.provider_presets import get_catalog, telemetry_provider_slugs
from backend.services import ai_model_settings as ai
from backend.services.studio import failure_identity
"""telemetry provider enum = every preset in provider_presets.json (+ compatible/other),
one source for backend, frontend and event_catalog.json. No known preset falls into 'other'."""

ROOT = Path(__file__).resolve().parents[2]
PRESET_IDS = list(json.loads((ROOT / 'backend/presets/provider_presets.json').read_text(encoding='utf-8'))['providers'])


def test_catalog_has_all_presets_and_generated_copies_are_fresh():
    assert len(PRESET_IDS) == 40
    assert list(telemetry_provider_slugs()) == PRESET_IDS + ['compatible', 'other']
    done = subprocess.run([sys.executable, str(ROOT / 'scripts/gen_provider_slugs.py'), '--check'], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize('preset', PRESET_IDS)
def test_every_preset_is_its_own_slug_everywhere(preset, monkeypatch):
    assert llm_telemetry.sanitize_provider(preset) == preset
    assert preset in llm_telemetry.TELEMETRY_PROVIDERS
    connection = SimpleNamespace(id='c', provider=preset, base_url=get_catalog().providers[preset].base_url)
    settings = SimpleNamespace(connections=[connection], analysis=SimpleNamespace(connection_id='c', model='m'))
    monkeypatch.setattr(ai, 'load', lambda **k: settings)
    assert failure_identity.provider_identity()['provider'] == preset
    assert event_catalog.validate_event('studio_generation_finished', {
        'outcome': 'error', 'error_code': 'timeout', 'failure_stage': 'analyze', 'provider': preset,
    }) == []


def test_aliases_resolve_and_unknown_is_other(monkeypatch):
    assert llm_telemetry.sanitize_provider('moonshot') == 'kimi'
    assert llm_telemetry.sanitize_provider('my-gateway') is None
    connection = SimpleNamespace(id='c', provider='my-gateway', base_url='https://gw.example')
    monkeypatch.setattr(ai, 'load', lambda **k: SimpleNamespace(connections=[connection], analysis=SimpleNamespace(connection_id='c', model='m')))
    assert failure_identity.provider_identity()['provider'] == 'other'
